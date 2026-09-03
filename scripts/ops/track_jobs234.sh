#!/usr/bin/env bash
# Live tracker for jobs 2-4 (missing cells -> tranche-100 recovery -> replication-80).
ROOT=/home/22pf2/BenchmarkLLMAgent
SCR=/home/22pf2/tmp/claude-10136/-home-22pf2-BenchmarkLLMAgent/4e1bec19-55a0-47d5-80ca-555e473168e0/scratchpad
running() { ps -eo cmd --no-headers | grep -qE "^[^ ]*python[^ ]*[ ].*$1"; }
while true; do
  clear
  echo "======== $(date '+%F %H:%M:%S') ========================================"
  echo
  echo "CHAIN"
  tail -6 "$SCR/jobs234.log" 2>/dev/null | sed 's/^/  /'
  echo
  a=$(ls "$ROOT/runs/stage6_missing_cells/arms" 2>/dev/null | wc -l)
  c=$(ls -d "$ROOT"/runs/stage6_sample_m1_*_aider_* "$ROOT"/runs/stage6_sample_m1_*_openhands_* 2>/dev/null | wc -l)
  running "score_missing_cells\.py" && s="RUNNING" || s="done/idle"
  echo "JOB 2  score 14 missing cells      [$s]   arms scored: $a"
  echo
  t=$(find "$ROOT/runs/stage6_100_rescore" -name status.json 2>/dev/null | wc -l)
  running "rescore_tranche100\.py" && s="RUNNING" || s="pending/done"
  echo "JOB 3  tranche-100 recovery        [$s]   per-test files: $t / ~336"
  echo
  running "run_matrix_test\.py" && s="RUNNING" || s="pending/done"
  r=$(ls -dt "$ROOT"/runs/replication80_* 2>/dev/null | head -1)
  echo "JOB 4  replication-80              [$s]"
  [ -n "$r" ] && tail -3 "$r/matrix.log" 2>/dev/null | cut -c1-100 | sed 's/^/     /'
  echo
  echo "containers: $(docker ps -q | wc -l)    load:$(uptime | sed 's/.*load average://')"
  echo "GPU (ours = the 3 pinned to :11435):"
  nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null | \
    while IFS=, read p m; do
      printf "   %-10s %s\n" "$(ps -o user= -p ${p// /} 2>/dev/null | tr -d ' ')" "$m"
    done | sort | uniq -c
  sleep 30
done
