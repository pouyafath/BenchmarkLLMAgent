"""
Mini-SWE-Agent enhancer — Category A.

Uses the real `mini` CLI (pip install mini-swe-agent) pointed at gpt-oss:120b
via Ollama's OpenAI-compatible endpoint.

Falls back to llm_proxy_enhance if the binary is not available or times out.

Environment variables (all optional):
  MINI_MODEL       - model to use  (default: gpt-oss:120b)
  MINI_BASE_URL    - OpenAI-compat base URL (default: http://localhost:11434/v1)
  MINI_API_KEY     - API key (default: ollama)
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

from src.enhancers.ready_to_use.llm_proxy_enhancer import enhance_issue as llm_proxy_enhance

_MODEL    = os.environ.get("MINI_MODEL",    "gpt-oss:120b")
_BASE_URL = os.environ.get("MINI_BASE_URL", "http://localhost:11434/v1")
_API_KEY  = os.environ.get("MINI_API_KEY",  "ollama")
_TIMEOUT  = int(os.environ.get("MINI_TIMEOUT", "300"))

ENHANCEMENT_PROMPT = """\
You are Mini-SWE-Agent: a minimal, focused software engineering agent.
Enhance the GitHub issue below to be clear, complete, and actionable.

Improve:
- Add reproduction steps if missing
- Clarify expected vs actual behavior
- Reference affected files / components from the hints
- Tighten the title to be specific and informative

Output ONLY in this exact format (nothing before or after the --- delimiters):
---
ENHANCED_TITLE: <improved single-line title>
ENHANCED_BODY:
<improved body as markdown>
---"""


def _find_mini() -> str | None:
    """Find the mini binary: bench_env first, then system PATH."""
    bench = Path(__file__).resolve().parent.parent.parent.parent / "bench_env" / "bin" / "mini"
    if bench.exists():
        return str(bench)
    return shutil.which("mini")


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
    mini_bin = _find_mini()
    if not mini_bin:
        return llm_proxy_enhance(issue, changed_files, agent_id="mini_swe_agent")

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
        cmd = [
            mini_bin,
            "--model", _MODEL,
            "--task", task_text,
            "--yolo",
            "--exit-immediately",
        ]

        env = {
            **os.environ,
            "OPENAI_API_KEY": _API_KEY,
            "OPENAI_BASE_URL": _BASE_URL,
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
            return llm_proxy_enhance(issue, changed_files, agent_id="mini_swe_agent")
        except Exception as e:
            return {
                "enhanced_title": title,
                "enhanced_body":  body,
                "enhancement_metadata": {
                    "enhancer_type": "real",
                    "agent_id": "mini_swe_agent",
                    "error": str(e),
                },
            }

        output = (result.stdout or "").strip()
        if result.returncode != 0:
            return {
                "enhanced_title": title,
                "enhanced_body":  body,
                "enhancement_metadata": {
                    "enhancer_type": "error",
                    "agent_id": "mini_swe_agent",
                    "model": _MODEL,
                    "base_url": _BASE_URL,
                    "returncode": result.returncode,
                    "stderr_preview": (result.stderr or "")[:300],
                },
            }
        enh_title, enh_body = _parse_output(output, title, body)

        return {
            "enhanced_title": enh_title,
            "enhanced_body":  enh_body,
            "enhancement_metadata": {
                "enhancer_type": "real",
                "agent_id": "mini_swe_agent",
                "model": _MODEL,
                "base_url": _BASE_URL,
                "returncode": result.returncode,
                "stderr_preview": (result.stderr or "")[:300],
            },
        }
