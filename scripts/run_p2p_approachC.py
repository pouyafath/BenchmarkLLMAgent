#!/usr/bin/env python3
"""Approach C: P2P retry loop.

After initial evaluation, identifies instances where F2P passed but P2P failed,
appends P2P failure feedback to the enhanced description, and re-runs the solver
for those specific instances (max 1 retry).

Usage:
    bench_env/bin/python scripts/run_p2p_approachC.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
DATASET_JSONL = ROOT / "data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl"
SELECTED_IDS = ROOT / "data/samples/groupC_swebenchlive_50/groupC_50_instance_ids.txt"
SAMPLES_JSON = ROOT / "data/samples/groupC_swebenchlive_50/groupC_50_samples.json"
SWEBENCH_PYTHON = ROOT / "bench_env" / "bin" / "python"

# Use Task 1 results as the initial run
INITIAL_RESULTS_DIR = ROOT / "results/groupC50_code_context_devstral_testpatch/code_context__code_context_devstral_testpatch_groupC50_20260413"
INITIAL_RUN_ID = "secondpaper10_code_context_code_context_devstral_testpatch_groupC50_20260413"

# Approach C output
OUTPUT_DIR = ROOT / "results/groupC50_p2p_approachC"
OUTPUT_TAG = "code_context_devstral_tp_retry_groupC50_20260414"

BENCHMARK_CONFIG = Path("/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks.yaml")
MODEL_OVERRIDE_CONFIG = Path("/home/22pf2/SWE-Bench_Replication/config/devstral_vllm_override.yaml")
MODEL_CLASS = "minisweagent.models.litellm_textbased_model.LitellmTextbasedModel"

MAX_RETRIES = 1


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def load_dataset():
    rows = {}
    with DATASET_JSONL.open() as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                rows[row["instance_id"]] = row
    return rows


def load_instance_ids():
    return [l.strip() for l in SELECTED_IDS.read_text().splitlines() if l.strip()][:50]


def find_f2p_pass_p2p_fail_instances(run_id, instance_ids, dataset):
    """Find instances where F2P passed but P2P failed."""
    eval_dir = ROOT / "logs" / "run_evaluation" / run_id
    if not eval_dir.exists():
        print(f"  Eval dir not found: {eval_dir}")
        return []

    model_dirs = sorted([p for p in eval_dir.iterdir() if p.is_dir()])
    if not model_dirs:
        return []
    model_dir = model_dirs[0]

    candidates = []
    for iid in instance_ids:
        report_path = model_dir / iid / "report.json"
        if not report_path.exists():
            continue

        report = json.loads(report_path.read_text())
        inst_report = report.get(iid, {})

        f2p_status = inst_report.get("tests_status", {}).get("FAIL_TO_PASS", {})
        p2p_status = inst_report.get("tests_status", {}).get("PASS_TO_PASS", {})

        # Check F2P all pass
        if "success" in f2p_status or "failure" in f2p_status:
            f2p_passed = len(f2p_status.get("success", []))
            f2p_failed = len(f2p_status.get("failure", []))
        else:
            f2p_passed = sum(1 for v in f2p_status.values() if v == "PASSED")
            f2p_failed = sum(1 for v in f2p_status.values() if v != "PASSED")

        if f2p_failed > 0 or f2p_passed == 0:
            continue  # F2P didn't pass

        # Check P2P failed
        if "success" in p2p_status or "failure" in p2p_status:
            p2p_failed_tests = p2p_status.get("failure", [])
        else:
            p2p_failed_tests = [k for k, v in p2p_status.items() if v != "PASSED"]

        if len(p2p_failed_tests) == 0:
            continue  # P2P all pass (already resolved)

        candidates.append({
            "instance_id": iid,
            "f2p_passed": f2p_passed,
            "p2p_failed_tests": p2p_failed_tests[:20],  # Cap at 20 for prompt
            "p2p_failed_count": len(p2p_failed_tests),
        })

    return candidates


def build_retry_dataset(candidates, initial_enhanced_jsonl, output_jsonl):
    """Build a new JSONL with P2P failure feedback appended to the problem statement."""
    # Load the initial enhanced dataset
    enhanced_rows = {}
    with initial_enhanced_jsonl.open() as f:
        for line in f:
            row = json.loads(line.strip())
            enhanced_rows[row["instance_id"]] = row

    retry_ids = []
    with output_jsonl.open("w") as f:
        for candidate in candidates:
            iid = candidate["instance_id"]
            row = dict(enhanced_rows[iid])

            # Append P2P failure feedback
            failed_tests = candidate["p2p_failed_tests"]
            feedback = (
                f"\n\n---\n"
                f"## IMPORTANT: Previous Fix Attempt Broke Regression Tests\n\n"
                f"A previous attempt to fix this issue succeeded in passing the target tests, "
                f"but **broke {candidate['p2p_failed_count']} existing tests** (regressions). "
                f"Your fix MUST pass the target tests WITHOUT breaking these regression tests:\n\n"
            )
            for test in failed_tests:
                feedback += f"- `{test}`\n"
            if candidate["p2p_failed_count"] > 20:
                feedback += f"- *(... and {candidate['p2p_failed_count'] - 20} more)*\n"
            feedback += (
                f"\n**Strategy**: Make minimal, targeted changes. Avoid modifying shared utilities "
                f"or base classes unless absolutely necessary. Prefer adding new behavior over "
                f"modifying existing behavior.\n"
            )

            row["problem_statement"] = row["problem_statement"] + feedback
            row["retry_attempt"] = 1
            row["p2p_failed_count"] = candidate["p2p_failed_count"]

            f.write(json.dumps(row) + "\n")
            retry_ids.append(iid)

    return retry_ids


def run_solver(dataset_jsonl, instance_ids, output_dir):
    """Run mini-SWE-agent solver on specific instances."""
    filter_regex = "|".join(f"^{iid}$" for iid in instance_ids)
    cmd = [
        str(SWEBENCH_PYTHON),
        str(ROOT / "scripts" / "solvers" / "run_mini_sweagent_jsonl.py"),
        "--dataset-jsonl", str(dataset_jsonl),
        "--filter", filter_regex,
        "--workers", "4",
        "--redo-existing",
        "--output", str(output_dir),
        "--model-class", MODEL_CLASS,
        "-c", str(BENCHMARK_CONFIG),
        "-c", str(MODEL_OVERRIDE_CONFIG),
    ]
    print(f"  Running solver on {len(instance_ids)} instances...")
    proc = subprocess.run(cmd, cwd=ROOT)
    return proc.returncode


def run_eval(dataset_jsonl, preds_json, instance_ids, run_id):
    """Run SWE-bench evaluation."""
    cmd = [
        str(SWEBENCH_PYTHON),
        "-m", "swebench.harness.run_evaluation",
        "--dataset_name", str(dataset_jsonl),
        "--predictions_path", str(preds_json),
        "--instance_ids", *instance_ids,
        "--max_workers", "4",
        "--timeout", "1800",
        "--run_id", run_id,
        "--namespace", "starryzhang",
    ]
    print(f"  Running evaluation...")
    proc = subprocess.run(cmd, cwd=ROOT)
    return proc.returncode


def main():
    print(f"=== Approach C: P2P Retry Loop ===")
    print(f"Started at: {utc_now()}")

    dataset = load_dataset()
    instance_ids = load_instance_ids()

    # Step 1: Find F2P-pass, P2P-fail instances from Task 1 results
    print(f"\n--- Step 1: Finding F2P-pass, P2P-fail instances ---")
    candidates = find_f2p_pass_p2p_fail_instances(INITIAL_RUN_ID, instance_ids, dataset)
    print(f"  Found {len(candidates)} candidates for retry:")
    for c in candidates:
        print(f"    {c['instance_id']}: {c['p2p_failed_count']} P2P failures")

    if not candidates:
        print("  No candidates for retry. Exiting.")
        return

    # Step 2: Build retry dataset with P2P failure feedback
    print(f"\n--- Step 2: Building retry dataset ---")
    experiment_dir = OUTPUT_DIR / f"code_context__{OUTPUT_TAG}"
    experiment_dir.mkdir(parents=True, exist_ok=True)

    # Copy baseline
    baseline_src = INITIAL_RESULTS_DIR / "baseline_solver_run"
    baseline_dst = experiment_dir / "baseline_solver_run"
    if not baseline_dst.exists():
        subprocess.run(["cp", "-r", str(baseline_src), str(baseline_dst)])

    initial_enhanced_jsonl = INITIAL_RESULTS_DIR / "secondpaper10_enhanced_code_context.jsonl"
    retry_jsonl = experiment_dir / "retry_enhanced_code_context.jsonl"
    retry_ids = build_retry_dataset(candidates, initial_enhanced_jsonl, retry_jsonl)
    print(f"  Retry dataset: {retry_jsonl}")
    print(f"  Instances for retry: {len(retry_ids)}")

    # Step 3: Run solver on retry instances
    print(f"\n--- Step 3: Running solver on retry instances ---")
    retry_solver_dir = experiment_dir / "retry_solver_run"
    retry_solver_dir.mkdir(parents=True, exist_ok=True)
    rc = run_solver(retry_jsonl, retry_ids, retry_solver_dir)
    print(f"  Solver exit code: {rc}")

    # Step 4: Evaluate retry
    print(f"\n--- Step 4: Evaluating retry ---")
    retry_preds = retry_solver_dir / "preds.json"
    if retry_preds.exists():
        retry_run_id = f"secondpaper10_retry_{OUTPUT_TAG}"
        run_eval(DATASET_JSONL, retry_preds, retry_ids, retry_run_id)

        # Analyze retry results
        print(f"\n--- Step 5: Analyzing retry results ---")
        retry_candidates = find_f2p_pass_p2p_fail_instances(retry_run_id, retry_ids, dataset)
        retry_eval_dir = ROOT / "logs" / "run_evaluation" / retry_run_id
        model_dirs = sorted([p for p in retry_eval_dir.iterdir() if p.is_dir()])
        model_dir = model_dirs[0] if model_dirs else None

        resolved_count = 0
        f2p_still_pass = 0
        p2p_improved = 0
        for iid in retry_ids:
            report_path = model_dir / iid / "report.json" if model_dir else None
            if not report_path or not report_path.exists():
                print(f"    {iid}: No report (eval failed)")
                continue
            report = json.loads(report_path.read_text()).get(iid, {})
            resolved = report.get("resolved", False)
            f2p = report.get("tests_status", {}).get("FAIL_TO_PASS", {})
            p2p = report.get("tests_status", {}).get("PASS_TO_PASS", {})

            if "success" in f2p or "failure" in f2p:
                f2p_ok = len(f2p.get("failure", [])) == 0 and len(f2p.get("success", [])) > 0
                p2p_failed = len(p2p.get("failure", []))
            else:
                f2p_ok = all(v == "PASSED" for v in f2p.values()) and len(f2p) > 0
                p2p_failed = sum(1 for v in p2p.values() if v != "PASSED")

            # Find original P2P failures for comparison
            orig = next((c for c in candidates if c["instance_id"] == iid), None)
            orig_p2p_fails = orig["p2p_failed_count"] if orig else "?"

            status = "RESOLVED" if resolved else ("F2P✓ P2P✗" if f2p_ok else "F2P✗")
            print(f"    {iid}: {status} (P2P fails: {orig_p2p_fails}→{p2p_failed})")

            if resolved:
                resolved_count += 1
            if f2p_ok:
                f2p_still_pass += 1
            if orig and p2p_failed < orig["p2p_failed_count"]:
                p2p_improved += 1

        # Save summary
        summary = {
            "approach": "C_retry",
            "timestamp": utc_now(),
            "initial_candidates": len(candidates),
            "retry_ids": retry_ids,
            "resolved_after_retry": resolved_count,
            "f2p_still_pass_after_retry": f2p_still_pass,
            "p2p_improved": p2p_improved,
        }
        summary_path = experiment_dir / "retry_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"\n  Summary saved to: {summary_path}")
        print(f"  Resolved after retry: {resolved_count}/{len(retry_ids)}")
        print(f"  F2P still passing: {f2p_still_pass}/{len(retry_ids)}")
        print(f"  P2P improved: {p2p_improved}/{len(retry_ids)}")
    else:
        print("  ERROR: No predictions file generated")

    print(f"\nApproach C completed at: {utc_now()}")


if __name__ == "__main__":
    main()
