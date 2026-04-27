#!/bin/bash
# Run eval + comparison for experiments where solver was restarted manually.
# Usage: bash scripts/workflows/run_pending_eval_and_comparison.sh <experiment_name>
#
# experiment_name: "append_analysis" or "hybrid_v2"
#
# This script:
# 1. Checks that the solver has completed all 50 issues
# 2. Runs SWE-bench harness evaluation on the enhanced predictions
# 3. Runs the full workflow in skip-solver mode to generate comparison

set -euo pipefail
cd /home/22pf2/BenchmarkLLMAgent

EXPERIMENT="${1:-}"
BENCH_PYTHON="bench_env/bin/python"
DATASET_JSONL="data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl"
IDS_FILE="data/samples/groupC_swebenchlive_50/groupC_50_instance_ids.txt"
SAMPLES_JSON="data/samples/groupC_swebenchlive_50/groupC_50_samples.json"
NAMESPACE="starryzhang"

if [ "$EXPERIMENT" == "append_analysis" ]; then
    OUTPUT_TAG="llm_append_analysis_groupC50_20260409"
    ENHANCER_AGENT="llm_append_analysis"
    RESULTS_DIR="results/groupC50_baseline_vs_enhanced/llm_append_analysis__llm_append_analysis_groupC50_20260409"
    PREDS="$RESULTS_DIR/enhanced_solver_run/preds.json"
    RUN_ID="groupC50_llm_append_analysis_llm_append_analysis_groupC50_20260409"
elif [ "$EXPERIMENT" == "hybrid_v2" ]; then
    OUTPUT_TAG="llm_hybrid_groupC50_20260409v2"
    ENHANCER_AGENT="llm_hybrid"
    RESULTS_DIR="results/groupC50_baseline_vs_enhanced/llm_hybrid__llm_hybrid_groupC50_20260409v2"
    PREDS="$RESULTS_DIR/enhanced_solver_run/preds.json"
    RUN_ID="groupC50_llm_hybrid_llm_hybrid_groupC50_20260409v2"
else
    echo "Usage: $0 <append_analysis|hybrid_v2>"
    exit 1
fi

# Check solver completion
DONE=$(python3 -c "import json; print(len(json.load(open('$PREDS'))))")
echo "Solver done: $DONE/50 instances"
if [ "$DONE" -lt 50 ]; then
    echo "ERROR: Solver not yet complete ($DONE/50). Wait for it to finish."
    exit 1
fi

echo ""
echo "=== Step 1: Running SWE-bench harness evaluation ==="
INSTANCE_IDS=$(cat "$IDS_FILE" | tr '\n' ' ')

$BENCH_PYTHON -m swebench.harness.run_evaluation \
    --dataset_name "$DATASET_JSONL" \
    --predictions_path "$PREDS" \
    --instance_ids $INSTANCE_IDS \
    --max_workers 4 \
    --timeout 1800 \
    --run_id "$RUN_ID" \
    --namespace "$NAMESPACE"

echo ""
echo "=== Step 2: Running comparison via workflow script ==="
# Re-run workflow with all steps skipped except eval+comparison
python scripts/workflows/run_groupC50_cl_enhanced_vs_baseline.py \
    --enhancer-agent "$ENHANCER_AGENT" \
    --output-tag "$OUTPUT_TAG" \
    --solver-workers 4 --eval-workers 4 --enhancer-parallel 1 \
    --allow-identical-enhancements \
    --max-enhanced-body-chars 30000 \
    --namespace "$NAMESPACE" \
    --mini-benchmark-config /home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks_regression_guard.yaml \
    --skip-enhancement --skip-solver --skip-eval \
    --results-root results/groupC50_baseline_vs_enhanced

echo ""
echo "=== Done! Check $RESULTS_DIR/comparison_summary.json ==="
