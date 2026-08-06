#!/usr/bin/env python3
"""
STAGE 6 (combined) — score solver patches on the gold-validated evaluable subset, using
PER-INSTANCE the method that passed the gold probe:
  v3_fileLevel -> stage6_new182_v3.jsonl, label-agnostic (raw pytest: >=1 passed, 0 failed/err)
  v2_targeted  -> stage6_new182_v2.jsonl, report.json PASS_TO_PASS (0 fail, >0 pass)
  v1_files     -> stage6_new182_v1.jsonl, report.json PASS_TO_PASS
Produces the correctness matrix over the evaluable instances.
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path
ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
EVAL = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"
PY = "/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python"
DATASETS = {"v3_fileLevel": ROOT/"data/stage6_new182_v3.jsonl",
            "v2_targeted":  ROOT/"data/stage6_new182_v2.jsonl",
            "v1_files":     ROOT/"data/stage6_new182_v1.jsonl"}
STATES = ["baseline", "enh:openhands", "enh:swe_agent", "enh:aider"]
SOLVERS = ["openhands", "swe_agent", "aider"]


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


def run_group(dataset, preds, ids, outdir, workers):
    outdir.mkdir(parents=True, exist_ok=True)
    # NOTE: harness runs with cwd=EVAL.parent, so output_dir MUST be absolute or the reports
    # land under evaluation/<relpath> while the checker looks under the repo root (-> 0 found).
    subprocess.run([PY, str(EVAL), "--dataset", str(dataset), "--patch_dir", str(Path(preds).resolve()),
                    "--platform", "linux", "--workers", str(workers),
                    "--output_dir", str(outdir.resolve()), "--overwrite", "1", "--instance_ids", *ids],
                   cwd=str(EVAL.parent), capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", required=True)   # evaluable_methods.json
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    methods = json.load(open(a.methods))          # {iid: method}
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    by_method = {}
    for iid, m in methods.items(): by_method.setdefault(m, []).append(iid)
    print(f"Combined Stage 6 | {len(methods)} evaluable | groups: "
          + ", ".join(f"{m}={len(v)}" for m, v in by_method.items()), flush=True)

    matrix = {s: {sv: {} for sv in SOLVERS} for s in STATES}
    for state in STATES:
        for solver in SOLVERS:
            cdir = f"{state.replace(':','_')}__solver_{solver}"
            for run in a.runs:
                hits = list((ROOT/run if not Path(run).is_absolute() else Path(run)).glob(f"*/stage5/{cdir}/preds.json"))
                if not hits: continue
                preds = hits[0]
                try: keys = set(json.load(open(preds)).keys())
                except Exception: keys = set()
                for method, ids in by_method.items():
                    grp = [i for i in ids if i in keys]
                    if not grp: continue
                    odir = out / Path(run).name / cdir / method
                    run_group(DATASETS[method], preds, grp, odir, a.workers)
                    for iid in grp:
                        if method == "v3_fileLevel":
                            ok = label_agnostic_pass(odir/iid/"post_patch_log.txt")
                        else:
                            ok = report_p2p_pass(odir/iid/"report.json")
                        matrix[state][solver][iid] = ok
            d = matrix[state][solver]
            print(f"  [{state} -> {solver}] {sum(d.values())}/{len(d)} resolved", flush=True)

    print("\n=== STAGE 6 — CORRECTNESS matrix (gold-validated evaluable subset) ===")
    hdr = "state \\ solver      | " + " | ".join(f"{s:^10}" for s in SOLVERS); print(hdr); print("-"*len(hdr))
    for state in STATES:
        cells = [f"{sum(matrix[state][sv].values())}/{len(matrix[state][sv])}".center(10) for sv in SOLVERS]
        print(f"{state:<20}| " + " | ".join(cells))
    (out/"stage6_combined_matrix.json").write_text(json.dumps(
        {"methods": methods, "matrix": matrix}, indent=2))
    print(f"\nWrote {out/'stage6_combined_matrix.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
