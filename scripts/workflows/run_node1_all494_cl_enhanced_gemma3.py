#!/usr/bin/env python3
"""
Stage 4-6 driver: openhands enhancer on Node1 all-494 (510-row) P2P>0 merged dataset.

Batch: node1_all494
LLM: gpt-oss:120b via Ollama (http://localhost:11435)
MUST NOT be pooled with batch2, pilot40, wave1, wave2, wave3, or wave4.

Usage:
    cd /home/22pf2/BenchmarkLLMAgent
    bench_env/bin/python scripts/workflows/run_node1_all494_openhands.py --stage4-only
    bench_env/bin/python scripts/workflows/run_node1_all494_openhands.py --resume
"""
from __future__ import annotations
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Config ────────────────────────────────────────────────────────────────────
ENHANCER_ID       = "cl_enhanced_gemma3"
BATCH_LABEL       = "node1_all494"
BATCH_ISOLATION_NOTE = "Do not pool with batch2, pilot40, wave1, wave2, wave3, wave4"
SOLVER_MODEL      = "gpt-oss:120b"
SOLVER_WORKERS    = 4
SOLVER_TIMEOUT    = 43200
EVAL_WORKERS      = 2
EXPECTED_ROWS     = 510   # actual count from merged dataset (spec estimated 494)

STAGE3_EXPORT_SOURCE = Path(
    "/home/22pf2/BenchmarkLLMAgent/data/node1_all494_stage3_merged_20260610.jsonl"
)
DATA_DIR   = ROOT / "data"
DATASET    = STAGE3_EXPORT_SOURCE   # merged dataset IS the dataset
RUN_DIR_FULL = ROOT / f"runs/node1_all494_{ENHANCER_ID}_494_20260610"
RUN_DIR: Path = None  # type: ignore[assignment]

BENCH_ENV_PYTHON = ROOT / "bench_env/bin/python"
PAUL_ENV_PYTHON  = Path("/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python")
SOLVER_SCRIPT    = ROOT / "scripts/solvers/run_mini_sweagent_jsonl.py"
EVAL_SCRIPT      = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"
SWEBENCH_CONFIG  = Path(
    "/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/"
    "config/benchmarks/swebench_backticks.yaml"
)
OLLAMA_OVERRIDE  = ROOT / "configs/p2p_pipeline/ollama_gpt_oss_override.yaml"

EVAL_TIMEOUT     = 14400
ENHANCER_TIMEOUT = 600
ENHANCER_PARALLEL = 4   # concurrent Ollama slots

# ── Ollama env ────────────────────────────────────────────────────────────────
os.environ["USE_OLLAMA"]          = "1"
os.environ["OLLAMA_MODEL"]        = "gpt-oss:120b"
os.environ["OLLAMA_BASE_URL"]     = "http://localhost:11435"
# cl_enhanced_gemma3 subprocess uses CL_GEMMA3_MODEL / CL_GEMMA3_BASE_URL
os.environ["CL_GEMMA3_MODEL"]     = "gpt-oss:120b"
os.environ["CL_GEMMA3_BASE_URL"]  = "http://localhost:11435"

# ── Load .env ─────────────────────────────────────────────────────────────────
_dotenv = ROOT / ".env"
if _dotenv.exists():
    for line in _dotenv.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

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

def run_subprocess(cmd, env=None, log_path=None, timeout=7200):
    merged = dict(os.environ)
    if env: merged.update(env)
    log_file = log_path or Path("/dev/null")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "w") as lf:
        lf.write(f"$ {' '.join(str(c) for c in cmd)}\n\n"); lf.flush()
        proc = subprocess.run(cmd, env=merged, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout)
    return proc.returncode

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

    for i in range(len(instances)):
        iid, row, ok, _ = results_map[i]
        if row.get("_enhancement_valid"):
            enhanced_rows.append(row)
        else:
            failures.append(iid)

    stage4_dir = RUN_DIR / "stage4_enhanced"; stage4_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(stage4_dir / "baseline.jsonl", [_solver_ready(i) for i in instances])
    _write_jsonl(stage4_dir / f"{ENHANCER_ID}.jsonl", [_solver_ready(r) for r in enhanced_rows])
    (stage4_dir / "enhancement_failures.json").write_text(json.dumps(failures, indent=2))
    valid_count = sum(1 for r in enhanced_rows if r.get("_enhancement_valid"))
    (stage4_dir / "stage4_summary.json").write_text(json.dumps({
        "timestamp":_now(),"enhancer":ENHANCER_ID,"solver_model":SOLVER_MODEL,
        "total_instances":len(instances),"enhanced_count":len(enhanced_rows),
        "truly_enhanced_count":valid_count,"failure_count":len(failures),
    }, indent=2))
    progress["stage4_truly_enhanced_count"] = valid_count
    write_progress(progress, f"  Stage 4 done: {valid_count}/{len(instances)} truly enhanced")
    return enhanced_rows

# ── Stage 5 ───────────────────────────────────────────────────────────────────
def run_solver(label, dataset_path, solver_dir, progress):
    solver_dir.mkdir(parents=True, exist_ok=True)
    write_progress(progress, f"STAGE 5: Running solver ({label})...")
    cmd = [str(BENCH_ENV_PYTHON), str(SOLVER_SCRIPT),
           "--dataset-jsonl", str(dataset_path),
           "-c", str(SWEBENCH_CONFIG),
           "-c", str(OLLAMA_OVERRIDE),
           "--output", str(solver_dir),
           "--workers", str(SOLVER_WORKERS)]
    try:
        run_subprocess(cmd, log_path=solver_dir/"minisweagent.log", timeout=SOLVER_TIMEOUT)
    except subprocess.TimeoutExpired:
        write_progress(progress, f"  Solver ({label}) TIMEOUT after {SOLVER_TIMEOUT}s")
    preds_path = solver_dir/"preds.json"
    n = len(json.loads(preds_path.read_text())) if preds_path.exists() else 0
    write_progress(progress, f"  Solver ({label}) done: {n} predictions")
    return solver_dir

def run_evaluation(label, validated_path, solver_dir, eval_dir, instance_ids, progress):
    eval_dir.mkdir(parents=True, exist_ok=True)
    write_progress(progress, f"  Evaluating {len(instance_ids)} instances ({label})...")
    preds_file = solver_dir/"preds.json"
    if not preds_file.exists():
        write_progress(progress, f"  SKIP eval ({label}): no preds.json")
        return {"resolved":0,"total":len(instance_ids),"resolved_ids":[],"failed_ids":instance_ids}
    cmd = [str(PAUL_ENV_PYTHON), str(EVAL_SCRIPT),
           "--dataset", str(validated_path),
           "--patch_dir", str(preds_file),
           "--platform","linux","--workers",str(EVAL_WORKERS),
           "--output_dir",str(eval_dir),"--overwrite","1",
           "--instance_ids",*instance_ids]
    try:
        run_subprocess(cmd, log_path=eval_dir/"eval.log", timeout=EVAL_TIMEOUT)
    except subprocess.TimeoutExpired:
        write_progress(progress, f"  Eval ({label}) TIMEOUT")
    resolved_ids, failed_ids = [], []
    for iid in instance_ids:
        report = eval_dir/iid/"report.json"
        if report.exists():
            r = json.loads(report.read_text())
            (resolved_ids if r.get("resolved") else failed_ids).append(iid)
        else:
            failed_ids.append(iid)
    result = {"resolved":len(resolved_ids),"total":len(instance_ids),
              "resolved_ids":sorted(resolved_ids),"failed_ids":sorted(failed_ids)}
    (eval_dir/"eval_results.json").write_text(json.dumps(result,indent=2))
    write_progress(progress, f"  Eval ({label}): {len(resolved_ids)}/{len(instance_ids)} resolved")
    return result

# ── Stage 6 ───────────────────────────────────────────────────────────────────
def generate_report(instances, enhanced_rows, baseline_result, enhanced_result, progress, not_evaluated=None):
    if not_evaluated is None: not_evaluated = {}
    write_progress(progress, "STAGE 6: Generating comparison report")
    report_dir = RUN_DIR/"stage6_report"; report_dir.mkdir(parents=True, exist_ok=True)
    all_ids = [r["instance_id"] for r in instances]
    type_map = {r["instance_id"]:r.get("issue_type","unknown") for r in instances}
    baseline_set = set(baseline_result.get("resolved_ids",[]))
    enhanced_set = set(enhanced_result.get("resolved_ids",[]))
    not_eval_set = set(not_evaluated.keys())
    evaluated_ids = [iid for iid in all_ids if iid not in not_eval_set]
    truly_enhanced_ids, unchanged_ids = set(), set()
    for row in enhanced_rows:
        iid = row["instance_id"]
        if row.get("_enhancement_valid") and row.get("problem_statement","") != row.get("original_problem_statement",""):
            truly_enhanced_ids.add(iid)
        else:
            unchanged_ids.add(iid)
    gained = sorted(enhanced_set - baseline_set)
    lost = sorted(baseline_set - enhanced_set)
    both = sorted(baseline_set & enhanced_set)
    n = max(len(evaluated_ids), 1)
    summary = {
        "timestamp":_now(),"batch":BATCH_LABEL,
        "batch_isolation_note": BATCH_ISOLATION_NOTE,
        "source_dataset":str(STAGE3_EXPORT_SOURCE),
        "total_instances_in_batch":len(all_ids),"total_evaluated":len(evaluated_ids),
        "issue_type_counts":_issue_type_counts(instances),
        "enhancer":ENHANCER_ID,"solver_model":SOLVER_MODEL,
        "solver_backend":"Ollama gpt-oss:120b at http://localhost:11435",
        "truly_enhanced_count":len(truly_enhanced_ids),"unchanged_count":len(unchanged_ids),
        "baseline":{"resolved":baseline_result["resolved"],"total":baseline_result["total"],
                    "rate_pct":round(baseline_result["resolved"]/n*100,2)},
        "enhanced":{"resolved":enhanced_result["resolved"],"total":enhanced_result["total"],
                    "rate_pct":round(enhanced_result["resolved"]/n*100,2)},
        "comparison":{"improvement_pp":round((enhanced_result["resolved"]-baseline_result["resolved"])/n*100,2),
                      "gained_by_enhancement":gained,"lost_by_enhancement":lost,"resolved_by_both":both},
    }
    (report_dir/"summary.json").write_text(json.dumps(summary,indent=2))
    bl, en = baseline_result, enhanced_result
    imp = summary["comparison"]["improvement_pp"]
    lines = [
        f"# Stage 6 Report: {BATCH_LABEL} / {ENHANCER_ID}",
        f"**Generated:** {_now()}",
        f"**Batch:** {BATCH_LABEL} | **Enhancer:** {ENHANCER_ID} | **Solver:** mini_swe_agent ({SOLVER_MODEL} via Ollama)",
        f"**Instances:** {len(all_ids)} total, {len(evaluated_ids)} evaluated",
        "",
        f"> {BATCH_ISOLATION_NOTE}",
        "",
        "| Condition | Resolved | Total | Rate |","|---|---:|---:|---:|",
        f"| Baseline | {bl['resolved']} | {bl['total']} | {bl['resolved']/n*100:.1f}% |",
        f"| Enhanced ({ENHANCER_ID}) | {en['resolved']} | {en['total']} | {en['resolved']/n*100:.1f}% |",
        "",
        f"**Improvement:** {imp:+.1f} pp | **Gained:** {len(gained)} | **Lost:** {len(lost)}",
    ]
    (report_dir/"REPORT.md").write_text("\n".join(lines)+"\n")
    write_progress(progress, "  Report written to stage6_report/")

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
    print(f"{BATCH_LABEL} / {ENHANCER_ID} ({len(all_instances)} rows)")
    print(f"Dataset: {DATASET}\nRun dir: {RUN_DIR}")
    print(f"LLM: {SOLVER_MODEL} via Ollama @ {os.environ.get('OLLAMA_BASE_URL')}")

    instances = all_instances
    validated_path = RUN_DIR/"validated_instances.jsonl"
    _write_jsonl(validated_path, instances)

    (RUN_DIR/"experiment_config.json").write_text(json.dumps({
        "batch":BATCH_LABEL,"batch_isolation_note":BATCH_ISOLATION_NOTE,
        "source_dataset":str(STAGE3_EXPORT_SOURCE),"total_instances":len(instances),
        "issue_type_counts":_issue_type_counts(instances),
        "enhancer":ENHANCER_ID,"solver_model":SOLVER_MODEL,
        "solver_backend":"Ollama gpt-oss:120b","solver_workers":SOLVER_WORKERS,
        "eval_workers":EVAL_WORKERS,"run_dir":str(RUN_DIR),
    }, indent=2))

    progress: dict[str,Any] = {"started_at":_now(),"batch":BATCH_LABEL,"total_instances":len(instances)}
    write_progress(progress, f"Experiment started: {len(instances)} instances, enhancer={ENHANCER_ID}")
    all_ids = [r["instance_id"] for r in instances]

    # Stage 4
    stage4_enhanced_path = RUN_DIR/f"stage4_enhanced/{ENHANCER_ID}.jsonl"
    if args.resume and _step_done("stage4"):
        write_progress(progress, "STAGE 4: SKIP (already done)")
        enhanced_rows = _load_jsonl(stage4_enhanced_path) if stage4_enhanced_path.exists() else []
    else:
        enhanced_rows = run_stage4_enhancement(instances, progress)
        _mark_done("stage4")

    if args.stage4_only:
        _truly = sum(1 for r in enhanced_rows if r.get("_enhancement_valid"))
        ckpt = {"checkpoint_type":"stage4_only","timestamp":_now(),"stage4_done":True,
                "truly_enhanced":_truly,"total":len(instances)}
        (RUN_DIR/"stage4_checkpoint.json").write_text(json.dumps(ckpt,indent=2))
        write_progress(progress, f"STAGE 4 CHECKPOINT: truly_enhanced={_truly}/{len(instances)}")
        write_progress(progress, "Stopped after Stage 4. Resume with --resume.")
        progress["finished_at"] = _now()
        (RUN_DIR/"progress.json").write_text(json.dumps(progress,indent=2))
        return 0

    not_evaluated: dict[str,str] = {}
    runnable_manifest = RUN_DIR/"runnable_ids.json"
    if runnable_manifest.exists():
        manifest = json.loads(runnable_manifest.read_text())
        confirmed_runnable = manifest.get("confirmed_runnable",[])
        for reason, ids in manifest.get("not_runnable",{}).items():
            for iid in ids: not_evaluated[iid] = reason
        for iid in all_ids:
            if iid not in set(confirmed_runnable)|set(not_evaluated): not_evaluated[iid]="still_pending"
    else:
        confirmed_runnable = list(all_ids)
    runnable_set = set(confirmed_runnable)

    # Stage 5a baseline solver
    baseline_dataset = RUN_DIR/"stage4_enhanced/baseline.jsonl"
    baseline_solver_dir = RUN_DIR/"stage5_solver_eval/solver_baseline"
    if args.resume and _step_done("stage5_baseline_solver"):
        write_progress(progress, "STAGE 5 (baseline solver): SKIP")
    else:
        run_solver("baseline", baseline_dataset, baseline_solver_dir, progress)
        _mark_done("stage5_baseline_solver")

    # Stage 5b baseline eval
    runnable_baseline_ids = [iid for iid in all_ids if iid in runnable_set]
    eval_baseline_dir = RUN_DIR/"stage5_solver_eval/eval_baseline"
    if args.resume and _step_done("stage5_baseline_eval"):
        write_progress(progress, "STAGE 5 (baseline eval): SKIP")
        baseline_result = json.loads((eval_baseline_dir/"eval_results.json").read_text()) if (eval_baseline_dir/"eval_results.json").exists() else {"resolved":0,"total":len(runnable_baseline_ids),"resolved_ids":[],"failed_ids":runnable_baseline_ids}
    else:
        baseline_result = run_evaluation("baseline", validated_path, baseline_solver_dir, eval_baseline_dir, runnable_baseline_ids, progress)
        _mark_done("stage5_baseline_eval")

    # Stage 5c enhanced solver
    enhanced_solver_dir = RUN_DIR/"stage5_solver_eval/solver_enhanced"
    enhanced_ids = [r["instance_id"] for r in enhanced_rows]
    if args.resume and _step_done("stage5_enhanced_solver"):
        write_progress(progress, "STAGE 5 (enhanced solver): SKIP")
    else:
        if enhanced_rows: run_solver("enhanced", stage4_enhanced_path, enhanced_solver_dir, progress)
        else: write_progress(progress, "STAGE 5 (enhanced solver): SKIP (no enhanced instances)")
        _mark_done("stage5_enhanced_solver")

    # Stage 5d enhanced eval
    runnable_enhanced_ids = [iid for iid in enhanced_ids if iid in runnable_set]
    eval_enhanced_dir = RUN_DIR/"stage5_solver_eval/eval_enhanced"
    if args.resume and _step_done("stage5_enhanced_eval"):
        write_progress(progress, "STAGE 5 (enhanced eval): SKIP")
        enhanced_result = json.loads((eval_enhanced_dir/"eval_results.json").read_text()) if (eval_enhanced_dir/"eval_results.json").exists() else {"resolved":0,"total":len(runnable_enhanced_ids),"resolved_ids":[],"failed_ids":runnable_enhanced_ids}
    else:
        if runnable_enhanced_ids: enhanced_result = run_evaluation("enhanced", validated_path, enhanced_solver_dir, eval_enhanced_dir, runnable_enhanced_ids, progress)
        else: enhanced_result = {"resolved":0,"total":0,"resolved_ids":[],"failed_ids":[]}
        _mark_done("stage5_enhanced_eval")

    # Stage 6
    generate_report(instances, enhanced_rows, baseline_result, enhanced_result, progress, not_evaluated)
    _mark_done("stage6")
    progress["step"] = "done"; progress["finished_at"] = _now()
    write_progress(progress, "ALL STAGES COMPLETE")
    print(f"\nReport: {RUN_DIR/'stage6_report/REPORT.md'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
