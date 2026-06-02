"""
Mini-SWE-Agent enhancer — Category A.

Uses the real `mini` CLI (pip install mini-swe-agent) pointed at gpt-5.4-mini
via OpenAI API.

Returns an error dict if the binary is not found, times out, or exits non-zero.

Environment variables (all optional):
  MINI_MODEL       - model to use  (default: gpt-5.4-mini)
  MINI_BASE_URL    - OpenAI-compat base URL (default: https://api.openai.com/v1)
  MINI_API_KEY     - API key (default: OPENAI_API_KEY env var)
  MINI_TIMEOUT     - seconds before giving up (default: 300)
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

import sys
_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_root))

from src.enhancers.ready_to_use.native_output_parser import parse_enhanced_output



_MODEL    = os.environ.get("MINI_MODEL",    "gpt-5.4-mini")
_BASE_URL = os.environ.get("MINI_BASE_URL", "https://api.openai.com/v1")
_API_KEY  = os.environ.get("MINI_API_KEY",  os.environ.get("OPENAI_API_KEY", ""))
_TIMEOUT  = int(os.environ.get("MINI_TIMEOUT", "300"))

# mini v2 requires a global config file; we write it before running
_MINI_CONFIG_DIR = Path.home() / ".config" / "mini-swe-agent"

ENHANCEMENT_TASK = """\
Enhance the GitHub issue below and write your result to the file `enhanced_issue.md`.

Repository: {repo}
Issue #{num}

## Original Title
{title}

## Original Body
{body}

## Hints (files changed in the fix)
{changed_files}

Instructions:
1. You MUST write the enhanced issue to `enhanced_issue.md` using this EXACT bash command:
```bash
cat > enhanced_issue.md << 'ENDOFFILE'
ENHANCED_TITLE: <your improved single-line title here>
ENHANCED_BODY:
## Summary
<summary>
## Steps to Reproduce
<steps>
## Expected Behavior
<expected>
## Actual Behavior
<actual>
ENDOFFILE
```
2. CRITICAL: The file MUST start with `ENHANCED_TITLE:` on the first line and `ENHANCED_BODY:` on the third line. Do NOT skip this step.
3. Improve: add reproduction steps, clarify expected vs actual, reference affected files.
4. Run: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"""


def _find_mini() -> str | None:
    """Find the mini binary: bench_env first, then system PATH."""
    bench = Path(__file__).resolve().parent.parent.parent.parent / "bench_env" / "bin" / "mini"
    if bench.exists():
        return str(bench)
    return shutil.which("mini")


def _parse_output(text: str, fallback_title: str, fallback_body: str) -> tuple[str, str]:
    title, body, _ = parse_enhanced_output(text, fallback_title, fallback_body)
    return title, body


def _ensure_mini_config() -> None:
    """Create the global mini config file if missing (required by mini v2).
    Previous failure cause: missing .env → mini aborted at interactive setup wizard.
    """
    _MINI_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    env_file = _MINI_CONFIG_DIR / ".env"
    if not env_file.exists():
        # Write a minimal config; actual API key comes from OPENAI_API_KEY env var
        env_file.write_text("MODEL=openai/gpt-5.4-mini\n", encoding="utf-8")


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    title = issue.get("title") or issue.get("instance_id") or ""
    body  = issue.get("body") or issue.get("problem_statement") or ""

    mini_bin = _find_mini()
    if not mini_bin:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "mini_swe_agent",
                "error": "mini CLI not found",
            },
        }

    # Ensure global config exists (mini v2 requires it)
    _ensure_mini_config()

    repo  = issue.get("repo_name", "")
    num   = issue.get("issue_number", "")

    if not changed_files and "pr_files" in issue:
        changed_files = ", ".join(f["filename"] for f in issue["pr_files"][:10])

    task_text = ENHANCEMENT_TASK.format(
        repo=repo, num=num, title=title, body=body, changed_files=changed_files
    )

    # mini requires model name with provider prefix (e.g., "openai/gpt-4o-mini")
    # Strip provider prefix from stored model name if already included, then add it
    model_for_mini = _MODEL if "/" in _MODEL else f"openai/{_MODEL}"

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            mini_bin,
            "--model", model_for_mini,
            "--task", task_text,
            "--yolo",
            "--exit-immediately",
        ]

        env = {
            **os.environ,
            "OPENAI_API_KEY": _API_KEY,
            "OPENAI_BASE_URL": _BASE_URL,
            # mini v2 skips interactive setup wizard only when MSWEA_CONFIGURED=1
            "MSWEA_CONFIGURED": "1",
            # Suppress cost-tracking errors for unmapped models
            # Without this, litellm raises and mini exits 1 even when the task succeeded
            "MSWEA_COST_TRACKING": "ignore_errors",
        }

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                cwd=tmpdir,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return {
                "enhanced_title": title,
                "enhanced_body":  body,
                "enhancement_metadata": {
                    "enhancer_type": "error",
                    "agent_id": "mini_swe_agent",
                    "model": _MODEL,
                    "base_url": _BASE_URL,
                    "error": f"mini timeout after {_TIMEOUT}s",
                },
            }
        except Exception as e:
            return {
                "enhanced_title": title,
                "enhanced_body":  body,
                "enhancement_metadata": {
                    "enhancer_type": "error",
                    "agent_id": "mini_swe_agent",
                    "error": str(e),
                },
            }

        # Require returncode == 0: a non-zero exit means the CLI itself failed,
        # even if a partial output file was written with valid markers.
        if result.returncode != 0:
            return {
                "enhanced_title": title,
                "enhanced_body":  body,
                "enhancement_metadata": {
                    "enhancer_type": "error",
                    "agent_id": "mini_swe_agent",
                    "model": _MODEL,
                    "base_url": _BASE_URL,
                    "error": f"mini exited with returncode {result.returncode}",
                    "returncode": result.returncode,
                    "stderr_preview": (result.stderr or "")[:300],
                },
            }

        # Read the output file written by the agent
        output_file = Path(tmpdir) / "enhanced_issue.md"
        file_content = ""
        if output_file.exists():
            file_content = output_file.read_text(encoding="utf-8", errors="replace")

        # Also try stdout as fallback
        stdout_content = (result.stdout or "").strip()

        for content in (file_content, stdout_content):
            if not content:
                continue
            enh_title, enh_body, parse_source = parse_enhanced_output(content, title, body)
            # Reject unfilled prompt template placeholders leaked from stdout
            if "<summary>" in enh_body and "<steps>" in enh_body:
                continue
            if enh_title != title or enh_body != body:
                return {
                    "enhanced_title": enh_title,
                    "enhanced_body":  enh_body,
                    "enhancement_metadata": {
                        "enhancer_type": "real",
                        "agent_id": "mini_swe_agent",
                        "model": _MODEL,
                        "base_url": _BASE_URL,
                        "returncode": result.returncode,
                        "parse_source": parse_source,
                        "source": "file" if content == file_content else "stdout",
                    },
                }

        return {
            "enhanced_title": title,
            "enhanced_body":  body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "mini_swe_agent",
                "model": _MODEL,
                "base_url": _BASE_URL,
                "returncode": result.returncode,
                "error": "no ENHANCED_TITLE/ENHANCED_BODY markers in output file or stdout",
                "file_exists": output_file.exists(),
                "file_preview": file_content[:300],
                "stderr_preview": (result.stderr or "")[:300],
            },
        }
