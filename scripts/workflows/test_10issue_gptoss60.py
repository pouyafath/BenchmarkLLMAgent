#!/usr/bin/env python3
"""
10-issue validation: gpt-oss:120b with max_iter=60 (doubled from 30).
"""
from __future__ import annotations
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Config ───────────────────────────────────────────────────────────────────
TEST_IDS = [
    "AstrBotDevs__AstrBot-6065",
    "graphistry__pygraphistry-1386",
    "graphistry__pygraphistry-1182",
    "graphistry__pygraphistry-1442",
    "ipython__ipython-15027",
    "aws-powertools__powertools-lambda-python-8092",
    "conan-io__conan-18429",
    "darkoperator__dnsrecon-507",
    "docling-project__docling-2011",
    "feast-dev__feast-5454",
]
MODEL       = "gpt-oss:120b"
BASE_URL    = "http://localhost:11435/v1"
API_KEY     = "ollama"
WORKERS     = 1          # 1 solver at a time — share GPU with qwen3 run
TIMEOUT     = 3600
ENH_PARALLEL= 2
MAX_ITER    = 60         # doubled from 30

DATASET = ROOT / "data/node1_all494_stage3_merged_20260610.jsonl"
RUN_DIR = ROOT / "runs" / f"test10_gptoss60_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

os.environ.update({
    "USE_OLLAMA": "1", "OLLAMA_MODEL": MODEL,
    "OLLAMA_BASE_URL": "http://localhost:11435",
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
    r=dict(i);
    if r.get("docker_image"): r["image_name"]=r["docker_image"]
    return r

def log(msg, lvl="INFO"):
    line = f"[{_now()}] [{lvl}] {msg}"
    print(line, flush=True)
    with open(RUN_DIR/"test.log","a") as f: f.write(line+"\n")

def log_section(t): log("="*70); log(f"  {t}"); log("="*70)

# ── Preflight ────────────────────────────────────────────────────────────────
def preflight(instances):
    log_section("PRE-FLIGHT CHECKS")
    import subprocess; ok=True
    try:
        r=subprocess.run(["curl","-s","--max-time","60",f"{BASE_URL}/chat/completions",
            "-H","Content-Type: application/json","-d",json.dumps({"model":MODEL,
            "messages":[{"role":"user","content":"Say OK"}],"max_tokens":256,"temperature":0.3})],
            capture_output=True,text=True,timeout=90)
        resp=json.loads(r.stdout)
        c=resp.get("choices",[{}])[0].get("message",{}).get("content","") or ""
        if c.strip(): log(f"LLM: {MODEL} OK ({c[:30]})")
        else: log(f"LLM: {MODEL} EMPTY response!","ERROR"); ok=False
    except Exception as e: log(f"LLM: FAILED — {e}","ERROR"); ok=False
    for inst in instances:
        img=inst.get("docker_image","")
        r=subprocess.run(["docker","image","inspect",img,"--format","{{.Id}}"],capture_output=True,text=True)
        if r.returncode!=0: log(f"Docker: {img[:50]}... MISSING","ERROR"); ok=False
    try:
        from src.enhancers.dispatcher import get_enhancer; get_enhancer("openhands"); log("Enhancer: OK")
    except: log("Enhancer: FAIL","ERROR"); ok=False
    try:
        from src.solvers.openhands_solver import run_batch; log("Solver: OK")
    except: log("Solver: FAIL","ERROR"); ok=False
    return ok

# ── Stage 4 ──────────────────────────────────────────────────────────────────
def run_stage4(instances):
    log_section(f"STAGE 4: ENHANCEMENT ({MODEL}) — {len(instances)} inst, {ENH_PARALLEL} parallel")
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
        except Exception as e: return inst,{"enhancement_metadata":{"error":str(e),"enhancer_type":"error"}},time.time()-t0,False

    with ThreadPoolExecutor(max_workers=ENH_PARALLEL) as pool:
        futs={pool.submit(_do,i):i for i in instances}
        dm={}
        for f in as_completed(futs): inst,res,el,ok=f.result(); dm[inst["instance_id"]]=(inst,res,el,ok)

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
            log(f"  [{len(enh)+len(fb)}/{len(instances)}] {iid}: ENHANCED {el:.0f}s ({len(ps)}->{len(body)} chars)")
        else:
            row["enhancement_metadata"]=meta; row["_enhancement_valid"]=False; row["_fallback_used"]=True
            fb.append(row); log(f"  [{len(enh)+len(fb)}/{len(instances)}] {iid}: FALLBACK {el:.0f}s","WARN")
        all_map[iid]=row

    all_rows=[all_map[i["instance_id"]] for i in instances]
    s4=RUN_DIR/"stage4_enhanced"; s4.mkdir(parents=True,exist_ok=True)
    _dump(s4/"baseline.jsonl",[_sr(i) for i in instances])
    _dump(s4/"enhanced_all.jsonl",[_sr(r) for r in all_rows])
    (s4/"fallback_manifest.json").write_text(json.dumps({
        "total":len(instances),"truly_enhanced":len(enh),"fallback_count":len(fb),
        "fallback_ids":sorted(r["instance_id"] for r in fb),
        "enhanced_ids":sorted(r["instance_id"] for r in enh)},indent=2))
    log(f"  Stage 4: {len(enh)}/{len(instances)} enhanced, {len(fb)} fallback")
    return all_rows, enh, fb

# ── Stage 5 ──────────────────────────────────────────────────────────────────
def run_solver(label, instances, sdir):
    log_section(f"STAGE 5: SOLVER ({label}) — {len(instances)} inst, {WORKERS} parallel, max_iter={MAX_ITER}")
    sdir.mkdir(parents=True,exist_ok=True)
    instances=[_sr(i) for i in instances]; preds_out=sdir/"preds.json"
    from src.solvers.openhands_solver import run_batch
    t0=time.time()
    try:
        run_batch(instances,API_KEY,sdir/"work",preds_out,model=MODEL,base_url=BASE_URL,
                  max_iter=MAX_ITER,workers=WORKERS,timeout=TIMEOUT)
    except Exception as e: log(f"  Solver error: {e}","ERROR")
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
    log(f"  Solver ({label}) done {elapsed:.0f}s: {ne}/{len(preds)} non-empty")
    return preds

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    RUN_DIR.mkdir(parents=True,exist_ok=True); N=len(TEST_IDS)
    log_section(f"10-ISSUE TEST: {MODEL} max_iter={MAX_ITER}")
    log(f"Run: {RUN_DIR}"); log(f"LLM: {MODEL} @ {BASE_URL}"); log(f"IDs ({N}): {TEST_IDS}")

    data=_load(DATASET); ids=set(TEST_IDS)
    instances=[r for r in data if r["instance_id"] in ids]
    if len(instances)!=N: log(f"Missing IDs","ERROR"); return 1
    im={r["instance_id"]:r for r in instances}; instances=[im[i] for i in TEST_IDS]
    log(f"Loaded {N}/{len(data)}")

    if not preflight(instances): log("Preflight FAILED","ERROR"); return 1
    log("")

    all_rows,enh,fb = run_stage4(instances); log("")
    bl_preds = run_solver("baseline",instances,RUN_DIR/"stage5_solver_eval"/"solver_baseline"); log("")
    en_preds = run_solver("enhanced",all_rows,RUN_DIR/"stage5_solver_eval"/"solver_enhanced"); log("")

    bl_ne=sum(1 for p in bl_preds.values() if (p.get("model_patch","") or "").strip())
    en_ne=sum(1 for p in en_preds.values() if (p.get("model_patch","") or "").strip())

    log_section("FINAL RESULT")
    log(f"Model:            {MODEL} (max_iter={MAX_ITER})")
    log(f"Enhancement:      {len(enh)}/{N} truly enhanced")
    log(f"Baseline patches: {bl_ne}/{N} non-empty")
    log(f"Enhanced patches: {en_ne}/{N} non-empty")

    (RUN_DIR/"test_result.json").write_text(json.dumps({
        "timestamp":_now(),"model":MODEL,"max_iter":MAX_ITER,
        "truly_enhanced":len(enh),"fallback":len(fb),
        "baseline_nonempty":bl_ne,"enhanced_nonempty":en_ne,
    },indent=2))
    return 0

if __name__=="__main__": sys.exit(main())
