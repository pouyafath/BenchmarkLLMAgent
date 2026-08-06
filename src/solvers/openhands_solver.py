"""
OpenHands CodeActAgent as a SWE-bench solver.

Uses the repo's RepoLaunch-built Docker image as the sandbox base, so the
agent starts with the exact repository state at the target commit (/testbed).

Environment variables:
  OH_SOLVER_MODEL      model name (default: gpt-5.4-mini)
  OH_SOLVER_BASE_URL   OpenAI-compat base URL (default: https://api.openai.com/v1)
  OH_SOLVER_API_KEY    API key
  OH_SOLVER_MAX_ITER   max agent iterations (default: 30)
  OH_SOLVER_TIMEOUT    subprocess timeout in seconds (default: 1800)
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MODEL = os.environ.get("OH_SOLVER_MODEL", "gpt-5.4-mini")
_BASE_URL = os.environ.get("OH_SOLVER_BASE_URL", "https://api.openai.com/v1")
_API_KEY = os.environ.get("OH_SOLVER_API_KEY", "")
_MAX_ITER = int(os.environ.get("OH_SOLVER_MAX_ITER", "30"))
_TIMEOUT = int(os.environ.get("OH_SOLVER_TIMEOUT", "1800"))

# Mirrors mini-SWE-agent's swebench_backticks.yaml task framing for fair comparison.
_TASK_TEMPLATE = """\
<pr_description>
Consider the following PR description:
{problem_statement}
</pr_description>

<instructions>
# Task Instructions

## Overview

You're a software engineer interacting continuously with a computer by submitting commands.
You'll be helping implement necessary changes to meet requirements in the PR description.
Your task is specifically to make changes to non-test files in the current directory in order
to fix the issue described in the PR description in a way that is general and consistent
with the codebase.

## Important Boundaries

- The repository is mounted at `/testbed`. You MUST change directory to `/testbed` to see the code.
- MODIFY: Regular source code files in `/testbed`
- DO NOT MODIFY: Tests, configuration files (pyproject.toml, setup.cfg, etc.)

## Recommended Workflow

1. `cd /testbed`
2. Analyze the codebase by finding and reading relevant files
3. Create a script to reproduce the issue
4. Edit the source code to resolve the issue
5. Verify your fix works by running your script again

## Submission

When you have completed your work, you MUST submit your changes as a git patch.
Run these steps IN ORDER, as SEPARATE commands:

Step 1 — create the patch in the shared workspace directory:
    cd /testbed && git diff > /workspace/oh_solution.patch

Step 2 — verify the patch is non-empty:
    cat /workspace/oh_solution.patch

The patch must only contain changes to the source files you modified to fix the issue.
Do NOT include test files, reproduction scripts, or build artifacts.
</instructions>"""


def _build_config_toml(docker_image: str, api_key: str, model: str, base_url: str, workspace_dir: str,
                       native_tool_calling: bool | None = None) -> str:
    ntc_line = "" if native_tool_calling is None else f"\nnative_tool_calling = {str(native_tool_calling).lower()}"
    return f"""[core]
workspace_base = "{workspace_dir}"

[llm]
model = "openai/{model}"
base_url = "{base_url}"
api_key = "{api_key}"
temperature = 0.3
max_output_tokens = 16384{ntc_line}

[sandbox]
base_container_image = "{docker_image}"
user_id = 0
timeout = 120
"""


def _ensure_model_healthy(base_url: str, model: str, api_key: str) -> None:
    """Verify the LLM responds with non-empty content; reload via Ollama if broken.

    Ollama-hosted reasoning models (e.g. gpt-oss:120b) can enter a corrupted
    state where they return empty responses after sustained use.  An unload +
    reload cycle restores normal operation.  For non-Ollama backends this is a
    no-op on failure (just logs a warning).
    """
    chat_url = base_url.rstrip("/") + "/chat/completions"
    # gpt-5.x reject max_tokens (require max_completion_tokens) and any non-default
    # temperature — sending the Ollama-style payload 400s. Mirror llm_client.py.
    _is_gpt5 = model.split("/")[-1].lower().startswith("gpt-5")
    _body = {"model": model, "messages": [{"role": "user", "content": "Say OK"}]}
    if _is_gpt5:
        _body["max_completion_tokens"] = 512
    else:
        _body["max_tokens"] = 256
        _body["temperature"] = 0.0
    payload = json.dumps(_body).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    def _ping() -> bool:
        try:
            req = urllib.request.Request(chat_url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            choices = data.get("choices", [])
            if not choices:
                return False
            content = (choices[0].get("message", {}).get("content", "") or "")
            if content.strip():
                return True
            # gpt-5.x can legitimately return empty *visible* content on a trivial
            # prompt (reasoning consumes the budget); a well-formed 200 with a
            # finish_reason still means the endpoint is alive. For Ollama, empty
            # content signals the corrupted state we actually want to catch.
            return _is_gpt5 and bool(choices[0].get("finish_reason"))
        except Exception as exc:
            logger.warning("Model health-check request failed: %s", exc)
            return False

    if _ping():
        return  # model is healthy

    logger.warning("Model returned empty response — attempting Ollama unload/reload cycle")
    # Ollama-specific: unload by setting keep_alive=0 via the generate endpoint
    ollama_base = base_url.rstrip("/").removesuffix("/v1")
    try:
        unload_payload = json.dumps({"model": model, "keep_alive": 0}).encode()
        req = urllib.request.Request(
            ollama_base + "/api/generate", data=unload_payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=30)
        time.sleep(5)  # allow GPU memory to be freed
    except Exception as exc:
        logger.warning("Ollama unload failed (may not be Ollama): %s", exc)

    # Retry — Ollama auto-loads on next request
    if _ping():
        logger.info("Model recovered after reload")
    else:
        logger.error("Model still unhealthy after reload — solver may produce empty patches")


def _extract_patch(output: str) -> str:
    """Extract git diff from OH_PATCH_START/OH_PATCH_END markers."""
    m = re.search(
        r"=== OH_PATCH_START ===\s*\n(.*?)\n=== OH_PATCH_END ===",
        output,
        re.DOTALL,
    )
    if m:
        candidate = m.group(1).strip()
        if candidate.startswith("diff --git"):
            return candidate

    # Fallback: find the last complete git diff block in the output
    blocks = list(re.finditer(r"(diff --git .+?)(?=\ndiff --git |\Z)", output, re.DOTALL))
    if blocks:
        return "\n".join(b.group(1).strip() for b in blocks)

    return ""


def solve_instance(
    instance: dict,
    api_key: str,
    work_dir: Path,
    *,
    model: str = _MODEL,
    base_url: str = _BASE_URL,
    max_iter: int = _MAX_ITER,
    timeout: int = _TIMEOUT,
    native_tool_calling: bool | None = None,
) -> dict:
    """Run OpenHands to fix one SWE-bench instance.

    Returns a preds.json-style entry dict:
        {"instance_id": ..., "model_name_or_path": ..., "model_patch": ...}
    """
    instance_id = instance["instance_id"]
    docker_image = instance.get("docker_image") or instance.get("image_name", "")
    problem_statement = instance.get("problem_statement", "")

    # Guard against Ollama model-state corruption (see docstring of _ensure_model_healthy)
    _ensure_model_healthy(base_url, model, api_key)

    # Always use absolute paths — OpenHands resolves paths relative to its own cwd,
    # not the caller's, so relative paths cause FileNotFoundError.
    inst_dir = work_dir.resolve() / instance_id
    inst_dir.mkdir(parents=True, exist_ok=True)

    task_file = inst_dir / "task.txt"
    task_file.write_text(_TASK_TEMPLATE.format(problem_statement=problem_statement), encoding="utf-8")

    workspace_dir = inst_dir / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    config_file = inst_dir / "config.toml"
    config_file.write_text(
        _build_config_toml(docker_image, api_key, model, base_url, str(workspace_dir),
                           native_tool_calling=native_tool_calling), encoding="utf-8"
    )

    cmd = [
        sys.executable,
        "-m", "openhands.core.main",
        "-f", str(task_file),
        "-i", str(max_iter),
        "--config-file", str(config_file),
    ]

    log_file = inst_dir / "openhands.log"
    patch = ""
    # DOCKER_BUILDKIT=0 forces the legacy builder which resolves local images
    # without trying Docker Hub first (our stage2_2026 images are local-only).
    env = {**os.environ, "DOCKER_BUILDKIT": "0"}
    try:
        with log_file.open("w") as lf:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=lf,
                text=True,
                timeout=timeout,
                cwd=str(inst_dir),
                env=env,
            )
        full_output = proc.stdout or ""
        # Write stdout log
        (inst_dir / "stdout.log").write_text(full_output, encoding="utf-8")

        patch_file = workspace_dir / "oh_solution.patch"
        if patch_file.exists():
            try:
                patch = patch_file.read_text(encoding="utf-8")
            except PermissionError:
                # The runtime container sometimes flushes the patch as its own UID with
                # 0600 perms, leaving it unreadable to the host process (seen ~2% of the
                # time in the 100-issue run). Recover it via a root container (root can
                # read 0600) instead of silently dropping a real patch.
                import subprocess as _sp
                _r = _sp.run(
                    ["docker", "run", "--rm", "-v", f"{workspace_dir.resolve()}:/mnt:ro",
                     "python:3.12-slim", "cat", "/mnt/oh_solution.patch"],
                    capture_output=True, text=True, timeout=120,
                )
                patch = _r.stdout or _extract_patch(full_output)
        else:
            patch = _extract_patch(full_output)
    except subprocess.TimeoutExpired:
        logger.warning("[%s] OpenHands solver timed out after %ds", instance_id, timeout)
        patch = ""
    except Exception as exc:
        logger.error("[%s] OpenHands solver error: %s", instance_id, exc)
        patch = ""

    return {
        "instance_id": instance_id,
        "model_name_or_path": f"openhands-codeact/{model}",
        "model_patch": patch,
    }


def run_batch(
    instances: list[dict],
    api_key: str,
    work_dir: Path,
    preds_out: Path,
    *,
    model: str = _MODEL,
    base_url: str = _BASE_URL,
    max_iter: int = _MAX_ITER,
    timeout: int = _TIMEOUT,
    workers: int = 2,
    native_tool_calling: bool | None = None,
) -> dict:
    """Run OpenHands solver on a batch of instances, write preds.json, return dict."""
    work_dir.mkdir(parents=True, exist_ok=True)

    # Load any existing preds to allow resumption
    existing: dict = {}
    if preds_out.exists():
        try:
            existing = json.loads(preds_out.read_text())
        except Exception:
            existing = {}

    remaining = [i for i in instances if i["instance_id"] not in existing]
    logger.info("OpenHands solver: %d/%d instances remaining", len(remaining), len(instances))

    def _solve(inst: dict) -> dict:
        return solve_instance(
            inst, api_key, work_dir,
            model=model, base_url=base_url,
            max_iter=max_iter, timeout=timeout,
            native_tool_calling=native_tool_calling,
        )

    results: dict = dict(existing)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_solve, inst): inst["instance_id"] for inst in remaining}
        for fut in concurrent.futures.as_completed(futs):
            iid = futs[fut]
            try:
                entry = fut.result()
                results[iid] = entry
                logger.info("[%s] patch length=%d chars", iid, len(entry.get("model_patch", "")))
            except Exception as exc:
                logger.error("[%s] future failed: %s", iid, exc)
                results[iid] = {"instance_id": iid, "model_name_or_path": f"openhands-codeact/{model}", "model_patch": ""}
            # Write incrementally so partial runs are recoverable
            preds_out.write_text(json.dumps(results, indent=2))

    preds_out.write_text(json.dumps(results, indent=2))
    logger.info("OpenHands solver: wrote %d entries → %s", len(results), preds_out)
    return results
