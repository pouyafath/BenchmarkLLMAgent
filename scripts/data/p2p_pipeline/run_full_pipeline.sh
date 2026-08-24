#!/bin/bash
# P2P Pipeline — Full automated chain (Steps 4 → 9)
#
# Waits for Paul Stage 2 to finish, then runs:
#   Step 4: Collect Stage 2 results
#   Step 5: (Stage 3 full suite — skipped for now, run later on final subset)
#   Steps 6-9: Enhancer+Solver experiment on first 10 instances (test run)
#
# Usage:
#   nohup bash scripts/data/p2p_pipeline/run_full_pipeline.sh > runs/p2p_pipeline_auto.log 2>&1 &
#
# Monitor:
#   python scripts/data/p2p_pipeline/monitor.py
#   tail -f runs/p2p_pipeline_auto.log

set -euo pipefail
cd /home/22pf2/BenchmarkLLMAgent

PAUL_WS="/home/22pf2/paul-RepoLaunch/workspace/p2p_pipeline_stage2_20260515"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "[$(date)] P2P Pipeline auto-chain started"

# ── Wait for Paul to finish ──────────────────────────────────────────────────
echo "[$(date)] Waiting for Paul/RepoLaunch to complete..."
while pgrep -f "paul.run.*p2p_pipeline_stage2" > /dev/null 2>&1; do
    COMPLETED=$(find "$PAUL_WS/playground/" -name "result.json" 2>/dev/null | wc -l)
    echo "[$(date)] Paul still running... $COMPLETED/387 completed"
    sleep 120
done
echo "[$(date)] Paul/RepoLaunch finished!"

# ── Step 4: Collect Stage 2 results ──────────────────────────────────────────
echo "[$(date)] Step 4: Collecting Paul results..."
python scripts/data/p2p_pipeline/stage2_collect_results.py
STAGE2_COUNT=$(wc -l < data/samples/pouya_p2p_pipeline/stage2_approach2/dataset.jsonl)
echo "[$(date)] Stage 2 collected: $STAGE2_COUNT validated instances"

if [ "$STAGE2_COUNT" -eq 0 ]; then
    echo "[$(date)] ERROR: No Stage 2 instances survived. Aborting."
    exit 1
fi

# ── Steps 6-9: Experiment (test run with limit=10) ───────────────────────────
EXPERIMENT_DIR="runs/p2p_experiment_test_${TIMESTAMP}"
echo "[$(date)] Steps 6-9: Running test experiment (limit=10) → $EXPERIMENT_DIR"

python scripts/data/p2p_pipeline/run_experiment.py \
    --stage2-dataset data/samples/pouya_p2p_pipeline/stage2_approach2/dataset.jsonl \
    --run-dir "$EXPERIMENT_DIR" \
    --limit 10 \
    --enhancer llm_append_analysis

echo "[$(date)] Test experiment complete → $EXPERIMENT_DIR"
echo "[$(date)] Check results: cat $EXPERIMENT_DIR/analysis_summary.txt"
echo "[$(date)] Full monitor:  python scripts/data/p2p_pipeline/monitor.py"
echo "[$(date)] P2P Pipeline auto-chain DONE"
