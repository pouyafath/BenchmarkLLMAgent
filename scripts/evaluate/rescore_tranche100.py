#!/usr/bin/env python3
"""
Recover per-test artifacts for the first 100-issue tranche.

That tranche's scoring output was lost and recovered only as booleans, so it cannot be
rescored under the executed FAIL_TO_PASS criterion -- it is the sole gap in the strict
matrix. The solver patches themselves survived in runs/stage6_100_consol, so re-running
the harness over them regenerates the per-test status.json.

Only 28 of the tranche's 100 instances carry an executed fail->pass test, and the P2P-only
numbers for the full 100 already exist, so this runs the 28 rather than all 100: the same
recovery at roughly a quarter of the container cost.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score_sample import ROOT, DATASETS, METHODS, run_group

SRC  = ROOT/"runs/stage6_100_consol/qwen3_32b/stage5"
OUT  = ROOT/"runs/stage6_100_rescore"
IDS  = json.load(open(ROOT/"data/stage6_tranche100_gradeable_28.json"))
WORKERS = int(os.environ.get("SCORE_WORKERS", "4"))

def main() -> int:
    methods = json.load(open(METHODS))
    arms = sorted(p.name for p in SRC.iterdir() if (p/"preds.json").exists())
    print(f"{len(arms)} arms x {len(IDS)} gradeable instances", flush=True)
    for arm in arms:
        preds_path = SRC/arm/"preds.json"
        preds = json.load(open(preds_path))
        todo = [i for i in IDS
                if (preds.get(i) or {}).get("model_patch", "").strip()
                and not (OUT/arm/methods.get(i, "")/i/"status.json").exists()]
        if not todo:
            print(f"[{arm}] nothing to do", flush=True); continue
        by_method: dict[str, list[str]] = {}
        for i in todo:
            by_method.setdefault(methods[i], []).append(i)
        for method, grp in by_method.items():
            run_group(DATASETS[method], preds_path, grp, OUT/arm/method, WORKERS)
        got = sum(1 for i in IDS if (OUT/arm/methods.get(i, "")/i/"status.json").exists())
        print(f"[{arm}] {got}/{len(IDS)} have per-test status", flush=True)
    print("done", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
