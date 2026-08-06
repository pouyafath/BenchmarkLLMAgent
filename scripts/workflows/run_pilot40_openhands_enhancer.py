#!/usr/bin/env python3
"""
Stage 4-6 driver for openhands enhancer on the 40-row pilot dataset.

Input:  Immutable Stage 3 completed export (40 rows, PASS_TO_PASS > 0 gate).
Output: Separate immutable stage artifacts per the handoff output contract.

Stages:
  4. Enhancement — openhands agent (gpt-5.4-mini via OpenAI)
  5. Solver evaluation — mini-SWE-agent on baseline + enhanced conditions
  6. Report — per-issue-type comparison, summary.json, REPORT.md

Usage:
    cd /home/22pf2/BenchmarkLLMAgent
    # 5-row canary first:
    bench_env/bin/python scripts/workflows/run_pilot40_openhands_enhancer.py --canary 5
    # Full 40-row run:
    bench_env/bin/python scripts/workflows/run_pilot40_openhands_enhancer.py
    # Resume (skip completed steps):
    bench_env/bin/python scripts/workflows/run_pilot40_openhands_enhancer.py --resume
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Paths ───────────────────────────────────────────────────────────────────

STAGE3_EXPORT = Path(
    "/home/22pf2/paul-RepoLaunch/runs/"
    "stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/"
    "stage3_validation_completed40.jsonl"
)
RUN_DIR = ROOT / "runs/paul_pilot40_openhands_20260601"

BENCH_ENV_PYTHON = ROOT / "bench_env/bin/python"
PAUL_ENV_PYTHON = Path("/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python")
SOLVER_SCRIPT = ROOT / "scripts/solvers/run_mini_sweagent_jsonl.py"
EVAL_SCRIPT = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"
SWEBENCH_CONFIG = Path(
    "/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/"
    "config/benchmarks/swebench_backticks.yaml"
)
GPT54MINI_OVERRIDE = Path(
    "/home/22pf2/SWE-Bench_Replication/config/openai_gpt54mini_override.yaml"
)

SOLVER_WORKERS = 2
EVAL_WORKERS = 2
SOLVER_TIMEOUT = 14400   # 4 hours per solver batch
EVAL_TIMEOUT = 7200      # 2 hours per eval batch
ENHANCER_TIMEOUT = 600   # 10 min per enhancement (openhands can be slow)

SOLVER_MODEL = "gpt-5.4-mini"
ENHANCER_ID = "openhands"

# ── Load .env for OPENAI_API_KEY ────────────────────────────────────────────

_dotenv = ROOT / ".env"
if _dotenv.exists():
    for line in _dotenv.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


# ── Helpers ─────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _solver_ready(inst: dict) -> dict:
    """Force image_name for mini-SWE-agent compatibility."""
    row = dict(inst)
    if row.get("docker_image"):
        row["image_name"] = row["docker_image"]
    return row


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


def _step_done(marker_name: str) -> bool:
    return (RUN_DIR / f".done_{marker_name}").exists()


def _mark_done(marker_name: str) -> None:
    (RUN_DIR / f".done_{marker_name}").write_text(_now())


# ── Stage 4: Enhancement (openhands) ─────────────────────────────────────

def run_stage4_enhancement(instances: list[dict], progress: dict) -> list[dict]:
    """Enhance problem_statement via openhands (gpt-5.4-mini via OpenAI)."""
    progress["step"] = "stage4_enhancement"
    write_progress(progress,
                   f"STAGE 4: openhands enhancement on {len(instances)} instances")

    from src.enhancers.dispatcher import get_enhancer
    enhancer = get_enhancer(ENHANCER_ID)
    if enhancer is None:
        write_progress(progress, f"  ERROR: enhancer '{ENHANCER_ID}' not found")
        return []

    enhanced_rows: list[dict] = []
    failures: list[dict] = []

    for i, inst in enumerate(instances):
        iid = inst["instance_id"]
        t0 = time.time()
        try:
            result = enhancer(inst)
            elapsed = time.time() - t0
            row = dict(inst)
            enhanced_body = result.get("enhanced_body", "") if isinstance(result, dict) else ""
            meta = result.get("enhancement_metadata", {}) if isinstance(result, dict) else {}
            original_ps = inst.get("problem_statement", "")
            body_changed = bool(enhanced_body) and enhanced_body.strip() != original_ps.strip()
            is_error = meta.get("enhancer_type") == "error"

            if body_changed and not is_error:
                row["original_problem_statement"] = original_ps
                row["problem_statement"] = enhanced_body
                row["enhanced_title"] = result.get("enhanced_title")
                row["enhancement_metadata"] = meta
                row["_enhancement_valid"] = True
                enhanced_rows.append(row)
                write_progress(progress,
                               f"  [{i+1}/{len(instances)}] {iid} enhanced ({elapsed:.0f}s)")
            else:
                reason = meta.get("error", "unchanged body") if is_error else "body unchanged after enhancement"
                failures.append({"instance_id": iid, "reason": reason,
                                 "enhancement_metadata": meta, "elapsed_s": elapsed})
                row["original_problem_statement"] = original_ps
                row["enhancement_metadata"] = meta
                row["_enhancement_valid"] = False
                enhanced_rows.append(row)
                write_progress(progress,
                               f"  [{i+1}/{len(instances)}] {iid} unchanged ({reason[:60]}) ({elapsed:.0f}s)")
        except Exception as exc:
            elapsed = time.time() - t0
            failures.append({"instance_id": iid, "reason": str(exc)[:300],
                             "elapsed_s": elapsed})
            write_progress(progress,
                           f"  [{i+1}/{len(instances)}] {iid} FAILED ({elapsed:.0f}s): {exc}")

    stage4_dir = RUN_DIR / "stage4_enhanced"
    stage4_dir.mkdir(parents=True, exist_ok=True)

    # Write baseline dataset (original problem_statement, solver-ready)
    _write_jsonl(stage4_dir / "baseline.jsonl",
                 [_solver_ready(inst) for inst in instances])

    # Write enhanced dataset
    _write_jsonl(stage4_dir / f"{ENHANCER_ID}.jsonl",
                 [_solver_ready(r) for r in enhanced_rows])

    # Write failures
    (stage4_dir / "enhancement_failures.json").write_text(
        json.dumps(failures, indent=2))

    valid_count = sum(1 for r in enhanced_rows if r.get("_enhancement_valid"))
    # Write stage 4 summary
    (stage4_dir / "stage4_summary.json").write_text(json.dumps({
        "timestamp": _now(),
        "enhancer": ENHANCER_ID,
        "enhancer_model": SOLVER_MODEL,
        "total_instances": len(instances),
        "enhanced_count": len(enhanced_rows),
        "truly_enhanced_count": valid_count,
        "failure_count": len(failures),
        "issue_types_input": _issue_type_counts(instances),
        "issue_types_enhanced": _issue_type_counts(enhanced_rows),
    }, indent=2))

    progress["stage4_enhanced_count"] = len(enhanced_rows)
    progress["stage4_truly_enhanced_count"] = valid_count
    progress["stage4_failure_count"] = len(failures)
    write_progress(progress,
                   f"  Stage 4 done: {valid_count}/{len(instances)} truly enhanced, "
                   f"{len(enhanced_rows)} total rows")
    return enhanced_rows


# ── Stage 5: Solver + Evaluation ──────────────────────────────────────────

def run_solver(label: str, dataset_path: Path, solver_dir: Path,
               progress: dict) -> Path:
    """Run mini-SWE-agent solver on a dataset."""
    solver_dir.mkdir(parents=True, exist_ok=True)
    progress["step"] = f"stage5_solver_{label}"
    write_progress(progress, f"STAGE 5: Running solver ({label})...")

    instances = _load_jsonl(dataset_path)
    _write_jsonl(solver_dir / "solver_instances.jsonl",
                 [_solver_ready(r) for r in instances])

    cmd = [
        str(BENCH_ENV_PYTHON), str(SOLVER_SCRIPT),
        "--dataset-jsonl", str(dataset_path),
        "-c", str(SWEBENCH_CONFIG),
        "-c", str(GPT54MINI_OVERRIDE),
        "--output", str(solver_dir),
        "--workers", str(SOLVER_WORKERS),
    ]

    try:
        run_subprocess(cmd, log_path=solver_dir / "minisweagent.log",
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
    """Run gold-patch evaluation."""
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
    empty_patch_ids = []
    error_ids = []

    results_path = eval_dir / "results.json"
    if results_path.exists():
        results = json.loads(results_path.read_text())
        empty_patch_ids = results.get("empty_patch_ids", [])
        error_ids = results.get("error_ids", [])

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
        "empty_patch_ids": sorted(empty_patch_ids),
        "error_ids": sorted(error_ids),
    }
    (eval_dir / "eval_results.json").write_text(json.dumps(result, indent=2))
    write_progress(progress,
                   f"  Eval ({label}): {len(resolved_ids)}/{len(instance_ids)} resolved")
    return result


# ── Stage 6: Report ──────────────────────────────────────────────────────

def generate_report(instances: list[dict], enhanced_rows: list[dict],
                    baseline_result: dict, enhanced_result: dict,
                    progress: dict, is_canary: bool = False) -> None:
    """Generate Stage 6 comparison report."""
    progress["step"] = "stage6_report"
    write_progress(progress, "STAGE 6: Generating comparison report")

    report_dir = RUN_DIR / "stage6_report"
    report_dir.mkdir(parents=True, exist_ok=True)

    all_ids = [r["instance_id"] for r in instances]
    type_map = {r["instance_id"]: r.get("issue_type", "unknown") for r in instances}
    baseline_set = set(baseline_result.get("resolved_ids", []))
    enhanced_set = set(enhanced_result.get("resolved_ids", []))

    # Identify truly-enhanced vs unchanged instances
    truly_enhanced_ids = set()
    unchanged_ids = set()
    for row in enhanced_rows:
        iid = row["instance_id"]
        meta = row.get("enhancement_metadata", {})
        valid = row.get("_enhancement_valid", True)
        if not valid or meta.get("enhancer_type") == "error":
            unchanged_ids.add(iid)
        elif row.get("problem_statement", "") != row.get("original_problem_statement", ""):
            truly_enhanced_ids.add(iid)
        else:
            unchanged_ids.add(iid)

    gained = sorted(enhanced_set - baseline_set)
    lost = sorted(baseline_set - enhanced_set)
    both = sorted(baseline_set & enhanced_set)

    # Per-issue-type breakdown
    per_type: dict[str, dict] = {}
    for t in sorted(set(type_map.values())):
        t_ids = [iid for iid in all_ids if type_map.get(iid) == t]
        per_type[t] = {
            "total": len(t_ids),
            "truly_enhanced": len([iid for iid in t_ids if iid in truly_enhanced_ids]),
            "baseline_resolved": len([iid for iid in t_ids if iid in baseline_set]),
            "enhanced_resolved": len([iid for iid in t_ids if iid in enhanced_set]),
            "baseline_resolved_ids": sorted(iid for iid in t_ids if iid in baseline_set),
            "enhanced_resolved_ids": sorted(iid for iid in t_ids if iid in enhanced_set),
        }

    n = max(len(all_ids), 1)
    summary = {
        "timestamp": _now(),
        "source_dataset": str(STAGE3_EXPORT),
        "total_instances": len(all_ids),
        "is_canary": is_canary,
        "issue_type_counts": _issue_type_counts(instances),
        "enhancer": ENHANCER_ID,
        "enhancer_model": f"{SOLVER_MODEL} via OpenAI",
        "solver": f"mini_swe_agent ({SOLVER_MODEL} via OpenAI)",
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
        "cross_references": {
            "pilot40_llm_append_gpt54mini": {
                "baseline": 9,
                "enhanced": 8,
                "report": "runs/paul_pilot40_stage4_stage6_20260526/stage6_report/summary.json",
            },
            "pilot40_llm_append_gptoss": {
                "baseline": 0,
                "enhanced": 0,
                "report": "runs/paul_pilot40_gptoss_solver_20260527/stage6_report/summary.json",
            },
            "native_20issue_comparison": {
                "baseline": 3,
                "openhands": 2,
                "aider": 3,
                "trae": 2,
                "mini_swe_agent": 2,
                "swe_agent": 1,
                "report": "runs/pouya20_native_solver_comparison_fixed/ANALYSIS.md",
                "note": "Different 20-row dataset, not directly comparable",
            },
        },
    }

    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    # ── Markdown report ──────────────────────────────────────────────────
    bl = baseline_result
    en = enhanced_result
    imp = summary["comparison"]["improvement_pp"]

    canary_note = " (CANARY — 5-row subset)" if is_canary else ""
    lines = [
        f"# Stage 6: Pilot-40 OpenHands Enhancer+Solver Comparison Report{canary_note}",
        "",
        f"**Generated:** {_now()}",
        f"**Source dataset:** `{STAGE3_EXPORT.name}` ({len(all_ids)} instances{canary_note})",
        f"**Issue types:** {summary['issue_type_counts']}",
        f"**Enhancer:** {ENHANCER_ID} ({SOLVER_MODEL} via OpenAI)",
        f"**Solver:** mini-SWE-agent ({SOLVER_MODEL} via OpenAI)",
        "",
        "## Overall Results",
        "",
        "| Condition | Resolved | Total | Rate |",
        "|---|---:|---:|---:|",
        f"| Baseline (original) | {bl['resolved']} | {bl['total']} | {bl['resolved']/n*100:.1f}% |",
        f"| Enhanced ({ENHANCER_ID}) | {en['resolved']} | {en['total']} | {en['resolved']/n*100:.1f}% |",
        "",
        f"**Improvement:** {imp:+.1f} percentage points",
        f"**Gained by enhancement:** {len(gained)} instances ({', '.join(f'`{g}`' for g in gained) or 'none'})",
        f"**Lost by enhancement:** {len(lost)} instances ({', '.join(f'`{l}`' for l in lost) or 'none'})",
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
        f"- Unchanged (error/empty): {len(unchanged_ids)}",
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

    # Cross-references
    lines.extend([
        "## Cross-Reference: Prior Pilot Runs",
        "",
        "### Same 40-row pilot dataset",
        "",
        "| Run | Enhancer | Solver Model | Baseline | Enhanced |",
        "|---|---|---|---:|---:|",
        f"| **This run** | {ENHANCER_ID} | {SOLVER_MODEL} | {bl['resolved']}/40 | {en['resolved']}/40 |",
        "| pilot40 (2026-05-26) | llm_append_analysis | gpt-5.4-mini | 9/40 | 8/40 |",
        "| pilot40 gptoss (2026-05-27) | llm_append_analysis | gpt-oss:120b | 0/40 | 0/40 |",
        "",
        "### Previous 20-row native CLI benchmark (different dataset)",
        "",
        "| Condition | Resolved / 20 |",
        "|---|---:|",
        "| Baseline | 3/20 |",
        "| aider | 3/20 |",
        "| trae | 2/20 |",
        "| openhands | 2/20 |",
        "| mini_swe_agent | 2/20 |",
        "| swe_agent | 1/20 |",
        "",
        "**Note:** The 20-issue native CLI benchmark used a different dataset. "
        "Cross-dataset comparisons are descriptive only, not statistically comparable.",
        "",
        "## Artifacts",
        "",
        f"- Run directory: `{RUN_DIR}`",
        f"- Summary JSON: `{report_dir / 'summary.json'}`",
        f"- Stage 4 enhanced datasets: `{RUN_DIR / 'stage4_enhanced'}`",
        f"- Stage 5 solver outputs: `{RUN_DIR / 'stage5_solver_eval'}`",
        f"- This report: `{report_dir / 'REPORT.md'}`",
    ])

    (report_dir / "REPORT.md").write_text("\n".join(lines) + "\n")
    write_progress(progress, "  Report written to stage6_report/")


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Pilot-40 Stage 4-6 with openhands enhancer")
    parser.add_argument("--resume", action="store_true",
                        help="Skip completed steps (check .done_ markers)")
    parser.add_argument("--canary", type=int, default=0,
                        help="Run on first N rows only (canary mode)")
    args = parser.parse_args()
    resume = args.resume
    canary = args.canary

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load instances ───────────────────────────────────────────────────
    if not STAGE3_EXPORT.exists():
        print(f"ERROR: Stage 3 export not found: {STAGE3_EXPORT}", file=sys.stderr)
        return 1

    all_instances = _load_jsonl(STAGE3_EXPORT)
    assert len(all_instances) == 40, f"Expected 40 rows, got {len(all_instances)}"

    if canary > 0:
        instances = all_instances[:canary]
        print(f"CANARY MODE: using first {canary} of {len(all_instances)} instances")
    else:
        instances = all_instances

    type_counts = _issue_type_counts(instances)
    print(f"Loaded {len(instances)} instances: {type_counts}")

    # Write immutable copy of input
    validated_path = RUN_DIR / "validated_instances.jsonl"
    _write_jsonl(validated_path, instances)

    # Save experiment config
    (RUN_DIR / "experiment_config.json").write_text(json.dumps({
        "source_dataset": str(STAGE3_EXPORT),
        "total_instances_source": len(all_instances),
        "total_instances_used": len(instances),
        "canary_mode": canary > 0,
        "canary_size": canary if canary > 0 else None,
        "issue_type_counts": type_counts,
        "enhancer": ENHANCER_ID,
        "enhancer_model": f"{SOLVER_MODEL} (OpenAI API)",
        "solver": "mini_swe_agent",
        "solver_model": SOLVER_MODEL,
        "solver_backend": "OpenAI API",
        "solver_workers": SOLVER_WORKERS,
        "eval_workers": EVAL_WORKERS,
        "run_dir": str(RUN_DIR),
    }, indent=2))

    progress: dict[str, Any] = {
        "started_at": _now(),
        "total_instances": len(instances),
        "issue_types": type_counts,
        "canary_mode": canary > 0,
    }
    write_progress(progress, f"Experiment started: {len(instances)} instances, "
                   f"enhancer={ENHANCER_ID}, canary={canary > 0}")

    all_ids = [r["instance_id"] for r in instances]

    # ── Stage 4: Enhancement ─────────────────────────────────────────────
    stage4_enhanced_path = RUN_DIR / f"stage4_enhanced/{ENHANCER_ID}.jsonl"
    if resume and _step_done("stage4"):
        write_progress(progress, "STAGE 4: SKIP (already done)")
        enhanced_rows = _load_jsonl(stage4_enhanced_path) if stage4_enhanced_path.exists() else []
    else:
        enhanced_rows = run_stage4_enhancement(instances, progress)
        _mark_done("stage4")

    # ── Stage 5a: Baseline solver ────────────────────────────────────────
    baseline_dataset = RUN_DIR / "stage4_enhanced/baseline.jsonl"
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
    enhanced_ids = [r["instance_id"] for r in enhanced_rows]
    if resume and _step_done("stage5_enhanced_solver"):
        write_progress(progress, "STAGE 5 (enhanced solver): SKIP (already done)")
    else:
        if enhanced_rows:
            run_solver("enhanced", stage4_enhanced_path,
                       enhanced_solver_dir, progress)
        else:
            write_progress(progress, "STAGE 5 (enhanced solver): SKIP (no enhanced instances)")
        _mark_done("stage5_enhanced_solver")

    # ── Stage 5d: Enhanced evaluation ────────────────────────────────────
    eval_enhanced_dir = RUN_DIR / "stage5_solver_eval/eval_enhanced"
    if resume and _step_done("stage5_enhanced_eval"):
        write_progress(progress, "STAGE 5 (enhanced eval): SKIP (already done)")
        if (eval_enhanced_dir / "eval_results.json").exists():
            enhanced_result = json.loads(
                (eval_enhanced_dir / "eval_results.json").read_text())
        else:
            enhanced_result = {"resolved": 0, "total": len(enhanced_ids),
                               "resolved_ids": [], "failed_ids": enhanced_ids}
    else:
        if enhanced_rows:
            enhanced_result = run_evaluation(
                "enhanced", validated_path, enhanced_solver_dir,
                eval_enhanced_dir, enhanced_ids, progress)
        else:
            enhanced_result = {"resolved": 0, "total": 0,
                               "resolved_ids": [], "failed_ids": []}
        _mark_done("stage5_enhanced_eval")

    # ── Stage 5e: P2P-gated re-evaluation (mandatory for pilot40 datasets)
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    from pilot40_reeval_lib import reeval_run as _reeval_run

    write_progress(progress, "STAGE 5e: P2P-gated re-evaluation")
    reeval_results = _reeval_run(RUN_DIR, conditions=["baseline", "enhanced"])
    if "baseline" in reeval_results:
        baseline_result = reeval_results["baseline"]
    if "enhanced" in reeval_results:
        enhanced_result = reeval_results["enhanced"]
    write_progress(progress,
                   f"  Re-eval: baseline {baseline_result['resolved']}/{baseline_result['total']}, "
                   f"enhanced {enhanced_result['resolved']}/{enhanced_result['total']}")

    # ── Stage 6: Report ──────────────────────────────────────────────────
    generate_report(instances, enhanced_rows, baseline_result,
                    enhanced_result, progress, is_canary=(canary > 0))
    _mark_done("stage6")

    progress["step"] = "done"
    progress["finished_at"] = _now()
    write_progress(progress, "ALL STAGES COMPLETE")

    print(f"\nReport: {RUN_DIR / 'stage6_report/REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
