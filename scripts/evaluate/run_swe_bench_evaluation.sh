#!/bin/bash
set -e

./bench_env/bin/python -m swebench.harness.run_evaluation \
  --predictions_path $1 \
  --max_workers 1 \
  --run_id iteration1_eval \
  --dataset_name SWE-bench-Live/SWE-bench-Live \
  --split verified \
  --cache_level env
