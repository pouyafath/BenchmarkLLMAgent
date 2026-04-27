"""
Patch validation module for detecting malformed unified diff patches.

This module validates patches before application to detect common formatting
issues that cause git apply to fail. It implements 5 critical validation rules
based on RFC 3881 unified diff standard.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ValidationError:
    """Represents a validation error in a patch."""

    type: str  # "truncation", "incomplete_hunk", "missing_eof", "wrong_line_count", "context_mismatch", "file_path"
    location: str  # File path or line number
    message: str
    auto_fixable: bool = False

    def __repr__(self) -> str:
        return f"ValidationError({self.type} at {self.location}: {self.message})"


@dataclass
class ValidationResult:
    """Result of patch validation."""

    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    severity: str = "minor"  # "critical", "fixable", "minor"

    def add_error(self, error: ValidationError):
        """Add an error and update severity."""
        self.errors.append(error)
        self.is_valid = False

        # Update severity based on error type
        if not error.auto_fixable:
            self.severity = "critical"
        elif self.severity != "critical":
            self.severity = "fixable"

    def add_warning(self, warning: str):
        """Add a warning (doesn't invalidate patch)."""
        self.warnings.append(warning)


class PatchValidator:
    """
    Validates unified diff patches to detect malformed formatting.

    Implements 5 validation rules:
    1. Truncation detection - checks for "... (N more lines)" notation
    2. Hunk completeness - verifies hunk line counts match headers
    3. EOF newlines - ensures patch ends with newline
    4. File path validation - checks file paths are valid
    5. Context line validation - ensures sufficient context lines
    """

    # Regex patterns
    TRUNCATION_PATTERN = re.compile(r'\.\.\.\s*\(\d+\s+more\s+lines?\)')
    HUNK_HEADER_PATTERN = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
    DIFF_HEADER_PATTERN = re.compile(r'^diff --git a/(.+) b/(.+)$')
    FILE_HEADER_PATTERN = re.compile(r'^(---|\+\+\+) (?:a/|b/)?(.+)$')

    def validate(self, patch: str, file_list: Optional[List[str]] = None) -> ValidationResult:
        """
        Validate a unified diff patch.

        Args:
            patch: The patch content as string
            file_list: Optional list of expected file paths

        Returns:
            ValidationResult with validation status and errors
        """
        if file_list is None:
            file_list = []

        result = ValidationResult(is_valid=True)

        if not patch or not patch.strip():
            result.add_error(ValidationError(
                type="empty_patch",
                location="",
                message="Patch is empty",
                auto_fixable=False
            ))
            return result

        # Rule 1: Check for truncation
        self._check_truncation(patch, result)

        # Rule 2: Check hunk completeness and line counts
        self._check_hunk_completeness(patch, result)

        # Rule 3: Check EOF newline
        self._check_eof_newlines(patch, result)

        # Rule 4: Check file paths
        if file_list:
            self._check_file_paths(patch, file_list, result)

        # Rule 5: Check context lines
        self._check_context_lines(patch, result)

        # Rule 6: Check syntax completeness (enhanced validation)
        self._check_syntax_completeness(patch, result)

        return result

    def _check_truncation(self, patch: str, result: ValidationResult):
        """
        Rule 1: Detect literal "... (N more lines)" truncation.

        This is CRITICAL - cannot auto-fix, requires regeneration.
        """
        matches = self.TRUNCATION_PATTERN.findall(patch)
        if matches:
            for match in matches:
                line_num = patch[:patch.find(match)].count('\n') + 1
                result.add_error(ValidationError(
                    type="truncation",
                    location=f"line {line_num}",
                    message=f"Found invalid truncation notation '{match}'. "
                            "Unified diff requires all lines to be written explicitly.",
                    auto_fixable=False
                ))

    def _check_hunk_completeness(self, patch: str, result: ValidationResult):
        """
        Rule 2: Verify hunk line counts match @@ headers.

        This is FIXABLE - can recalculate line counts.
        """
        hunks = self._extract_hunks(patch)

        for hunk_info in hunks:
            hunk_text = hunk_info['text']
            header_match = hunk_info['header_match']
            file_path = hunk_info['file_path']

            # Extract line counts from header
            old_start = int(header_match.group(1))
            old_count = int(header_match.group(2)) if header_match.group(2) else 1
            new_start = int(header_match.group(3))
            new_count = int(header_match.group(4)) if header_match.group(4) else 1

            # Count actual lines in hunk
            hunk_lines = hunk_text.split('\n')[1:]  # Skip header line
            actual_old_count = 0
            actual_new_count = 0

            for line in hunk_lines:
                if not line:  # Empty line at end
                    continue
                if line.startswith(' '):  # Context line
                    actual_old_count += 1
                    actual_new_count += 1
                elif line.startswith('-'):  # Deletion
                    actual_old_count += 1
                elif line.startswith('+'):  # Addition
                    actual_new_count += 1
                elif line.startswith('\\'):  # "\ No newline" marker
                    continue

            # Check if counts match
            if old_count != actual_old_count or new_count != actual_new_count:
                result.add_error(ValidationError(
                    type="wrong_line_count",
                    location=f"{file_path}:@@ -{old_start},{old_count} +{new_start},{new_count} @@",
                    message=f"Hunk header declares {old_count}/{new_count} lines but "
                            f"actually has {actual_old_count}/{actual_new_count} lines",
                    auto_fixable=True
                ))

    def _check_eof_newlines(self, patch: str, result: ValidationResult):
        """
        Rule 3: Ensure patch ends with newline.

        This is FIXABLE - can add newline.
        """
        if not patch.endswith('\n'):
            # Check if it's the special "no newline" marker
            if not patch.endswith('\\ No newline at end of file'):
                result.add_error(ValidationError(
                    type="missing_eof_newline",
                    location="end of patch",
                    message="Patch must end with a newline character",
                    auto_fixable=True
                ))

    def _check_file_paths(self, patch: str, file_list: List[str], result: ValidationResult):
        """
        Rule 4: Verify file paths in patch match expected files.

        This is INFO - the _fix_patch_paths() function handles this.
        """
        # Extract file paths from diff headers
        patch_files = set()
        for line in patch.split('\n'):
            match = self.DIFF_HEADER_PATTERN.match(line)
            if match:
                # Extract filename (same in both a/ and b/ in most cases)
                patch_files.add(match.group(1))

        # Check for mismatches (just warnings, not errors)
        if file_list and patch_files:
            for patch_file in patch_files:
                if patch_file not in file_list and not any(f.endswith(patch_file) for f in file_list):
                    result.add_warning(
                        f"File '{patch_file}' in patch not found in expected file list. "
                        "May need path correction."
                    )

    def _check_context_lines(self, patch: str, result: ValidationResult):
        """
        Rule 5: Check for sufficient trailing context lines in each hunk.

        Each hunk should have 3+ context lines after changes.
        This is CRITICAL if missing - indicates incomplete hunk.
        """
        hunks = self._extract_hunks(patch)

        for hunk_info in hunks:
            hunk_text = hunk_info['text']
            file_path = hunk_info['file_path']

            # Get hunk lines (skip header)
            hunk_lines = hunk_text.split('\n')[1:]

            # Find last non-empty, non-marker line
            last_lines = []
            for line in reversed(hunk_lines):
                if line and not line.startswith('\\'):
                    last_lines.insert(0, line)
                    if len(last_lines) >= 3:
                        break

            # Check if last 3 lines are context lines
            if len(last_lines) >= 3:
                trailing_context = sum(1 for line in last_lines[:3] if line.startswith(' '))
                if trailing_context < 3:
                    result.add_warning(
                        f"Hunk in {file_path} has only {trailing_context} trailing context lines. "
                        "Recommend 3+ for robustness."
                    )
            else:
                # Hunk too short - may be incomplete
                if len(hunk_lines) > 0 and not all(line.startswith(' ') for line in last_lines if line):
                    result.add_error(ValidationError(
                        type="incomplete_hunk",
                        location=file_path,
                        message="Hunk appears incomplete - insufficient trailing context",
                        auto_fixable=False
                    ))

    def _check_syntax_completeness(self, patch: str, result: ValidationResult):
        """
        Rule 6: Check for incomplete syntax in patch lines.

        Detects common syntax errors:
        - Unbalanced parentheses, brackets, braces
        - Unclosed string literals
        - Incomplete function definitions
        - Truncated lines (ending with operators like +, -, *, etc.)

        This helps catch cases where LLM generated syntactically incomplete code.
        """
        hunks = self._extract_hunks(patch)

        for hunk_info in hunks:
            hunk_text = hunk_info['text']
            file_path = hunk_info['file_path']
            hunk_lines = hunk_text.split('\n')[1:]  # Skip header

            # Track bracket/paren balance for added/changed lines
            for i, line in enumerate(hunk_lines):
                if not line or line.startswith('\\'):
                    continue

                # Only check added or modified lines
                if not (line.startswith('+') or line.startswith('-')):
                    continue

                content = line[1:]  # Remove +/- prefix

                # Check for unbalanced brackets on single line
                # (Simplistic check - doesn't handle multi-line constructs perfectly)
                if content.strip():
                    parens = content.count('(') - content.count(')')
                    brackets = content.count('[') - content.count(']')
                    braces = content.count('{') - content.count('}')

                    # Allow imbalance for multi-line constructs, but detect obvious errors
                    if abs(parens) > 3 or abs(brackets) > 2 or abs(braces) > 2:
                        result.add_warning(
                            f"Potential unbalanced brackets in {file_path} line {i+1}: "
                            f"({parens:+d} parens, {brackets:+d} brackets, {braces:+d} braces)"
                        )

                    # Check for incomplete function definitions (missing colon in Python-like)
                    if file_path.endswith(('.py', '.pyx')) and 'def ' in content:
                        # Simple heuristic: function def should end with : or continue on next line
                        if content.strip().startswith('def ') and not content.rstrip().endswith((':',  ',')):
                            if not content.rstrip().endswith('\\'):
                                result.add_warning(
                                    f"Possible incomplete function definition in {file_path} line {i+1}"
                                )

                    # Check for lines ending with binary operators (likely truncated)
                    if content.rstrip() and content.rstrip()[-1] in ('+', '-', '*', '/', '=', '&', '|', ','):
                        # Allow if it's clearly intentional (e.g., multi-line expression)
                        if not content.rstrip().endswith(('\\', ',=')):
                            result.add_warning(
                                f"Line in {file_path} ends with operator '{content.rstrip()[-1]}' - may be truncated"
                            )

    def _extract_hunks(self, patch: str) -> List[dict]:
        """
        Extract all hunks from patch with metadata.

        Returns:
            List of dicts with keys: 'text', 'header_match', 'file_path'
        """
        hunks = []
        current_file = "unknown"
        lines = patch.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Track current file
            diff_match = self.DIFF_HEADER_PATTERN.match(line)
            if diff_match:
                current_file = diff_match.group(1)
                i += 1
                continue

            # Find hunk headers
            hunk_match = self.HUNK_HEADER_PATTERN.match(line)
            if hunk_match:
                # Extract this hunk until next hunk or file
                hunk_lines = [line]
                i += 1

                while i < len(lines):
                    next_line = lines[i]

                    # Stop at next hunk or diff header
                    if self.HUNK_HEADER_PATTERN.match(next_line) or \
                       self.DIFF_HEADER_PATTERN.match(next_line):
                        break

                    hunk_lines.append(next_line)
                    i += 1

                hunks.append({
                    'text': '\n'.join(hunk_lines),
                    'header_match': hunk_match,
                    'file_path': current_file
                })
                continue

            i += 1

        return hunks


# Convenience function for quick validation
def validate_patch(patch: str, file_list: Optional[List[str]] = None) -> ValidationResult:
    """
    Quick validation function.

    Args:
        patch: Patch content
        file_list: Optional list of expected files

    Returns:
        ValidationResult
    """
    validator = PatchValidator()
    return validator.validate(patch, file_list)
