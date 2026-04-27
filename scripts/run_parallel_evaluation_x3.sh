#!/bin/bash
# Parallel SWE-bench Harness Evaluation (3 workers)
# Estimated speedup: ~3x (25-35 minutes for 10 issues) - RECOMMENDED
# This script runs 3 instances in parallel for fastest evaluation

set -e

NUM_ISSUES=${1:-10}
OUTPUT_TAG="iteration_parallel_x3"
NUM_WORKERS=3

echo "=========================================="
echo "Parallel SWE-bench Harness Evaluation"
echo "Issues: $NUM_ISSUES"
echo "Workers: $NUM_WORKERS (est. 3x speedup) ⭐ RECOMMENDED"
echo "Started: $(date)"
echo "=========================================="

# Verify predictions file exists
PREDICTIONS_FILE="eval_results/swebench/iteration4_final_predictions/all_predictions.jsonl"
if [ ! -f "$PREDICTIONS_FILE" ]; then
  echo "ERROR: Predictions file not found: $PREDICTIONS_FILE"
  exit 1
fi

# Step 1: Run harness with parallel workers
echo ""
echo "[Step 1/3] Running harness with $NUM_WORKERS parallel workers..."
mkdir -p logs/run_evaluation/${OUTPUT_TAG}

./bench_env/bin/python -m swebench.harness.run_evaluation \
  --predictions_path "$PREDICTIONS_FILE" \
  --max_workers $NUM_WORKERS \
  --run_id ${OUTPUT_TAG} \
  --dataset_name SWE-bench-Live/SWE-bench-Live \
  --split verified \
  --namespace starryzhang \
  --cache_level env \
  --report_dir logs/run_evaluation/${OUTPUT_TAG} \
  --timeout 1800

# Step 2: Aggregate results
echo ""
echo "[Step 2/3] Aggregating results..."
mkdir -p eval_results/swebench/

./bench_env/bin/python scripts/reports/aggregate_swebench_results.py \
  --harness-logs logs/run_evaluation/${OUTPUT_TAG} \
  --output eval_results/swebench/${OUTPUT_TAG}_aggregate_report.json 2>/dev/null || \
  echo "Note: aggregate_swebench_results.py not found; skipping aggregation"

# Step 3: Generate metrics
echo ""
echo "[Step 3/3] Computing metrics..."
./bench_env/bin/python scripts/reports/compute_fix_rate_metrics.py \
  --harness-logs logs/run_evaluation/${OUTPUT_TAG} \
  --output eval_results/swebench/${OUTPUT_TAG}_fix_rate_metrics.json 2>/dev/null || \
  echo "Note: compute_fix_rate_metrics.py not found; skipping metrics"

echo ""
echo "=========================================="
echo "Parallel Evaluation Complete!"
echo "Completed: $(date)"
echo "=========================================="
echo "Results saved to:"
echo "  - Logs: logs/run_evaluation/${OUTPUT_TAG}/"
echo "  - Aggregate: eval_results/swebench/${OUTPUT_TAG}_aggregate_report.json"
echo "  - Metrics: eval_results/swebench/${OUTPUT_TAG}_fix_rate_metrics.json"
echo ""
