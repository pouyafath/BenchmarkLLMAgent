#!/usr/bin/env python3
"""
Stage 4-6 driver for openclaw enhancer on the wave1 20-row P2P>0 subset.

Input:  Pre-filtered Stage 3 P2P>0 subset (20 rows) from wave1 Stage 3 export.
Output: Isolated immutable stage artifacts. MUST NOT be pooled with batch2 or pilot40.

Stages:
  4. Enhancement — openclaw agent (gpt-5.4-mini via OpenAI)
  5. Solver evaluation — mini-SWE-agent on baseline + enhanced conditions
  6. Report — per-issue-type comparison, summary.json, REPORT.md

Usage:
    cd /home/22pf2/BenchmarkLLMAgent
    # Stage 4 only (enhancement, no Docker needed):
    bench_env/bin/python scripts/workflows/run_wave1_openclaw.py --stage4-only
    # Full 20-row run (after Stage 4, once images available):
    bench_env/bin/python scripts/workflows/run_wave1_openclaw.py
    # Resume (skip completed steps):
    bench_env/bin/python scripts/workflows/run_wave1_openclaw.py --resume

Prerequisites:
    The openclaw binary must be available before running.
    Set OPENCLAW_CMD to the absolute path of the binary, or ensure `openclaw`
    is on PATH.  Example:
        export OPENCLAW_CMD=/path/to/openclaw
        export OPENCLAW_API_KEY=$OPENAI_API_KEY   # or set OPENAI_API_KEY
        bench_env/bin/python scripts/workflows/run_wave1_openclaw.py --stage4-only

Batch isolation:
    Results from this batch MUST NOT be pooled numerically with batch2 or pilot40.
    wave1 = 20-row P2P>0 subset from stage3_wave1_p2p_gt0_20.jsonl
    batch2 = 55-row P2P>0 subset from stage3_validation_completed122.jsonl
    pilot40 = 40-row dataset from stage3_validation_completed40.jsonl
    These are different datasets from different Stage 3 exports.
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

STAGE3_EXPORT_SOURCE = Path(
    "/home/22pf2/paul-RepoLaunch/runs/"
    "stage2_2026_node1_wave1_stage3_exports_20260608_1830_utc/"
    "stage3_wave1_p2p_gt0_20.jsonl"
)

DATA_DIR = ROOT / "data"
DATASET_FULL = DATA_DIR / "wave1_stage3_p2p_20_20260608.jsonl"

RUN_DIR_FULL = ROOT / "runs/paul_wave1_openclaw_20_20260608"
RUN_DIR: Path = None  # type: ignore[assignment]

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
SOLVER_TIMEOUT = 14400
EVAL_TIMEOUT = 7200
ENHANCER_TIMEOUT = 600

SOLVER_MODEL = "gpt-5.4-mini"
ENHANCER_ID = "openclaw"
BATCH_LABEL = "wave1"
EXPECTED_ROWS = 20

# ── Load .env ────────────────────────────────────────────────────────────────

_dotenv = ROOT / ".env"
if _dotenv.exists():
    for line in _dotenv.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


# ── Helpers ──────────────────────────────────────────────────────────────────

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


# ── Stage 4: Enhancement ─────────────────────────────────────────────────────

def run_stage4_enhancement(instances: list[dict], progress: dict) -> list[dict]:
    progress["step"] = "stage4_enhancement"
    write_progress(progress,
                   f"STAGE 4: openclaw enhancement on {len(instances)} instances")

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

    _write_jsonl(stage4_dir / "baseline.jsonl",
                 [_solver_ready(inst) for inst in instances])
    _write_jsonl(stage4_dir / f"{ENHANCER_ID}.jsonl",
                 [_solver_ready(r) for r in enhanced_rows])
    (stage4_dir / "enhancement_failures.json").write_text(
        json.dumps(failures, indent=2))

    valid_count = sum(1 for r in enhanced_rows if r.get("_enhancement_valid"))
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


# ── Stage 5: Solver + Evaluation ─────────────────────────────────────────────

def run_solver(label: str, dataset_path: Path, solver_dir: Path,
               progress: dict) -> Path:
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
    write_progress(progress, f"  Solver ({label}) done: {n_preds} predictions")
    return solver_dir


def run_evaluation(label: str, validated_path: Path, solver_dir: Path,
                   eval_dir: Path, instance_ids: list[str],
                   progress: dict) -> dict[str, Any]:
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


# ── Stage 6: Report ───────────────────────────────────────────────────────────

def generate_report(instances: list[dict], enhanced_rows: list[dict],
                    baseline_result: dict, enhanced_result: dict,
                    progress: dict,
                    not_evaluated: dict[str, str] | None = None) -> None:
    """
    not_evaluated: mapping of instance_id -> reason string for rows excluded
    from Stage 5 evaluation (upstream unavailable). Excluded from denominator.
    """
    if not_evaluated is None:
        not_evaluated = {}

    progress["step"] = "stage6_report"
    write_progress(progress, "STAGE 6: Generating comparison report")

    report_dir = RUN_DIR / "stage6_report"
    report_dir.mkdir(parents=True, exist_ok=True)

    all_ids = [r["instance_id"] for r in instances]
    type_map = {r["instance_id"]: r.get("issue_type", "unknown") for r in instances}
    baseline_set = set(baseline_result.get("resolved_ids", []))
    enhanced_set = set(enhanced_result.get("resolved_ids", []))

    not_eval_set = set(not_evaluated.keys())
    evaluated_ids = [iid for iid in all_ids if iid not in not_eval_set]

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

    per_type: dict[str, dict] = {}
    for t in sorted(set(type_map.values())):
        t_ids = [iid for iid in all_ids if type_map.get(iid) == t]
        t_eval_ids = [iid for iid in t_ids if iid not in not_eval_set]
        per_type[t] = {
            "total_in_batch": len(t_ids),
            "evaluated": len(t_eval_ids),
            "not_evaluated": len(t_ids) - len(t_eval_ids),
            "truly_enhanced": len([iid for iid in t_ids if iid in truly_enhanced_ids]),
            "baseline_resolved": len([iid for iid in t_eval_ids if iid in baseline_set]),
            "enhanced_resolved": len([iid for iid in t_eval_ids if iid in enhanced_set]),
            "baseline_resolved_ids": sorted(iid for iid in t_eval_ids if iid in baseline_set),
            "enhanced_resolved_ids": sorted(iid for iid in t_eval_ids if iid in enhanced_set),
        }

    # Denominator = evaluated rows (not full batch)
    n = max(len(evaluated_ids), 1)

    not_eval_by_reason: dict[str, list[str]] = {}
    for iid, reason in sorted(not_evaluated.items()):
        not_eval_by_reason.setdefault(reason, []).append(iid)

    summary = {
        "timestamp": _now(),
        "batch": BATCH_LABEL,
        "batch_isolation_note": (
            "This batch MUST NOT be pooled numerically with batch2 or pilot40. "
            f"wave1=20 P2P>0 rows from stage3_wave1_p2p_gt0_20.jsonl; "
            "batch2=55 P2P>0 rows from stage3_validation_completed122.jsonl; "
            "pilot40=40 rows from stage3_validation_completed40.jsonl."
        ),
        "source_dataset": str(STAGE3_EXPORT_SOURCE),
        "filtered_dataset": str(DATASET_FULL),
        "total_instances_in_batch": len(all_ids),
        "total_evaluated": len(evaluated_ids),
        "total_not_evaluated": len(not_evaluated),
        "denominator_note": (
            f"resolved/total denominators use evaluated subset ({len(evaluated_ids)} rows), "
            f"not full batch ({len(all_ids)} rows). "
            f"{len(not_evaluated)} rows excluded: see not_evaluated block."
        ),
        "issue_type_counts": _issue_type_counts(instances),
        "enhancer": ENHANCER_ID,
        "enhancer_model": f"{SOLVER_MODEL} via OpenAI",
        "solver": f"mini_swe_agent ({SOLVER_MODEL} via OpenAI)",
        "truly_enhanced_count": len(truly_enhanced_ids),
        "unchanged_count": len(unchanged_ids),
        "truly_enhanced_ids": sorted(truly_enhanced_ids),
        "unchanged_ids": sorted(unchanged_ids),
        "not_evaluated": {
            "total": len(not_evaluated),
            "note": (
                "Rows excluded from Stage 5 evaluation due to upstream image "
                "unavailability. Excluded from resolved/total denominators."
            ),
            "by_reason": not_eval_by_reason,
            "per_instance": {iid: reason for iid, reason in sorted(not_evaluated.items())},
        },
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
            "wave1_openhands": {
                "run_dir": "runs/paul_wave1_openhands_20_20260608",
                "report": "runs/paul_wave1_openhands_20_20260608/stage6_report/summary.json",
                "isolation_note": "Same dataset, different enhancer — directly comparable",
            },
            "batch2_openhands": {
                "baseline": 19,
                "enhanced": 21,
                "total_evaluated": 30,
                "total_in_batch": 55,
                "report": "runs/paul_batch2_openhands_55_20260604/stage6_report/summary.json",
                "isolation_note": "Different dataset — not numerically comparable with wave1",
            },
            "pilot40_openhands": {
                "baseline": 9,
                "enhanced": 10,
                "total": 40,
                "report": "runs/paul_pilot40_openhands_20260601/stage6_report/summary.json",
                "isolation_note": "Different dataset — not numerically comparable with wave1",
            },
        },
    }

    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    bl = baseline_result
    en = enhanced_result
    imp = summary["comparison"]["improvement_pp"]
    subset_note = (f" ({len(evaluated_ids)}/{len(all_ids)} evaluated — "
                   f"{len(not_evaluated)} upstream unavailable)"
                   if not_evaluated else "")

    lines = [
        "# Stage 6: Wave1 OpenClaw Enhancer+Solver Comparison Report",
        "",
        f"**Generated:** {_now()}",
        f"**Batch:** wave1 (wave1 Stage 3 export, P2P>0 subset)",
        f"**Source dataset:** `{STAGE3_EXPORT_SOURCE.name}` → P2P>0 filter → {len(all_ids)} instances",
        f"**Evaluated:** {len(evaluated_ids)}/{len(all_ids)} instances{subset_note}",
        f"**Issue types:** {summary['issue_type_counts']}",
        f"**Enhancer:** {ENHANCER_ID} ({SOLVER_MODEL} via OpenAI)",
        f"**Solver:** mini-SWE-agent ({SOLVER_MODEL} via OpenAI)",
        "",
        "> **Batch isolation**: Results in this report are for wave1 only.",
        "> Do NOT pool these numbers with batch2 or pilot40 (different datasets/exports).",
        "",
        "## Overall Results",
        "",
        f"> Denominator = {len(evaluated_ids)} evaluated rows.",
        f"> {len(not_evaluated)} rows excluded from denominator (upstream unavailable — see Not Evaluated section).",
        "",
        "| Condition | Resolved | Evaluated | Rate |",
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
        "| Issue Type | In Batch | Evaluated | Truly Enhanced | Baseline Resolved | Enhanced Resolved |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for t, data in per_type.items():
        lines.append(
            f"| {t} | {data['total_in_batch']} | {data['evaluated']} | "
            f"{data['truly_enhanced']} | "
            f"{data['baseline_resolved']}/{data['evaluated']} | "
            f"{data['enhanced_resolved']}/{data['evaluated']} |"
        )

    te_baseline = len([iid for iid in truly_enhanced_ids if iid in baseline_set])
    te_enhanced = len([iid for iid in truly_enhanced_ids if iid in enhanced_set])
    uc_baseline = len([iid for iid in unchanged_ids if iid in baseline_set])
    uc_enhanced = len([iid for iid in unchanged_ids if iid in enhanced_set])

    lines.extend([
        "",
        "## Enhancement Coverage",
        "",
        f"- Instances in batch: {len(all_ids)}",
        f"- Truly enhanced (body changed): {len(truly_enhanced_ids)}",
        f"- Unchanged (error/empty): {len(unchanged_ids)}",
        "",
        "## Sub-Analysis: Truly Enhanced Only",
        "",
        "| Subset | Count | Baseline Resolved | Enhanced Resolved |",
        "|---|---:|---:|---:|",
        f"| Truly enhanced | {len(truly_enhanced_ids)} | {te_baseline} | {te_enhanced} |",
        f"| Unchanged | {len(unchanged_ids)} | {uc_baseline} | {uc_enhanced} |",
        f"| Total evaluated | {len(evaluated_ids)} | {bl['resolved']} | {en['resolved']} |",
        "",
    ])

    if not_evaluated:
        lines.extend([
            "## Not Evaluated (Upstream Unavailable)",
            "",
            f"**{len(not_evaluated)} rows** were excluded from Stage 5 evaluation and from the "
            "resolved/total denominator. Docker images could not be restored for these instances.",
            "",
            "| Instance ID | Reason |",
            "|---|---|",
        ])
        for reason, ids in sorted(not_eval_by_reason.items()):
            for iid in sorted(ids):
                lines.append(f"| `{iid}` | {reason} |")
        lines.append("")

    lines.extend([
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
        "## Cross-Reference: Prior Runs",
        "",
        "**Note:** wave1_openhands uses the same dataset and is directly comparable.",
        "batch2 and pilot40 use different datasets and are NOT directly comparable.",
        "",
        "| Run | Dataset | Enhancer | Baseline | Enhanced |",
        "|---|---|---|---:|---:|",
        f"| **This run (wave1 openclaw)** | 20-row P2P>0 (wave1), {len(evaluated_ids)} evaluated | {ENHANCER_ID} | {bl['resolved']}/{bl['total']} | {en['resolved']}/{en['total']} |",
        "| wave1 openhands | 20-row P2P>0 (wave1) — same dataset | openhands | TBD | TBD |",
        "| batch2 openhands (2026-06-05) | 55-row P2P>0 (batch123), 30 evaluated | openhands | 19/30 | 21/30 |",
        "| pilot40 openhands (2026-06-01) | 40-row pilot40 | openhands | 9/40 | 10/40 |",
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


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    global RUN_DIR

    import argparse
    parser = argparse.ArgumentParser(
        description="Wave1 Stage 4-6 with openclaw enhancer (20-row P2P>0 subset)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip completed steps (check .done_ markers)")
    parser.add_argument("--stage4-only", action="store_true",
                        help="Run Stage 4 only, then checkpoint and exit. "
                             "Resumable via --resume once Docker images are available.")
    args = parser.parse_args()

    resume = args.resume
    stage4_only = args.stage4_only

    RUN_DIR = RUN_DIR_FULL

    if not STAGE3_EXPORT_SOURCE.exists():
        print(f"ERROR: Stage 3 source export not found: {STAGE3_EXPORT_SOURCE}", file=sys.stderr)
        return 1
    if not DATASET_FULL.exists():
        print(f"ERROR: Dataset not found: {DATASET_FULL}", file=sys.stderr)
        return 1

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    all_instances = _load_jsonl(DATASET_FULL)
    if len(all_instances) != EXPECTED_ROWS:
        print(f"ERROR: Expected {EXPECTED_ROWS} rows, got {len(all_instances)}", file=sys.stderr)
        return 1

    non_p2p = [r["instance_id"] for r in all_instances
               if r.get("stage3_pass_to_pass_observed_count", 0) == 0]
    if non_p2p:
        print(f"ERROR: {len(non_p2p)} instances have P2P observed count == 0: {non_p2p}",
              file=sys.stderr)
        return 1

    type_counts = _issue_type_counts(all_instances)
    docker_count = sum(1 for r in all_instances if r.get("docker_image"))
    print(f"Wave1 FULL ({EXPECTED_ROWS} rows)")
    print(f"Dataset: {DATASET_FULL}")
    print(f"Run dir: {RUN_DIR}")
    print(f"Instances: {len(all_instances)} | types: {type_counts} | docker: {docker_count}/{len(all_instances)}")

    instances = all_instances
    validated_path = RUN_DIR / "validated_instances.jsonl"
    _write_jsonl(validated_path, instances)

    (RUN_DIR / "experiment_config.json").write_text(json.dumps({
        "batch": BATCH_LABEL,
        "batch_isolation_note": "Do not pool numerically with batch2 or pilot40",
        "source_dataset": str(STAGE3_EXPORT_SOURCE),
        "filtered_dataset": str(DATASET_FULL),
        "total_instances_in_p2p_subset": EXPECTED_ROWS,
        "total_instances_used": len(instances),
        "issue_type_counts": type_counts,
        "docker_image_present": docker_count,
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
        "batch": BATCH_LABEL,
        "total_instances": len(instances),
        "issue_types": type_counts,
    }
    write_progress(progress, f"Wave1 experiment started: {len(instances)} instances, "
                   f"enhancer={ENHANCER_ID}")

    all_ids = [r["instance_id"] for r in instances]

    # ── Stage 4: Enhancement ─────────────────────────────────────────────────
    stage4_enhanced_path = RUN_DIR / f"stage4_enhanced/{ENHANCER_ID}.jsonl"
    if resume and _step_done("stage4"):
        write_progress(progress, "STAGE 4: SKIP (already done)")
        enhanced_rows = _load_jsonl(stage4_enhanced_path) if stage4_enhanced_path.exists() else []
    else:
        enhanced_rows = run_stage4_enhancement(instances, progress)
        _mark_done("stage4")

    # ── Stage 4-only checkpoint ───────────────────────────────────────────────
    if stage4_only:
        _docker_result = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True, text=True,
        )
        _available_images = set(_docker_result.stdout.strip().splitlines())
        _docker_ready = []
        _docker_missing = []
        for _r in instances:
            _img = _r.get("docker_image", "") or _r.get("image_name", "")
            if _img in _available_images:
                _docker_ready.append(_r["instance_id"])
            else:
                _docker_missing.append(_r["instance_id"])
        _truly_enhanced = sum(1 for r in enhanced_rows if r.get("_enhancement_valid"))
        _failures = [r for r in enhanced_rows if not r.get("_enhancement_valid")]
        _checkpoint = {
            "checkpoint_type": "stage4_only",
            "timestamp": _now(),
            "stage4_done": True,
            "stage5_blocked": True,
            "stage5_unblock_instruction": (
                "Restore missing pouya/stage2_2026:<id>_linux Docker images, "
                "then rerun with --resume (without --stage4-only) to continue from Stage 5."
            ),
            "enhancement_summary": {
                "total_instances": len(instances),
                "truly_enhanced": _truly_enhanced,
                "failures": len(_failures),
                "failure_ids": [r["instance_id"] for r in _failures],
            },
            "docker_image_status": {
                "ready_for_stage5": len(_docker_ready),
                "blocked_by_missing_image": len(_docker_missing),
                "ready_ids": _docker_ready,
                "missing_ids": _docker_missing,
            },
        }
        _ckpt_path = RUN_DIR / "stage4_checkpoint.json"
        _ckpt_path.write_text(json.dumps(_checkpoint, indent=2))
        write_progress(progress,
                       f"STAGE 4 CHECKPOINT: truly_enhanced={_truly_enhanced}/{len(instances)}, "
                       f"docker_ready={len(_docker_ready)}/{len(instances)}, "
                       f"docker_missing={len(_docker_missing)}/{len(instances)}")
        write_progress(progress, f"  Checkpoint saved: {_ckpt_path}")
        write_progress(progress,
                       "  Run stopped after Stage 4 (--stage4-only). "
                       "Resume with --resume once images are restored.")
        progress["step"] = "stage4_checkpoint"
        progress["finished_at"] = _now()
        (RUN_DIR / "progress.json").write_text(json.dumps(progress, indent=2))
        return 0

    # ── Runnable-subset manifest ──────────────────────────────────────────────
    runnable_manifest_path = RUN_DIR / "runnable_ids.json"
    not_evaluated: dict[str, str] = {}

    if runnable_manifest_path.exists():
        manifest = json.loads(runnable_manifest_path.read_text())
        confirmed_runnable: list[str] = manifest.get("confirmed_runnable", [])
        not_runnable: dict[str, list[str]] = manifest.get("not_runnable", {})
        for reason, ids in not_runnable.items():
            for iid in ids:
                not_evaluated[iid] = reason
        all_ids_set = set(all_ids)
        accounted = set(confirmed_runnable) | set(not_evaluated.keys())
        for iid in all_ids:
            if iid not in accounted:
                not_evaluated[iid] = "still_pending"
        write_progress(progress,
                       f"  Runnable manifest loaded: {len(confirmed_runnable)} confirmed_runnable, "
                       f"{len(not_evaluated)} not_evaluated")
    else:
        confirmed_runnable = list(all_ids)
        write_progress(progress,
                       f"  No runnable_ids.json — evaluating all {len(all_ids)} IDs")

    runnable_eval_set = set(confirmed_runnable)

    # ── Stage 5a: Baseline solver ─────────────────────────────────────────────
    baseline_dataset = RUN_DIR / "stage4_enhanced/baseline.jsonl"
    baseline_solver_dir = RUN_DIR / "stage5_solver_eval/solver_baseline"
    if resume and _step_done("stage5_baseline_solver"):
        write_progress(progress, "STAGE 5 (baseline solver): SKIP (already done)")
    else:
        run_solver("baseline", baseline_dataset, baseline_solver_dir, progress)
        _mark_done("stage5_baseline_solver")

    # ── Stage 5b: Baseline evaluation ────────────────────────────────────────
    runnable_baseline_ids = [iid for iid in all_ids if iid in runnable_eval_set]
    eval_baseline_dir = RUN_DIR / "stage5_solver_eval/eval_baseline"
    if resume and _step_done("stage5_baseline_eval"):
        write_progress(progress, "STAGE 5 (baseline eval): SKIP (already done)")
        if (eval_baseline_dir / "eval_results.json").exists():
            baseline_result = json.loads(
                (eval_baseline_dir / "eval_results.json").read_text())
        else:
            baseline_result = {"resolved": 0, "total": len(runnable_baseline_ids),
                               "resolved_ids": [], "failed_ids": runnable_baseline_ids}
    else:
        baseline_result = run_evaluation(
            "baseline", validated_path, baseline_solver_dir,
            eval_baseline_dir, runnable_baseline_ids, progress)
        _mark_done("stage5_baseline_eval")

    # ── Stage 5c: Enhanced solver ─────────────────────────────────────────────
    enhanced_solver_dir = RUN_DIR / "stage5_solver_eval/solver_enhanced"
    enhanced_ids = [r["instance_id"] for r in enhanced_rows]
    if resume and _step_done("stage5_enhanced_solver"):
        write_progress(progress, "STAGE 5 (enhanced solver): SKIP (already done)")
    else:
        if enhanced_rows:
            run_solver("enhanced", stage4_enhanced_path, enhanced_solver_dir, progress)
        else:
            write_progress(progress, "STAGE 5 (enhanced solver): SKIP (no enhanced instances)")
        _mark_done("stage5_enhanced_solver")

    # ── Stage 5d: Enhanced evaluation ────────────────────────────────────────
    runnable_enhanced_ids = [iid for iid in enhanced_ids if iid in runnable_eval_set]
    eval_enhanced_dir = RUN_DIR / "stage5_solver_eval/eval_enhanced"
    if resume and _step_done("stage5_enhanced_eval"):
        write_progress(progress, "STAGE 5 (enhanced eval): SKIP (already done)")
        if (eval_enhanced_dir / "eval_results.json").exists():
            enhanced_result = json.loads(
                (eval_enhanced_dir / "eval_results.json").read_text())
        else:
            enhanced_result = {"resolved": 0, "total": len(runnable_enhanced_ids),
                               "resolved_ids": [], "failed_ids": runnable_enhanced_ids}
    else:
        if runnable_enhanced_ids:
            enhanced_result = run_evaluation(
                "enhanced", validated_path, enhanced_solver_dir,
                eval_enhanced_dir, runnable_enhanced_ids, progress)
        else:
            enhanced_result = {"resolved": 0, "total": 0,
                               "resolved_ids": [], "failed_ids": []}
        _mark_done("stage5_enhanced_eval")

    # ── Stage 5e: P2P-gated re-evaluation ────────────────────────────────────
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    from pilot40_reeval_lib import reeval_run as _reeval_run

    write_progress(progress, "STAGE 5e: P2P-gated re-evaluation")
    reeval_results = _reeval_run(RUN_DIR, conditions=["baseline", "enhanced"])
    if "baseline" in reeval_results:
        baseline_result = reeval_results["baseline"]
        # Fix total to evaluated count (reeval_run returns total=all_instances)
        baseline_result["total"] = len(runnable_baseline_ids)
    if "enhanced" in reeval_results:
        enhanced_result = reeval_results["enhanced"]
        enhanced_result["total"] = len(runnable_enhanced_ids)
    write_progress(progress,
                   f"  Re-eval: baseline {baseline_result['resolved']}/{baseline_result['total']}, "
                   f"enhanced {enhanced_result['resolved']}/{enhanced_result['total']}")

    # ── Stage 6: Report ───────────────────────────────────────────────────────
    generate_report(instances, enhanced_rows, baseline_result,
                    enhanced_result, progress, not_evaluated=not_evaluated)
    _mark_done("stage6")

    progress["step"] = "done"
    progress["finished_at"] = _now()
    write_progress(progress, "ALL STAGES COMPLETE")

    print(f"\nReport: {RUN_DIR / 'stage6_report/REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
