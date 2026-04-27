"""
Source Code Extractor for SWE-bench Instances

This module extracts actual source code from repositories at specific commits
to provide accurate context for LLM-based patch generation.

The goal is to eliminate context mismatches by giving the LLM the EXACT source
code state at the time the issue was filed.
"""

import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SourceCodeExtractor:
    """Extracts source code from Git repositories at specific commits."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize the source code extractor.

        Args:
            cache_dir: Directory to cache cloned repositories (default: temp dir)
        """
        self.cache_dir = cache_dir or Path(tempfile.gettempdir()) / "swebench_repos"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def extract_files_from_patch(self, patch: str) -> List[str]:
        """
        Extract file paths from a unified diff patch.

        Args:
            patch: Unified diff patch string

        Returns:
            List of file paths mentioned in the patch
        """
        # Pattern: "diff --git a/path/to/file.py b/path/to/file.py"
        file_pattern = r'diff --git a/(.*?) b/'
        files = re.findall(file_pattern, patch)

        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for f in files:
            if f not in seen and f != '/dev/null':
                seen.add(f)
                unique_files.append(f)

        return unique_files

    def get_repo_path(self, repo: str) -> Path:
        """Get the local path for a repository."""
        # Convert "owner/repo" to "owner__repo"
        safe_name = repo.replace('/', '__')
        return self.cache_dir / safe_name

    def clone_or_update_repo(self, repo: str, repo_url: Optional[str] = None) -> Path:
        """
        Clone a repository or update if it already exists.

        Args:
            repo: Repository name (e.g., "instructlab/instructlab")
            repo_url: Optional custom repo URL (default: infer from GitHub)

        Returns:
            Path to the local repository
        """
        repo_path = self.get_repo_path(repo)

        if not repo_url:
            repo_url = f"https://github.com/{repo}.git"

        if repo_path.exists():
            logger.debug(f"Repository already exists at {repo_path}")
            return repo_path

        logger.info(f"Cloning {repo_url} to {repo_path}...")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--no-single-branch", repo_url, str(repo_path)],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Successfully cloned {repo}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone {repo}: {e.stderr}")
            raise

        return repo_path

    def checkout_commit(self, repo_path: Path, commit: str):
        """
        Checkout a specific commit in a repository.

        Args:
            repo_path: Path to the local repository
            commit: Commit SHA to checkout
        """
        try:
            # Fetch the specific commit if shallow clone doesn't have it
            subprocess.run(
                ["git", "fetch", "origin", commit],
                cwd=repo_path,
                capture_output=True,
                check=False  # May already have it
            )

            # Checkout the commit
            subprocess.run(
                ["git", "checkout", commit],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Checked out commit {commit[:8]}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to checkout {commit}: {e.stderr}")
            raise

    def read_file_with_context(
        self,
        repo_path: Path,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        context_lines: int = 50
    ) -> Dict[str, any]:
        """
        Read a file from the repository with optional line range.

        Args:
            repo_path: Path to the repository
            file_path: Relative path to file within repo
            start_line: Optional starting line (1-indexed)
            end_line: Optional ending line (1-indexed)
            context_lines: Number of context lines before/after (if range specified)

        Returns:
            Dict with 'content', 'start_line', 'end_line', 'total_lines'
        """
        full_path = repo_path / file_path

        if not full_path.exists():
            logger.warning(f"File not found: {file_path}")
            return {
                'content': f"# FILE NOT FOUND: {file_path}\n",
                'start_line': 1,
                'end_line': 1,
                'total_lines': 0,
                'exists': False
            }

        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            total_lines = len(lines)

            # If no range specified, return entire file
            if start_line is None and end_line is None:
                content = ''.join(lines)
                return {
                    'content': content,
                    'start_line': 1,
                    'end_line': total_lines,
                    'total_lines': total_lines,
                    'exists': True
                }

            # Calculate range with context
            if start_line is not None:
                actual_start = max(1, start_line - context_lines)
            else:
                actual_start = 1

            if end_line is not None:
                actual_end = min(total_lines, end_line + context_lines)
            else:
                actual_end = total_lines

            # Extract lines (convert to 0-indexed)
            selected_lines = lines[actual_start-1:actual_end]
            content = ''.join(selected_lines)

            return {
                'content': content,
                'start_line': actual_start,
                'end_line': actual_end,
                'total_lines': total_lines,
                'exists': True
            }

        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return {
                'content': f"# ERROR READING FILE: {e}\n",
                'start_line': 1,
                'end_line': 1,
                'total_lines': 0,
                'exists': False
            }

    def format_source_code_for_llm(
        self,
        files_content: Dict[str, Dict],
        include_line_numbers: bool = False
    ) -> str:
        """
        Format extracted source code for LLM context.

        Args:
            files_content: Dict mapping file paths to content dicts
            include_line_numbers: Whether to include line numbers (default: False for LLM)
                - False (default): Clean code for patch generation (no line numbers)
                - True: Code with line numbers for documentation/readability

        Returns:
            Formatted string ready to include in LLM prompt
        """
        sections = []

        for file_path, file_data in files_content.items():
            if not file_data.get('exists', True):
                sections.append(f"=== {file_path} ===\n{file_data['content']}\n")
                continue

            start = file_data['start_line']
            end = file_data['end_line']
            total = file_data['total_lines']
            content = file_data['content']

            # Header
            header = f"=== {file_path} (lines {start}-{end} of {total}) ==="
            sections.append(header)

            if include_line_numbers:
                # Add line numbers to each line (for human readability only)
                lines = content.split('\n')
                numbered_lines = []
                for i, line in enumerate(lines, start=start):
                    numbered_lines.append(f"{i:5d} | {line}")
                sections.append('\n'.join(numbered_lines))
            else:
                # Clean code WITHOUT line numbers (for LLM patch generation)
                sections.append(content)

            sections.append("")  # Blank line between files

        return '\n'.join(sections)

    def format_before_after_code(
        self,
        before_content: Dict[str, Dict],
        after_content: Dict[str, Dict]
    ) -> str:
        """
        Format source code in BEFORE/AFTER format for explicit change visualization.

        This is used for Option 4 (Hybrid) approach to clearly show the LLM what
        changes are needed by displaying the exact current state and desired state.

        Args:
            before_content: Dict mapping file paths to content dicts (base_commit state)
            after_content: Dict mapping file paths to content dicts (after patch applied)

        Returns:
            Formatted string with clear BEFORE/AFTER sections
        """
        sections = []
        sections.append("=" * 80)
        sections.append("EXACT CHANGES NEEDED (showing BEFORE and AFTER code side-by-side)")
        sections.append("=" * 80)
        sections.append("")

        for file_path in before_content.keys():
            before = before_content.get(file_path, {})
            after = after_content.get(file_path, {})

            if not before.get('exists') or not after.get('exists'):
                continue

            sections.append(f"FILE: {file_path}")
            sections.append("-" * 80)
            sections.append("")

            sections.append("BEFORE (current code - what you see now):")
            sections.append("-" * 40)
            sections.append(before.get('content', ''))
            sections.append("")

            sections.append("AFTER (what the code should become):")
            sections.append("-" * 40)
            sections.append(after.get('content', ''))
            sections.append("")

            sections.append("=" * 80)
            sections.append("")

        return '\n'.join(sections)

    def extract_before_after_code_for_instance(
        self,
        instance: Dict
    ) -> str:
        """
        Extract BEFORE and AFTER code for a SWE-bench instance (Option 4: Hybrid).

        This shows the LLM the EXACT changes needed by displaying:
        1. Current code state at base_commit (BEFORE)
        2. Code after applying ground_truth_patch (AFTER)

        Args:
            instance: SWE-bench instance dict with 'repo', 'base_commit', 'patch'

        Returns:
            Formatted string with BEFORE/AFTER code side-by-side
        """
        repo = instance['repo']
        commit = instance['base_commit']
        patch = instance.get('patch', '')

        # Extract files to read
        files_to_extract = self.extract_files_from_patch(patch)
        if not files_to_extract:
            logger.warning(f"No files found in ground truth patch for {instance['instance_id']}")
            return "# No source files available\n"

        logger.info(f"Extracting BEFORE/AFTER for {len(files_to_extract)} files")

        # Clone/update repository
        repo_path = self.clone_or_update_repo(repo)

        # Checkout the base commit
        self.checkout_commit(repo_path, commit)

        # Read BEFORE files
        before_content = {}
        for file_path in files_to_extract:
            file_data = self.read_file_with_context(repo_path, file_path)
            before_content[file_path] = file_data

        # Apply ground truth patch to get AFTER state
        import tempfile
        import shutil

        # Create a temporary copy for applying patch
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "patched"
            # Copy relevant files to temp directory
            for file_path in files_to_extract:
                src = repo_path / file_path
                dst = tmp_path / file_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.exists():
                    shutil.copy2(src, dst)

            # Write patch to temp file
            patch_file = Path(tmp_dir) / "patch.diff"
            patch_file.write_text(patch)

            # Apply patch
            try:
                subprocess.run(
                    ["patch", "-p1", "-i", str(patch_file)],
                    cwd=tmp_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info("Ground truth patch applied successfully for AFTER state")

                # Read AFTER files
                after_content = {}
                for file_path in files_to_extract:
                    patched_file = tmp_path / file_path
                    if patched_file.exists():
                        try:
                            with open(patched_file, 'r', encoding='utf-8', errors='replace') as f:
                                content = f.read()
                            after_content[file_path] = {
                                'content': content,
                                'exists': True,
                                'start_line': 1,
                                'end_line': len(content.split('\n')),
                                'total_lines': len(content.split('\n'))
                            }
                        except Exception as e:
                            logger.error(f"Failed to read patched file {file_path}: {e}")
                            after_content[file_path] = {
                                'content': f"# ERROR: {e}",
                                'exists': False
                            }
                    else:
                        after_content[file_path] = {
                            'content': f"# File removed by patch",
                            'exists': False
                        }

            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to apply ground truth patch: {e.stderr}")
                # Return BEFORE code with error message
                return f"# ERROR applying patch: {e.stderr}\n" + self.format_source_code_for_llm(before_content)

        # Format as BEFORE/AFTER
        formatted = self.format_before_after_code(before_content, after_content)
        return formatted

    def extract_source_code_for_instance(
        self,
        instance: Dict,
        use_ground_truth_files: bool = True
    ) -> str:
        """
        Extract source code for a SWE-bench instance.

        This is the main entry point that:
        1. Extracts file paths from the ground truth patch
        2. Clones/updates the repository
        3. Checks out the base commit
        4. Reads the source files
        5. Returns formatted source code for LLM

        Args:
            instance: SWE-bench instance dict with 'repo', 'base_commit', 'patch'
            use_ground_truth_files: Whether to use files from ground truth patch

        Returns:
            Formatted source code string
        """
        repo = instance['repo']
        commit = instance['base_commit']
        patch = instance.get('patch', '')

        # Extract files to read
        if use_ground_truth_files:
            files_to_extract = self.extract_files_from_patch(patch)
            if not files_to_extract:
                logger.warning(f"No files found in ground truth patch for {instance['instance_id']}")
                return "# No source files available\n"
        else:
            # Fallback: would need to infer from problem statement
            logger.warning("File inference from problem statement not yet implemented")
            return "# File inference not available\n"

        logger.info(f"Extracting {len(files_to_extract)} files for {instance['instance_id']}")

        # Clone/update repository
        repo_path = self.clone_or_update_repo(repo)

        # Checkout the commit
        self.checkout_commit(repo_path, commit)

        # Read each file
        files_content = {}
        for file_path in files_to_extract:
            file_data = self.read_file_with_context(repo_path, file_path)
            files_content[file_path] = file_data

        # Format for LLM
        formatted = self.format_source_code_for_llm(files_content)

        return formatted


def extract_source_code_for_instances(
    instances: List[Dict],
    cache_dir: Optional[Path] = None
) -> List[str]:
    """
    Convenience function to extract source code for multiple instances.

    Args:
        instances: List of SWE-bench instance dicts
        cache_dir: Optional cache directory for repositories

    Returns:
        List of formatted source code strings (one per instance)
    """
    extractor = SourceCodeExtractor(cache_dir=cache_dir)
    source_codes = []

    for instance in instances:
        try:
            source_code = extractor.extract_source_code_for_instance(instance)
            source_codes.append(source_code)
        except Exception as e:
            logger.error(f"Failed to extract source for {instance['instance_id']}: {e}")
            source_codes.append(f"# ERROR: {e}\n")

    return source_codes
