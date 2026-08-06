#!/usr/bin/env python3
"""
TARGETED RERUN — re-solve ONLY the slow iterative solvers (openhands, swe_agent) across all 4
issue-states, REUSING the Stage-4 enhanced texts from a prior matrix run.

Why: the 50-issue matrix (matrix50_node01_20260619) ran at --workers 8, which starved the slow
iterative solvers (each makes ~30 sequential LLM calls) -> 1800 s timeouts -> empty patches
(openhands 6/200, swe_agent 0/200). The fast aider solver was unaffected (97/200, valid) and the
Stage-4 enhanced issue texts are intact. So we keep the aider column + reuse enhancement, and only
re-solve the two slow columns under the CORRECTED config (per-solver workers=4, timeout 3600 s),
imported verbatim from run_matrix_test.py.

Final matrix = these reran openhands/swe_agent columns  +  the kept aider column from the original.

Usage:
  bench_env/bin/python scripts/workflows/rerun_slow_solvers.py \
      --orig-run runs/matrix50_node01_20260619_185640 \
      --dataset  data/matrix_sample50_node01.jsonl \
      --limit 10 --tag rerun_slow10
  # then, if healthy, drop --limit for the full 50.
"""
from __future__ import annotations
import argparse, json, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
sys.path.insert(0, str(ROOT))
# reuse the VALIDATED config + functions (workers/timeout live as module globals there)
from scripts.workflows.run_matrix_test import (
    set_llm_env, preflight, solve, _load, _disk_swap,
    SOLVE_TIMEOUT, SOLVER_WORKERS,
)

LLM = "qwen3:32b"
SOLVERS_TO_RERUN = ["openhands", "swe_agent"]
STATE_ORDER = ["baseline", "enh:openhands", "enh:swe_agent", "enh:aider"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig-run", required=True, help="prior matrix run dir (has qwen3_32b/stage4/*)")
    ap.add_argument("--dataset", required=True, help="original baseline dataset (un-enhanced rows)")
    ap.add_argument("--limit", type=int, default=0, help="first-N issues; 0 = all")
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()

    orig = Path(a.orig_run); s4 = orig / "qwen3_32b" / "stage4"
    baseline = _load(a.dataset)
    if a.limit:
        baseline = baseline[:a.limit]
    ids = [r["instance_id"] for r in baseline]
    print(f"[{datetime.now(timezone.utc):%H:%M:%S}] {len(ids)} issues selected "
          f"(limit={a.limit or 'all'}); first: {ids[0]}", flush=True)

    def load_enh(e):
        by = {r["instance_id"]: r for r in _load(s4 / e / f"enhanced_{e}.jsonl")}
        missing = [i for i in ids if i not in by]
        if missing:
            print(f"  WARN: {len(missing)} ids missing from enh:{e} — using baseline for those")
        return [by.get(i) or next(b for b in baseline if b["instance_id"] == i) for i in ids]

    states = {"baseline": baseline,
              "enh:openhands": load_enh("openhands"),
              "enh:swe_agent": load_enh("swe_agent"),
              "enh:aider": load_enh("aider")}
    # sanity: every state must cover the same id set, same order
    for sn, st in states.items():
        assert [r["instance_id"] for r in st] == ids, f"state {sn} id mismatch"

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = ROOT / "runs" / f"{a.tag}_{ts}"
    llm_dir = run_dir / "qwen3_32b"
    llm_dir.mkdir(parents=True, exist_ok=True)
    print(f"Run dir: {run_dir}")
    print(f"Config (from run_matrix_test): SOLVE_TIMEOUT={SOLVE_TIMEOUT}s  "
          f"workers={ {s: SOLVER_WORKERS.get(s) for s in SOLVERS_TO_RERUN} }", flush=True)

    set_llm_env(LLM)
    allinsts = {r["instance_id"]: r for st in states.values() for r in st}
    if not preflight(list(allinsts.values())):
        print("PREFLIGHT FAILED — aborting"); return 1

    free, swap = _disk_swap()
    print(f"Disk free {free:.0f}GB on / (Docker root now on /home) | swap {swap:.1f}GB", flush=True)

    matrix = {sn: {} for sn in STATE_ORDER}
    t0 = time.time()
    for solver in SOLVERS_TO_RERUN:
        for sname in STATE_ORDER:
            insts = states[sname]
            sdir = llm_dir / "stage5" / f"{sname.replace(':', '_')}__solver_{solver}"
            tc = time.time()
            print(f"\n=== CONDITION {sname} -> {solver}  ({len(insts)} issues) ===", flush=True)
            preds = solve(solver, insts, sdir, LLM)
            issues = {i: bool((preds.get(i, {}).get("model_patch", "") or "").strip()) for i in ids}
            ne = sum(issues.values())
            matrix[sname][solver] = {"n_nonempty": ne, "n_total": len(ids), "issues": issues}
            print(f"[{sname} -> {solver}] {ne}/{len(ids)} non-empty  ({time.time()-tc:.0f}s)", flush=True)

    dt = time.time() - t0
    # ── report ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"RERUN (slow solvers, corrected config) — {len(ids)} issues — {dt/3600:.2f} h")
    print("=" * 70)
    hdr = "state \\ solver      | " + " | ".join(f"{s:^11}" for s in SOLVERS_TO_RERUN)
    print(hdr); print("-" * len(hdr))
    for sname in STATE_ORDER:
        cells = [f"{matrix[sname][s]['n_nonempty']}/{matrix[sname][s]['n_total']}".center(11)
                 for s in SOLVERS_TO_RERUN]
        print(f"{sname:<20}| " + " | ".join(cells))

    out = {"tag": a.tag, "llm": LLM, "n_issues": len(ids), "ids": ids,
           "orig_run": str(orig), "solvers_reran": SOLVERS_TO_RERUN,
           "solve_timeout": SOLVE_TIMEOUT,
           "workers": {s: SOLVER_WORKERS.get(s) for s in SOLVERS_TO_RERUN},
           "elapsed_h": dt / 3600, "matrix": matrix}
    (run_dir / "rerun_result.json").write_text(json.dumps(out, indent=2))
    print(f"\nWrote {run_dir/'rerun_result.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
