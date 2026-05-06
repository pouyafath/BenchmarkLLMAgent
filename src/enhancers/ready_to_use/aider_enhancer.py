"""
Aider-based enhancement for Category A.

Uses aider CLI when available: writes issue to temp file, runs aider with
enhancement message, parses result. Returns error metadata if aider not found
(no fallback to LLM proxy).

Environment variables (all optional):
  AIDER_MODEL      - Model name for aider (default: openai/Devstral-Small-2-24B-Instruct-2512)
  AIDER_API_BASE   - Base URL for OpenAI-compat endpoint (default: http://127.0.0.1:18000/v1)
  AIDER_API_KEY    - API key (default: local-devstral)
  AIDER_TIMEOUT    - Seconds before giving up (default: 300)
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

import sys
_here = Path(__file__).resolve()
_root = _here.parent.parent.parent
sys.path.insert(0, str(_root))

_AIDER_CLI = "/home/22pf2/BenchmarkLLMAgent/bench_env/bin/aider"
_MODEL     = os.environ.get("AIDER_MODEL",    "openai/Devstral-Small-2-24B-Instruct-2512")
_API_BASE  = os.environ.get("AIDER_API_BASE", "http://127.0.0.1:18000/v1")
_API_KEY   = os.environ.get("AIDER_API_KEY",  "local-devstral")
_TIMEOUT   = int(os.environ.get("AIDER_TIMEOUT", "300"))
_NOOP_MAX_RETRIES = int(os.environ.get("AIDER_NOOP_MAX_RETRIES", "2"))
_RETRY_TEMPERATURE = float(os.environ.get("AIDER_RETRY_TEMPERATURE", "0.2"))

ENHANCEMENT_PROMPT = """Enhance this GitHub issue. Improve the title and body to be more complete, clear, and actionable.

Add: reproduction steps, expected vs actual behavior, environment details where inferable.
Keep the original content but restructure and enrich it. Add file references from the hints if relevant.

Output the enhanced issue in this exact format at the end of your response:
---
ENHANCED_TITLE: <improved title>
ENHANCED_BODY:
<improved body as markdown>
---"""

FORCE_REWRITE_SUFFIX = """\

Additional hard constraints for this attempt:
- Do not copy the original text verbatim.
- Keep the same facts, but rewrite and restructure the issue.
- The body must include these sections exactly as markdown headers:
  - `## Summary`
  - `## Steps to Reproduce`
  - `## Expected Behavior`
  - `## Actual Behavior`
  - `## Scope / Affected Areas`
- Include at least one bulleted list.
"""


def _aider_available() -> bool:
    return os.path.exists(_AIDER_CLI) or shutil.which("aider") is not None


def _get_aider_cmd() -> str:
    if os.path.exists(_AIDER_CLI):
        return _AIDER_CLI
    return shutil.which("aider") or "aider"


def _is_placeholder_title(title: str) -> bool:
    """Detect placeholder text that the LLM copied from the prompt template."""
    t = (title or "").strip().lower()
    if not t:
        return True
    placeholder_tokens = (
        "<improved title>",
        "improved title",
        "<improved single-line title>",
        "improved single-line title",
        "<improved single line title>",
        "improved single line title",
        "<title>",
        "enhanced_title:",
    )
    return any(tok in t for tok in placeholder_tokens)


def _is_placeholder_body(body: str) -> bool:
    """Detect placeholder text that the LLM copied from the prompt template."""
    b = (body or "").strip().lower()
    if not b:
        return True
    placeholder_tokens = (
        "<improved body as markdown>",
        "improved body as markdown",
        "<improved body>",
        "enhanced_body:",
    )
    return any(tok in b for tok in placeholder_tokens)


def _parse_aider_output(content: str, fallback_title: str, fallback_body: str) -> tuple[str, str]:
    """Extract ENHANCED_TITLE and ENHANCED_BODY from aider's edited file content."""
    # Aider edits the file in place; content may be the full file
    title = fallback_title
    body = fallback_body
    m = re.search(r"ENHANCED_TITLE:\s*(.+?)(?:\n|$)", content, re.DOTALL)
    if m:
        candidate_title = m.group(1).strip()
        if not _is_placeholder_title(candidate_title):
            title = candidate_title
    m = re.search(r"ENHANCED_BODY:\s*\n([\s\S]*?)(?=---|\Z)", content, re.DOTALL)
    if m:
        candidate_body = m.group(1).strip()
        if not _is_placeholder_body(candidate_body):
            body = candidate_body
    return title, body


def _build_task_text(
    *,
    repo: str,
    num: str | int,
    title: str,
    body: str,
    changed_files: str,
    force_rewrite: bool,
) -> str:
    suffix = FORCE_REWRITE_SUFFIX if force_rewrite else ""
    return f"""# GitHub Issue

Repository: {repo}
Issue #{num}

## Original Title
{title}

## Original Body
{body}

## Hints (files changed in fix)
{changed_files}

{ENHANCEMENT_PROMPT}
{suffix}"""


def _run_aider_once(
    *,
    task_text: str,
    title: str,
    body: str,
) -> dict[str, Any]:
    aider_cmd = _get_aider_cmd()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a git repo (aider requires it)
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

        issue_path = Path(tmpdir) / "issue.md"
        issue_path.write_text(task_text, encoding="utf-8")

        subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmpdir, capture_output=True)

        # Build a clean environment for aider: strip AIDER_* vars to prevent
        # them from being auto-interpreted as CLI flags by aider.
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("AIDER_")}
        clean_env["OPENAI_API_KEY"] = _API_KEY
        clean_env["OPENAI_API_BASE"] = _API_BASE
        clean_env["AIDER_YES"] = "1"

        try:
            result = subprocess.run(
                [
                    aider_cmd,
                    "--model", _MODEL,
                    "--no-auto-commits",
                    "--no-git",
                    "--yes",
                    "--no-check-update",
                    "--no-analytics",
                    "--no-show-model-warnings",
                    "--message", ENHANCEMENT_PROMPT,
                    str(issue_path),
                ],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                cwd=tmpdir,
                env=clean_env,
            )
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(str(e)) from e

        # Try to parse from the edited file first
        content = issue_path.read_text(encoding="utf-8")
        file_title, file_body = _parse_aider_output(content, title, body)

        # Also try stdout
        stdout_title, stdout_body = _parse_aider_output(result.stdout or "", title, body)

        # Pick best
        candidates = [(file_title, file_body), (stdout_title, stdout_body)]
        best = (title, body)
        for ct, cb in candidates:
            if ct != title or cb != body:
                best = (ct, cb)
                break

        return {
            "enhanced_title": best[0],
            "enhanced_body": best[1],
            "returncode": result.returncode,
            "stderr_preview": (result.stderr or "")[:300],
            "stdout_preview": (result.stdout or "")[:500],
        }


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    """Enhance using aider CLI (native only, no proxy fallback)."""
    title = issue.get("title") or issue.get("instance_id") or ""
    body = issue.get("body") or issue.get("problem_statement") or ""
    if not _aider_available():
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "aider",
                "error": f"aider CLI not found at {_AIDER_CLI} or in PATH",
            },
        }

    repo = issue.get("repo_name", "")
    num = issue.get("issue_number", "")
    if not changed_files and "pr_files" in issue:
        changed_files = ", ".join(f["filename"] for f in issue["pr_files"][:10])

    attempts: list[dict[str, Any]] = []
    run_errors: list[str] = []
    first_result: dict[str, Any] | None = None
    final_result: dict[str, Any] | None = None

    for attempt_idx in range(_NOOP_MAX_RETRIES + 1):
        force_rewrite = attempt_idx > 0
        task_text = _build_task_text(
            repo=repo,
            num=num,
            title=title,
            body=body,
            changed_files=changed_files,
            force_rewrite=force_rewrite,
        )
        try:
            run_result = _run_aider_once(
                task_text=task_text,
                title=title,
                body=body,
            )
        except TimeoutError:
            return {
                "enhanced_title": title,
                "enhanced_body": body,
                "enhancement_metadata": {
                    "enhancer_type": "error",
                    "agent_id": "aider",
                    "model": _MODEL,
                    "base_url": _API_BASE,
                    "error": f"aider timeout after {_TIMEOUT}s",
                    "attempts": attempts,
                },
            }
        except Exception as e:
            run_errors.append(str(e))
            continue

        attempts.append(
            {
                "attempt": attempt_idx + 1,
                "force_rewrite": force_rewrite,
                "returncode": run_result.get("returncode"),
                "enhancement_noop": (
                    run_result.get("enhanced_title") == title
                    and run_result.get("enhanced_body") == body
                ),
            }
        )

        if first_result is None:
            first_result = run_result
        final_result = run_result
        if run_result["enhanced_title"] != title or run_result["enhanced_body"] != body:
            break

    if final_result is None:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "aider",
                "model": _MODEL,
                "base_url": _API_BASE,
                "error": run_errors[-1] if run_errors else "aider execution failed",
                "attempts": attempts,
            },
        }

    enh_title = final_result["enhanced_title"]
    enh_body = final_result["enhanced_body"]
    returncode = int(final_result.get("returncode", 1))

    if returncode != 0 and enh_title == title and enh_body == body:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "aider",
                "model": _MODEL,
                "base_url": _API_BASE,
                "aider_returncode": returncode,
                "aider_stderr_preview": final_result.get("stderr_preview", ""),
                "attempts": attempts,
            },
        }

    return {
        "enhanced_title": enh_title,
        "enhanced_body": enh_body,
        "enhancement_metadata": {
            "enhancer_type": "real",
            "agent_id": "aider",
            "model": _MODEL,
            "base_url": _API_BASE,
            "aider_returncode": returncode,
            "aider_stderr_preview": final_result.get("stderr_preview", ""),
            "aider_stdout_preview": final_result.get("stdout_preview", ""),
            "enhancement_noop": enh_title == title and enh_body == body,
            "attempt_count": len(attempts),
            "noop_retry_used": len(attempts) > 1,
            "attempts": attempts,
            "initial_noop": (
                first_result is not None
                and first_result.get("enhanced_title") == title
                and first_result.get("enhanced_body") == body
            ),
        },
    }
