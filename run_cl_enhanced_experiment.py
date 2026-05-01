#!/usr/bin/env python3
"""
Standalone step-by-step launcher for cl_enhanced_gemma3 GroupC50 experiment.

Runs each phase independently and writes a progress file so we can track status.
"""

from __future__ import annotations
import json, os, subprocess, sys, time
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
SAMPLES_JSON = ROOT / "data/samples/groupC_swebenchlive_50/groupC_50_samples.json"
SELECTED_IDS = ROOT / "data/samples/groupC_swebenchlive_50/groupC_50_instance_ids.txt"
DATASET_JSONL = ROOT / "data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl"
RESULTS_ROOT = ROOT / "results/groupC50_baseline_vs_enhanced"
ENHANCER_AGENT = "cl_enhanced_gemma3"
OUTPUT_TAG = "native_groupC50_20260404"
EXP_DIR = RESULTS_ROOT / f"{ENHANCER_AGENT}__{OUTPUT_TAG}"
ENHANCEMENT_DIR = EXP_DIR / "enhancements"
LOG_DIR = EXP_DIR / "logs"
PROGRESS_FILE = EXP_DIR / "progress.json"
BENCH_PY = ROOT / "bench_env/bin/python"
BASELINE_SOLVER_DIR = RESULTS_ROOT / "trae__native_groupC50_20260401/baseline_solver_run"

PARALLEL = 2
SOLVER_WORKERS = 4
EVAL_WORKERS = 4
NAMESPACE = "starryzhang"

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def save_progress(phase, status, extra=None):
    p = {"phase": phase, "status": status, "updated_at": datetime.utcnow().isoformat()+"Z"}
    if extra:
        p.update(extra)
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(p, indent=2))

def run(cmd, **kwargs):
    log(f"Running: {' '.join(str(c) for c in cmd[:6])}...")
    result = subprocess.run(cmd, **kwargs)
    return result

log("============================================================")
log("GroupC50 CL-Enhanced Agent Experiment — Standalone Launcher")
log(f"EXP_DIR: {EXP_DIR}")
log("============================================================")

# Load IDs
instance_ids = [l.strip() for l in SELECTED_IDS.read_text().splitlines() if l.strip()][:50]
log(f"Loaded {len(instance_ids)} instance IDs")

EXP_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
ENHANCEMENT_DIR.mkdir(parents=True, exist_ok=True)

# ─── Step 3: Enhancement ────────────────────────────────────────────────────
save_progress("step3_enhancement", "running")
log("\n─── Step 3: Running enhancement ───")
enhance_env = dict(os.environ)
enhance_cmd = [
    str(BENCH_PY),
    str(ROOT / "scripts/enhancers/run_enhancement_benchmark.py"),
    "--agents", ENHANCER_AGENT,
    "--max-issues", "50",
    "--parallel", str(PARALLEL),
    "--samples", str(SAMPLES_JSON),
    "--output-dir", str(ENHANCEMENT_DIR),
]
r3 = run(enhance_cmd, cwd=str(ROOT), env=enhance_env)
if r3.returncode != 0:
    save_progress("step3_enhancement", "FAILED", {"returncode": r3.returncode})
    log(f"Enhancement FAILED with code {r3.returncode}")
    sys.exit(1)

# Count completions
enh_files = list(ENHANCEMENT_DIR.glob("*.json"))
save_progress("step3_enhancement", "done", {"enhancement_count": len(enh_files)})
log(f"Enhancement done: {len(enh_files)} files")

# ─── Step 4: Build enhanced dataset JSONL ───────────────────────────────────
save_progress("step4_build_jsonl", "running")
log("\n─── Step 4: Building enhanced JSONL ───")
SAMPLES = json.loads(SAMPLES_JSON.read_text())
sample_by_id = {s["instance_id"]: s for s in SAMPLES["issues"]}

instances = []
with DATASET_JSONL.open() as f:
    for line in f:
        line = line.strip()
        if line:
            instances.append(json.loads(line))
rows_by_id = {inst["instance_id"]: inst for inst in instances}

ENHANCED_JSONL = EXP_DIR / f"groupC50_enhanced_{ENHANCER_AGENT}.jsonl"
built = 0
errors = []
with ENHANCED_JSONL.open("w") as out_f:
    for iid in instance_ids:
        sample = sample_by_id.get(iid)
        if not sample:
            errors.append(f"sample not found: {iid}")
            continue
        owner = sample["pr_owner"]
        repo = sample["pr_repo"]
        issue_number = sample["issue_number"]
        enh_file = ENHANCEMENT_DIR / f"{ENHANCER_AGENT}__{owner}__{repo}__{issue_number}.json"
        if not enh_file.exists():
            errors.append(f"missing enhancement: {enh_file.name}")
            continue
        enh = json.loads(enh_file.read_text())
        row = dict(rows_by_id[iid])
        enhanced_title = enh.get("enhanced_title", sample.get("title", ""))
        enhanced_body = enh.get("enhanced_body", sample.get("body", ""))
        row["problem_statement"] = f"{enhanced_title.strip()}\n\n{enhanced_body.strip()}".strip()
        row["enhancement_agent"] = ENHANCER_AGENT
        out_f.write(json.dumps(row) + "\n")
        built += 1

save_progress("step4_build_jsonl", "done", {"built": built, "errors": len(errors)})
log(f"JSONL built: {built} rows, {len(errors)} errors")
if errors:
    log(f"  First errors: {errors[:3]}")

if built == 0:
    log("ERROR: No rows built — cannot proceed to solver")
    sys.exit(1)

# ─── Step 5: Enhanced solver ─────────────────────────────────────────────────
save_progress("step5_enhanced_solver", "running")
log("\n─── Step 5: Running enhanced solver ───")
ENHANCED_SOLVER_DIR = EXP_DIR / "enhanced_solver_run"
ENHANCED_SOLVER_DIR.mkdir(parents=True, exist_ok=True)
REPLICATION_DIR = Path("/home/22pf2/SWE-Bench_Replication")
filter_regex = "^(" + "|".join(instance_ids) + ")$"
solver_cmd = [
    str(BENCH_PY),
    str(ROOT / "scripts/solvers/run_mini_sweagent_jsonl.py"),
    "--dataset-jsonl", str(ENHANCED_JSONL),
    "--filter", filter_regex,
    "--workers", str(SOLVER_WORKERS),
    "--redo-existing",
    "--output", str(ENHANCED_SOLVER_DIR),
    "--model-class", "minisweagent.models.litellm_textbased_model.LitellmTextbasedModel",
    "-c", str(REPLICATION_DIR / "mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks.yaml"),
    "-c", str(REPLICATION_DIR / "config/devstral_vllm_override.yaml"),
]
r5 = run(solver_cmd, cwd=str(ROOT))
save_progress("step5_enhanced_solver", "done" if r5.returncode == 0 else "FAILED",
              {"returncode": r5.returncode})
log(f"Enhanced solver done: rc={r5.returncode}")

# ─── Step 6: Evaluate enhanced solver ────────────────────────────────────────
save_progress("step6_evaluation", "running")
log("\n─── Step 6: Evaluating enhanced solver ───")
PREDS_JSON = ENHANCED_SOLVER_DIR / "preds.json"
RUN_ID = f"groupC50_{ENHANCER_AGENT}_{OUTPUT_TAG}".replace("-", "_")
eval_cmd = [
    str(BENCH_PY), "-m", "swebench.harness.run_evaluation",
    "--dataset_name", str(DATASET_JSONL),
    "--predictions_path", str(PREDS_JSON),
    "--instance_ids", *instance_ids,
    "--max_workers", str(EVAL_WORKERS),
    "--timeout", "1800",
    "--run_id", RUN_ID,
    "--namespace", NAMESPACE,
]
if PREDS_JSON.exists():
    r6 = run(eval_cmd, cwd=str(ROOT))
    save_progress("step6_evaluation", "done" if r6.returncode == 0 else "FAILED",
                  {"returncode": r6.returncode})
    log(f"Evaluation done: rc={r6.returncode}")
else:
    log(f"Skipping eval: preds.json not found at {PREDS_JSON}")
    save_progress("step6_evaluation", "skipped", {"reason": "preds.json missing"})

save_progress("all_done", "SUCCESS")
log("\n✅ All steps complete!")
