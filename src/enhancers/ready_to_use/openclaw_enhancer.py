"""
OpenClaw enhancer — Category A, Python SDK integration.

Uses the OpenClaw/CMDOP Python SDK (``openclaw.OpenClaw``) to run a remote
agent that enhances a GitHub issue.  The SDK connects to the CMDOP cloud relay
via gRPC; no local CLI binary is required.

Environment variables:
  OPENCLAW_API_KEY  - CMDOP API key (cmdop_live_xxx).  **Required**.
  OPENCLAW_MODEL    - LLM model passed to the agent (default: gpt-5.4-mini)
  OPENCLAW_TIMEOUT  - seconds before giving up (default: 300)
  OPENCLAW_MAX_ITER - max agent turns (default: 8)
  OPENCLAW_SERVER   - gRPC relay endpoint (default: grpc.cmdop.com:443)
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_root))

from src.enhancers.ready_to_use.native_output_parser import parse_enhanced_output

_API_KEY  = os.environ.get("OPENCLAW_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
_MODEL    = os.environ.get("OPENCLAW_MODEL", "gpt-5.4-mini")
_TIMEOUT  = int(os.environ.get("OPENCLAW_TIMEOUT", "300"))
_MAX_ITER = int(os.environ.get("OPENCLAW_MAX_ITER", "8"))
_SERVER   = os.environ.get("OPENCLAW_SERVER", "grpc.cmdop.com:443")


ENHANCEMENT_TASK = """\
Enhance the GitHub issue below.  Return your answer using EXACTLY this format
(including the --- delimiters):

---
ENHANCED_TITLE: <improved single-line title>
ENHANCED_BODY:
<improved body as markdown with: ## Summary, ## Steps to Reproduce, ## Expected, ## Actual>
---

Repository: {repo}
Issue #{num}

## Original Title
{title}

## Original Body
{body}

## Hints (files changed in the fix)
{changed_files}

Instructions:
1. Improve: add reproduction steps, clarify expected vs actual, reference affected files.
2. Keep the enhanced body concise and actionable."""


def _make_error(title: str, body: str, error: str,
                **extra: Any) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "enhancer_type": "error",
        "agent_id": "openclaw",
        "error": error,
    }
    meta.update(extra)
    return {
        "enhanced_title": title,
        "enhanced_body": body,
        "enhancement_metadata": meta,
    }


def _sdk_available() -> bool:
    """Return True if the openclaw SDK can be imported."""
    try:
        from openclaw import OpenClaw  # noqa: F401
        return True
    except ImportError:
        return False


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    title = issue.get("title") or issue.get("instance_id") or ""
    body  = issue.get("body") or issue.get("problem_statement") or ""
    repo  = issue.get("repo_name", "")
    num   = issue.get("issue_number", "")

    if not _sdk_available():
        return _make_error(title, body,
                           "openclaw SDK not installed (pip install openclaw)")

    if not _API_KEY:
        return _make_error(title, body,
                           "OPENCLAW_API_KEY not set (need a cmdop_live_xxx key "
                           "or set OPENAI_API_KEY as fallback)")

    if not changed_files and "pr_files" in issue:
        changed_files = ", ".join(f["filename"] for f in issue["pr_files"][:10])

    prompt = ENHANCEMENT_TASK.format(
        repo=repo, num=num, title=title, body=body, changed_files=changed_files,
    )

    from openclaw import OpenClaw
    from cmdop.models.agent import AgentRunOptions, AgentType

    try:
        client = OpenClaw.remote(api_key=_API_KEY, server=_SERVER)
    except Exception as exc:
        return _make_error(title, body,
                           f"OpenClaw connection failed: {exc}",
                           server=_SERVER)

    try:
        options = AgentRunOptions(
            model=_MODEL,
            max_turns=_MAX_ITER,
            timeout_seconds=min(_TIMEOUT, 600),
        )
        result = client.agent.run(
            prompt=prompt,
            agent_type=AgentType.CHAT,
            options=options,
        )
    except Exception as exc:
        return _make_error(title, body,
                           f"OpenClaw agent.run failed: {exc}",
                           model=_MODEL, server=_SERVER)
    finally:
        try:
            client.close()
        except Exception:
            pass

    if not result.success:
        return _make_error(title, body,
                           result.error or "agent returned success=False",
                           model=_MODEL, server=_SERVER,
                           duration_ms=result.duration_ms)

    agent_text = (result.text or "").strip()
    if not agent_text:
        return _make_error(title, body,
                           "agent returned empty text",
                           model=_MODEL, server=_SERVER,
                           duration_ms=result.duration_ms)

    enh_title, enh_body, parse_source = parse_enhanced_output(
        agent_text, title, body,
    )

    if enh_title == title and enh_body == body:
        return _make_error(title, body,
                           "no ENHANCED_TITLE/ENHANCED_BODY markers in agent output",
                           model=_MODEL, server=_SERVER,
                           duration_ms=result.duration_ms,
                           agent_text_preview=agent_text[:300])

    return {
        "enhanced_title": enh_title,
        "enhanced_body": enh_body,
        "enhancement_metadata": {
            "enhancer_type": "real",
            "agent_id": "openclaw",
            "model": _MODEL,
            "server": _SERVER,
            "parse_source": parse_source,
            "duration_ms": result.duration_ms,
            "usage": {
                "prompt_tokens": result.usage.prompt_tokens,
                "completion_tokens": result.usage.completion_tokens,
                "total_tokens": result.usage.total_tokens,
            },
        },
    }
