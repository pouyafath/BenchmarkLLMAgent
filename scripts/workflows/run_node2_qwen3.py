#!/usr/bin/env python3
"""
Node2 stages 4-6: qwen3:32b on 878 issues (GPU-02).
Run from: ~/BenchmarkLLMAgent/
Usage:
  python scripts/workflows/run_node2_qwen3.py             # all 878
  python scripts/workflows/run_node2_qwen3.py --pilot 50   # first 50 only
"""
from __future__ import annotations
import argparse, json, os, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Config ───────────────────────────────────────────────────────────────────
MODEL       = "qwen3:32b"
BASE_URL    = "http://localhost:11434/v1"
API_KEY     = "ollama"
WORKERS     = 4
TIMEOUT     = 3600
ENH_PARALLEL= 2
MAX_ITER    = 30

DATASET = ROOT / "data/node2_stage3_p2p878_20260610.jsonl"
NFS_RESULTS = Path("/data/22pf2_data/gpu02_results")

os.environ.update({
    "USE_OLLAMA": "1", "OLLAMA_MODEL": MODEL,
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OPENHANDS_BASE_URL": BASE_URL, "OPENHANDS_MODEL": MODEL,
    "OH_SOLVER_MAX_ITER": str(MAX_ITER),
})

# ── Helpers ──────────────────────────────────────────────────────────────────
def _now():  return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
def _load(p): return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]
def _dump(p, rows):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p,"w") as f:
        for r in rows: f.write(json.dumps(r, sort_keys=True)+"\n")
def _sr(i):
    r=dict(i)
    if r.get("docker_image"): r["image_name"]=r["docker_image"]
    return r

RUN_DIR = None
LOG_FILE = None
RESOURCE_LOG = None

def log(msg, lvl="INFO"):
    line = f"[{_now()}] [{lvl}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE,"a") as f: f.write(line+"\n")
    except: pass

def log_section(t): log("="*70); log(f"  {t}"); log("="*70)

def log_resources(stage, idx=0, total=0):
    import subprocess
    try:
        docker_ps = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True, timeout=10)
        docker_count = len(docker_ps.stdout.strip().split("\n")) if docker_ps.stdout.strip() else 0
    except: docker_count = -1
    try:
        with open("/proc/meminfo") as f:
            mi = {}
            for line in f:
                parts = line.split()
                if parts[0] in ("MemTotal:", "MemAvailable:"):
                    mi[parts[0].rstrip(":")] = int(parts[1])
        mem_total_gb = mi.get("MemTotal", 0) / 1024 / 1024
        mem_avail_gb = mi.get("MemAvailable", 0) / 1024 / 1024
        mem_used_gb = mem_total_gb - mem_avail_gb
    except: mem_total_gb = mem_avail_gb = mem_used_gb = -1
    try: load1, load5, load15 = os.getloadavg()
    except: load1 = load5 = load15 = -1

    entry = {
        "timestamp": _now(), "stage": stage, "idx": idx, "total": total,
        "docker_containers": docker_count,
        "mem_total_gb": round(mem_total_gb, 1),
        "mem_used_gb": round(mem_used_gb, 1),
        "mem_avail_gb": round(mem_avail_gb, 1),
        "load_1m": round(load1, 1), "load_5m": round(load5, 1), "load_15m": round(load15, 1),
    }
    try:
        with open(RESOURCE_LOG, "a") as f: f.write(json.dumps(entry) + "\n")
    except: pass
    log(f"  [RESOURCES] Docker={docker_count} | RAM={mem_used_gb:.0f}/{mem_total_gb:.0f}GB ({mem_avail_gb:.0f}GB free) | Load={load1:.1f}/{load5:.1f}/{load15:.1f}")

# ── Preflight ────────────────────────────────────────────────────────────────
def preflight(instances):
    log_section("PRE-FLIGHT CHECKS")
    import subprocess; ok=True

    # Disk space check
    import shutil
    total, used, free = shutil.disk_usage("/")
    free_gb = free / (1024**3)
    if free_gb < 50:
        log(f"DISK: Only {free_gb:.0f}GB free on root — need at least 50GB", "ERROR")
        log(f"  Run: docker builder prune --all -f && docker container prune -f", "ERROR")
        ok = False
    else:
        log(f"DISK: {free_gb:.0f}GB free on root — OK")
    # /tmp guard — Docker build cache filling the disk killed runs on 2026-06-15
    try:
        ts = os.statvfs("/tmp")
        tmp_free_gb = ts.f_bavail * ts.f_frsize / 1024**3
        tmp_total_gb = ts.f_blocks * ts.f_frsize / 1024**3
        if tmp_free_gb < 20:
            log(f"/tmp LOW: {tmp_free_gb:.0f}GB free of {tmp_total_gb:.0f}GB (<20GB) "
                f"— run `docker builder prune -f` before launching", "ERROR"); ok = False
        else:
            log(f"/tmp: {tmp_free_gb:.0f}GB free of {tmp_total_gb:.0f}GB")
    except Exception as e:
        log(f"/tmp check failed: {e}", "WARN")

    docker_ps = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True)
    running = len(docker_ps.stdout.strip().split("\n")) if docker_ps.stdout.strip() else 0
    if running > 2:
        log(f"WARNING: {running} Docker containers already running", "WARN")

    try:
        r=subprocess.run(["curl","-s","--max-time","60",f"{BASE_URL}/chat/completions",
            "-H","Content-Type: application/json","-d",json.dumps({"model":MODEL,
            "messages":[{"role":"user","content":"Say OK"}],"max_tokens":256,"temperature":0.3})],
            capture_output=True,text=True,timeout=90)
        resp=json.loads(r.stdout)
        msg=resp.get("choices",[{}])[0].get("message",{})
        c=(msg.get("content","") or "") + (msg.get("reasoning","") or "")
        if c.strip(): log(f"LLM: {MODEL} OK ({c[:40]})")
        else: log(f"LLM: {MODEL} EMPTY response!","ERROR"); ok=False
    except Exception as e: log(f"LLM: FAILED — {e}","ERROR"); ok=False

    missing=0
    for inst in instances:
        img=inst.get("docker_image","")
        r=subprocess.run(["docker","image","inspect",img,"--format","{{.Id}}"],capture_output=True,text=True)
        if r.returncode!=0: missing+=1
    if missing: log(f"Docker: {missing}/{len(instances)} images MISSING","ERROR"); ok=False
    else: log(f"Docker: all {len(instances)} images present")

    try:
        from src.enhancers.dispatcher import get_enhancer; get_enhancer("openhands"); log("Enhancer: OK")
    except Exception as e: log(f"Enhancer: FAIL — {e}","ERROR"); ok=False
    try:
        from src.solvers.openhands_solver import run_batch; log("Solver: OK")
    except Exception as e: log(f"Solver: FAIL — {e}","ERROR"); ok=False

    log_resources("preflight")
    return ok

# ── Stage 4 ──────────────────────────────────────────────────────────────────
def run_stage4(instances):
    N = len(instances)
    log_section(f"STAGE 4: ENHANCEMENT ({MODEL}) — {N} inst, {ENH_PARALLEL} parallel")
    from src.enhancers.dispatcher import get_enhancer
    enhancer = get_enhancer("openhands")
    all_map, enh, fb = {}, [], []

    def _do(inst):
        iid=inst["instance_id"]; ps=inst.get("problem_statement",""); t0=time.time()
        try:
            res=enhancer(inst); el=time.time()-t0
            body=res.get("enhanced_body","") if isinstance(res,dict) else ""
            meta=res.get("enhancement_metadata",{}) if isinstance(res,dict) else {}
            changed=bool(body) and body.strip()!=ps.strip() and meta.get("enhancer_type")!="error"
            return inst,res,el,changed
        except Exception as e:
            return inst,{"enhancement_metadata":{"error":str(e),"enhancer_type":"error"}},time.time()-t0,False

    with ThreadPoolExecutor(max_workers=ENH_PARALLEL) as pool:
        futs={pool.submit(_do,i):i for i in instances}
        dm={}
        done_count = 0
        for f in as_completed(futs):
            inst,res,el,ok=f.result()
            dm[inst["instance_id"]]=(inst,res,el,ok)
            done_count += 1
            iid = inst["instance_id"]
            status = "ENHANCED" if ok else "FALLBACK"
            log(f"  [{done_count}/{N}] {iid}: {status} {el:.0f}s")
            if done_count % 50 == 0:
                log_resources("stage4_progress", done_count, N)

    for inst in instances:
        iid=inst["instance_id"]; ps=inst.get("problem_statement","")
        inst,res,el,ok=dm[iid]
        meta=res.get("enhancement_metadata",{}) if isinstance(res,dict) else {}
        body=res.get("enhanced_body","") if isinstance(res,dict) else ""
        row=dict(inst)
        if ok:
            row["problem_statement"]=body; row["enhanced_title"]=res.get("enhanced_title")
            row["enhancement_metadata"]=meta; row["_enhancement_valid"]=True; row["_fallback_used"]=False
            enh.append(row)
        else:
            row["enhancement_metadata"]=meta; row["_enhancement_valid"]=False; row["_fallback_used"]=True
            fb.append(row)
        all_map[iid]=row

    all_rows=[all_map[i["instance_id"]] for i in instances]
    s4=RUN_DIR/"stage4_enhanced"; s4.mkdir(parents=True,exist_ok=True)
    _dump(s4/"baseline.jsonl",[_sr(i) for i in instances])
    _dump(s4/"enhanced_all.jsonl",[_sr(r) for r in all_rows])
    (s4/"fallback_manifest.json").write_text(json.dumps({
        "total":N,"truly_enhanced":len(enh),"fallback_count":len(fb),
        "fallback_ids":sorted(r["instance_id"] for r in fb),
        "enhanced_ids":sorted(r["instance_id"] for r in enh)},indent=2))
    log(f"  Stage 4 DONE: {len(enh)}/{N} enhanced, {len(fb)} fallback (enhancer_error)")
    log_resources("stage4_done")
    return all_rows, enh, fb

# ── Stage 5 ──────────────────────────────────────────────────────────────────
def run_solver(label, instances, sdir):
    N = len(instances)
    log_section(f"STAGE 5: SOLVER ({label}) — {N} inst, {WORKERS} workers, max_iter={MAX_ITER}")
    sdir.mkdir(parents=True,exist_ok=True)
    instances=[_sr(i) for i in instances]; preds_out=sdir/"preds.json"
    from src.solvers.openhands_solver import run_batch
    t0=time.time()
    log_resources(f"solver_{label}_start")
    try:
        run_batch(instances,API_KEY,sdir/"work",preds_out,model=MODEL,base_url=BASE_URL,
                  max_iter=MAX_ITER,workers=WORKERS,timeout=TIMEOUT)
    except Exception as e:
        log(f"  Solver error: {e}","ERROR")
        traceback.print_exc()
    elapsed=time.time()-t0
    preds=json.loads(preds_out.read_text()) if preds_out.exists() else {}
    ne=0
    for iid,pred in sorted(preds.items()):
        p=(pred.get("model_patch","") or "").strip()
        if p: ne+=1; log(f"  {iid}: PATCH ({len(p)} chars)")
        else:
            log(f"  {iid}: EMPTY PATCH","WARN")
            lp=sdir/"work"/iid/"openhands.log"
            if lp.exists():
                c=lp.read_text(errors="replace")
                if "AgentStuckInLoopError" in c: log(f"    AgentStuckInLoopError","ERROR")
                if "reached maximum iteration" in c: log(f"    Max iterations ({MAX_ITER})","WARN")
    log(f"  Solver ({label}) DONE {elapsed:.0f}s: {ne}/{len(preds)} non-empty patches")
    log_resources(f"solver_{label}_done")
    return preds

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    global RUN_DIR, LOG_FILE, RESOURCE_LOG, BASE_URL

    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=int, default=0, help="Run only first N instances (0=all)")
    parser.add_argument("--dataset", type=str, default=str(DATASET), help="Path to input JSONL dataset")
    parser.add_argument("--base-url", type=str, default=BASE_URL, help="OpenAI-compatible base URL (Ollama)")
    args = parser.parse_args()

    BASE_URL = args.base_url
    _ollama_host = BASE_URL.replace("/v1", "")
    os.environ["OLLAMA_BASE_URL"] = _ollama_host
    os.environ["OPENHANDS_BASE_URL"] = BASE_URL

    DATASET_PATH = Path(args.dataset)
    data = _load(DATASET_PATH)
    if args.pilot > 0:
        data = data[:args.pilot]
        tag = f"node2_qwen3_pilot{args.pilot}"
    else:
        tag = "node2_qwen3_full"

    RUN_DIR = ROOT / "runs" / f"{tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    LOG_FILE = RUN_DIR / "test.log"
    RESOURCE_LOG = RUN_DIR / "resource_usage.jsonl"
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    N = len(data)
    log_section(f"NODE2 STAGES 4-6: {MODEL} — {N} instances, workers={WORKERS}")
    log(f"Run dir:  {RUN_DIR}")
    log(f"Model:    {MODEL} @ {BASE_URL}")
    log(f"Budget:   WORKERS={WORKERS}, ENH_PARALLEL={ENH_PARALLEL}, max_iter={MAX_ITER}")
    log(f"Dataset:  {DATASET_PATH} ({N} instances)")

    # Filter to instances with local Docker images
    import subprocess
    result = subprocess.run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
                            capture_output=True, text=True)
    local_images = set(result.stdout.strip().split("\n"))
    instances = [r for r in data if (r.get("docker_image","") or r.get("image_name","")) in local_images]
    skipped = N - len(instances)
    if skipped > 0:
        log(f"Skipped {skipped}/{N} instances (Docker image not found locally)", "WARN")
    N = len(instances)
    log(f"Running {N} instances (with local Docker images)")

    if N == 0:
        log("No instances to run!", "ERROR")
        return 1

    if not preflight(instances): log("Preflight FAILED","ERROR"); return 1
    log("")

    t_start = time.time()

    # Stage 4: Enhancement
    all_rows, enh, fb = run_stage4(instances)
    log("")

    # Stage 5a: Baseline solver
    try:
        bl_preds = run_solver("baseline", instances, RUN_DIR/"stage5_solver_eval"/"solver_baseline")
    except Exception as e:
        log(f"BASELINE SOLVER CRASHED: {e}","ERROR")
        traceback.print_exc()
        bl_preds = {}
    log("")

    # Stage 5b: Enhanced solver
    try:
        en_preds = run_solver("enhanced", all_rows, RUN_DIR/"stage5_solver_eval"/"solver_enhanced")
    except Exception as e:
        log(f"ENHANCED SOLVER CRASHED: {e}","ERROR")
        traceback.print_exc()
        en_preds = {}
    log("")

    t_total = time.time() - t_start

    bl_ne = sum(1 for p in bl_preds.values() if (p.get("model_patch","") or "").strip())
    en_ne = sum(1 for p in en_preds.values() if (p.get("model_patch","") or "").strip())

    # Split analysis: truly-enhanced vs fallback (enhancer_error)
    enh_ids = set(r["instance_id"] for r in enh)
    fb_ids  = set(r["instance_id"] for r in fb)

    def _count_patches(preds, id_set):
        return sum(1 for iid, p in preds.items()
                   if iid in id_set and (p.get("model_patch","") or "").strip())

    bl_enh_ne = _count_patches(bl_preds, enh_ids)
    bl_fb_ne  = _count_patches(bl_preds, fb_ids)
    en_enh_ne = _count_patches(en_preds, enh_ids)
    en_fb_ne  = _count_patches(en_preds, fb_ids)
    n_enh = len(enh_ids)
    n_fb  = len(fb_ids)

    log_section("FINAL RESULT")
    log(f"Model:            {MODEL} (max_iter={MAX_ITER}, workers={WORKERS})")
    log(f"Instances:        {N}")
    log(f"Enhancement:      {n_enh}/{N} truly enhanced, {n_fb} enhancer_error (fallback)")
    log(f"")
    log(f"--- Overall ---")
    log(f"Baseline patches: {bl_ne}/{N} non-empty")
    log(f"Enhanced patches: {en_ne}/{N} non-empty")
    log(f"")
    log(f"--- Truly Enhanced Only (excludes enhancer_error) ---")
    log(f"Baseline patches: {bl_enh_ne}/{n_enh} non-empty")
    log(f"Enhanced patches: {en_enh_ne}/{n_enh} non-empty")
    log(f"")
    log(f"--- Enhancer Error (fallback — enhanced=original) ---")
    log(f"Baseline patches: {bl_fb_ne}/{n_fb} non-empty")
    log(f"Enhanced patches: {en_fb_ne}/{n_fb} non-empty")
    log(f"Fallback IDs:")
    for fid in sorted(fb_ids):
        log(f"  [enhancer_error] {fid}")
    log(f"")
    log(f"Total time:       {t_total:.0f}s ({t_total/60:.1f}min, {t_total/3600:.1f}h)")
    log_resources("final")

    result = {
        "timestamp": _now(), "server": "gpu-02", "model": MODEL,
        "max_iter": MAX_ITER, "workers": WORKERS,
        "n_instances": N,
        "truly_enhanced": n_enh, "fallback": n_fb,
        "baseline_nonempty": bl_ne, "enhanced_nonempty": en_ne,
        "split_truly_enhanced": {
            "count": n_enh,
            "baseline_nonempty": bl_enh_ne,
            "enhanced_nonempty": en_enh_ne,
        },
        "split_fallback": {
            "count": n_fb,
            "baseline_nonempty": bl_fb_ne,
            "enhanced_nonempty": en_fb_ne,
            "ids": sorted(fb_ids),
            "label": "enhancer_error",
        },
        "total_seconds": round(t_total, 1),
    }
    (RUN_DIR/"test_result.json").write_text(json.dumps(result, indent=2))

    # Copy results to NFS so GPU-01 can see them
    try:
        nfs_dest = NFS_RESULTS / RUN_DIR.name
        nfs_dest.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(RUN_DIR/"test_result.json", nfs_dest/"test_result.json")
        shutil.copy2(LOG_FILE, nfs_dest/"test.log")
        if RESOURCE_LOG.exists():
            shutil.copy2(RESOURCE_LOG, nfs_dest/"resource_usage.jsonl")
        log(f"Results copied to NFS: {nfs_dest}")
    except Exception as e:
        log(f"Failed to copy to NFS: {e}", "WARN")

    # Post-run disk cleanup: remove openhands-runtime images built during this run.
    # These are always rebuilt fresh per run and each is 10-20 GB — leaving them
    # accumulates across runs and fills the disk (the cause of the June-15 ENOSPC crash).
    # pouya/stage2_2026 images are NEVER touched here — they are irreplaceable.
    try:
        r = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}", "ghcr.io/openhands/runtime"],
            capture_output=True, text=True)
        oh_imgs = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
        if oh_imgs:
            log(f"Post-run cleanup: removing {len(oh_imgs)} ghcr.io/openhands/runtime images "
                f"({len(oh_imgs)*12:.0f}+ GB est.)...")
            subprocess.run(["docker", "rmi", "-f"] + oh_imgs, capture_output=True)
            df = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
            disk_line = [l for l in df.stdout.splitlines() if "/dev/" in l]
            log(f"Disk after cleanup: {disk_line[0] if disk_line else 'unknown'}")
        else:
            log("Post-run cleanup: no openhands-runtime images to remove")
    except Exception as e:
        log(f"Post-run cleanup failed: {e}", "WARN")

    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FATAL: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
