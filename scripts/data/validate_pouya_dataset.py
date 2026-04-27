"""
Validate the Pouya-SWE-bench-Live-style dataset via SWE-bench harness.

Steps:
  1. Generate gold predictions (model_patch = gold patch for each instance)
  2. Run swebench harness evaluation on a pilot batch
  3. Parse evaluation logs to extract REAL F2P/P2P test names
  4. Update dataset with validated F2P/P2P

Usage:
    # Step 1: Generate gold predictions
    bench_env/bin/python scripts/data/validate_pouya_dataset.py --step gold

    # Step 2: Run harness validation (pilot: 5 instances from diverse repos)
    bench_env/bin/python scripts/data/validate_pouya_dataset.py --step run-pilot

    # Step 3: Parse logs and update dataset
    bench_env/bin/python scripts/data/validate_pouya_dataset.py --step parse-logs

    # Or run all on full dataset:
    bench_env/bin/python scripts/data/validate_pouya_dataset.py --step gold
    bench_env/bin/python scripts/data/validate_pouya_dataset.py --step run-all
    bench_env/bin/python scripts/data/validate_pouya_dataset.py --step parse-logs
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "samples" / "pouya_swebench_live_style_50"
JSONL = DATA_DIR / "pouya_50_dataset.jsonl"
GOLD_PREDS = DATA_DIR / "gold_predictions.json"
RUN_ID = "pouya_gold_validation"
BENCH_PYTHON = str(ROOT / "bench_env" / "bin" / "python")


def load_instances():
    rows = []
    with open(JSONL) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def step_gold():
    """Generate gold predictions: model_patch = gold patch for each instance."""
    rows = load_instances()
    preds = {}
    for row in rows:
        iid = row["instance_id"]
        preds[iid] = {
            "instance_id": iid,
            "model_name_or_path": "gold",
            "model_patch": row["patch"],
        }
    with open(GOLD_PREDS, "w") as f:
        json.dump(preds, f, indent=2)
    print(f"Generated gold predictions for {len(preds)} instances: {GOLD_PREDS}")


def step_run(pilot=False, max_workers=4, timeout=1800):
    """Run swebench harness evaluation."""
    if not GOLD_PREDS.exists():
        print("ERROR: Run --step gold first")
        sys.exit(1)

    rows = load_instances()

    if pilot:
        # Pick 1 instance per repo (diverse repos), up to 5
        seen_repos = set()
        pilot_ids = []
        for row in rows:
            repo = row["repo"]
            if repo not in seen_repos:
                seen_repos.add(repo)
                pilot_ids.append(row["instance_id"])
                if len(pilot_ids) >= 5:
                    break
        instance_ids = pilot_ids
        print(f"Pilot: {len(instance_ids)} instances from {len(seen_repos)} repos")
    else:
        instance_ids = [row["instance_id"] for row in rows]
        print(f"Full run: {len(instance_ids)} instances")

    print("Instance IDs:", instance_ids)

    # No --namespace: build images locally instead of pulling from Docker Hub
    cmd = [
        BENCH_PYTHON, "-m", "swebench.harness.run_evaluation",
        "--dataset_name", str(JSONL),
        "--predictions_path", str(GOLD_PREDS),
        "--instance_ids", *instance_ids,
        "--max_workers", str(max_workers),
        "--timeout", str(timeout),
        "--run_id", RUN_ID,
        "--namespace", "none",
    ]
    print(f"\nRunning: {' '.join(cmd[:6])}...")
    subprocess.run(cmd)


def step_parse_logs():
    """Parse evaluation logs to extract real F2P/P2P from harness results."""
    # Find the grading results
    # swebench writes to: logs/run_evaluation/<run_id>/<instance_id>/<run_id>.<instance_id>.eval.log
    # and grading output to: logs/run_evaluation/...
    log_base = ROOT / "logs" / "run_evaluation" / RUN_ID

    if not log_base.exists():
        print(f"ERROR: Log directory not found: {log_base}")
        print("Run --step run-pilot or --step run-all first")
        sys.exit(1)

    # Also check for grading JSON
    grading_file = log_base / f"{RUN_ID}.json"
    if grading_file.exists():
        with open(grading_file) as f:
            grading = json.load(f)
        print(f"Found grading results: {grading_file}")
        print(json.dumps(grading, indent=2)[:2000])
    else:
        print(f"No grading file at {grading_file}")
        # List what's in the log dir
        for p in sorted(log_base.rglob("*")):
            print(f"  {p.relative_to(log_base)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", required=True,
                        choices=["gold", "run-pilot", "run-all", "parse-logs"])
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    if args.step == "gold":
        step_gold()
    elif args.step == "run-pilot":
        step_run(pilot=True, max_workers=args.max_workers, timeout=args.timeout)
    elif args.step == "run-all":
        step_run(pilot=False, max_workers=args.max_workers, timeout=args.timeout)
    elif args.step == "parse-logs":
        step_parse_logs()


if __name__ == "__main__":
    main()
