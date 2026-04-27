#!/bin/bash
# Full Evaluation Pipeline: Patch Generation + SWE-bench Harness + Metrics Collection
# This script runs the complete pipeline to get F2P/P2P/Fix Rate metrics

set -e  # Exit on error

NUM_ISSUES=${1:-2}  # Default to 2 issues, can override with argument
OUTPUT_TAG="iteration4_improved"

echo "========================================"
echo "Full Evaluation Pipeline"
echo "Issues to process: $NUM_ISSUES"
echo "Output tag: $OUTPUT_TAG"
echo "========================================"

# Step 1: Generate patches with improved workflow
echo ""
echo "[Step 1/5] Generating patches with improved solver..."
./bench_env/bin/python scripts/enhancers/run_solving_after_enhancement.py \
  --solver openhands \
  --baseline-mode \
  --max-issues $NUM_ISSUES \
  --output-dir results/${OUTPUT_TAG}_patches

# Check if patches were generated
PATCH_COUNT=$(ls results/${OUTPUT_TAG}_patches/*.json 2>/dev/null | wc -l)
echo "Generated $PATCH_COUNT patches"

if [ "$PATCH_COUNT" -eq 0 ]; then
  echo "ERROR: No patches generated!"
  exit 1
fi

# Step 2: Convert to SWE-bench predictions format
echo ""
echo "[Step 2/5] Converting to SWE-bench predictions format..."
./bench_env/bin/python scripts/swebench/convert_to_predictions.py \
  --baseline-dir results/${OUTPUT_TAG}_patches \
  --output-dir eval_results/swebench/${OUTPUT_TAG}_predictions

# Step 3: Run SWE-bench harness evaluation (gets F2P/P2P)
echo ""
echo "[Step 3/5] Running SWE-bench harness evaluation..."
mkdir -p logs/run_evaluation/${OUTPUT_TAG}

# Combine all predictions into a single JSONL file
cat eval_results/swebench/${OUTPUT_TAG}_predictions/*.jsonl > \
  eval_results/swebench/${OUTPUT_TAG}_all_predictions.jsonl

# Run SWE-bench harness (this takes ~5-10 minutes per issue in Docker)
echo "Running SWE-bench harness (est. ~$((NUM_ISSUES * 7)) minutes)..."
./bench_env/bin/python -m swebench.harness.run_evaluation \
  --predictions_path eval_results/swebench/${OUTPUT_TAG}_all_predictions.jsonl \
  --max_workers 1 \
  --run_id ${OUTPUT_TAG} \
  --dataset_name SWE-bench-Live/SWE-bench-Live \
  --split verified \
  --cache_level env \
  --log_dir logs/run_evaluation/${OUTPUT_TAG}

# Step 4: Compute comprehensive metrics
echo ""
echo "[Step 4/5] Computing comprehensive metrics..."
./bench_env/bin/python scripts/reports/comprehensive_metrics.py \
  --harness-logs logs/run_evaluation/${OUTPUT_TAG} \
  --patches-dir results/${OUTPUT_TAG}_patches \
  --output eval_results/swebench/${OUTPUT_TAG}_comprehensive_metrics.json

# Step 5: Compute fix rate metrics (SWE-EVO)
echo ""
echo "[Step 5/5] Computing fix rate metrics..."
./bench_env/bin/python scripts/reports/compute_fix_rate_metrics.py \
  --harness-logs logs/run_evaluation/${OUTPUT_TAG} \
  --output eval_results/swebench/${OUTPUT_TAG}_fix_rate_metrics.json

echo ""
echo "========================================"
echo "Pipeline Complete!"
echo "========================================"
echo "Results saved to:"
echo "  - Patches: results/${OUTPUT_TAG}_patches/"
echo "  - Predictions: eval_results/swebench/${OUTPUT_TAG}_predictions/"
echo "  - Harness logs: logs/run_evaluation/${OUTPUT_TAG}/"
echo "  - Comprehensive metrics: eval_results/swebench/${OUTPUT_TAG}_comprehensive_metrics.json"
echo "  - Fix rate metrics: eval_results/swebench/${OUTPUT_TAG}_fix_rate_metrics.json"
