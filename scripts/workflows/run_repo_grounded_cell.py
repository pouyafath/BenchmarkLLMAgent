#!/usr/bin/env python3
"""
Test the repo-grounded enhancer: baseline vs enh:repo_grounded, same solver, same model.

This is the experiment the paper's thesis actually calls for — an enhancer agent that
gets the SAME container and tools as the solver (repo at /testbed), with no oracle
access, versus solver-alone.

Usage:
  bench_env/bin/python scripts/workflows/run_repo_grounded_cell.py \
      --model qwen3:32b --base-url http://localhost:11435/v1 \
      --instances-file .secrets/sample5_rge.txt --tag rge_qwen3 --workers 2
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

ROOT = Path("/home/22pf2/BenchmarkLLMAgent"); sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--api-key", default="ollama")
    ap.add_argument("--instances-file", required=True)
    ap.add_argument("--tag", default="rge")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--max-iter", type=int, default=30)
    ap.add_argument("--enh-max-iter", type=int, default=30)
    ap.add_argument("--solve-timeout", type=int, default=1800)
    ap.add_argument("--enh-timeout", type=int, default=1800)
    ap.add_argument("--skip-baseline", action="store_true",
                    help="reuse a known baseline instead of re-running it")
    a = ap.parse_args()

    # Point the enhancer at the same LLM as the solver
    os.environ.update({
        "RGE_MODEL": a.model, "RGE_BASE_URL": a.base_url, "RGE_API_KEY": a.api_key,
        "RGE_MAX_ITER": str(a.enh_max_iter), "RGE_TIMEOUT": str(a.enh_timeout),
    })

    import scripts.workflows.run_matrix_test as rmt
    rmt.BASE_URL = a.base_url; rmt.API_KEY = a.api_key
    rmt.SOLVE_TIMEOUT = a.solve_timeout; rmt.ENH_TIMEOUT = a.enh_timeout
    rmt.SOLVE_MAX_ITER = a.max_iter
    rmt.WORKERS = a.workers
    rmt.SOLVER_WORKERS = {k: a.workers for k in rmt.SOLVER_WORKERS}
    os.environ.update({
        "OH_SOLVER_MODEL": a.model, "OH_SOLVER_BASE_URL": a.base_url,
        "OH_SOLVER_API_KEY": a.api_key, "OH_SOLVER_TIMEOUT": str(a.solve_timeout),
        "OH_SOLVER_MAX_ITER": str(a.max_iter),
    })
    from scripts.workflows.run_matrix_test import _load, enhance, solve

    all_inst = _load(str(ROOT/"data/matrix_sample382_node01.jsonl"))
    want = [l.strip() for l in Path(a.instances_file).read_text().splitlines() if l.strip()]
    by = {i["instance_id"]: i for i in all_inst}
    inst = [by[i] for i in want if i in by]
    missing = [i for i in want if i not in by]
    if missing: print(f"[warn] not in dataset: {missing}", flush=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    mdir = a.model.replace("/", "_").replace(":", "_").replace(".", "")
    rd = ROOT/"runs"/f"{a.tag}_{ts}"/mdir
    rd.mkdir(parents=True, exist_ok=True)
    os.environ["RGE_WORK_DIR"] = str(rd/"stage4_repo_grounded_work")
    print(f"[rge cell] model={a.model} n={len(inst)} workers={a.workers} "
          f"solve_cap={a.max_iter} enh_cap={a.enh_max_iter} -> {rd}", flush=True)

    t0 = time.time()
    if not a.skip_baseline:
        print("=== BASELINE: openhands on original ===", flush=True)
        bp = solve("openhands", inst, rd/"baseline__solver_openhands", a.model)
        bne = sum(1 for i in inst if (bp.get(i["instance_id"], {}).get("model_patch", "") or "").strip())
        print(f"[baseline] non-empty {bne}/{len(inst)}  ({(time.time()-t0)/60:.1f} min)", flush=True)

    print("=== ENHANCE: repo_grounded (agent explores /testbed) ===", flush=True)
    rows, nok = enhance("repo_grounded", inst, rd/"stage4_repo_grounded", a.model)
    print(f"[enhance:repo_grounded] {nok}/{len(inst)} truly enhanced", flush=True)

    # surface the enhancer's own verification metadata
    meta_path = rd/"stage4_repo_grounded"/"enhanced_repo_grounded.jsonl"
    if meta_path.exists():
        print("--- enhancer verification ---", flush=True)
        for line in open(meta_path):
            line = line.strip()
            if not line: continue
            try: d = json.loads(line)
            except Exception: continue
            # run_matrix_test.enhance() drops enhancement_metadata, so read the
            # sidecar the enhancer writes into its per-instance work dir.
            m = d.get("enhancement_metadata", {}) or {}
            side = Path(os.environ["RGE_WORK_DIR"])/str(d.get("instance_id",""))/"meta.json"
            if side.exists():
                try: m = json.loads(side.read_text())
                except Exception: pass
            print(f"    {d.get('instance_id','?'):<45} ok={d.get('_enh_ok')} "
                  f"len_ratio={m.get('len_ratio')} refs={m.get('refs_verified')}/{m.get('refs_cited')} "
                  f"bad={m.get('refs_bad')} {('ERR: '+str(m.get('error'))) if m.get('error') else ''}",
                  flush=True)

    print("=== ENHANCED SOLVE: openhands on enh:repo_grounded ===", flush=True)
    ep = solve("openhands", rows, rd/"enh_repo_grounded__solver_openhands", a.model)
    ene = sum(1 for i in rows if (ep.get(i["instance_id"], {}).get("model_patch", "") or "").strip())
    print(f"[enhanced] non-empty {ene}/{len(rows)}", flush=True)
    print(f"DONE model={a.model} enhanced_ne={ene} ({(time.time()-t0)/60:.1f} min)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
