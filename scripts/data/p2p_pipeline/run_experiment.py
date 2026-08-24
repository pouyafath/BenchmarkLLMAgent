#!/usr/bin/env python3
"""
P2P Pipeline — Enhancer+Solver Experiment (Steps 6–9).

Runs on Stage 2 validated instances (have real Docker images).
Uses gpt-oss:120b via Ollama for both enhancer and solver.

Steps:
  6. Baseline solver — solve issues using original problem_statement
  7. Enhancer — rewrite/enhance each issue's problem_statement
  8. Enhanced solver — solve issues using enhanced problem_statement
  9. Analysis — compare P2P pass rates: baseline vs enhanced

Usage:
    python scripts/data/p2p_pipeline/run_experiment.py \\
        --stage2-dataset data/samples/pouya_p2p_pipeline/stage2_approach2/dataset.jsonl \\
        --run-dir runs/p2p_experiment_20260515 \\
        --limit 10  # start small for testing
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Optional

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

BENCH_ENV_PYTHON = ROOT / "bench_env/bin/python"
PAUL_ENV_PYTHON = pathlib.Path("/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python")
SOLVER_SCRIPT = ROOT / "scripts/solvers/run_mini_sweagent_jsonl.py"
EVAL_SCRIPT = ROOT / "scripts/evaluate/evaluate.py"
SWEBENCH_CONFIG = pathlib.Path(
    "/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks.yaml"
)
OLLAMA_OVERRIDE = ROOT / "configs/p2p_pipeline/ollama_gpt_oss_override.yaml"

# ── Ollama environment for enhancer ──────────────────────────────────────────
OLLAMA_ENV = {
    "USE_OLLAMA": "1",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OLLAMA_MODEL": "gpt-oss:120b",
    # Unset OpenAI-compat so enhancer falls through to Ollama
    "OPENAI_COMPAT_BASE_URL": "",
    "OPENAI_COMPAT_API_KEY": "",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def write_progress(run_dir: pathlib.Path, progress: dict, msg: str):
    progress["last_update"] = _now()
    progress.setdefault("log", []).append(f"{_now()} {msg}")
    (run_dir / "progress.json").write_text(json.dumps(progress, indent=2))
    with open(run_dir / "progress.log", "a") as f:
        f.write(f"{_now()} {msg}\n")
    print(f"[{_now()}] {msg}")

def run_subprocess(cmd, env=None, log_path=None, timeout=7200):
    merged = dict(os.environ)
    if env:
        merged.update(env)
    with open(log_path or "/dev/null", "w") as log_f:
        proc = subprocess.run(
            cmd, env=merged, stdout=log_f, stderr=subprocess.STDOUT,
            timeout=timeout
        )
    return proc.returncode


def solver_ready_instance(inst: dict) -> dict:
    """Force image_name to docker_image (mini-SWE-agent checks image_name first)."""
    row = dict(inst)
    if row.get("docker_image"):
        row["image_name"] = row["docker_image"]
    return row


# ── Step 6: Baseline solver ─────────────────────────────────────────────────

def run_baseline_solver(run_dir: pathlib.Path, instances: list[dict],
                        progress: dict) -> pathlib.Path:
    progress["step"] = "step6_baseline_solver"
    write_progress(run_dir, progress,
                   f"STEP 6: Baseline solver on {len(instances)} instances")

    solver_dir = run_dir / "solver_baseline"
    solver_dir.mkdir(exist_ok=True)

    # Write solver input dataset
    dataset_path = run_dir / "solver_baseline_dataset.jsonl"
    with open(dataset_path, "w") as f:
        for inst in instances:
            f.write(json.dumps(solver_ready_instance(inst)) + "\n")

    # Write solver_instances.jsonl (for eval to find)
    with open(solver_dir / "solver_instances.jsonl", "w") as f:
        for inst in instances:
            f.write(json.dumps(solver_ready_instance(inst)) + "\n")

    cmd = [
        str(BENCH_ENV_PYTHON), str(SOLVER_SCRIPT),
        "--dataset-jsonl", str(dataset_path),
        "-c", str(SWEBENCH_CONFIG),
        "-c", str(OLLAMA_OVERRIDE),
        "--output", str(solver_dir),
        "--workers", "2",
    ]

    write_progress(run_dir, progress, "  Running mini-SWE-agent baseline…")
    try:
        run_subprocess(cmd, log_path=solver_dir / "minisweagent.log", timeout=14400)
    except subprocess.TimeoutExpired:
        write_progress(run_dir, progress, "  Baseline solver TIMEOUT")

    write_progress(run_dir, progress,
                   f"  Baseline solver done → {solver_dir}/preds.json")
    return solver_dir


# ── Step 7: Enhancer ─────────────────────────────────────────────────────────

def run_enhancer(run_dir: pathlib.Path, instances: list[dict],
                 progress: dict, enhancer_id: str = "llm_append_analysis") -> list[dict]:
    progress["step"] = "step7_enhancer"
    write_progress(run_dir, progress,
                   f"STEP 7: Enhancement ({enhancer_id}) on {len(instances)} instances")

    # Set Ollama env for the enhancer
    for k, v in OLLAMA_ENV.items():
        os.environ[k] = v

    from src.enhancers.dispatcher import get_enhancer
    enhancer = get_enhancer(enhancer_id)
    if enhancer is None:
        write_progress(run_dir, progress, f"  ERROR: enhancer '{enhancer_id}' not found")
        return []

    enhanced_rows = []
    failures = []
    for i, inst in enumerate(instances):
        iid = inst["instance_id"]
        try:
            result = enhancer(inst)
            row = dict(inst)
            if isinstance(result, dict) and result.get("enhanced_body"):
                row["problem_statement"] = result["enhanced_body"]
                row["enhanced_title"] = result.get("enhanced_title")
                row["enhancement_metadata"] = result.get("enhancement_metadata", {})
                enhanced_rows.append(row)
                write_progress(run_dir, progress,
                               f"  [{i+1}/{len(instances)}] {iid} enhanced ✓")
            else:
                failures.append({"instance_id": iid, "reason": "no enhanced_body"})
                write_progress(run_dir, progress,
                               f"  [{i+1}/{len(instances)}] {iid} no output")
        except Exception as exc:
            failures.append({"instance_id": iid, "reason": str(exc)[:200]})
            write_progress(run_dir, progress,
                           f"  [{i+1}/{len(instances)}] {iid} FAILED: {exc}")

    # Save enhanced dataset
    enhanced_path = run_dir / "solver_enhanced_dataset.jsonl"
    with open(enhanced_path, "w") as f:
        for r in enhanced_rows:
            f.write(json.dumps(r) + "\n")

    (run_dir / "enhancement_failures.json").write_text(json.dumps(failures, indent=2))

    progress["enhanced_count"] = len(enhanced_rows)
    progress["enhancement_failures"] = len(failures)
    write_progress(run_dir, progress,
                   f"  Enhancement done: {len(enhanced_rows)}/{len(instances)} valid")
    return enhanced_rows


# ── Step 8: Enhanced solver ──────────────────────────────────────────────────

def run_enhanced_solver(run_dir: pathlib.Path, enhanced_instances: list[dict],
                        progress: dict) -> pathlib.Path:
    progress["step"] = "step8_enhanced_solver"
    write_progress(run_dir, progress,
                   f"STEP 8: Enhanced solver on {len(enhanced_instances)} instances")

    solver_dir = run_dir / "solver_enhanced"
    solver_dir.mkdir(exist_ok=True)

    dataset_path = run_dir / "solver_enhanced_dataset.jsonl"
    if not dataset_path.exists():
        with open(dataset_path, "w") as f:
            for inst in enhanced_instances:
                f.write(json.dumps(solver_ready_instance(inst)) + "\n")

    with open(solver_dir / "solver_instances.jsonl", "w") as f:
        for inst in enhanced_instances:
            f.write(json.dumps(solver_ready_instance(inst)) + "\n")

    cmd = [
        str(BENCH_ENV_PYTHON), str(SOLVER_SCRIPT),
        "--dataset-jsonl", str(dataset_path),
        "-c", str(SWEBENCH_CONFIG),
        "-c", str(OLLAMA_OVERRIDE),
        "--output", str(solver_dir),
        "--workers", "2",
    ]

    write_progress(run_dir, progress, "  Running mini-SWE-agent enhanced…")
    try:
        run_subprocess(cmd, log_path=solver_dir / "minisweagent.log", timeout=14400)
    except subprocess.TimeoutExpired:
        write_progress(run_dir, progress, "  Enhanced solver TIMEOUT")

    write_progress(run_dir, progress,
                   f"  Enhanced solver done → {solver_dir}/preds.json")
    return solver_dir


# ── Step 9: Evaluation & Analysis ────────────────────────────────────────────

def run_evaluation(run_dir: pathlib.Path, instances: list[dict],
                   solver_dir: pathlib.Path, eval_name: str,
                   progress: dict) -> dict:
    """Run SWE-bench evaluation on solver predictions. Returns results dict."""
    progress["step"] = f"eval_{eval_name}"
    eval_dir = run_dir / eval_name
    eval_dir.mkdir(exist_ok=True)

    preds_file = solver_dir / "preds.json"
    if not preds_file.exists():
        write_progress(run_dir, progress, f"  SKIP {eval_name}: no preds.json")
        return {"resolved": 0, "total": 0, "resolved_ids": [], "failed_ids": []}

    # Write validated_instances for evaluator
    subset_path = run_dir / "validated_instances.jsonl"
    if not subset_path.exists():
        with open(subset_path, "w") as f:
            for r in instances:
                f.write(json.dumps(r) + "\n")

    instance_ids = [r["instance_id"] for r in instances]
    cmd = [
        str(PAUL_ENV_PYTHON), str(EVAL_SCRIPT),
        "--dataset", str(subset_path),
        "--patch_dir", str(preds_file),
        "--platform", "linux",
        "--workers", "2",
        "--output_dir", str(eval_dir),
        "--overwrite", "1",
        "--instance_ids", *instance_ids,
    ]

    write_progress(run_dir, progress, f"  Evaluating {len(instance_ids)} instances ({eval_name})…")
    try:
        run_subprocess(cmd, log_path=eval_dir / "eval.log", timeout=3600)
    except subprocess.TimeoutExpired:
        write_progress(run_dir, progress, f"  {eval_name} TIMEOUT")

    resolved_ids = []
    failed_ids = []
    for iid in instance_ids:
        report = eval_dir / iid / "report.json"
        if report.exists():
            r = json.loads(report.read_text())
            (resolved_ids if r.get("resolved") else failed_ids).append(iid)
        else:
            failed_ids.append(iid)

    result = {
        "resolved": len(resolved_ids),
        "total": len(instance_ids),
        "resolved_ids": resolved_ids,
        "failed_ids": failed_ids,
    }
    (eval_dir / "results.json").write_text(json.dumps(result, indent=2))
    write_progress(run_dir, progress,
                   f"  {eval_name}: {len(resolved_ids)}/{len(instance_ids)} resolved")
    return result


def run_analysis(run_dir: pathlib.Path, instances: list[dict],
                 baseline_result: dict, enhanced_result: dict,
                 progress: dict):
    """Step 9: Compare baseline vs enhanced results and write summary."""
    progress["step"] = "step9_analysis"
    write_progress(run_dir, progress, "STEP 9: Analysis — baseline vs enhanced")

    baseline_set = set(baseline_result.get("resolved_ids", []))
    enhanced_set = set(enhanced_result.get("resolved_ids", []))
    all_ids = [r["instance_id"] for r in instances]

    gained = enhanced_set - baseline_set  # fixed by enhanced but not baseline
    lost   = baseline_set - enhanced_set  # fixed by baseline but not enhanced
    both   = baseline_set & enhanced_set  # fixed by both

    # Per-type breakdown
    type_map = {r["instance_id"]: r.get("issue_type", "?") for r in instances}
    types = sorted(set(type_map.values()))

    per_type = {}
    for t in types:
        t_ids = [iid for iid in all_ids if type_map.get(iid) == t]
        per_type[t] = {
            "total": len(t_ids),
            "baseline_resolved": len([iid for iid in t_ids if iid in baseline_set]),
            "enhanced_resolved": len([iid for iid in t_ids if iid in enhanced_set]),
        }

    analysis = {
        "timestamp": _now(),
        "total_instances": len(all_ids),
        "baseline_resolved": baseline_result["resolved"],
        "enhanced_resolved": enhanced_result["resolved"],
        "gained_by_enhancement": sorted(gained),
        "lost_by_enhancement": sorted(lost),
        "resolved_by_both": sorted(both),
        "per_issue_type": per_type,
        "improvement_pp": round(
            (enhanced_result["resolved"] - baseline_result["resolved"])
            / max(len(all_ids), 1) * 100, 2
        ),
    }

    (run_dir / "analysis.json").write_text(json.dumps(analysis, indent=2))

    # Human-readable summary
    lines = [
        "=" * 60,
        "P2P Pipeline — Enhancer+Solver Experiment Results",
        "=" * 60,
        f"Total instances:        {len(all_ids)}",
        f"Baseline resolved:      {baseline_result['resolved']}/{len(all_ids)} "
        f"({baseline_result['resolved']/max(len(all_ids),1)*100:.1f}%)",
        f"Enhanced resolved:      {enhanced_result['resolved']}/{len(all_ids)} "
        f"({enhanced_result['resolved']/max(len(all_ids),1)*100:.1f}%)",
        f"Improvement:            {analysis['improvement_pp']:+.1f} pp",
        f"Gained by enhancement:  {len(gained)} instances",
        f"Lost by enhancement:    {len(lost)} instances",
        "",
        "--- Per Issue Type ---",
    ]
    for t, data in per_type.items():
        lines.append(
            f"  {t:15s}: baseline {data['baseline_resolved']}/{data['total']}, "
            f"enhanced {data['enhanced_resolved']}/{data['total']}"
        )
    lines.extend(["", "=" * 60])

    summary_text = "\n".join(lines)
    (run_dir / "analysis_summary.txt").write_text(summary_text)
    print(summary_text)
    write_progress(run_dir, progress, summary_text)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="P2P Pipeline Enhancer+Solver Experiment")
    parser.add_argument("--stage2-dataset", type=pathlib.Path, required=True,
                        help="Stage 2 validated dataset with Docker images")
    parser.add_argument("--run-dir", type=pathlib.Path, required=True,
                        help="Output directory for this experiment run")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit to first N instances (0 = all)")
    parser.add_argument("--enhancer", default="llm_append_analysis",
                        help="Enhancer agent ID")
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--skip-enhanced", action="store_true")
    args = parser.parse_args()

    run_dir = args.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    # Load instances
    instances = [json.loads(l) for l in open(args.stage2_dataset) if l.strip()]
    if args.limit > 0:
        instances = instances[:args.limit]
    print(f"Loaded {len(instances)} instances from {args.stage2_dataset}")

    # Issue type breakdown
    type_counts = {}
    for r in instances:
        t = r.get("issue_type", "?")
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"Issue types: {type_counts}")

    # Progress
    progress = {
        "started_at": _now(),
        "dataset": str(args.stage2_dataset),
        "total_instances": len(instances),
        "issue_types": type_counts,
        "enhancer": args.enhancer,
        "solver": "mini_swe_agent",
        "llm": "gpt-oss:120b (Ollama)",
        "step": "init",
    }
    write_progress(run_dir, progress, f"Experiment started with {len(instances)} instances")

    # Save config
    (run_dir / "experiment_config.json").write_text(json.dumps({
        "dataset": str(args.stage2_dataset),
        "limit": args.limit,
        "enhancer": args.enhancer,
        "solver": "mini_swe_agent",
        "llm_model": "gpt-oss:120b",
        "llm_backend": "ollama (localhost:11434)",
    }, indent=2))

    # Write validated_instances for evaluator
    with open(run_dir / "validated_instances.jsonl", "w") as f:
        for r in instances:
            f.write(json.dumps(r) + "\n")

    # ── Step 6: Baseline solver ──────────────────────────────────────────
    baseline_dir = run_dir / "solver_baseline"
    if not args.skip_baseline:
        baseline_dir = run_baseline_solver(run_dir, instances, progress)
    else:
        write_progress(run_dir, progress, "STEP 6: SKIPPED (--skip-baseline)")

    # ── Step 6b: Baseline evaluation ─────────────────────────────────────
    baseline_result = run_evaluation(
        run_dir, instances, baseline_dir, "eval_baseline", progress
    )
    progress["baseline_resolved"] = baseline_result.get("resolved_ids", [])

    # ── Step 7: Enhancement ──────────────────────────────────────────────
    enhanced_instances = run_enhancer(
        run_dir, instances, progress, enhancer_id=args.enhancer
    )

    if not enhanced_instances:
        write_progress(run_dir, progress, "No enhanced instances — cannot run enhanced solver")
        enhanced_result = {"resolved": 0, "total": 0, "resolved_ids": [], "failed_ids": []}
    else:
        # ── Step 8: Enhanced solver ──────────────────────────────────────
        if not args.skip_enhanced:
            enhanced_dir = run_enhanced_solver(run_dir, enhanced_instances, progress)
        else:
            enhanced_dir = run_dir / "solver_enhanced"
            write_progress(run_dir, progress, "STEP 8: SKIPPED (--skip-enhanced)")

        # ── Step 8b: Enhanced evaluation ─────────────────────────────────
        enhanced_result = run_evaluation(
            run_dir, enhanced_instances, enhanced_dir, "eval_enhanced", progress
        )
        progress["enhanced_resolved"] = enhanced_result.get("resolved_ids", [])

    # ── Step 9: Analysis ─────────────────────────────────────────────────
    run_analysis(run_dir, instances, baseline_result, enhanced_result, progress)

    progress["step"] = "done"
    progress["finished_at"] = _now()
    write_progress(run_dir, progress, "EXPERIMENT COMPLETE")


if __name__ == "__main__":
    main()
