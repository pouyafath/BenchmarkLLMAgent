#!/usr/bin/env bash
# Post-run-4 sequence, unattended:
#   1. wait for the append-only scoring to finish
#   2. apply the 3-GPU budget (see start_private_ollama.sh)
#   3. launch the F2P re-derivation (Docker only; it needs no GPU)
ROOT=/home/22pf2/BenchmarkLLMAgent
SCR=/home/22pf2/tmp/claude-10136/-home-22pf2-BenchmarkLLMAgent/4e1bec19-55a0-47d5-80ca-555e473168e0/scratchpad
ts() { date '+%F %H:%M:%S'; }

# Anchor on a command that STARTS with a python interpreter: `pgrep -f name` also matches
# any shell wrapper that merely mentions the name, which reports a process that never ran.
running() { ps -eo cmd --no-headers | grep -qE "^[^ ]*python[^ ]*[ ].*$1"; }

echo "[$(ts)] waiting for score_run4 to finish"
while running "score_run4\.py"; do sleep 60; done
echo "[$(ts)] scoring done: $(ls "$ROOT/runs/stage6_run4_appendonly/arms" | wc -l)/24 arms"

echo "[$(ts)] ---- applying 3-GPU budget ----"
# The watchdog restarts :11435 on a confirmed death, so stop it first or it races us.
pkill -f 'bash.*watchdog_private_ollama' 2>/dev/null && echo "[$(ts)] watchdog stopped"
sleep 2

# :11436 was spun up to add capacity for the reruns and is no longer needed. Stopping it
# frees its four GPUs outright. :11434 belongs to another tenant and is never touched.
P36=$(ss -ltnp 2>/dev/null | grep ':11436 ' | grep -oP 'pid=\K[0-9]+' | head -1)
if [ -n "${P36:-}" ]; then
  echo "[$(ts)] stopping the :11436 daemon (pid $P36), freeing its GPUs"
  kill "$P36" 2>/dev/null
  for _ in $(seq 1 15); do ss -ltn 2>/dev/null | grep -q ':11436 ' || break; sleep 1; done
fi

# Relaunch :11435 on three GPUs. The launcher picks from what is free right now, skips
# GPU-0 by default and skips anything above 50% util, so the other tenant's busy GPU is
# excluded automatically rather than by hard-coding an index that may change.
echo "[$(ts)] relaunching :11435 on 3 GPUs"
bash "$ROOT/scripts/ops/start_private_ollama.sh" 3 2>&1 | sed "s/^/[$(ts)] launcher: /"

nohup bash "$ROOT/scripts/ops/watchdog_private_ollama.sh" 120 3 \
      >> "$SCR/ollama_watchdog.log" 2>&1 &
echo "[$(ts)] watchdog restarted with a 3-GPU recovery budget"
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader | sed "s/^/[$(ts)] gpu /"

echo "[$(ts)] ---- launching F2P re-derivation (279 PRE container runs) ----"
cd "$ROOT" || exit 1
nohup bench_env/bin/python scripts/evaluate/derive_f2p.py pre >> "$SCR/derive_f2p.log" 2>&1 &
echo "[$(ts)] derive_f2p pre started (pid $!)"
