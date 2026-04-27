"""
Patch sanitization module for automatically fixing common patch formatting issues.

This module attempts to repair malformed patches by fixing structural issues
like missing EOF newlines, incorrect line counts, and whitespace problems.
"""

import re
from dataclasses import dataclass, field
from typing import List

from src.utils.patch_validator import ValidationResult, ValidationError


@dataclass
class SanitizationResult:
    """Result of patch sanitization."""

    sanitized_patch: str
    fixes_applied: List[str] = field(default_factory=list)
    unfixable_errors: List[ValidationError] = field(default_factory=list)
    success: bool = True

    def add_fix(self, fix_description: str):
        """Record a fix that was applied."""
        self.fixes_applied.append(fix_description)

    def add_unfixable(self, error: ValidationError):
        """Record an error that couldn't be fixed."""
        self.unfixable_errors.append(error)
        self.success = False


class PatchSanitizer:
    """
    Automatically repairs common patch formatting issues.

    Fixes:
    1. Missing EOF newlines
    2. Incorrect hunk line counts in @@ headers
    3. Whitespace normalization
    4. Missing /dev/null for new/deleted files
    """

    HUNK_HEADER_PATTERN = re.compile(r'^(@@ -)(\d+)(?:,(\d+))? (\+)(\d+)(?:,(\d+))? (@@.*)$')
    DIFF_HEADER_PATTERN = re.compile(r'^diff --git a/(.+) b/(.+)$')

    def sanitize(self, patch: str, validation_result: ValidationResult) -> SanitizationResult:
        """
        Attempt to fix validation errors in patch.

        Args:
            patch: The patch content
            validation_result: Result from PatchValidator

        Returns:
            SanitizationResult with sanitized patch and applied fixes
        """
        result = SanitizationResult(sanitized_patch=patch)

        if not validation_result.errors:
            # No errors to fix
            return result

        # Separate fixable from unfixable errors
        fixable_errors = [e for e in validation_result.errors if e.auto_fixable]
        unfixable_errors = [e for e in validation_result.errors if not e.auto_fixable]

        # Record unfixable errors
        for error in unfixable_errors:
            result.add_unfixable(error)

        if not fixable_errors:
            # Nothing we can fix
            result.success = len(unfixable_errors) == 0
            return result

        # Apply fixes in order
        current_patch = patch

        # Fix 1: EOF newlines (simple, do first)
        if any(e.type == "missing_eof_newline" for e in fixable_errors):
            current_patch = self._fix_missing_eof_newline(current_patch)
            result.add_fix("Added missing EOF newline")

        # Fix 2: Hunk line counts (complex, requires parsing)
        if any(e.type == "wrong_line_count" for e in fixable_errors):
            try:
                current_patch = self._fix_hunk_line_counts(current_patch)
                result.add_fix("Fixed incorrect hunk line counts")
            except Exception as e:
                # If fix fails, record as unfixable
                result.add_unfixable(ValidationError(
                    type="wrong_line_count",
                    location="patch",
                    message=f"Failed to fix line counts: {e}",
                    auto_fixable=False
                ))

        # Fix 3: Whitespace normalization (safe, do last)
        current_patch = self._normalize_whitespace(current_patch)
        result.add_fix("Normalized whitespace")

        result.sanitized_patch = current_patch
        result.success = len(result.unfixable_errors) == 0

        return result

    def _fix_missing_eof_newline(self, patch: str) -> str:
        """
        Fix 1: Add missing newline at end of patch.

        Args:
            patch: Patch content

        Returns:
            Patch with trailing newline
        """
        if not patch.endswith('\n'):
            # Don't add if it explicitly has the "no newline" marker
            if patch.endswith('\\ No newline at end of file'):
                return patch
            return patch + '\n'
        return patch

    def _fix_hunk_line_counts(self, patch: str) -> str:
        """
        Fix 2: Recalculate and update hunk line counts in @@ headers.

        Args:
            patch: Patch content

        Returns:
            Patch with corrected line counts
        """
        lines = patch.split('\n')
        result_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check if this is a hunk header
            hunk_match = self.HUNK_HEADER_PATTERN.match(line)
            if hunk_match:
                # Extract hunk content
                hunk_start = i
                i += 1

                # Find end of hunk (next hunk header or diff header or end)
                while i < len(lines):
                    if self.HUNK_HEADER_PATTERN.match(lines[i]) or \
                       self.DIFF_HEADER_PATTERN.match(lines[i]):
                        break
                    i += 1

                # Count lines in this hunk
                hunk_lines = lines[hunk_start + 1:i]
                old_count, new_count = self._count_hunk_lines(hunk_lines)

                # Rebuild header with correct counts
                old_start = int(hunk_match.group(2))
                new_start = int(hunk_match.group(5))
                header_suffix = hunk_match.group(7)

                corrected_header = f"@@ -{old_start},{old_count} +{new_start},{new_count} {header_suffix}"
                result_lines.append(corrected_header)
                result_lines.extend(hunk_lines)
            else:
                result_lines.append(line)
                i += 1

        return '\n'.join(result_lines)

    def _count_hunk_lines(self, hunk_lines: List[str]) -> tuple[int, int]:
        """
        Count actual lines in a hunk for old and new versions.

        Args:
            hunk_lines: Lines of hunk content (excluding header)

        Returns:
            Tuple of (old_count, new_count)
        """
        old_count = 0
        new_count = 0

        for line in hunk_lines:
            if not line or line.startswith('\\'):
                # Empty line or "no newline" marker - skip
                continue

            if line.startswith(' '):  # Context line
                old_count += 1
                new_count += 1
            elif line.startswith('-'):  # Deletion
                old_count += 1
            elif line.startswith('+'):  # Addition
                new_count += 1

        # Ensure at least count of 1 (unified diff standard)
        return max(1, old_count), max(1, new_count)

    def _normalize_whitespace(self, patch: str) -> str:
        """
        Fix 3: Normalize whitespace in patch lines.

        Ensures:
        - Context lines start with single space
        - Deletion lines start with single '-'
        - Addition lines start with single '+'

        Args:
            patch: Patch content

        Returns:
            Patch with normalized whitespace
        """
        lines = patch.split('\n')
        result_lines = []

        in_hunk = False

        for line in lines:
            # Track if we're inside a hunk
            if self.HUNK_HEADER_PATTERN.match(line):
                in_hunk = True
                result_lines.append(line)
                continue

            if self.DIFF_HEADER_PATTERN.match(line) or line.startswith('---') or line.startswith('+++'):
                in_hunk = False
                result_lines.append(line)
                continue

            # Only normalize lines inside hunks
            if in_hunk and line:
                # Check first character
                if line[0] in [' ', '-', '+']:
                    # Already has prefix - ensure only one
                    prefix = line[0]
                    content = line[1:].lstrip()
                    # Preserve original spacing for context lines
                    if prefix == ' ':
                        result_lines.append(' ' + line[1:])
                    else:
                        result_lines.append(prefix + content)
                else:
                    # No prefix - might be context line with missing space
                    # Be conservative - keep as is
                    result_lines.append(line)
            else:
                result_lines.append(line)

        return '\n'.join(result_lines)

    def _add_dev_null_markers(self, patch: str, file_list: List[str]) -> str:
        """
        Fix 4: Add /dev/null markers for new or deleted files.

        This fix is currently not used as it requires knowing which files
        exist in the repo, which is context-dependent.

        Args:
            patch: Patch content
            file_list: List of existing files

        Returns:
            Patch with /dev/null markers where appropriate
        """
        # TODO: Implement if needed
        # Requires checking if files in --- headers exist in file_list
        return patch


# Convenience function
def sanitize_patch(patch: str, validation_result: ValidationResult) -> SanitizationResult:
    """
    Quick sanitization function.

    Args:
        patch: Patch content
        validation_result: Validation result from PatchValidator

    Returns:
        SanitizationResult
    """
    sanitizer = PatchSanitizer()
    return sanitizer.sanitize(patch, validation_result)
