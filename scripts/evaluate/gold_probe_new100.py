#!/usr/bin/env python3
"""
STAGE 6 (100-issue) — Phase 2: gold-probe gate.
Run the SWE-bench-Live harness with the GOLD patch under each method; an instance is "evaluable
by method m" iff the gold patch passes under m. Assign each instance the most precise passing
method (priority v2 > v3 > v1). Writes evaluable_methods_new100.json {iid: method}.

Incremental: probe v2 on all 100, then v3 only on the not-yet-evaluable, then v1 on the rest.
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
EVAL = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"
PY = "/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python"
GOLD = "/home/22pf2/stage6/gold_preds_new100.json"
OUTDIR = ROOT / "runs/stage6_new100_goldprobe"
WORKERS = 3
DATASETS = {"v2": ROOT / "data/stage6_new100_v2.jsonl",
            "v3": ROOT / "data/stage6_new100_v3.jsonl",
            "v1": ROOT / "data/stage6_new100_v1.jsonl"}
PRIORITY = ["v2", "v3", "v1"]


def label_agnostic_pass(logfile: Path) -> bool:
    if not logfile.exists(): return False
    t = logfile.read_text(errors="replace")
    passed = sum(int(x) for x in re.findall(r'(\d+) passed', t))
    failed = sum(int(x) for x in re.findall(r'(\d+) failed', t))
    errors = sum(int(x) for x in re.findall(r'(\d+) error', t))
    return failed == 0 and errors == 0 and passed > 0


def report_p2p_pass(report: Path) -> bool:
    if not report.exists(): return False
    p = json.load(open(report)).get("PASS_TO_PASS", {})
    return len(p.get("failure", [])) == 0 and len(p.get("success", [])) > 0


def run_harness(dataset, ids, odir):
    odir.mkdir(parents=True, exist_ok=True)
    subprocess.run([PY, str(EVAL), "--dataset", str(dataset), "--patch_dir", GOLD,
                    "--platform", "linux", "--workers", str(WORKERS),
                    "--output_dir", str(odir), "--overwrite", "1", "--instance_ids", *ids],
                   cwd=str(EVAL.parent), capture_output=True, text=True)


def main():
    all_ids = list(json.load(open(GOLD)).keys())
    methods = {}
    remaining = set(all_ids)
    for m in PRIORITY:
        if not remaining: break
        ids = sorted(remaining)
        odir = OUTDIR / m
        print(f"[gold-probe {m}] probing {len(ids)} instances ...", flush=True)
        run_harness(DATASETS[m], ids, odir)
        passed = []
        for iid in ids:
            ok = (label_agnostic_pass(odir / iid / "post_patch_log.txt") if m == "v3"
                  else report_p2p_pass(odir / iid / "report.json"))
            if ok:
                methods[iid] = f"{m}_fileLevel" if m == "v3" else (f"{m}_targeted" if m == "v2" else f"{m}_files")
                passed.append(iid)
        remaining -= set(passed)
        print(f"  [{m}] gold-passes: {len(passed)} | cumulative evaluable: {len(methods)}/{len(all_ids)}", flush=True)

    outf = Path("/home/22pf2/stage6/evaluable_methods_new100.json")
    outf.write_text(json.dumps(methods, indent=2))
    from collections import Counter
    print(f"\nEvaluable: {len(methods)}/{len(all_ids)} ({100*len(methods)//len(all_ids)}%)")
    print("  by method:", dict(Counter(methods.values())))
    print(f"  wrote {outf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
