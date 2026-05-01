"""
OpenHands-based Issue-Solving Agent.

Uses the OpenHands LLM module to call gpt-oss:120b via Ollama and produce
unified diff patches for GitHub issues.

Environment variables (all optional):
  OPENHANDS_SOLVER_MODEL     - LLM model (default: gpt-oss:120b)
  OPENHANDS_SOLVER_BASE_URL  - OpenAI-compat base URL (default: http://localhost:11434/v1)
  OPENHANDS_SOLVER_API_KEY   - API key (default: ollama)
  OPENHANDS_SOLVER_TIMEOUT   - seconds before giving up (default: 600)
"""

import os
import re
import sys
import time
import logging
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_root))

from src.utils.patch_utils import extract_patch_from_response
from src.utils.patch_validator import PatchValidator, ValidationResult
from src.utils.patch_sanitizer import PatchSanitizer

logger = logging.getLogger(__name__)

_MODEL = os.environ.get("OPENHANDS_SOLVER_MODEL", "gpt-oss:120b")
_BASE_URL = os.environ.get("OPENHANDS_SOLVER_BASE_URL", "http://localhost:11434/v1")
_API_KEY = os.environ.get("OPENHANDS_SOLVER_API_KEY", "ollama")
_TIMEOUT = int(os.environ.get("OPENHANDS_SOLVER_TIMEOUT", "600"))

SYSTEM_PROMPT = """\
You are a code diff generator. Your ONLY task:
1. Look at the BEFORE code (current state)
2. Look at the AFTER code (desired state)
3. Generate a unified diff patch showing the transformation from BEFORE to AFTER

Output format requirements:
- Start with: diff --git a/path b/path
- Then: --- a/path and +++ b/path
- Then hunks with @@ -start,count +start,count @@
- Context lines (unchanged): start with single space
- Removed lines: start with -
- Added lines: start with +
- Include 3+ context lines before and after each change
- End with newline

Output ONLY the patch. No explanations."""

SOLVER_TASK_TEMPLATE = """\
## Issue: {title}
{body}

## BEFORE (current code) and AFTER (desired code):
{source_code}

## GENERATE DIFF PATCH
Find the exact differences between BEFORE and AFTER code.
Output a complete unified diff patch that transforms BEFORE into AFTER exactly.
Use standard diff format with context lines, no truncation."""


def _fix_patch_paths(patch: str, valid_files: list[str]) -> str:
    """Fix file paths in the patch to match the actual repository files.

    The LLM sometimes uses wrong paths (e.g. 'instructlab/sdg.py' instead of
    'src/instructlab/model/accelerated_train.py'). This function attempts to
    remap patch file references to the closest matching valid file.
    """
    if not patch or not valid_files:
        return patch

    # Extract files referenced in the patch
    patch_files = re.findall(r'diff --git a/(\S+) b/(\S+)', patch)
    if not patch_files:
        return patch

    # Build mapping from wrong paths to correct paths
    remap = {}
    for a_path, b_path in patch_files:
        # Already valid?
        if a_path in valid_files:
            continue

        # Try to find best match by filename
        a_basename = os.path.basename(a_path)
        candidates = [f for f in valid_files if os.path.basename(f) == a_basename]
        if len(candidates) == 1:
            remap[a_path] = candidates[0]
            continue

        # Try partial path match (last 2 components)
        a_parts = a_path.split("/")
        best_match = None
        best_score = 0
        for vf in valid_files:
            vf_parts = vf.split("/")
            # Count matching trailing path components
            score = 0
            for ap, vp in zip(reversed(a_parts), reversed(vf_parts)):
                if ap == vp:
                    score += 1
                else:
                    break
            if score > best_score:
                best_score = score
                best_match = vf

        if best_match and best_score > 0:
            remap[a_path] = best_match
        elif len(valid_files) == 1:
            # Only one valid file - map everything to it
            remap[a_path] = valid_files[0]

    # Apply remapping
    if not remap:
        return patch

    result = patch
    for old_path, new_path in remap.items():
        result = result.replace(f"diff --git a/{old_path} b/{old_path}",
                                f"diff --git a/{new_path} b/{new_path}")
        result = result.replace(f"--- a/{old_path}", f"--- a/{new_path}")
        result = result.replace(f"+++ b/{old_path}", f"+++ b/{new_path}")

    return result


def run_openhands_solver(
    issue: dict,
    title: str,
    body: str,
    changed_files: str,
    source_code: str,
) -> dict[str, Any]:
    """Run OpenHands LLM to solve an issue and return a patch.

    Uses the OpenHands LLM module for direct inference with gpt-oss:120b.
    Returns dict with keys: response, patch, elapsed_s, model, error
    """
    from openhands.core.config import LLMConfig
    from openhands.llm.llm import LLM

    # Parse changed_files into a list
    file_list = [f.strip() for f in changed_files.split(",") if f.strip()]
    file_list_formatted = "\n".join(f"- {f}" for f in file_list) if file_list else "(none specified)"
    example_file = file_list[0] if file_list else "path/to/file.py"

    task_text = SOLVER_TASK_TEMPLATE.format(
        repo_name=f"{issue['pr_owner']}/{issue['pr_repo']}",
        issue_number=issue["issue_number"],
        title=title,
        body=body[:3000],
        file_list=file_list_formatted,
        source_code=source_code or "(No source code available)",
        example_file=example_file,
    )

    config = LLMConfig(
        model=f"openai/{_MODEL}",
        base_url=_BASE_URL,
        api_key=_API_KEY,
        timeout=_TIMEOUT,
    )

    start = time.time()

    try:
        llm = LLM(config=config, service_id="openhands_solver")

        response = llm.completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task_text},
            ],
            temperature=0,
        )

        elapsed = time.time() - start
        raw_output = response.choices[0].message.content or ""
        patch = extract_patch_from_response(raw_output)

        # Fix file paths if they don't match the expected files
        if patch and file_list:
            patch = _fix_patch_paths(patch, file_list)

        return {
            "response": raw_output[-2000:] if len(raw_output) > 2000 else raw_output,
            "patch": patch,
            "elapsed_s": elapsed,
            "model": _MODEL,
            "error": None if patch else "No patch extracted from LLM response",
        }

    except Exception as e:
        elapsed = time.time() - start
        return {
            "response": "",
            "patch": "",
            "elapsed_s": elapsed,
            "model": _MODEL,
            "error": str(e)[:500],
        }


def _build_retry_feedback(validation: ValidationResult, attempt_num: int) -> str:
    """Build explicit feedback for retry attempt based on validation errors."""
    feedback = ["\n" + "=" * 60]
    feedback.append(f"RETRY ATTEMPT #{attempt_num} - FIX THESE ERRORS:")
    feedback.append("=" * 60)

    # Template for each error type
    templates = {
        "truncation": """
⚠️ CRITICAL ERROR - TRUNCATION DETECTED
Your previous patch contained "... (N more lines)" which is INVALID unified diff syntax.

You MUST write out EVERY SINGLE LINE in FULL. No abbreviations. No ellipsis.
Even if a hunk contains 500 lines, you must write all 500 lines explicitly.

Example of what you did (WRONG):
@@ -10,100 +10,100 @@
 context
-old_line
+new_line
... (97 more lines)  ← INVALID!

What you MUST do (CORRECT):
@@ -10,100 +10,100 @@
 context1
 context2
 context3
-old_line
+new_line
 context4
 context5
... (write all 100 lines explicitly)
 context98
 context99
 context100
""",
        "incomplete_hunk": """
⚠️ ERROR - INCOMPLETE HUNK at {location}
Your hunk ends prematurely without sufficient context lines.

Each hunk MUST have:
- 3+ context lines BEFORE the change
- 3+ context lines AFTER the change

Add more context lines from the source code.
""",
        "wrong_line_count": """
⚠️ ERROR - INCORRECT LINE COUNT IN HUNK HEADER at {location}
Your hunk header has wrong counts: {message}

How to calculate:
- old_count = number of context lines + number of deletion lines (-)
- new_count = number of context lines + number of addition lines (+)

Count every line in your hunk and fix the header numbers.
""",
        "missing_eof_newline": """
⚠️ WARNING - MISSING NEWLINE AT END OF PATCH
Your patch must end with a newline character (\\n).
"""
    }

    # Add error-specific feedback
    for error in validation.errors:
        template = templates.get(error.type, "")
        if template:
            feedback.append(template.format(
                location=error.location,
                message=error.message
            ))
        else:
            feedback.append(f"❌ {error.type} at {error.location}: {error.message}")

    feedback.append("\n⚠️ Generate a COMPLETE, VALID unified diff patch now. NO TRUNCATION!")
    return "\n".join(feedback)


def _select_best_result(results: list[dict]) -> dict:
    """Select best result from multiple attempts."""
    if not results:
        return {
            "response": "",
            "patch": "",
            "elapsed_s": 0,
            "model": _MODEL,
            "error": "No results generated"
        }

    # Prefer valid patches
    valid = [r for r in results if r.get("validation", {}).get("is_valid", False)]
    if valid:
        return valid[0]

    # Prefer fixable errors over critical errors
    fixable = [r for r in results if r.get("validation", {}).get("severity") == "fixable"]
    if fixable:
        return fixable[0]

    # Return last attempt
    return results[-1]


def run_openhands_solver_with_retry(
    issue: dict,
    title: str,
    body: str,
    changed_files: str,
    source_code: str,
    max_retries: int = 2
) -> dict[str, Any]:
    """
    Run OpenHands solver with validation and retry on failure.

    Flow:
    1. Generate patch via run_openhands_solver()
    2. Validate patch via PatchValidator
    3. If fixable errors → sanitize via PatchSanitizer
    4. If critical errors (truncation) → retry with explicit feedback
    5. Return best valid patch found

    Args:
        issue: GitHub issue dict
        title: Issue title
        body: Issue body
        changed_files: Comma-separated file paths
        source_code: Source code content
        max_retries: Maximum retry attempts (default: 2, total 3 attempts)

    Returns:
        Result dict with keys: response, patch, elapsed_s, model, error,
        validation, sanitization (optional), attempts
    """
    validator = PatchValidator()
    sanitizer = PatchSanitizer()
    file_list = [f.strip() for f in changed_files.split(",") if f.strip()]

    results = []
    retry_context = ""  # Accumulate feedback for retries

    for attempt in range(max_retries + 1):
        # Modify body with retry feedback if this is a retry
        current_body = body
        if retry_context:
            current_body = f"{body}\n\n{retry_context}"

        # Generate patch
        logger.info(f"[OpenHands] Attempt {attempt + 1}/{max_retries + 1}")
        result = run_openhands_solver(
            issue, title, current_body, changed_files, source_code
        )

        if not result["patch"]:
            logger.warning(f"[OpenHands] Attempt {attempt + 1} generated no patch")
            results.append(result)
            continue

        # Validate
        validation = validator.validate(result["patch"], file_list)
        result["validation"] = {
            "is_valid": validation.is_valid,
            "errors": [{"type": e.type, "location": e.location, "message": e.message}
                       for e in validation.errors],
            "warnings": validation.warnings,
            "severity": validation.severity
        }

        # Try sanitization if fixable
        if not validation.is_valid and validation.severity == "fixable":
            logger.info(f"[OpenHands] Attempting sanitization ({len(validation.errors)} errors)")
            sanitized = sanitizer.sanitize(result["patch"], validation)

            if sanitized.success:
                # Re-validate sanitized patch
                revalidation = validator.validate(sanitized.sanitized_patch, file_list)
                if revalidation.is_valid:
                    logger.info(f"[OpenHands] Sanitization successful: {sanitized.fixes_applied}")
                    result["patch"] = sanitized.sanitized_patch
                    # Update validation to show post-sanitization state
                    result["validation"] = {
                        "is_valid": True,
                        "errors": [],  # Cleared by sanitization
                        "warnings": revalidation.warnings,
                        "severity": "minor",
                        "original_errors": [{"type": e.type, "location": e.location, "message": e.message}
                                           for e in validation.errors]
                    }
                    result["sanitization"] = {
                        "fixes_applied": sanitized.fixes_applied,
                        "success": True
                    }
                    validation = revalidation

        result["attempt"] = attempt + 1
        results.append(result)

        # If valid, return success
        if validation.is_valid:
            logger.info(f"[OpenHands] Valid patch generated on attempt {attempt + 1}")
            result["attempts"] = attempt + 1
            return result

        # If last attempt, return best effort
        if attempt == max_retries:
            logger.warning(f"[OpenHands] Max retries reached. Returning best attempt.")
            break

        # Build retry feedback for critical errors
        if validation.severity == "critical":
            retry_context = _build_retry_feedback(validation, attempt + 2)
            logger.info(f"[OpenHands] Retry {attempt + 2} with feedback (first 100 chars): {retry_context[:100]}...")

    # Return best result from all attempts
    best = _select_best_result(results)
    best["attempts"] = max_retries + 1
    return best
