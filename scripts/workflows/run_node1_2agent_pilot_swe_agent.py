#!/usr/bin/env python3
"""
Stage 4-6 pilot: swe_agent as BOTH enhancer AND solver on Node1 all-494 dataset.

Baseline: swe_agent solver on original (unenhanced) instances.
Enhanced: swe_agent solver on swe_agent-enhanced instances.

Batch: node1_2agent_pilot
LLM: gpt-oss:120b via Ollama (http://localhost:11435)
MUST NOT be pooled with batch2, pilot40, wave1-5, or node1_all494 batches.

Usage:
    cd /home/22pf2/BenchmarkLLMAgent
    bench_env/bin/python scripts/workflows/run_node1_2agent_pilot_swe_agent.py
    bench_env/bin/python scripts/workflows/run_node1_2agent_pilot_swe_agent.py --resume
    bench_env/bin/python scripts/workflows/run_node1_2agent_pilot_swe_agent.py --stage4-only
"""
from __future__ import annotations
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Config ────────────────────────────────────────────────────────────────────
ENHANCER_ID      = "swe_agent"
SOLVER_ID        = "swe_agent"
BATCH_LABEL      = "node1_2agent_pilot"
BATCH_ISOLATION_NOTE = "Do not pool with batch2, pilot40, wave1-5, or node1_all494 batches"
SOLVER_MODEL     = "gpt-oss:120b"
SOLVER_BASE_URL  = "http://localhost:11435/v1"
SOLVER_API_KEY   = "ollama"          # Ollama ignores the key
SOLVER_WORKERS   = 4
SOLVER_TIMEOUT   = 43200
EVAL_WORKERS     = 2
EXPECTED_ROWS    = 510
ENHANCER_PARALLEL = 4
ENHANCER_TIMEOUT  = 600

DATASET = Path("/home/22pf2/BenchmarkLLMAgent/data/node1_all494_stage3_merged_20260610.jsonl")
RUN_DIR_FULL = ROOT / "runs/node1_2agent_pilot_swe_agent_20260610"
RUN_DIR: Path = None  # type: ignore[assignment]

PAUL_ENV_PYTHON = Path("/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python")
EVAL_SCRIPT     = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"

# ── Ollama / enhancer env ─────────────────────────────────────────────────────
os.environ["USE_OLLAMA"]          = "1"
os.environ["OLLAMA_MODEL"]        = "gpt-oss:120b"
os.environ["OLLAMA_BASE_URL"]     = "http://localhost:11435"
# sweagent_enhancer reads SWEAGENT_BASE_URL / SWEAGENT_MODEL
os.environ["SWEAGENT_BASE_URL"]   = "http://localhost:11435/v1"
os.environ["SWEAGENT_MODEL"]      = "gpt-oss:120b"

# ── Helpers ───────────────────────────────────────────────────────────────────
def _now(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
def _load_jsonl(p): return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]
def _write_jsonl(p, rows):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        for r in rows: f.write(json.dumps(r, sort_keys=True) + "\n")
def _solver_ready(inst):
    row = dict(inst)
    if row.get("docker_image"): row["image_name"] = row["docker_image"]
    return row
def _issue_type_counts(rows): return dict(Counter(r.get("issue_type","unknown") for r in rows))
def _step_done(name): return (RUN_DIR / f".done_{name}").exists()
def _mark_done(name): (RUN_DIR / f".done_{name}").write_text(_now())

def write_progress(progress, msg):
    progress["last_update"] = _now()
    progress.setdefault("log", []).append(f"{_now()} {msg}")
    (RUN_DIR / "progress.json").write_text(json.dumps(progress, indent=2))
    with open(RUN_DIR / "progress.log", "a") as f: f.write(f"{_now()} {msg}\n")
    print(f"[{_now()}] {msg}", flush=True)

# ── Stage 4 ───────────────────────────────────────────────────────────────────
def run_stage4_enhancement(instances, progress):
    progress["step"] = "stage4_enhancement"
    write_progress(progress, f"STAGE 4: {ENHANCER_ID} enhancement on {len(instances)} instances")
    from src.enhancers.dispatcher import get_enhancer
    enhancer = get_enhancer(ENHANCER_ID)
    if enhancer is None:
        write_progress(progress, f"  ERROR: enhancer '{ENHANCER_ID}' not found"); return []
    enhanced_rows, failures = [], []

    def _enhance_one(inst_with_idx):
        idx, inst = inst_with_idx
        iid = inst["instance_id"]
        original_ps = inst.get("problem_statement", "")
        t0 = time.time()
        try:
            result = enhancer(inst); elapsed = time.time() - t0
            enhanced_body = result.get("enhanced_body","") if isinstance(result,dict) else ""
            meta = result.get("enhancement_metadata",{}) if isinstance(result,dict) else {}
            body_changed = bool(enhanced_body) and enhanced_body.strip() != original_ps.strip()
            is_error = meta.get("enhancer_type") == "error"
            row = dict(inst)
            if body_changed and not is_error:
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
            row = dict(inst); row["_enhancement_valid"] = False
            return idx, iid, row, False, elapsed

    results_map = {}
    with ThreadPoolExecutor(max_workers=ENHANCER_PARALLEL) as pool:
        futs = {pool.submit(_enhance_one, (i, inst)): i for i, inst in enumerate(instances)}
        completed = 0
        for fut in as_completed(futs):
            idx, iid, row, ok, elapsed = fut.result()
            results_map[idx] = (iid, row, ok, elapsed)
            completed += 1
            status = "enhanced" if (ok and row.get("_enhancement_valid")) else "failed/unchanged"
            write_progress(progress, f"  [{completed}/{len(instances)}] {iid} {status} ({elapsed:.0f}s)")

    # Separate truly enhanced vs fallback (returned original unchanged)
    all_rows = []       # ALL rows in original order — enhanced where possible, original where not
    fallback_ids = []
    for i in range(len(instances)):
        iid, row, ok, _ = results_map[i]
        if row.get("_enhancement_valid"):
            row["_fallback_used"] = False
            enhanced_rows.append(row)
        else:
            row["_fallback_used"] = True
            row["_enhancement_valid"] = False
            fallback_ids.append(iid)
            failures.append(iid)
        all_rows.append(row)

    stage4_dir = RUN_DIR / "stage4_enhanced"; stage4_dir.mkdir(parents=True, exist_ok=True)
    # baseline.jsonl = all instances with ORIGINAL text (for baseline solver)
    _write_jsonl(stage4_dir / "baseline.jsonl", [_solver_ready(i) for i in instances])
    # enhanced_all.jsonl = all instances: enhanced text where successful, original where fallback
    # This ensures baseline and enhanced solvers run on the SAME set of instances (fair comparison)
    _write_jsonl(stage4_dir / "enhanced_all.jsonl", [_solver_ready(r) for r in all_rows])
    # enhanced_only.jsonl = only truly enhanced (for subset analysis)
    _write_jsonl(stage4_dir / f"{ENHANCER_ID}.jsonl", [_solver_ready(r) for r in enhanced_rows])
    (stage4_dir / "enhancement_failures.json").write_text(json.dumps(failures, indent=2))
    # Fallback manifest: clearly separates real enhancements from fallback/unchanged
    (stage4_dir / "fallback_manifest.json").write_text(json.dumps({
        "total": len(instances),
        "truly_enhanced": len(enhanced_rows),
        "fallback_count": len(fallback_ids),
        "fallback_ids": sorted(fallback_ids),
        "enhanced_ids": sorted(r["instance_id"] for r in enhanced_rows),
        "note": "fallback_ids used original issue text (enhancement failed/timed out)",
    }, indent=2))
    valid_count = len(enhanced_rows)
    (stage4_dir / "stage4_summary.json").write_text(json.dumps({
        "timestamp": _now(), "enhancer": ENHANCER_ID, "solver_model": SOLVER_MODEL,
        "total_instances": len(instances), "enhanced_count": valid_count,
        "failure_count": len(fallback_ids),
    }, indent=2))
    progress["stage4_truly_enhanced_count"] = valid_count
    write_progress(progress, f"  Stage 4 done: {valid_count}/{len(instances)} truly enhanced, "
                              f"{len(fallback_ids)} fallback (original text)")
    return all_rows

# ── Stage 5 solver (swe_agent) ────────────────────────────────────────────────
def run_solver(label, dataset_path_or_instances, solver_dir, progress):
    solver_dir.mkdir(parents=True, exist_ok=True)
    write_progress(progress, f"STAGE 5: swe_agent solver ({label})...")

    if isinstance(dataset_path_or_instances, Path):
        instances = _load_jsonl(dataset_path_or_instances)
    else:
        instances = list(dataset_path_or_instances)
    instances = [_solver_ready(i) for i in instances]

    preds_out = solver_dir / "preds.json"
    try:
        from src.solvers.swe_agent_solver import run_batch
        run_batch(
            instances,
            SOLVER_API_KEY,
            solver_dir / "work",
            preds_out,
            model=SOLVER_MODEL,
            base_url=SOLVER_BASE_URL,
            max_steps=int(os.environ.get("SWEA_SOLVER_MAX_STEPS", "30")),
            workers=SOLVER_WORKERS,
            timeout=SOLVER_TIMEOUT,
        )
    except Exception as exc:
        write_progress(progress, f"  Solver ({label}) error: {exc}")

    n = len(json.loads(preds_out.read_text())) if preds_out.exists() else 0
    write_progress(progress, f"  Solver ({label}) done: {n} predictions")
    return solver_dir

# ── Stage 5 evaluation ────────────────────────────────────────────────────────
def run_evaluation(label, validated_path, solver_dir, eval_dir, instance_ids, progress):
    import subprocess
    eval_dir.mkdir(parents=True, exist_ok=True)
    write_progress(progress, f"  Evaluating {len(instance_ids)} instances ({label})...")
    preds_file = solver_dir / "preds.json"
    if not preds_file.exists():
        write_progress(progress, f"  SKIP eval ({label}): no preds.json")
        return {"resolved":0,"total":len(instance_ids),"resolved_ids":[],"failed_ids":list(instance_ids)}
    cmd = [str(PAUL_ENV_PYTHON), str(EVAL_SCRIPT),
           "--dataset", str(validated_path),
           "--patch_dir", str(preds_file),
           "--platform", "linux", "--workers", str(EVAL_WORKERS),
           "--output_dir", str(eval_dir), "--overwrite", "1",
           "--instance_ids", *instance_ids]
    log_path = eval_dir / "eval.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log_path, "w") as lf:
            subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, timeout=14400)
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
    result = {"resolved":len(resolved_ids),"total":len(instance_ids),
              "resolved_ids":sorted(resolved_ids),"failed_ids":sorted(failed_ids)}
    (eval_dir / "eval_results.json").write_text(json.dumps(result, indent=2))
    write_progress(progress, f"  Eval ({label}): {len(resolved_ids)}/{len(instance_ids)} resolved")
    return result

# ── Stage 6 ───────────────────────────────────────────────────────────────────
def generate_report(instances, enhanced_rows, baseline_result, enhanced_result, progress):
    write_progress(progress, "STAGE 6: Generating comparison report")
    report_dir = RUN_DIR / "stage6_report"; report_dir.mkdir(parents=True, exist_ok=True)
    all_ids = [r["instance_id"] for r in instances]
    truly_enhanced_ids = {r["instance_id"] for r in enhanced_rows if not r.get("_fallback_used")}
    fallback_ids = sorted(set(all_ids) - truly_enhanced_ids)
    baseline_set = set(baseline_result.get("resolved_ids",[]))
    enhanced_set = set(enhanced_result.get("resolved_ids",[]))
    gained = sorted(enhanced_set - baseline_set)
    lost   = sorted(baseline_set - enhanced_set)
    n = max(baseline_result["total"], 1)
    imp = round((enhanced_result["resolved"] - baseline_result["resolved"]) / n * 100, 2)
    summary = {
        "timestamp": _now(), "batch": BATCH_LABEL,
        "batch_isolation_note": BATCH_ISOLATION_NOTE,
        "source_dataset": str(DATASET),
        "total_instances": len(all_ids),
        "issue_type_counts": _issue_type_counts(instances),
        "enhancer": ENHANCER_ID, "solver": SOLVER_ID, "solver_model": SOLVER_MODEL,
        "solver_backend": f"Ollama {SOLVER_MODEL} at {SOLVER_BASE_URL}",
        "truly_enhanced_count": len(truly_enhanced_ids),
        "fallback_count": len(fallback_ids),
        "fallback_ids": fallback_ids,
        "baseline": {"resolved": baseline_result["resolved"], "total": baseline_result["total"],
                     "rate_pct": round(baseline_result["resolved"]/n*100, 2)},
        "enhanced": {"resolved": enhanced_result["resolved"], "total": enhanced_result["total"],
                     "rate_pct": round(enhanced_result["resolved"]/n*100, 2)},
        "comparison": {"improvement_pp": imp, "gained": gained, "lost": lost},
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    bl, en = baseline_result, enhanced_result
    lines = [
        f"# Stage 6 Report: {BATCH_LABEL} / {ENHANCER_ID} enhancer + {SOLVER_ID} solver",
        f"**Generated:** {_now()}",
        f"**Enhancer:** {ENHANCER_ID}  |  **Solver:** {SOLVER_ID} ({SOLVER_MODEL} via Ollama)",
        f"**Instances:** {len(all_ids)} total  |  **Enhanced:** {len(truly_enhanced_ids)}  |  **Fallback (original):** {len(fallback_ids)}",
        "",
        f"> {BATCH_ISOLATION_NOTE}",
        f"> **Fallback note:** {len(fallback_ids)} issues used original text in the enhanced condition (enhancement failed/timed out). Both conditions solve ALL {len(all_ids)} instances for fair comparison.",
        "",
        "| Condition | Resolved | Total | Rate |","|---|---:|---:|---:|",
        f"| Baseline (no enhancement) | {bl['resolved']} | {bl['total']} | {bl['resolved']/n*100:.1f}% |",
        f"| Enhanced ({ENHANCER_ID}) | {en['resolved']} | {en['total']} | {en['resolved']/n*100:.1f}% |",
        "",
        f"**Improvement:** {imp:+.1f} pp  |  **Gained:** {len(gained)}  |  **Lost:** {len(lost)}",
    ]
    (report_dir / "REPORT.md").write_text("\n".join(lines) + "\n")
    write_progress(progress, f"  Report written. Improvement: {imp:+.1f} pp")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global RUN_DIR
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stage4-only", action="store_true")
    args = parser.parse_args()
    RUN_DIR = RUN_DIR_FULL

    if not DATASET.exists():
        print(f"ERROR: Dataset not found: {DATASET}", file=sys.stderr); return 1
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    all_instances = _load_jsonl(DATASET)
    print(f"{BATCH_LABEL} / enhancer={ENHANCER_ID} / solver={SOLVER_ID} ({len(all_instances)} rows)")
    print(f"Dataset: {DATASET}\nRun dir: {RUN_DIR}")
    print(f"LLM: {SOLVER_MODEL} via Ollama @ {SOLVER_BASE_URL}")

    validated_path = RUN_DIR / "validated_instances.jsonl"
    _write_jsonl(validated_path, all_instances)
    (RUN_DIR / "experiment_config.json").write_text(json.dumps({
        "batch": BATCH_LABEL, "batch_isolation_note": BATCH_ISOLATION_NOTE,
        "source_dataset": str(DATASET), "total_instances": len(all_instances),
        "issue_type_counts": _issue_type_counts(all_instances),
        "enhancer": ENHANCER_ID, "solver": SOLVER_ID,
        "solver_model": SOLVER_MODEL, "solver_backend": f"Ollama @ {SOLVER_BASE_URL}",
        "solver_workers": SOLVER_WORKERS, "eval_workers": EVAL_WORKERS,
        "run_dir": str(RUN_DIR),
    }, indent=2))

    progress: dict[str, Any] = {"started_at": _now(), "batch": BATCH_LABEL,
                                 "total_instances": len(all_instances)}
    write_progress(progress, f"Experiment started: {len(all_instances)} instances, "
                              f"enhancer={ENHANCER_ID} solver={SOLVER_ID}")
    all_ids = [r["instance_id"] for r in all_instances]

    # ── Stage 4 ───────────────────────────────────────────────────────────────
    enhanced_all_resume_path = RUN_DIR / "stage4_enhanced/enhanced_all.jsonl"
    if args.resume and _step_done("stage4"):
        write_progress(progress, "STAGE 4: SKIP (already done)")
        enhanced_rows = _load_jsonl(enhanced_all_resume_path) if enhanced_all_resume_path.exists() else []
    else:
        enhanced_rows = run_stage4_enhancement(all_instances, progress)
        _mark_done("stage4")

    if args.stage4_only:
        _truly = len(enhanced_rows)
        ckpt = {"checkpoint_type":"stage4_only","timestamp":_now(),"stage4_done":True,
                "truly_enhanced":_truly,"total":len(all_instances)}
        (RUN_DIR / "stage4_checkpoint.json").write_text(json.dumps(ckpt, indent=2))
        write_progress(progress, f"STAGE 4 CHECKPOINT: truly_enhanced={_truly}/{len(all_instances)}")
        write_progress(progress, "Stopped after Stage 4. Resume with --resume.")
        progress["finished_at"] = _now()
        (RUN_DIR / "progress.json").write_text(json.dumps(progress, indent=2))
        return 0

    # ── Stage 5a: baseline solver ─────────────────────────────────────────────
    baseline_dataset = RUN_DIR / "stage4_enhanced/baseline.jsonl"
    baseline_solver_dir = RUN_DIR / "stage5_solver_eval/solver_baseline"
    if args.resume and _step_done("stage5_baseline_solver"):
        write_progress(progress, "STAGE 5 (baseline solver): SKIP")
    else:
        run_solver("baseline", baseline_dataset, baseline_solver_dir, progress)
        _mark_done("stage5_baseline_solver")

    # ── Stage 5b: baseline eval ───────────────────────────────────────────────
    eval_baseline_dir = RUN_DIR / "stage5_solver_eval/eval_baseline"
    if args.resume and _step_done("stage5_baseline_eval"):
        write_progress(progress, "STAGE 5 (baseline eval): SKIP")
        _r = eval_baseline_dir / "eval_results.json"
        baseline_result = json.loads(_r.read_text()) if _r.exists() else \
            {"resolved":0,"total":len(all_ids),"resolved_ids":[],"failed_ids":all_ids}
    else:
        baseline_result = run_evaluation("baseline", validated_path, baseline_solver_dir,
                                          eval_baseline_dir, all_ids, progress)
        _mark_done("stage5_baseline_eval")

    # ── Stage 5c: enhanced solver (runs on ALL instances — fair comparison) ──
    # enhanced_all.jsonl has enhanced text where Stage 4 succeeded, original text where fallback.
    # This ensures baseline and enhanced solvers run on the SAME population of instances.
    enhanced_all_path = RUN_DIR / "stage4_enhanced/enhanced_all.jsonl"
    enhanced_solver_dir = RUN_DIR / "stage5_solver_eval/solver_enhanced"
    if args.resume and _step_done("stage5_enhanced_solver"):
        write_progress(progress, "STAGE 5 (enhanced solver): SKIP")
    else:
        run_solver("enhanced", enhanced_all_path, enhanced_solver_dir, progress)
        _mark_done("stage5_enhanced_solver")

    # ── Stage 5d: enhanced eval (ALL instances — same population as baseline) ─
    eval_enhanced_dir = RUN_DIR / "stage5_solver_eval/eval_enhanced"
    if args.resume and _step_done("stage5_enhanced_eval"):
        write_progress(progress, "STAGE 5 (enhanced eval): SKIP")
        _r = eval_enhanced_dir / "eval_results.json"
        enhanced_result = json.loads(_r.read_text()) if _r.exists() else \
            {"resolved":0,"total":len(all_ids),"resolved_ids":[],"failed_ids":all_ids}
    else:
        enhanced_result = run_evaluation("enhanced", validated_path, enhanced_solver_dir,
                                          eval_enhanced_dir, all_ids, progress)
        _mark_done("stage5_enhanced_eval")

    # ── Stage 6 ───────────────────────────────────────────────────────────────
    truly_enhanced = [r for r in enhanced_rows if not r.get("_fallback_used")]
    generate_report(all_instances, truly_enhanced, baseline_result, enhanced_result, progress)
    progress["finished_at"] = _now()
    (RUN_DIR / "progress.json").write_text(json.dumps(progress, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
