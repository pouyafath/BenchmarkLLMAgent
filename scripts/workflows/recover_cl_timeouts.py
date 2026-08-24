#!/usr/bin/env python3
"""Recover CL-Enhanced arm timeout cells: re-solve the timed-out issues on their enh:cl_enhanced
text (from the run's Stage-4 output) at lower concurrency, merge non-empty results into preds."""
from __future__ import annotations
import json, sys, time
from pathlib import Path

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
sys.path.insert(0, str(ROOT))
from scripts.workflows.run_matrix_test import set_llm_env, solve, _sr

LLM = "qwen3:32b"
RUN = Path(sys.argv[1])   # cl_enhanced run dir
# enhanced (or fallback-to-original) rows the run actually solved on
ENH = {json.loads(l)["instance_id"]: json.loads(l)
       for l in open(RUN / "qwen3_32b/stage4/cl_enhanced/enhanced_cl_enhanced_gemma3.jsonl")}
CELLS = {"openhands": json.load(open("/tmp/cl_oh_timeouts.json"))["enh:cl_enhanced"],
         "swe_agent": [], "aider": json.load(open("/tmp/cl_aider_timeouts.json"))["enh:cl_enhanced"]}
WORKERS = {"openhands": 2, "swe_agent": 4, "aider": 4}

set_llm_env(LLM)
for solver, iids in CELLS.items():
    if not iids: continue
    insts = [_sr(ENH[i]) for i in iids if i in ENH]
    sdir = RUN / "qwen3_32b/stage5_recovery" / f"enh_cl_enhanced__solver_{solver}"
    sdir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== recover {solver}: {len(insts)} cells (workers={WORKERS[solver]}, t=5400) ===", flush=True)
    import scripts.workflows.run_matrix_test as M
    M.SOLVE_TIMEOUT = 5400; M.SOLVER_WORKERS[solver] = WORKERS[solver]
    t0 = time.time()
    preds = solve(solver, insts, sdir, LLM)
    # merge non-empty into main preds
    mainf = RUN / "qwen3_32b/stage5" / f"enh_cl_enhanced__solver_{solver}" / "preds.json"
    mp = json.loads(mainf.read_text())
    rec = 0
    for i in iids:
        if (preds.get(i, {}).get("model_patch", "") or "").strip():
            mp[i] = preds[i]; rec += 1
    mainf.write_text(json.dumps(mp, indent=2))
    print(f"  recovered {rec}/{len(iids)} in {(time.time()-t0)/60:.0f} min -> merged", flush=True)
print("\nDONE")
