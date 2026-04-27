#!/bin/bash
# Master launcher: Chain B → C experiments after A completes
# A is already running separately. This script waits for A to finish,
# then runs B, then C.
set -e
cd /home/22pf2/BenchmarkLLMAgent

echo "=== Master P2P Experiment Sequencer ==="
echo "Started at: $(date -u)"

# Wait for Approach A to finish (check for its preds.json)
A_PREDS="results/groupC50_p2p_approachA/code_context__code_context_devstral_tp_p2p_groupC50_20260413/enhanced_solver_run/preds.json"
echo "Waiting for Approach A to complete..."
while [ ! -f "$A_PREDS" ]; do
    sleep 60
    echo "  $(date -u): Still waiting for A..."
done
echo "Approach A solver done at: $(date -u)"
# Give extra time for A's eval+comparison to finish
sleep 120

# ── Approach B: Regression Guard Prompt ──
echo ""
echo "=== Starting Approach B ==="
bash scripts/run_p2p_approachB.sh
echo "Approach B completed at: $(date -u)"

# ── Approach C: Retry Loop ──
echo ""
echo "=== Starting Approach C ==="
bench_env/bin/python scripts/run_p2p_approachC.py
echo "Approach C completed at: $(date -u)"

echo ""
echo "=== All P2P experiments completed ==="
echo "Finished at: $(date -u)"
echo ""
echo "Results:"
echo "  A: results/groupC50_p2p_approachA/code_context__code_context_devstral_tp_p2p_groupC50_20260413/"
echo "  B: results/groupC50_p2p_approachB/code_context__code_context_devstral_tp_regguard_groupC50_20260414/"
echo "  C: results/groupC50_p2p_approachC/code_context__code_context_devstral_tp_retry_groupC50_20260414/"
