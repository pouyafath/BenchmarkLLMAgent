"""
OpenHands enhancer — Category A.

Uses the real `openhands` CLI in headless mode, pointing at gpt-oss:120b
via Ollama's OpenAI-compatible endpoint.

Falls back to llm_proxy_enhance if binary is not found or times out.

Environment variables (all optional):
  OPENHANDS_MODEL    - model (default: gpt-oss:120b)
  OPENHANDS_BASE_URL - OpenAI-compat base URL (default: http://localhost:11434/v1)
  OPENHANDS_API_KEY  - API key (default: ollama)
  OPENHANDS_TIMEOUT  - seconds before giving up (default: 300)
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

from src.enhancers.ready_to_use.llm_proxy_enhancer import enhance_issue as llm_proxy_enhance

_MODEL    = os.environ.get("OPENHANDS_MODEL",    "gpt-oss:120b")
_BASE_URL = os.environ.get("OPENHANDS_BASE_URL", "http://localhost:11434/v1")
_API_KEY  = os.environ.get("OPENHANDS_API_KEY",  "ollama")
_TIMEOUT  = int(os.environ.get("OPENHANDS_TIMEOUT", "300"))

ENHANCEMENT_PROMPT = """\
You are OpenHands, an AI software development agent.
Enhance the GitHub issue below to make it clear, complete, and immediately actionable.

Improvements to make:
- Add precise reproduction steps (commands, config, versions)
- Clarify expected vs actual behavior with concrete examples
- Reference the affected files / components from the hints
- Propose what the fix SHOULD look like at a high level
- Use markdown structure: ## Summary, ## Steps to Reproduce, ## Expected, ## Actual, ## Context

Output ONLY in this exact format (nothing before or after the --- delimiters):
---
ENHANCED_TITLE: <improved single-line title>
ENHANCED_BODY:
<improved body as markdown>
---"""


def _find_openhands() -> str | None:
    """Find the openhands binary: bench_env first, then system PATH."""
    bench = Path(__file__).resolve().parent.parent.parent.parent / "bench_env" / "bin" / "openhands"
    if bench.exists():
        return str(bench)
    return shutil.which("openhands")


def _parse_output(text: str, fallback_title: str, fallback_body: str) -> tuple[str, str]:
    title = fallback_title
    body  = fallback_body
    m = re.search(r"ENHANCED_TITLE:\s*(.+?)(?:\n|$)", text, re.DOTALL)
    if m:
        title = m.group(1).strip()
    m = re.search(r"ENHANCED_BODY:\s*\n([\s\S]*?)(?=---|$)", text, re.DOTALL)
    if m:
        body = m.group(1).strip()
    return title, body


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    # We now run OpenHands as a python module directly


    title = issue.get("title", "")
    body  = issue.get("body") or ""
    repo  = issue.get("repo_name", "")
    num   = issue.get("issue_number", "")

    if not changed_files and "pr_files" in issue:
        changed_files = ", ".join(f["filename"] for f in issue["pr_files"][:10])

    task_text = f"""Enhance the following GitHub issue.

Repository: {repo}
Issue #{num}

## Original Title
{title}

## Original Body
{body}

## Hints (files changed in the fix)
{changed_files}

{ENHANCEMENT_PROMPT}"""

    with tempfile.TemporaryDirectory() as tmpdir:
        task_file = Path(tmpdir) / "task.txt"
        task_file.write_text(task_text, encoding="utf-8")

        config_toml = f"""
[llm]
model = "openai/{_MODEL}"
base_url = "{_BASE_URL}"
api_key = "{_API_KEY}"

[agent]
name = "CodeAct"
"""
        (Path(tmpdir) / "config.toml").write_text(config_toml, encoding="utf-8")

        cmd = [
            sys.executable,
            "-m", "openhands.core.main",
            "-f", str(task_file),
            "-i", "2",  # keep it short for testing/enhancement
            "--config-file", "config.toml",
        ]

        env = {**os.environ}

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
            return llm_proxy_enhance(issue, changed_files, agent_id="openhands")
        except Exception as e:
            return {
                "enhanced_title": title,
                "enhanced_body":  body,
                "enhancement_metadata": {
                    "enhancer_type": "real",
                    "agent_id": "openhands",
                    "error": str(e),
                },
            }

        output = (result.stdout or "").strip()
        enh_title, enh_body = _parse_output(output, title, body)

        # If real CLI failed (no pattern match), fall back to proxy
        if enh_title == title and enh_body == body and result.returncode != 0:
            return llm_proxy_enhance(issue, changed_files, agent_id="openhands")

        return {
            "enhanced_title": enh_title,
            "enhanced_body":  enh_body,
            "enhancement_metadata": {
                "enhancer_type": "real",
                "agent_id": "openhands",
                "model": _MODEL,
                "base_url": _BASE_URL,
                "returncode": result.returncode,
                "stderr_preview": (result.stderr or "")[:300],
            },
        }
