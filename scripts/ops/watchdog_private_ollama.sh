#!/usr/bin/env bash
# Conservative watchdog for the private Ollama on :11435.
#
# It ONLY restarts the daemon when the model is genuinely DEAD (endpoint down, or
# no model loaded, or a real generation request fails twice in a row). It does NOT
# restart just because a neighbour appeared on one of our GPUs — restarting reloads
# the model and drops in-flight solver calls, which is costly mid-batch.
#
# On a confirmed death it calls start_private_ollama.sh, which re-selects whatever
# GPUs are free at that moment (the "shuffle" recovery).
#
# Usage:  watchdog_private_ollama.sh [INTERVAL_SEC] [N_GPUS]
# Defaults: INTERVAL_SEC=120  N_GPUS=4
# Run detached:  nohup scripts/ops/watchdog_private_ollama.sh 120 4 > /tmp/ollama_watchdog.log 2>&1 &
set -uo pipefail

INTERVAL="${1:-120}"
N_GPUS="${2:-4}"
PORT=11435
MODEL="qwen3:32b"
HERE="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$HERE/start_private_ollama.sh"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

healthy() {
  # 1) model must be listed as loaded
  curl -s --max-time 8 "http://127.0.0.1:${PORT}/api/ps" 2>/dev/null \
    | grep -q "\"$MODEL\"" || return 1
  # 2) a tiny generation must succeed and be non-empty
  local out
  out=$(curl -s --max-time 60 "http://127.0.0.1:${PORT}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":8}" 2>/dev/null)
  echo "$out" | grep -q '"choices"' || return 1
  return 0
}

echo "[$(ts)] watchdog started: interval=${INTERVAL}s, recover with N_GPUS=${N_GPUS}"
while true; do
  if healthy; then
    : # quiet on healthy
  else
    echo "[$(ts)] UNHEALTHY (check 1) — re-checking in 15s before restart..."
    sleep 15
    if healthy; then
      echo "[$(ts)] recovered on its own, no restart."
    else
      echo "[$(ts)] CONFIRMED DEAD — restarting on currently-free GPUs."
      bash "$LAUNCHER" "$N_GPUS" 2>&1 | sed "s/^/[$(ts)] launcher: /"
      echo "[$(ts)] restart attempt done."
    fi
  fi
  sleep "$INTERVAL"
done
