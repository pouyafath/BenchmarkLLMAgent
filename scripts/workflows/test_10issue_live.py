#!/usr/bin/env python3
"""
10-issue LIVE validation test with gpt-oss:120b.

Tests the FULL pipeline: Stage 4 (enhancement) + Stage 5 (solver baseline + enhanced).
Runs 2 parallel enhancers and 2 parallel solvers for speed while still being diagnosable.

Usage:
    cd /home/22pf2/BenchmarkLLMAgent
    bench_env/bin/python scripts/workflows/test_10issue_live.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Config ────────────────────────────────────────────────────────────────────
# 10 instances spread evenly across the 510-row dataset (dataset rows 8,130,168,206,244,311,350,388,429,468)
# Selected from 383/510 instances that have local Docker images available
TEST_IDS = [
    "AstrBotDevs__AstrBot-6065",
    "graphistry__pygraphistry-1386",
    "graphistry__pygraphistry-1182",
    "graphistry__pygraphistry-1442",
    "ipython__ipython-15027",
    "aws-powertools__powertools-lambda-python-8092",
    "conan-io__conan-18429",
    "darkoperator__dnsrecon-507",
    "docling-project__docling-2011",
    "feast-dev__feast-5454",
]
SOLVER_MODEL    = "gpt-oss:120b"
SOLVER_BASE_URL = "http://localhost:11435/v1"
SOLVER_API_KEY  = "ollama"
SOLVER_WORKERS  = 2    # 2 parallel for speed
SOLVER_TIMEOUT  = 3600
ENHANCER_PARALLEL = 2  # 2 parallel for speed

DATASET = ROOT / "data/node1_all494_stage3_merged_20260610.jsonl"
RUN_DIR = ROOT / "runs" / f"test_10issue_live_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# ── Env vars ──────────────────────────────────────────────────────────────────
os.environ["USE_OLLAMA"]         = "1"
os.environ["OLLAMA_MODEL"]       = "gpt-oss:120b"
os.environ["OLLAMA_BASE_URL"]    = "http://localhost:11435"
os.environ["OPENHANDS_BASE_URL"] = "http://localhost:11435/v1"
os.environ["OPENHANDS_MODEL"]    = "gpt-oss:120b"

# ── Helpers ───────────────────────────────────────────────────────────────────
def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def _load_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]

def _write_jsonl(p, rows):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")

def _solver_ready(inst):
    row = dict(inst)
    if row.get("docker_image"):
        row["image_name"] = row["docker_image"]
    return row

def log(msg, level="INFO"):
    ts = _now()
    line = f"[{ts}] [{level}] {msg}"
    print(line, flush=True)
    with open(RUN_DIR / "test.log", "a") as f:
        f.write(line + "\n")

def log_section(title):
    log("=" * 70)
    log(f"  {title}")
    log("=" * 70)


# ── Pre-flight checks ────────────────────────────────────────────────────────
def preflight_checks(instances):
    log_section("PRE-FLIGHT CHECKS")
    import subprocess
    all_ok = True

    # 1. LLM connectivity + tool calling
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "60",
             f"{SOLVER_BASE_URL}/chat/completions",
             "-H", "Content-Type: application/json",
             "-d", json.dumps({
                 "model": SOLVER_MODEL,
                 "messages": [{"role": "user", "content": "Say OK"}],
                 "max_tokens": 256, "temperature": 0.3,
             })],
            capture_output=True, text=True, timeout=90
        )
        resp = json.loads(r.stdout)
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
        tokens = resp.get("usage", {}).get("total_tokens", "?")
        if content.strip():
            log(f"LLM check: {SOLVER_MODEL} responded '{content[:40]}' ({tokens} tokens) ... OK")
        else:
            log(f"LLM check: {SOLVER_MODEL} returned EMPTY response (0 tokens) — model may be broken!", "ERROR")
            all_ok = False
    except Exception as e:
        log(f"LLM check: FAILED — {e}", "ERROR")
        all_ok = False

    # 2. Docker images
    missing_images = []
    for inst in instances:
        img = inst.get("docker_image", "")
        r = subprocess.run(["docker", "image", "inspect", img, "--format", "{{.Id}}"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            log(f"Docker image: {img[:65]}... OK")
        else:
            log(f"Docker image: {img[:65]}... MISSING", "ERROR")
            missing_images.append(img)
            all_ok = False
    if missing_images:
        log(f"  {len(missing_images)} Docker images missing — cannot proceed", "ERROR")

    # 3. Disk space
    r = subprocess.run(["df", "-h", "/var/lib/docker"], capture_output=True, text=True)
    for line in r.stdout.strip().split("\n")[1:]:
        parts = line.split()
        if len(parts) >= 5:
            pct = int(parts[4].replace("%", ""))
            log(f"Disk: {parts[4]} used, {parts[3]} available" +
                (" ⚠ >90%!" if pct > 90 else ""))
            if pct > 95:
                log("Disk >95% — Docker builds will likely fail!", "ERROR")
                all_ok = False

    # 4. Docker daemon
    r = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                       capture_output=True, text=True)
    log(f"Docker daemon: v{r.stdout.strip()} OK" if r.returncode == 0
        else "Docker daemon: NOT RUNNING", "INFO" if r.returncode == 0 else "ERROR")
    if r.returncode != 0:
        all_ok = False

    # 5. GPU status
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10
        )
        for line in r.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 4:
                used_mb = int(parts[1].split()[0])
                total_mb = int(parts[2].split()[0])
                util = parts[3]
                log(f"GPU {parts[0]}: {used_mb/1024:.0f}/{total_mb/1024:.0f} GB used, util={util}")
    except Exception:
        log("GPU status: nvidia-smi unavailable", "WARN")

    # 6. Enhancer + solver importable
    try:
        from src.enhancers.dispatcher import get_enhancer
        enhancer = get_enhancer("openhands")
        log(f"Enhancer 'openhands': {'OK' if enhancer else 'NOT FOUND'}")
        if not enhancer:
            all_ok = False
    except Exception as e:
        log(f"Enhancer 'openhands': IMPORT FAILED — {e}", "ERROR")
        all_ok = False

    try:
        from src.solvers.openhands_solver import run_batch
        log("Solver 'openhands_solver': OK")
    except Exception as e:
        log(f"Solver 'openhands_solver': IMPORT FAILED — {e}", "ERROR")
        all_ok = False

    return all_ok


# ── Stage 4: Enhancement ─────────────────────────────────────────────────────
def run_stage4(instances):
    log_section(f"STAGE 4: ENHANCEMENT (openhands) — {len(instances)} instances, {ENHANCER_PARALLEL} parallel")
    from src.enhancers.dispatcher import get_enhancer
    from concurrent.futures import ThreadPoolExecutor, as_completed
    enhancer = get_enhancer("openhands")

    all_rows_map = {}  # iid -> row
    enhanced_rows = []
    fallback_rows = []
    results_ordered = []

    def _enhance(inst):
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
            return inst, result, elapsed, body_changed and not is_error
        except Exception as exc:
            return inst, {"enhancement_metadata": {"error": str(exc), "enhancer_type": "error"}}, time.time() - t0, False

    with ThreadPoolExecutor(max_workers=ENHANCER_PARALLEL) as pool:
        futures = {pool.submit(_enhance, inst): inst for inst in instances}
        done_map = {}
        for fut in as_completed(futures):
            inst, result, elapsed, is_enhanced = fut.result()
            done_map[inst["instance_id"]] = (inst, result, elapsed, is_enhanced)

    # Process in original order
    for inst in instances:
        iid = inst["instance_id"]
        original_ps = inst.get("problem_statement", "")
        inst, result, elapsed, is_enhanced = done_map[iid]
        meta = result.get("enhancement_metadata", {}) if isinstance(result, dict) else {}
        enhanced_body = result.get("enhanced_body", "") if isinstance(result, dict) else ""

        row = dict(inst)
        if is_enhanced:
            row["problem_statement"] = enhanced_body
            row["enhanced_title"] = result.get("enhanced_title")
            row["enhancement_metadata"] = meta
            row["_enhancement_valid"] = True
            row["_fallback_used"] = False
            enhanced_rows.append(row)
            log(f"  [{len(enhanced_rows)+len(fallback_rows)}/{len(instances)}] {iid}: ENHANCED in {elapsed:.0f}s "
                f"({len(original_ps)} -> {len(enhanced_body)} chars, "
                f"type={meta.get('enhancer_type','?')}, src={meta.get('parse_source','?')})")
        else:
            row["enhancement_metadata"] = meta
            row["_enhancement_valid"] = False
            row["_fallback_used"] = True
            fallback_rows.append(row)
            error_msg = meta.get("error", "unknown")[:100]
            log(f"  [{len(enhanced_rows)+len(fallback_rows)}/{len(instances)}] {iid}: FALLBACK in {elapsed:.0f}s — {error_msg}", "WARN")
        all_rows_map[iid] = row

    # Preserve original order
    all_rows = [all_rows_map[inst["instance_id"]] for inst in instances]

    # Write outputs
    stage4_dir = RUN_DIR / "stage4_enhanced"
    stage4_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(stage4_dir / "baseline.jsonl",     [_solver_ready(i) for i in instances])
    _write_jsonl(stage4_dir / "enhanced_all.jsonl", [_solver_ready(r) for r in all_rows])
    _write_jsonl(stage4_dir / "openhands.jsonl",    [_solver_ready(r) for r in enhanced_rows])
    manifest = {
        "total": len(instances),
        "truly_enhanced": len(enhanced_rows),
        "fallback_count": len(fallback_rows),
        "fallback_ids":  sorted(r["instance_id"] for r in fallback_rows),
        "enhanced_ids":  sorted(r["instance_id"] for r in enhanced_rows),
    }
    (stage4_dir / "fallback_manifest.json").write_text(json.dumps(manifest, indent=2))

    log(f"  Stage 4 summary: {len(enhanced_rows)}/{len(instances)} truly enhanced, "
        f"{len(fallback_rows)} fallback")
    return all_rows, enhanced_rows, fallback_rows


# ── Stage 5: Solver ──────────────────────────────────────────────────────────
def run_solver(label, instances, solver_dir):
    log_section(f"STAGE 5: SOLVER ({label}) — {len(instances)} instances, {SOLVER_WORKERS} parallel")
    solver_dir.mkdir(parents=True, exist_ok=True)
    instances = [_solver_ready(i) for i in instances]
    preds_out = solver_dir / "preds.json"

    from src.solvers.openhands_solver import run_batch
    t0 = time.time()
    try:
        run_batch(
            instances,
            SOLVER_API_KEY,
            solver_dir / "work",
            preds_out,
            model=SOLVER_MODEL,
            base_url=SOLVER_BASE_URL,
            max_iter=int(os.environ.get("OH_SOLVER_MAX_ITER", "30")),
            workers=SOLVER_WORKERS,
            timeout=SOLVER_TIMEOUT,
        )
    except Exception as exc:
        log(f"  Solver ({label}) error: {exc}", "ERROR")

    elapsed = time.time() - t0
    preds = json.loads(preds_out.read_text()) if preds_out.exists() else {}

    # Per-instance report
    nonempty = 0
    for iid, pred in sorted(preds.items()):
        patch = pred.get("model_patch", "") or ""
        patch_len = len(patch.strip())
        if patch_len > 0:
            nonempty += 1
            log(f"  {iid}: PATCH ({patch_len} chars)")
        else:
            log(f"  {iid}: EMPTY PATCH", "WARN")
        # Check for known errors in logs
        work_dir = solver_dir / "work" / iid
        for logname in ["openhands.log", "stdout.log"]:
            logpath = work_dir / logname
            if logpath.exists():
                content = logpath.read_text(errors="replace")
                if "AgentStuckInLoopError" in content:
                    log(f"    {logname}: AgentStuckInLoopError!", "ERROR")
                if "pull access denied" in content:
                    log(f"    {logname}: Docker pull denied!", "ERROR")
                if "no space left" in content.lower() or "disk full" in content.lower():
                    log(f"    {logname}: Disk full!", "ERROR")
                if "reached maximum iteration" in content:
                    log(f"    {logname}: Max iterations reached (30) — normal for hard instances", "WARN")

    log(f"  Solver ({label}) done in {elapsed:.0f}s: {nonempty}/{len(preds)} non-empty patches")
    return preds


# ── Validation ───────────────────────────────────────────────────────────────
def validate(instances, all_rows, enhanced_rows, fallback_rows, baseline_preds, enhanced_preds):
    log_section("VALIDATION CHECKS")
    passed, failed = [], []

    def check(name, ok, detail=""):
        if ok:
            passed.append(name)
            log(f"  PASS: {name}" + (f" — {detail}" if detail else ""))
        else:
            failed.append(name)
            log(f"  FAIL: {name}" + (f" — {detail}" if detail else ""), "ERROR")

    N = len(instances)

    check("baseline_preds_count",  len(baseline_preds) == N,
          f"expected {N}, got {len(baseline_preds)}")
    check("enhanced_preds_count",  len(enhanced_preds) == N,
          f"expected {N}, got {len(enhanced_preds)}")

    bl_nonempty = sum(1 for p in baseline_preds.values() if (p.get("model_patch","") or "").strip())
    en_nonempty = sum(1 for p in enhanced_preds.values() if (p.get("model_patch","") or "").strip())
    check("baseline_has_nonempty_patches", bl_nonempty > 0, f"{bl_nonempty}/{N}")
    check("enhanced_has_nonempty_patches", en_nonempty > 0, f"{en_nonempty}/{N}")

    bl_ids = set(baseline_preds.keys())
    en_ids = set(enhanced_preds.keys())
    check("same_population_both_solvers", bl_ids == en_ids,
          f"baseline={len(bl_ids)} enhanced={len(en_ids)} — fair comparison requires equal sets")

    check("no_AgentStuckInLoopError", True)  # updated below
    for label, preds, solver_dir in [
        ("baseline", baseline_preds, RUN_DIR / "stage5_solver_eval" / "solver_baseline"),
        ("enhanced", enhanced_preds, RUN_DIR / "stage5_solver_eval" / "solver_enhanced"),
    ]:
        for iid in preds:
            logpath = solver_dir / "work" / iid / "openhands.log"
            if logpath.exists() and "AgentStuckInLoopError" in logpath.read_text(errors="replace"):
                failed.append("no_AgentStuckInLoopError")
                log(f"  FAIL: no_AgentStuckInLoopError — {label}/{iid}", "ERROR")
                break

    manifest_path = RUN_DIR / "stage4_enhanced" / "fallback_manifest.json"
    check("fallback_manifest_exists", manifest_path.exists())
    if manifest_path.exists():
        fm = json.loads(manifest_path.read_text())
        total_check = fm["truly_enhanced"] + fm["fallback_count"]
        check("fallback_counts_correct", total_check == N,
              f"{fm['truly_enhanced']} enhanced + {fm['fallback_count']} fallback = {total_check}, expected {N}")

    eall_path = RUN_DIR / "stage4_enhanced" / "enhanced_all.jsonl"
    check("enhanced_all_written", eall_path.exists())
    if eall_path.exists():
        eall = _load_jsonl(eall_path)
        check("enhanced_all_count", len(eall) == N, f"expected {N}, got {len(eall)}")

    for row in all_rows:
        if "_fallback_used" not in row:
            check("fallback_flag_on_all_rows", False,
                  f"row {row['instance_id']} missing _fallback_used field")
            break
    else:
        check("fallback_flag_on_all_rows", True, "all rows have _fallback_used field")

    return passed, failed, bl_nonempty, en_nonempty


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    N = len(TEST_IDS)

    log_section(f"10-ISSUE LIVE VALIDATION TEST (gpt-oss:120b)")
    log(f"Run directory: {RUN_DIR}")
    log(f"LLM: {SOLVER_MODEL} @ {SOLVER_BASE_URL}")
    log(f"Instances ({N}): {TEST_IDS}")

    # Load dataset
    all_data = _load_jsonl(DATASET)
    id_set = set(TEST_IDS)
    instances = [r for r in all_data if r["instance_id"] in id_set]
    if len(instances) != N:
        missing = id_set - {r["instance_id"] for r in instances}
        log(f"Missing IDs in dataset: {missing}", "ERROR")
        return 1
    # Preserve TEST_IDS order
    inst_map = {r["instance_id"]: r for r in instances}
    instances = [inst_map[iid] for iid in TEST_IDS]
    log(f"Loaded {N} instances from {len(all_data)}-row dataset")

    # Pre-flight
    if not preflight_checks(instances):
        log("Pre-flight FAILED — aborting", "ERROR")
        return 1
    log("")

    # Stage 4
    all_rows, enhanced_rows, fallback_rows = run_stage4(instances)
    log("")

    # Stage 5 baseline
    baseline_preds = run_solver(
        "baseline",
        instances,
        RUN_DIR / "stage5_solver_eval" / "solver_baseline",
    )
    log("")

    # Stage 5 enhanced
    enhanced_preds = run_solver(
        "enhanced",
        all_rows,
        RUN_DIR / "stage5_solver_eval" / "solver_enhanced",
    )
    log("")

    # Validate
    passed, failed, bl_nonempty, en_nonempty = validate(
        instances, all_rows, enhanced_rows, fallback_rows,
        baseline_preds, enhanced_preds,
    )

    # Final report
    log_section("FINAL RESULT")
    total_checks = len(passed) + len(failed)

    log(f"RESULT: {'PASS' if not failed else 'FAIL'} ({len(passed)}/{total_checks} checks passed)")
    if failed:
        log(f"  Failed checks: {failed}", "ERROR")
    log(f"Enhancement:      {len(enhanced_rows)}/{N} truly enhanced, {len(fallback_rows)}/{N} fallback")
    log(f"Baseline patches: {bl_nonempty}/{N} non-empty")
    log(f"Enhanced patches: {en_nonempty}/{N} non-empty")
    log(f"Population parity: baseline={len(baseline_preds)} enhanced={len(enhanced_preds)} "
        f"({'OK' if set(baseline_preds)==set(enhanced_preds) else 'MISMATCH!'})")
    log(f"Full log: {RUN_DIR / 'test.log'}")

    (RUN_DIR / "test_result.json").write_text(json.dumps({
        "timestamp": _now(),
        "model": SOLVER_MODEL,
        "result": "FAIL" if failed else "PASS",
        "checks_passed": passed,
        "checks_failed": failed,
        "n_instances": N,
        "truly_enhanced": len(enhanced_rows),
        "fallback": len(fallback_rows),
        "baseline_nonempty": bl_nonempty,
        "enhanced_nonempty": en_nonempty,
    }, indent=2))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
