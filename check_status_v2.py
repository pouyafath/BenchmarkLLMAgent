#!/usr/bin/env python3
"""Comprehensive experiment status checker."""
import os, json, subprocess, glob
from pathlib import Path
from datetime import datetime

# Write to the source file itself as output (readable by view_file)
BENCH = Path("/home/22pf2/BenchmarkLLMAgent")
RESULTS_DIR = BENCH / "results" / "groupC50_baseline_vs_enhanced"
EXP_DIR = RESULTS_DIR / "cl_enhanced_gemma3__native_groupC50_20260404"

lines = []
lines.append(f"=== STATUS REPORT @ {datetime.utcnow().isoformat()}Z ===")
lines.append(f"exp_dir exists: {EXP_DIR.exists()}")

# Check all results dirs
lines.append(f"\nAll dirs in results/groupC50_baseline_vs_enhanced:")
for d in sorted(RESULTS_DIR.iterdir()):
    if d.is_dir():
        files = list(d.rglob("*"))
        lines.append(f"  {d.name}: {len(files)} files")

# Check logs dir
lines.append(f"\nNew log files in logs/:")
for lf in BENCH.joinpath("logs").glob("*.log"):
    s = lf.stat().st_size
    mt = datetime.utcfromtimestamp(lf.stat().st_mtime).isoformat()
    lines.append(f"  {lf.name}: {s} bytes, modified {mt}")

# running processes
lines.append(f"\nRunning python processes:")
try:
    ps = subprocess.check_output(["ps", "auxww"], text=True)
    for line in ps.splitlines():
        if "python" in line and ("BenchmarkLLMAgent" in line or "issue_enhancer" in line or "run_group" in line or "cl_enhanced" in line):
            lines.append("  " + line[:180])
except Exception as e:
    lines.append(f"  ps error: {e}")

# Check LLMforGithubIssuesRefactor recently modified files (enhancement subprocess output)
lines.append(f"\nRecently modified files in LLMforGithubIssuesRefactor:")
try:
    recent = subprocess.check_output(
        ["find", "/home/22pf2/LLMforGithubIssuesRefactor", "-newer",
         "/home/22pf2/BenchmarkLLMAgent/check_status.py", "-name", "*.json", "-o",
         "-newer", "/home/22pf2/BenchmarkLLMAgent/check_status.py", "-name", "*.log"],
        text=True, timeout=15
    )
    for f in recent.strip().splitlines()[:10]:
        lines.append(f"  {f}")
except Exception as e:
    lines.append(f"  find error: {e}")

report = "\n".join(lines)
# Write to a .txt file in the bench root
(BENCH / "STATUS_REPORT.txt").write_text(report)
print(report)
