"""
LLM proxy enhancer for Category A agents.

Uses the shared LLM with agent-specific prompts when real integration
is not available. Metadata clearly marks enhancer_type as "llm_proxy".
"""

import json
import re
from pathlib import Path
from typing import Any, Dict

import sys
_here = Path(__file__).resolve()
_root = _here.parent.parent.parent
sys.path.insert(0, str(_root))

from src.utils.llm_client import get_client
from src.enhancers.ready_to_use.registry import get_agent_by_id

BASE_SYSTEM = """You are an expert at improving GitHub issue descriptions. Your task is to enhance an issue's title and body.

Improvements: add reproduction steps, expected vs actual behavior, environment; restructure for clarity; add file/code references when inferable; use proper formatting (sections, code blocks).

Output format: Respond with a JSON object only:
{
  "enhanced_title": "...",
  "enhanced_body": "...",
  "enhancement_rationale": "Brief explanation of changes"
}

Keep the output concise:
- preserve all essential technical details from the original
- do not copy the full original body verbatim
- include only the key sections needed for reproduction/fix

Do not add fictional information. Output ONLY the JSON object."""


def _extract_json(text: str) -> dict:
    """Extract JSON from model output."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group(0))
    return json.loads(text)


def enhance_issue(issue: dict, changed_files: str = "", agent_id: str = "chatbr",
                  strategy_override: str | None = None) -> Dict[str, Any]:
    """
    Enhance issue using LLM with agent-specific prompt (proxy for Category A agent).
    Pass strategy_override to skip the registry lookup and use a custom strategy.
    """
    if strategy_override:
        strategy = strategy_override
    else:
        agent = get_agent_by_id(agent_id)
        strategy = agent["enhancement_strategy"] if agent else "Improve the issue structure and clarity."
    system = f"{BASE_SYSTEM}\n\nAgent persona: {strategy}"


    title = issue.get("title") or issue.get("instance_id") or ""
    body = issue.get("body") or issue.get("problem_statement") or ""
    repo = issue.get("repo_name", "")
    num = issue.get("issue_number", "")
    if not changed_files and "pr_files" in issue:
        changed_files = ", ".join(f["filename"] for f in issue["pr_files"][:10])

    user_msg = f"""## GitHub Issue to Enhance

**Repository**: {repo}
**Issue #{num}**

### Original Title
{title}

### Original Body
{body}

### Hints (files changed in the fix)
{changed_files}

---
Enhance this issue as the specified agent would. Output ONLY a valid JSON object."""

    client = get_client(max_new_tokens=4096, temperature=0.0)
    response, meta = client.generate(system, user_msg)

    try:
        data = _extract_json(response)
        return {
            "enhanced_title": data.get("enhanced_title", title),
            "enhanced_body": data.get("enhanced_body", body),
            "enhancement_metadata": {
                "enhancer_type": "llm_proxy",
                "agent_id": agent_id,
                "enhancement_rationale": data.get("enhancement_rationale", ""),
                "elapsed_s": meta.get("elapsed_s", 0),
                "backend": meta.get("backend", ""),
                "model_id": meta.get("model_id", ""),
            },
        }
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "llm_proxy",
                "agent_id": agent_id,
                "error": str(e),
                "raw_response_preview": response[:500] if response else "",
            },
        }
