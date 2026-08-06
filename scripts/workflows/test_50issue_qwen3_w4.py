#!/usr/bin/env python3
"""
50-instance pilot: qwen3:32b with max_iter=30, WORKERS=4.
Concurrency budget: WORKERS=4 (tested safe at 2, RAM was 118/1510GB).
"""
from __future__ import annotations
import json, os, sys, time, signal, traceback
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Config ───────────────────────────────────────────────────────────────────
TEST_IDS = [
    "elastic__rally-2014",
    "biopython__biopython-5021",
    "Lightning-AI__litgpt-2193",
    "google__langextract-138",
    "ipython__ipython-15079",
    "huggingface__transformers-38076",
    "graphistry__pygraphistry-1442",
    "graphistry__pygraphistry-1005",
    "google__langextract-97",
    "atlassian-api__atlassian-python-api-1638",
    "flet-dev__flet-6296",
    "decoderesearch__SAELens-627",
    "graphistry__pygraphistry-1057",
    "dlt-hub__dlt-3676",
    "chardet__chardet-347",
    "MemPalace__mempalace-1466",
    "MemPalace__mempalace-1191",
    "graphistry__pygraphistry-1020",
    "hhursev__recipe-scrapers-1853",
    "holoviz__panel-8471",
    "custom-components__ble_monitor-1535",
    "docling-project__docling-3223",
    "Lightning-AI__pytorch-lightning-21105",
    "dgtlmoon__changedetection.io-3460",
    "graphistry__pygraphistry-1487",
    "getsentry__sentry-python-6131",
    "emcie-co__parlant-774",
    "getsentry__sentry-python-4984",
    "chardet__chardet-336",
    "griptape-ai__griptape-2086",
    "conan-io__conan-18327",
    "dlt-hub__dlt-3606",
    "huggingface__trl-4093",
    "Azure-Samples__azure-search-openai-demo-2752",
    "graphistry__pygraphistry-1379",
    "getsentry__sentry-python-4621",
    "Marker-Inc-Korea__AutoRAG-1150",
    "gptme__gptme-861",
    "holoviz__panel-8321",
    "Lightning-AI__litgpt-2239",
    "bghira__SimpleTuner-2662",
    "gptme__gptme-893",
    "SWE-agent__mini-swe-agent-645",
    "MemPalace__mempalace-1359",
    "docling-project__docling-3425",
    "ipython__ipython-14996",
    "Tuxemon__Tuxemon-3468",
    "goldspanlabs__optopsy-199",
    "conan-io__conan-18995",
    "dask__distributed-9120",
]
MODEL       = "qwen3:32b"
BASE_URL    = "http://localhost:11434/v1"
API_KEY     = "ollama"
WORKERS     = 4           # increased from 2 — tested safe (118/1510GB RAM at WORKERS=2)
TIMEOUT     = 3600
ENH_PARALLEL= 2
MAX_ITER    = 30

DATASET = ROOT / "data/node1_all494_stage3_merged_20260610.jsonl"
RUN_DIR = ROOT / "runs" / f"test50_qwen3_w4_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
LOG_FILE = RUN_DIR / "test.log"
RESOURCE_LOG = RUN_DIR / "resource_usage.jsonl"

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
                if parts[0] in ("MemTotal:", "MemAvailable:", "MemFree:", "Buffers:", "Cached:"):
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
    docker_ps = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True)
    running = len(docker_ps.stdout.strip().split("\n")) if docker_ps.stdout.strip() else 0
    if running > 2:
        log(f"WARNING: {running} Docker containers already running — budget is max 4+{WORKERS}", "WARN")
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
    except: log("Enhancer: FAIL","ERROR"); ok=False
    try:
        from src.solvers.openhands_solver import run_batch; log("Solver: OK")
    except: log("Solver: FAIL","ERROR"); ok=False
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
    log(f"  Stage 4 DONE: {len(enh)}/{N} enhanced, {len(fb)} fallback")
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
    RUN_DIR.mkdir(parents=True,exist_ok=True); N=len(TEST_IDS)
    log_section(f"50-INSTANCE PILOT: {MODEL} max_iter={MAX_ITER}, workers={WORKERS}")
    log(f"Run dir: {RUN_DIR}")
    log(f"Model:   {MODEL} @ {BASE_URL}")
    log(f"Budget:  WORKERS={WORKERS}, ENH_PARALLEL={ENH_PARALLEL}, max_iter={MAX_ITER}")
    log(f"IDs:     {N} instances")

    data=_load(DATASET); ids=set(TEST_IDS)
    instances=[r for r in data if r["instance_id"] in ids]
    if len(instances)!=N:
        found = set(r["instance_id"] for r in instances)
        missing = ids - found
        log(f"Missing {len(missing)} IDs: {missing}","ERROR"); return 1
    im={r["instance_id"]:r for r in instances}; instances=[im[i] for i in TEST_IDS]
    log(f"Loaded {N}/{len(data)}")

    if not preflight(instances): log("Preflight FAILED","ERROR"); return 1
    log("")

    t_start = time.time()

    # Stage 4: Enhancement
    all_rows,enh,fb = run_stage4(instances)
    log("")

    # Stage 5a: Baseline solver
    try:
        bl_preds = run_solver("baseline",instances,RUN_DIR/"stage5_solver_eval"/"solver_baseline")
    except Exception as e:
        log(f"BASELINE SOLVER CRASHED: {e}","ERROR")
        traceback.print_exc()
        bl_preds = {}
    log("")

    # Stage 5b: Enhanced solver
    try:
        en_preds = run_solver("enhanced",all_rows,RUN_DIR/"stage5_solver_eval"/"solver_enhanced")
    except Exception as e:
        log(f"ENHANCED SOLVER CRASHED: {e}","ERROR")
        traceback.print_exc()
        en_preds = {}
    log("")

    t_total = time.time() - t_start

    bl_ne=sum(1 for p in bl_preds.values() if (p.get("model_patch","") or "").strip())
    en_ne=sum(1 for p in en_preds.values() if (p.get("model_patch","") or "").strip())

    # ── Split analysis: truly-enhanced vs fallback ──────────────────────────
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
    log(f"Enhancement:      {n_enh}/{N} truly enhanced, {n_fb} fallback (enhancer_error)")
    log(f"")
    log(f"--- Overall ---")
    log(f"Baseline patches: {bl_ne}/{N} non-empty")
    log(f"Enhanced patches: {en_ne}/{N} non-empty")
    log(f"")
    log(f"--- Truly Enhanced Only (excludes fallback) ---")
    log(f"Baseline patches: {bl_enh_ne}/{n_enh} non-empty")
    log(f"Enhanced patches: {en_enh_ne}/{n_enh} non-empty")
    log(f"")
    log(f"--- Fallback Only (enhancer_error — enhanced=original) ---")
    log(f"Baseline patches: {bl_fb_ne}/{n_fb} non-empty")
    log(f"Enhanced patches: {en_fb_ne}/{n_fb} non-empty")
    log(f"Fallback IDs:")
    for fid in sorted(fb_ids):
        log(f"  [enhancer_error] {fid}")
    log(f"")
    log(f"Total time:       {t_total:.0f}s ({t_total/60:.1f}min, {t_total/3600:.1f}h)")
    log(f"Avg per instance: {t_total/N:.0f}s (all stages)")
    log_resources("final")

    # Estimate for full 383 run
    est_383 = (t_total / N) * 383
    log(f"")
    log(f"ESTIMATE for 383 instances at WORKERS={WORKERS}: ~{est_383/3600:.1f} hours")

    (RUN_DIR/"test_result.json").write_text(json.dumps({
        "timestamp":_now(),"model":MODEL,"max_iter":MAX_ITER,"workers":WORKERS,
        "n_instances":N,
        "truly_enhanced":n_enh,"fallback":n_fb,
        "baseline_nonempty":bl_ne,"enhanced_nonempty":en_ne,
        "split_truly_enhanced":{
            "count":n_enh,
            "baseline_nonempty":bl_enh_ne,
            "enhanced_nonempty":en_enh_ne,
        },
        "split_fallback":{
            "count":n_fb,
            "baseline_nonempty":bl_fb_ne,
            "enhanced_nonempty":en_fb_ne,
            "ids":sorted(fb_ids),
            "label":"enhancer_error",
        },
        "total_seconds":round(t_total,1),
        "avg_per_instance_seconds":round(t_total/N,1),
        "estimate_383_hours":round(est_383/3600,1),
    },indent=2))

    # Resource usage summary
    if RESOURCE_LOG.exists():
        entries = [json.loads(l) for l in RESOURCE_LOG.read_text().splitlines() if l.strip()]
        if entries:
            peak_docker = max(e.get("docker_containers",0) for e in entries)
            peak_mem = max(e.get("mem_used_gb",0) for e in entries)
            peak_load = max(e.get("load_1m",0) for e in entries)
            log(f"")
            log(f"RESOURCE PEAKS: Docker={peak_docker} containers | RAM={peak_mem:.0f}GB | Load={peak_load:.1f}")
            log(f"Budget:         Docker≤4+{WORKERS} | Workers={WORKERS}")

    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FATAL: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
