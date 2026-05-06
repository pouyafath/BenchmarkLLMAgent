"""
Simple enhancement agent using the unified LLM client.

Uses Gemma 3 12B (HuggingFace or Ollama) for issue enhancement.
No framework dependencies — just the shared LLM client.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict

import sys
_here = Path(__file__).resolve()
_root = _here.parent.parent.parent.parent
sys.path.insert(0, str(_root))

from src.utils.llm_client import get_client

SYSTEM_PROMPT = """You are an expert at improving GitHub issue descriptions. Your task is to enhance an issue's title and body to make it more complete, clear, actionable, and well-structured.

Improvements you should make:
- Add missing information: reproduction steps, expected vs actual behavior, environment details
- Restructure unclear descriptions and remove ambiguity
- Make the issue more specific so a developer (or an AI agent) knows exactly what to fix
- Use proper formatting: sections, code blocks, bullet points, error messages
- Add relevant code references, file paths, or component names when inferable

Output format: Respond with a JSON object containing:
{
  "enhanced_title": "...",
  "enhanced_body": "...",
  "enhancement_rationale": "Brief explanation of changes made"
}

Keep the output concise:
- `enhanced_body` must be at most 1200 characters
- do not copy the full original body verbatim
- include only key sections needed to reproduce and fix

Do not add fictional information. Output ONLY the JSON object, no markdown or extra text."""


def _extract_json(text: str) -> dict:
    """Extract JSON from model output (may be wrapped in markdown)."""
    text = text.strip()
    # First try strict JSON parse. This handles valid JSON that may contain
    # markdown code fences inside string values.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # If the model wrapped the object in an outer markdown block, unwrap once.
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Fallback: parse the largest JSON-looking object.
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group(0))
    return json.loads(text)


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    """
    Enhance a single GitHub issue. Returns dict with enhanced_title, enhanced_body, metadata.
    """
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
Enhance this issue. Output ONLY a valid JSON object with keys: enhanced_title, enhanced_body, enhancement_rationale."""

    client = get_client(max_new_tokens=4096, temperature=0.0)
    response, meta = client.generate(SYSTEM_PROMPT, user_msg)

    try:
        data = _extract_json(response)
        return {
            "enhanced_title": data.get("enhanced_title", title),
            "enhanced_body": data.get("enhanced_body", body),
            "enhancement_metadata": {
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
                "error": str(e),
                "raw_response_preview": response[:500] if response else "",
            },
        }
