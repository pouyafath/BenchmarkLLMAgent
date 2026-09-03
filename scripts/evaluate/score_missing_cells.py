#!/usr/bin/env python3
"""
Score the enhancer x solver cells from runs 1 and 3 that never got a result.json.

Two were lost to harness hangs (m3_B trae->aider, m3_B mini->aider); the other twelve are
run-1's aider- and openhands-enhancer cells, which were never scored at all -- only the
swe_agent-enhancer cells of that run were.

Each distinct arm is evaluated once and cached, then the cells are assembled. Scoring
cell-by-cell with score_sample.py would re-run every baseline arm three times.

Writes runs/stage6_sample_<label>/result.json in the shape the existing sample results
use, so downstream analysis picks them up without changes.
"""
from __future__ import annotations
import json, os, sys, collections
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score_sample import (ROOT, DATASETS, METHODS, run_group, label_agnostic_pass,
                          report_p2p_pass, applied_cleanly)

TODO = json.loads(Path(os.environ.get("TODO_CELLS",
    "/home/22pf2/tmp/claude-10136/-home-22pf2-BenchmarkLLMAgent/"
    "4e1bec19-55a0-47d5-80ca-555e473168e0/scratchpad/todo_cells.json")).read_text())
CACHE   = ROOT/"runs/stage6_missing_cells"
WORKERS = int(os.environ.get("SCORE_WORKERS", "4"))


def score_arm(preds_path: Path, tag: str, methods: dict) -> dict:
    cache = CACHE/"arms"/f"{tag}.json"
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
        odir = CACHE/"work"/tag/method
        run_group(DATASETS[method], preds_path, grp, odir, WORKERS)
        for iid in grp:
            out[iid]["resolved"] = (label_agnostic_pass(odir/iid/"post_patch_log.txt")
                                    if method == "v3_fileLevel"
                                    else report_p2p_pass(odir/iid/"report.json"))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out, indent=1))
    n_ev = sum(len(v) for v in by_method.values())
    print(f"[{tag}] {sum(v['resolved'] for v in out.values())}/{len(ids)} resolved "
          f"({n_ev} evaluated)", flush=True)
    return out


def main() -> int:
    methods = json.load(open(METHODS))
    arms: dict[str, dict] = {}

    def get(run: str, cell: str) -> dict:
        tag = f"{Path(run).name}__{cell}"
        if tag not in arms:
            p = ROOT/run/"qwen3_32b/stage5"/cell/"preds.json"
            if not p.exists():
                print(f"!! MISSING {p}", flush=True); arms[tag] = {}
            else:
                arms[tag] = score_arm(p, tag, methods)
        return arms[tag]

    for c in TODO:
        b = get(c["run"], f"baseline__solver_{c['sol']}")
        e = get(c["run"], c["cell"])
        ids = sorted(set(b) & set(e))
        if not ids:
            print(f"!! no shared instances for {c['label']}", flush=True); continue
        rb = {i: b[i]["resolved"] for i in ids}
        re_ = {i: e[i]["resolved"] for i in ids}
        nb, ne = sum(rb.values()), sum(re_.values())
        out = ROOT/"runs"/f"stage6_sample_{c['label'].replace('stage6_sample_','')}"
        out.mkdir(parents=True, exist_ok=True)
        (out/"result.json").write_text(json.dumps({
            "label": c["label"], "n": len(ids), "baseline": nb, "enh": ne, "delta": ne-nb,
            "require_applied": False,
            "rescues":   sum(1 for i in ids if not rb[i] and re_[i]),
            "breakages": sum(1 for i in ids if rb[i] and not re_[i]),
            "resolved_baseline": rb, "resolved_enh": re_}, indent=1))
        print(f"  {c['label']:44s} n={len(ids)} base={nb} enh={ne} d={ne-nb:+d}", flush=True)
    print("\ndone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
