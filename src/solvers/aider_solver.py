"""Aider CLI as a SWE-bench solver.

This wrapper runs the native `aider` CLI against the `/testbed` checkout from
each RepoLaunch Docker image, captures the resulting git diff, and writes
SWE-bench-compatible `preds.json` entries.

Environment variables:
  AIDER_SOLVER_MODEL       model name (default: openai/gpt-5.4-mini)
  AIDER_SOLVER_BASE_URL    OpenAI-compatible base URL
  AIDER_SOLVER_API_KEY     API key
  AIDER_SOLVER_TIMEOUT     per-instance timeout in seconds (default: 1800)
  AIDER_SOLVER_WORKERS     parallel workers (default: 1)
  AIDER_SOLVER_KEEP_REPOS  keep copied repos when set to 1 (default: 0)
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[2]
_AIDER_CLI = str(_ROOT / "bench_env" / "bin" / "aider")

_MODEL = os.environ.get("AIDER_SOLVER_MODEL", "openai/gpt-5.4-mini")
_BASE_URL = os.environ.get("AIDER_SOLVER_BASE_URL", "https://api.openai.com/v1")
_API_KEY = os.environ.get("AIDER_SOLVER_API_KEY", "")
_TIMEOUT = int(os.environ.get("AIDER_SOLVER_TIMEOUT", "1800"))
_WORKERS = int(os.environ.get("AIDER_SOLVER_WORKERS", "1"))
_KEEP_REPOS = os.environ.get("AIDER_SOLVER_KEEP_REPOS", "0") == "1"

_TASK_TEMPLATE = """\
We need modify this repository to solve one SWE-bench issue.

<pr_description>
{problem_statement}
</pr_description>

Instructions:
- Work in the current repository checkout.
- Make the minimal source-code changes needed to satisfy the PR description.
- Make the actual code edits now. Do not only describe a plan.
- Do not modify tests, test fixtures, benchmark metadata, lock files, or unrelated configuration.
- Do not create reproduction scripts or notes as final artifacts.
- Prefer reading relevant code before editing.
- When the fix is complete, stop. The final answer can be brief; the benchmark uses the git diff.
"""


def _aider_cmd() -> str:
    if Path(_AIDER_CLI).exists():
        return _AIDER_CLI
    found = shutil.which("aider")
    if found:
        return found
    raise FileNotFoundError(f"aider CLI not found at {_AIDER_CLI} or on PATH")


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _copy_testbed_from_image(image: str, repo_dir: Path, log_file: Path) -> None:
    cid = ""
    try:
        create = _run(["docker", "create", image, "sleep", "1"], timeout=180)
        log_file.write_text(
            f"$ docker create {image} sleep 1\n{create.stdout}{create.stderr}\n",
            encoding="utf-8",
        )
        if create.returncode != 0:
            raise RuntimeError(f"docker create failed for {image}: {create.stderr[:500]}")
        cid = create.stdout.strip()
        cp = _run(["docker", "cp", f"{cid}:/testbed", str(repo_dir)], timeout=900)
        with log_file.open("a", encoding="utf-8") as log:
            log.write(f"$ docker cp {cid}:/testbed {repo_dir}\n{cp.stdout}{cp.stderr}\n")
        if cp.returncode != 0:
            raise RuntimeError(f"docker cp failed for {image}: {cp.stderr[:500]}")
    finally:
        if cid:
            rm = _run(["docker", "rm", "-f", cid], timeout=60)
            with log_file.open("a", encoding="utf-8") as log:
                log.write(f"$ docker rm -f {cid}\n{rm.stdout}{rm.stderr}\n")


def _is_test_path(path: str) -> bool:
    parts = Path(path).parts
    name = Path(path).name
    return (
        "tests" in parts
        or "test" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".snap")
    )


def _is_forbidden_patch_path(path: str) -> bool:
    if path == ".gitignore" or path.startswith(".aider"):
        return True
    return _is_test_path(path)


def _restore_forbidden_changes(repo_dir: Path) -> list[str]:
    changed = _run(["git", "diff", "--name-only"], cwd=repo_dir, timeout=60)
    if changed.returncode != 0:
        return []
    forbidden_paths = [p for p in changed.stdout.splitlines() if p and _is_forbidden_patch_path(p)]
    if forbidden_paths:
        _run(["git", "checkout", "--", *forbidden_paths], cwd=repo_dir, timeout=120)
    return forbidden_paths


def _include_untracked_source_files(repo_dir: Path) -> list[str]:
    untracked = _run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=repo_dir,
        timeout=60,
    )
    if untracked.returncode != 0:
        return []
    paths = [p for p in untracked.stdout.splitlines() if p and not _is_forbidden_patch_path(p)]
    if paths:
        _run(["git", "add", "-N", "--", *paths], cwd=repo_dir, timeout=120)
    return paths


def _git_diff(repo_dir: Path) -> str:
    diff = _run(["git", "diff", "--"], cwd=repo_dir, timeout=120)
    if diff.returncode != 0:
        return ""
    return diff.stdout or ""


def solve_instance(
    instance: dict[str, Any],
    api_key: str,
    work_dir: Path,
    *,
    model: str = _MODEL,
    base_url: str = _BASE_URL,
    timeout: int = _TIMEOUT,
    keep_repo: bool = _KEEP_REPOS,
) -> dict[str, Any]:
    instance_id = instance["instance_id"]
    image = instance.get("docker_image") or instance.get("image_name", "")
    problem_statement = instance.get("problem_statement", "")
    inst_dir = work_dir.resolve() / instance_id
    repo_dir = inst_dir / "repo"
    inst_dir.mkdir(parents=True, exist_ok=True)

    prompt_file = inst_dir / "prompt.md"
    prompt_file.write_text(
        _TASK_TEMPLATE.format(problem_statement=problem_statement),
        encoding="utf-8",
    )

    patch = ""
    metadata: dict[str, Any] = {
        "instance_id": instance_id,
        "docker_image": image,
        "model": model,
        "base_url": base_url,
        "timeout": timeout,
        "returncode": None,
        "restored_forbidden_paths": [],
        "untracked_source_paths": [],
    }
    try:
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
        _copy_testbed_from_image(image, repo_dir, inst_dir / "docker.log")
        if not (repo_dir / ".git").exists():
            raise RuntimeError(f"{instance_id}: copied /testbed has no .git directory")

        _run(["git", "config", "--local", "user.email", "benchmark@example.com"], cwd=repo_dir)
        _run(["git", "config", "--local", "user.name", "Benchmark Solver"], cwd=repo_dir)

        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("AIDER_")}
        clean_env["OPENAI_API_KEY"] = api_key
        clean_env["OPENAI_API_BASE"] = base_url
        clean_env["AIDER_YES"] = "1"

        cmd = [
            _aider_cmd(),
            "--model",
            model,
            "--openai-api-base",
            base_url,
            "--message-file",
            str(prompt_file),
            "--yes-always",
            "--no-auto-commits",
            "--no-check-update",
            "--no-analytics",
            "--no-show-model-warnings",
            "--no-gitignore",
            "--no-pretty",
            "--no-stream",
            "--edit-format",
            "diff",
            "--map-tokens",
            "8192",
            "--chat-history-file",
            str(inst_dir / "aider.chat.history.md"),
            "--input-history-file",
            str(inst_dir / "aider.input.history"),
            "--llm-history-file",
            str(inst_dir / "aider.llm.history"),
        ]
        safe_cmd = ["***" if part == api_key else part for part in cmd]
        metadata["command"] = safe_cmd
        with (inst_dir / "aider.log").open("w", encoding="utf-8") as log:
            log.write("$ " + " ".join(safe_cmd) + "\n\n")
            proc = subprocess.run(
                cmd,
                cwd=str(repo_dir),
                env=clean_env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )
        metadata["returncode"] = proc.returncode

        restored = _restore_forbidden_changes(repo_dir)
        included = _include_untracked_source_files(repo_dir)
        patch = _git_diff(repo_dir)
        metadata["restored_forbidden_paths"] = restored
        metadata["untracked_source_paths"] = included
        metadata["changed_paths"] = _run(
            ["git", "diff", "--name-only", "--"],
            cwd=repo_dir,
            timeout=60,
        ).stdout.splitlines()
        if proc.returncode != 0:
            metadata["error"] = f"aider exited with returncode {proc.returncode}"
            # Keep a non-empty patch if aider managed to make changes before
            # exiting; the return code is recorded for audit.
    except subprocess.TimeoutExpired:
        metadata["error"] = f"aider timeout after {timeout}s"
        logger.warning("[%s] Aider solver timed out after %ds", instance_id, timeout)
    except Exception as exc:
        metadata["error"] = str(exc)
        logger.error("[%s] Aider solver error: %s", instance_id, exc)
    finally:
        (inst_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        (inst_dir / "patch.diff").write_text(patch, encoding="utf-8")
        if repo_dir.exists() and not keep_repo:
            shutil.rmtree(repo_dir, ignore_errors=True)

    return {
        "instance_id": instance_id,
        "model_name_or_path": f"aider/{model}",
        "model_patch": patch,
    }


def run_batch(
    instances: list[dict[str, Any]],
    api_key: str,
    work_dir: Path,
    preds_out: Path,
    *,
    model: str = _MODEL,
    base_url: str = _BASE_URL,
    timeout: int = _TIMEOUT,
    workers: int = _WORKERS,
) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if preds_out.exists():
        try:
            existing = json.loads(preds_out.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    remaining = [i for i in instances if i["instance_id"] not in existing]
    logger.info("Aider solver: %d/%d instances remaining", len(remaining), len(instances))

    results = dict(existing)

    def _solve(inst: dict[str, Any]) -> dict[str, Any]:
        return solve_instance(
            inst,
            api_key,
            work_dir,
            model=model,
            base_url=base_url,
            timeout=timeout,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = {pool.submit(_solve, inst): inst["instance_id"] for inst in remaining}
        for fut in concurrent.futures.as_completed(futs):
            iid = futs[fut]
            try:
                results[iid] = fut.result()
            except Exception as exc:
                logger.error("[%s] Aider solver future error: %s", iid, exc)
                results[iid] = {
                    "instance_id": iid,
                    "model_name_or_path": f"aider/{model}",
                    "model_patch": "",
                }
            preds_out.parent.mkdir(parents=True, exist_ok=True)
            preds_out.write_text(json.dumps(results, indent=2), encoding="utf-8")
            logger.info("Aider solver progress: %d/%d", len(results), len(instances))

    preds_out.parent.mkdir(parents=True, exist_ok=True)
    preds_out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results
