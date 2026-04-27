#!/bin/bash
# Quick Benchmark: Compare Sequential vs Parallel Harness Performance
# This script measures the speedup from parallel processing
# Run this AFTER the current harness completes to validate Phase 2.1

set -e

echo "=========================================="
echo "Phase 2.1 Parallel Performance Benchmark"
echo "=========================================="
echo ""
echo "This script will:"
echo "1. Measure sequential evaluation time (--max_workers 1)"
echo "2. Measure parallel-2 evaluation time (--max_workers 2)"
echo "3. Measure parallel-3 evaluation time (--max_workers 3)"
echo "4. Report speedup improvements"
echo ""
echo "Estimated total time: ~2 hours (multiple runs)"
echo ""

# Check if predictions file exists
PREDICTIONS_FILE="eval_results/swebench/iteration4_final_predictions/all_predictions.jsonl"
if [ ! -f "$PREDICTIONS_FILE" ]; then
  echo "ERROR: Predictions file not found: $PREDICTIONS_FILE"
  echo "Please run the main harness first to generate predictions."
  exit 1
fi

# Create benchmark directory
mkdir -p logs/parallel_benchmark
BENCHMARK_LOG="logs/parallel_benchmark/benchmark_results.txt"

echo "Benchmark Results" > "$BENCHMARK_LOG"
echo "=================" >> "$BENCHMARK_LOG"
echo "" >> "$BENCHMARK_LOG"

# Helper function to run harness and measure time
run_harness_benchmark() {
  local workers=$1
  local tag="parallel_bench_x${workers}"
  local run_id=${tag}

  echo "Running with --max_workers $workers..."
  echo "Start time: $(date)" | tee -a "$BENCHMARK_LOG"

  local start_time=$(date +%s)

  mkdir -p logs/run_evaluation/${tag}

  ./bench_env/bin/python -m swebench.harness.run_evaluation \
    --predictions_path "$PREDICTIONS_FILE" \
    --max_workers $workers \
    --run_id ${run_id} \
    --dataset_name SWE-bench-Live/SWE-bench-Live \
    --split verified \
    --namespace starryzhang \
    --cache_level env \
    --report_dir logs/run_evaluation/${tag} \
    --timeout 1800 \
    2>&1 | tee logs/parallel_benchmark/${tag}.log

  local end_time=$(date +%s)
  local elapsed=$((end_time - start_time))
  local minutes=$((elapsed / 60))
  local seconds=$((elapsed % 60))

  echo ""
  echo "Completed with --max_workers $workers:"
  echo "  Time: ${minutes}m ${seconds}s"
  echo ""

  echo "Workers: $workers, Time: ${minutes}m ${seconds}s" >> "$BENCHMARK_LOG"
}

# Run benchmarks
echo ""
echo "Starting benchmarks..."
echo ""

# Sequential baseline
run_harness_benchmark 1

# Parallel-2
run_harness_benchmark 2

# Parallel-3
run_harness_benchmark 3

# Summary
echo ""
echo "=========================================="
echo "Benchmark Summary"
echo "=========================================="
cat "$BENCHMARK_LOG"

echo ""
echo "Full results saved to: $BENCHMARK_LOG"
echo "Individual logs saved to: logs/parallel_benchmark/"
echo ""
echo "Next steps:"
echo "1. Review the speedup results"
echo "2. Choose optimal worker count (usually --max_workers 3)"
echo "3. Use the chosen configuration for future evaluations"
echo ""
