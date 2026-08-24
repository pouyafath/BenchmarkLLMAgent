#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# NODE1 2-AGENT PILOT LAUNCHER
#
# Runs openhands and swe_agent as BOTH enhancer AND solver (paired).
# Each run includes:
#   - Stage 4 : enhancement  (4 parallel Ollama threads)
#   - Stage 5 : baseline solving THEN enhanced solving  (4 solver workers each)
#   - Stage 6 : comparison report
#
# LLM: gpt-oss:120b via Ollama @ localhost:11435  (OLLAMA_NUM_PARALLEL=4)
# Max concurrent Ollama requests: 4 (one stage at a time, 4 workers each).
#
# Usage:
#   bash scripts/workflows/launch_node1_2agent_pilot.sh            # full
#   bash scripts/workflows/launch_node1_2agent_pilot.sh resume     # resume both
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail
cd /home/22pf2/BenchmarkLLMAgent

PYTHON="bench_env/bin/python"
LOG_DIR="logs/node1_2agent_pilot"
mkdir -p "$LOG_DIR"

MODE="${1:-full}"   # full | resume

echo "═══════════════════════════════════════════════════════════"
echo "  NODE1 2-AGENT PILOT  |  mode=$MODE  |  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "  Ollama: gpt-oss:120b @ localhost:11435  |  PARALLEL=4"
echo "  Pairs: openhands+openhands  |  swe_agent+swe_agent"
echo "═══════════════════════════════════════════════════════════"

run_pair() {
  local name="$1"
  local script="scripts/workflows/run_node1_2agent_pilot_${name}.py"
  local log="$LOG_DIR/${name}.log"
  local flag=""
  [[ "$MODE" == "resume" ]] && flag="--resume"
  echo ""
  echo "[$(date -u '+%H:%M:%S UTC')] ▶ Starting pair: $name  (log: $log)"
  $PYTHON "$script" $flag 2>&1 | tee "$log"
  echo "[$(date -u '+%H:%M:%S UTC')] ✓ Pair done: $name"
}

run_pair openhands
run_pair swe_agent

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ALL PAIRS COMPLETE  |  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "═══════════════════════════════════════════════════════════"
