#!/usr/bin/env python3
"""
Stage 5-6 driver for gpt-oss:120b SOLVER on the 40-row pilot.

Reuses Stage 4 enhanced artifacts from the gpt-5.4-mini run.
Creates a NEW run directory so both results are preserved for comparison.

Key difference from the original pipeline:
  - Solver uses gpt-oss:120b via Ollama with litellm_textbased model class
    (text-based regex parsing instead of tool-call mode)
  - Longer timeouts: 120B model is ~10x slower per turn than gpt-5.4-mini
  - Workers=1 to avoid overloading Ollama

Usage:
    cd /home/22pf2/BenchmarkLLMAgent
    bench_env/bin/python scripts/workflows/run_pilot40_gptoss_solver.py
    bench_env/bin/python scripts/workflows/run_pilot40_gptoss_solver.py --resume
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Paths ─────────────────────────────────────────────────────────────────

STAGE3_EXPORT = Path(
    "/home/22pf2/paul-RepoLaunch/runs/"
    "stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/"
    "stage3_validation_completed40.jsonl"
)

# Previous run with gpt-5.4-mini solver (Stage 4 artifacts reused)
PREV_RUN_DIR = ROOT / "runs/paul_pilot40_stage4_stage6_20260526"

# New run directory for gpt-oss:120b solver
RUN_DIR = ROOT / "runs/paul_pilot40_gptoss_solver_20260527"

BENCH_ENV_PYTHON = ROOT / "bench_env/bin/python"
PAUL_ENV_PYTHON = Path("/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python")
SOLVER_SCRIPT = ROOT / "scripts/solvers/run_mini_sweagent_jsonl.py"
EVAL_SCRIPT = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"
SWEBENCH_CONFIG = Path(
    "/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/"
    "config/benchmarks/swebench_backticks.yaml"
)
OLLAMA_OVERRIDE = ROOT / "configs/p2p_pipeline/ollama_gpt_oss_override.yaml"

# gpt-oss:120b is ~10x slower per turn than gpt-5.4-mini
SOLVER_WORKERS = 1      # single worker to avoid overloading Ollama
EVAL_WORKERS = 2
SOLVER_TIMEOUT = 43200  # 12 hours (120B model needs ~30 min/instance × 40)
EVAL_TIMEOUT = 7200     # 2 hours per eval batch

SOLVER_MODEL = "gpt-oss:120b"


# ── Helpers ───────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _issue_type_counts(rows: list[dict]) -> dict[str, int]:
    return dict(Counter(r.get("issue_type", "unknown") for r in rows))


def write_progress(progress: dict, msg: str) -> None:
    progress["last_update"] = _now()
    progress.setdefault("log", []).append(f"{_now()} {msg}")
    (RUN_DIR / "progress.json").write_text(json.dumps(progress, indent=2))
    with open(RUN_DIR / "progress.log", "a") as f:
        f.write(f"{_now()} {msg}\n")
    print(f"[{_now()}] {msg}", flush=True)


def run_subprocess(cmd: list[str], env: dict | None = None,
                   log_path: Path | None = None,
                   timeout: int = 7200) -> int:
    merged = dict(os.environ)
    if env:
        merged.update(env)
    log_file = log_path or Path("/dev/null")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "w") as log_f:
        log_f.write(f"$ {' '.join(str(c) for c in cmd)}\n\n")
        log_f.flush()
        proc = subprocess.run(
            cmd, env=merged, stdout=log_f, stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    return proc.returncode


def _make_solver_env() -> dict[str, str]:
    """Environment for solver — Ollama gpt-oss:120b."""
    env = os.environ.copy()
    env["TAVILY_API_KEY"] = "tvly-dummy-no-tavily-calls"
    return env


def _step_done(marker_name: str) -> bool:
    return (RUN_DIR / f".done_{marker_name}").exists()


def _mark_done(marker_name: str) -> None:
    (RUN_DIR / f".done_{marker_name}").write_text(_now())


# ── Stage 5: Solver + Evaluation ─────────────────────────────────────────

def run_solver(label: str, dataset_path: Path, solver_dir: Path,
               progress: dict) -> Path:
    """Run mini-SWE-agent solver with gpt-oss:120b via Ollama."""
    solver_dir.mkdir(parents=True, exist_ok=True)
    progress["step"] = f"stage5_solver_{label}"
    write_progress(progress, f"STAGE 5: Running solver ({label}) with {SOLVER_MODEL}...")

    instances = _load_jsonl(dataset_path)
    _write_jsonl(solver_dir / "solver_instances.jsonl", instances)

    cmd = [
        str(BENCH_ENV_PYTHON), str(SOLVER_SCRIPT),
        "--dataset-jsonl", str(dataset_path),
        "-c", str(SWEBENCH_CONFIG),
        "-c", str(OLLAMA_OVERRIDE),
        "--output", str(solver_dir),
        "--workers", str(SOLVER_WORKERS),
    ]

    try:
        run_subprocess(cmd, env=_make_solver_env(),
                       log_path=solver_dir / "minisweagent.log",
                       timeout=SOLVER_TIMEOUT)
    except subprocess.TimeoutExpired:
        write_progress(progress, f"  Solver ({label}) TIMEOUT after {SOLVER_TIMEOUT}s")

    preds_path = solver_dir / "preds.json"
    n_preds = 0
    if preds_path.exists():
        data = json.loads(preds_path.read_text())
        n_preds = len(data) if isinstance(data, dict) else len(data)
    write_progress(progress,
                   f"  Solver ({label}) done: {n_preds} predictions")
    return solver_dir


def run_evaluation(label: str, validated_path: Path, solver_dir: Path,
                   eval_dir: Path, instance_ids: list[str],
                   progress: dict) -> dict[str, Any]:
    """Run gold-patch evaluation via SWE-bench-Live evaluation script."""
    eval_dir.mkdir(parents=True, exist_ok=True)
    progress["step"] = f"stage5_eval_{label}"
    write_progress(progress,
                   f"  Evaluating {len(instance_ids)} instances ({label})...")

    preds_file = solver_dir / "preds.json"
    if not preds_file.exists():
        write_progress(progress, f"  SKIP eval ({label}): no preds.json")
        return {"resolved": 0, "total": len(instance_ids),
                "resolved_ids": [], "failed_ids": instance_ids}

    cmd = [
        str(PAUL_ENV_PYTHON), str(EVAL_SCRIPT),
        "--dataset", str(validated_path),
        "--patch_dir", str(preds_file),
        "--platform", "linux",
        "--workers", str(EVAL_WORKERS),
        "--output_dir", str(eval_dir),
        "--overwrite", "1",
        "--instance_ids", *instance_ids,
    ]

    try:
        run_subprocess(cmd, log_path=eval_dir / "eval.log",
                       timeout=EVAL_TIMEOUT)
    except subprocess.TimeoutExpired:
        write_progress(progress, f"  Eval ({label}) TIMEOUT after {EVAL_TIMEOUT}s")

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
        "resolved_ids": sorted(resolved_ids),
        "failed_ids": sorted(failed_ids),
    }
    (eval_dir / "eval_results.json").write_text(json.dumps(result, indent=2))
    write_progress(progress,
                   f"  Eval ({label}): {len(resolved_ids)}/{len(instance_ids)} resolved")
    return result


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Pilot-40 Stage 5-6 with gpt-oss:120b solver")
    parser.add_argument("--resume", action="store_true",
                        help="Skip completed steps")
    args = parser.parse_args()
    resume = args.resume

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load instances ───────────────────────────────────────────────────
    instances = _load_jsonl(STAGE3_EXPORT)
    assert len(instances) == 40, f"Expected 40 rows, got {len(instances)}"
    type_counts = _issue_type_counts(instances)
    print(f"Loaded {len(instances)} instances: {type_counts}")

    # Write immutable copy of input
    validated_path = RUN_DIR / "validated_instances.jsonl"
    if not validated_path.exists():
        _write_jsonl(validated_path, instances)

    # ── Reuse Stage 4 artifacts from previous run ────────────────────────
    stage4_dir = RUN_DIR / "stage4_enhanced"
    if not stage4_dir.exists():
        prev_stage4 = PREV_RUN_DIR / "stage4_enhanced"
        assert prev_stage4.exists(), f"Previous Stage 4 not found: {prev_stage4}"
        shutil.copytree(prev_stage4, stage4_dir)
        print(f"Copied Stage 4 artifacts from {prev_stage4}")

    _mark_done("stage4")

    # Save experiment config
    (RUN_DIR / "experiment_config.json").write_text(json.dumps({
        "source_dataset": str(STAGE3_EXPORT),
        "total_instances": len(instances),
        "issue_type_counts": type_counts,
        "enhancer": "llm_append_analysis",
        "enhancer_model": "gpt-oss:120b (ollama localhost:11434)",
        "solver": "mini_swe_agent",
        "solver_model": f"{SOLVER_MODEL} (ollama localhost:11434, litellm_textbased)",
        "solver_config": str(OLLAMA_OVERRIDE),
        "solver_workers": SOLVER_WORKERS,
        "eval_workers": EVAL_WORKERS,
        "run_dir": str(RUN_DIR),
        "prev_run_dir": str(PREV_RUN_DIR),
        "note": "Same Stage 4 artifacts as gpt-5.4-mini run, solver changed to gpt-oss:120b",
    }, indent=2))

    progress: dict[str, Any] = {
        "started_at": _now(),
        "total_instances": len(instances),
        "issue_types": type_counts,
        "solver_model": SOLVER_MODEL,
    }
    write_progress(progress, f"Experiment started: {len(instances)} instances, solver={SOLVER_MODEL}")

    all_ids = [r["instance_id"] for r in instances]
    baseline_dataset = stage4_dir / "baseline.jsonl"
    enhanced_dataset = stage4_dir / "llm_append_analysis.jsonl"
    enhanced_rows = _load_jsonl(enhanced_dataset)

    # ── Stage 5a: Baseline solver ────────────────────────────────────────
    baseline_solver_dir = RUN_DIR / "stage5_solver_eval/solver_baseline"
    if resume and _step_done("stage5_baseline_solver"):
        write_progress(progress, "STAGE 5 (baseline solver): SKIP (already done)")
    else:
        run_solver("baseline", baseline_dataset, baseline_solver_dir, progress)
        _mark_done("stage5_baseline_solver")

    # ── Stage 5b: Baseline evaluation ────────────────────────────────────
    eval_baseline_dir = RUN_DIR / "stage5_solver_eval/eval_baseline"
    if resume and _step_done("stage5_baseline_eval"):
        write_progress(progress, "STAGE 5 (baseline eval): SKIP (already done)")
        if (eval_baseline_dir / "eval_results.json").exists():
            baseline_result = json.loads(
                (eval_baseline_dir / "eval_results.json").read_text())
        else:
            baseline_result = {"resolved": 0, "total": len(all_ids),
                               "resolved_ids": [], "failed_ids": all_ids}
    else:
        baseline_result = run_evaluation(
            "baseline", validated_path, baseline_solver_dir,
            eval_baseline_dir, all_ids, progress)
        _mark_done("stage5_baseline_eval")

    # ── Stage 5c: Enhanced solver ────────────────────────────────────────
    enhanced_solver_dir = RUN_DIR / "stage5_solver_eval/solver_enhanced"
    if resume and _step_done("stage5_enhanced_solver"):
        write_progress(progress, "STAGE 5 (enhanced solver): SKIP (already done)")
    else:
        run_solver("enhanced", enhanced_dataset, enhanced_solver_dir, progress)
        _mark_done("stage5_enhanced_solver")

    # ── Stage 5d: Enhanced evaluation ────────────────────────────────────
    eval_enhanced_dir = RUN_DIR / "stage5_solver_eval/eval_enhanced"
    enhanced_ids = [r["instance_id"] for r in enhanced_rows]
    if resume and _step_done("stage5_enhanced_eval"):
        write_progress(progress, "STAGE 5 (enhanced eval): SKIP (already done)")
        if (eval_enhanced_dir / "eval_results.json").exists():
            enhanced_result = json.loads(
                (eval_enhanced_dir / "eval_results.json").read_text())
        else:
            enhanced_result = {"resolved": 0, "total": len(enhanced_ids),
                               "resolved_ids": [], "failed_ids": enhanced_ids}
    else:
        enhanced_result = run_evaluation(
            "enhanced", validated_path, enhanced_solver_dir,
            eval_enhanced_dir, enhanced_ids, progress)
        _mark_done("stage5_enhanced_eval")

    # ── Stage 6: Report (reuse regenerate script) ────────────────────────
    write_progress(progress, "STAGE 6: Generating report...")

    # Run the regenerate script adapted for this run dir
    report_dir = RUN_DIR / "stage6_report"
    report_dir.mkdir(parents=True, exist_ok=True)

    # Generate summary inline (same logic as regenerate_pilot40_report.py)
    baseline_ps = {r["instance_id"]: r.get("problem_statement", "")
                   for r in _load_jsonl(baseline_dataset)}
    truly_enhanced_ids = set()
    unchanged_ids = set()
    for row in enhanced_rows:
        iid = row["instance_id"]
        meta = row.get("enhancement_metadata", {})
        if meta.get("enhancer_type") == "error":
            unchanged_ids.add(iid)
        elif row.get("problem_statement", "").strip() != baseline_ps.get(iid, "").strip():
            truly_enhanced_ids.add(iid)
        else:
            unchanged_ids.add(iid)

    type_map = {r["instance_id"]: r.get("issue_type", "unknown") for r in instances}
    baseline_set = set(baseline_result.get("resolved_ids", []))
    enhanced_set = set(enhanced_result.get("resolved_ids", []))
    gained = sorted(enhanced_set - baseline_set)
    lost = sorted(baseline_set - enhanced_set)
    both = sorted(baseline_set & enhanced_set)
    n = max(len(all_ids), 1)

    per_type: dict[str, dict] = {}
    for t in sorted(set(type_map.values())):
        t_ids = [iid for iid in all_ids if type_map.get(iid) == t]
        per_type[t] = {
            "total": len(t_ids),
            "truly_enhanced": len([iid for iid in t_ids if iid in truly_enhanced_ids]),
            "baseline_resolved": len([iid for iid in t_ids if iid in baseline_set]),
            "enhanced_resolved": len([iid for iid in t_ids if iid in enhanced_set]),
        }

    summary = {
        "timestamp": _now(),
        "source_dataset": str(STAGE3_EXPORT),
        "total_instances": len(all_ids),
        "issue_type_counts": type_counts,
        "enhancer": "llm_append_analysis",
        "solver": f"mini_swe_agent ({SOLVER_MODEL} via Ollama, litellm_textbased)",
        "truly_enhanced_count": len(truly_enhanced_ids),
        "unchanged_count": len(unchanged_ids),
        "truly_enhanced_ids": sorted(truly_enhanced_ids),
        "unchanged_ids": sorted(unchanged_ids),
        "baseline": {
            "resolved": baseline_result["resolved"],
            "total": baseline_result["total"],
            "rate_pct": round(baseline_result["resolved"] / n * 100, 2),
            "resolved_ids": baseline_result.get("resolved_ids", []),
        },
        "enhanced": {
            "resolved": enhanced_result["resolved"],
            "total": enhanced_result["total"],
            "rate_pct": round(enhanced_result["resolved"] / n * 100, 2),
            "resolved_ids": enhanced_result.get("resolved_ids", []),
        },
        "comparison": {
            "improvement_pp": round(
                (enhanced_result["resolved"] - baseline_result["resolved"]) / n * 100, 2
            ),
            "gained_by_enhancement": gained,
            "lost_by_enhancement": lost,
            "resolved_by_both": both,
        },
        "per_issue_type": per_type,
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    bl = baseline_result
    en = enhanced_result
    imp = summary["comparison"]["improvement_pp"]
    lines = [
        "# Stage 6: Pilot-40 Enhancer+Solver Comparison Report",
        "",
        f"**Generated:** {_now()}",
        f"**Source dataset:** `{STAGE3_EXPORT.name}` ({len(all_ids)} instances)",
        f"**Issue types:** {summary['issue_type_counts']}",
        f"**Enhancer:** llm_append_analysis (gpt-oss:120b via Ollama)",
        f"**Solver:** mini-SWE-agent ({SOLVER_MODEL} via Ollama, litellm_textbased)",
        "",
        "## Overall Results",
        "",
        "| Condition | Resolved | Total | Rate |",
        "|---|---:|---:|---:|",
        f"| Baseline (original) | {bl['resolved']} | {bl['total']} | {bl['resolved']/n*100:.1f}% |",
        f"| Enhanced (llm_append_analysis) | {en['resolved']} | {en['total']} | {en['resolved']/n*100:.1f}% |",
        "",
        f"**Improvement:** {imp:+.1f} percentage points",
        f"**Gained by enhancement:** {len(gained)} instances "
        f"({', '.join(f'`{g}`' for g in gained) or 'none'})",
        f"**Lost by enhancement:** {len(lost)} instances "
        f"({', '.join(f'`{l}`' for l in lost) or 'none'})",
        f"**Resolved by both:** {len(both)} instances",
        "",
        "## Per Issue Type",
        "",
        "| Issue Type | Count | Enhanced | Baseline Resolved | Enhanced Resolved |",
        "|---|---:|---:|---:|---:|",
    ]
    for t, data in per_type.items():
        lines.append(
            f"| {t} | {data['total']} | "
            f"{data['truly_enhanced']}/{data['total']} | "
            f"{data['baseline_resolved']}/{data['total']} | "
            f"{data['enhanced_resolved']}/{data['total']} |"
        )

    te_baseline = len([iid for iid in truly_enhanced_ids if iid in baseline_set])
    te_enhanced = len([iid for iid in truly_enhanced_ids if iid in enhanced_set])
    uc_baseline = len([iid for iid in unchanged_ids if iid in baseline_set])
    uc_enhanced = len([iid for iid in unchanged_ids if iid in enhanced_set])

    lines.extend([
        "",
        "## Enhancement Coverage",
        "",
        f"- Instances sent to enhancer: {len(all_ids)}",
        f"- Truly enhanced (body changed): {len(truly_enhanced_ids)}",
        f"- Unchanged (LLM error/empty): {len(unchanged_ids)}",
        "",
        "## Sub-Analysis: Truly Enhanced Only",
        "",
        "| Subset | Count | Baseline Resolved | Enhanced Resolved |",
        "|---|---:|---:|---:|",
        f"| Truly enhanced | {len(truly_enhanced_ids)} | {te_baseline} | {te_enhanced} |",
        f"| Unchanged | {len(unchanged_ids)} | {uc_baseline} | {uc_enhanced} |",
        f"| Total | {len(all_ids)} | {bl['resolved']} | {en['resolved']} |",
        "",
        "## Resolved Instance Details",
        "",
    ])
    if baseline_result.get("resolved_ids"):
        lines.append("### Baseline resolved")
        for iid in sorted(baseline_result["resolved_ids"]):
            flag = " (truly enhanced)" if iid in truly_enhanced_ids else " (unchanged)"
            lines.append(f"- `{iid}` ({type_map.get(iid, '?')}{flag})")
        lines.append("")
    if enhanced_result.get("resolved_ids"):
        lines.append("### Enhanced resolved")
        for iid in sorted(enhanced_result["resolved_ids"]):
            flag = " (truly enhanced)" if iid in truly_enhanced_ids else " (unchanged)"
            lines.append(f"- `{iid}` ({type_map.get(iid, '?')}{flag})")
        lines.append("")

    lines.extend([
        "## Artifacts",
        "",
        f"- Run directory: `{RUN_DIR}`",
        f"- Previous run (gpt-5.4-mini solver): `{PREV_RUN_DIR}`",
        f"- Summary JSON: `{report_dir / 'summary.json'}`",
        f"- Stage 4 enhanced datasets: `{stage4_dir}`",
        f"- Stage 5 solver outputs: `{RUN_DIR / 'stage5_solver_eval'}`",
        f"- This report: `{report_dir / 'REPORT.md'}`",
    ])
    (report_dir / "REPORT.md").write_text("\n".join(lines) + "\n")

    _mark_done("stage6")
    progress["step"] = "done"
    progress["finished_at"] = _now()
    write_progress(progress, "ALL STAGES COMPLETE")
    print(f"\nReport: {report_dir / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
