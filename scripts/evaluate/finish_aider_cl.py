#!/usr/bin/env python3
"""Finish the CL-Enhanced aider condition: score the 120 remaining evaluable aider instances
(excluding docling-2039, whose aider patch hangs the harness) into the existing output dir."""
import json, subprocess
from pathlib import Path
ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
EVAL = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"
PYX = "/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python"
DS = {"v2_targeted": ROOT/"data/stage6_382_v2.jsonl",
      "v3_fileLevel": ROOT/"data/stage6_382_v3.jsonl",
      "v1_files": ROOT/"data/stage6_382_v1.jsonl"}
meth = json.load(open("/home/22pf2/stage6/evaluable_methods_382.json"))
remaining = json.load(open("/tmp/aider_remaining.json"))
run = [p for p in (ROOT/"runs/cl_enhanced_scores").iterdir() if p.is_dir()][0]
conddir = run / "enh_cl_enhanced__solver_aider"
preds = ROOT / Path(open("/tmp/cl_enhanced.rundir").read().strip()) / "qwen3_32b/stage5/enh_cl_enhanced__solver_aider/preds.json"
by = {}
for i in remaining:
    by.setdefault(meth[i], []).append(i)
for m, ids in by.items():
    odir = conddir / m; odir.mkdir(parents=True, exist_ok=True)
    print(f"scoring aider {m}: {len(ids)} instances", flush=True)
    subprocess.run([PYX, str(EVAL), "--dataset", str(DS[m]), "--patch_dir", str(preds.resolve()),
                    "--platform", "linux", "--workers", "8", "--output_dir", str(odir.resolve()),
                    "--overwrite", "1", "--instance_ids", *ids],
                   cwd=str(EVAL.parent), capture_output=True, text=True)
    print(f"  done {m}", flush=True)
print("AIDER COMPLETION DONE", flush=True)
