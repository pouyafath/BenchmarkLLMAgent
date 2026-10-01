#!/usr/bin/env python3
"""
Score a single solver arm. Used for the second GPT-5-mini baseline draw, where there is no
enhanced arm to pair against: the comparison is draw 1 against draw 2.

score_sample.py always scores two arms of one cell, so it cannot express this.

Usage:
  bench_env/bin/python scripts/evaluate/score_one_arm.py <preds.json> <label>
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from score_sample import (ROOT, DATASETS, METHODS, run_group, label_agnostic_pass,
                          report_p2p_pass, applied_cleanly)

def main() -> int:
    preds_path = Path(sys.argv[1]); label = sys.argv[2]
    workers = int(os.environ.get("SCORE_WORKERS", "4"))
    methods = json.load(open(METHODS))
    preds = json.load(open(preds_path))
    out = ROOT/"runs"/f"stage6_arm_{label}"
    ids = sorted(preds)
    res = {i: {"resolved": False, "applied": False, "empty": True} for i in ids}
    by_method: dict[str, list[str]] = {}
    for i in ids:
        patch = (preds.get(i) or {}).get("model_patch") or ""
        if not patch.strip():
            continue
        res[i]["empty"] = False
        res[i]["applied"] = applied_cleanly(patch)
        m = methods.get(i)
        if m:
            by_method.setdefault(m, []).append(i)
    for method, grp in by_method.items():
        odir = out/"work"/method
        run_group(DATASETS[method], preds_path, grp, odir, workers)
        for iid in grp:
            res[iid]["resolved"] = (label_agnostic_pass(odir/iid/"post_patch_log.txt")
                                    if method == "v3_fileLevel"
                                    else report_p2p_pass(odir/iid/"report.json"))
    out.mkdir(parents=True, exist_ok=True)
    (out/"result.json").write_text(json.dumps(
        {"label": label, "n": len(ids),
         "resolved": sum(v["resolved"] for v in res.values()),
         "per_instance": res}, indent=1))
    print(f"\n{label}: {sum(v['resolved'] for v in res.values())}/{len(ids)} resolved")
    print(f"Wrote {out/'result.json'}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
