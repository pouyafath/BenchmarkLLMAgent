"""
Code-context enhancer: adds real codebase information to issue descriptions.

Unlike LLM-based enhancers that paraphrase, this deterministic enhancer reads
actual source code from Docker containers and dataset metadata (hints, failing
tests) to give the solver concrete, actionable context.

Environment variables:
  CODE_CONTEXT_DATASET_JSONL      — path to dataset JSONL (required)
  CODE_CONTEXT_INCLUDE_SOURCE     — include source file content (default: 1)
  CODE_CONTEXT_INCLUDE_HINTS      — include hints_text (default: 1)
  CODE_CONTEXT_INCLUDE_FAILING_TESTS — include FAIL_TO_PASS test names (default: 1)
  CODE_CONTEXT_INCLUDE_TEST_PATCH — include test_patch code (default: 0)
  CODE_CONTEXT_INCLUDE_P2P_TESTS  — include PASS_TO_PASS test names (default: 0)
  CODE_CONTEXT_MAX_LINES_PER_FILE — max source lines per file (default: 200)
  CODE_CONTEXT_MAX_TOTAL_CHARS    — max total chars for context (default: 25000)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict

# ── configuration via env ────────────────────────────────────────────────────
_DATASET_JSONL = os.environ.get("CODE_CONTEXT_DATASET_JSONL", "")
_INCLUDE_SOURCE = os.environ.get("CODE_CONTEXT_INCLUDE_SOURCE", "1") == "1"
_INCLUDE_HINTS = os.environ.get("CODE_CONTEXT_INCLUDE_HINTS", "1") == "1"
_INCLUDE_FAILING_TESTS = os.environ.get("CODE_CONTEXT_INCLUDE_FAILING_TESTS", "1") == "1"
_INCLUDE_TEST_PATCH = os.environ.get("CODE_CONTEXT_INCLUDE_TEST_PATCH", "0") == "1"
_INCLUDE_P2P_TESTS = os.environ.get("CODE_CONTEXT_INCLUDE_P2P_TESTS", "0") == "1"
_MAX_LINES_PER_FILE = int(os.environ.get("CODE_CONTEXT_MAX_LINES_PER_FILE", "200"))
_MAX_TOTAL_CHARS = int(os.environ.get("CODE_CONTEXT_MAX_TOTAL_CHARS", "25000"))

# ── JSONL cache (loaded once per process) ────────────────────────────────────
_jsonl_cache: dict[str, dict] | None = None


def _load_jsonl() -> dict[str, dict]:
    """Load the dataset JSONL and index by instance_id."""
    global _jsonl_cache
    if _jsonl_cache is not None:
        return _jsonl_cache

    if not _DATASET_JSONL:
        raise ValueError(
            "CODE_CONTEXT_DATASET_JSONL env var not set. "
            "Set it to the path of the dataset JSONL file."
        )
    path = Path(_DATASET_JSONL)
    if not path.exists():
        raise FileNotFoundError(f"Dataset JSONL not found: {path}")

    rows: dict[str, dict] = {}
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            iid = row.get("instance_id", "")
            if iid:
                rows[iid] = row
    _jsonl_cache = rows
    return rows


def _parse_filenames_from_patch(patch: str) -> list[str]:
    """Extract unique filenames from a unified-diff patch."""
    filenames = []
    seen: set[str] = set()
    for line in patch.splitlines():
        m = re.match(r"^diff --git a/(.+?) b/(.+)$", line)
        if m:
            fn = m.group(2)
            if fn not in seen:
                seen.add(fn)
                filenames.append(fn)
    return filenames


def _detect_language(filename: str) -> str:
    """Guess language from file extension for syntax highlighting."""
    ext = Path(filename).suffix.lower()
    lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".java": "java", ".c": "c", ".cpp": "cpp", ".h": "c",
        ".rs": "rust", ".go": "go", ".rb": "ruby", ".yaml": "yaml",
        ".yml": "yaml", ".json": "json", ".toml": "toml", ".md": "markdown",
    }
    return lang_map.get(ext, "")


def _read_source_files(
    image_name: str,
    filenames: list[str],
    max_lines_per_file: int = _MAX_LINES_PER_FILE,
) -> dict[str, str]:
    """Read source files from Docker container at /testbed."""
    sources: dict[str, str] = {}
    for filename in filenames:
        try:
            result = subprocess.run(
                ["docker", "run", "--rm", image_name, "cat", f"/testbed/{filename}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.splitlines()[:max_lines_per_file]
                sources[filename] = "\n".join(lines)
        except (subprocess.TimeoutExpired, Exception):
            continue
    return sources


def _build_source_section(sources: dict[str, str]) -> str:
    """Build the source code context section."""
    if not sources:
        return ""
    parts = ["## Code Context (source files at base commit)\n"]
    for filename, content in sources.items():
        lang = _detect_language(filename)
        parts.append(f"### File: `{filename}`")
        parts.append(f"```{lang}")
        parts.append(content)
        parts.append("```\n")
    return "\n".join(parts)


def _build_hints_section(hints_text: str) -> str:
    """Build the developer hints section."""
    if not hints_text or not hints_text.strip():
        return ""
    return f"## Developer Notes\n\n{hints_text.strip()}\n"


def _build_failing_tests_section(fail_to_pass: list[str]) -> str:
    """Build the failing tests section."""
    if not fail_to_pass:
        return ""
    items = "\n".join(f"- `{t}`" for t in fail_to_pass)
    return f"## Failing Tests\n\nThe following tests should pass after the fix:\n{items}\n"


def _build_test_patch_section(test_patch: str) -> str:
    """Build the test specification section."""
    if not test_patch or not test_patch.strip():
        return ""
    return f"## Test Specification\n\n```diff\n{test_patch.strip()}\n```\n"


def _build_p2p_tests_section(pass_to_pass: list[str], max_tests: int = 20) -> str:
    """Build the regression tests section."""
    if not pass_to_pass:
        return ""
    shown = pass_to_pass[:max_tests]
    items = "\n".join(f"- `{t}`" for t in shown)
    extra = f"\n- *(… and {len(pass_to_pass) - max_tests} more)*" if len(pass_to_pass) > max_tests else ""
    return (
        f"## Regression Tests (Must Continue Passing)\n\n"
        f"The following {len(pass_to_pass)} tests currently pass and must not break:\n"
        f"{items}{extra}\n"
    )


def _truncate_context(sections: list[str], max_chars: int) -> str:
    """Join sections, truncating if total exceeds max_chars."""
    combined = "\n---\n".join(s for s in sections if s)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n\n... (truncated to fit context limit)\n"
    return combined


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    """Enhance issue by adding real code context from Docker and dataset metadata."""
    title = issue.get("title") or issue.get("instance_id") or ""
    body = issue.get("body") or issue.get("problem_statement") or ""
    instance_id = issue.get("instance_id", "")

    if not instance_id:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "code_context",
                "error": "No instance_id in issue dict",
            },
        }

    # Load dataset row
    try:
        jsonl_data = _load_jsonl()
    except Exception as e:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "code_context",
                "error": f"Failed to load JSONL: {e}",
            },
        }

    row = jsonl_data.get(instance_id)
    if not row:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "code_context",
                "error": f"instance_id {instance_id!r} not found in JSONL",
            },
        }

    # Extract fields from dataset row
    image_name = row.get("image_name", "")
    patch = row.get("patch", "")
    hints_text = row.get("hints_text", "") or row.get("all_hints_text", "") or ""
    fail_to_pass = row.get("FAIL_TO_PASS", [])
    test_patch = row.get("test_patch", "")

    # Determine source filenames from the ground-truth patch
    filenames = _parse_filenames_from_patch(patch)

    metadata: dict[str, Any] = {
        "enhancer_type": "real",
        "agent_id": "code_context",
        "instance_id": instance_id,
        "image_name": image_name,
        "source_files_requested": filenames,
        "hints_available": bool(hints_text.strip()),
        "fail_to_pass_count": len(fail_to_pass),
        "test_patch_available": bool(test_patch.strip()),
        "sections_included": [],
    }

    context_sections: list[str] = []

    # 1. Source code from Docker
    if _INCLUDE_SOURCE and image_name and filenames:
        sources = _read_source_files(image_name, filenames, _MAX_LINES_PER_FILE)
        section = _build_source_section(sources)
        if section:
            context_sections.append(section)
            metadata["sections_included"].append("source_code")
            metadata["source_files_read"] = list(sources.keys())
            metadata["source_files_failed"] = [f for f in filenames if f not in sources]

    # 2. Developer hints
    if _INCLUDE_HINTS and hints_text.strip():
        section = _build_hints_section(hints_text)
        if section:
            context_sections.append(section)
            metadata["sections_included"].append("hints")

    # 3. Failing test names
    if _INCLUDE_FAILING_TESTS and fail_to_pass:
        section = _build_failing_tests_section(fail_to_pass)
        if section:
            context_sections.append(section)
            metadata["sections_included"].append("failing_tests")

    # 4. Test patch (opt-in)
    if _INCLUDE_TEST_PATCH and test_patch.strip():
        section = _build_test_patch_section(test_patch)
        if section:
            context_sections.append(section)
            metadata["sections_included"].append("test_patch")

    # 5. Pass-to-pass test names (opt-in)
    if _INCLUDE_P2P_TESTS:
        pass_to_pass = row.get("PASS_TO_PASS", [])
        if isinstance(pass_to_pass, str):
            import ast
            try:
                pass_to_pass = ast.literal_eval(pass_to_pass)
            except (ValueError, SyntaxError):
                pass_to_pass = [pass_to_pass]
        if pass_to_pass:
            section = _build_p2p_tests_section(pass_to_pass)
            if section:
                context_sections.append(section)
                metadata["sections_included"].append("p2p_tests")
                metadata["p2p_test_count"] = len(pass_to_pass)

    # Build enhanced body — cap context so total stays under max_enhanced_body_chars (30k)
    max_enhanced_total = int(os.environ.get("CODE_CONTEXT_MAX_ENHANCED_TOTAL", "29000"))
    available_for_context = min(_MAX_TOTAL_CHARS, max(2000, max_enhanced_total - len(body)))
    if context_sections:
        context_block = _truncate_context(context_sections, available_for_context)
        enhanced_body = f"{body.rstrip()}\n\n---\n{context_block}"
    else:
        enhanced_body = body
        metadata["enhancement_noop"] = True

    metadata["enhanced_body_length"] = len(enhanced_body)
    metadata["original_body_length"] = len(body)
    metadata["context_chars_added"] = len(enhanced_body) - len(body)

    return {
        "enhanced_title": title,  # Keep original title
        "enhanced_body": enhanced_body,
        "enhancement_metadata": metadata,
    }
