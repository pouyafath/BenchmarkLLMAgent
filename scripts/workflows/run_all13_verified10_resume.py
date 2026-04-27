#!/usr/bin/env python3
"""Resume all 13 verified10 enhancement-vs-baseline runs.

This runner skips agents that already have `comparison_summary.json`, and only
executes unfinished agents using the same output tag.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

AGENTS = [
    "openhands",
    "swe_agent",
    "github_copilot",
    "sweep",
    "aider",
    "cline",
    "magis",
    "copilot_workspace",
    "chatbr",
    "coderabbit",
    "mini_swe_agent",
    "live_swe_agent",
    "trae",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def load_status(path: Path, tag: str) -> dict:
    if path.exists():
        try:
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                data.setdefault("tag", tag)
                data.setdefault("started_at_utc", utc_now())
                data.setdefault("runs", {})
                return data
        except json.JSONDecodeError:
            pass
    return {"tag": tag, "started_at_utc": utc_now(), "runs": {}}


def save_status(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


def parse_args() -> argparse.Namespace:
    root = Path("/home/22pf2/BenchmarkLLMAgent")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workflow-script",
        type=Path,
        default=root / "scripts" / "workflows" / "run_verified10_enhancement_vs_baseline.py",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=Path("/home/22pf2/SWE-Bench_Replication/.venv312/bin/python"),
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=root / "results" / "verified10_baseline_vs_enhanced",
    )
    parser.add_argument("--output-tag", type=str, default="all13_full10_defaultdevstral_20260319")
    parser.add_argument("--max-issues", type=int, default=10)
    parser.add_argument("--enhancer-parallel", type=int, default=4)
    parser.add_argument("--solver-workers", type=int, default=4)
    parser.add_argument("--eval-workers", type=int, default=4)
    parser.add_argument("--cuda-visible-devices", type=str, default="2,3,6,7")
    parser.add_argument("--api-base", type=str, default="http://127.0.0.1:18000/v1")
    parser.add_argument("--api-key", type=str, default="local-devstral")
    parser.add_argument("--model", type=str, default="Devstral-Small-2-24B-Instruct-2512")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.workflow_script.resolve().parents[2]
    status_path = args.results_root / f"batch_status_{args.output_tag}.json"

    status = load_status(status_path, args.output_tag)
    for agent in AGENTS:
        run = status["runs"].setdefault(agent, {})
        exp_dir = args.results_root / f"{agent}__{args.output_tag}"
        comparison = exp_dir / "comparison_summary.json"
        if comparison.exists():
            run.update(
                {
                    "state": "completed",
                    "returncode": 0,
                    "comparison_summary_exists": True,
                    "comparison_summary": str(comparison),
                    "experiment_dir": str(exp_dir),
                    "updated_at_utc": utc_now(),
                }
            )
        else:
            run.setdefault("state", "pending")
            run.setdefault("experiment_dir", str(exp_dir))
            run["updated_at_utc"] = utc_now()
    save_status(status_path, status)

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = args.cuda_visible_devices
    env["OPENAI_COMPAT_API_BASE"] = args.api_base
    env["OPENAI_COMPAT_API_KEY"] = args.api_key
    env["OPENAI_COMPAT_MODEL"] = args.model

    for agent in AGENTS:
        exp_dir = args.results_root / f"{agent}__{args.output_tag}"
        comparison = exp_dir / "comparison_summary.json"
        if comparison.exists():
            status["runs"][agent].update(
                {
                    "state": "completed",
                    "returncode": 0,
                    "comparison_summary_exists": True,
                    "comparison_summary": str(comparison),
                    "experiment_dir": str(exp_dir),
                    "updated_at_utc": utc_now(),
                    "resume_skip_reason": "already_completed",
                }
            )
            save_status(status_path, status)
            continue

        cmd = [
            str(args.python),
            str(args.workflow_script),
            "--enhancer-agent",
            agent,
            "--max-issues",
            str(args.max_issues),
            "--output-tag",
            args.output_tag,
            "--enhancer-parallel",
            str(args.enhancer_parallel),
            "--solver-workers",
            str(args.solver_workers),
            "--eval-workers",
            str(args.eval_workers),
        ]
        status["runs"][agent].update(
            {
                "state": "running",
                "command": cmd,
                "experiment_dir": str(exp_dir),
                "updated_at_utc": utc_now(),
            }
        )
        save_status(status_path, status)

        proc = subprocess.run(cmd, cwd=str(repo_root), env=env)
        comparison_exists = comparison.exists()
        status["runs"][agent].update(
            {
                "state": "completed" if proc.returncode == 0 and comparison_exists else "failed",
                "returncode": proc.returncode,
                "comparison_summary_exists": comparison_exists,
                "comparison_summary": str(comparison) if comparison_exists else "",
                "updated_at_utc": utc_now(),
            }
        )
        save_status(status_path, status)

    status["finished_at_utc"] = utc_now()
    save_status(status_path, status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
