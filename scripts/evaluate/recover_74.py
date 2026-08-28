#!/usr/bin/env python3
"""
Recover the 74 instances whose scoring artifacts were lost.

runs/stage6_100_scores/stage6_combined_matrix.json is all-zero for every cell — a failed
scoring pass, not a result. Its 74 instances are real members of the 279 gold-evaluable
set (205 + 74 = 279 exactly, and the paper's Table 1 credits them with 15 OpenHands and
30 Aider resolves). Their SOLVER OUTPUTS survive in
runs/stage6_100_consol/qwen3_32b/stage5/ for all 12 conditions; only the harness reports
were lost. This re-runs the harness over them and writes a corrected matrix.

Docker only — no API cost.

Usage:
  bench_env/bin/python scripts/evaluate/recover_74.py [--workers 4]
"""
from __future__ import annotations
import argparse, json, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from score_sample import (ROOT, DATASETS, METHODS, run_group,
                          label_agnostic_pass, report_p2p_pass)

SRC   = ROOT / "runs/stage6_100_consol/qwen3_32b/stage5"
OUT   = ROOT / "runs/stage6_100_recovered"
STATES  = ["baseline", "enh_openhands", "enh_swe_agent", "enh_aider"]
SOLVERS = ["openhands", "swe_agent", "aider"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--ids", default="/tmp/recover74.txt")
    a = ap.parse_args()

    ids = [l.strip() for l in open(a.ids) if l.strip()]
    methods = json.load(open(METHODS))
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Recovering {len(ids)} instances x {len(STATES)*len(SOLVERS)} conditions", flush=True)

    matrix: dict[str, dict[str, dict[str, bool]]] = {}
    for state in STATES:
        key = "baseline" if state == "baseline" else state.replace("enh_", "enh:")
        matrix[key] = {}
        for solver in SOLVERS:
            cond = f"{state}__solver_{solver}"
            preds_path = SRC / cond / "preds.json"
            if not preds_path.exists():
                print(f"  [{cond}] MISSING preds.json", flush=True)
                matrix[key][solver] = {}
                continue
            preds = json.load(open(preds_path))
            resolved = {i: False for i in ids}

            by_method: dict[str, list[str]] = {}
            for i in ids:
                m = methods.get(i)
                if not m:
                    continue
                patch = (preds.get(i, {}) or {}).get("model_patch", "") or ""
                if patch.strip():
                    by_method.setdefault(m, []).append(i)

            for method, grp in by_method.items():
                odir = OUT / cond / method
                run_group(DATASETS[method], preds_path, grp, odir, a.workers)
                for iid in grp:
                    resolved[iid] = (label_agnostic_pass(odir/iid/"post_patch_log.txt")
                                     if method == "v3_fileLevel"
                                     else report_p2p_pass(odir/iid/"report.json"))
            n_eval = sum(len(v) for v in by_method.values())
            print(f"  [{cond}] {sum(resolved.values())}/{len(ids)} resolved "
                  f"({n_eval} evaluated)", flush=True)
            matrix[key][solver] = resolved

    out_json = OUT / "stage6_combined_matrix.json"
    out_json.write_text(json.dumps(
        {"methods": {i: methods.get(i) for i in ids if methods.get(i)},
         "matrix": matrix}, indent=1))
    print(f"\nWrote {out_json}", flush=True)

    print("\nRecovered matrix (resolved / evaluated):", flush=True)
    for state in matrix:
        row = "  ".join(f"{sv}={sum(matrix[state][sv].values())}" for sv in SOLVERS)
        print(f"  {state:<16} {row}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
