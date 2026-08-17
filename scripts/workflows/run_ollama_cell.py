#!/usr/bin/env python3
"""
Run one enhancer x solver cell (enh:Aider -> sol:OpenHands) on a LOCAL Ollama model via the private
:11435 OpenAI-compat endpoint. Baseline + enhanced, same as run_openai_cell.py but pointed at Ollama.
Usage:
  bench_env/bin/python scripts/workflows/run_ollama_cell.py --model qwen3:32b \
      --instances-file .secrets/sample20.txt --tag ollama_sample20 --workers 4
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
ROOT = Path("/home/22pf2/BenchmarkLLMAgent"); sys.path.insert(0, str(ROOT))
BASE = "http://localhost:11435/v1"; KEY = "ollama"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--instances-file", required=True)
    ap.add_argument("--tag", default="ollama_cell")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-iter", type=int, default=30)
    ap.add_argument("--enh-timeout", type=int, default=600)
    ap.add_argument("--solve-timeout", type=int, default=1800)
    ap.add_argument("--base-url", default=BASE, help="Ollama OpenAI-compat endpoint (:11435 private, :11434 shared)")
    a = ap.parse_args()

    import scripts.workflows.run_matrix_test as rmt
    rmt.BASE_URL = a.base_url; rmt.API_KEY = KEY
    rmt.SOLVE_TIMEOUT = a.solve_timeout; rmt.ENH_TIMEOUT = a.enh_timeout
    rmt.SOLVE_MAX_ITER = a.max_iter
    rmt.WORKERS = a.workers; rmt.SOLVER_WORKERS = {k: a.workers for k in rmt.SOLVER_WORKERS}
    os.environ.update({
        "USE_OLLAMA": "1", "OLLAMA_MODEL": a.model, "OLLAMA_BASE_URL": a.base_url.replace("/v1", ""),
        "AIDER_MODEL": f"openai/{a.model}", "AIDER_API_BASE": a.base_url, "AIDER_API_KEY": KEY, "AIDER_TIMEOUT": str(a.enh_timeout),
        "OH_SOLVER_MODEL": a.model, "OH_SOLVER_BASE_URL": a.base_url, "OH_SOLVER_API_KEY": KEY,
        "OH_SOLVER_TIMEOUT": str(a.solve_timeout), "OH_SOLVER_MAX_ITER": str(a.max_iter),
    })
    from scripts.workflows.run_matrix_test import _load, enhance, solve

    all_inst = _load(str(ROOT / "data" / "matrix_sample382_node01.jsonl"))
    want = set(l.strip() for l in Path(a.instances_file).read_text().splitlines() if l.strip())
    by = {i["instance_id"]: i for i in all_inst}
    inst = [by[i] for i in want if i in by]
    ts = time.strftime("%Y%m%d_%H%M%S")
    mdir = a.model.replace("/", "_").replace(":", "_").replace(".", "")
    rd = ROOT / "runs" / f"{a.tag}_{ts}" / mdir
    rd.mkdir(parents=True, exist_ok=True)
    print(f"[ollama cell] model={a.model} n={len(inst)} workers={a.workers} cap={a.max_iter} -> {rd}", flush=True)

    t0 = time.time()
    print("=== BASELINE: openhands on original ===", flush=True)
    bp = solve("openhands", inst, rd / "baseline__solver_openhands", a.model)
    bne = sum(1 for i in inst if (bp.get(i["instance_id"], {}).get("model_patch", "") or "").strip())
    print(f"[baseline] non-empty {bne}/{len(inst)}  ({(time.time()-t0)/60:.1f} min)", flush=True)

    print("=== ENHANCE: aider ===", flush=True)
    rows, nok = enhance("aider", inst, rd / "stage4_aider", a.model)
    print(f"[enhance:aider] {nok}/{len(inst)} truly enhanced", flush=True)

    print("=== ENHANCED SOLVE: openhands on enh:aider ===", flush=True)
    ep = solve("openhands", rows, rd / "enh_aider__solver_openhands", a.model)
    ene = sum(1 for i in rows if (ep.get(i["instance_id"], {}).get("model_patch", "") or "").strip())
    print(f"[enhanced] non-empty {ene}/{len(rows)}", flush=True)
    print(f"DONE model={a.model} baseline_ne={bne} enhanced_ne={ene} ({(time.time()-t0)/60:.1f} min)", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
