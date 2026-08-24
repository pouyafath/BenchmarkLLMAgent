#!/usr/bin/env python3
"""
RECOVERY (generic) — re-solve (state, solver, issue) cells that TIMED OUT in a matrix run.
Works for openhands or aider. Reuses the same problem statement each condition used:
  - baseline  -> original text from --baseline-dataset
  - enh:X      -> enhanced text from <run>/qwen3_32b/stage4/X/enhanced_X.jsonl
Writes into a stage5_recovery/ dir; --merge folds recovered non-empty patches back into preds.json.

Usage:
  ... --run <rundir> --solver openhands --cells /tmp/oh_timeout_cells_382.json \
      --baseline-dataset data/matrix_sample182extra_node01.jsonl --workers 2 --timeout 5400 --merge
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
    ap.add_argument("--run", required=True)
    ap.add_argument("--solver", required=True, choices=["openhands", "swe_agent", "aider"])
    ap.add_argument("--cells", required=True)
    ap.add_argument("--baseline-dataset", required=True)
    ap.add_argument("--states", nargs="+", default=list(STMAP))
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=5400)
    ap.add_argument("--merge", action="store_true")
    a = ap.parse_args()

    run = Path(a.run)
    cells = json.load(open(a.cells))
    base_rows = {r["instance_id"]: r for r in _load(a.baseline_dataset)}
    if a.solver == "openhands":
        from src.solvers.openhands_solver import run_batch as batch
        model_kw = dict(model=LLM)
    elif a.solver == "swe_agent":
        from src.solvers.swe_agent_solver import run_batch as batch
        model_kw = dict(model=LLM)
    else:
        from src.solvers.aider_solver import run_batch as batch
        model_kw = dict(model=f"openai/{LLM}")

    grand = {}
    for state in a.states:
        iids = cells.get(state, [])
        if not iids:
            continue
        if state == "baseline":
            src = base_rows
        else:
            erows = _load(run / "qwen3_32b" / "stage4" / ENHSRC[state] / f"enhanced_{ENHSRC[state]}.jsonl")
            src = {r["instance_id"]: r for r in erows}
        insts = [_sr(src[i]) for i in iids if i in src]
        sdir = run / "qwen3_32b" / "stage5_recovery" / f"{STMAP[state]}__solver_{a.solver}"
        sdir.mkdir(parents=True, exist_ok=True)
        preds_out = sdir / "preds.json"
        print(f"\n=== RECOVER {state} -> {a.solver} | {len(insts)} issues | workers={a.workers} timeout={a.timeout}s ===", flush=True)
        for i in insts:
            print(f"    - {i['instance_id']}", flush=True)
        set_llm_env(LLM)
        t0 = time.time()
        batch(insts, API_KEY, sdir / "work", preds_out, base_url=BASE_URL, timeout=a.timeout,
              workers=a.workers, **model_kw)
        dt = time.time() - t0
        preds = json.loads(preds_out.read_text()) if preds_out.exists() else {}
        got = {i: bool((preds.get(i, {}).get("model_patch", "") or "").strip()) for i in iids if i in src}
        n = sum(got.values())
        print(f"  -> recovered {n}/{len(got)} non-empty in {dt/60:.1f} min  "
              f"({', '.join(k.split('__')[-1]+('+' if v else '-') for k,v in got.items())})", flush=True)
        grand[state] = {"recovered_nonempty": n, "n": len(got), "issues": got, "elapsed_min": dt/60}

        if a.merge:
            main_preds_f = run / "qwen3_32b" / "stage5" / f"{STMAP[state]}__solver_{a.solver}" / "preds.json"
            mp = json.loads(main_preds_f.read_text())
            for i in iids:
                if i in preds:
                    mp[i] = preds[i]
            main_preds_f.write_text(json.dumps(mp, indent=2))
            print(f"  merged into {main_preds_f}")

    print("\n=== RECOVERY SUMMARY ===")
    for st, v in grand.items():
        print(f"  {st:<14}: +{v['recovered_nonempty']}/{v['n']}  ({v['elapsed_min']:.0f} min)")
    (run / f"{a.solver}_recovery_summary.json").write_text(json.dumps(
        {"solver": a.solver, "workers": a.workers, "timeout": a.timeout, "merged": a.merge, "result": grand}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
