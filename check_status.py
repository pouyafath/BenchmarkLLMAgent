#!/usr/bin/env python3
"""Status checker for groupC50 cl_enhanced experiment."""
import os, json, subprocess, glob
from pathlib import Path
from datetime import datetime

STATUS_OUT = Path("/home/22pf2/.gemini/antigravity/brain/889e0434-bf7e-499d-85e1-b1ae721fbef5/exp_status.json")
BENCH = Path("/home/22pf2/BenchmarkLLMAgent")
RESULTS_DIR = BENCH / "results" / "groupC50_baseline_vs_enhanced"
EXP_DIR = RESULTS_DIR / "cl_enhanced_gemma3__native_groupC50_20260404"
LOGS_DIR = BENCH / "logs"

status = {
    "checked_at": datetime.utcnow().isoformat() + "Z",
    "exp_dir_exists": EXP_DIR.exists(),
    "exp_dir": str(EXP_DIR),
    "log_files": [],
    "enhancements": {},
    "comparison_summary": None,
    "ps_output": "",
    "recent_files": [],
}

# Check exp_dir contents
if EXP_DIR.exists():
    status["exp_dir_contents"] = [str(p) for p in sorted(EXP_DIR.rglob("*")) if p.is_file()][:30]
    enh_dir = EXP_DIR / "enhancements"
    if enh_dir.exists():
        enh_files = list(enh_dir.glob("*.json"))
        status["enhancements"] = {"count": len(enh_files), "files": [f.name for f in enh_files[:5]]}
    cmp = EXP_DIR / "comparison_summary.json"
    if cmp.exists():
        status["comparison_summary"] = json.loads(cmp.read_text())

# Check all log files in results dir
for lf in LOGS_DIR.glob("cl_enhanced*.log"):
    status["log_files"].append({"name": lf.name, "size": lf.stat().st_size, "tail": lf.read_text()[-500:]})

# Check ALL results directories for anything new
for d in RESULTS_DIR.iterdir():
    if d.is_dir():
        files = list(d.rglob("*"))
        status["recent_files"].append({"dir": d.name, "file_count": len(files), "subdirs": [sd.name for sd in d.iterdir() if sd.is_dir()]})

# Check processes
try:
    ps = subprocess.check_output(["ps", "auxww"], text=True)
    relevant = [line for line in ps.splitlines() if any(k in line for k in ["run_groupC50", "cl_enhanced", "enhancer", "bench_env", "issue_enhancer"])]
    status["ps_output"] = "\n".join(relevant[:20])
except Exception as e:
    status["ps_output"] = str(e)

# Check for any log files created recently anywhere
try:
    find_out = subprocess.check_output(
        ["find", str(BENCH), "-name", "*.log", "-newer", str(BENCH / "debug_launch.sh"), "-type", "f"],
        text=True, timeout=10
    )
    status["new_log_files"] = find_out.strip().splitlines()[:20]
except Exception as e:
    status["new_log_files"] = [str(e)]

STATUS_OUT.write_text(json.dumps(status, indent=2))
print(f"Status written to {STATUS_OUT}")
print(f"exp_dir_exists: {status['exp_dir_exists']}")
print(f"ps_output:\n{status['ps_output']}")
print(f"enhancements: {status['enhancements']}")
