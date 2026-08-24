#!/usr/bin/env python3
"""
STAGE 6 — P2P scoring of solver patches (no LLM/GPU; Docker+CPU only).

Scores every matrix condition's preds.json by applying the solver patch inside the
validated pouya/stage2_2026 image, running the PASS_TO_PASS test FILES (tolerant of
stale node-IDs), and checking that the expected P2P tests pass. Uses the SWE-bench-Live
harness (SWE-bench-Live-Collection/evaluation/evaluation.py).

Validated approach (gold-probe gated): run test FILES + --continue-on-collection-errors +
test_patch applied; an instance "P2P-passes" iff >=1 expected P2P ran and 0 failed.
Only the gold-evaluable subset (gold patch P2P-passes) is scored — others aren't trustworthy.

Usage:
  python scripts/evaluate/run_stage6_p2p.py \
     --eval-dataset data/stage6_sample20_p2p.jsonl \
     --evaluable /home/22pf2/stage6/evaluable_ids.txt \
     --runs runs/matrix20_node01_20260617_082502 runs/matrix20_node01_batch2_175203 \
     --out /home/22pf2/stage6/solver_scores --workers 6
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
EVAL = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"
PYTHON = "/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python"
STATES = ["baseline", "enh:openhands", "enh:swe_agent", "enh:aider"]
SOLVERS = ["openhands", "swe_agent", "aider"]


def cond_dirname(state, solver):
    return f"{state.replace(':','_')}__solver_{solver}"


def score_condition(eval_ds, preds, evaluable, outdir, workers):
    """Run the harness for one condition's preds.json on the evaluable subset; return {iid: p2p_pass}."""
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [PYTHON, str(EVAL), "--dataset", str(eval_ds), "--patch_dir", str(preds),
           "--platform", "linux", "--workers", str(workers),
           "--output_dir", str(outdir), "--overwrite", "1",
           "--instance_ids", *evaluable]
    subprocess.run(cmd, cwd=str(EVAL.parent), capture_output=True, text=True)
    res = {}
    for iid in evaluable:
        rp = outdir / iid / "report.json"
        if rp.exists():
            r = json.load(open(rp)); p = r.get("PASS_TO_PASS", {})
            res[iid] = (len(p.get("failure", [])) == 0 and len(p.get("success", [])) > 0)
        else:
            res[iid] = False
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-dataset", required=True)
    ap.add_argument("--evaluable", required=True, help="file with evaluable instance_ids (one/line)")
    ap.add_argument("--runs", nargs="+", required=True, help="matrix run dirs (preds under stage5/)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    evaluable = [l.strip() for l in open(args.evaluable) if l.strip()]
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    # also restrict the eval dataset to evaluable rows (faster load)
    print(f"Stage 6 P2P scoring | evaluable={len(evaluable)} | conditions={len(STATES)*len(SOLVERS)} | runs={len(args.runs)}", flush=True)

    # matrix[state][solver] = {iid: pass}; aggregate across the provided run dirs (batches)
    matrix = {s: {sv: {} for sv in SOLVERS} for s in STATES}
    for state in STATES:
        for solver in SOLVERS:
            cdir = cond_dirname(state, solver)
            for run in args.runs:
                # preds live under <run>/<llm>/stage5/<cond>/preds.json (cwd-independent)
                run_path = Path(run) if Path(run).is_absolute() else (ROOT / run)
                hits = list(run_path.glob(f"*/stage5/{cdir}/preds.json"))
                if not hits:
                    continue
                preds = hits[0]
                # which evaluable instances are in THIS run's preds?
                try: keys = set(json.load(open(preds)).keys())
                except Exception: keys = set()
                sub = [i for i in evaluable if i in keys]
                if not sub:
                    continue
                odir = out / Path(run).name / cdir
                r = score_condition(args.eval_dataset, preds, sub, odir, args.workers)
                matrix[state][solver].update(r)
                print(f"  [{state} -> {solver}] ({Path(run).name}): "
                      f"{sum(r.values())}/{len(sub)} P2P-pass", flush=True)

    # report
    print("\n=== STAGE 6 — P2P resolved matrix (evaluable subset) ===")
    hdr = "state \\ solver      | " + " | ".join(f"{s:^10}" for s in SOLVERS)
    print(hdr); print("-"*len(hdr))
    summary = {}
    for state in STATES:
        cells = []
        for sv in SOLVERS:
            d = matrix[state][sv]; n = len(d); passed = sum(d.values())
            cells.append(f"{passed}/{n}".center(10))
            summary[f"{state}->{sv}"] = {"pass": passed, "n": n}
        print(f"{state:<20}| " + " | ".join(cells))
    (out / "stage6_p2p_matrix.json").write_text(json.dumps(
        {"evaluable": evaluable, "matrix": {s:{sv:matrix[s][sv] for sv in SOLVERS} for s in STATES},
         "summary": summary}, indent=2))
    print(f"\nWrote {out/'stage6_p2p_matrix.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
