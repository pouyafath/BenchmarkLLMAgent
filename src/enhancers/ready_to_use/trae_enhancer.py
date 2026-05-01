"""
TRAE-based enhancement for Category A.

Uses trae-cli pointed at a configured OpenAI-compatible endpoint.

Key design decisions:
  - Uses -f <file> flag to pass task (not @file or positional arg)
  - Uses --console-type simple so output goes to stdout (not rich TTY)
  - Uses -t <trajectory_file> and parses trajectory JSON for the LLM's last response
  - Returns explicit native error metadata if trae-cli is unavailable/fails

Environment variables (all optional):
  TRAE_PROVIDER   - LLM provider for trae-cli (default: openai)
  TRAE_BASE_URL   - Base URL for OpenAI-compatible endpoint (default: http://localhost:8001/v1)
  TRAE_MODEL      - Model name as served by vLLM (default: gemma-3-12b-it)
  TRAE_API_KEY    - API key (default: dummy — vLLM does not require one locally)
  TRAE_TIMEOUT    - Seconds before giving up (default: 180)
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict

import sys
_here = Path(__file__).resolve()
_root = _here.parent.parent.parent.parent
sys.path.insert(0, str(_root))

# ── installed TRAE path ──────────────────────────────────────────────────────
_TRAE_CLI = "/home/22pf2/trae-agent/.venv/bin/trae-cli"

# ── defaults (all overridable via env) ──────────────────────────────────────
_PROVIDER  = os.environ.get("TRAE_PROVIDER",  "openai")
_BASE_URL  = os.environ.get("TRAE_BASE_URL",  "http://localhost:11434/v1")  # Ollama OpenAI-compat
_MODEL     = os.environ.get("TRAE_MODEL",     "gpt-oss:120b")
_API_KEY   = os.environ.get("TRAE_API_KEY",   "ollama")  # Ollama ignores this
_TIMEOUT   = int(os.environ.get("TRAE_TIMEOUT", "300"))   # 5 min — 120B is slower
_MAX_STEPS = int(os.environ.get("TRAE_MAX_STEPS", "10"))
_TEMPERATURE = float(os.environ.get("TRAE_TEMPERATURE", "0"))
_RETRY_TEMPERATURE = float(os.environ.get("TRAE_RETRY_TEMPERATURE", "0.2"))
_NOOP_MAX_RETRIES = int(os.environ.get("TRAE_NOOP_MAX_RETRIES", "2"))

ENHANCEMENT_PROMPT = """\
You are TRAE Agent, an autonomous coding agent by ByteDance.
Enhance the GitHub issue below so it is complete, clear, and actionable.

Improvements to make:
- Add reproduction steps if missing
- Clarify expected vs actual behavior
- Reference affected files/components from the hints
- Add environment details where inferable
- Restructure for clarity using markdown sections

CRITICAL: You MUST include the enhanced issue in your FINAL response (not inside a tool call) using EXACTLY this format:

---
ENHANCED_TITLE: <write the improved single-line title here>
ENHANCED_BODY:
<write the improved body as markdown here>
---

Do NOT just call task_done without first outputting the enhanced issue above. The enhanced title and body must appear in your response text."""

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


def _trae_available() -> bool:
    return os.path.exists(_TRAE_CLI)


def _clean_title(text: str) -> str:
    title = (text or "").strip()
    # Some CLI renderers can surround text with table separators.
    title = re.sub(r"^[\|\u2502]+\s*", "", title)
    title = re.sub(r"\s*[\|\u2502]+$", "", title)
    title = title.strip("` ").strip()
    title = re.sub(r"\s+", " ", title)
    return title


def _clean_body(text: str) -> str:
    body = (text or "").strip()
    if body.startswith("```") and body.endswith("```"):
        body = body.strip("`").strip()
    return body


def _is_placeholder_title(title: str) -> bool:
    t = (title or "").strip().lower()
    if not t:
        return True
    placeholder_tokens = (
        "<improved single-line title>",
        "improved single-line title",
        "<improved single line title>",
        "improved single line title",
        "<title>",
        "enhanced_title:",
    )
    return any(tok in t for tok in placeholder_tokens)


def _is_placeholder_body(body: str) -> bool:
    b = (body or "").strip().lower()
    if not b:
        return True
    placeholder_tokens = (
        "<improved body as markdown>",
        "improved body as markdown",
        "enhanced_body:",
    )
    return any(tok in b for tok in placeholder_tokens)


def _score_candidate(
    cand_title: str, cand_body: str, fallback_title: str, fallback_body: str
) -> int:
    score = 0
    if not _is_placeholder_title(cand_title):
        score += 1
        if cand_title.strip() != fallback_title.strip():
            score += 2
    else:
        score -= 3

    if not _is_placeholder_body(cand_body):
        score += 1
        if cand_body.strip() != fallback_body.strip():
            score += 2
    else:
        score -= 2

    return score


def _pick_best_candidate(
    candidates: list[tuple[str, str]], fallback_title: str, fallback_body: str
) -> tuple[str, str]:
    best = (fallback_title, fallback_body)
    best_score = _score_candidate(best[0], best[1], fallback_title, fallback_body)

    for raw_title, raw_body in candidates:
        cand_title = _clean_title(raw_title)
        cand_body = _clean_body(raw_body)

        if _is_placeholder_title(cand_title):
            cand_title = fallback_title
        if _is_placeholder_body(cand_body):
            cand_body = fallback_body

        score = _score_candidate(cand_title, cand_body, fallback_title, fallback_body)
        if score > best_score:
            best = (cand_title, cand_body)
            best_score = score

    return best


def _parse_trae_output(text: str, fallback_title: str, fallback_body: str) -> tuple[str, str]:
    """Extract ENHANCED_TITLE and ENHANCED_BODY from trae output text."""
    candidates: list[tuple[str, str]] = []
    if not text:
        return fallback_title, fallback_body

    strict_pattern = re.compile(
        r"---\s*ENHANCED_TITLE:\s*(.*?)\s*ENHANCED_BODY:\s*\r?\n([\s\S]*?)\s*---",
        re.IGNORECASE,
    )
    loose_pattern = re.compile(
        r"ENHANCED_TITLE:\s*(.*?)\s*ENHANCED_BODY:\s*\r?\n([\s\S]*?)(?=(?:\r?\n){0,2}---\s*(?:\r?\n|$)|ENHANCED_TITLE:|$)",
        re.IGNORECASE,
    )

    for m in strict_pattern.finditer(text):
        candidates.append((m.group(1), m.group(2)))
    for m in loose_pattern.finditer(text):
        candidates.append((m.group(1), m.group(2)))

    if not candidates:
        return fallback_title, fallback_body
    return _pick_best_candidate(candidates, fallback_title, fallback_body)


def _extract_from_trajectory(traj_path: Path, fallback_title: str, fallback_body: str) -> tuple[str, str]:
    """Parse trae trajectory JSON to extract the enhanced content from the last LLM response."""
    candidates: list[tuple[str, str]] = []

    def _check_text(text: str) -> None:
        if text and ("ENHANCED_TITLE:" in text or "ENHANCED_BODY:" in text):
            candidates.append(_parse_trae_output(text, fallback_title, fallback_body))

    try:
        traj = json.loads(traj_path.read_text(encoding="utf-8"))

        # trae trajectory uses "agent_steps" (not "steps")
        steps = traj.get("agent_steps", []) or traj.get("steps", [])
        for step in reversed(steps):
            # LLM response content lives in step["llm_response"]["content"]
            llm_resp = step.get("llm_response") or {}
            if isinstance(llm_resp, dict):
                _check_text(llm_resp.get("content", "") or "")
                # Also check tool_calls inside llm_response
                for tc in (llm_resp.get("tool_calls") or []):
                    _check_text(json.dumps(tc.get("arguments", {})) if isinstance(tc.get("arguments"), dict) else str(tc.get("arguments", "")))

            # Check tool_calls at step level (name + arguments)
            for tc in (step.get("tool_calls") or []):
                args = tc.get("arguments", {})
                if isinstance(args, dict):
                    # sequentialthinking stores content in "thought" arg
                    for val in args.values():
                        if isinstance(val, str):
                            _check_text(val)
                elif isinstance(args, str):
                    _check_text(args)

            # Check tool_results at step level
            for tr in (step.get("tool_results") or []):
                _check_text(tr.get("result", "") or "")

            # Legacy: step-level content/response (older trajectory formats)
            _check_text(step.get("content", "") or "")
            _check_text(step.get("response", "") or "")

        # Also scan llm_interactions (alternative location in trae trajectories)
        for interaction in (traj.get("llm_interactions") or []):
            resp = interaction.get("response", {})
            if isinstance(resp, dict):
                _check_text(resp.get("content", "") or "")

    except Exception:
        return fallback_title, fallback_body

    if not candidates:
        return fallback_title, fallback_body
    return _pick_best_candidate(candidates, fallback_title, fallback_body)


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
    return f"""Enhance the following GitHub issue.

Repository: {repo}
Issue #{num}

## Original Title
{title}

## Original Body
{body}

## Hints (files changed in the fix)
{changed_files}

{ENHANCEMENT_PROMPT}
{suffix}"""


def _run_trae_once(
    *,
    task_text: str,
    title: str,
    body: str,
    temperature: float,
) -> dict[str, Any]:
    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        task_file = Path(tmpdir) / "task.txt"
        traj_file = Path(tmpdir) / "trajectory.json"
        cfg_file = Path(tmpdir) / "trae_config.yaml"
        task_file.write_text(task_text, encoding="utf-8")

        config_text = f"""\
agents:
  trae_agent:
    enable_lakeview: false
    model: trae_agent_model
    max_steps: {_MAX_STEPS}
    tools:
      - sequentialthinking
      - task_done
model_providers:
  {_PROVIDER}:
    api_key: {_API_KEY}
    provider: {_PROVIDER}
    base_url: {_BASE_URL}
models:
  trae_agent_model:
    model_provider: {_PROVIDER}
    model: {_MODEL}
    max_tokens: 4096
    temperature: {temperature}
    top_p: 1
    top_k: 0
    max_retries: 3
    parallel_tool_calls: true
"""
        cfg_file.write_text(config_text, encoding="utf-8")

        cmd = [
            _TRAE_CLI, "run",
            "-f", str(task_file),
            "--working-dir", tmpdir,
            "--provider", _PROVIDER,
            "--model", _MODEL,
            "--model-base-url", _BASE_URL,
            "--api-key", _API_KEY,
            "--console-type", "simple",
            "--trajectory-file", str(traj_file),
            "--max-steps", str(_MAX_STEPS),
            "--config-file", str(cfg_file),
        ]
        env = {
            **os.environ,
            "OPENAI_API_KEY": _API_KEY,
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
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(str(e)) from e

        output = (result.stdout or "").strip()
        output_title, output_body = _parse_trae_output(output, title, body)
        traj_title, traj_body = title, body
        if traj_file.exists():
            traj_title, traj_body = _extract_from_trajectory(traj_file, title, body)

        # Track whether any raw candidate had placeholder text (before fallback replacement)
        raw_candidates = [(output_title, output_body), (traj_title, traj_body)]
        placeholder_detected = any(
            _is_placeholder_title(ct) or _is_placeholder_body(cb)
            for ct, cb in raw_candidates
            if ct != title or cb != body  # only check candidates that differ from fallback
        )

        enh_title, enh_body = _pick_best_candidate(
            raw_candidates,
            title,
            body,
        )

        return {
            "enhanced_title": enh_title,
            "enhanced_body": enh_body,
            "returncode": result.returncode,
            "stderr_preview": (result.stderr or "")[:300],
            "stdout_preview": (result.stdout or "")[:500],
            "trajectory_used": traj_file.exists(),
            "placeholder_detected": placeholder_detected,
        }


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    """Enhance using trae-cli (native only, no proxy fallback)."""
    title = issue.get("title", "")
    body = issue.get("body") or ""
    if not _trae_available():
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "trae",
                "error": f"trae-cli not found at {_TRAE_CLI}",
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
        temperature = _RETRY_TEMPERATURE if force_rewrite else _TEMPERATURE
        task_text = _build_task_text(
            repo=repo,
            num=num,
            title=title,
            body=body,
            changed_files=changed_files,
            force_rewrite=force_rewrite,
        )
        try:
            run_result = _run_trae_once(
                task_text=task_text,
                title=title,
                body=body,
                temperature=temperature,
            )
        except TimeoutError:
            return {
                "enhanced_title": title,
                "enhanced_body": body,
                "enhancement_metadata": {
                    "enhancer_type": "error",
                    "agent_id": "trae",
                    "provider": _PROVIDER,
                    "model": _MODEL,
                    "base_url": _BASE_URL,
                    "error": f"trae timeout after {_TIMEOUT}s",
                    "attempts": attempts,
                },
            }
        except Exception as e:
            run_errors.append(str(e))
            continue

        is_noop = (
            run_result.get("enhanced_title") == title
            and run_result.get("enhanced_body") == body
        )
        attempts.append(
            {
                "attempt": attempt_idx + 1,
                "force_rewrite": force_rewrite,
                "temperature": temperature,
                "returncode": run_result.get("returncode"),
                "trajectory_used": run_result.get("trajectory_used"),
                "enhancement_noop": is_noop,
                "placeholder_detected": run_result.get("placeholder_detected", False),
            }
        )

        if first_result is None:
            first_result = run_result
        final_result = run_result
        if not is_noop:
            break
        # If placeholder text was detected, retrying with force-rewrite won't help
        # (the LLM copied template text; forcing a rewrite just adds noise)
        if run_result.get("placeholder_detected"):
            break

    if final_result is None:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "trae",
                "provider": _PROVIDER,
                "model": _MODEL,
                "base_url": _BASE_URL,
                "error": run_errors[-1] if run_errors else "trae execution failed",
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
                "agent_id": "trae",
                "provider": _PROVIDER,
                "model": _MODEL,
                "base_url": _BASE_URL,
                "trae_returncode": returncode,
                "trae_stderr_preview": final_result.get("stderr_preview", ""),
                "trajectory_used": bool(final_result.get("trajectory_used")),
                "attempts": attempts,
            },
        }

    return {
        "enhanced_title": enh_title,
        "enhanced_body": enh_body,
        "enhancement_metadata": {
            "enhancer_type": "real",
            "agent_id": "trae",
            "provider": _PROVIDER,
            "model": _MODEL,
            "base_url": _BASE_URL,
            "trae_returncode": returncode,
            "trae_stderr_preview": final_result.get("stderr_preview", ""),
            "trae_stdout_preview": final_result.get("stdout_preview", ""),
            "trajectory_used": bool(final_result.get("trajectory_used")),
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
