#!/bin/bash
set -e
cd /home/22pf2/BenchmarkLLMAgent

RESULTS_ROOT="results/groupC90_baseline_vs_enhanced"
OUTPUT_TAG="baseline_groupC90_$(date +%Y%m%d)"
V1_CONFIG="/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks_regression_guard.yaml"

echo "=== 90-Issue Scale-Up Strategy 1: Baseline Experiment ==="
echo "Started at: $(date -u)"

mkdir -p "$RESULTS_ROOT"

# Run workflow: run baseline solver and eval. Skip enhancement steps since this is baseline only.
bench_env/bin/python scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py \
  --enhancer-agent code_context \
  --output-tag "$OUTPUT_TAG" \
  --dataset-jsonl data/samples/groupC_swebenchlive_90/groupC_90_dataset.jsonl \
  --selected-ids-file data/samples/groupC_swebenchlive_90/groupC_90_instance_ids.txt \
  --samples-json data/samples/groupC_swebenchlive_90/groupC_90_samples.json \
  --max-issues 90 \
  --namespace starryzhang \
  --allow-identical-enhancements \
  --max-enhanced-body-chars 30000 \
  --solver-workers 4 \
  --eval-workers 4 \
  --skip-enhancement \
  --skip-solver \
  --skip-eval \
  --results-root "$RESULTS_ROOT" \
  --mini-benchmark-config "$V1_CONFIG"

echo "Baseline fully completed at: $(date -u)"

# The Code-Context + V1 Guard script (Strategy 2) and the Improved LLM Append script (Strategy 3)
# will be executed subsequently and assume the baseline has successfully populated results.
