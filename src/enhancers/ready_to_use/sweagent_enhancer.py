"""
SWE-agent-based enhancement for Category A.

Uses sweagent CLI (Docker deployment) pointed at a configured OpenAI-compatible
endpoint (e.g. OpenAI API with gpt-5.4-mini).

Key design decisions:
  - Uses ``sweagent run`` with ``--env.deployment.type=docker``
  - Runs the agent inside a python:3.12-slim container (no repo needed)
  - Uses TextProblemStatement with the enhancement prompt
  - Parses the trajectory JSON for ENHANCED_TITLE/ENHANCED_BODY
  - Returns explicit error metadata if sweagent is unavailable/fails
  - No fallback to llm_proxy

Environment variables (all optional):
  SWEAGENT_BASE_URL   - Base URL for OpenAI-compat endpoint (default: https://api.openai.com/v1)
  SWEAGENT_MODEL      - Model name (default: gpt-5.4-mini)
  SWEAGENT_API_KEY    - API key (default: OPENAI_API_KEY env var)
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

from src.enhancers.ready_to_use.native_output_parser import parse_enhanced_output

# ── installed sweagent path ──────────────────────────────────────────────────
_SWEAGENT_CLI = "/home/22pf2/BenchmarkLLMAgent/bench_env/bin/sweagent"

# ── defaults (all overridable via env) ────────────────────────────────────
_BASE_URL   = os.environ.get("SWEAGENT_BASE_URL", "https://api.openai.com/v1")
_MODEL      = os.environ.get("SWEAGENT_MODEL",    "gpt-5.4-mini")
_API_KEY    = os.environ.get("SWEAGENT_API_KEY",  os.environ.get("OPENAI_API_KEY", ""))
_TIMEOUT    = int(os.environ.get("SWEAGENT_TIMEOUT", "300"))
# ~30-step agent loop, matching the paper's stated configuration (was 10).
_MAX_STEPS  = int(os.environ.get("SWEAGENT_MAX_STEPS", "30"))
_EXECUTION_TIMEOUT = int(os.environ.get("SWEAGENT_EXECUTION_TIMEOUT", "120"))
_TEMPERATURE = float(os.environ.get("SWEAGENT_TEMPERATURE", "0"))
_NOOP_MAX_RETRIES = int(os.environ.get("SWEAGENT_NOOP_MAX_RETRIES", "2"))
_RETRY_TEMPERATURE = float(os.environ.get("SWEAGENT_RETRY_TEMPERATURE", "0.2"))

ENHANCEMENT_PROMPT = """\
You are SWE-agent, an autonomous coding agent by Princeton NLP.
Enhance the GitHub issue below so it is complete, clear, and actionable.

FIRST, investigate the codebase. The repository is checked out at /testbed (if it is
present). `cd /testbed` and search/read the source to find the code the issue describes.
Do NOT modify anything there and do NOT write a fix — this is investigation only.

Improvements to make:
- Add reproduction steps if missing
- Clarify expected vs actual behavior
- Reference the affected files/functions you VERIFIED in /testbed (never guess a path)
- Add a "## Code Context" section with real file paths, symbols and line numbers
- Add environment details where inferable
- Restructure for clarity using markdown sections
- Preserve the original report's information; add to it rather than replacing it

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
    title = title.strip()
    title = re.sub(r"\s+", " ", title)
    return title


def _clean_body(text: str) -> str:
    body = (text or "").strip()
    if body.startswith("```") and body.endswith("```"):
        body = body.strip("`").strip()
    return body


def _is_placeholder_title(title: str) -> bool:
    t = (title or "").strip().lower()
    if not t or t in ("...", "…"):
        return True
    placeholder_tokens = (
        "<improved single-line title>",
        "improved single-line title",
        "<improved single line title>",
        "improved single line title",
        "<improved title>",
        "improved title>",
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


def _is_quality_body(body: str, fallback_body: str) -> bool:
    text = (body or "").strip()
    if (
        not text
        or text == (fallback_body or "").strip()
        or _is_placeholder_body(text)
        or len(text) < 300
    ):
        return False

    lower = text.lower()
    if "was cancelled because it took more than" in lower:
        return False
    if "please try a different command" in lower:
        return False
    if "source of this error is if the command is interactive" in lower:
        return False

    has_summary = "summary" in lower
    has_steps = "steps" in lower or "reproduce" in lower or "reproduction" in lower
    has_expected_actual = "expected" in lower and "actual" in lower
    return has_summary and has_steps and has_expected_actual


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
    title, body, _ = parse_enhanced_output(text, fallback_title, fallback_body)
    return title, body


def _extract_from_trajectory(traj_path: Path, fallback_title: str, fallback_body: str) -> tuple[str, str]:
    """Parse sweagent trajectory JSON for enhanced content."""
    candidates: list[tuple[str, str]] = []

    def add_candidate(content: Any) -> None:
        if not isinstance(content, str) or not content.strip():
            return
        lowered = content.lower()
        has_markers = "enhanced_title:" in lowered or "enhanced_body:" in lowered
        has_issue_sections = (
            ("## summary" in lowered or "### summary" in lowered)
            and ("reproduce" in lowered or "steps" in lowered)
            and "expected" in lowered
            and "actual" in lowered
        )
        if has_markers or has_issue_sections:
            candidates.append(_parse_output(content, fallback_title, fallback_body))

    try:
        traj = json.loads(traj_path.read_text(encoding="utf-8"))
        # SWE-agent trajectory has 'history' with messages or 'trajectory' with steps
        # Try multiple known formats
        history = traj.get("history", [])
        trajectory = traj.get("trajectory", [])
        messages = traj.get("messages", [])

        # Check history messages
        for msg in reversed(history):
            content = ""
            if isinstance(msg, dict):
                content = msg.get("content", "") or msg.get("response", "") or ""
            elif isinstance(msg, str):
                content = msg
            add_candidate(content)

        # Check message-format trajectories used by newer SWE-agent versions
        for msg in reversed(messages):
            content = ""
            if isinstance(msg, dict):
                content = msg.get("content", "") or msg.get("response", "") or ""
            elif isinstance(msg, str):
                content = msg
            add_candidate(content)

        # Check trajectory steps
        for step in reversed(trajectory):
            if isinstance(step, dict):
                for key in ("response", "content", "thought", "action", "observation"):
                    content = step.get(key, "") or ""
                    add_candidate(content)

        # Also check top-level info field
        info = traj.get("info", {})
        if isinstance(info, dict):
            submission = info.get("submission", "") or ""
            add_candidate(submission)

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
    """Create a minimal sweagent config YAML for issue enhancement.

    Previous failure cause: temperature=0 with gpt-5.x models raises
    LiteLLM UnsupportedParamsError.  gpt-5 only supports temperature=1.
    top_p must be null (not 1.0) for the same reason.
    """
    # gpt-5.x models only support temperature=1 and reject top_p
    # Strip provider prefix (e.g. "openai/gpt-5.4-mini" → "gpt-5.4-mini") before check
    model_base = _MODEL.split("/")[-1].lower()
    if model_base.startswith("gpt-5"):
        effective_temperature = 1
        top_p_line = "    top_p: null"
    else:
        effective_temperature = temperature
        top_p_line = ""

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
    execution_timeout: {_EXECUTION_TIMEOUT}
    bundles:
      - path: tools/submit
    parse_function:
      type: single_bash_code_block
  model:
    name: {_MODEL if "/" in _MODEL else f"openai/{_MODEL}"}
    api_base: {_BASE_URL}
    api_key: {_API_KEY}
    per_instance_cost_limit: 0
    per_instance_call_limit: {_MAX_STEPS}
    total_cost_limit: 0
    temperature: {effective_temperature}
{top_p_line}
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
    docker_image: str = "",
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write config
        cfg_file = _create_sweagent_config(tmpdir, temperature)

        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()

        # Write task text to a file (avoids shell escaping issues with long text)
        task_file = Path(tmpdir) / "problem_statement.md"
        task_file.write_text(task_text, encoding="utf-8")

        # Repository access: run inside the instance's RepoLaunch image so the source
        # is present at /testbed, matching the paper's description. Falls back to a bare
        # python image only when no instance image is available.
        _image = docker_image or "python:3.12-slim"
        cmd = [
            _SWEAGENT_CLI, "run",
            "--config", str(cfg_file),
            "--env.deployment.type=docker",
            f"--env.deployment.image={_image}",
            f"--problem_statement.type=text_file",
            f"--problem_statement.path={task_file}",
            f"--output_dir={output_dir}",
        ]
        env = {
            **os.environ,
            "OPENAI_API_KEY": _API_KEY,
        }
        timed_out = False
        timeout_stdout = ""
        timeout_stderr = ""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                cwd=tmpdir,
                env=env,
            )
            returncode = result.returncode
            stdout_preview = (result.stdout or "")[:500]
            stderr_preview = (result.stderr or "")[:300]
        except subprocess.TimeoutExpired as e:
            # SWE-agent may produce the requested enhancement in its trajectory
            # but fail to call the submit tool before our wall-clock timeout.
            # Preserve a valid trajectory result instead of discarding it.
            timed_out = True
            returncode = None
            timeout_stdout = e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            timeout_stderr = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
            stdout_preview = timeout_stdout[:500]
            stderr_preview = timeout_stderr[:300]

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

        # SWE-agent stdout/stderr are rich execution logs and can contain echoed
        # prompt fragments or shell-planning text that resembles markers.  Only
        # trajectory content is accepted as a benchmark enhancement source.
        labeled = [
            ("trajectory", traj_title,   traj_body),
        ]

        # Track whether any raw candidate had placeholder text
        placeholder_detected = any(
            _is_placeholder_title(ct) or _is_placeholder_body(cb)
            for _, ct, cb in labeled
            if ct != title or cb != body
        )

        # Pick best candidate and track its source
        enh_title, enh_body = title, body
        best_score = _score_candidate(title, body, title, body)
        parse_source = "none"
        for src, raw_t, raw_b in labeled:
            ct = _clean_title(raw_t)
            cb = _clean_body(raw_b)
            if _is_placeholder_title(ct):
                ct = title
            if _is_placeholder_body(cb):
                cb = body
            if cb != body and not _is_quality_body(cb, body):
                ct = title
                cb = body
            score = _score_candidate(ct, cb, title, body)
            if score > best_score:
                enh_title, enh_body = ct, cb
                best_score = score
                parse_source = src

        return {
            "enhanced_title": enh_title,
            "enhanced_body": enh_body,
            "returncode": returncode,
            "stderr_preview": stderr_preview,
            "stdout_preview": stdout_preview,
            "trajectory_file_exists": traj_found,
            "trajectory_used": parse_source == "trajectory",
            "placeholder_detected": placeholder_detected,
            "parse_source": parse_source,
            "timed_out": timed_out,
        }


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    """Enhance using sweagent CLI (native only, no proxy fallback)."""
    title = issue.get("title") or issue.get("instance_id") or ""
    body = issue.get("body") or issue.get("problem_statement") or ""
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
                docker_image=issue.get("docker_image") or issue.get("image_name", ""),
            )
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
                "timed_out": run_result.get("timed_out", False),
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
    raw_returncode = final_result.get("returncode")
    returncode = int(raw_returncode) if raw_returncode is not None else None
    accepted_timeout_trajectory = (
        returncode is None
        and final_result.get("timed_out")
        and final_result.get("trajectory_used")
        and enh_title != title
        and enh_body != body
    )

    # Require returncode == 0: a non-zero exit means the CLI itself failed,
    # even if markers happen to appear in partial output.
    if returncode != 0 and not accepted_timeout_trajectory:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "swe_agent",
                "model": _MODEL,
                "base_url": _BASE_URL,
                "error": (
                    f"sweagent timeout after {_TIMEOUT}s"
                    if final_result.get("timed_out")
                    else f"sweagent exited with returncode {returncode}"
                ),
                "sweagent_returncode": returncode,
                "sweagent_stderr_preview": final_result.get("stderr_preview", ""),
                "trajectory_used": bool(final_result.get("trajectory_used")),
                "attempts": attempts,
            },
        }

    if enh_title == title and enh_body == body:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "swe_agent",
                "model": _MODEL,
                "base_url": _BASE_URL,
                "error": "sweagent exited 0 but no ENHANCED_TITLE/ENHANCED_BODY markers found",
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
            "parse_source": final_result.get("parse_source", "unknown"),
            "timed_out": bool(final_result.get("timed_out")),
            "warning": (
                f"sweagent timed out after {_TIMEOUT}s after producing parseable trajectory output"
                if accepted_timeout_trajectory
                else ""
            ),
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
