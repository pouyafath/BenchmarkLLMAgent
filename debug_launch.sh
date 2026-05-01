#!/bin/bash
# Debug launcher for cl_enhanced_gemma3 workflow
OUT=/home/22pf2/BenchmarkLLMAgent/cl_enhanced_debug.log
cd /home/22pf2/BenchmarkLLMAgent

echo "=== Script starting at $(date) ===" > "$OUT"
echo "Python: $(/home/22pf2/BenchmarkLLMAgent/bench_env/bin/python --version 2>&1)" >> "$OUT"
echo "CWD: $(pwd)" >> "$OUT"
echo "" >> "$OUT"

# Run the workflow script, capture everything
/home/22pf2/BenchmarkLLMAgent/bench_env/bin/python \
    scripts/workflows/run_groupC50_cl_enhanced_vs_baseline.py \
    --enhancer-parallel 2 \
    --solver-workers 4 \
    --eval-workers 4 \
    >> "$OUT" 2>&1

EXIT_CODE=$?
echo "" >> "$OUT"
echo "=== Exited with code $EXIT_CODE at $(date) ===" >> "$OUT"
