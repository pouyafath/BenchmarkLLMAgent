#!/usr/bin/env python3
"""
RECOVERY B — re-solve the aider cells that TIMED OUT in the new-50 full matrix.

The new-50 drew heavier repos than the validated-50; at aider workers=8 some hit the 3600 s wall
and were recorded empty (artifact, not a real failure). This re-solves ONLY those (state, issue)
cells, reusing the SAME problem statement each condition used:
  - baseline  -> original text from data/matrix_sample50new_node01.jsonl
  - enh:X      -> enhanced text from <run>/qwen3_32b/stage4/X/enhanced_X.jsonl
Results are MERGED into each condition's preds.json (only the timed-out issues are overwritten).

Usage (diagnostic):  ... --states baseline --only azure,AutoRAG,pyomo --workers 1 --timeout 5400
Usage (full):        ... --workers 4 --timeout 3600
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
sys.path.insert(0, str(ROOT))
from scripts.workflows.run_matrix_test import set_llm_env, _sr, _load

LLM = "qwen3:32b"
BASE_URL = "http://localhost:11435/v1"
API_KEY = "ollama"
STMAP = {"baseline": "baseline", "enh:openhands": "enh_openhands",
         "enh:swe_agent": "enh_swe_agent", "enh:aider": "enh_aider"}
ENHSRC = {"enh:openhands": "openhands", "enh:swe_agent": "swe_agent", "enh:aider": "aider"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="matrix100_new50 run dir")
    ap.add_argument("--cells", default="/tmp/aider_timeout_cells.json")
    ap.add_argument("--baseline-dataset", default="data/matrix_sample50new_node01.jsonl")
    ap.add_argument("--states", nargs="+", default=list(STMAP), help="which states to recover")
    ap.add_argument("--only", default="", help="comma substrings: restrict to matching issue ids (diagnostic)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--merge", action="store_true", help="write recovered patches back into preds.json")
    a = ap.parse_args()

    run = Path(a.run)
    cells = json.load(open(a.cells))                       # {state: [iid,...]}
    base_rows = {r["instance_id"]: r for r in _load(a.baseline_dataset)}
    subs = [s for s in a.only.split(",") if s]
    from src.solvers.aider_solver import run_batch as aider_batch

    grand = {}
    for state in a.states:
        iids = cells.get(state, [])
        if subs:
            iids = [i for i in iids if any(s in i for s in subs)]
        if not iids:
            continue
        # problem statement source
        if state == "baseline":
            src = base_rows
        else:
            erows = _load(run / "qwen3_32b" / "stage4" / ENHSRC[state] / f"enhanced_{ENHSRC[state]}.jsonl")
            src = {r["instance_id"]: r for r in erows}
        insts = [_sr(src[i]) for i in iids if i in src]
        sdir = run / "qwen3_32b" / "stage5_recovery" / f"{STMAP[state]}__solver_aider"
        sdir.mkdir(parents=True, exist_ok=True)
        preds_out = sdir / "preds.json"
        print(f"\n=== RECOVER {state} -> aider | {len(insts)} issues | workers={a.workers} timeout={a.timeout}s ===", flush=True)
        for i in insts:
            print(f"    - {i['instance_id']}", flush=True)
        set_llm_env(LLM)
        t0 = time.time()
        aider_batch(insts, API_KEY, sdir / "work", preds_out,
                    model=f"openai/{LLM}", base_url=BASE_URL, timeout=a.timeout, workers=a.workers)
        dt = time.time() - t0
        preds = json.loads(preds_out.read_text()) if preds_out.exists() else {}
        got = {i: bool((preds.get(i, {}).get("model_patch", "") or "").strip()) for i in iids if i in src}
        n = sum(got.values())
        print(f"  -> recovered {n}/{len(got)} non-empty in {dt/60:.1f} min  "
              f"({', '.join(k.split('__')[-1]+('+' if v else '-') for k,v in got.items())})", flush=True)
        grand[state] = {"recovered_nonempty": n, "n": len(got), "issues": got, "elapsed_min": dt/60}

        if a.merge:
            main_preds_f = run / "qwen3_32b" / "stage5" / f"{STMAP[state]}__solver_aider" / "preds.json"
            mp = json.loads(main_preds_f.read_text())
            for i in iids:
                if i in preds:
                    mp[i] = preds[i]
            main_preds_f.write_text(json.dumps(mp, indent=2))
            print(f"  merged into {main_preds_f}")

    print("\n=== RECOVERY SUMMARY ===")
    for st, v in grand.items():
        print(f"  {st:<14}: +{v['recovered_nonempty']}/{v['n']}  ({v['elapsed_min']:.0f} min)")
    (run / "aider_recovery_summary.json").write_text(json.dumps(
        {"workers": a.workers, "timeout": a.timeout, "merged": a.merge, "result": grand}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
