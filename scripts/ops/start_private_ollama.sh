#!/usr/bin/env bash
# Start (or restart) the dedicated private Ollama on :11435, auto-selecting the
# GPUs that are free RIGHT NOW — the "shuffle" behaviour: we grab whatever idle
# GPUs exist at launch instead of hard-coding 3,4,5,7.
#
# A loaded model can't migrate between GPUs, so "shuffle" = pick free GPUs each
# time this script runs. Pair with watchdog_private_ollama.sh for auto-recovery.
#
# Usage:
#   start_private_ollama.sh [N_GPUS] [MIN_FREE_MIB] [MAX_UTIL] [EXCLUDE_CSV]
# Defaults: N_GPUS=3  MIN_FREE_MIB=36000  MAX_UTIL=50  EXCLUDE=0
#   (GPU-0 excluded by default: system Ollama + the :11434 pilot live there.)
#
# GPU BUDGET POLICY (2026-09-01). This is a shared 8-GPU server and we are one tenant of
# several. Our footprint is capped at MAX_GPUS; N_GPUS is clamped to it no matter what the
# caller passes, so the watchdog's recovery path cannot quietly re-expand us to 8. Two of
# our daemons on four GPUs each is what occupied the whole server before this cap.
# qwen3:32b needs ~20GB of weights and fits comfortably in three A100-80GBs even at the
# 131072-token context we run, so the cap costs throughput, not capability.
# Raise MAX_GPUS deliberately and only when the box is genuinely idle.
set -euo pipefail

MAX_GPUS="${MAX_GPUS:-3}"
N_GPUS="${1:-3}"
if [ "$N_GPUS" -gt "$MAX_GPUS" ]; then
  echo "NOTE: requested $N_GPUS GPUs; clamping to the MAX_GPUS=$MAX_GPUS budget." >&2
  N_GPUS="$MAX_GPUS"
fi
MIN_FREE_MIB="${2:-36000}"
MAX_UTIL="${3:-50}"
EXCLUDE_CSV="${4:-0}"

PORT=11435
MODEL="qwen3:32b"
LOG=/tmp/ollama_private_11435.log

# --- pick free GPUs: free>=MIN_FREE and util<=MAX_UTIL, excluding EXCLUDE, most-free first
mapfile -t PICK < <(
  nvidia-smi --query-gpu=index,memory.free,utilization.gpu --format=csv,noheader,nounits \
  | awk -F', ' -v minf="$MIN_FREE_MIB" -v maxu="$MAX_UTIL" -v excl=",${EXCLUDE_CSV}," '
      { idx=$1+0; free=$2+0; util=$3+0;
        if (index(excl, ","idx",")>0) next;
        if (free>=minf && util<=maxu) print free"\t"idx }' \
  | sort -rn | awk '{print $2}'
)

if [ "${#PICK[@]}" -eq 0 ]; then
  echo "ERROR: no GPU has >=${MIN_FREE_MIB}MiB free and util<=${MAX_UTIL}% (excluding ${EXCLUDE_CSV})." >&2
  echo "Current GPUs:" >&2
  nvidia-smi --query-gpu=index,memory.free,utilization.gpu --format=csv,noheader >&2
  exit 1
fi

CHOSEN=("${PICK[@]:0:$N_GPUS}")
CVD=$(IFS=, ; echo "${CHOSEN[*]}")
echo "Free GPUs available: ${PICK[*]}"
echo "Selecting (up to $N_GPUS): GPU(s) $CVD"
if [ "${#CHOSEN[@]}" -lt "$N_GPUS" ]; then
  echo "NOTE: only ${#CHOSEN[@]} free GPU(s) found (< requested $N_GPUS) — using those." >&2
fi

# --- kill existing private daemon on :11435 (NOT the system one on :11434)
OLD=$(ss -ltnp 2>/dev/null | grep ":${PORT} " | grep -oP 'pid=\K[0-9]+' | head -1 || true)
if [ -n "${OLD:-}" ]; then
  echo "Stopping existing private Ollama (pid=$OLD) on :$PORT ..."
  kill "$OLD" 2>/dev/null || true
  for _ in 1 2 3 4 5; do ss -ltn 2>/dev/null | grep -q ":${PORT} " || break; sleep 1; done
fi

# --- launch pinned to the chosen GPUs
echo "Launching private Ollama on :$PORT pinned to GPUs $CVD ..."
OLLAMA_HOST=127.0.0.1:${PORT} \
OLLAMA_MODELS="${OLLAMA_MODELS_DIR:-/data/22pf2_data/ollama_models}" \
CUDA_VISIBLE_DEVICES="$CVD" \
OLLAMA_SCHED_SPREAD=1 \
OLLAMA_NUM_PARALLEL=8 \
OLLAMA_KEEP_ALIVE=-1 \
OLLAMA_MAX_LOADED_MODELS=1 \
nohup /usr/local/bin/ollama serve > "$LOG" 2>&1 &
echo "serve pid: $!"

# --- wait for daemon, then warm up the model
for _ in $(seq 1 20); do
  curl -s --max-time 3 "http://127.0.0.1:${PORT}/api/version" >/dev/null 2>&1 && break
  sleep 1
done
echo "Warming up $MODEL (loads it onto GPUs $CVD) ..."
curl -s --max-time 180 "http://127.0.0.1:${PORT}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Say OK\"}],\"max_tokens\":32}" \
  >/dev/null 2>&1 || { echo "ERROR: warmup request failed" >&2; exit 1; }

echo "OK. Loaded model:"
curl -s "http://127.0.0.1:${PORT}/api/ps" 2>&1 \
  | python3 -c "import sys,json; [print('  ',m['name'],m['size_vram']//1024//1024//1024,'GB') for m in json.load(sys.stdin).get('models',[])]" 2>&1
echo "Endpoint: http://localhost:${PORT}/v1  (GPUs $CVD)"
