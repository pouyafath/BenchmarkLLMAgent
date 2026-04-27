#!/usr/bin/env python3
"""Run all enhancer agents on the second-paper-10 dataset (Group B).

Runs the baseline solver ONCE, then each enhancer sequentially while reusing
the shared baseline results.  Skips agents that already have a valid
comparison_summary.json.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Same 10 agents that succeeded for Group A (verified10).
# Excludes: mini_swe_agent, live_swe_agent, trae (failed in Group A).
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
]

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
DEFAULT_REPLICATION_DIR = Path("/home/22pf2/SWE-Bench_Replication")


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workflow-script", type=Path,
        default=ROOT / "scripts" / "workflows" / "run_secondpaper10_enhancement_vs_baseline.py",
    )
    parser.add_argument(
        "--python", type=Path,
        default=ROOT / "bench_env" / "bin" / "python",
    )
    parser.add_argument(
        "--results-root", type=Path,
        default=ROOT / "results" / "secondpaper10_baseline_vs_enhanced",
    )
    parser.add_argument("--output-tag", type=str, default="groupB_full10_20260324")
    parser.add_argument("--max-issues", type=int, default=10)
    parser.add_argument("--enhancer-parallel", type=int, default=4)
    parser.add_argument("--solver-workers", type=int, default=4)
    parser.add_argument("--eval-workers", type=int, default=4)
    parser.add_argument("--api-base", type=str, default="http://127.0.0.1:18000/v1")
    parser.add_argument("--api-key", type=str, default="local-devstral")
    parser.add_argument("--api-model", type=str, default="Devstral-Small-2-24B-Instruct-2512")
    parser.add_argument("--agents", type=str, default="",
                        help="Comma-separated agent list (default: all 10)")
    parser.add_argument("--force-rerun", action="store_true",
                        help="Ignore existing comparison_summary.json and re-run all agents")
    args = parser.parse_args()

    agents = [a.strip() for a in args.agents.split(",") if a.strip()] if args.agents else AGENTS
    results_root = args.results_root
    results_root.mkdir(parents=True, exist_ok=True)

    status_path = results_root / f"batch_status_{args.output_tag}.json"
    status = load_status(status_path, args.output_tag)

    # ── Shared baseline: run once, copy for each agent ──
    # The baseline solver is deterministic (temperature=0) so running it once
    # and sharing the results across all enhancer agents saves ~30min per agent.
    shared_baseline_dir: Path | None = None

    # Check if any agent already has a baseline_solver_run with preds.json
    for agent in agents:
        candidate = results_root / f"{agent}__{args.output_tag}" / "baseline_solver_run" / "preds.json"
        if candidate.exists():
            shared_baseline_dir = candidate.parent
            print(f"[BASELINE] Reusing existing baseline from: {shared_baseline_dir}")
            break

    for agent in agents:
        print(f"\n{'='*60}")
        print(f"Agent: {agent}")
        print(f"{'='*60}")

        existing = status["runs"].get(agent, {})
        exp_dir = results_root / f"{agent}__{args.output_tag}"
        comp_json = exp_dir / "comparison_summary.json"

        if not args.force_rerun and existing.get("state") == "completed" and comp_json.exists():
            print(f"  Already completed, skipping.")
            # Track as baseline source if needed
            baseline_candidate = exp_dir / "baseline_solver_run"
            if shared_baseline_dir is None and (baseline_candidate / "preds.json").exists():
                shared_baseline_dir = baseline_candidate
            continue

        # Delete stale comparison_summary.json if re-running
        if comp_json.exists():
            comp_json.unlink()

        # Prepare baseline: either copy from shared or let this agent run it
        this_baseline = exp_dir / "baseline_solver_run"
        skip_baseline = False

        if shared_baseline_dir and shared_baseline_dir != this_baseline:
            # Copy shared baseline into this agent's experiment dir
            if this_baseline.exists():
                shutil.rmtree(this_baseline)
            exp_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(shared_baseline_dir, this_baseline)
            skip_baseline = True
            print(f"  [BASELINE] Copied shared baseline to {this_baseline}")
        elif (this_baseline / "preds.json").exists():
            # This agent already ran the baseline solver
            skip_baseline = True
            print(f"  [BASELINE] Reusing existing baseline in {this_baseline}")

        cmd = [
            str(args.python),
            str(args.workflow_script),
            "--enhancer-agent", agent,
            "--max-issues", str(args.max_issues),
            "--output-tag", args.output_tag,
            "--results-root", str(results_root),
            "--enhancer-parallel", str(args.enhancer_parallel),
            "--solver-workers", str(args.solver_workers),
            "--eval-workers", str(args.eval_workers),
            "--enhancer-api-base", args.api_base,
            "--enhancer-api-key", args.api_key,
            "--enhancer-model", args.api_model,
            "--allow-identical-enhancements",
        ]
        if skip_baseline:
            cmd.append("--skip-baseline")

        status["runs"][agent] = {
            "state": "running",
            "experiment_dir": str(exp_dir),
            "command": cmd,
            "updated_at_utc": utc_now(),
        }
        save_status(status_path, status)

        try:
            proc = subprocess.run(cmd, check=False)
            returncode = proc.returncode
        except Exception as e:
            print(f"  Exception: {e}")
            returncode = -1

        comp_exists = comp_json.exists()
        state = "completed" if returncode == 0 and comp_exists else "failed"

        status["runs"][agent] = {
            "state": state,
            "experiment_dir": str(exp_dir),
            "returncode": returncode,
            "baseline_shared": skip_baseline,
            "comparison_summary_exists": comp_exists,
            "comparison_summary": str(comp_json) if comp_exists else "",
            "updated_at_utc": utc_now(),
        }
        save_status(status_path, status)

        if state == "completed":
            print(f"  Completed successfully.")
            # Track as baseline source for subsequent agents
            if shared_baseline_dir is None and (this_baseline / "preds.json").exists():
                shared_baseline_dir = this_baseline
            # Read and print summary
            try:
                comp = json.loads(comp_json.read_text())
                baseline = comp.get("baseline", {})
                enhanced = comp.get("enhanced", {})
                delta = comp.get("delta", {})
                print(f"  Baseline: {baseline.get('resolved_issue_count', '?')}/{baseline.get('num_issues', '?')} resolved")
                print(f"  Enhanced: {enhanced.get('resolved_issue_count', '?')}/{enhanced.get('num_issues', '?')} resolved")
                if delta:
                    print(f"  Delta resolved: {delta.get('resolved_issue_rate_delta', 0)*100:+.1f}%")
            except Exception:
                pass
        else:
            print(f"  Failed with exit code {returncode}")

    status["finished_at_utc"] = utc_now()
    save_status(status_path, status)

    # Print final summary
    print(f"\n\n{'='*60}")
    print(f"BATCH SUMMARY")
    print(f"{'='*60}")
    for agent in agents:
        run = status["runs"].get(agent, {})
        state = run.get("state", "unknown")
        print(f"  {agent:25s} {state}")

    completed = sum(1 for a in agents if status["runs"].get(a, {}).get("state") == "completed")
    print(f"\nCompleted: {completed}/{len(agents)}")
    print(f"Status file: {status_path}")


if __name__ == "__main__":
    main()
