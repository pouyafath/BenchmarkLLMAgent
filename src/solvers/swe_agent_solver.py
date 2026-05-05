"""
SWE-agent 1.1.0 as a SWE-bench solver (batch mode).

Uses `sweagent run-batch --instances.type file` with a custom YAML config
that mirrors mini-SWE-agent's SWE-bench task framing for fair comparison.

Environment variables:
  SWEA_SOLVER_MODEL      model name (default: gpt-5.4-mini)
  SWEA_SOLVER_BASE_URL   OpenAI-compat base URL (default: https://api.openai.com/v1)
  SWEA_SOLVER_API_KEY    API key
  SWEA_SOLVER_MAX_STEPS  max agent steps (default: 30)
  SWEA_SOLVER_WORKERS    parallel workers (default: 2)
  SWEA_SOLVER_TIMEOUT    subprocess timeout in seconds (default: 7200)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_SWEAGENT_CLI = str(Path(__file__).resolve().parent.parent.parent / "bench_env" / "bin" / "sweagent")

_MODEL = os.environ.get("SWEA_SOLVER_MODEL", "gpt-5.4-mini")
_BASE_URL = os.environ.get("SWEA_SOLVER_BASE_URL", "https://api.openai.com/v1")
_API_KEY = os.environ.get("SWEA_SOLVER_API_KEY", "")
_MAX_STEPS = int(os.environ.get("SWEA_SOLVER_MAX_STEPS", "30"))
_WORKERS = int(os.environ.get("SWEA_SOLVER_WORKERS", "2"))
_TIMEOUT = int(os.environ.get("SWEA_SOLVER_TIMEOUT", "7200"))


def _build_config_yaml(model: str, base_url: str, api_key: str, max_steps: int) -> str:
    """Build a sweagent YAML config mirroring mini-SWE-agent's SWE-bench framing."""
    return f"""\
agent:
  type: default
  templates:
    system_template: |-
      You are a helpful assistant that can interact with a computer to solve tasks.
    instance_template: |-
      <uploaded_files>
      {{{{working_dir}}}}
      </uploaded_files>
      I've uploaded a python code repository in the directory {{{{working_dir}}}}. Consider the following PR description:

      <pr_description>
      {{{{problem_statement}}}}
      </pr_description>

      Can you help me implement the necessary changes to the repository so that the requirements specified in the <pr_description> are met?
      I've already taken care of all changes to any of the test files described in the <pr_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!
      Your task is to make the minimal changes to non-tests files in the {{{{working_dir}}}} directory to ensure the <pr_description> is satisfied.
      Follow these steps to resolve the issue:
      1. As a first step, it might be a good idea to find and read code relevant to the <pr_description>
      2. Create a script to reproduce the error and execute it with `python <filename.py>` using the bash tool, to confirm the error
      3. Edit the sourcecode of the repo to resolve the issue
      4. Rerun your reproduce script and confirm that the error is fixed!
      5. Think about edgecases and make sure your fix handles them as well
      Your thinking should be thorough and so it's fine if it's very long.
    next_step_template: |-
      OBSERVATION:
      {{{{observation}}}}
    next_step_no_output_template: |-
      Your last command ran successfully and did not produce any output.
  tools:
    execution_timeout: 300
    bundles:
      - path: tools/registry
      - path: tools/edit_anthropic
      - path: tools/review_on_submit_m
    enable_bash_tool: true
    parse_function:
      type: function_calling
    env_variables:
      PAGER: cat
      MANPAGER: cat
      LESS: -R
      PIP_PROGRESS_BAR: 'off'
      TQDM_DISABLE: '1'
      GIT_PAGER: cat
    registry_variables:
      USE_FILEMAP: 'true'
      SUBMIT_REVIEW_MESSAGES:
        - |
          Thank you for your work on this issue. Please carefully follow the steps below to help review your changes.

          1. If you made any changes to your code after running the reproduction script, please run the reproduction script again.
             If the reproduction script is failing, please revisit your changes and make sure they are correct.
             If you have already removed your reproduction script, please ignore this step.
          2. Remove your reproduction script (if you haven't done so already).
          3. If you have modified any TEST files, please revert them to the state they had before you started fixing the issue.
             You can do this with `git checkout -- /path/to/test/file.py`. Use below <diff> to find the files you need to revert.
          4. Run the submit command again to confirm.

          Here is a list of all of your changes:

          <diff>
          {{{{diff}}}}
          </diff>
  model:
    name: openai/{model}
    api_base: {base_url}
    api_key: {api_key}
    temperature: 0.0
    per_instance_cost_limit: 3.0
    per_instance_call_limit: {max_steps}
    total_cost_limit: 0
    delay: 0.0
    retry:
      retries: 3
      max_wait: 30
"""


def _to_sweagent_instance(inst: dict) -> dict:
    """Convert a solver-ready instance dict to SWE-agent SimpleBatchInstance format."""
    # Use our RepoLaunch image (docker_image), falling back to image_name
    image = inst.get("docker_image") or inst.get("image_name", "")
    return {
        "instance_id": inst["instance_id"],
        "image_name": image,
        "problem_statement": inst.get("problem_statement", ""),
        "repo_name": "testbed",
        "base_commit": inst.get("base_commit", "HEAD"),
    }


def _collect_preds(output_dir: Path, model: str) -> dict:
    """Collect all .pred files written by sweagent and build a preds.json dict."""
    results: dict = {}
    for pred_file in output_dir.rglob("*.pred"):
        try:
            data = json.loads(pred_file.read_text(encoding="utf-8"))
            iid = data.get("instance_id") or pred_file.parent.name
            patch = data.get("model_patch") or ""
            if patch is None:
                patch = ""
            results[iid] = {
                "instance_id": iid,
                "model_name_or_path": f"sweagent/{model}",
                "model_patch": str(patch),
            }
        except Exception as exc:
            logger.warning("Failed to parse pred file %s: %s", pred_file, exc)
    return results


def run_batch(
    instances: list[dict],
    api_key: str,
    work_dir: Path,
    preds_out: Path,
    *,
    model: str = _MODEL,
    base_url: str = _BASE_URL,
    max_steps: int = _MAX_STEPS,
    workers: int = _WORKERS,
    timeout: int = _TIMEOUT,
) -> dict:
    """Run SWE-agent on a batch of instances, write preds.json, return dict.

    Args:
        instances: List of solver-ready instance dicts (with docker_image, base_commit, etc.)
        api_key: OpenAI-compatible API key
        work_dir: Directory for sweagent output and config files
        preds_out: Path to write preds.json
        model: Model name (without openai/ prefix)
        base_url: OpenAI-compat base URL
        max_steps: Max agent steps per instance
        workers: Number of parallel workers
        timeout: Total subprocess timeout in seconds
    """
    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    # Load existing preds to allow resumption
    existing: dict = {}
    if preds_out.exists():
        try:
            existing = json.loads(preds_out.read_text())
        except Exception:
            existing = {}

    remaining = [i for i in instances if i["instance_id"] not in existing]
    logger.info("SWE-agent solver: %d/%d instances remaining", len(remaining), len(instances))

    if not remaining:
        preds_out.write_text(json.dumps(existing, indent=2))
        return existing

    # Write sweagent-format JSONL
    instances_jsonl = work_dir / "instances.jsonl"
    with instances_jsonl.open("w") as f:
        for inst in remaining:
            f.write(json.dumps(_to_sweagent_instance(inst)) + "\n")

    # Write config YAML
    cfg_file = work_dir / "sweagent_solver_config.yaml"
    cfg_file.write_text(
        _build_config_yaml(model, base_url, api_key, max_steps), encoding="utf-8"
    )

    output_dir = work_dir / "trajectories"
    output_dir.mkdir(exist_ok=True)

    cmd = [
        _SWEAGENT_CLI, "run-batch",
        "--config", str(cfg_file),
        "--instances.type", "file",
        "--instances.path", str(instances_jsonl),
        "--output_dir", str(output_dir),
        "--num_workers", str(workers),
        "--redo_existing=False",
    ]

    log_file = work_dir / "sweagent.log"
    env = {**os.environ, "OPENAI_API_KEY": api_key}

    logger.info("SWE-agent solver: launching %d instances with %d workers", len(remaining), workers)
    try:
        with log_file.open("w") as lf:
            subprocess.run(
                cmd,
                stdout=lf,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                cwd=str(work_dir),
                env=env,
            )
    except subprocess.TimeoutExpired:
        logger.warning("SWE-agent solver timed out after %ds (partial results may exist)", timeout)
    except Exception as exc:
        logger.error("SWE-agent solver error: %s", exc)

    # Collect .pred files written by sweagent
    new_results = _collect_preds(output_dir, model)
    logger.info("SWE-agent solver: collected %d pred files", len(new_results))

    # Merge with existing and write preds.json
    results = {**existing, **new_results}

    # For instances with no pred file (crashed/timeout), write empty patch
    for inst in remaining:
        iid = inst["instance_id"]
        if iid not in results:
            results[iid] = {
                "instance_id": iid,
                "model_name_or_path": f"sweagent/{model}",
                "model_patch": "",
            }

    preds_out.parent.mkdir(parents=True, exist_ok=True)
    preds_out.write_text(json.dumps(results, indent=2))
    logger.info("SWE-agent solver: wrote %d entries → %s", len(results), preds_out)
    return results
