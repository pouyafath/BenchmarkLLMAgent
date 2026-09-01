#!/usr/bin/env bash
# Live tracker for run-4 append-only scoring + the F2P re-derivation that follows it.
ROOT=/home/22pf2/BenchmarkLLMAgent
SCR=/home/22pf2/tmp/claude-10136/-home-22pf2-BenchmarkLLMAgent/4e1bec19-55a0-47d5-80ca-555e473168e0/scratchpad
# Detect a live job WITHOUT matching this script's own command line.
# pgrep -f <name> matches any shell wrapper that merely mentions the name, which reports a
# phantom RUNNING (observed: a tracker claiming derive_f2p was live when nothing had run).
# Anchoring on a command that *starts* with a python interpreter excludes bash wrappers.
running() { ps -eo cmd --no-headers | grep -qE "^[^ ]*python[^ ]*[ ].*$1"; }

while true; do
  clear
  echo "===== $(date '+%F %H:%M:%S') ====================================="
  a=$(ls "$ROOT/runs/stage6_run4_appendonly/arms" 2>/dev/null | wc -l)
  echo "run-4 scoring:  $a/24 arms   containers: $(docker ps -q | wc -l)"
  running "score_run4\.py" && echo "  status: RUNNING" || echo "  status: not running"
  echo
  echo "--- arms completed ---"
  tail -12 "$SCR/score_run4.log" 2>/dev/null | sed 's/^/  /'
  echo
  p=$(find "$ROOT/runs/f2p_rederive/pre" -name status.json 2>/dev/null | wc -l)
  if [ "$p" -gt 0 ] || running "derive_f2p\.py"; then
    echo "--- F2P re-derivation: $p/279 PRE runs ---"
    running "derive_f2p\.py" && echo "  status: RUNNING" || echo "  status: not running"
  fi
  echo
  echo "--- GPUs (budget: 3 of 8) ---"
  nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader | sed 's/^/  gpu /'
  echo
  echo "--- chain ---"
  tail -4 "$SCR/after_run4_chain.log" 2>/dev/null | sed 's/^/  /'
  echo
  echo "load: $(uptime | sed 's/.*load average/load/')   free RAM: $(free -g | awk '/Mem:/{print $7}')GB"
  sleep 30
done
