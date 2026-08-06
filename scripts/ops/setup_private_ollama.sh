#!/usr/bin/env bash
# ==============================================================================
# Reproducible PRIVATE Ollama for the benchmark pipeline — identical on GPU-01 & GPU-02.
#
# WHY: GPU-01 has a SHARED Ollama on :11434 used by other users (18mcs6). It is
#      unreliable for us (model eviction, health-check timeouts) and does NOT exist
#      on GPU-02. So we ALWAYS run our OWN private Ollama on :11435 and never touch
#      :11434. This script produces the exact same endpoint on either node.
#
# GPUs: makes ALL 8 GPUs visible and sets OLLAMA_SCHED_SPREAD=1 so the scheduler
#       distributes the model across every GPU that has free VRAM. On GPU-02 that's
#       all 8; on GPU-01 it transparently uses whichever of the 8 are free (it will
#       not OOM on the GPUs the shared Ollama has filled).
#
# Models live on /home (42 TB, persistent) so they are downloaded once and reused
# forever across runs and reboots — never re-pulled.
#
# Usage:
#   bash scripts/ops/setup_private_ollama.sh            # start + verify + ensure models
#   bash scripts/ops/setup_private_ollama.sh status     # just show health
#   bash scripts/ops/setup_private_ollama.sh restart    # force kill + restart
# ==============================================================================
set -uo pipefail

# ── Fixed, reproducible config ────────────────────────────────────────────────
export OLLAMA_HOST="127.0.0.1:11435"          # private port — NEVER :11434

# GPU selection: we want ALL 8 GPUs, distributing compute across them. But on GPU-01
# the SHARED Ollama already fills GPUs 0,1,2,6 (~77GB each); forcing SCHED_SPREAD onto
# those crashes the runner with CUDA OOM ("llama runner terminated, exit status 2").
# So we auto-detect GPUs with enough FREE VRAM and spread across exactly those:
#   * GPU-02 (all 8 free)  -> uses all 8     (full 8-way distribution)
#   * GPU-01 (4 free)      -> uses the 4 free GPUs (the shared Ollama keeps the rest)
# Same script, adapts per node, never OOMs. Override with FREE_VRAM_MIN_MB / FORCE_GPUS.
FREE_VRAM_MIN_MB="${FREE_VRAM_MIN_MB:-40000}"   # a GPU counts as "free" if it has >40GB free
if [ -n "${FORCE_GPUS:-}" ]; then
  GPUS="$FORCE_GPUS"
else
  GPUS="$(nvidia-smi --query-gpu=index,memory.free --format=csv,noheader,nounits \
          | awk -F', ' -v m="$FREE_VRAM_MIN_MB" '$2+0 >= m {print $1}' | paste -sd, -)"
fi
[ -z "$GPUS" ] && GPUS="0"   # fallback: at least GPU 0
export CUDA_VISIBLE_DEVICES="$GPUS"
export OLLAMA_SCHED_SPREAD="1"                 # distribute compute across the chosen GPUs
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-8}"   # concurrent inference slots. 8 supports
                           # --workers 8 (~3-4x); GPUs were only ~22% util at 4, KV cache fits
                           # (~28GB/GPU of 80GB). Takes effect on the next `restart`.
export OLLAMA_KEEP_ALIVE="-1"                  # never unload the model
export OLLAMA_MAX_LOADED_MODELS="1"            # one model resident (avoid thrash)
# Writable, persistent, NFS-shared model store (visible on BOTH nodes; pulled once,
# reused forever). NOT /home/ollama_shared_models — that is owned by the 'ollama'
# user and is read-only for us (new pulls fail with permission denied there).
export OLLAMA_MODELS="/data/22pf2_data/ollama_models"

# Binary selection. Default = system ollama (proven on this server's driver).
#
# NOTE on MoE models (qwen3-coder:30b, qwen3moe arch): the system ollama (v0.23.4) is too
# old to load them, BUT the newer user-space v0.30.8 binary's CUDA kernels require a newer
# NVIDIA driver than GPU-01/02 have (driver 535 / CUDA 12.2 -> "device kernel image is
# invalid"). So MoE models are blocked here until the driver is upgraded (needs admin).
# The user-space binary path is therefore OPT-IN only (USE_USERSPACE_OLLAMA=1), so the
# default path stays on the proven, working system binary.
USERSPACE_OLLAMA="/home/22pf2/ollama-latest/bin/ollama"
if [ "${USE_USERSPACE_OLLAMA:-0}" = "1" ] && [ -z "${OLLAMA_BIN:-}" ] && [ -x "$USERSPACE_OLLAMA" ]; then
  OLLAMA_BIN="$USERSPACE_OLLAMA"
  export LD_LIBRARY_PATH="/home/22pf2/ollama-latest/lib/ollama:${LD_LIBRARY_PATH:-}"
fi
OLLAMA_BIN="${OLLAMA_BIN:-ollama}"

PORT=11435
LOG="/home/22pf2/ollama_private_11435.log"
MODELS_REQUIRED=("qwen3:32b" "qwen3-coder:30b")

log() { echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $*"; }

ollama_up() { curl -s --max-time 5 "http://127.0.0.1:${PORT}/api/tags" >/dev/null 2>&1; }

show_status() {
  if ollama_up; then
    log "Private Ollama :${PORT} is UP"
    log "GPUs visible: ${CUDA_VISIBLE_DEVICES} | SCHED_SPREAD=${OLLAMA_SCHED_SPREAD} | NUM_PARALLEL=${OLLAMA_NUM_PARALLEL}"
    echo "  Models present:"
    curl -s "http://127.0.0.1:${PORT}/api/tags" | python3 -c "import json,sys;[print('   ',m['name']) for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null
  else
    log "Private Ollama :${PORT} is DOWN"
  fi
}

start_server() {
  if ollama_up; then
    log "Already running on :${PORT}"
    return 0
  fi
  log "Starting private Ollama on :${PORT} (GPUs ${CUDA_VISIBLE_DEVICES}, SCHED_SPREAD=1, bin=${OLLAMA_BIN})..."
  nohup "$OLLAMA_BIN" serve > "$LOG" 2>&1 &
  for i in $(seq 1 30); do
    sleep 1
    ollama_up && { log "Up after ${i}s"; return 0; }
  done
  log "ERROR: did not come up in 30s — see $LOG"; return 1
}

kill_server() {
  # Kill ONLY our private :11435 server (match the OLLAMA_HOST in its env), never the shared one.
  for pid in $(pgrep -u "$USER" -f "ollama serve"); do
    if tr '\0' '\n' < /proc/$pid/environ 2>/dev/null | grep -q "OLLAMA_HOST=127.0.0.1:11435"; then
      log "Killing private ollama serve pid $pid"; kill "$pid" 2>/dev/null
    fi
  done
  sleep 3
}

ensure_models() {
  local present
  present="$(curl -s "http://127.0.0.1:${PORT}/api/tags" | python3 -c "import json,sys;print(' '.join(m['name'] for m in json.load(sys.stdin).get('models',[])))" 2>/dev/null)"
  for m in "${MODELS_REQUIRED[@]}"; do
    if echo "$present" | grep -qw "$m"; then
      log "Model present: $m"
    else
      log "Pulling missing model: $m (one-time; persists in $OLLAMA_MODELS)..."
      OLLAMA_HOST="127.0.0.1:${PORT}" "$OLLAMA_BIN" pull "$m" || log "WARN: pull failed for $m"
    fi
  done
}

case "${1:-up}" in
  status)  show_status ;;
  restart) kill_server; start_server && ensure_models && show_status ;;
  up|*)    start_server && ensure_models && show_status ;;
esac
