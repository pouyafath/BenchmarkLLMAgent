#!/usr/bin/env bash
# Live progress for the enhancer x solver matrix re-run.
#   one-shot : bash scripts/ops/track_matrix.sh
#   live     : watch -n 30 -c bash /home/22pf2/BenchmarkLLMAgent/scripts/ops/track_matrix.sh
ROOT=/home/22pf2/BenchmarkLLMAgent
cd "$ROOT" || exit 1

SCR=/home/22pf2/tmp/claude-10136/-home-22pf2-BenchmarkLLMAgent/4e1bec19-55a0-47d5-80ca-555e473168e0/scratchpad
# batch: A (GPUs 0,1,2,5 via :11435) or B (GPUs 3,4,6,7 via :11436)
BATCH=${1:-A}
if [ "$BATCH" = "B" ]; then
  RD=$(ls -1dt runs/rerun2_qwen3_B_*/ 2>/dev/null | head -1)
  LOG=$SCR/rerun2_B.log; DS=data/rerun_matrix_40b.jsonl; PAT='[r]un_matrix_test_b'
else
  RD=$(ls -1dt runs/rerun2_qwen3_A_*/ 2>/dev/null | head -1)
  LOG=$SCR/rerun2_A.log;   DS=data/rerun_matrix_40.jsonl;  PAT='[r]un_matrix_test.py'
fi
N=$(wc -l < "$DS" 2>/dev/null || echo 40)

printf '\n\033[1m== MATRIX RE-RUN · batch %s ==\033[0m  %s\n' "$BATCH" "$(date '+%H:%M:%S')"

pid=$(ps -eo pid,cmd --no-headers 2>/dev/null | grep "$PAT" | awk '{print $1}' | head -1)
if [ -n "$pid" ]; then
  printf '  pid %s   elapsed %s   %s\n\n' "$pid" "$(ps -o etime= -p "$pid" | tr -d ' ')" "$RD"
else
  printf '  \033[1mno matrix process running\033[0m   %s\n\n' "$RD"
fi

bar(){ local d=$1 t=$2 w=22 f
  [ "$t" -gt 0 ] 2>/dev/null || { printf '[%*s]' $w ''; return; }
  f=$(( d*w/t )); printf '['
  [ $f -gt 0 ] && printf '#%.0s' $(seq 1 $f)
  [ $((w-f)) -gt 0 ] && printf -- '-%.0s' $(seq 1 $((w-f)))
  printf ']'; }

# ---- phase 1: enhancement (3 enhancers x N instances) ----
printf '\033[1mENHANCE\033[0m  (agents explore /testbed; must finish before solving)\n'
tot_e=0
for e in openhands aider; do
  n=$(grep -cE "\[enh:$e\] [^ ]+: (OK|FALLBACK)" "$LOG" 2>/dev/null); n=${n:-0}
  ok=$(grep -cE "\[enh:$e\] [^ ]+: OK" "$LOG" 2>/dev/null); ok=${ok:-0}
  tot_e=$((tot_e+n))
  printf '  %-11s %s %3s/%-3s  (%s enriched, %s left)\n' "$e" "$(bar "$n" "$N")" "$n" "$N" "$ok" "$((N-n))"
done
printf '  %-11s %s %3s/%-3s\n\n' "TOTAL" "$(bar $tot_e $((N*2)))" "$tot_e" "$((N*2))"

# ---- phase 2: the 12 solver cells ----
printf '\033[1mSOLVE\033[0m  (2 states x 3 solvers = 6 cells)\n'
done_cells=0
for solver in openhands swe_agent aider; do
  for state in enh_openhands enh_aider; do
    w="$RD/qwen3_32b/stage5/${state}__solver_${solver}/work"
    p="$RD/qwen3_32b/stage5/${state}__solver_${solver}/preds.json"
    if [ -f "$p" ]; then
      ne=$(python3 -c "
import json,sys
try:
  d=json.load(open('$p')); print(sum(1 for v in d.values() if (v.get('model_patch') or '').strip()))
except Exception: print(0)" 2>/dev/null)
      printf '  %-30s \033[1mDONE\033[0m  %s non-empty patches\n' "${state} -> ${solver}" "$ne"
      done_cells=$((done_cells+1))
    elif [ -d "$w" ]; then
      c=$(ls -1 "$w" 2>/dev/null | wc -l)
      printf '  %-30s %s %3s/%-3s running\n' "${state} -> ${solver}" "$(bar "$c" "$N")" "$c" "$N"
    else
      printf '  %-30s %s   queued\n' "${state} -> ${solver}" "$(bar 0 "$N")"
    fi
  done
done
printf '\n  cells complete: %s/6   (baseline + enh:swe_agent already valid from run 1)\n' "$done_cells"

# ---- resources ----
printf '\n  containers: %s   RAM free: %sGB   disk free: %s\n' \
  "$(docker ps -q 2>/dev/null | wc -l)" \
  "$(free -g | awk '/Mem:/{print $7}')" \
  "$(df -h / | tail -1 | awk '{print $4}')"
printf '  GPU util:'
nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader 2>/dev/null \
  | awk -F', ' '{printf " g%s:%s", $1, $2}'
printf '\n\n'

# ---- recent activity ----
printf '\033[1mrecent\033[0m\n'
grep -E "\[enh:|SOLVE|LLM =|ERROR|Traceback" "$LOG" 2>/dev/null | tail -4 | sed 's/^/  /'
printf '\n'
