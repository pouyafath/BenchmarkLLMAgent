#!/usr/bin/env python3
"""
3-issue LIVE validation test with detailed logging.

Tests the FULL pipeline: Stage 4 (enhancement) + Stage 5 (solver baseline + enhanced).
Logs every step in detail: Docker builds, LLM calls, patch extraction, fallback labeling.

Usage:
    cd /home/22pf2/BenchmarkLLMAgent
    bench_env/bin/python scripts/workflows/test_3issue_live.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Config ────────────────────────────────────────────────────────────────────
TEST_IDS = [
    "AstrBotDevs__AstrBot-6065",
    "Azure-Samples__azure-search-openai-demo-2752",
    "DLR-RM__stable-baselines3-2205",
]
SOLVER_MODEL    = "gpt-oss:120b"
SOLVER_BASE_URL = "http://localhost:11435/v1"
SOLVER_API_KEY  = "ollama"
SOLVER_WORKERS  = 1   # sequential for clear logging
SOLVER_TIMEOUT  = 3600
ENHANCER_PARALLEL = 1  # sequential for clear logging

DATASET = ROOT / "data/node1_all494_stage3_merged_20260610.jsonl"
RUN_DIR = ROOT / "runs" / f"test_3issue_live_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

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
    all_ok = True

    # 1. LLM connectivity
    import subprocess
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "30",
             f"{SOLVER_BASE_URL}/chat/completions",
             "-H", "Content-Type: application/json",
             "-d", json.dumps({
                 "model": SOLVER_MODEL,
                 "messages": [{"role": "user", "content": "Say OK"}],
                 "max_tokens": 50, "temperature": 0.3
             })],
            capture_output=True, text=True, timeout=60
        )
        resp = json.loads(r.stdout)
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        log(f"LLM check: model={SOLVER_MODEL} responded: '{content[:50]}' ... OK")
    except Exception as e:
        log(f"LLM check: FAILED — {e}", "ERROR")
        all_ok = False

    # 2. Docker images
    for inst in instances:
        img = inst.get("docker_image", "")
        r = subprocess.run(["docker", "image", "inspect", img, "--format", "{{.Id}}"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            log(f"Docker image: {img[:60]}... OK")
        else:
            log(f"Docker image: {img[:60]}... MISSING", "ERROR")
            all_ok = False

    # 3. Docker disk space
    r = subprocess.run(["df", "-h", "/var/lib/docker"], capture_output=True, text=True)
    for line in r.stdout.strip().split("\n")[1:]:
        parts = line.split()
        if len(parts) >= 5:
            log(f"Disk: {parts[4]} used, {parts[3]} available")
            pct = int(parts[4].replace("%", ""))
            if pct > 90:
                log("Disk usage >90% — Docker builds may fail!", "WARN")

    # 4. Docker daemon
    r = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        log(f"Docker daemon: v{r.stdout.strip()} OK")
    else:
        log("Docker daemon: NOT RUNNING", "ERROR")
        all_ok = False

    # 5. Enhancer available
    from src.enhancers.dispatcher import get_enhancer
    enhancer = get_enhancer("openhands")
    if enhancer:
        log("Enhancer 'openhands': OK")
    else:
        log("Enhancer 'openhands': NOT FOUND", "ERROR")
        all_ok = False

    # 6. Solver importable
    try:
        from src.solvers.openhands_solver import run_batch
        log("Solver 'openhands_solver': OK")
    except Exception as e:
        log(f"Solver 'openhands_solver': IMPORT FAILED — {e}", "ERROR")
        all_ok = False

    return all_ok


# ── Stage 4: Enhancement ─────────────────────────────────────────────────────
def run_stage4(instances):
    log_section("STAGE 4: ENHANCEMENT (openhands)")
    from src.enhancers.dispatcher import get_enhancer
    enhancer = get_enhancer("openhands")

    all_rows = []
    enhanced_rows = []
    fallback_rows = []

    for i, inst in enumerate(instances):
        iid = inst["instance_id"]
        original_ps = inst.get("problem_statement", "")
        log(f"  [{i+1}/{len(instances)}] Enhancing {iid}...")
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
                row["problem_statement"] = enhanced_body
                row["enhanced_title"] = result.get("enhanced_title")
                row["enhancement_metadata"] = meta
                row["_enhancement_valid"] = True
                row["_fallback_used"] = False
                enhanced_rows.append(row)
                log(f"    ENHANCED in {elapsed:.0f}s (body changed: {len(original_ps)} -> {len(enhanced_body)} chars)")
                log(f"    enhancer_type={meta.get('enhancer_type','?')}, parse_source={meta.get('parse_source','?')}")
            else:
                row["enhancement_metadata"] = meta
                row["_enhancement_valid"] = False
                row["_fallback_used"] = True
                fallback_rows.append(row)
                error_msg = meta.get("error", "unknown")
                log(f"    FALLBACK in {elapsed:.0f}s — reason: {error_msg[:100]}", "WARN")
            all_rows.append(row)

        except Exception as exc:
            elapsed = time.time() - t0
            row = dict(inst)
            row["_enhancement_valid"] = False
            row["_fallback_used"] = True
            fallback_rows.append(row)
            all_rows.append(row)
            log(f"    EXCEPTION in {elapsed:.0f}s: {exc}", "ERROR")

    # Write outputs
    stage4_dir = RUN_DIR / "stage4_enhanced"
    stage4_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(stage4_dir / "baseline.jsonl", [_solver_ready(i) for i in instances])
    _write_jsonl(stage4_dir / "enhanced_all.jsonl", [_solver_ready(r) for r in all_rows])
    _write_jsonl(stage4_dir / "openhands.jsonl", [_solver_ready(r) for r in enhanced_rows])

    manifest = {
        "total": len(instances),
        "truly_enhanced": len(enhanced_rows),
        "fallback_count": len(fallback_rows),
        "fallback_ids": sorted(r["instance_id"] for r in fallback_rows),
        "enhanced_ids": sorted(r["instance_id"] for r in enhanced_rows),
    }
    (stage4_dir / "fallback_manifest.json").write_text(json.dumps(manifest, indent=2))

    log(f"  Stage 4 summary: {len(enhanced_rows)} enhanced, {len(fallback_rows)} fallback")
    log(f"  Files written: baseline.jsonl, enhanced_all.jsonl, openhands.jsonl, fallback_manifest.json")
    return all_rows, enhanced_rows, fallback_rows


# ── Stage 5: Solver ──────────────────────────────────────────────────────────
def run_solver(label, instances, solver_dir):
    log_section(f"STAGE 5: SOLVER ({label}) — {len(instances)} instances")
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
    preds = {}
    if preds_out.exists():
        preds = json.loads(preds_out.read_text())

    # Detailed per-instance analysis
    nonempty = 0
    for iid, pred in preds.items():
        patch = pred.get("model_patch", "")
        patch_len = len(patch.strip())
        if patch_len > 0:
            nonempty += 1
            log(f"  {iid}: PATCH ({patch_len} chars, first 80: {patch.strip()[:80]}...)")
        else:
            log(f"  {iid}: EMPTY PATCH", "WARN")
        # Check solver logs for errors
        work_dir = solver_dir / "work" / iid
        for logname in ["openhands.log", "stdout.log"]:
            logpath = work_dir / logname
            if logpath.exists():
                content = logpath.read_text(errors="replace")
                # Check for known error patterns
                if "AgentStuckInLoopError" in content:
                    log(f"    {logname}: AgentStuckInLoopError detected!", "ERROR")
                if "pull access denied" in content:
                    log(f"    {logname}: Docker pull access denied!", "ERROR")
                if "disk full" in content.lower() or "no space left" in content.lower():
                    log(f"    {logname}: Disk space error!", "ERROR")
                if "Connection reset" in content or "Connection refused" in content:
                    log(f"    {logname}: Connection error detected", "WARN")
                if "timeout" in content.lower() and "error" in content.lower():
                    log(f"    {logname}: Timeout error detected", "WARN")

    log(f"  Solver ({label}) done in {elapsed:.0f}s: {nonempty}/{len(preds)} non-empty patches")
    return preds


# ── Validation ───────────────────────────────────────────────────────────────
def validate(instances, all_rows, enhanced_rows, fallback_rows, baseline_preds, enhanced_preds):
    log_section("VALIDATION")
    passed, failed = [], []

    def check(name, ok, detail=""):
        if ok:
            passed.append(name)
            log(f"  PASS: {name}" + (f" — {detail}" if detail else ""))
        else:
            failed.append(name)
            log(f"  FAIL: {name}" + (f" — {detail}" if detail else ""), "ERROR")

    N = len(instances)

    # Core checks
    check("baseline_preds_count", len(baseline_preds) == N,
          f"expected {N}, got {len(baseline_preds)}")
    check("enhanced_preds_count", len(enhanced_preds) == N,
          f"expected {N}, got {len(enhanced_preds)}")

    bl_nonempty = sum(1 for p in baseline_preds.values() if p.get("model_patch", "").strip())
    en_nonempty = sum(1 for p in enhanced_preds.values() if p.get("model_patch", "").strip())
    check("baseline_nonempty_patches", bl_nonempty > 0,
          f"{bl_nonempty}/{len(baseline_preds)}")
    check("enhanced_nonempty_patches", en_nonempty > 0,
          f"{en_nonempty}/{len(enhanced_preds)}")

    # Same population check (CRITICAL — this is what we just fixed)
    bl_ids = set(baseline_preds.keys())
    en_ids = set(enhanced_preds.keys())
    check("same_population", bl_ids == en_ids,
          f"baseline has {len(bl_ids)} ids, enhanced has {len(en_ids)} ids")

    # Fallback labeling
    manifest_path = RUN_DIR / "stage4_enhanced" / "fallback_manifest.json"
    check("fallback_manifest_exists", manifest_path.exists())
    if manifest_path.exists():
        fm = json.loads(manifest_path.read_text())
        check("fallback_counts_add_up",
              fm["truly_enhanced"] + fm["fallback_count"] == N,
              f"{fm['truly_enhanced']} + {fm['fallback_count']} = {fm['truly_enhanced']+fm['fallback_count']}, expected {N}")

    # enhanced_all.jsonl has all rows
    eall_path = RUN_DIR / "stage4_enhanced" / "enhanced_all.jsonl"
    check("enhanced_all_has_all", eall_path.exists())
    if eall_path.exists():
        eall = _load_jsonl(eall_path)
        check("enhanced_all_count", len(eall) == N,
              f"expected {N}, got {len(eall)}")

    # _fallback_used flags
    for row in all_rows:
        if "_fallback_used" not in row:
            check("fallback_flag_present", False, f"{row['instance_id']} missing _fallback_used")
            break
    else:
        check("fallback_flag_present", True, "all rows have _fallback_used field")

    return passed, failed


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    log_section("3-ISSUE LIVE VALIDATION TEST")
    log(f"Run directory: {RUN_DIR}")
    log(f"Test IDs: {TEST_IDS}")
    log(f"LLM: {SOLVER_MODEL} @ {SOLVER_BASE_URL}")

    # Load dataset and select instances
    all_data = _load_jsonl(DATASET)
    id_set = set(TEST_IDS)
    instances = [r for r in all_data if r["instance_id"] in id_set]
    if len(instances) != len(TEST_IDS):
        found = {r["instance_id"] for r in instances}
        missing = id_set - found
        log(f"Missing instance IDs: {missing}", "ERROR")
        return 1
    log(f"Loaded {len(instances)} test instances from {len(all_data)}-row dataset")

    # Pre-flight
    if not preflight_checks(instances):
        log("Pre-flight checks FAILED — aborting", "ERROR")
        return 1
    log("")

    # Stage 4
    all_rows, enhanced_rows, fallback_rows = run_stage4(instances)
    log("")

    # Stage 5a: baseline solver (ALL instances, original text)
    baseline_preds = run_solver(
        "baseline",
        instances,  # original text
        RUN_DIR / "stage5_solver_eval" / "solver_baseline"
    )
    log("")

    # Stage 5b: enhanced solver (ALL instances — enhanced text where available, original where fallback)
    enhanced_preds = run_solver(
        "enhanced",
        all_rows,  # enhanced text where possible, original where fallback
        RUN_DIR / "stage5_solver_eval" / "solver_enhanced"
    )
    log("")

    # Validate
    passed, failed = validate(instances, all_rows, enhanced_rows, fallback_rows,
                              baseline_preds, enhanced_preds)

    # Final summary
    log_section("FINAL RESULT")
    total = len(passed) + len(failed)
    bl_nonempty = sum(1 for p in baseline_preds.values() if p.get("model_patch", "").strip())
    en_nonempty = sum(1 for p in enhanced_preds.values() if p.get("model_patch", "").strip())

    if failed:
        log(f"RESULT: FAIL ({len(passed)}/{total} checks passed)")
        log(f"Failed: {failed}")
    else:
        log(f"RESULT: PASS ({len(passed)}/{total} checks passed)")

    log(f"Baseline: {bl_nonempty}/{len(baseline_preds)} non-empty patches")
    log(f"Enhanced: {en_nonempty}/{len(enhanced_preds)} non-empty patches")
    log(f"Enhancement: {len(enhanced_rows)} truly enhanced, {len(fallback_rows)} fallback")
    log(f"Population: baseline={len(baseline_preds)} ids, enhanced={len(enhanced_preds)} ids (must be equal)")

    (RUN_DIR / "test_result.json").write_text(json.dumps({
        "timestamp": _now(),
        "result": "FAIL" if failed else "PASS",
        "checks_passed": passed,
        "checks_failed": failed,
        "baseline_preds": len(baseline_preds),
        "baseline_nonempty": bl_nonempty,
        "enhanced_preds": len(enhanced_preds),
        "enhanced_nonempty": en_nonempty,
        "truly_enhanced": len(enhanced_rows),
        "fallback": len(fallback_rows),
    }, indent=2))

    log(f"\nFull log: {RUN_DIR / 'test.log'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
