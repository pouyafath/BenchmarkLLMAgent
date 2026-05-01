#!/usr/bin/env python3
"""
Orchestrate creation of the `pouya_dataset_2026` benchmark dataset.

This workflow intentionally follows the SWE-bench-Live collection pipeline for:
- repository crawling and filtering
- issue/PR task extraction
- RepoLaunch-based environment setup
- executable validation

But it does NOT apply any description-quality filtering. Instead, it measures
quality signals and stores them as metadata for later analysis.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from itertools import cycle
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "data" / "samples" / "pouya_dataset_2026"
LIVE_ROOT = ROOT / "SWE-bench-Live-Collection"
LIVE_CURATION = LIVE_ROOT / "curation"
LIVE_TASKS = LIVE_CURATION / "swe_task_crawling"
LIVE_LAUNCH = LIVE_ROOT / "launch"
DEFAULT_TOKEN_FILE = ROOT / "tokens.txt"
VENDOR_DIR = ROOT / ".vendor"

if VENDOR_DIR.exists() and str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

REPOS_DIR = DATASET_DIR / "repos"
PRS_DIR = DATASET_DIR / "prs"
TASKS_DIR = DATASET_DIR / "tasks"
CACHE_DIR = DATASET_DIR / "cache"
ISSUE_CACHE_DIR = CACHE_DIR / "issues"
LAUNCH_DIR = DATASET_DIR / "launch"
VALIDATION_DIR = DATASET_DIR / "validation"
LOGS_DIR = DATASET_DIR / "logs"

RAW_REPOS_JSONL = REPOS_DIR / "raw_repos.jsonl"
FILTERED_REPOS_JSONL = REPOS_DIR / "filtered_repos.jsonl"
RAW_TASKS_JSONL = TASKS_DIR / "merged_raw_tasks.jsonl"
RAW_CANDIDATES_JSONL = DATASET_DIR / "raw_candidates.jsonl"
LAUNCH_READY_JSONL = DATASET_DIR / "launch_ready.jsonl"
VALIDATED_FULL_JSONL = DATASET_DIR / "validated_full.jsonl"
FROZEN_50_JSONL = DATASET_DIR / "frozen_50.jsonl"
REJECTED_CANDIDATES_JSONL = DATASET_DIR / "rejected_candidates.jsonl"
SUMMARY_JSON = DATASET_DIR / "collection_summary.json"
LAUNCH_CONFIG_JSON = LAUNCH_DIR / "config.json"
CRAWL_REPOS_PROGRESS_JSON = LOGS_DIR / "crawl-repos.progress.json"
FILTER_REPOS_PROGRESS_JSON = LOGS_DIR / "filter-repos.progress.json"
COLLECT_TASKS_PROGRESS_JSON = LOGS_DIR / "collect-tasks.progress.json"
BUILD_RAW_CANDIDATES_PROGRESS_JSON = LOGS_DIR / "build-raw-candidates.progress.json"
LAUNCH_SETUP_PROGRESS_JSON = LOGS_DIR / "launch-setup.progress.json"
LAUNCH_ORGANIZE_PROGRESS_JSON = LOGS_DIR / "launch-organize.progress.json"
MERGE_LAUNCH_PROGRESS_JSON = LOGS_DIR / "merge-launch.progress.json"
VALIDATE_PROGRESS_JSON = LOGS_DIR / "validate.progress.json"
GOLD_EVAL_PROGRESS_JSON = LOGS_DIR / "gold-eval.progress.json"
PROMOTE_VALIDATED_PROGRESS_JSON = LOGS_DIR / "promote.progress.json"
FREEZE_PROGRESS_JSON = LOGS_DIR / "freeze.progress.json"

DEFAULT_START_DATE = "2025-05-01"
DEFAULT_CUTOFF_DATE_COMPACT = "20250501"
DEFAULT_MIN_STARS = 1000
DEFAULT_MIN_TOTAL_PR_ISSUES = 200
DEFAULT_MIN_FORKS = 200
DEFAULT_MIN_LANG_PERCENT = 60.0

BUG_LABEL_KEYWORDS = {
    "bug",
    "bugs",
    "defect",
    "regression",
    "crash",
    "failure",
    "incorrect",
    "type: bug",
    "kind/bug",
    "kind: bug",
}
FEATURE_LABEL_KEYWORDS = {
    "feature",
    "enhancement",
    "proposal",
    "question",
    "docs",
    "documentation",
}
BUG_TEXT_PATTERNS = (
    "bug",
    "error",
    "exception",
    "traceback",
    "crash",
    "fails",
    "failing",
    "regression",
    "incorrect",
    "broken",
    "unexpected",
)


@dataclass
class GitHubIssueMetadata:
    issue_number: int
    created_at: str
    title: str
    body: str
    labels: list[str]
    html_url: str
    bug_like: bool
    feature_like: bool


def ensure_layout() -> None:
    for path in (
        DATASET_DIR,
        REPOS_DIR,
        PRS_DIR,
        TASKS_DIR,
        CACHE_DIR,
        ISSUE_CACHE_DIR,
        LAUNCH_DIR,
        VALIDATION_DIR,
        LOGS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def run_cmd(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"$ {' '.join(cmd)}")
    env = os.environ.copy()
    pythonpath_parts = []
    if VENDOR_DIR.exists():
        pythonpath_parts.append(str(VENDOR_DIR))
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    if pythonpath_parts:
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True, env=env)


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def read_progress(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def write_stage_progress(path: Path, stage: str, state: str, **payload: Any) -> None:
    progress = {
        "stage": stage,
        "state": state,
        "updated_at": int(time.time()),
    }
    progress.update(payload)
    write_json(path, progress)


def count_status_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.glob("*/status.json"))


def count_launch_results(workspace_root: Path, *, field: str) -> int:
    playground = workspace_root / "playground"
    if not playground.exists():
        return 0
    count = 0
    for result_path in playground.glob("*/result.json"):
        try:
            result = json.loads(result_path.read_text())
        except Exception:
            continue
        if result.get(field, False):
            count += 1
    return count


def run_cmd_monitored(
    cmd: list[str],
    *,
    cwd: Path | None,
    progress_file: Path,
    stage: str,
    total: int,
    completed_fn: Any,
    payload_fn: Any | None = None,
    on_poll: Any | None = None,
    poll_seconds: float = 5.0,
) -> None:
    print(f"$ {' '.join(cmd)}")
    env = os.environ.copy()
    pythonpath_parts = []
    if VENDOR_DIR.exists():
        pythonpath_parts.append(str(VENDOR_DIR))
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    if pythonpath_parts:
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    proc = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, env=env)
    try:
        while True:
            completed = max(0, min(total, int(completed_fn())))
            payload = {
                "total": total,
                "completed": completed,
                "remaining": max(total - completed, 0),
            }
            if payload_fn is not None:
                payload.update(payload_fn())
            retcode = proc.poll()
            state = "running" if retcode is None else ("done" if retcode == 0 else "failed")
            write_stage_progress(progress_file, stage, state, **payload)
            if on_poll is not None:
                on_poll(state, retcode)
            if retcode is not None:
                if retcode != 0:
                    raise subprocess.CalledProcessError(retcode, cmd)
                break
            time.sleep(poll_seconds)
    finally:
        if proc.poll() is None:
            proc.wait()


def load_tokens(token_file: Path | None) -> list[str]:
    resolved = token_file if token_file is not None else DEFAULT_TOKEN_FILE
    if resolved.exists():
        lines = [line.strip() for line in resolved.read_text().splitlines() if line.strip()]
        if lines:
            return lines
    env_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env_token:
        return [env_token]
    raise RuntimeError(
        f"No GitHub token found. Provide {DEFAULT_TOKEN_FILE} or set GITHUB_TOKEN / GH_TOKEN."
    )


def add_live_task_paths() -> None:
    for path in (str(LIVE_TASKS), str(LIVE_CURATION)):
        if path not in sys.path:
            sys.path.insert(0, path)


def repo_slug(repo: str) -> str:
    return repo.replace("/", "__")


def compact_date(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d")


def is_after_cutoff(created_at: str, start_date: str) -> bool:
    return created_at[:10] >= start_date


def quality_signals(problem_statement: str) -> dict[str, Any]:
    body = problem_statement or ""
    has_code_block = "```" in body or bool(re.search(r"(?m)^    \S", body))
    has_traceback = any(token in body for token in ("Traceback", "traceback", "Error:", "Exception"))
    has_reproduction_steps = any(
        token in body.lower()
        for token in (
            "steps to reproduce",
            "how to reproduce",
            "reproduction",
            "minimal example",
            "to reproduce",
            "repro",
        )
    )
    has_expected_behavior = any(
        token in body.lower()
        for token in ("expected", "should", "supposed to", "want")
    )
    word_count = len(body.split())
    body_length = len(body)
    total_signals = sum(
        int(flag)
        for flag in (
            has_code_block,
            has_traceback,
            has_reproduction_steps,
            has_expected_behavior,
        )
    )
    return {
        "word_count": word_count,
        "body_length": body_length,
        "has_code_block": has_code_block,
        "has_traceback": has_traceback,
        "has_reproduction_steps": has_reproduction_steps,
        "has_expected_behavior": has_expected_behavior,
        "total_signals": total_signals,
    }


def quality_bucket(problem_statement: str) -> str:
    stats = quality_signals(problem_statement)
    if stats["word_count"] < 50 or stats["total_signals"] == 0:
        return "vague"
    if stats["word_count"] < 200 or stats["total_signals"] <= 1:
        return "moderate"
    return "detailed"


def infer_bug_like(title: str, body: str, labels: list[str]) -> tuple[bool, bool]:
    label_set = {label.lower().strip() for label in labels}
    bug_like = bool(label_set & BUG_LABEL_KEYWORDS)
    feature_like = bool(label_set & FEATURE_LABEL_KEYWORDS)
    text = f"{title}\n{body}".lower()
    if not bug_like and any(pattern in text for pattern in BUG_TEXT_PATTERNS):
        bug_like = True
    return bug_like, feature_like


def issue_cache_path(repo: str, issue_number: int) -> Path:
    safe_repo = repo.replace("/", "__")
    return ISSUE_CACHE_DIR / f"{safe_repo}-{issue_number}.json"


def github_get(url: str, token_cycle: Any, params: dict[str, Any] | None = None) -> dict[str, Any]:
    while True:
        token = next(token_cycle)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        response = requests.get(url, headers=headers, params=params, timeout=60)
        if response.status_code == 429:
            reset = int(response.headers.get("X-RateLimit-Reset", 0))
            wait = max(60, reset - time.time()) + 5
            print(f"Rate limited (HTTP 429). Sleeping {wait:.0f}s before retry ...")
            time.sleep(wait)
            continue
        if response.status_code == 403:
            # Distinguish rate-limit (remaining=0) from forbidden/invalid-token (remaining != 0).
            # Forbidden means this token cannot access the resource at all — sleeping won't help.
            if response.headers.get("X-RateLimit-Remaining") == "0":
                reset = int(response.headers.get("X-RateLimit-Reset", 0))
                wait = max(60, reset - time.time()) + 5
                print(f"Rate limited (HTTP 403, quota exhausted). Sleeping {wait:.0f}s before retry ...")
                time.sleep(wait)
                continue
            # Forbidden or invalid token — raise immediately so the caller sees the error.
            response.raise_for_status()
        response.raise_for_status()
        return response.json()


def fetch_issue_metadata(repo: str, issue_number: int, token_cycle: cycle[str]) -> GitHubIssueMetadata:
    cache_file = issue_cache_path(repo, issue_number)
    if cache_file.exists():
        data = json.loads(cache_file.read_text())
    else:
        owner, name = repo.split("/")
        data = github_get(f"https://api.github.com/repos/{owner}/{name}/issues/{issue_number}", token_cycle)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data, indent=2))

    labels = [
        label["name"] if isinstance(label, dict) else str(label)
        for label in data.get("labels", [])
    ]
    bug_like, feature_like = infer_bug_like(data.get("title", ""), data.get("body", "") or "", labels)
    return GitHubIssueMetadata(
        issue_number=int(data["number"]),
        created_at=data["created_at"],
        title=data.get("title", ""),
        body=data.get("body") or "",
        labels=labels,
        html_url=data.get("html_url", ""),
        bug_like=bug_like,
        feature_like=feature_like,
    )


def merge_task_files(input_folder: Path, output_file: Path, repos_file: Path) -> int:
    repo_list = [json.loads(line) for line in repos_file.read_text().splitlines() if line.strip()]
    repo_dict = {row["full_name"]: row for row in repo_list}
    count = 0
    with output_file.open("w", encoding="utf-8") as out:
        for task_file in sorted(input_folder.glob("*.jsonl")):
            if task_file.resolve() == output_file.resolve():
                continue  # never include the merge output in its own input
            for line in task_file.read_text().splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                row["language"] = repo_dict.get(row["repo"], {}).get("language", "Python")
                out.write(json.dumps(row) + "\n")
                count += 1
    return count


def repo_collection_paths(repo: str, cutoff_date: str) -> dict[str, Path]:
    slug = repo_slug(repo)
    return {
        "issues": PRS_DIR / f"{slug}-issues-{cutoff_date}.jsonl",
        "pull2issue": PRS_DIR / f"{slug}-pull2issue-{cutoff_date}.jsonl",
        "prs": PRS_DIR / f"{slug}-prs.jsonl",
        "task": TASKS_DIR / f"{slug}-task-instances.jsonl",
    }


def fetch_pulls_safe(repo: str, token: str, cutoff_date: str) -> Path:
    from fetch_pulls import collect_closed_issues

    owner, repo_name = repo.split("/")
    paths = repo_collection_paths(repo, cutoff_date)
    print(f"[{repo}] Fetching closed issues ...")
    collect_closed_issues(owner, repo_name, token, str(paths["issues"]), cutoff_date)

    if not paths["issues"].exists():
        print(f"[{repo}] Found no issues closed by a pull.")
        paths["pull2issue"].write_text("", encoding="utf-8")
        return paths["pull2issue"]

    pull2issue: dict[int, list[int]] = {}
    with paths["issues"].open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            instance = json.loads(line)
            pull_number = int(instance["pull_number"])
            issue_number = int(instance["issue_number"])
            pull2issue.setdefault(pull_number, []).append(issue_number)

    with paths["pull2issue"].open("w", encoding="utf-8") as f:
        for pull_number, issue_numbers in pull2issue.items():
            f.write(json.dumps({"pull": pull_number, "issue": issue_numbers}) + "\n")
    print(f"[{repo}] Saved {len(pull2issue)} closed issue data instances.")
    return paths["pull2issue"]


def summarize_raw_candidates(
    raw_candidates: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    start_date: str = DEFAULT_START_DATE,
) -> dict[str, Any]:
    quality_counts: dict[str, int] = {}
    rejection_counts: dict[str, int] = {}
    for row in raw_candidates:
        bucket = row["quality_bucket"]
        quality_counts[bucket] = quality_counts.get(bucket, 0) + 1
    for row in rejected:
        reason = row.get("rejection_reason", "unknown")
        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
    return {
        "collection_track": "pouya_dataset_2026",
        "start_date": start_date,
        "raw_candidates": len(raw_candidates),
        "rejected_candidates": len(rejected),
        "quality_bucket_counts": quality_counts,
        "rejection_reason_counts": rejection_counts,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def cmd_status(_: argparse.Namespace) -> None:
    """Print a stage-by-stage progress summary for the current pipeline run."""
    def crawl_progress_summary() -> str | None:
        progress = read_progress(CRAWL_REPOS_PROGRESS_JSON)
        if progress is None:
            return None
        completed = int(progress.get("completed", 0) or 0)
        state = str(progress.get("state", "running")).upper()
        return f"{state:<7} {completed} fetched so far"

    def filter_progress_summary() -> str | None:
        progress = read_progress(FILTER_REPOS_PROGRESS_JSON)
        if progress is None:
            return None

        total = int(progress.get("total", 0) or 0)
        completed = int(progress.get("completed", 0) or 0)
        kept = int(progress.get("kept", 0) or 0)
        remaining = max(total - completed, 0)
        state = str(progress.get("state", "running")).upper()
        return (
            f"{state:<7} {completed}/{total} done, {remaining} remaining, "
            f"{kept} kept so far"
        )

    def collect_progress_summary() -> str | None:
        progress = read_progress(COLLECT_TASKS_PROGRESS_JSON)
        if progress is None:
            return None

        total = int(progress.get("total", 0) or 0)
        completed = int(progress.get("completed", 0) or 0)
        task_repos = int(progress.get("task_repos", 0) or 0)
        task_instances = int(progress.get("task_instances", 0) or 0)
        remaining = max(total - completed, 0)
        state = str(progress.get("state", "running")).upper()
        return (
            f"{state:<7} {completed}/{total} done, {remaining} remaining, "
            f"{task_repos} repos with tasks, {task_instances} task instances"
        )

    def build_raw_progress_summary() -> str | None:
        progress = read_progress(BUILD_RAW_CANDIDATES_PROGRESS_JSON)
        if progress is None:
            return None
        total = int(progress.get("total", 0) or 0)
        completed = int(progress.get("completed", 0) or 0)
        kept = int(progress.get("kept", 0) or 0)
        rejected = int(progress.get("rejected", 0) or 0)
        remaining = max(total - completed, 0)
        state = str(progress.get("state", "running")).upper()
        return (
            f"{state:<7} {completed}/{total} done, {remaining} remaining, "
            f"{kept} kept, {rejected} rejected"
        )

    def launch_setup_progress_summary() -> str | None:
        progress = read_progress(LAUNCH_SETUP_PROGRESS_JSON)
        if progress is None:
            return None
        total = int(progress.get("total", 0) or 0)
        completed = int(progress.get("completed", 0) or 0)
        remaining = max(total - completed, 0)
        state = str(progress.get("state", "running")).upper()
        return f"{state:<7} {completed}/{total} done, {remaining} remaining"

    def launch_organize_progress_summary() -> str | None:
        progress = read_progress(LAUNCH_ORGANIZE_PROGRESS_JSON)
        if progress is None:
            return None
        total = int(progress.get("total", 0) or 0)
        completed = int(progress.get("completed", 0) or 0)
        remaining = max(total - completed, 0)
        state = str(progress.get("state", "running")).upper()
        return f"{state:<7} {completed}/{total} done, {remaining} remaining"

    def merge_launch_progress_summary() -> str | None:
        progress = read_progress(MERGE_LAUNCH_PROGRESS_JSON)
        if progress is None:
            return None
        total = int(progress.get("total", 0) or 0)
        completed = int(progress.get("completed", 0) or 0)
        merged = int(progress.get("merged", 0) or 0)
        missing = int(progress.get("missing_raw", 0) or 0)
        remaining = max(total - completed, 0)
        state = str(progress.get("state", "running")).upper()
        return (
            f"{state:<7} {completed}/{total} done, {remaining} remaining, "
            f"{merged} merged, {missing} missing"
        )

    def validate_progress_summary() -> str | None:
        progress = read_progress(VALIDATE_PROGRESS_JSON)
        if progress is None:
            return None
        total = int(progress.get("total", 0) or 0)
        completed = int(progress.get("completed", 0) or 0)
        remaining = max(total - completed, 0)
        state = str(progress.get("state", "running")).upper()
        return f"{state:<7} {completed}/{total} done, {remaining} remaining"

    def gold_progress_summary() -> str | None:
        progress = read_progress(GOLD_EVAL_PROGRESS_JSON)
        if progress is None:
            return None
        total = int(progress.get("total", 0) or 0)
        completed = int(progress.get("completed", 0) or 0)
        remaining = max(total - completed, 0)
        current_run = int(progress.get("current_run", 1) or 1)
        total_runs = int(progress.get("total_runs", 1) or 1)
        state = str(progress.get("state", "running")).upper()
        return (
            f"{state:<7} run {current_run}/{total_runs}, "
            f"{completed}/{total} done, {remaining} remaining"
        )

    def promote_progress_summary() -> str | None:
        progress = read_progress(PROMOTE_VALIDATED_PROGRESS_JSON)
        if progress is None:
            return None
        total = int(progress.get("total", 0) or 0)
        completed = int(progress.get("completed", 0) or 0)
        validated = int(progress.get("validated", 0) or 0)
        rejected = int(progress.get("rejected", 0) or 0)
        remaining = max(total - completed, 0)
        state = str(progress.get("state", "running")).upper()
        return (
            f"{state:<7} {completed}/{total} done, {remaining} remaining, "
            f"{validated} validated, {rejected} rejected"
        )

    def freeze_progress_summary() -> str | None:
        progress = read_progress(FREEZE_PROGRESS_JSON)
        if progress is None:
            return None
        total = int(progress.get("total", 0) or 0)
        count = int(progress.get("count", 0) or 0)
        state = str(progress.get("state", "running")).upper()
        return f"{state:<7} freezing {count} from {total} validated"

    progress_summaries = {
        "crawl-repos": crawl_progress_summary,
        "filter-repos": filter_progress_summary,
        "collect-tasks": collect_progress_summary,
        "build-raw-cands": build_raw_progress_summary,
        "launch-setup": launch_setup_progress_summary,
        "launch-organize": launch_organize_progress_summary,
        "merge-launch": merge_launch_progress_summary,
        "validate": validate_progress_summary,
        "gold-eval": gold_progress_summary,
        "promote": promote_progress_summary,
        "freeze": freeze_progress_summary,
    }

    stages = [
        ("crawl-repos",       RAW_REPOS_JSONL,          "raw repos crawled"),
        ("filter-repos",      FILTERED_REPOS_JSONL,     "repos after filtering"),
        ("collect-tasks",     RAW_TASKS_JSONL,          "raw task instances merged"),
        ("build-raw-cands",   RAW_CANDIDATES_JSONL,     "raw candidates"),
        ("launch-setup",      LAUNCH_DIR / "workspace" / "setup.jsonl", "launch setup completed"),
        ("launch-organize",   LAUNCH_DIR / "workspace" / "organize.jsonl", "launch organize completed"),
        ("merge-launch",      LAUNCH_READY_JSONL,       "launch-ready instances"),
        ("validate",          VALIDATION_DIR / "validation_logs" / "validated_instances.jsonl", "validated instances"),
        ("gold-eval",         VALIDATION_DIR / "gold_eval_logs" / "gold_patch_evaluated_instances.jsonl", "gold-confirmed instances"),
        ("promote",           VALIDATED_FULL_JSONL,     "in validated_full"),
        ("freeze",            FROZEN_50_JSONL,          "in frozen_50"),
    ]
    print(f"\nPipeline status for: {DATASET_DIR}\n")
    for stage, path, label in stages:
        progress = read_progress({
            "crawl-repos": CRAWL_REPOS_PROGRESS_JSON,
            "filter-repos": FILTER_REPOS_PROGRESS_JSON,
            "collect-tasks": COLLECT_TASKS_PROGRESS_JSON,
            "build-raw-cands": BUILD_RAW_CANDIDATES_PROGRESS_JSON,
            "launch-setup": LAUNCH_SETUP_PROGRESS_JSON,
            "launch-organize": LAUNCH_ORGANIZE_PROGRESS_JSON,
            "merge-launch": MERGE_LAUNCH_PROGRESS_JSON,
            "validate": VALIDATE_PROGRESS_JSON,
            "gold-eval": GOLD_EVAL_PROGRESS_JSON,
            "promote": PROMOTE_VALIDATED_PROGRESS_JSON,
            "freeze": FREEZE_PROGRESS_JSON,
        }[stage])
        if progress is not None and str(progress.get("state", "")).lower() == "running":
            status = progress_summaries[stage]() or "RUNNING"
            marker = ">"
        else:
            n = count_jsonl_rows(path) if path.exists() else -1
            if n >= 0:
                status = f"{n:>5} {label}"
                marker = "✓"
            elif progress is not None:
                status = progress_summaries[stage]() or "       NOT YET RUN"
                marker = "!" if str(progress.get("state", "")).lower() == "failed" else "·"
            else:
                status = "       NOT YET RUN"
                marker = "·"
        print(f"  {marker}  {stage:<22}  {status}")
    print()


def cmd_init(_: argparse.Namespace) -> None:
    ensure_layout()
    print(f"Initialized dataset layout under {DATASET_DIR}")


def cmd_crawl_repos(args: argparse.Namespace) -> None:
    ensure_layout()
    token_file = Path(args.token_file)
    run_cmd(
        [
            sys.executable,
            str(LIVE_CURATION / "crawl_repo.py"),
            "--language",
            "Python",
            "--min_stars",
            str(args.min_stars),
            "--tokens_file",
            str(token_file),
            "--output_file",
            str(RAW_REPOS_JSONL),
            "--progress_file",
            str(Path(args.progress_file)),
        ],
        cwd=LIVE_CURATION,
    )


def cmd_filter_repos(args: argparse.Namespace) -> None:
    ensure_layout()
    if not RAW_REPOS_JSONL.exists():
        raise FileNotFoundError(f"Run crawl-repos first: {RAW_REPOS_JSONL} missing")
    token_file = Path(args.token_file)
    run_cmd(
        [
            sys.executable,
            str(LIVE_CURATION / "filter_repo.py"),
            "--input_file",
            str(RAW_REPOS_JSONL),
            "--output_file",
            str(FILTERED_REPOS_JSONL),
            "--tokens_file",
            str(token_file),
            "--language",
            "Python",
            "--min_total_pr_issues",
            str(args.min_total_pr_issues),
            "--min_forks",
            str(args.min_forks),
            "--min_lang_percent",
            str(args.min_lang_percent),
            "--max_workers",
            str(args.max_workers),
            "--progress_file",
            str(Path(args.progress_file)),
        ],
        cwd=LIVE_CURATION,
    )


def cmd_collect_tasks(args: argparse.Namespace) -> None:
    ensure_layout()
    if not FILTERED_REPOS_JSONL.exists():
        raise FileNotFoundError(f"Run filter-repos first: {FILTERED_REPOS_JSONL} missing")
    add_live_task_paths()
    from build_dataset import main as build_dataset_main
    from print_pulls import log_selected_pulls

    tokens = load_tokens(Path(args.token_file))
    repos = [
        json.loads(line)["full_name"]
        for line in FILTERED_REPOS_JSONL.read_text().splitlines()
        if line.strip()
    ]
    if args.limit_repos > 0:
        repos = repos[: args.limit_repos]
    cutoff_date = compact_date(args.start_date)

    worker_count = max(1, min(args.max_workers, len(tokens), len(repos)))
    work_queue: Queue[str] = Queue()
    for repo in repos:
        work_queue.put(repo)

    progress_lock = threading.Lock()
    progress = {
        "stage": "collect-tasks",
        "state": "running",
        "total": len(repos),
        "completed": 0,
        "remaining": len(repos),
        "selected_pr_repos": 0,
        "task_repos": 0,
        "task_instances": 0,
        "skipped_existing": 0,
        "no_linked_issue": 0,
        "errors": 0,
        "workers": worker_count,
        "updated_at": int(time.time()),
    }
    write_json(Path(args.progress_file), progress)

    def update_progress(
        *,
        state: str | None = None,
        completed_delta: int = 0,
        selected_pr_repos_delta: int = 0,
        task_repos_delta: int = 0,
        task_instances_delta: int = 0,
        skipped_existing_delta: int = 0,
        no_linked_issue_delta: int = 0,
        errors_delta: int = 0,
    ) -> None:
        with progress_lock:
            if state is not None:
                progress["state"] = state
            progress["completed"] += completed_delta
            progress["selected_pr_repos"] += selected_pr_repos_delta
            progress["task_repos"] += task_repos_delta
            progress["task_instances"] += task_instances_delta
            progress["skipped_existing"] += skipped_existing_delta
            progress["no_linked_issue"] += no_linked_issue_delta
            progress["errors"] += errors_delta
            progress["remaining"] = max(progress["total"] - progress["completed"], 0)
            progress["updated_at"] = int(time.time())
            write_json(Path(args.progress_file), progress)

    def worker(token: str) -> None:
        while True:
            try:
                repo = work_queue.get_nowait()
            except Empty:
                return

            paths = repo_collection_paths(repo, cutoff_date)
            try:
                if paths["task"].exists() and paths["task"].stat().st_size > 0:
                    print(f"[{repo}] task file exists, skipping")
                    update_progress(
                        completed_delta=1,
                        skipped_existing_delta=1,
                    )
                    continue

                fetch_pulls_safe(repo, token, cutoff_date)
                if not paths["pull2issue"].exists() or paths["pull2issue"].stat().st_size == 0:
                    print(f"[{repo}] no linked issue->PR pairs found, skipping")
                    update_progress(
                        completed_delta=1,
                        no_linked_issue_delta=1,
                    )
                    continue

                log_selected_pulls(repo, str(paths["prs"]), str(paths["pull2issue"]), token)
                build_dataset_main(str(paths["prs"]), str(paths["task"]), token)

                selected_pr_rows = count_jsonl_rows(paths["prs"])
                task_rows = count_jsonl_rows(paths["task"])
                update_progress(
                    completed_delta=1,
                    selected_pr_repos_delta=int(selected_pr_rows > 0),
                    task_repos_delta=int(task_rows > 0),
                    task_instances_delta=task_rows,
                )
            except Exception as exc:
                print(f"[{repo}] worker error: {exc}")
                update_progress(
                    completed_delta=1,
                    errors_delta=1,
                )
            finally:
                work_queue.task_done()

    threads = [
        threading.Thread(target=worker, name=f"collect-tasks-{i+1}", args=(tokens[i],), daemon=True)
        for i in range(worker_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    update_progress(state="done")

    merged = merge_task_files(TASKS_DIR, RAW_TASKS_JSONL, FILTERED_REPOS_JSONL)
    print(f"Merged {merged} task instances into {RAW_TASKS_JSONL}")


def cmd_build_raw_candidates(args: argparse.Namespace) -> None:
    ensure_layout()
    if not RAW_TASKS_JSONL.exists():
        raise FileNotFoundError(f"Run collect-tasks first: {RAW_TASKS_JSONL} missing")
    tokens = cycle(load_tokens(Path(args.token_file)))
    raw_tasks = [json.loads(line) for line in RAW_TASKS_JSONL.read_text().splitlines() if line.strip()]
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    progress_file = Path(args.progress_file)
    write_stage_progress(
        progress_file,
        "build-raw-cands",
        "running",
        total=len(raw_tasks),
        completed=0,
        remaining=len(raw_tasks),
        kept=0,
        rejected=0,
    )

    def update_progress() -> None:
        write_stage_progress(
            progress_file,
            "build-raw-cands",
            "running",
            total=len(raw_tasks),
            completed=len(kept) + len(rejected),
            remaining=max(len(raw_tasks) - len(kept) - len(rejected), 0),
            kept=len(kept),
            rejected=len(rejected),
        )

    for row in raw_tasks:
        if not row.get("issue_numbers"):
            row["rejection_reason"] = "no_linked_issue"
            rejected.append(row)
            update_progress()
            continue
        if not row.get("patch", "").strip():
            row["rejection_reason"] = "no_source_patch"
            rejected.append(row)
            update_progress()
            continue
        if not row.get("test_patch", "").strip():
            row["rejection_reason"] = "no_test_patch"
            rejected.append(row)
            update_progress()
            continue

        raw_issue_numbers = row["issue_numbers"]
        if isinstance(raw_issue_numbers, str):
            raw_issue_numbers = [raw_issue_numbers]
        issue_numbers = [int(i) for i in raw_issue_numbers]
        chosen_issue: GitHubIssueMetadata | None = None
        for issue_number in issue_numbers:
            metadata = fetch_issue_metadata(row["repo"], issue_number, tokens)
            if not is_after_cutoff(metadata.created_at, args.start_date):
                continue
            # Accept any issue past the cutoff regardless of label/text heuristics.
            # Bug-vs-feature classification is recorded as metadata but not used
            # to reject: executable F2P validation is the real gate.
            chosen_issue = metadata
            break

        if chosen_issue is None:
            row["rejection_reason"] = "issue_before_cutoff"
            rejected.append(row)
            update_progress()
            continue

        signals = quality_signals(row.get("problem_statement", ""))
        bucket = quality_bucket(row.get("problem_statement", ""))
        normalized = dict(row)
        normalized["collection_track"] = "pouya_dataset_2026"
        normalized["created_at"] = chosen_issue.created_at
        normalized["issue_created_at"] = chosen_issue.created_at
        normalized["pr_created_at"] = row.get("created_at")
        normalized["issue_url"] = chosen_issue.html_url
        normalized["language"] = "Python"
        normalized["quality_signals"] = signals
        normalized["quality_bucket"] = bucket
        normalized["validation_attempts"] = 0
        normalized["validation_status"] = "raw_candidate"
        normalized["rejection_reason"] = None
        kept.append(normalized)
        update_progress()

    write_jsonl(RAW_CANDIDATES_JSONL, kept)
    write_jsonl(REJECTED_CANDIDATES_JSONL, rejected)
    SUMMARY_JSON.write_text(json.dumps(summarize_raw_candidates(kept, rejected, args.start_date), indent=2))
    write_stage_progress(
        progress_file,
        "build-raw-cands",
        "done",
        total=len(raw_tasks),
        completed=len(raw_tasks),
        remaining=0,
        kept=len(kept),
        rejected=len(rejected),
    )
    print(f"Wrote {len(kept)} raw candidates to {RAW_CANDIDATES_JSONL}")
    print(f"Wrote {len(rejected)} rejected candidates to {REJECTED_CANDIDATES_JSONL}")


def cmd_write_launch_config(args: argparse.Namespace) -> None:
    ensure_layout()
    config = {
        "mode": {
            "setup": True,
            "organize": True,
        },
        "llm_provider_name": args.llm_provider,
        "model_config": {
            "model_name": args.model_name,
            "temperature": args.temperature,
        },
        "workspace_root": str(LAUNCH_DIR / "workspace"),
        "dataset": str(RAW_CANDIDATES_JSONL),
        "print_to_console": False,
        "first_N_repos": -1,
        "overwrite": False,
        "max_workers": args.max_workers,
        "os": "linux",
        "max_trials": args.max_trials,
        "max_steps_setup": args.max_steps_setup,
        "max_steps_verify": args.max_steps_verify,
        "max_steps_organize": args.max_steps_organize,
        "cmd_timeout": args.cmd_timeout,
        "image_prefix": args.image_prefix,
    }
    LAUNCH_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_CONFIG_JSON.write_text(json.dumps(config, indent=2))
    print(f"Wrote RepoLaunch config to {LAUNCH_CONFIG_JSON}")


def cmd_run_launch(args: argparse.Namespace) -> None:
    ensure_layout()
    config_path = Path(args.config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Launch config not found: {config_path}")

    config = json.loads(config_path.read_text())
    dataset_path = Path(config["dataset"])
    if not dataset_path.exists():
        raise FileNotFoundError(f"Launch dataset not found: {dataset_path}")
    total = count_jsonl_rows(dataset_path)
    workspace_root = Path(config["workspace_root"])
    setup_progress = Path(args.setup_progress_file)
    organize_progress = Path(args.organize_progress_file)

    def sync_organize_progress(state: str, _retcode: int | None) -> None:
        organize_completed = max(0, min(total, count_launch_results(workspace_root, field="organize_completed")))
        write_stage_progress(
            organize_progress,
            "launch-organize",
            state,
            total=total,
            completed=organize_completed,
            remaining=max(total - organize_completed, 0),
        )

    run_cmd_monitored(
        [
            sys.executable,
            "-m",
            "launch.run",
            "--config-path",
            str(config_path.resolve()),
        ],
        cwd=LIVE_ROOT / "launch",
        progress_file=setup_progress,
        stage="launch-setup",
        total=total,
        completed_fn=lambda: count_launch_results(workspace_root, field="completed"),
        on_poll=sync_organize_progress,
    )

    setup_jsonl = workspace_root / "setup.jsonl"
    organize_jsonl = workspace_root / "organize.jsonl"
    print(f"RepoLaunch setup output: {setup_jsonl}")
    print(f"RepoLaunch organize output: {organize_jsonl}")
    print(
        "Next step: "
        f"python scripts/data/pouya_dataset_2026.py merge-launch-results --organize-jsonl {organize_jsonl}"
    )


def cmd_merge_launch_results(args: argparse.Namespace) -> None:
    ensure_layout()
    organize_jsonl = Path(args.organize_jsonl)
    if not organize_jsonl.exists():
        raise FileNotFoundError(f"organize JSONL not found: {organize_jsonl}")
    if not RAW_CANDIDATES_JSONL.exists():
        raise FileNotFoundError(f"Run build-raw-candidates first: {RAW_CANDIDATES_JSONL} missing")

    raw_candidates = {
        row["instance_id"]: row
        for row in (json.loads(line) for line in RAW_CANDIDATES_JSONL.read_text().splitlines() if line.strip())
    }
    organize_rows = [
        json.loads(line) for line in organize_jsonl.read_text().splitlines() if line.strip()
    ]
    organize_ids = {row["instance_id"] for row in organize_rows}
    missing_from_organize = set(raw_candidates) - organize_ids
    if missing_from_organize:
        print(f"Warning: {len(missing_from_organize)} raw candidates absent from organize output "
              f"(RepoLaunch may have failed for them): {sorted(missing_from_organize)[:5]}{'...' if len(missing_from_organize) > 5 else ''}")

    merged: list[dict[str, Any]] = []
    processed = 0
    progress_file = Path(args.progress_file)
    write_stage_progress(
        progress_file,
        "merge-launch",
        "running",
        total=len(organize_rows),
        completed=0,
        remaining=len(organize_rows),
        merged=0,
        missing_raw=len(missing_from_organize),
    )
    for row in organize_rows:
        processed += 1
        instance_id = row["instance_id"]
        if instance_id not in raw_candidates:
            print(f"Warning: organize entry {instance_id!r} not in raw_candidates — skipping")
            write_stage_progress(
                progress_file,
                "merge-launch",
                "running",
                total=len(organize_rows),
                completed=processed,
                remaining=max(len(organize_rows) - processed, 0),
                merged=len(merged),
                missing_raw=len(missing_from_organize),
            )
            continue
        candidate = dict(raw_candidates[instance_id])
        candidate["docker_image"] = row.get("docker_image", "")
        candidate["image_name"] = row.get("docker_image", "")
        candidate["rebuild_cmds"] = row.get("rebuild_cmds", [])
        candidate["test_cmds"] = row.get("test_cmds", [])
        candidate["print_cmds"] = row.get("print_cmds", [])
        candidate["log_parser"] = row.get("log_parser", "pytest")
        candidate["setup_cmds"] = row.get("setup_cmds", [])
        candidate["validation_attempts"] = 1
        candidate["validation_status"] = "launch_ready"
        merged.append(candidate)
        write_stage_progress(
            progress_file,
            "merge-launch",
            "running",
            total=len(organize_rows),
            completed=processed,
            remaining=max(len(organize_rows) - processed, 0),
            merged=len(merged),
            missing_raw=len(missing_from_organize),
        )

    write_jsonl(LAUNCH_READY_JSONL, merged)
    write_stage_progress(
        progress_file,
        "merge-launch",
        "done",
        total=len(organize_rows),
        completed=len(organize_rows),
        remaining=0,
        merged=len(merged),
        missing_raw=len(missing_from_organize),
    )
    print(f"Wrote {len(merged)} launch-ready instances to {LAUNCH_READY_JSONL}")


def cmd_run_validation(args: argparse.Namespace) -> None:
    ensure_layout()
    launch_ready = Path(args.dataset) if args.dataset else LAUNCH_READY_JSONL
    if not launch_ready.exists():
        raise FileNotFoundError(f"Run merge-launch-results first: {launch_ready} missing")
    validation_output = VALIDATION_DIR / "validation_logs"
    gold_output = VALIDATION_DIR / "gold_eval_logs"
    validation_output.mkdir(parents=True, exist_ok=True)
    launch_ready_count = count_jsonl_rows(launch_ready)

    run_cmd_monitored(
        [
            sys.executable,
            "-m",
            "evaluation.validation",
            "--input_dir",
            str(launch_ready),
            "--platform",
            "linux",
            "--workers",
            str(args.workers),
            "--output_dir",
            str(validation_output),
            "--overwrite",
            "1" if args.overwrite else "0",
        ],
        cwd=LIVE_ROOT,
        progress_file=Path(args.validate_progress_file),
        stage="validate",
        total=launch_ready_count,
        completed_fn=lambda: count_status_files(validation_output),
    )

    validated_instances = validation_output / "validated_instances.jsonl"
    gold_base_cmd = [
        sys.executable,
        "-m",
        "evaluation.evaluation",
        "--dataset",
        str(validated_instances),
        "--patch_dir",
        "gold",
        "--platform",
        "linux",
        "--workers",
        str(args.workers),
        "--overwrite",
        "1",
        "--output_dir",
        str(gold_output),
    ]
    validated_count = count_jsonl_rows(validated_instances)
    gold_output.mkdir(parents=True, exist_ok=True)
    run_cmd_monitored(
        gold_base_cmd,
        cwd=LIVE_ROOT,
        progress_file=Path(args.gold_progress_file),
        stage="gold-eval",
        total=validated_count,
        completed_fn=lambda: count_status_files(gold_output),
    )


def derive_rejection_reason(
    row: dict[str, Any],
    launch_ready_ids: set[str],
    validated_ids: set[str],
    gold_success_ids: set[str],
    launch_workspace: Path | None,
) -> str:
    instance_id = row["instance_id"]
    if instance_id not in launch_ready_ids:
        return "environment_setup_missing"
    if instance_id not in validated_ids:
        if launch_workspace is not None:
            result_path = launch_workspace / "playground" / instance_id / "result.json"
            if result_path.exists():
                result = json.loads(result_path.read_text())
                if not result.get("completed", False):
                    return "build_or_test_environment_failure"
                if not result.get("organize_completed", False):
                    return "environment_setup_incomplete"
        return "validation_failed_or_no_f2p"
    if instance_id not in gold_success_ids:
        return "gold_patch_validation_failed_or_unstable"
    return "validated"


def cmd_promote_validated(args: argparse.Namespace) -> None:
    ensure_layout()
    if not RAW_CANDIDATES_JSONL.exists():
        raise FileNotFoundError(f"Run build-raw-candidates first: {RAW_CANDIDATES_JSONL} missing")
    _validated_instances = VALIDATION_DIR / "validation_logs" / "validated_instances.jsonl"
    if not _validated_instances.exists():
        raise FileNotFoundError(f"Run run-validation first: {_validated_instances} missing")
    _gold_confirmed = VALIDATION_DIR / "gold_eval_logs" / "gold_patch_evaluated_instances.jsonl"
    if not _gold_confirmed.exists():
        raise FileNotFoundError(f"Run run-validation first: {_gold_confirmed} missing")

    validation_output = VALIDATION_DIR / "validation_logs"
    gold_output = VALIDATION_DIR / "gold_eval_logs"
    launch_workspace = Path(args.launch_workspace) if args.launch_workspace else None

    raw_candidates = [
        json.loads(line) for line in RAW_CANDIDATES_JSONL.read_text().splitlines() if line.strip()
    ]
    launch_ready_rows = [
        json.loads(line) for line in LAUNCH_READY_JSONL.read_text().splitlines() if line.strip()
    ] if LAUNCH_READY_JSONL.exists() else []
    validated_rows = [
        json.loads(line)
        for line in (validation_output / "validated_instances.jsonl").read_text().splitlines()
        if line.strip()
    ] if (validation_output / "validated_instances.jsonl").exists() else []
    gold_rows = [
        json.loads(line)
        for line in (gold_output / "gold_patch_evaluated_instances.jsonl").read_text().splitlines()
        if line.strip()
    ] if (gold_output / "gold_patch_evaluated_instances.jsonl").exists() else []

    launch_ready_by_id = {row["instance_id"]: row for row in launch_ready_rows}
    validated_by_id = {row["instance_id"]: row for row in validated_rows}
    gold_success_ids = {row["instance_id"] for row in gold_rows}

    validated_full: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    progress_file = Path(args.progress_file)
    write_stage_progress(
        progress_file,
        "promote",
        "running",
        total=len(raw_candidates),
        completed=0,
        remaining=len(raw_candidates),
        validated=0,
        rejected=0,
    )
    for row in raw_candidates:
        instance_id = row["instance_id"]
        merged = dict(row)
        if instance_id in launch_ready_by_id:
            merged.update(
                {
                    "docker_image": launch_ready_by_id[instance_id].get("docker_image", ""),
                    "image_name": launch_ready_by_id[instance_id].get("image_name", ""),
                    "rebuild_cmds": launch_ready_by_id[instance_id].get("rebuild_cmds", []),
                    "test_cmds": launch_ready_by_id[instance_id].get("test_cmds", []),
                    "print_cmds": launch_ready_by_id[instance_id].get("print_cmds", []),
                    "log_parser": launch_ready_by_id[instance_id].get("log_parser", "pytest"),
                }
            )
        if instance_id in validated_by_id:
            merged["FAIL_TO_PASS"] = validated_by_id[instance_id]["FAIL_TO_PASS"]
            merged["PASS_TO_PASS"] = validated_by_id[instance_id]["PASS_TO_PASS"]

        merged["validation_attempts"] = sum(
            int(instance_id in ids)
            for ids in (
                set(launch_ready_by_id.keys()),
                set(validated_by_id.keys()),
                gold_success_ids,
            )
        )
        rejection_reason = derive_rejection_reason(
            row,
            set(launch_ready_by_id.keys()),
            set(validated_by_id.keys()),
            gold_success_ids,
            launch_workspace,
        )
        merged["rejection_reason"] = None if rejection_reason == "validated" else rejection_reason
        merged["validation_status"] = "validated" if rejection_reason == "validated" else "rejected"
        if merged["validation_status"] == "validated":
            validated_full.append(merged)
        else:
            rejected.append(merged)
        write_stage_progress(
            progress_file,
            "promote",
            "running",
            total=len(raw_candidates),
            completed=len(validated_full) + len(rejected),
            remaining=max(len(raw_candidates) - len(validated_full) - len(rejected), 0),
            validated=len(validated_full),
            rejected=len(rejected),
        )

    write_jsonl(VALIDATED_FULL_JSONL, validated_full)
    write_jsonl(REJECTED_CANDIDATES_JSONL, rejected)
    write_stage_progress(
        progress_file,
        "promote",
        "done",
        total=len(raw_candidates),
        completed=len(raw_candidates),
        remaining=0,
        validated=len(validated_full),
        rejected=len(rejected),
    )
    print(f"Wrote {len(validated_full)} validated instances to {VALIDATED_FULL_JSONL}")
    print(f"Wrote {len(rejected)} rejected instances to {REJECTED_CANDIDATES_JSONL}")


def cmd_freeze(args: argparse.Namespace) -> None:
    ensure_layout()
    if not VALIDATED_FULL_JSONL.exists():
        raise FileNotFoundError(f"Run promote-validated first: {VALIDATED_FULL_JSONL} missing")
    rows = [
        json.loads(line) for line in VALIDATED_FULL_JSONL.read_text().splitlines() if line.strip()
    ]
    if len(rows) < args.count:
        print(f"Warning: only {len(rows)} validated instances available, requested {args.count}")
    progress_file = Path(args.progress_file)
    write_stage_progress(
        progress_file,
        "freeze",
        "running",
        total=len(rows),
        count=args.count,
    )

    rng = random.Random(args.seed)
    rng.shuffle(rows)
    frozen = rows[: args.count]
    output_path = FROZEN_50_JSONL if args.count == 50 else DATASET_DIR / f"frozen_{args.count}.jsonl"
    write_jsonl(output_path, frozen)
    write_stage_progress(
        progress_file,
        "freeze",
        "done",
        total=len(rows),
        count=len(frozen),
    )
    print(f"Froze {len(frozen)} instances (seed={args.seed}, total validated={len(rows)})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status").set_defaults(func=cmd_status)
    subparsers.add_parser("init").set_defaults(func=cmd_init)

    crawl = subparsers.add_parser("crawl-repos")
    crawl.add_argument("--token-file", default=str(DEFAULT_TOKEN_FILE))
    crawl.add_argument("--min-stars", type=int, default=DEFAULT_MIN_STARS)
    crawl.add_argument("--progress-file", default=str(CRAWL_REPOS_PROGRESS_JSON))
    crawl.set_defaults(func=cmd_crawl_repos)

    filter_cmd = subparsers.add_parser("filter-repos")
    filter_cmd.add_argument("--token-file", default=str(DEFAULT_TOKEN_FILE))
    filter_cmd.add_argument("--min-total-pr-issues", type=int, default=DEFAULT_MIN_TOTAL_PR_ISSUES)
    filter_cmd.add_argument("--min-forks", type=int, default=DEFAULT_MIN_FORKS)
    filter_cmd.add_argument("--min-lang-percent", type=float, default=DEFAULT_MIN_LANG_PERCENT)
    filter_cmd.add_argument("--max-workers", type=int, default=10)
    filter_cmd.add_argument("--progress-file", default=str(FILTER_REPOS_PROGRESS_JSON))
    filter_cmd.set_defaults(func=cmd_filter_repos)

    collect = subparsers.add_parser("collect-tasks")
    collect.add_argument("--token-file", default=str(DEFAULT_TOKEN_FILE))
    collect.add_argument("--start-date", default=DEFAULT_START_DATE)
    collect.add_argument("--limit-repos", type=int, default=-1)
    collect.add_argument("--max-workers", type=int, default=8)
    collect.add_argument("--progress-file", default=str(COLLECT_TASKS_PROGRESS_JSON))
    collect.set_defaults(func=cmd_collect_tasks)

    build_raw = subparsers.add_parser("build-raw-candidates")
    build_raw.add_argument("--token-file", default=str(DEFAULT_TOKEN_FILE))
    build_raw.add_argument("--start-date", default=DEFAULT_START_DATE)
    build_raw.add_argument("--progress-file", default=str(BUILD_RAW_CANDIDATES_PROGRESS_JSON))
    build_raw.set_defaults(func=cmd_build_raw_candidates)

    launch_config = subparsers.add_parser("write-launch-config")
    launch_config.add_argument("--llm-provider", default="OpenAI")
    launch_config.add_argument("--model-name", default="gpt-4.1-20250414")
    launch_config.add_argument("--temperature", type=float, default=0.0)
    launch_config.add_argument("--max-workers", type=int, default=8)
    launch_config.add_argument("--max-trials", type=int, default=2)
    launch_config.add_argument("--max-steps-setup", type=int, default=60)
    launch_config.add_argument("--max-steps-verify", type=int, default=20)
    launch_config.add_argument("--max-steps-organize", type=int, default=40)
    launch_config.add_argument("--cmd-timeout", type=int, default=60)
    launch_config.add_argument("--image-prefix", default="repolaunch/pouya-dataset-2026")
    launch_config.set_defaults(func=cmd_write_launch_config)

    run_launch = subparsers.add_parser("run-launch")
    run_launch.add_argument("--config-path", default=str(LAUNCH_CONFIG_JSON))
    run_launch.add_argument("--setup-progress-file", default=str(LAUNCH_SETUP_PROGRESS_JSON))
    run_launch.add_argument("--organize-progress-file", default=str(LAUNCH_ORGANIZE_PROGRESS_JSON))
    run_launch.set_defaults(func=cmd_run_launch)

    merge_launch = subparsers.add_parser("merge-launch-results")
    merge_launch.add_argument("--organize-jsonl", required=True)
    merge_launch.add_argument("--progress-file", default=str(MERGE_LAUNCH_PROGRESS_JSON))
    merge_launch.set_defaults(func=cmd_merge_launch_results)

    validate = subparsers.add_parser("run-validation")
    validate.add_argument("--dataset", default=None)
    validate.add_argument("--workers", type=int, default=4)
    validate.add_argument("--overwrite", action="store_true")
    validate.add_argument("--validate-progress-file", default=str(VALIDATE_PROGRESS_JSON))
    validate.add_argument("--gold-progress-file", default=str(GOLD_EVAL_PROGRESS_JSON))
    validate.set_defaults(func=cmd_run_validation)

    promote = subparsers.add_parser("promote-validated")
    promote.add_argument("--launch-workspace", default=None)
    promote.add_argument("--progress-file", default=str(PROMOTE_VALIDATED_PROGRESS_JSON))
    promote.set_defaults(func=cmd_promote_validated)

    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--count", type=int, default=50)
    freeze.add_argument("--seed", type=int, default=42,
                        help="Random seed for shuffle (ensures reproducibility, default: 42)")
    freeze.add_argument("--progress-file", default=str(FREEZE_PROGRESS_JSON))
    freeze.set_defaults(func=cmd_freeze)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
