#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# NODE1 ALL-494 PARALLEL PIPELINE LAUNCHER
#
# Stage 4 strategy : run ONE enhancer at a time, but each uses 4 parallel
#                    threads internally → always 4 concurrent Ollama requests.
#
# Stage 5/6 strategy: SOLVER_WORKERS=4 per enhancer, sequential across enhancers.
#
# Ollama: gpt-oss:120b @ http://localhost:11435  (OLLAMA_NUM_PARALLEL=4)
#
# Usage:
#   bash scripts/workflows/launch_node1_all494_pipeline.sh           # Stage 4+5+6
#   bash scripts/workflows/launch_node1_all494_pipeline.sh stage4    # Stage 4 only
#   bash scripts/workflows/launch_node1_all494_pipeline.sh resume    # Resume all (5/6)
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

cd /home/22pf2/BenchmarkLLMAgent

PYTHON="bench_env/bin/python"
LOG_DIR="logs/node1_all494_pipeline"
mkdir -p "$LOG_DIR"

MODE="${1:-full}"   # full | stage4 | resume

ENHANCERS=(
  openhands
  swe_agent
  aider
  mini_swe_agent
  live_swe_agent
  trae
  cl_enhanced_gemma3
  simple_enhancer
)

run_stage4() {
  local enhancer="$1"
  local script="scripts/workflows/run_node1_all494_${enhancer}.py"
  local log="$LOG_DIR/stage4_${enhancer}.log"
  echo "[$(date -u '+%H:%M:%S UTC')] ▶ Stage 4: $enhancer  (log: $log)"
  $PYTHON "$script" --stage4-only > "$log" 2>&1
  echo "[$(date -u '+%H:%M:%S UTC')] ✓ Stage 4 done: $enhancer"
}

run_stage56() {
  local enhancer="$1"
  local script="scripts/workflows/run_node1_all494_${enhancer}.py"
  local log="$LOG_DIR/stage56_${enhancer}.log"
  echo "[$(date -u '+%H:%M:%S UTC')] ▶ Stage 5/6: $enhancer  (log: $log)"
  $PYTHON "$script" --resume > "$log" 2>&1
  echo "[$(date -u '+%H:%M:%S UTC')] ✓ Stage 5/6 done: $enhancer"
}

echo "═══════════════════════════════════════════════════════════"
echo "  NODE1 ALL-494 PIPELINE  |  mode=$MODE  |  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "  Ollama: gpt-oss:120b @ localhost:11435  |  PARALLEL=4"
echo "  Enhancers: ${#ENHANCERS[@]} total"
echo "═══════════════════════════════════════════════════════════"

if [[ "$MODE" == "stage4" || "$MODE" == "full" ]]; then
  echo ""
  echo "── STAGE 4: enhancement (4 parallel threads per enhancer) ──"
  for enhancer in "${ENHANCERS[@]}"; do
    run_stage4 "$enhancer"
  done
  echo ""
  echo "✓ All Stage 4 complete."
fi

if [[ "$MODE" == "resume" || "$MODE" == "full" ]]; then
  echo ""
  echo "── STAGE 5/6: solver + eval (SOLVER_WORKERS=4 per enhancer) ──"
  for enhancer in "${ENHANCERS[@]}"; do
    run_stage56 "$enhancer"
  done
  echo ""
  echo "✓ All Stage 5/6 complete."
fi

echo ""
echo "Pipeline finished at $(date -u '+%Y-%m-%d %H:%M UTC')"
