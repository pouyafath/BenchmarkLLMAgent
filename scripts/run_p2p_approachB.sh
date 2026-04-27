#!/bin/bash
# Approach B: Run Devstral+TP with regression guard prompt (modified solver config)
# Uses the same Task 1 enhancements (with test_patch), but a modified solver prompt
# that instructs the agent to run regression tests before submitting
set -e
cd /home/22pf2/BenchmarkLLMAgent

export CODE_CONTEXT_INCLUDE_TEST_PATCH=1
export CODE_CONTEXT_DATASET_JSONL=/home/22pf2/BenchmarkLLMAgent/data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl
export CODE_CONTEXT_MAX_ENHANCED_TOTAL=30000

RESULTS_ROOT="results/groupC50_p2p_approachB"
OUTPUT_TAG="code_context_devstral_tp_regguard_groupC50_20260414"
EXPERIMENT_DIR="$RESULTS_ROOT/code_context__${OUTPUT_TAG}"
REGGUARD_CONFIG="/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks_regression_guard.yaml"

echo "=== Approach B: Devstral + test_patch + regression guard prompt ==="
echo "Started at: $(date -u)"

# Copy baseline from Task 1
mkdir -p "$EXPERIMENT_DIR"
if [ ! -d "$EXPERIMENT_DIR/baseline_solver_run" ]; then
    cp -r results/groupC50_code_context_devstral_testpatch/code_context__code_context_devstral_testpatch_groupC50_20260413/baseline_solver_run "$EXPERIMENT_DIR/"
fi

# Copy enhancements from Task 1 (same enhanced content, different solver behavior)
if [ ! -d "$EXPERIMENT_DIR/enhancements" ]; then
    cp -r results/groupC50_code_context_devstral_testpatch/code_context__code_context_devstral_testpatch_groupC50_20260413/enhancements "$EXPERIMENT_DIR/"
fi

# Run with regression guard benchmark config
# Enhancement is skipped (reuse from Task 1)
# Solver uses modified config with regression guard prompt
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
  --skip-eval \
  --mini-benchmark-config "$REGGUARD_CONFIG" \
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

# Recompute comparison
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
  --mini-benchmark-config "$REGGUARD_CONFIG" \
  --results-root "$RESULTS_ROOT"

echo "Approach B experiment fully completed at: $(date -u)"
