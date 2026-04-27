#!/bin/bash
# Robust re-run of remaining experiments.
# - SWE-agent Group A: runs solver WITHOUT --redo-existing (picks up 8 remaining)
# - Other 3: run full Steps 4-7
# Does NOT use set -e; individual failures don't kill the pipeline.
# Uses 2 workers to reduce vLLM timeout pressure.

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

SWEBENCH_PYTHON="${PROJECT_ROOT}/bench_env/bin/python"
RUNNER="${PROJECT_ROOT}/scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py"
SOLVER="${PROJECT_ROOT}/scripts/solvers/run_mini_sweagent_jsonl.py"

LOG_FILE="${PROJECT_ROOT}/data/samples/101_issues_experiments/rerun_robust_output.log"

log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $*" | tee -a "$LOG_FILE"
}

log "============================================================"
log "ROBUST RE-RUN (2 workers, no set -e)"
log "============================================================"

# ── 1. Finish SWE-agent Group A solver (8 remaining issues) ──
log ""
log ">>> [1/4] SWE-agent Group A - finishing solver (8 remaining)"
log "============================================================"

SWA_DIR="${PROJECT_ROOT}/data/samples/101_issues_experiments/results_group_a/swe_agent__devstral101_groupA_20260327"

# Run solver WITHOUT --redo-existing to skip the 93 already done
"$SWEBENCH_PYTHON" "$SOLVER" \
    --dataset-jsonl "${SWA_DIR}/secondpaper10_enhanced_swe_agent.jsonl" \
    --workers 2 \
    --output "${SWA_DIR}/enhanced_solver_run" \
    --model-class minisweagent.models.litellm_textbased_model.LitellmTextbasedModel \
    -c /home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks.yaml \
    -c /home/22pf2/SWE-Bench_Replication/config/devstral_vllm_override.yaml \
    2>&1 | tee -a "$LOG_FILE"
log ">>> SWE-agent Group A solver finished (exit=$?)"

# Now run eval + comparison via the workflow script (skip baseline + enhancement + solver)
log ">>> SWE-agent Group A - running eval + comparison"
"$SWEBENCH_PYTHON" "$RUNNER" \
    --enhancer-agent swe_agent \
    --output-tag devstral101_groupA_20260327 \
    --results-root "${PROJECT_ROOT}/data/samples/101_issues_experiments/results_group_a" \
    --dataset-jsonl "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_a_101/group_a_101_dataset.jsonl" \
    --samples-json "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_a_101/group_a_101_samples.json" \
    --selected-ids-file "${PROJECT_ROOT}/data/samples/101_issues_experiments/group_a_101/group_a_101_instance_ids.txt" \
    --skip-baseline \
    --skip-enhancement \
    --skip-solver \
    --allow-identical-enhancements \
    --require-native-enhancer \
    --eval-workers 4 \
    --eval-timeout 1800 \
    --max-issues 101 \
    --enhancer-api-base "http://127.0.0.1:18000/v1" \
    --enhancer-model "Devstral-Small-2-24B-Instruct-2512" \
    --swebench-python "$SWEBENCH_PYTHON" \
    2>&1 | tee -a "$LOG_FILE"
log ">>> SWE-agent Group A eval+comparison finished (exit=$?)"

# Common args for remaining experiments (full Steps 4-7)
run_full_experiment() {
    local label="$1"
    local agent="$2"
    local group_dir="$3"
    local dataset_dir="$4"
    local group_tag="$5"

    log ""
    log ">>> $label"
    log "============================================================"

    "$SWEBENCH_PYTHON" "$RUNNER" \
        --enhancer-agent "$agent" \
        --output-tag "devstral101_${group_tag}_20260327" \
        --results-root "${PROJECT_ROOT}/data/samples/101_issues_experiments/${group_dir}" \
        --dataset-jsonl "${PROJECT_ROOT}/data/samples/101_issues_experiments/${dataset_dir}/${dataset_dir##*/}_dataset.jsonl" \
        --samples-json "${PROJECT_ROOT}/data/samples/101_issues_experiments/${dataset_dir}/${dataset_dir##*/}_samples.json" \
        --selected-ids-file "${PROJECT_ROOT}/data/samples/101_issues_experiments/${dataset_dir}/${dataset_dir##*/}_instance_ids.txt" \
        --skip-baseline \
        --skip-enhancement \
        --allow-identical-enhancements \
        --require-native-enhancer \
        --solver-workers 2 \
        --eval-workers 4 \
        --eval-timeout 1800 \
        --max-issues 101 \
        --enhancer-api-base "http://127.0.0.1:18000/v1" \
        --enhancer-model "Devstral-Small-2-24B-Instruct-2512" \
        --swebench-python "$SWEBENCH_PYTHON" \
        2>&1 | tee -a "$LOG_FILE"

    log ">>> $label finished (exit=$?)"
}

# 2. SWE-agent Group B (full Steps 4-7)
run_full_experiment "[2/4] SWE-agent Group B" "swe_agent" "results_group_b" "group_b_101" "groupB"

# 3. TRAE Group A (full Steps 4-7)
run_full_experiment "[3/4] TRAE Group A" "trae" "results_group_a" "group_a_101" "groupA"

# 4. TRAE Group B (full Steps 4-7)
run_full_experiment "[4/4] TRAE Group B" "trae" "results_group_b" "group_b_101" "groupB"

log ""
log "============================================================"
log "ALL 4 EXPERIMENTS COMPLETE"
log "============================================================"
log "Next: bash scripts/reports/run_all_101_analysis.sh"
