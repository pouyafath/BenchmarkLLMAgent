#!/bin/bash
# Approach A: Run Devstral+TP+P2P test names experiment
set -e
cd /home/22pf2/BenchmarkLLMAgent

export CODE_CONTEXT_INCLUDE_TEST_PATCH=1
export CODE_CONTEXT_INCLUDE_P2P_TESTS=1
export CODE_CONTEXT_DATASET_JSONL=/home/22pf2/BenchmarkLLMAgent/data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl
export CODE_CONTEXT_MAX_ENHANCED_TOTAL=30000

RESULTS_ROOT="results/groupC50_p2p_approachA"
OUTPUT_TAG="code_context_devstral_tp_p2p_groupC50_20260413"
EXPERIMENT_DIR="$RESULTS_ROOT/code_context__${OUTPUT_TAG}"

# Copy baseline from Task 1
mkdir -p "$EXPERIMENT_DIR"
cp -r results/groupC50_code_context_devstral_testpatch/code_context__code_context_devstral_testpatch_groupC50_20260413/baseline_solver_run "$EXPERIMENT_DIR/"

echo "=== Approach A: Devstral + test_patch + P2P test names ==="
echo "Started at: $(date -u)"

bench_env/bin/python scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py \
  --enhancer-agent code_context \
  --output-tag "$OUTPUT_TAG" \
  --dataset-jsonl data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl \
  --selected-ids-file data/samples/groupC_swebenchlive_50/groupC_50_instance_ids.txt \
  --samples-json data/samples/groupC_swebenchlive_50/groupC_50_samples.json \
  --max-issues 50 \
  --namespace starryzhang \
  --allow-identical-enhancements \
  --max-enhanced-body-chars 32000 \
  --solver-workers 4 \
  --eval-workers 4 \
  --skip-baseline \
  --skip-eval \
  --results-root "$RESULTS_ROOT"

echo "Solver completed at: $(date -u)"
echo "Now running evaluation..."

# Run evaluation
INSTANCE_IDS=$(cat data/samples/groupC_swebenchlive_50/groupC_50_instance_ids.txt | head -50 | tr '\n' ' ')
RUN_ID="secondpaper10_code_context_${OUTPUT_TAG}"

bench_env/bin/python -m swebench.harness.run_evaluation \
  --dataset_name data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl \
  --predictions_path "$EXPERIMENT_DIR/enhanced_solver_run/preds.json" \
  --instance_ids $INSTANCE_IDS \
  --max_workers 4 \
  --timeout 1800 \
  --run_id "$RUN_ID" \
  --namespace starryzhang

echo "Evaluation completed at: $(date -u)"

# Recompute comparison with all skips
bench_env/bin/python scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py \
  --enhancer-agent code_context \
  --output-tag "$OUTPUT_TAG" \
  --dataset-jsonl data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl \
  --selected-ids-file data/samples/groupC_swebenchlive_50/groupC_50_instance_ids.txt \
  --samples-json data/samples/groupC_swebenchlive_50/groupC_50_samples.json \
  --max-issues 50 \
  --namespace starryzhang \
  --allow-identical-enhancements \
  --max-enhanced-body-chars 32000 \
  --solver-workers 4 \
  --eval-workers 4 \
  --skip-baseline \
  --skip-enhancement \
  --skip-solver \
  --skip-eval \
  --results-root "$RESULTS_ROOT"

echo "Approach A experiment fully completed at: $(date -u)"
