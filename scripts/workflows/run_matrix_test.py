#!/usr/bin/env python3
"""
PART 2 (Stages 4-6) — enhancer x solver MATRIX health-check runner.
Reproducible on GPU-01 and GPU-02. Uses ONLY the private Ollama (:11435, all 8 GPUs);
never the shared :11434.

What it does, for each LLM you pass:
  Stage 4 (enhance):  each enhancer in ENHANCERS rewrites every sample issue.
  Stage 5 (solve):    each solver in SOLVERS produces a patch for
                        - baseline (original issue)
                        - every enhanced variant
  Stage 6 (evaluate): light health signal = was a NON-EMPTY patch produced?
                        (full SWE-bench F2P/P2P scoring is a separate follow-up step.)

Conditions per LLM = (1 baseline + |ENHANCERS|) issue-states  x  |SOLVERS| solvers.
Default 3x3: (1+3) x 3 = 12 conditions.

Every condition is isolated: one failing enhancer/solver never aborts the matrix —
the failure is captured so the health report shows exactly what broke.

Usage:
  python scripts/workflows/run_matrix_test.py \
      --dataset data/matrix_sample3.jsonl \
      --llms qwen3:32b qwen3-coder:30b
"""
from __future__ import annotations
import argparse, os, json, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Fixed config (reproducible on both nodes) ─────────────────────────────────
BASE_URL    = "http://localhost:11435/v1"     # private Ollama, all 8 GPUs
OLLAMA_HTTP = "http://localhost:11435"
API_KEY     = "ollama"
ENHANCERS   = ["openhands", "swe_agent", "aider"]
# Re-run control. A partial re-run (e.g. after fixing two enhancers) should not redo
# conditions that are already valid, which would double the compute for nothing.
#   MATRIX_ENHANCERS=openhands,aider   restrict to these enhancers
#   MATRIX_SKIP_BASELINE=1             skip the baseline state (already scored)
if os.environ.get("MATRIX_ENHANCERS"):
    ENHANCERS = [e.strip() for e in os.environ["MATRIX_ENHANCERS"].split(",") if e.strip()]
SKIP_BASELINE = os.environ.get("MATRIX_SKIP_BASELINE", "") == "1"
SOLVERS     = ["openhands", "swe_agent", "aider"]
WORKERS       = 4          # default; box measured ~80% idle at 2 (GPUs 22%). Override --workers
                           # (use 8 with OLLAMA_NUM_PARALLEL=8 for ~3-4x). See WORKFLOW.md §8.
ENH_TIMEOUT   = 1800       # enhancer wall-clock per issue (repo-grounded agents
                           # explore a container; 600s starved aider entirely)
ENH_MAX_ITER  = 30
SOLVE_TIMEOUT = 3600       # solver wall-clock per issue (raised 1800->3600 on 2026-06-22:
                           # slow iterative solvers timed out under concurrency in the 50-run)
# Per-solver concurrency: slow iterative solvers (openhands/swe_agent make ~30 sequential LLM
# calls) starve and time out at high --workers. Default --workers is the fallback; these override
# per solver. See WORKFLOW.md §8.
# 2026-06-29: lowered aider 8->4. On the new-50 (heavier repos) aider at workers=8 also starved on
# Ollama contention and hit the 3600s wall on 27 cells; re-solving at workers=4 recovered 20/27
# (median 881s, 1 genuine timeout). aider=8 is only safe on light repos — use 4 for unknown/large sets.
SOLVER_WORKERS = {"openhands": 4, "swe_agent": 4, "aider": 4}
SOLVE_MAX_ITER= 30

NFS_RESULTS = Path("/data/22pf2_data/gpu_matrix_results")

RUN_DIR = None
LOG_FILE = None


def _now():  return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
def log(msg, lvl="INFO"):
    line = f"[{_now()}] [{lvl}] {msg}"
    print(line, flush=True)
    if LOG_FILE:
        with open(LOG_FILE, "a") as f: f.write(line + "\n")
def log_section(t): log("="*70); log(t); log("="*70)
def _load(p): return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]
def _sr(i):
    r = dict(i)
    if r.get("docker_image"): r["image_name"] = r["docker_image"]
    return r
def _disk_swap():
    s = os.statvfs("/"); free = s.f_bavail*s.f_frsize/1024**3
    try:
        mi = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo") if ":" in l}
        swap = (mi["SwapTotal"]-mi["SwapFree"])/1024**2
    except Exception: swap = -1
    return free, swap


def set_llm_env(llm: str):
    """Point every enhancer + solver at the private Ollama and the given model."""
    bare = llm                       # openhands / swe_agent add 'openai/' themselves
    prefixed = f"openai/{llm}"        # aider/litellm needs the explicit prefix
    os.environ.update({
        "USE_OLLAMA": "1", "OLLAMA_MODEL": bare, "OLLAMA_BASE_URL": OLLAMA_HTTP,
        # enhancers
        "OPENHANDS_MODEL": bare, "OPENHANDS_BASE_URL": BASE_URL, "OPENHANDS_API_KEY": API_KEY,
        "OPENHANDS_TIMEOUT": str(ENH_TIMEOUT), "OPENHANDS_MAX_ITER": str(ENH_MAX_ITER),
        "SWEAGENT_MODEL": bare, "SWEAGENT_BASE_URL": BASE_URL, "SWEAGENT_API_KEY": API_KEY,
        "SWEAGENT_TIMEOUT": str(ENH_TIMEOUT), "SWEAGENT_MAX_STEPS": str(ENH_MAX_ITER),
        # trae / mini default to gpt-5.4-mini on api.openai.com; pin them local too
        "TRAE_MODEL": bare, "TRAE_BASE_URL": BASE_URL, "TRAE_API_KEY": API_KEY,
        "TRAE_TIMEOUT": str(ENH_TIMEOUT), "TRAE_MAX_STEPS": str(ENH_MAX_ITER),
        "MINI_MODEL": bare, "MINI_BASE_URL": BASE_URL, "MINI_API_KEY": API_KEY,
        "MINI_TIMEOUT": str(ENH_TIMEOUT), "MINI_MAX_STEPS": str(ENH_MAX_ITER),
        "AIDER_MODEL": prefixed, "AIDER_API_BASE": BASE_URL, "AIDER_API_KEY": API_KEY,
        "AIDER_TIMEOUT": str(ENH_TIMEOUT),
        "MINI_TIMEOUT": str(ENH_TIMEOUT),
        # solvers
        "OH_SOLVER_MODEL": bare, "OH_SOLVER_BASE_URL": BASE_URL, "OH_SOLVER_API_KEY": API_KEY,
        "OH_SOLVER_MAX_ITER": str(SOLVE_MAX_ITER), "OH_SOLVER_TIMEOUT": str(SOLVE_TIMEOUT),
        "SWEA_SOLVER_MODEL": bare, "SWEA_SOLVER_BASE_URL": BASE_URL, "SWEA_SOLVER_API_KEY": API_KEY,
        "SWEA_SOLVER_MAX_STEPS": str(SOLVE_MAX_ITER), "SWEA_SOLVER_WORKERS": str(WORKERS),
        "AIDER_SOLVER_MODEL": prefixed, "AIDER_SOLVER_BASE_URL": BASE_URL, "AIDER_SOLVER_API_KEY": API_KEY,
        "AIDER_SOLVER_TIMEOUT": str(SOLVE_TIMEOUT), "AIDER_SOLVER_WORKERS": str(WORKERS),
    })


def preflight(instances):
    log_section("PREFLIGHT")
    ok = True
    free, swap = _disk_swap()
    log(f"Disk free={free:.0f}GB on / | swap used={swap:.1f}GB")
    if free < 20: log("Disk LOW (<20GB) — clean before running", "ERROR"); ok = False
    # LLM endpoint
    try:
        import subprocess
        r = subprocess.run(["curl","-s","--max-time","90",f"{BASE_URL}/chat/completions",
            "-H","Content-Type: application/json","-d",json.dumps({"model":os.environ.get("OLLAMA_MODEL","qwen3:32b"),
            "messages":[{"role":"user","content":"Say OK"}],"max_tokens":64})],
            capture_output=True,text=True,timeout=120)
        resp = json.loads(r.stdout); msg = resp.get("choices",[{}])[0].get("message",{})
        c = (msg.get("content","") or "")+(msg.get("reasoning","") or "")
        log(f"LLM endpoint OK ({c[:40]!r})" if c.strip() else "LLM endpoint EMPTY response", "INFO" if c.strip() else "ERROR")
        ok = ok and bool(c.strip())
    except Exception as e:
        log(f"LLM endpoint FAILED: {e}", "ERROR"); ok = False
    # docker images
    import subprocess
    miss = 0
    for inst in instances:
        img = inst.get("docker_image","")
        if subprocess.run(["docker","image","inspect",img,"--format","{{.Id}}"],
                          capture_output=True).returncode != 0:
            miss += 1; log(f"  MISSING image: {img}", "ERROR")
    if miss: log(f"{miss}/{len(instances)} docker images missing", "ERROR"); ok = False
    else: log(f"All {len(instances)} docker images present")
    # importability of every enhancer + solver
    from src.enhancers.dispatcher import get_enhancer
    for e in ENHANCERS:
        if get_enhancer(e) is None: log(f"  enhancer '{e}' not found", "ERROR"); ok = False
    for s in SOLVERS:
        try: __import__(f"src.solvers.{ {'openhands':'openhands_solver','swe_agent':'swe_agent_solver','aider':'aider_solver'}[s] }", fromlist=["run_batch"])
        except Exception as ex: log(f"  solver '{s}' import failed: {ex}", "ERROR"); ok = False
    log(f"Enhancers={ENHANCERS} Solvers={SOLVERS}")
    return ok


def enhance(enhancer_id, instances, edir, llm):
    """Run one enhancer over all instances. Returns list of rows (enhanced or fallback)."""
    from src.enhancers.dispatcher import get_enhancer
    fn = get_enhancer(enhancer_id)
    edir.mkdir(parents=True, exist_ok=True)
    # Enhancers now run a containerised agent over the repository (minutes per instance),
    # so this loop is parallelised. It used to be sequential, which was fine when the
    # enhancers were sub-second text rewriters but costs hours at container speed.
    from concurrent.futures import ThreadPoolExecutor

    def _one(inst):
        iid = inst["instance_id"]; ps = inst.get("problem_statement",""); t0 = time.time()
        try:
            res = fn(inst)
            body = res.get("enhanced_body","") if isinstance(res, dict) else ""
            meta = res.get("enhancement_metadata",{}) if isinstance(res, dict) else {}
            ok = bool(body) and body.strip() != ps.strip() and meta.get("enhancer_type") != "error"
            err = meta.get("error","")
        except Exception as e:
            body, meta, ok, err = "", {"enhancer_type":"error","error":str(e)}, False, str(e)
        el = time.time() - t0
        row = dict(inst)
        if ok: row["problem_statement"] = body
        row["_enh_ok"] = ok; row["_enh_by"] = enhancer_id; row["_enh_err"] = err
        log(f"    [enh:{enhancer_id}] {iid}: {'OK' if ok else 'FALLBACK'} {el:.0f}s"
            + (f"  ({err[:60]})" if err else ""))
        return row

    ew = max(1, int(os.environ.get("ENH_WORKERS", str(WORKERS))))
    with ThreadPoolExecutor(max_workers=ew) as ex:
        rows = list(ex.map(_one, instances))
    n_ok = sum(1 for r in rows if r.get("_enh_ok"))
    from scripts.workflows.run_node1_full383_qwen3 import _dump  # reuse jsonl writer
    _dump(edir/f"enhanced_{enhancer_id}.jsonl", [_sr(r) for r in rows])
    log(f"  [enh:{enhancer_id}] {n_ok}/{len(instances)} truly enhanced")
    return rows, n_ok


def solve(solver_id, instances, sdir, llm):
    """Run one solver over all instances. Returns preds dict {iid: {model_patch,...}}."""
    sdir.mkdir(parents=True, exist_ok=True)
    insts = [_sr(i) for i in instances]
    preds_out = sdir / "preds.json"
    bare, prefixed = llm, f"openai/{llm}"
    w = SOLVER_WORKERS.get(solver_id, WORKERS)   # per-solver concurrency
    try:
        if solver_id == "openhands":
            from src.solvers.openhands_solver import run_batch as rb
            rb(insts, API_KEY, sdir/"work", preds_out, model=bare, base_url=BASE_URL,
               max_iter=SOLVE_MAX_ITER, timeout=SOLVE_TIMEOUT, workers=w)
        elif solver_id == "swe_agent":
            from src.solvers.swe_agent_solver import run_batch as rb
            rb(insts, API_KEY, sdir/"work", preds_out, model=bare, base_url=BASE_URL,
               max_steps=SOLVE_MAX_ITER, timeout=SOLVE_TIMEOUT, workers=w)
        elif solver_id == "aider":
            from src.solvers.aider_solver import run_batch as rb
            rb(insts, API_KEY, sdir/"work", preds_out, model=prefixed, base_url=BASE_URL,
               timeout=SOLVE_TIMEOUT, workers=w)
    except Exception as e:
        log(f"  [solve:{solver_id}] CRASHED: {e}", "ERROR")
        traceback.print_exc()
    preds = json.loads(preds_out.read_text()) if preds_out.exists() else {}
    return preds


def main():
    global RUN_DIR, LOG_FILE, WORKERS
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--llms", nargs="+", default=["qwen3:32b"])
    ap.add_argument("--tag", default="matrix")
    ap.add_argument("--workers", type=int, default=WORKERS, help="solver parallelism")
    ap.add_argument("--disk-floor", type=int, default=120,
                    help="GB; if root free drops below this before a condition, prune ephemeral "
                         "runtime images + build cache (never base images) to avoid ENOSPC")
    args = ap.parse_args()
    WORKERS = args.workers

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    RUN_DIR = ROOT / "runs" / f"{args.tag}_{ts}"
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE = RUN_DIR / "matrix.log"

    data = _load(args.dataset)
    # only instances whose Stage 1-3 image is present locally
    import subprocess
    local = set(subprocess.run(["docker","images","--format","{{.Repository}}:{{.Tag}}"],
                               capture_output=True,text=True).stdout.split())
    instances = [r for r in data if (r.get("docker_image","") or r.get("image_name","")) in local]
    log_section("MATRIX HEALTH-CHECK")
    log(f"Run dir:  {RUN_DIR}")
    log(f"Dataset:  {args.dataset} ({len(data)} total, {len(instances)} with local images)")
    log(f"LLMs:     {args.llms}")
    _states = ([] if SKIP_BASELINE else ['baseline']) + [f"enh:{e}" for e in ENHANCERS]
    log(f"Matrix:   {_states} states x {SOLVERS} solvers = "
        f"{len(_states)*len(SOLVERS)} conditions per LLM")
    for inst in instances:
        log(f"  issue: {inst['instance_id']} ({inst.get('language','?')})")

    if not instances:
        log("No instances with local images — run Part 1 (build_images) first.", "ERROR"); return 1

    results = {}   # results[llm][state][solver] = {n_nonempty, issues:{iid:bool}}
    t_start = time.time()

    for llm in args.llms:
        set_llm_env(llm)
        if not preflight(instances):
            log(f"Preflight FAILED for {llm} — skipping", "ERROR"); continue
        log_section(f"LLM = {llm}")
        llm_dir = RUN_DIR / llm.replace(":","_").replace("/","_")
        results[llm] = {}

        # ── Stage 4: enhance with each enhancer ──────────────────────────────
        enhanced = {}   # enhancer_id -> rows
        enh_ok = {}
        for e in ENHANCERS:
            rows, n_ok = enhance(e, instances, llm_dir/"stage4"/e, llm)
            enhanced[e] = rows; enh_ok[e] = n_ok

        # ── Stage 5: each solver x {baseline + each enhanced} ────────────────
        states = {} if SKIP_BASELINE else {"baseline": instances}
        for e in ENHANCERS: states[f"enh:{e}"] = enhanced[e]
        for solver in SOLVERS:
            for state_name, state_insts in states.items():
                cond = f"{state_name} -> {solver}"
                free, swap = _disk_swap()
                # Mid-run disk guard: a 10-20 issue matrix accumulates many ~10GB
                # ghcr.io/openhands/runtime images. If disk gets low, prune those + build
                # cache (they rebuild on demand) — NEVER touch pouya/stage2_2026 base images.
                if free < args.disk_floor:
                    log(f"[{llm}] disk {free:.0f}GB < floor {args.disk_floor}GB — pruning ephemeral images/cache", "WARN")
                    import subprocess as _sp
                    oh = [l.strip() for l in _sp.run(["docker","images","--format","{{.Repository}}:{{.Tag}}",
                          "ghcr.io/openhands/runtime"],capture_output=True,text=True).stdout.split("\n") if l.strip()]
                    if oh: _sp.run(["docker","rmi","-f"]+oh, capture_output=True)
                    _sp.run(["docker","builder","prune","-f"], capture_output=True)
                    free, swap = _disk_swap()
                    log(f"[{llm}] after prune: disk {free:.0f}GB free")
                log(f"[{llm}] CONDITION {cond}  (disk {free:.0f}GB free, swap {swap:.1f}GB)")
                sdir = llm_dir / "stage5" / f"{state_name.replace(':','_')}__solver_{solver}"
                preds = solve(solver, state_insts, sdir, llm)
                issues = {}
                for inst in state_insts:
                    iid = inst["instance_id"]
                    patch = (preds.get(iid, {}).get("model_patch","") or "").strip()
                    issues[iid] = bool(patch)
                n_ne = sum(issues.values())
                results[llm].setdefault(state_name, {})[solver] = {
                    "n_nonempty": n_ne, "n_total": len(state_insts), "issues": issues}
                log(f"[{llm}] {cond}: {n_ne}/{len(state_insts)} non-empty patches")

        results[llm]["_enhancement_ok"] = enh_ok

    t_total = time.time() - t_start

    # ── Report ───────────────────────────────────────────────────────────────
    log_section("MATRIX RESULT (non-empty patches per condition)")
    for llm in args.llms:
        if llm not in results: continue
        log(f"\n### LLM = {llm}")
        log(f"Enhancement success (truly-enhanced / {len(instances)}): "
            + ", ".join(f"{e}={results[llm]['_enhancement_ok'].get(e,0)}" for e in ENHANCERS))
        header = "state \\ solver      | " + " | ".join(f"{s:^10}" for s in SOLVERS)
        log(header); log("-"*len(header))
        for state in ["baseline"]+[f"enh:{e}" for e in ENHANCERS]:
            cells = []
            for s in SOLVERS:
                cell = results[llm].get(state,{}).get(s,{})
                cells.append(f"{cell.get('n_nonempty','-')}/{cell.get('n_total','-')}".center(10))
            log(f"{state:<20}| " + " | ".join(cells))
    log(f"\nTotal time: {t_total/60:.1f} min ({t_total/3600:.2f} h)")

    out = {"timestamp":_now(), "host":os.uname().nodename, "llms":args.llms,
           "enhancers":ENHANCERS, "solvers":SOLVERS,
           "n_instances":len(instances),
           "instances":[i["instance_id"] for i in instances],
           "results":results, "total_seconds":round(t_total,1)}
    (RUN_DIR/"matrix_result.json").write_text(json.dumps(out, indent=2))
    log(f"Wrote {RUN_DIR/'matrix_result.json'}")

    try:
        nfs = NFS_RESULTS / RUN_DIR.name; nfs.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(RUN_DIR/"matrix_result.json", nfs/"matrix_result.json")
        shutil.copy2(LOG_FILE, nfs/"matrix.log")
        log(f"Copied results to NFS: {nfs}")
    except Exception as e:
        log(f"NFS copy failed: {e}", "WARN")

    # Post-run cleanup: drop ephemeral openhands runtime images (never the base images)
    try:
        r = subprocess.run(["docker","images","--format","{{.Repository}}:{{.Tag}}","ghcr.io/openhands/runtime"],
                           capture_output=True,text=True)
        oh = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
        if oh:
            subprocess.run(["docker","rmi","-f"]+oh, capture_output=True)
            log(f"Post-run cleanup: removed {len(oh)} ghcr.io/openhands/runtime images")
    except Exception as e:
        log(f"Post-run cleanup failed: {e}", "WARN")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FATAL: {e}", flush=True); traceback.print_exc(); sys.exit(1)
