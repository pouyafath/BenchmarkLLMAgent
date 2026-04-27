#!/bin/bash
# Run remaining 3 experiments: SWE-agent Group B, TRAE Group A, TRAE Group B
# SWE-agent Group A eval is already running separately.
# No set -e - individual failures don't kill the pipeline.

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

SWEBENCH_PYTHON="${PROJECT_ROOT}/bench_env/bin/python"
RUNNER="${PROJECT_ROOT}/scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py"

LOG_FILE="${PROJECT_ROOT}/data/samples/101_issues_experiments/remaining_3_experiments.log"

log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $*" | tee -a "$LOG_FILE"
}

COMMON_ARGS=(
    --skip-baseline
    --skip-enhancement
    --allow-identical-enhancements
    --require-native-enhancer
    --solver-workers 2
    --eval-workers 4
    --eval-timeout 1800
    --max-issues 101
    --enhancer-api-base "http://127.0.0.1:18000/v1"
    --enhancer-model "Devstral-Small-2-24B-Instruct-2512"
    --swebench-python "$SWEBENCH_PYTHON"
)

run_experiment() {
    local label="$1"
    local agent="$2"
    local group_dir="$3"
    local dataset_subdir="$4"
    local group_tag="$5"

    log ""
    log ">>> $label"
    log "============================================================"

    "$SWEBENCH_PYTHON" "$RUNNER" \
        --enhancer-agent "$agent" \
        --output-tag "devstral101_${group_tag}_20260327" \
        --results-root "${PROJECT_ROOT}/data/samples/101_issues_experiments/${group_dir}" \
        --dataset-jsonl "${PROJECT_ROOT}/data/samples/101_issues_experiments/${dataset_subdir}/${dataset_subdir}_dataset.jsonl" \
        --samples-json "${PROJECT_ROOT}/data/samples/101_issues_experiments/${dataset_subdir}/${dataset_subdir}_samples.json" \
        --selected-ids-file "${PROJECT_ROOT}/data/samples/101_issues_experiments/${dataset_subdir}/${dataset_subdir}_instance_ids.txt" \
        "${COMMON_ARGS[@]}" \
        2>&1 | tee -a "$LOG_FILE"

    local ec=$?
    log ">>> $label finished (exit=$ec)"
    return 0  # Always continue
}

log "============================================================"
log "RUNNING REMAINING 3 EXPERIMENTS"
log "============================================================"

# Wait for SWE-agent Group A eval to finish first
log "Waiting for SWE-agent Group A eval to complete..."
while ps aux | grep -v grep | grep -q "swe_agent_groupA_eval"; do
    sleep 30
done
log "SWE-agent Group A eval done. Proceeding."

# 1. SWE-agent Group B
run_experiment "[1/3] SWE-agent Group B" "swe_agent" "results_group_b" "group_b_101" "groupB"

# 2. TRAE Group A
run_experiment "[2/3] TRAE Group A" "trae" "results_group_a" "group_a_101" "groupA"

# 3. TRAE Group B
run_experiment "[3/3] TRAE Group B" "trae" "results_group_b" "group_b_101" "groupB"

log ""
log "============================================================"
log "ALL 3 REMAINING EXPERIMENTS COMPLETE"
log "============================================================"
log "Next: bash scripts/reports/run_all_101_analysis.sh"
