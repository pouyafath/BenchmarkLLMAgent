#!/bin/bash
# V2 Regression Guard Experiment
# Uses improved prompt with pre-patch testing, minimality rules, focused tests, 180s timeout
set -e
cd /home/22pf2/BenchmarkLLMAgent

export CODE_CONTEXT_INCLUDE_TEST_PATCH=1
export CODE_CONTEXT_DATASET_JSONL=/home/22pf2/BenchmarkLLMAgent/data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl
export CODE_CONTEXT_MAX_ENHANCED_TOTAL=30000

RESULTS_ROOT="results/groupC50_p2p_regguard_v2"
OUTPUT_TAG="code_context_devstral_tp_regguard_v2_groupC50_20260414"
EXPERIMENT_DIR="$RESULTS_ROOT/code_context__${OUTPUT_TAG}"
V2_CONFIG="/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks_regression_guard_v2.yaml"

echo "=== V2 Regression Guard Experiment ==="
echo "Config: $V2_CONFIG"
echo "Started at: $(date -u)"

# Copy baseline from Task 1
mkdir -p "$EXPERIMENT_DIR"
if [ ! -d "$EXPERIMENT_DIR/baseline_solver_run" ]; then
    cp -r results/groupC50_code_context_devstral_testpatch/code_context__code_context_devstral_testpatch_groupC50_20260413/baseline_solver_run "$EXPERIMENT_DIR/"
fi

# Copy enhancements from Task 1 (same enhanced descriptions with test_patch)
if [ ! -d "$EXPERIMENT_DIR/enhancements" ]; then
    cp -r results/groupC50_code_context_devstral_testpatch/code_context__code_context_devstral_testpatch_groupC50_20260413/enhancements "$EXPERIMENT_DIR/"
fi

# Run workflow: skip baseline, skip enhancement (reuse), run solver with v2 config, skip eval (manual)
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
  --mini-benchmark-config "$V2_CONFIG" \
  --results-root "$RESULTS_ROOT"

echo "Solver completed at: $(date -u)"
echo "Now running evaluation..."

# Evaluate
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

# Compute comparison
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
  --mini-benchmark-config "$V2_CONFIG" \
  --results-root "$RESULTS_ROOT"

echo "V2 Regression Guard experiment fully completed at: $(date -u)"
