#!/bin/bash
# Launcher for Devstral + test_patch experiment
# Runs as a detached process that survives terminal closure

export CODE_CONTEXT_INCLUDE_TEST_PATCH=1
export CODE_CONTEXT_DATASET_JSONL=/home/22pf2/BenchmarkLLMAgent/data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl
export CODE_CONTEXT_MAX_ENHANCED_TOTAL=30000

cd /home/22pf2/BenchmarkLLMAgent

bench_env/bin/python scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py \
  --enhancer-agent code_context \
  --output-tag code_context_devstral_testpatch_groupC50_20260413 \
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
  --results-root results/groupC50_code_context_devstral_testpatch \
  > /home/22pf2/BenchmarkLLMAgent/logs/devstral_testpatch_run.log 2>&1

echo "Experiment completed with exit code: $?" >> /home/22pf2/BenchmarkLLMAgent/logs/devstral_testpatch_run.log
