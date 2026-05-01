"""
Append-only LLM enhancer: adds LLM analysis WITHOUT modifying the original issue.

This enhancer addresses the "lossy compressor" problem observed with Aider, SWE-agent,
and TRAE, which degraded solver performance by rewriting issues into clean summaries
that stripped raw stack traces, error messages, and technical jargon.

Key invariant: the original issue body is NEVER modified. LLM output is appended
below a --- separator, following the same pattern as code_context_enhancer.

Three strategies:
  append_analysis   — Root cause hypothesis + affected components + fix direction
  extract_highlight — Organized index of stack traces, error msgs, file paths, code
  hybrid            — Chains code_context_enhancer first, then adds LLM root cause analysis
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

from src.utils.llm_client import get_client
from src.enhancers.ready_to_use.code_context_enhancer import enhance_issue as code_context_enhance


# ── System prompts (append-only: LLM must NOT rewrite the original) ─────────

SYSTEM_APPEND_ANALYSIS = """\
You are an expert software debugger. You are given a GitHub issue description.
Your job is to produce a structured analysis that will help an automated solver find and fix the bug.

IMPORTANT: Do NOT rewrite, summarize, or paraphrase the original issue. The original text
will be preserved verbatim. You are only producing ADDITIONAL analysis to append below it.

Produce a JSON object with exactly this structure:
{
  "analysis": "<your analysis in markdown>",
  "rationale": "<1-2 sentence explanation of your reasoning>"
}

Your analysis section (markdown) MUST include these subsections:
## Root Cause Hypothesis
What is likely causing this bug? Be specific about the mechanism.

## Affected Components
List the files, classes, or functions most likely involved.

## Key Error Signals
Quote verbatim any stack traces, error messages, or version numbers from the issue.
Do NOT paraphrase — copy them exactly.

## Fix Direction
What approach should the fix take? Be concrete (e.g., "add a null check in X.method()").

Keep total analysis under 2000 characters. Be precise and technical."""

SYSTEM_EXTRACT_HIGHLIGHT = """\
You are a technical signal extractor. You are given a GitHub issue description.
Your job is to extract and organize all actionable technical signals from the issue
into a structured index that an automated solver can quickly reference.

IMPORTANT: Do NOT rewrite, summarize, or paraphrase anything. Extract signals VERBATIM
from the original text. The original issue will be preserved above your output.

Produce a JSON object with exactly this structure:
{
  "analysis": "<your organized index in markdown>",
  "rationale": "<1-2 sentence explanation>"
}

Your analysis section (markdown) MUST include these subsections (skip empty ones):
## Stack Traces
Copy any stack traces or tracebacks verbatim from the issue.

## Error Messages
Copy any error messages, warnings, or assertion failures verbatim.

## File Paths & Line Numbers
List all file paths, module names, class names, and line numbers mentioned.

## Code Snippets
Copy any code snippets, configuration fragments, or command outputs verbatim.

## Environment & Versions
List any Python versions, package versions, OS info, or environment details.

## Behavioral Description
Summarize the expected vs actual behavior in 1-2 sentences.

Keep total output under 3000 characters. Extract VERBATIM — do not paraphrase."""

SYSTEM_HYBRID = """\
You are performing root-cause analysis on a software bug. You are given:
1. The original issue description
2. Relevant source code from the repository (added by a code-context tool)

Your job is to analyze the source code in light of the bug report and produce
a focused root-cause analysis.

IMPORTANT: Do NOT rewrite or summarize the original issue or source code.
Your analysis will be appended below the existing content.

Produce a JSON object with exactly this structure:
{
  "analysis": "<your root-cause analysis in markdown>",
  "rationale": "<1-2 sentence explanation>"
}

Your analysis section (markdown) MUST include:
## Root Cause Analysis
Identify the specific bug location in the source code. Reference file names and
line numbers. Explain the mechanism of the failure.

## Bug Location
State the exact file(s) and function(s) where the fix should be applied.

## Suggested Fix Approach
Describe concretely what code change would fix the bug (e.g., "change the comparison
operator on line X from < to <=").

## Test Implications
What behavior should the test verify after the fix?

Keep total analysis under 2000 characters. Be precise — reference actual code."""


# ── JSON extraction (reused from llm_proxy_enhancer) ────────────────────────

def _extract_json(text: str) -> dict:
    """Extract JSON from model output, handling fenced blocks and raw JSON."""
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
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return json.loads(text)


# ── Strategy configs ────────────────────────────────────────────────────────

_STRATEGY_CONFIG = {
    "append_analysis": {
        "system_prompt": SYSTEM_APPEND_ANALYSIS,
        "header": "LLM Analysis",
    },
    "extract_highlight": {
        "system_prompt": SYSTEM_EXTRACT_HIGHLIGHT,
        "header": "Technical Signal Index",
    },
    "hybrid": {
        "system_prompt": SYSTEM_HYBRID,
        "header": "Root Cause Analysis",
    },
}


# ── Main enhance function ──────────────────────────────────────────────────

def enhance_issue(
    issue: dict,
    changed_files: str = "",
    strategy: str = "append_analysis",
) -> Dict[str, Any]:
    """
    Enhance issue by appending LLM analysis below the preserved original body.

    Args:
        issue: dict with title, body/problem_statement, instance_id, etc.
        changed_files: comma-separated list of changed files (optional hint)
        strategy: one of 'append_analysis', 'extract_highlight', 'hybrid'

    Returns:
        dict with enhanced_title, enhanced_body, enhancement_metadata
    """
    title = issue.get("title", "")
    body = issue.get("body") or issue.get("problem_statement") or ""
    instance_id = issue.get("instance_id", "")

    config = _STRATEGY_CONFIG.get(strategy)
    if not config:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": f"llm_{strategy}",
                "error": f"Unknown strategy: {strategy!r}",
            },
        }

    # For hybrid: chain code_context_enhancer first to get source code context
    if strategy == "hybrid":
        try:
            cc_result = code_context_enhance(issue, changed_files)
            base_body = cc_result["enhanced_body"]
            cc_metadata = cc_result.get("enhancement_metadata", {})
        except Exception as e:
            # Fall back to original body if code_context fails
            base_body = body
            cc_metadata = {"code_context_error": str(e)}
    else:
        base_body = body
        cc_metadata = {}

    # Build user message for the LLM
    repo = issue.get("repo_name", "")
    num = issue.get("issue_number", "")
    user_msg = f"""## GitHub Issue

**Repository**: {repo}
**Issue #{num}**

### Issue Content
{base_body}

---
Produce your analysis as a JSON object. Do NOT rewrite the issue above."""

    # Call LLM
    try:
        client = get_client(max_new_tokens=4096, temperature=0.0)
        response, meta = client.generate(config["system_prompt"], user_msg)
    except Exception as e:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": f"llm_{strategy}",
                "error": f"LLM call failed: {e}",
            },
        }

    # Parse LLM response
    try:
        data = _extract_json(response)
        analysis = data.get("analysis", "")
        rationale = data.get("rationale", "")
    except (json.JSONDecodeError, KeyError) as e:
        # If JSON parse fails, try using raw response as analysis
        analysis = response.strip() if response else ""
        rationale = f"JSON parse failed ({e}); using raw response"

    if not analysis:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": f"llm_{strategy}",
                "error": "LLM produced empty analysis",
                "raw_response_preview": response[:500] if response else "",
            },
        }

    # CRITICAL: Append, don't replace — same pattern as code_context_enhancer
    header = config["header"]
    max_body = int(os.environ.get("LLM_APPEND_MAX_BODY_CHARS", "29500"))
    if strategy == "hybrid":
        # base_body already has code context appended; add LLM analysis on top
        prefix = f"{base_body.rstrip()}\n\n---\n\n## {header}\n\n"
    else:
        prefix = f"{body.rstrip()}\n\n---\n\n## {header}\n\n"

    available = max_body - len(prefix)
    if available < 100:
        # Not enough room for analysis; just use the base body
        enhanced_body = base_body if strategy == "hybrid" else body
        analysis = ""
    elif len(analysis) > available:
        analysis = analysis[:available] + "\n\n... (truncated to fit context limit)"
        enhanced_body = prefix + analysis
    else:
        enhanced_body = prefix + analysis

    metadata: Dict[str, Any] = {
        "enhancer_type": "llm_append",
        "agent_id": f"llm_{strategy}",
        "strategy": strategy,
        "instance_id": instance_id,
        "rationale": rationale,
        "elapsed_s": meta.get("elapsed_s", 0),
        "backend": meta.get("backend", ""),
        "model_id": meta.get("model_id", ""),
        "original_body_length": len(body),
        "enhanced_body_length": len(enhanced_body),
        "analysis_chars": len(analysis),
        "original_preserved": enhanced_body.startswith(body.rstrip()),
    }
    if cc_metadata:
        metadata["code_context_metadata"] = cc_metadata

    return {
        "enhanced_title": title,  # Keep original title
        "enhanced_body": enhanced_body,
        "enhancement_metadata": metadata,
    }
