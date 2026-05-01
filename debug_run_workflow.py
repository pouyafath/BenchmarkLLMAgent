#!/usr/bin/env python3
"""
Debug script: Run workflow script and capture all output to a file.
"""
import subprocess, sys

LOG = "/home/22pf2/BenchmarkLLMAgent/cl_enhanced_debug.log"

with open(LOG, "w") as f:
    f.write("=== Debug run starting ===\n")
    f.flush()
    
    result = subprocess.run(
        [
            "/home/22pf2/BenchmarkLLMAgent/bench_env/bin/python",
            "scripts/workflows/run_groupC50_cl_enhanced_vs_baseline.py",
            "--enhancer-parallel", "2",
            "--solver-workers", "4",
            "--eval-workers", "4",
        ],
        cwd="/home/22pf2/BenchmarkLLMAgent",
        capture_output=True,
        text=True,
        timeout=7200,  # 2 hours
    )
    
    f.write(f"STDOUT:\n{result.stdout}\n")
    f.write(f"STDERR:\n{result.stderr}\n")
    f.write(f"RETURN CODE: {result.returncode}\n")

print(f"Done. Exit code: {result.returncode}. Log written to {LOG}")
print(f"First 200 chars of stdout: {result.stdout[:200]!r}")
print(f"First 200 chars of stderr: {result.stderr[:200]!r}")
