#!/usr/bin/env python3
"""
Stage 4-6 driver for Node2 — supports all 6 enhancer×solver conditions.

Enhancers: none / openhands / sweagent
Solvers:   openhands / swe_agent

LLM backend: gpt-oss:120b via Ollama (http://localhost:11434)
Dataset:     node2_stage3_p2p878_20260610.jsonl  (878 rows, P2P>0)

Usage:
    cd /home/22pf2/BenchmarkLLMAgent

    # canary (5 instances, no enhancement, openhands solver):
    bench_env/bin/python scripts/workflows/run_node2_condition.py \\
        --enhancer none --solver openhands \\
        --dataset data/node2_canary5_20260610.jsonl \\
        --run-dir runs/node2_canary5_baseline_20260610

    # full baseline:
    bench_env/bin/python scripts/workflows/run_node2_condition.py \\
        --enhancer none --solver openhands \\
        --run-dir runs/node2_baseline_openhands_20260610

    # enhanced:
    bench_env/bin/python scripts/workflows/run_node2_condition.py \\
        --enhancer openhands --solver swe_agent \\
        --run-dir runs/node2_openhands_sweagent_20260610

    # resume after interruption:
    bench_env/bin/python scripts/workflows/run_node2_condition.py \\
        --enhancer openhands --solver openhands \\
        --run-dir runs/node2_openhands_openhands_20260610 --resume

    # stage4 only (no solve/eval):
    bench_env/bin/python scripts/workflows/run_node2_condition.py \\
        --enhancer openhands --solver openhands \\
        --run-dir runs/node2_openhands_openhands_20260610 --stage4-only
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_DATASET = ROOT / "data/node2_stage3_p2p878_20260610.jsonl"
BATCH_LABEL = "node2"
BATCH_ISOLATION_NOTE = "Node2 878-row P2P>0 dataset. Do not pool with Node1 batches."
SOLVER_WORKERS = 2
EVAL_WORKERS = 2
ENHANCER_PARALLEL = 2
ENHANCER_TIMEOUT = 600
SOLVER_TIMEOUT = 43200
EVAL_TIMEOUT = 14400

BENCH_ENV_PYTHON = ROOT / "bench_env/bin/python"
PAUL_ENV_PYTHON = Path("/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python")
EVAL_SCRIPT = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"
SWEBENCH_CONFIG = Path(
    "/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/"
    "config/benchmarks/swebench_backticks.yaml"
)
OLLAMA_OVERRIDE = ROOT / "configs/p2p_pipeline/ollama_gpt_oss_override.yaml"

# Solver scripts
MINI_SWE_SCRIPT = ROOT / "scripts/solvers/run_mini_sweagent_jsonl.py"

# ── GPT-OSS Ollama env ────────────────────────────────────────────────────────
GPT_OSS_ENV = {
    # openhands enhancer
    "OPENHANDS_MODEL": "gpt-oss:120b",
    "OPENHANDS_BASE_URL": "http://localhost:11434/v1",
    "OPENHANDS_API_KEY": "ollama",
    # sweagent enhancer
    "SWEAGENT_MODEL": "gpt-oss:120b",
    "SWEAGENT_BASE_URL": "http://localhost:11434/v1",
    "SWEAGENT_API_KEY": "ollama",
    # openhands solver
    "OH_SOLVER_MODEL": "gpt-oss:120b",
    "OH_SOLVER_BASE_URL": "http://localhost:11434/v1",
    "OH_SOLVER_API_KEY": "ollama",
    # swe_agent solver
    "SWEA_SOLVER_MODEL": "gpt-oss:120b",
    "SWEA_SOLVER_BASE_URL": "http://localhost:11434/v1",
    "SWEA_SOLVER_API_KEY": "ollama",
    # generic fallback
    "OPENAI_API_KEY": "ollama",
    "OPENAI_BASE_URL": "http://localhost:11434/v1",
    "USE_OLLAMA": "1",
    "OLLAMA_MODEL": "gpt-oss:120b",
    "OLLAMA_BASE_URL": "http://localhost:11434",
}

# Apply to process env immediately
os.environ.update(GPT_OSS_ENV)

# ── Load .env (non-override) ──────────────────────────────────────────────────
_dotenv = ROOT / ".env"
if _dotenv.exists():
    for _line in _dotenv.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            k, v = _line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# ── Runtime globals (set in main) ─────────────────────────────────────────────
RUN_DIR: Path = None  # type: ignore[assignment]
ENHANCER_ID: str = None  # type: ignore[assignment]
SOLVER_ID: str = None  # type: ignore[assignment]
DATASET: Path = None  # type: ignore[assignment]

# ── Helpers ───────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def _load_jsonl(p: Path) -> list:
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]

def _write_jsonl(p: Path, rows: list) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")

def _solver_ready(inst: dict) -> dict:
    row = dict(inst)
    if row.get("docker_image"):
        row["image_name"] = row["docker_image"]
    return row

def _issue_type_counts(rows: list) -> dict:
    return dict(Counter(r.get("issue_type", "unknown") for r in rows))

def _step_done(name: str) -> bool:
    return (RUN_DIR / f".done_{name}").exists()

def _mark_done(name: str) -> None:
    (RUN_DIR / f".done_{name}").write_text(_now())

def write_progress(progress: dict, msg: str) -> None:
    progress["last_update"] = _now()
    progress.setdefault("log", []).append(f"{_now()} {msg}")
    (RUN_DIR / "progress.json").write_text(json.dumps(progress, indent=2))
    with open(RUN_DIR / "progress.log", "a") as f:
        f.write(f"{_now()} {msg}\n")
    print(f"[{_now()}] {msg}", flush=True)

def run_subprocess(cmd, log_path=None, timeout=7200) -> int:
    env = dict(os.environ)
    env.update(GPT_OSS_ENV)
    log_file = Path(log_path) if log_path else Path("/dev/null")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "w") as lf:
        lf.write(f"$ {' '.join(str(c) for c in cmd)}\n\n")
        lf.flush()
        proc = subprocess.run(
            cmd, env=env, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout
        )
    return proc.returncode

# ── Stage 4: Enhancement ──────────────────────────────────────────────────────
def run_stage4_enhancement(instances: list, progress: dict) -> list:
    if ENHANCER_ID == "none":
        write_progress(progress, "STAGE 4: no enhancement (baseline condition)")
        stage4_dir = RUN_DIR / "stage4_enhanced"
        stage4_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(stage4_dir / "baseline.jsonl", [_solver_ready(i) for i in instances])
        _write_jsonl(stage4_dir / f"enhanced.jsonl", [])
        (stage4_dir / "stage4_summary.json").write_text(json.dumps({
            "timestamp": _now(), "enhancer": "none", "solver": SOLVER_ID,
            "total_instances": len(instances), "enhanced_count": 0,
            "truly_enhanced_count": 0, "failure_count": 0,
        }, indent=2))
        return []

    write_progress(progress, f"STAGE 4: {ENHANCER_ID} enhancement on {len(instances)} instances")
    from src.enhancers.dispatcher import get_enhancer
    enhancer = get_enhancer(ENHANCER_ID)
    if enhancer is None:
        write_progress(progress, f"  ERROR: enhancer '{ENHANCER_ID}' not found — writing baseline.jsonl only")
        stage4_dir = RUN_DIR / "stage4_enhanced"
        stage4_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(stage4_dir / "baseline.jsonl", [_solver_ready(i) for i in instances])
        _write_jsonl(stage4_dir / "enhanced.jsonl", [])
        return []

    enhanced_rows, results_map = [], {}

    def _enhance_one(inst_with_idx):
        idx, inst = inst_with_idx
        iid = inst["instance_id"]
        original_ps = inst.get("problem_statement", "")
        t0 = time.time()
        try:
            result = enhancer(inst)
            elapsed = time.time() - t0
            enhanced_body = result.get("enhanced_body", "") if isinstance(result, dict) else ""
            meta = result.get("enhancement_metadata", {}) if isinstance(result, dict) else {}
            body_changed = bool(enhanced_body) and enhanced_body.strip() != original_ps.strip()
            is_error = meta.get("enhancer_type") == "error"
            row = dict(inst)
            if body_changed and not is_error:
                row["original_problem_statement"] = original_ps
                row["problem_statement"] = enhanced_body
                row["enhanced_title"] = result.get("enhanced_title")
                row["enhancement_metadata"] = meta
                row["_enhancement_valid"] = True
            else:
                row["enhancement_metadata"] = meta
                row["_enhancement_valid"] = False
            return idx, iid, row, True, elapsed
        except Exception as exc:
            elapsed = time.time() - t0
            row = dict(inst)
            row["_enhancement_valid"] = False
            row["_enhancement_error"] = str(exc)
            return idx, iid, row, False, elapsed

    with ThreadPoolExecutor(max_workers=ENHANCER_PARALLEL) as pool:
        futs = {pool.submit(_enhance_one, (i, inst)): i for i, inst in enumerate(instances)}
        completed = 0
        for fut in as_completed(futs):
            idx, iid, row, ok, elapsed = fut.result()
            results_map[idx] = (iid, row, ok, elapsed)
            completed += 1
            status = "enhanced" if (ok and row.get("_enhancement_valid")) else "failed/unchanged"
            write_progress(progress, f"  [{completed}/{len(instances)}] {iid} {status} ({elapsed:.0f}s)")

    for i in range(len(instances)):
        iid, row, ok, _ = results_map[i]
        if row.get("_enhancement_valid"):
            enhanced_rows.append(row)

    stage4_dir = RUN_DIR / "stage4_enhanced"
    stage4_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(stage4_dir / "baseline.jsonl", [_solver_ready(i) for i in instances])
    _write_jsonl(stage4_dir / "enhanced.jsonl", [_solver_ready(r) for r in enhanced_rows])
    failures = [results_map[i][0] for i in range(len(instances)) if not results_map[i][1].get("_enhancement_valid")]
    (stage4_dir / "enhancement_failures.json").write_text(json.dumps(failures, indent=2))
    truly = len(enhanced_rows)
    (stage4_dir / "stage4_summary.json").write_text(json.dumps({
        "timestamp": _now(), "enhancer": ENHANCER_ID, "solver": SOLVER_ID,
        "total_instances": len(instances), "enhanced_count": truly,
        "truly_enhanced_count": truly, "failure_count": len(failures),
    }, indent=2))
    progress["stage4_truly_enhanced_count"] = truly
    write_progress(progress, f"  Stage 4 done: {truly}/{len(instances)} truly enhanced")
    return enhanced_rows

# ── Stage 5: Solve ─────────────────────────────────────────────────────────────
def run_solver(label: str, dataset_path: Path, solver_dir: Path, progress: dict) -> None:
    solver_dir.mkdir(parents=True, exist_ok=True)
    write_progress(progress, f"STAGE 5: Running {SOLVER_ID} solver ({label}) on {dataset_path.name}...")

    if SOLVER_ID == "openhands":
        _run_openhands_solver(label, dataset_path, solver_dir, progress)
    elif SOLVER_ID == "swe_agent":
        _run_sweagent_solver(label, dataset_path, solver_dir, progress)
    else:
        write_progress(progress, f"  ERROR: unknown solver '{SOLVER_ID}'")
        return

    preds_path = solver_dir / "preds.json"
    n = len(json.loads(preds_path.read_text())) if preds_path.exists() else 0
    write_progress(progress, f"  Solver ({label}) done: {n} predictions")

def _run_openhands_solver(label: str, dataset_path: Path, solver_dir: Path, progress: dict) -> None:
    instances = _load_jsonl(dataset_path)
    from src.solvers.openhands_solver import solve_instance
    preds = []

    def _solve(inst):
        return solve_instance(
            inst,
            api_key=GPT_OSS_ENV["OH_SOLVER_API_KEY"],
            work_dir=solver_dir / inst["instance_id"],
            model=GPT_OSS_ENV["OH_SOLVER_MODEL"],
            base_url=GPT_OSS_ENV["OH_SOLVER_BASE_URL"],
        )

    completed = 0
    solver_errors = []
    with ThreadPoolExecutor(max_workers=SOLVER_WORKERS) as pool:
        futs = {pool.submit(_solve, inst): inst["instance_id"] for inst in instances}
        for fut in as_completed(futs):
            iid = futs[fut]
            try:
                result = fut.result()
                preds.append(result)
                write_progress(progress, f"  [{completed+1}/{len(instances)}] {iid} solved")
            except Exception as exc:
                preds.append({"instance_id": iid, "model_name_or_path": "openhands/gpt-oss",
                               "model_patch": "", "_solver_error": str(exc)})
                solver_errors.append({"instance_id": iid, "error": str(exc)})
                write_progress(progress, f"  [{completed+1}/{len(instances)}] {iid} SOLVER_ERROR: {exc}")
            completed += 1

    if solver_errors:
        (solver_dir / "solver_errors.json").write_text(json.dumps(solver_errors, indent=2))
        write_progress(progress, f"  WARNING: {len(solver_errors)}/{len(instances)} instances had solver exceptions — see solver_errors.json")

    (solver_dir / "preds.json").write_text(json.dumps(preds, indent=2))

def _run_sweagent_solver(label: str, dataset_path: Path, solver_dir: Path, progress: dict) -> None:
    from src.solvers.swe_agent_solver import run_batch
    instances = _load_jsonl(dataset_path)
    preds_out = solver_dir / "preds.json"
    solver_dir.mkdir(parents=True, exist_ok=True)
    preds = run_batch(
        instances,
        api_key=GPT_OSS_ENV["SWEA_SOLVER_API_KEY"],
        work_dir=solver_dir,
        preds_out=preds_out,
        model=GPT_OSS_ENV["SWEA_SOLVER_MODEL"],
        base_url=GPT_OSS_ENV["SWEA_SOLVER_BASE_URL"],
        workers=SOLVER_WORKERS,
    )
    if not preds_out.exists():
        preds_out.write_text(json.dumps(preds if isinstance(preds, list) else [], indent=2))
    write_progress(progress, f"  SWE-agent solver ({label}) done: {len(preds) if preds else 0} predictions")

# ── Stage 5: Evaluate ─────────────────────────────────────────────────────────
def run_evaluation(label: str, validated_path: Path, solver_dir: Path,
                   eval_dir: Path, instance_ids: list, progress: dict) -> dict:
    eval_dir.mkdir(parents=True, exist_ok=True)
    write_progress(progress, f"  Evaluating {len(instance_ids)} instances ({label})...")
    preds_file = solver_dir / "preds.json"
    if not preds_file.exists():
        write_progress(progress, f"  ERROR: eval ({label}) ABORTED — preds.json missing (solver likely crashed entirely)")
        # Write an explicit error marker so the report knows this is not resolved=0 from a working solver
        error_result = {
            "resolved": 0, "total": len(instance_ids), "resolved_ids": [], "failed_ids": instance_ids,
            "_eval_aborted": True, "_reason": "preds.json missing — solver did not produce output",
        }
        (eval_dir / "eval_results.json").write_text(json.dumps(error_result, indent=2))
        return error_result

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
        run_subprocess(cmd, log_path=eval_dir / "eval.log", timeout=EVAL_TIMEOUT)
    except subprocess.TimeoutExpired:
        write_progress(progress, f"  Eval ({label}) TIMEOUT")

    resolved_ids, failed_ids = [], []
    for iid in instance_ids:
        report = eval_dir / iid / "report.json"
        if report.exists():
            r = json.loads(report.read_text())
            (resolved_ids if r.get("resolved") else failed_ids).append(iid)
        else:
            failed_ids.append(iid)

    result = {
        "resolved": len(resolved_ids), "total": len(instance_ids),
        "resolved_ids": sorted(resolved_ids), "failed_ids": sorted(failed_ids),
    }
    (eval_dir / "eval_results.json").write_text(json.dumps(result, indent=2))
    write_progress(progress, f"  Eval ({label}): {len(resolved_ids)}/{len(instance_ids)} resolved")
    return result

# ── Stage 6: Report ────────────────────────────────────────────────────────────
def generate_report(instances: list, enhanced_rows: list,
                    baseline_result: dict, enhanced_result: dict, progress: dict) -> None:
    write_progress(progress, "STAGE 6: Generating comparison report")
    report_dir = RUN_DIR / "stage6_report"
    report_dir.mkdir(parents=True, exist_ok=True)

    all_ids = [r["instance_id"] for r in instances]
    n = max(len(all_ids), 1)
    bl, en = baseline_result, enhanced_result
    gained = sorted(set(en.get("resolved_ids", [])) - set(bl.get("resolved_ids", [])))
    lost = sorted(set(bl.get("resolved_ids", [])) - set(en.get("resolved_ids", [])))

    condition_label = f"{ENHANCER_ID}→{SOLVER_ID}"
    bl_aborted = bl.get("_eval_aborted", False)
    en_aborted = en.get("_eval_aborted", False)
    summary = {
        "timestamp": _now(), "batch": BATCH_LABEL,
        "batch_isolation_note": BATCH_ISOLATION_NOTE,
        "source_dataset": str(DATASET),
        "enhancer": ENHANCER_ID, "solver": SOLVER_ID,
        "solver_model": "gpt-oss:120b",
        "solver_backend": "Ollama gpt-oss:120b at http://localhost:11434",
        "total_instances": len(all_ids),
        "issue_type_counts": _issue_type_counts(instances),
        "truly_enhanced_count": len(enhanced_rows),
        "baseline": {
            "resolved": bl["resolved"], "total": bl["total"],
            "rate_pct": round(bl["resolved"] / n * 100, 2),
            "_eval_aborted": bl_aborted,
        },
        "enhanced": {
            "resolved": en["resolved"], "total": en["total"],
            "rate_pct": round(en["resolved"] / max(en["total"], 1) * 100, 2),
            "_eval_aborted": en_aborted,
        },
        "comparison": {
            "improvement_pp": round((en["resolved"] - bl["resolved"]) / n * 100, 2),
            "gained_by_enhancement": gained,
            "lost_by_enhancement": lost,
            "data_integrity": "INVALID — eval aborted; results are not meaningful" if (bl_aborted or en_aborted) else "OK",
        },
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    imp = summary["comparison"]["improvement_pp"]
    lines = [
        f"# Stage 6 Report: {BATCH_LABEL} / {condition_label}",
        f"**Generated:** {_now()}",
        f"**Condition:** enhancer={ENHANCER_ID}, solver={SOLVER_ID}, model=gpt-oss:120b (Ollama)",
        f"**Instances:** {len(all_ids)} total",
        "",
        f"> {BATCH_ISOLATION_NOTE}",
        "",
        "| Condition | Resolved | Total | Rate |",
        "|---|---:|---:|---:|",
        f"| Baseline (no enhancement) | {bl['resolved']} | {bl['total']} | {bl['resolved']/n*100:.1f}% |" + (" ⚠️ EVAL ABORTED" if bl_aborted else ""),
        f"| Enhanced ({ENHANCER_ID}→{SOLVER_ID}) | {en['resolved']} | {en['total']} | {en['resolved']/max(en['total'],1)*100:.1f}% |" + (" ⚠️ EVAL ABORTED" if en_aborted else ""),
        "",
        f"**Improvement:** {imp:+.1f} pp | **Gained:** {len(gained)} | **Lost:** {len(lost)}",
        ("", "**⚠️ DATA INTEGRITY WARNING: One or more eval runs were aborted (solver crash). Results above are NOT valid.**")[bl_aborted or en_aborted],
    ]
    (report_dir / "REPORT.md").write_text("\n".join(lines) + "\n")
    write_progress(progress, f"  Report written → stage6_report/REPORT.md")

# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> int:
    global RUN_DIR, ENHANCER_ID, SOLVER_ID, DATASET

    parser = argparse.ArgumentParser(description="Node2 Stage 4-6 pipeline driver")
    parser.add_argument("--enhancer", choices=["none", "openhands", "sweagent", "swe_agent"], required=True)
    parser.add_argument("--solver", choices=["openhands", "swe_agent"], required=True)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stage4-only", action="store_true")
    args = parser.parse_args()

    # Normalize: both "sweagent" and "swe_agent" map to "swe_agent" (dispatcher key)
    ENHANCER_ID = "swe_agent" if args.enhancer == "sweagent" else args.enhancer
    SOLVER_ID = args.solver
    DATASET = args.dataset
    RUN_DIR = args.run_dir

    global SOLVER_WORKERS, ENHANCER_PARALLEL
    SOLVER_WORKERS = args.workers
    ENHANCER_PARALLEL = args.workers

    if not DATASET.exists():
        print(f"ERROR: Dataset not found: {DATASET}", file=sys.stderr)
        return 1

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    instances = _load_jsonl(DATASET)
    condition = f"{ENHANCER_ID}→{SOLVER_ID}"

    print(f"Node2 condition: {condition}  ({len(instances)} rows)")
    print(f"Dataset: {DATASET}")
    print(f"Run dir: {RUN_DIR}")
    print(f"LLM: gpt-oss:120b via Ollama @ http://localhost:11434")

    validated_path = RUN_DIR / "validated_instances.jsonl"
    _write_jsonl(validated_path, instances)

    (RUN_DIR / "experiment_config.json").write_text(json.dumps({
        "batch": BATCH_LABEL, "batch_isolation_note": BATCH_ISOLATION_NOTE,
        "condition": condition, "enhancer": ENHANCER_ID, "solver": SOLVER_ID,
        "source_dataset": str(DATASET), "total_instances": len(instances),
        "issue_type_counts": _issue_type_counts(instances),
        "solver_model": "gpt-oss:120b", "solver_backend": "Ollama gpt-oss:120b",
        "solver_workers": SOLVER_WORKERS, "eval_workers": EVAL_WORKERS,
        "run_dir": str(RUN_DIR),
    }, indent=2))

    progress: dict[str, Any] = {
        "started_at": _now(), "batch": BATCH_LABEL,
        "condition": condition, "total_instances": len(instances),
    }
    write_progress(progress, f"Experiment started: {len(instances)} instances, {condition}")
    all_ids = [r["instance_id"] for r in instances]

    # ── Stage 4 ──
    stage4_enhanced_path = RUN_DIR / "stage4_enhanced/enhanced.jsonl"
    if args.resume and _step_done("stage4"):
        write_progress(progress, "STAGE 4: SKIP (already done)")
        enhanced_rows = _load_jsonl(stage4_enhanced_path) if stage4_enhanced_path.exists() else []
    else:
        enhanced_rows = run_stage4_enhancement(instances, progress)
        _mark_done("stage4")

    if args.stage4_only:
        truly = len(enhanced_rows)
        ckpt = {
            "checkpoint_type": "stage4_only", "timestamp": _now(),
            "stage4_done": True, "condition": condition,
            "truly_enhanced": truly, "total": len(instances),
        }
        (RUN_DIR / "stage4_checkpoint.json").write_text(json.dumps(ckpt, indent=2))
        (RUN_DIR / ".done_stage4").write_text(_now())
        write_progress(progress, f"STAGE 4 CHECKPOINT: truly_enhanced={truly}/{len(instances)}")
        write_progress(progress, "Stopped after Stage 4. Resume with --resume.")
        progress["finished_at"] = _now()
        (RUN_DIR / "progress.json").write_text(json.dumps(progress, indent=2))
        return 0

    # ── Stage 5a: baseline solve ──
    baseline_dataset = RUN_DIR / "stage4_enhanced/baseline.jsonl"
    baseline_solver_dir = RUN_DIR / "stage5_solver_eval/solver_baseline"
    if args.resume and _step_done("stage5_baseline_solver"):
        write_progress(progress, "STAGE 5 (baseline solver): SKIP")
    else:
        run_solver("baseline", baseline_dataset, baseline_solver_dir, progress)
        _mark_done("stage5_baseline_solver")

    # ── Stage 5b: baseline eval ──
    eval_baseline_dir = RUN_DIR / "stage5_solver_eval/eval_baseline"
    if args.resume and _step_done("stage5_baseline_eval"):
        write_progress(progress, "STAGE 5 (baseline eval): SKIP")
        _res_f = eval_baseline_dir / "eval_results.json"
        baseline_result = json.loads(_res_f.read_text()) if _res_f.exists() else \
            {"resolved": 0, "total": len(all_ids), "resolved_ids": [], "failed_ids": all_ids}
    else:
        baseline_result = run_evaluation(
            "baseline", validated_path, baseline_solver_dir, eval_baseline_dir, all_ids, progress
        )
        _mark_done("stage5_baseline_eval")

    # ── Stage 5c: enhanced solve (skip for baseline conditions) ──
    enhanced_solver_dir = RUN_DIR / "stage5_solver_eval/solver_enhanced"
    enhanced_ids = [r["instance_id"] for r in enhanced_rows]
    if args.resume and _step_done("stage5_enhanced_solver"):
        write_progress(progress, "STAGE 5 (enhanced solver): SKIP")
    else:
        if enhanced_rows:
            run_solver("enhanced", stage4_enhanced_path, enhanced_solver_dir, progress)
        else:
            write_progress(progress, "STAGE 5 (enhanced solver): SKIP (no enhanced instances)")
        _mark_done("stage5_enhanced_solver")

    # ── Stage 5d: enhanced eval ──
    eval_enhanced_dir = RUN_DIR / "stage5_solver_eval/eval_enhanced"
    if args.resume and _step_done("stage5_enhanced_eval"):
        write_progress(progress, "STAGE 5 (enhanced eval): SKIP")
        _res_f = eval_enhanced_dir / "eval_results.json"
        enhanced_result = json.loads(_res_f.read_text()) if _res_f.exists() else \
            {"resolved": 0, "total": 0, "resolved_ids": [], "failed_ids": []}
    else:
        if enhanced_ids:
            enhanced_result = run_evaluation(
                "enhanced", validated_path, enhanced_solver_dir, eval_enhanced_dir, enhanced_ids, progress
            )
        else:
            enhanced_result = {"resolved": 0, "total": 0, "resolved_ids": [], "failed_ids": []}
        _mark_done("stage5_enhanced_eval")

    # ── Stage 6 ──
    generate_report(instances, enhanced_rows, baseline_result, enhanced_result, progress)
    _mark_done("stage6")
    progress["step"] = "done"
    progress["finished_at"] = _now()
    (RUN_DIR / "progress.json").write_text(json.dumps(progress, indent=2))
    write_progress(progress, "ALL STAGES COMPLETE")

    bl, en = baseline_result, enhanced_result
    n = max(len(all_ids), 1)
    print(f"\n{'='*60}")
    print(f"RESULTS: {condition}  ({BATCH_LABEL})")
    print(f"  Baseline:  {bl['resolved']}/{bl['total']}  ({bl['resolved']/n*100:.1f}%)")
    if enhanced_ids:
        ne = max(en['total'], 1)
        print(f"  Enhanced:  {en['resolved']}/{en['total']}  ({en['resolved']/ne*100:.1f}%)")
        imp = (en['resolved'] - bl['resolved']) / n * 100
        print(f"  Delta:     {imp:+.1f} pp")
    print(f"  Report:    {RUN_DIR / 'stage6_report/REPORT.md'}")
    print(f"{'='*60}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
