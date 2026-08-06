#!/usr/bin/env python3
"""
Raw-LLM (zero-shot) enhancer arm on the 382 set: the `simple_enhancer` — a single Qwen3-32B call
that rewrites the issue title+body to be clearer/more actionable (no agent loop, no RAG, no reward
gate). This is the "did the agent machinery buy anything over just prompting?" comparator.

Runs ONLY Stage 4 (simple_enhancer) + Stage 5 (3 solvers on the enh:simple state). Baseline is
REUSED from the existing 382 matrix runs. Model held constant at qwen3:32b (:11435) via set_llm_env.

Usage:
  MINI_TIMEOUT=600 nohup bench_env/bin/python scripts/workflows/run_simple_enhanced_arm.py \
      --dataset data/matrix_sample382_node01.jsonl --tag simple_enh_382 > ~/simple_enh_382.log 2>&1 &
"""
from __future__ import annotations
import argparse, json, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
sys.path.insert(0, str(ROOT))
from scripts.workflows.run_matrix_test import set_llm_env, enhance, solve, preflight, _load

LLM = "qwen3:32b"
SOLVERS = ["openhands", "swe_agent", "aider"]
ENHANCER = "simple_enhancer"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--tag", default="simple_enh_382")
    a = ap.parse_args()

    instances = _load(a.dataset)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = ROOT / "runs" / f"{a.tag}_{ts}" / "qwen3_32b"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{datetime.now(timezone.utc):%H:%M:%S}] Simple (zero-shot) arm | {len(instances)} issues | "
          f"enhancer={ENHANCER} | model={LLM} @ :11435", flush=True)
    print(f"Run dir: {run_dir}", flush=True)

    set_llm_env(LLM)   # sets OLLAMA_MODEL=qwen3:32b, OLLAMA_BASE_URL=:11435 (for the enhancer's llm_client)
                       # + solver env, all qwen3:32b
    if not preflight(instances):
        print("PREFLIGHT FAILED — aborting"); return 1

    # ── Stage 4: zero-shot enhancement ────────────────────────────────────────
    t0 = time.time()
    rows, n_ok = enhance(ENHANCER, instances, run_dir / "stage4" / "simple", LLM)
    print(f"[Stage 4] simple_enhancer: {n_ok}/{len(instances)} truly enhanced "
          f"in {(time.time()-t0)/3600:.2f} h", flush=True)

    # ── Stage 5: 3 solvers on the enh:simple state ────────────────────────────
    summary = {}
    for solver in SOLVERS:
        sdir = run_dir / "stage5" / f"enh_simple__solver_{solver}"
        tc = time.time()
        print(f"\n=== enh:simple -> {solver} ({len(rows)} issues) ===", flush=True)
        preds = solve(solver, rows, sdir, LLM)
        ne = sum(1 for inst in rows
                 if (preds.get(inst["instance_id"], {}).get("model_patch", "") or "").strip())
        summary[solver] = {"n_nonempty": ne, "n": len(rows)}
        print(f"[enh:simple -> {solver}] {ne}/{len(rows)} non-empty  ({(time.time()-tc)/3600:.2f} h)", flush=True)

    out = {"tag": a.tag, "llm": LLM, "enhancer": ENHANCER, "n": len(instances),
           "truly_enhanced": n_ok, "solvers": summary, "elapsed_h": (time.time()-t0)/3600}
    (run_dir.parent / "simple_enh_result.json").write_text(json.dumps(out, indent=2))
    print(f"\n=== DONE ({out['elapsed_h']:.1f} h) === truly enhanced: {n_ok}/{len(instances)} | "
          + ", ".join(f"{s}={v['n_nonempty']}/{v['n']}" for s, v in summary.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
