#!/usr/bin/env bash
# Wait until the machine is genuinely free, then run the targeted-60 experiment ALONE.
#
# The first attempt was launched alongside four other jobs, hit 209 containers, and
# returned 0/60 patches in both arms after 15 hours. This waits for exclusive use rather
# than competing for it.
ROOT=/home/22pf2/BenchmarkLLMAgent
SCR=/home/22pf2/tmp/claude-10136/-home-22pf2-BenchmarkLLMAgent/4e1bec19-55a0-47d5-80ca-555e473168e0/scratchpad
cd "$ROOT" || exit 1
LOG="$SCR/targeted60_v2.log"
STATUS="$SCR/queue_targeted60.status"

busy() {   # any competing solver / scoring / eval process?
  ps -eo cmd --no-headers 2>/dev/null \
    | grep -cE '[r]un_matrix_test|[s]core_run[13]\.sh|[e]valuation\.py|[r]ecover_74\.py'
}

echo "$(date '+%F %T') waiting for exclusive use" > "$STATUS"
while true; do
  n=$(busy); c=$(docker ps -q 2>/dev/null | wc -l)
  if [ "$n" -eq 0 ] && [ "$c" -le 10 ]; then
    echo "$(date '+%F %T') box free (jobs=$n containers=$c) — starting" >> "$STATUS"
    break
  fi
  echo "$(date '+%F %T') waiting: $n competing job(s), $c containers" > "$STATUS"
  sleep 300
done

# keep the reaper alive for the duration so leaks cannot accumulate again
pgrep -f reap_leaked.sh >/dev/null 2>&1 || nohup bash scripts/ops/reap_leaked.sh >> "$SCR/reaper.log" 2>&1 &

bench_env/bin/python scripts/workflows/run_repo_grounded_cell.py \
  --model qwen3:32b --base-url http://localhost:11435/v1 --api-key ollama \
  --instances-file /tmp/targeted60_ids.txt --tag targeted60v2 \
  --workers 6 --max-iter 30 --enh-max-iter 30 >> "$LOG" 2>&1

echo "$(date '+%F %T') targeted-60 finished (rc=$?)" >> "$STATUS"
