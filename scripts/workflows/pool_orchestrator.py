#!/usr/bin/env python3
"""
Keep POOL_TOTAL open-source model cells (enh:Aider->sol:OpenHands, 20-sample) running in parallel on
the shared :11434 (which multi-loads). gpt-oss (launched separately) counts toward the pool. As each
model finishes, launch the next from QUEUE. VRAM-aware (won't launch if it won't fit). Health-logs
every cycle so parallel load can be watched.
"""
import json, os, subprocess, sys, time, shutil
from pathlib import Path
ROOT = Path("/home/22pf2/BenchmarkLLMAgent"); os.chdir(ROOT)
ENDPOINT = "http://localhost:11434/v1"
SAMPLE = str(ROOT/".secrets/sample20_gpt5solved.txt")
POOL_TOTAL = 3
WORKERS = 2
VRAM_BUFFER_GB = 12
# (model, approx VRAM GB) — smaller/faster first, the 141GB fp16 last
QUEUE = [
    ("mixtral:8x7b-instruct-v0.1-fp16", 94),
    ("qwen2.5:32b", 20),
    ("glm-4.7-flash:latest", 19),
    ("deepseek-coder-v2:16b", 9),
    ("llama3:8b-instruct-fp16", 16),
    ("deepseek-r1:latest", 6),
    ("llama3:latest", 5),
    ("deepseek-r1:70b", 43),
]
GPTOSS_DIRGLOB = "runs/ollama_gptoss_g5s20_*/gpt-oss_120b"

def log(msg): print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)
def sh(cmd, t=15):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t).stdout.strip()
    except Exception: return ""
def free_vram_gb():
    o = sh("nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits")
    try: return sum(int(x) for x in o.split())//1024
    except Exception: return 0
def gpu_line():
    return sh("nvidia-smi --query-gpu=index,memory.free --format=csv,noheader,nounits").replace("\n"," | ")
def containers(): return sh("docker ps -q | wc -l")
def ram_avail(): return sh("free -g | awk '/Mem/{print $7}'")
def cell_progress(rundir):
    p=Path(rundir)
    def n(sub):
        f=p/sub/"preds.json"
        try: return len(json.load(open(f)))
        except Exception: return 0
    return n("baseline__solver_openhands"), (p/"stage4_aider"/"enhanced_aider.jsonl").exists(), n("enh_aider__solver_openhands")
def gptoss_active():
    return False  # gpt-oss already finished in the first batch; full pool of 3 for this batch
def model_loads(model):
    r=sh(f"""curl -s --max-time 240 {ENDPOINT}/chat/completions -H 'Content-Type: application/json' -d '{{"model":"{model}","messages":[{{"role":"user","content":"reply OK"}}],"max_tokens":16}}'""", t=250)
    return '"choices"' in r

running = {}   # model -> {proc, tag, rundir_glob}
launched = set()
qi = 0
log(f"pool orchestrator start | POOL_TOTAL={POOL_TOTAL} workers={WORKERS} | queue={len(QUEUE)}")

while qi < len(QUEUE) or running:
    # reap finished
    for m in list(running):
        pr = running[m]["proc"]
        if pr.poll() is not None:
            log(f"FINISHED {m} (exit {pr.returncode})")
            del running[m]
    active_total = len(running) + (1 if gptoss_active() else 0)
    # fill pool
    while active_total < POOL_TOTAL and qi < len(QUEUE):
        model, sz = QUEUE[qi]
        fv = free_vram_gb()
        if fv < sz + VRAM_BUFFER_GB:
            log(f"HOLD {model}: needs ~{sz}GB, only {fv}GB free — waiting")
            break
        log(f"LAUNCH {model} (~{sz}GB, {fv}GB free) — verifying load...")
        if not model_loads(model):
            log(f"SKIP {model}: failed to load on {ENDPOINT}")
            qi += 1; continue
        tag = f"pool_{model.split(':')[0].replace('.','').replace('/','_')}"
        lf = f"/home/22pf2/pool_{tag}_{time.strftime('%H%M%S')}.log"
        cmd = (f"bench_env/bin/python scripts/workflows/run_ollama_cell.py --model '{model}' "
               f"--base-url {ENDPOINT} --instances-file {SAMPLE} --tag ollama_pool2_g5s20 "
               f"--workers {WORKERS} --max-iter 30 --solve-timeout 1800 --enh-timeout 600")
        proc = subprocess.Popen(cmd, shell=True, stdout=open(lf,"w"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        running[model] = {"proc": proc, "tag": tag, "log": lf}
        launched.add(model); qi += 1; active_total += 1
        log(f"  -> launched {model} pid={proc.pid} log={lf}")
        time.sleep(20)  # stagger so loads don't collide
    # HEALTH LOG
    gptoss = "active" if gptoss_active() else "done"
    log(f"HEALTH | running={list(running)} gptoss={gptoss} | freeVRAM={free_vram_gb()}GB containers={containers()} RAMavail={ram_avail()}GB")
    log(f"  gpuFree(MiB): {gpu_line()}")
    time.sleep(300)

log("ALL QUEUED MODELS DONE")
