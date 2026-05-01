"""
SWE-agent-based enhancement for Category A.

Uses sweagent CLI (local deployment) pointed at a configured OpenAI-compatible
endpoint (e.g. vLLM with Devstral).

Key design decisions:
  - Uses ``sweagent run`` with ``--env.deployment.type=local``
  - Creates a lightweight temp git repo so the agent has a working directory
  - Uses TextProblemStatement with the enhancement prompt
  - Parses the trajectory JSON for ENHANCED_TITLE/ENHANCED_BODY
  - Returns explicit error metadata if sweagent is unavailable/fails
  - No fallback to llm_proxy

Environment variables (all optional):
  SWEAGENT_BASE_URL   - Base URL for OpenAI-compat endpoint (default: http://127.0.0.1:18000/v1)
  SWEAGENT_MODEL      - Model name as served by vLLM (default: Devstral-Small-2-24B-Instruct-2512)
  SWEAGENT_API_KEY    - API key (default: local-devstral)
  SWEAGENT_TIMEOUT    - Seconds before giving up (default: 300)
  SWEAGENT_MAX_STEPS  - Max agent steps (default: 10)
  SWEAGENT_TEMPERATURE - Temperature (default: 0)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

import sys
_here = Path(__file__).resolve()
_root = _here.parent.parent.parent.parent
sys.path.insert(0, str(_root))

# ── installed sweagent path ──────────────────────────────────────────────────
_SWEAGENT_CLI = "/home/22pf2/BenchmarkLLMAgent/bench_env/bin/sweagent"

# ── defaults (all overridable via env) ────────────────────────────────────
_BASE_URL   = os.environ.get("SWEAGENT_BASE_URL", "http://127.0.0.1:18000/v1")
_MODEL      = os.environ.get("SWEAGENT_MODEL",    "Devstral-Small-2-24B-Instruct-2512")
_API_KEY    = os.environ.get("SWEAGENT_API_KEY",   "local-devstral")
_TIMEOUT    = int(os.environ.get("SWEAGENT_TIMEOUT", "300"))
_MAX_STEPS  = int(os.environ.get("SWEAGENT_MAX_STEPS", "10"))
_TEMPERATURE = float(os.environ.get("SWEAGENT_TEMPERATURE", "0"))
_NOOP_MAX_RETRIES = int(os.environ.get("SWEAGENT_NOOP_MAX_RETRIES", "2"))
_RETRY_TEMPERATURE = float(os.environ.get("SWEAGENT_RETRY_TEMPERATURE", "0.2"))

ENHANCEMENT_PROMPT = """\
You are SWE-agent, an autonomous coding agent by Princeton NLP.
Enhance the GitHub issue below so it is complete, clear, and actionable.

Improvements to make:
- Add reproduction steps if missing
- Clarify expected vs actual behavior
- Reference affected files/components from the hints
- Add environment details where inferable
- Restructure for clarity using markdown sections

IMPORTANT: Output the result in EXACTLY this format (and nothing else before or after the --- delimiters):
---
ENHANCED_TITLE: <improved single-line title>
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


def _sweagent_available() -> bool:
    return os.path.exists(_SWEAGENT_CLI)


def _clean_title(text: str) -> str:
    title = (text or "").strip()
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


def _parse_output(text: str, fallback_title: str, fallback_body: str) -> tuple[str, str]:
    """Extract ENHANCED_TITLE and ENHANCED_BODY from output text."""
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
    """Parse sweagent trajectory JSON for enhanced content."""
    candidates: list[tuple[str, str]] = []
    try:
        traj = json.loads(traj_path.read_text(encoding="utf-8"))
        # SWE-agent trajectory has 'history' with messages or 'trajectory' with steps
        # Try multiple known formats
        history = traj.get("history", [])
        trajectory = traj.get("trajectory", [])

        # Check history messages
        for msg in reversed(history):
            content = ""
            if isinstance(msg, dict):
                content = msg.get("content", "") or msg.get("response", "") or ""
            elif isinstance(msg, str):
                content = msg
            if "ENHANCED_TITLE:" in content or "ENHANCED_BODY:" in content:
                candidates.append(_parse_output(content, fallback_title, fallback_body))

        # Check trajectory steps
        for step in reversed(trajectory):
            if isinstance(step, dict):
                for key in ("response", "content", "thought", "action", "observation"):
                    content = step.get(key, "") or ""
                    if "ENHANCED_TITLE:" in content or "ENHANCED_BODY:" in content:
                        candidates.append(_parse_output(content, fallback_title, fallback_body))

        # Also check top-level info field
        info = traj.get("info", {})
        if isinstance(info, dict):
            submission = info.get("submission", "") or ""
            if "ENHANCED_TITLE:" in submission or "ENHANCED_BODY:" in submission:
                candidates.append(_parse_output(submission, fallback_title, fallback_body))

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


def _create_sweagent_config(tmpdir: str, temperature: float) -> Path:
    """Create a minimal sweagent config YAML for issue enhancement."""
    cfg_path = Path(tmpdir) / "sweagent_enhance_config.yaml"
    config_text = f"""\
agent:
  type: default
  templates:
    system_template: |-
      You are a helpful assistant that enhances GitHub issue descriptions.
      Read the task carefully and output the enhanced issue in the exact format requested.
      Use the bash tool to echo your output, then run submit.
    instance_template: |-
      {{{{problem_statement}}}}

      When you have your enhanced issue ready, echo it using a bash command, then run `submit`.
    next_step_template: |-
      OBSERVATION:
      {{{{observation}}}}
    next_step_no_output_template: |-
      Your command ran successfully and did not produce any output.
  tools:
    execution_timeout: 60
    bundles:
      - path: tools/submit
    parse_function:
      type: single_bash_code_block
  model:
    name: openai/{_MODEL}
    api_base: {_BASE_URL}
    api_key: {_API_KEY}
    per_instance_cost_limit: 0
    per_instance_call_limit: {_MAX_STEPS}
    total_cost_limit: 0
    temperature: {temperature}
    delay: 0.0
    retry:
      retries: 3
      max_wait: 30
"""
    cfg_path.write_text(config_text, encoding="utf-8")
    return cfg_path


def _run_sweagent_once(
    *,
    task_text: str,
    title: str,
    body: str,
    temperature: float,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write config
        cfg_file = _create_sweagent_config(tmpdir, temperature)

        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()

        # Write task text to a file (avoids shell escaping issues with long text)
        task_file = Path(tmpdir) / "problem_statement.md"
        task_file.write_text(task_text, encoding="utf-8")

        # Use Docker deployment (local deployment requires root permissions)
        # No repo needed - enhancement is a text-only task
        cmd = [
            _SWEAGENT_CLI, "run",
            "--config", str(cfg_file),
            "--env.deployment.type=docker",
            "--env.deployment.image=python:3.12-slim",
            f"--problem_statement.type=text_file",
            f"--problem_statement.path={task_file}",
            f"--output_dir={output_dir}",
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

        # Parse stdout for ENHANCED_TITLE/ENHANCED_BODY
        output = (result.stdout or "").strip()
        output_title, output_body = _parse_output(output, title, body)

        # Also check stderr (sweagent sometimes puts agent output in logs)
        stderr = (result.stderr or "").strip()
        stderr_title, stderr_body = _parse_output(stderr, title, body)

        # Find trajectory files
        traj_title, traj_body = title, body
        traj_found = False
        for traj_path in output_dir.rglob("*.traj"):
            traj_found = True
            traj_title, traj_body = _extract_from_trajectory(traj_path, title, body)
            break

        # Also check for .json trajectory files
        if not traj_found:
            for traj_path in output_dir.rglob("*.json"):
                traj_found = True
                traj_title, traj_body = _extract_from_trajectory(traj_path, title, body)
                break

        # Track whether any raw candidate had placeholder text (before fallback replacement)
        raw_candidates = [(output_title, output_body), (stderr_title, stderr_body), (traj_title, traj_body)]
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
            "trajectory_used": traj_found,
            "placeholder_detected": placeholder_detected,
        }


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    """Enhance using sweagent CLI (native only, no proxy fallback)."""
    title = issue.get("title", "")
    body = issue.get("body") or ""
    if not _sweagent_available():
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "swe_agent",
                "error": f"sweagent CLI not found at {_SWEAGENT_CLI}",
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
            run_result = _run_sweagent_once(
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
                    "agent_id": "swe_agent",
                    "model": _MODEL,
                    "base_url": _BASE_URL,
                    "error": f"sweagent timeout after {_TIMEOUT}s",
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
        if run_result.get("placeholder_detected"):
            break

    if final_result is None:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "swe_agent",
                "model": _MODEL,
                "base_url": _BASE_URL,
                "error": run_errors[-1] if run_errors else "sweagent execution failed",
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
                "agent_id": "swe_agent",
                "model": _MODEL,
                "base_url": _BASE_URL,
                "sweagent_returncode": returncode,
                "sweagent_stderr_preview": final_result.get("stderr_preview", ""),
                "trajectory_used": bool(final_result.get("trajectory_used")),
                "attempts": attempts,
            },
        }

    return {
        "enhanced_title": enh_title,
        "enhanced_body": enh_body,
        "enhancement_metadata": {
            "enhancer_type": "real",
            "agent_id": "swe_agent",
            "model": _MODEL,
            "base_url": _BASE_URL,
            "sweagent_returncode": returncode,
            "sweagent_stderr_preview": final_result.get("stderr_preview", ""),
            "sweagent_stdout_preview": final_result.get("stdout_preview", ""),
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
