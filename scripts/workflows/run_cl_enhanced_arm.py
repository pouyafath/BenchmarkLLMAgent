#!/usr/bin/env python3
"""
CL-Enhanced (\ourmethod) 4th enhancer arm on the 382 set.
Runs ONLY: Stage 4 (cl_enhanced_gemma3 enhancement) + Stage 5 (3 solvers on the enh:cl_enhanced
state). Baseline is REUSED from the existing 382 matrix runs (not recomputed).

Model held constant at qwen3:32b (same LLM the generic enhancers used) so the comparison isolates
the enhancement METHOD (managed reward-gated RAG) from the model. Reward gate abstains on ~51% of
these issues (returns original -> baseline-equivalent); acts on the rest.

Deps that must be up: Qdrant server :6333 (seed_309), private Ollama :11435 (qwen3:32b).

Usage:
  CL_GEMMA3_MODEL=qwen3:32b CL_GEMMA3_BASE_URL=http://localhost:11435 CL_ENHANCED_TIMEOUT=700 \
  nohup bench_env/bin/python scripts/workflows/run_cl_enhanced_arm.py \
      --dataset data/matrix_sample382_node01.jsonl --tag cl_enhanced_382 > ~/cl_enhanced_382.log 2>&1 &
"""
from __future__ import annotations
import argparse, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
sys.path.insert(0, str(ROOT))
from scripts.workflows.run_matrix_test import set_llm_env, enhance, solve, preflight, _load, _sr

LLM = "qwen3:32b"
SOLVERS = ["openhands", "swe_agent", "aider"]
ENHANCER = "cl_enhanced_gemma3"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--tag", default="cl_enhanced_382")
    a = ap.parse_args()

    # cl_enhanced reads these; keep the LLM = qwen3:32b (the control), point at private Ollama
    os.environ.setdefault("CL_GEMMA3_MODEL", "qwen3:32b")
    os.environ.setdefault("CL_GEMMA3_BASE_URL", "http://localhost:11435")
    os.environ.setdefault("CL_ENHANCED_TIMEOUT", "700")

    instances = _load(a.dataset)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = ROOT / "runs" / f"{a.tag}_{ts}" / "qwen3_32b"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{datetime.now(timezone.utc):%H:%M:%S}] CL-Enhanced arm | {len(instances)} issues | "
          f"model={os.environ['CL_GEMMA3_MODEL']} @ {os.environ['CL_GEMMA3_BASE_URL']}", flush=True)
    print(f"Run dir: {run_dir}", flush=True)

    set_llm_env(LLM)   # solver env (qwen3:32b on :11435)
    if not preflight(instances):
        print("PREFLIGHT FAILED — aborting"); return 1

    # ── Stage 4: cl_enhanced enhancement ──────────────────────────────────────
    t0 = time.time()
    rows, n_ok = enhance(ENHANCER, instances, run_dir / "stage4" / "cl_enhanced", LLM)
    print(f"[Stage 4] cl_enhanced: {n_ok}/{len(instances)} truly enhanced "
          f"(rest abstained -> original) in {(time.time()-t0)/3600:.2f} h", flush=True)

    # ── Stage 5: 3 solvers on the enh:cl_enhanced state ───────────────────────
    summary = {}
    for solver in SOLVERS:
        sdir = run_dir / "stage5" / f"enh_cl_enhanced__solver_{solver}"
        tc = time.time()
        print(f"\n=== enh:cl_enhanced -> {solver} ({len(rows)} issues) ===", flush=True)
        preds = solve(solver, rows, sdir, LLM)
        ne = sum(1 for inst in rows
                 if (preds.get(inst["instance_id"], {}).get("model_patch", "") or "").strip())
        summary[solver] = {"n_nonempty": ne, "n": len(rows)}
        print(f"[enh:cl_enhanced -> {solver}] {ne}/{len(rows)} non-empty  ({(time.time()-tc)/3600:.2f} h)", flush=True)

    out = {"tag": a.tag, "llm": LLM, "enhancer": ENHANCER, "n": len(instances),
           "cl_model": os.environ["CL_GEMMA3_MODEL"], "truly_enhanced": n_ok,
           "solvers": summary, "elapsed_h": (time.time()-t0)/3600}
    (run_dir.parent / "cl_enhanced_result.json").write_text(json.dumps(out, indent=2))
    print(f"\n=== DONE ({out['elapsed_h']:.1f} h) ===")
    print(f"truly enhanced: {n_ok}/{len(instances)} | non-empty per solver: "
          + ", ".join(f"{s}={v['n_nonempty']}/{v['n']}" for s, v in summary.items()))
    print(f"Saved {run_dir.parent / 'cl_enhanced_result.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
