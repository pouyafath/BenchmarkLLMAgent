#!/usr/bin/env python3
"""
Score run-4: the append-only matrix (3 enhancers x 3 solvers x 80 instances).

Run-4 is the only configuration in the project where the treatment is purely additive.
Its enhanced arms reuse run-3's enhancements with enforce_append_only() applied, so the
original report always survives and the contrast isolates *added* context. Every earlier
enhancement number is confounded: the agents replaced the report rather than adding to it
(235/236 rows needed repair), so a null there could mean either "context does not help" or
"we deleted the useful part".

Run-4 carries no baseline of its own (it was launched with MATRIX_SKIP_BASELINE). The
paired baselines are run-3's, whose instance sets are identical half-for-half (verified:
r4A == r3A, r4B == r3B).

Why not scripts/evaluate/score_sample.py: that scores both arms of one cell per
invocation, so covering 18 cells would re-run each baseline arm 3 times -- ~200 redundant
container evaluations. This scores each distinct arm once, caches it, and assembles the
cells afterwards.

Both metric variants come out of a single harness pass: the run is done without
--require-applied (every non-empty patch is evaluated) and the stricter number is
recovered afterwards by intersecting with applied_cleanly(), which is a pure function of
the patch text.
"""
from __future__ import annotations
import json, sys, itertools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score_sample import (ROOT, DATASETS, METHODS, run_group, label_agnostic_pass,
                          report_p2p_pass, applied_cleanly)

HALVES = {
    "A": ("runs/rerun3_A_20260827_234635/qwen3_32b/stage5",
          "runs/rerun4_A_20260828_220623/qwen3_32b/stage5"),
    "B": ("runs/rerun3_B_20260827_234639/qwen3_32b/stage5",
          "runs/rerun4_B_20260828_220627/qwen3_32b/stage5"),
}
SOLVERS   = ["openhands", "swe_agent", "aider"]
ENHANCERS = ["openhands", "trae", "mini_swe_agent"]
OUT = ROOT / "runs/stage6_run4_appendonly"
WORKERS = int(__import__("os").environ.get("SCORE_WORKERS", "4"))


def score_arm(preds_path: Path, tag: str, methods: dict) -> dict:
    """Evaluate one arm once. Returns {iid: {resolved, applied, empty}}."""
    cache = OUT / "arms" / f"{tag}.json"
    if cache.exists():
        print(f"[{tag}] cached", flush=True)
        return json.load(open(cache))
    preds = json.load(open(preds_path))
    ids = sorted(preds)
    out = {i: {"resolved": False, "applied": False, "empty": True} for i in ids}

    by_method: dict[str, list[str]] = {}
    for i in ids:
        patch = (preds.get(i) or {}).get("model_patch") or ""
        if not patch.strip():
            continue
        out[i]["empty"] = False
        out[i]["applied"] = applied_cleanly(patch)
        m = methods.get(i)
        if not m:
            print(f"[{tag}] no gold-probe method for {i}", flush=True); continue
        by_method.setdefault(m, []).append(i)

    for method, grp in by_method.items():
        odir = OUT / "work" / tag / method
        run_group(DATASETS[method], preds_path, grp, odir, WORKERS)
        for iid in grp:
            out[iid]["resolved"] = (label_agnostic_pass(odir/iid/"post_patch_log.txt")
                                    if method == "v3_fileLevel"
                                    else report_p2p_pass(odir/iid/"report.json"))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out, indent=1))
    n_ev = sum(len(v) for v in by_method.values())
    print(f"[{tag}] {sum(v['resolved'] for v in out.values())}/{len(ids)} resolved "
          f"({n_ev} evaluated, {len(ids)-n_ev} empty)", flush=True)
    return out


def main() -> int:
    methods = json.load(open(METHODS))
    arms: dict[str, dict] = {}

    for half, (bdir, edir) in HALVES.items():
        for s in SOLVERS:
            p = ROOT / bdir / f"baseline__solver_{s}" / "preds.json"
            if p.exists():
                arms[f"{half}__baseline__{s}"] = score_arm(p, f"{half}__baseline__{s}", methods)
            else:
                print(f"!! MISSING {p}", flush=True)
        for e, s in itertools.product(ENHANCERS, SOLVERS):
            p = ROOT / edir / f"enh_{e}__solver_{s}" / "preds.json"
            if p.exists():
                arms[f"{half}__enh_{e}__{s}"] = score_arm(p, f"{half}__enh_{e}__{s}", methods)
            else:
                print(f"!! MISSING {p}", flush=True)

    # assemble the 9 cells, pooling the two halves
    cells = {}
    for e, s in itertools.product(ENHANCERS, SOLVERS):
        rb, re_ = {}, {}
        for half in HALVES:
            rb.update(arms.get(f"{half}__baseline__{s}", {}))
            re_.update(arms.get(f"{half}__enh_{e}__{s}", {}))
        ids = sorted(set(rb) & set(re_))
        def tally(d, strict):
            return sum(1 for i in ids if d[i]["resolved"] and (d[i]["applied"] or not strict))
        cells[f"enh_{e}__solver_{s}"] = {
            "n": len(ids),
            "baseline": tally(rb, False), "enh": tally(re_, False),
            "baseline_strict": tally(rb, True), "enh_strict": tally(re_, True),
            "rescues":   sum(1 for i in ids if not rb[i]["resolved"] and re_[i]["resolved"]),
            "breakages": sum(1 for i in ids if rb[i]["resolved"] and not re_[i]["resolved"]),
            "resolved_baseline": {i: rb[i]["resolved"] for i in ids},
            "resolved_enh":      {i: re_[i]["resolved"] for i in ids},
        }
        c = cells[f"enh_{e}__solver_{s}"]
        c["delta"] = c["enh"] - c["baseline"]
        c["delta_strict"] = c["enh_strict"] - c["baseline_strict"]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/"result.json").write_text(json.dumps(cells, indent=1))
    print(f"\n{'cell':38s} {'n':>3} {'base':>5} {'enh':>4} {'d':>4}   {'base*':>5} {'enh*':>4} {'d*':>4}  {'resc':>4} {'brk':>4}")
    for k, c in cells.items():
        print(f"{k:38s} {c['n']:3d} {c['baseline']:5d} {c['enh']:4d} {c['delta']:+4d}   "
              f"{c['baseline_strict']:5d} {c['enh_strict']:4d} {c['delta_strict']:+4d}  "
              f"{c['rescues']:4d} {c['breakages']:4d}")
    print("\n* = --require-applied (patch must be a well-formed, non-dump diff)")
    print(f"Wrote {OUT/'result.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
