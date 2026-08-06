#!/usr/bin/env python3
"""Run native CLI enhancers on a small Pouya-20 subset and summarize health.

This is intentionally enhancer-only. It verifies that the native agent CLIs
return real enhanced issue text before launching expensive solver/eval runs.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DEFAULT_DATASET = ROOT / "runs/pouya_final20b_20260505_050130/validated_instances.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "runs/native_cli_pouya5_20260509"
AGENTS = ["aider", "trae", "openhands", "mini_swe_agent", "swe_agent"]


def _set_default_env() -> dict[str, str]:
    """Set default env vars for native enhancers (OpenAI gpt-5.4-mini)."""
    defaults = {
        "AIDER_MODEL": "openai/gpt-5.4-mini",
        "AIDER_API_BASE": "https://api.openai.com/v1",
        "AIDER_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "AIDER_TIMEOUT": "500",
        "TRAE_BASE_URL": "https://api.openai.com/v1",
        "TRAE_MODEL": "gpt-5.4-mini",
        "TRAE_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "TRAE_TIMEOUT": "500",
        "OPENHANDS_BASE_URL": "https://api.openai.com/v1",
        "OPENHANDS_MODEL": "gpt-5.4-mini",
        "OPENHANDS_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "OPENHANDS_TIMEOUT": "500",
        "MINI_BASE_URL": "https://api.openai.com/v1",
        "MINI_MODEL": "gpt-5.4-mini",
        "MINI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "MINI_TIMEOUT": "500",
        "SWEAGENT_BASE_URL": "https://api.openai.com/v1",
        "SWEAGENT_MODEL": "gpt-5.4-mini",
        "SWEAGENT_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "SWEAGENT_TIMEOUT": "500",
    }
    applied = {}
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
        applied[key] = os.environ[key]
    return applied


def _load_rows(path: Path, limit: int) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return rows[:limit]


def _issue_number(instance_id: str) -> str:
    match = re.search(r"-(\d+)$", instance_id)
    return match.group(1) if match else ""


def _title_from_problem(problem: str, fallback: str) -> str:
    for line in (problem or "").splitlines():
        cleaned = line.strip().strip("#").strip()
        if cleaned:
            return cleaned
    return fallback


def _changed_files(row: dict[str, Any]) -> str:
    files = []
    for line in (row.get("patch") or "").splitlines():
        match = re.match(r"diff --git a/(.*?) b/(.*)$", line)
        if match:
            files.append(match.group(2))
    return ", ".join(files[:10])


def _normalize_issue(row: dict[str, Any]) -> dict[str, Any]:
    instance_id = row["instance_id"]
    repo = row.get("repo", "")
    owner_repo = repo.split("/", 1)
    repo_name = owner_repo[1] if len(owner_repo) == 2 else repo
    problem = row.get("problem_statement") or row.get("body") or ""
    issue = dict(row)
    issue["title"] = row.get("title") or _title_from_problem(problem, instance_id)
    issue["body"] = problem
    issue["repo_name"] = row.get("repo_name") or repo_name
    issue["issue_number"] = row.get("issue_number") or _issue_number(instance_id)
    return issue


def _module_for_agent(agent: str) -> str:
    if agent == "mini_swe_agent":
        return "src.enhancers.ready_to_use.mini_swe_agent_enhancer"
    if agent == "swe_agent":
        return "src.enhancers.ready_to_use.sweagent_enhancer"
    return f"src.enhancers.ready_to_use.{agent}_enhancer"


def _quality_flags(row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    original_title = row["title"]
    original_body = row["body"]
    enhanced_title = result.get("enhanced_title") or ""
    enhanced_body = result.get("enhanced_body") or ""
    meta = result.get("enhancement_metadata") or {}
    lower_body = enhanced_body.lower()
    timeout_contaminated = (
        "was cancelled because it took more than" in lower_body
        or "please try a different command" in lower_body
        or "source of this error is if the command is interactive" in lower_body
    )
    returncode = next(
        (
            meta.get(key)
            for key in ("returncode", "aider_returncode", "trae_returncode", "sweagent_returncode")
            if meta.get(key) is not None
        ),
        None,
    )
    return {
        "enhancer_type": meta.get("enhancer_type"),
        "parse_source": meta.get("parse_source"),
        "source": meta.get("source"),
        "returncode": returncode,
        "trajectory_used": meta.get("trajectory_used"),
        "error": meta.get("error"),
        "title_changed": enhanced_title.strip() != original_title.strip(),
        "body_changed": enhanced_body.strip() != original_body.strip(),
        "enhanced_body_len": len(enhanced_body),
        "has_summary": "summary" in lower_body,
        "has_repro_or_steps": "reproduce" in lower_body or "steps" in lower_body,
        "has_expected_actual": "expected" in lower_body and "actual" in lower_body,
        "timeout_contaminated": timeout_contaminated,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--agents", default=",".join(AGENTS))
    parser.add_argument(
        "--instance-ids",
        default="",
        help="Optional comma-separated instance IDs to run from the selected subset.",
    )
    args = parser.parse_args()

    env = _set_default_env()
    rows = [_normalize_issue(r) for r in _load_rows(args.dataset, args.limit)]
    if args.instance_ids.strip():
        wanted = {item.strip() for item in args.instance_ids.split(",") if item.strip()}
        rows = [row for row in rows if row["instance_id"] in wanted]
        missing = sorted(wanted - {row["instance_id"] for row in rows})
        if missing:
            raise SystemExit(f"Instance IDs not found in selected subset: {missing}")
    agents = [a.strip() for a in args.agents.split(",") if a.strip()]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.output_dir / "raw_results"
    raw_dir.mkdir(exist_ok=True)

    summary: dict[str, Any] = {
        "run_date": datetime.now(timezone.utc).isoformat(),
        "dataset": str(args.dataset),
        "output_dir": str(args.output_dir),
        "limit": args.limit,
        "instance_ids": [r["instance_id"] for r in rows],
        "env": env,
        "agents": {},
    }

    for agent in agents:
        print(f"\n=== {agent} ===", flush=True)
        module = importlib.import_module(_module_for_agent(agent))
        enhance_issue = getattr(module, "enhance_issue")
        agent_results = []

        for idx, row in enumerate(rows, start=1):
            instance_id = row["instance_id"]
            changed_files = _changed_files(row)
            start = time.monotonic()
            print(f"[{agent} {idx}/{len(rows)}] {instance_id}", flush=True)
            try:
                result = enhance_issue(row, changed_files)
            except Exception as exc:
                result = {
                    "enhanced_title": row["title"],
                    "enhanced_body": row["body"],
                    "enhancement_metadata": {
                        "enhancer_type": "error",
                        "agent_id": agent,
                        "error": f"exception: {exc}",
                    },
                }
            elapsed = round(time.monotonic() - start, 2)
            flags = _quality_flags(row, result)
            raw = {
                "agent": agent,
                "instance_id": instance_id,
                "elapsed_seconds": elapsed,
                "original_title": row["title"],
                "original_body_len": len(row["body"]),
                "changed_files": changed_files,
                "result": result,
                "checks": flags,
            }
            raw_path = raw_dir / f"{agent}__{instance_id}.json"
            raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
            agent_results.append({"instance_id": instance_id, "elapsed_seconds": elapsed, **flags})
            print(
                "  -> "
                f"type={flags['enhancer_type']} rc={flags['returncode']} "
                f"parse={flags['parse_source']} len={flags['enhanced_body_len']} "
                f"changed={flags['title_changed']}/{flags['body_changed']} "
                f"error={flags['error']}",
                flush=True,
            )

        failures = [r for r in agent_results if r.get("enhancer_type") != "real"]
        weak = [
            r for r in agent_results
            if r.get("enhancer_type") == "real"
            and (
                not r.get("body_changed")
                or r.get("enhanced_body_len", 0) < 300
                or not r.get("has_repro_or_steps")
                or not r.get("has_expected_actual")
                or r.get("timeout_contaminated")
            )
        ]
        summary["agents"][agent] = {
            "total": len(agent_results),
            "real_count": len(agent_results) - len(failures),
            "failure_count": len(failures),
            "weak_count": len(weak),
            "results": agent_results,
        }
        (args.output_dir / "SUMMARY.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
