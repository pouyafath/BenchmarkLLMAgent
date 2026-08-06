#!/usr/bin/env python3
"""Robustly finish the CL-Enhanced aider condition: score each remaining evaluable aider instance
in its own harness call with a hard per-instance timeout, so hang-prone repos (docling, peft, ...)
auto-skip and count as unresolved instead of deadlocking the whole pass. Small parallelism + a
container reaper for timed-out instances."""
import json, subprocess, concurrent.futures as cf, time
from pathlib import Path
ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
EVAL = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"
PYX = "/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python"
DS = {"v2_targeted": ROOT/"data/stage6_382_v2.jsonl",
      "v3_fileLevel": ROOT/"data/stage6_382_v3.jsonl",
      "v1_files": ROOT/"data/stage6_382_v1.jsonl"}
PER_INSTANCE_TIMEOUT = 500
PARALLEL = 4
meth = json.load(open("/home/22pf2/stage6/evaluable_methods_382.json"))
remaining = json.load(open("/tmp/aider_remaining2.json"))
run = [p for p in (ROOT/"runs/cl_enhanced_scores").iterdir() if p.is_dir()][0]
conddir = run / "enh_cl_enhanced__solver_aider"
preds = (ROOT / Path(open("/tmp/cl_enhanced.rundir").read().strip()) /
         "qwen3_32b/stage5/enh_cl_enhanced__solver_aider/preds.json").resolve()

def score_one(iid):
    m = meth[iid]; odir = conddir / m; odir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([PYX, str(EVAL), "--dataset", str(DS[m]), "--patch_dir", str(preds),
                        "--platform", "linux", "--workers", "1", "--output_dir", str(odir.resolve()),
                        "--overwrite", "1", "--instance_ids", iid],
                       cwd=str(EVAL.parent), capture_output=True, text=True,
                       timeout=PER_INSTANCE_TIMEOUT)
        return (iid, "done")
    except subprocess.TimeoutExpired:
        # reap any container the harness left for this instance
        short = iid.replace("__", "-").replace("_", "-")[:40]
        try:
            names = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.split()
            for n in names:
                if any(part in n for part in iid.split("__")):
                    subprocess.run(["docker", "kill", n], capture_output=True)
        except Exception:
            pass
        return (iid, "TIMEOUT")

t0 = time.time(); n_to = 0
print(f"scoring {len(remaining)} remaining aider instances, {PARALLEL}-parallel, {PER_INSTANCE_TIMEOUT}s each", flush=True)
with cf.ThreadPoolExecutor(max_workers=PARALLEL) as ex:
    for i, (iid, st) in enumerate(ex.map(score_one, remaining), 1):
        if st == "TIMEOUT": n_to += 1
        if i % 10 == 0 or st == "TIMEOUT":
            print(f"  [{i}/{len(remaining)}] {iid}: {st}  (timeouts so far: {n_to}, {(time.time()-t0)/60:.0f}m)", flush=True)
print(f"DONE: {len(remaining)} attempted, {n_to} timed out (unresolved), {(time.time()-t0)/60:.0f} min", flush=True)
