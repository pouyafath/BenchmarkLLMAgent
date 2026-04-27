#!/bin/bash
# Re-run enhanced solver + evaluation for SWE-agent and TRAE experiments
# after fixing enhancement error files.
#
# This script skips baseline and enhancement steps (already done),
# and runs only Steps 4-7: build enhanced dataset, solver, eval, comparison.
#
# Usage: bash scripts/reports/rerun_fixed_experiments.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

SWEBENCH_PYTHON="${PROJECT_ROOT}/bench_env/bin/python"
RUNNER="${PROJECT_ROOT}/scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py"

# Common args for all reruns
COMMON_ARGS=(
    --skip-baseline
    --skip-enhancement
    --allow-identical-enhancements
    --require-native-enhancer
    --solver-workers 4
    --eval-workers 4
    --eval-timeout 1800
    --max-issues 101
    --enhancer-api-base "http://127.0.0.1:18000/v1"
    --enhancer-model "Devstral-Small-2-24B-Instruct-2512"
    --swebench-python "$SWEBENCH_PYTHON"
)

echo "============================================================"
echo "RE-RUNNING FIXED EXPERIMENTS (Steps 4-7 only)"
echo "============================================================"

# --- SWE-agent Group A ---
echo ""
echo ">>> [1/4] SWE-agent Group A"
echo "============================================================"
"$SWEBENCH_PYTHON" "$RUNNER" \
    --enhancer-agent swe_agent \
    --output-tag devstral101_groupA_20260327 \
    --results-root "${PROJECT_ROOT}/data/samples/101_issues_experiments/results_group_a" \
    --dataset-jsonl "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_a_101/group_a_101_dataset.jsonl" \
    --samples-json "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_a_101/group_a_101_samples.json" \
    --selected-ids-file "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_a_101/group_a_101_instance_ids.txt" \
    "${COMMON_ARGS[@]}" \
    2>&1 | tee "${PROJECT_ROOT}/data/samples/101_issues_experiments/results_group_a/swe_agent__devstral101_groupA_20260327/logs/rerun_steps4to7.log"

# --- SWE-agent Group B ---
echo ""
echo ">>> [2/4] SWE-agent Group B"
echo "============================================================"
"$SWEBENCH_PYTHON" "$RUNNER" \
    --enhancer-agent swe_agent \
    --output-tag devstral101_groupB_20260327 \
    --results-root "${PROJECT_ROOT}/data/samples/101_issues_experiments/results_group_b" \
    --dataset-jsonl "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_b_101/group_b_101_dataset.jsonl" \
    --samples-json "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_b_101/group_b_101_samples.json" \
    --selected-ids-file "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_b_101/group_b_101_instance_ids.txt" \
    "${COMMON_ARGS[@]}" \
    2>&1 | tee "${PROJECT_ROOT}/data/samples/101_issues_experiments/results_group_b/swe_agent__devstral101_groupB_20260327/logs/rerun_steps4to7.log"

# --- TRAE Group A ---
echo ""
echo ">>> [3/4] TRAE Group A"
echo "============================================================"
"$SWEBENCH_PYTHON" "$RUNNER" \
    --enhancer-agent trae \
    --output-tag devstral101_groupA_20260327 \
    --results-root "${PROJECT_ROOT}/data/samples/101_issues_experiments/results_group_a" \
    --dataset-jsonl "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_a_101/group_a_101_dataset.jsonl" \
    --samples-json "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_a_101/group_a_101_samples.json" \
    --selected-ids-file "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_a_101/group_a_101_instance_ids.txt" \
    "${COMMON_ARGS[@]}" \
    2>&1 | tee "${PROJECT_ROOT}/data/samples/101_issues_experiments/results_group_a/trae__devstral101_groupA_20260327/logs/rerun_steps4to7.log"

# --- TRAE Group B ---
echo ""
echo ">>> [4/4] TRAE Group B"
echo "============================================================"
"$SWEBENCH_PYTHON" "$RUNNER" \
    --enhancer-agent trae \
    --output-tag devstral101_groupB_20260327 \
    --results-root "${PROJECT_ROOT}/data/samples/101_issues_experiments/results_group_b" \
    --dataset-jsonl "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_b_101/group_b_101_dataset.jsonl" \
    --samples-json "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_b_101/group_b_101_samples.json" \
    --selected-ids-file "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_b_101/group_b_101_instance_ids.txt" \
    "${COMMON_ARGS[@]}" \
    2>&1 | tee "${PROJECT_ROOT}/data/samples/101_issues_experiments/results_group_b/trae__devstral101_groupB_20260327/logs/rerun_steps4to7.log"

echo ""
echo "============================================================"
echo "ALL 4 EXPERIMENTS RE-RUN COMPLETE"
echo "============================================================"
echo ""
echo "Next: Re-run analysis scripts to update results"
echo "  bash scripts/reports/run_all_101_analysis.sh"
