#!/bin/bash
# Run evaluation for the enhanced solver predictions
# Then recompute comparison using the workflow script with all skips

set -e

cd /home/22pf2/BenchmarkLLMAgent

INSTANCE_IDS=$(cat data/samples/groupC_swebenchlive_50/groupC_50_instance_ids.txt | head -50 | tr '\n' ' ')
PREDS="results/groupC50_code_context_devstral_testpatch/code_context__code_context_devstral_testpatch_groupC50_20260413/enhanced_solver_run/preds.json"
DATASET="data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl"
RUN_ID="secondpaper10_code_context_code_context_devstral_testpatch_groupC50_20260413"

echo "Starting enhanced evaluation at $(date -u)"
echo "Run ID: $RUN_ID"
echo "Predictions: $PREDS"

bench_env/bin/python -m swebench.harness.run_evaluation \
  --dataset_name "$DATASET" \
  --predictions_path "$PREDS" \
  --instance_ids $INSTANCE_IDS \
  --max_workers 4 \
  --timeout 1800 \
  --run_id "$RUN_ID" \
  --namespace starryzhang

echo "Evaluation completed at $(date -u) with exit code: $?"
