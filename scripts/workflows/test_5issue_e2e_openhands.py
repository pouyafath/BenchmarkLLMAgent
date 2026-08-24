#!/usr/bin/env python3
"""
5-issue end-to-end test: validates the full Stage 4-5 pipeline with openhands.

PURPOSE: Verify that solver fixes (Docker BuildKit=0, config.toml fixes) produce
non-empty patches, and that fallback labeling works correctly.

This script:
  1. Selects 5 instances from the node1 510-row dataset
  2. Stage 4: Enhances them with openhands enhancer
  3. Stage 5a: Runs openhands solver on ORIGINAL (baseline) issues
  4. Stage 5b: Runs openhands solver on ENHANCED issues
  5. Validates: non-empty patches, fallback labels, file outputs
  6. Prints a PASS/FAIL summary

Eval (Stage 5 eval + Stage 6 report) is skipped — this tests the solver fix only.

Usage:
    cd /home/22pf2/BenchmarkLLMAgent
    bench_env/bin/python scripts/workflows/test_5issue_e2e_openhands.py

    # Skip Stage 4 enhancement (solver-only test — faster):
    bench_env/bin/python scripts/workflows/test_5issue_e2e_openhands.py --solver-only

    # Use specific instance IDs:
    bench_env/bin/python scripts/workflows/test_5issue_e2e_openhands.py --ids "id1,id2,id3"
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
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Config ────────────────────────────────────────────────────────────────────
SOLVER_MODEL    = "gpt-oss:120b"
SOLVER_BASE_URL = "http://localhost:11435/v1"
SOLVER_API_KEY  = "ollama"
SOLVER_WORKERS  = 2           # keep low for test
SOLVER_TIMEOUT  = 7200        # 2h total for 5 instances
ENHANCER_PARALLEL = 2
N_TEST_ISSUES   = 5

DATASET = Path("/home/22pf2/BenchmarkLLMAgent/data/node1_all494_stage3_merged_20260610.jsonl")
RUN_DIR = ROOT / "runs" / f"test_5issue_e2e_openhands_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

PAUL_ENV_PYTHON = Path("/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python3.12")

# ── Env vars for Ollama routing ──────────────────────────────────────────────
os.environ["USE_OLLAMA"]         = "1"
os.environ["OLLAMA_MODEL"]       = "gpt-oss:120b"
os.environ["OLLAMA_BASE_URL"]    = "http://localhost:11435"
os.environ["OPENHANDS_BASE_URL"] = "http://localhost:11435/v1"
os.environ["OPENHANDS_MODEL"]    = "gpt-oss:120b"

# ── Helpers ──────────────────────────────────────────────────────────────────
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

def log(msg):
    ts = _now()
    print(f"[{ts}] {msg}", flush=True)
    with open(RUN_DIR / "test.log", "a") as f:
        f.write(f"[{ts}] {msg}\n")


def select_instances(all_instances, n, specific_ids=None):
    """Select n instances. If specific_ids given, use those. Otherwise pick evenly spaced."""
    if specific_ids:
        id_set = set(specific_ids)
        selected = [i for i in all_instances if i["instance_id"] in id_set]
        if len(selected) < len(specific_ids):
            missing = id_set - {i["instance_id"] for i in selected}
            log(f"WARNING: {len(missing)} requested IDs not found: {missing}")
        return selected

    # Pick evenly spaced instances for diversity
    step = max(1, len(all_instances) // n)
    selected = []
    for i in range(0, len(all_instances), step):
        selected.append(all_instances[i])
        if len(selected) >= n:
            break
    return selected[:n]


# ── Stage 4: Enhancement ─────────────────────────────────────────────────────
def run_stage4(instances):
    log(f"STAGE 4: openhands enhancement on {len(instances)} instances")
    from src.enhancers.dispatcher import get_enhancer
    enhancer = get_enhancer("openhands")
    if enhancer is None:
        log("ERROR: openhands enhancer not found!")
        return [], instances  # all fallback

    enhanced_rows = []
    fallback_rows = []

    def _enhance_one(inst):
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
                row["problem_statement"] = enhanced_body
                row["enhanced_title"] = result.get("enhanced_title")
                row["enhancement_metadata"] = meta
                row["_enhancement_valid"] = True
                row["_fallback_used"] = False
            else:
                row["enhancement_metadata"] = meta
                row["_enhancement_valid"] = False
                row["_fallback_used"] = True
            return iid, row, elapsed
        except Exception as exc:
            elapsed = time.time() - t0
            log(f"  Enhancement error for {iid}: {exc}")
            row = dict(inst)
            row["_enhancement_valid"] = False
            row["_fallback_used"] = True
            return iid, row, elapsed

    with ThreadPoolExecutor(max_workers=ENHANCER_PARALLEL) as pool:
        futs = {pool.submit(_enhance_one, inst): inst["instance_id"] for inst in instances}
        for fut in as_completed(futs):
            iid, row, elapsed = fut.result()
            if row.get("_enhancement_valid"):
                enhanced_rows.append(row)
                log(f"  {iid}: ENHANCED ({elapsed:.0f}s)")
            else:
                fallback_rows.append(row)
                log(f"  {iid}: FALLBACK ({elapsed:.0f}s)")

    # Write outputs
    stage4_dir = RUN_DIR / "stage4_enhanced"
    stage4_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(stage4_dir / "baseline.jsonl", [_solver_ready(i) for i in instances])
    _write_jsonl(stage4_dir / "openhands.jsonl", [_solver_ready(r) for r in enhanced_rows])
    (stage4_dir / "fallback_manifest.json").write_text(json.dumps({
        "total": len(instances),
        "truly_enhanced": len(enhanced_rows),
        "fallback_count": len(fallback_rows),
        "fallback_ids": sorted(r["instance_id"] for r in fallback_rows),
        "enhanced_ids": sorted(r["instance_id"] for r in enhanced_rows),
        "note": "fallback_ids used original issue text (enhancement failed/timed out)",
    }, indent=2))

    log(f"  Stage 4 done: {len(enhanced_rows)} enhanced, {len(fallback_rows)} fallback")
    return enhanced_rows, fallback_rows


# ── Stage 5: Solver ──────────────────────────────────────────────────────────
def run_solver(label, instances, solver_dir):
    solver_dir.mkdir(parents=True, exist_ok=True)
    log(f"STAGE 5 ({label}): openhands solver on {len(instances)} instances")

    instances = [_solver_ready(i) for i in instances]
    preds_out = solver_dir / "preds.json"

    try:
        from src.solvers.openhands_solver import run_batch
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
        log(f"  Solver ({label}) error: {exc}")

    if preds_out.exists():
        preds = json.loads(preds_out.read_text())
        log(f"  Solver ({label}) done: {len(preds)} predictions")
        return preds
    else:
        log(f"  Solver ({label}): NO preds.json produced!")
        return {}


# ── Validation ───────────────────────────────────────────────────────────────
def validate_results(
    all_instances, enhanced_rows, fallback_rows,
    baseline_preds, enhanced_preds, solver_only
):
    """Run validation checks and return (passed, failed) lists."""
    checks_passed = []
    checks_failed = []

    def check(name, condition, detail=""):
        if condition:
            checks_passed.append(name)
            log(f"  PASS: {name}" + (f" ({detail})" if detail else ""))
        else:
            checks_failed.append(name)
            log(f"  FAIL: {name}" + (f" ({detail})" if detail else ""))

    log("=" * 60)
    log("VALIDATION CHECKS")
    log("=" * 60)

    # --- Solver fix validation (most critical) ---
    check(
        "baseline_preds_exist",
        len(baseline_preds) > 0,
        f"{len(baseline_preds)} predictions"
    )
    check(
        "baseline_preds_count_matches",
        len(baseline_preds) == len(all_instances),
        f"expected {len(all_instances)}, got {len(baseline_preds)}"
    )

    # Check for non-empty patches (THE critical Docker fix test)
    bl_nonempty = sum(1 for p in baseline_preds.values() if p.get("model_patch", "").strip())
    check(
        "baseline_has_nonempty_patches",
        bl_nonempty > 0,
        f"{bl_nonempty}/{len(baseline_preds)} have non-empty patches"
    )

    # Check model_name_or_path
    for iid, pred in baseline_preds.items():
        if "openhands-codeact" not in pred.get("model_name_or_path", ""):
            check("baseline_model_name", False, f"{iid} has wrong model: {pred.get('model_name_or_path')}")
            break
    else:
        check("baseline_model_name", True, "all have openhands-codeact prefix")

    if not solver_only:
        # --- Stage 4 fallback labeling ---
        fallback_manifest = RUN_DIR / "stage4_enhanced" / "fallback_manifest.json"
        check("fallback_manifest_exists", fallback_manifest.exists())

        if fallback_manifest.exists():
            fm = json.loads(fallback_manifest.read_text())
            check(
                "fallback_manifest_counts",
                fm["total"] == len(all_instances),
                f"total={fm['total']}, truly_enhanced={fm['truly_enhanced']}, fallback={fm['fallback_count']}"
            )
            check(
                "fallback_ids_match",
                set(fm["fallback_ids"]) == {r["instance_id"] for r in fallback_rows},
                f"manifest fallback={len(fm['fallback_ids'])}, actual fallback={len(fallback_rows)}"
            )
            check(
                "enhanced_ids_match",
                set(fm["enhanced_ids"]) == {r["instance_id"] for r in enhanced_rows},
                f"manifest enhanced={len(fm['enhanced_ids'])}, actual enhanced={len(enhanced_rows)}"
            )

        # --- Enhanced solver checks ---
        if enhanced_rows:
            check(
                "enhanced_preds_exist",
                len(enhanced_preds) > 0,
                f"{len(enhanced_preds)} predictions"
            )
            en_nonempty = sum(1 for p in enhanced_preds.values() if p.get("model_patch", "").strip())
            check(
                "enhanced_has_nonempty_patches",
                en_nonempty > 0,
                f"{en_nonempty}/{len(enhanced_preds)} have non-empty patches"
            )
        else:
            log("  SKIP: enhanced solver checks (all instances fell back)")

        # --- _fallback_used field ---
        for row in enhanced_rows:
            if row.get("_fallback_used") is not False:
                check("enhanced_rows_no_fallback_flag", False, f"{row['instance_id']} has _fallback_used != False")
                break
        else:
            check("enhanced_rows_no_fallback_flag", True, "all enhanced rows have _fallback_used=False")

        for row in fallback_rows:
            if row.get("_fallback_used") is not True:
                check("fallback_rows_have_flag", False, f"{row['instance_id']} has _fallback_used != True")
                break
        else:
            check("fallback_rows_have_flag", True, "all fallback rows have _fallback_used=True")

    # --- Output files ---
    baseline_jsonl = RUN_DIR / "stage4_enhanced" / "baseline.jsonl"
    if not solver_only:
        check("baseline_jsonl_exists", baseline_jsonl.exists())
        enhanced_jsonl = RUN_DIR / "stage4_enhanced" / "openhands.jsonl"
        check("enhanced_jsonl_exists", enhanced_jsonl.exists())

    return checks_passed, checks_failed


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="5-issue end-to-end test for openhands pipeline")
    parser.add_argument("--solver-only", action="store_true",
                        help="Skip Stage 4 enhancement, test solver only")
    parser.add_argument("--ids", type=str, default="",
                        help="Comma-separated instance IDs to use")
    parser.add_argument("--n", type=int, default=N_TEST_ISSUES,
                        help="Number of test instances (default: 5)")
    args = parser.parse_args()

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    if not DATASET.exists():
        print(f"ERROR: Dataset not found: {DATASET}", file=sys.stderr)
        return 1

    all_data = _load_jsonl(DATASET)
    log(f"Loaded {len(all_data)} instances from {DATASET}")

    # Select test instances
    specific_ids = [x.strip() for x in args.ids.split(",") if x.strip()] if args.ids else None
    instances = select_instances(all_data, args.n, specific_ids)
    log(f"Selected {len(instances)} test instances:")
    for inst in instances:
        img = inst.get("docker_image", "")
        log(f"  {inst['instance_id']}  docker_image={img[:60]}...")

    # Save test config
    (RUN_DIR / "test_config.json").write_text(json.dumps({
        "timestamp": _now(),
        "test_type": "5-issue end-to-end",
        "solver_only": args.solver_only,
        "n_instances": len(instances),
        "instance_ids": [i["instance_id"] for i in instances],
        "solver_model": SOLVER_MODEL,
        "solver_base_url": SOLVER_BASE_URL,
        "solver_workers": SOLVER_WORKERS,
    }, indent=2))

    enhanced_rows = []
    fallback_rows = []

    # ── Stage 4 ───────────────────────────────────────────────────────────
    if args.solver_only:
        log("STAGE 4: SKIPPED (--solver-only mode)")
        # Write baseline.jsonl for solver
        stage4_dir = RUN_DIR / "stage4_enhanced"
        stage4_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(stage4_dir / "baseline.jsonl", [_solver_ready(i) for i in instances])
    else:
        enhanced_rows, fallback_rows = run_stage4(instances)

    # ── Stage 5a: baseline solver ─────────────────────────────────────────
    baseline_solver_dir = RUN_DIR / "stage5_solver_eval" / "solver_baseline"
    baseline_preds = run_solver("baseline", instances, baseline_solver_dir)

    # ── Stage 5b: enhanced solver ─────────────────────────────────────────
    enhanced_preds = {}
    if not args.solver_only and enhanced_rows:
        enhanced_solver_dir = RUN_DIR / "stage5_solver_eval" / "solver_enhanced"
        enhanced_preds = run_solver("enhanced", enhanced_rows, enhanced_solver_dir)
    elif args.solver_only:
        log("STAGE 5 (enhanced): SKIPPED (--solver-only mode)")
    else:
        log("STAGE 5 (enhanced): SKIPPED (no enhanced instances)")

    # ── Validation ────────────────────────────────────────────────────────
    passed, failed = validate_results(
        instances, enhanced_rows, fallback_rows,
        baseline_preds, enhanced_preds, args.solver_only
    )

    # ── Summary ───────────────────────────────────────────────────────────
    log("")
    log("=" * 60)
    total = len(passed) + len(failed)
    if failed:
        log(f"RESULT: FAIL  ({len(passed)}/{total} checks passed)")
        log(f"Failed checks: {failed}")
    else:
        log(f"RESULT: PASS  ({len(passed)}/{total} checks passed)")
    log("=" * 60)

    # Patch summary
    bl_nonempty = sum(1 for p in baseline_preds.values() if p.get("model_patch", "").strip())
    log(f"Baseline patches: {bl_nonempty}/{len(baseline_preds)} non-empty")
    if enhanced_preds:
        en_nonempty = sum(1 for p in enhanced_preds.values() if p.get("model_patch", "").strip())
        log(f"Enhanced patches: {en_nonempty}/{len(enhanced_preds)} non-empty")
    if not args.solver_only:
        log(f"Fallback labeling: {len(enhanced_rows)} enhanced, {len(fallback_rows)} fallback")

    log(f"\nRun directory: {RUN_DIR}")
    log(f"Log file: {RUN_DIR / 'test.log'}")

    # Save summary
    (RUN_DIR / "test_result.json").write_text(json.dumps({
        "timestamp": _now(),
        "result": "FAIL" if failed else "PASS",
        "checks_passed": passed,
        "checks_failed": failed,
        "baseline_preds_count": len(baseline_preds),
        "baseline_nonempty_patches": bl_nonempty,
        "enhanced_preds_count": len(enhanced_preds),
        "enhanced_nonempty_patches": sum(1 for p in enhanced_preds.values() if p.get("model_patch", "").strip()),
        "enhanced_count": len(enhanced_rows),
        "fallback_count": len(fallback_rows),
    }, indent=2))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
