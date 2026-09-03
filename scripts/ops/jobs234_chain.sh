#!/usr/bin/env bash
# Serialize jobs 2-4. They all drive the Docker harness, and running harness jobs
# concurrently is what produced 209 containers and 115 timeouts on targeted-60 v1.
ROOT=/home/22pf2/BenchmarkLLMAgent
SCR=/home/22pf2/tmp/claude-10136/-home-22pf2-BenchmarkLLMAgent/4e1bec19-55a0-47d5-80ca-555e473168e0/scratchpad
cd "$ROOT" || exit 1
ts() { date '+%F %H:%M:%S'; }
# Anchor on a command starting with a python interpreter: `pgrep -f name` also matches any
# shell wrapper mentioning the name, which reports a process that never ran.
running() { ps -eo cmd --no-headers | grep -qE "^[^ ]*python[^ ]*[ ].*$1"; }
wait_for() { while running "$1"; do sleep 60; done; }

ps -eo cmd --no-headers | grep -qE '^(/bin/)?bash .*reap_leaked' || \
  nohup bash "$ROOT/scripts/ops/reap_leaked.sh" >> "$SCR/reaper.log" 2>&1 &

echo "[$(ts)] JOB 2 running: score the 14 unscored run-1/run-3 cells"
wait_for "score_missing_cells\.py"
echo "[$(ts)] JOB 2 done"

echo "[$(ts)] JOB 3 start: recover per-test artifacts for the first-100 tranche (28 gradeable)"
bench_env/bin/python scripts/evaluate/rescore_tranche100.py >> "$SCR/rescore_tranche100.log" 2>&1
echo "[$(ts)] JOB 3 done"

echo "[$(ts)] JOB 4 start: replicate enh:openhands -> sol:aider on a fresh, disjoint 80"
# Single cell only: without MATRIX_SOLVERS this would also run the two solvers the
# pre-registered test does not measure.
MATRIX_ENHANCERS=openhands \
MATRIX_SOLVERS=aider \
ENH_WORKERS=4 \
OLLAMA_MODEL=qwen3:32b \
bench_env/bin/python scripts/workflows/run_matrix_test.py \
  --dataset data/replication80_openhands_aider.jsonl \
  --llms qwen3:32b --tag replication80 --workers 4 \
  >> "$SCR/replication80.log" 2>&1
echo "[$(ts)] JOB 4 solve done — scoring"

RUN=$(ls -dt "$ROOT"/runs/replication80_* 2>/dev/null | head -1)
if [ -n "$RUN" ]; then
  bench_env/bin/python scripts/evaluate/score_sample.py \
    "$RUN/qwen3_32b/stage5" \
    <(python3 -c "
import json
[print(json.loads(l)['instance_id']) for l in open('$ROOT/data/replication80_openhands_aider.jsonl')]") \
    replication80 --enh-dir enh_openhands__solver_aider \
    --baseline-dir baseline__solver_aider --workers 4 \
    >> "$SCR/replication80.log" 2>&1
  echo "[$(ts)] JOB 4 scored"
else
  echo "[$(ts)] JOB 4 ERROR: no replication80 run dir found"
fi
echo "[$(ts)] ALL JOBS DONE"
