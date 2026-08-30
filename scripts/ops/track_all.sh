#!/usr/bin/env bash
# Unified live status: matrix runs (enhance + solve cells) and any scoring job.
#   one-shot : bash scripts/ops/track_all.sh
#   live     : watch -n 30 -c bash /home/22pf2/BenchmarkLLMAgent/scripts/ops/track_all.sh
ROOT=/home/22pf2/BenchmarkLLMAgent
SCR=/home/22pf2/tmp/claude-10136/-home-22pf2-BenchmarkLLMAgent/4e1bec19-55a0-47d5-80ca-555e473168e0/scratchpad
cd "$ROOT" || exit 1
ENHANCERS="openhands trae mini_swe_agent"
SOLVERS="openhands swe_agent aider"

bar(){ local d=$1 t=$2 w=20 f
  [ "$t" -gt 0 ] 2>/dev/null || { printf '[%*s]' $w ''; return; }
  f=$(( d*w/t )); printf '['
  [ $f -gt 0 ] && printf '#%.0s' $(seq 1 $f)
  [ $((w-f)) -gt 0 ] && printf -- '-%.0s' $(seq 1 $((w-f)))
  printf ']'; }

printf '\n\033[1m╔══ BenchmarkLLMAgent — live status ══╗\033[0m  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"

for tag in A B; do
  LOG="$SCR/rerun3_${tag}.log"
  RD=$(ls -1dt runs/rerun3_${tag}_*/ 2>/dev/null | head -1)
  DS=$([ "$tag" = A ] && echo data/rerun_matrix_40.jsonl || echo data/rerun_matrix_40b.jsonl)
  N=$(wc -l < "$DS" 2>/dev/null || echo 40)
  PAT=$([ "$tag" = A ] && echo '[r]un_matrix_test.py' || echo '[r]un_matrix_test_b.py')
  pid=$(ps -eo pid,cmd --no-headers 2>/dev/null | grep "$PAT" | awk '{print $1}' | head -1)

  printf '\n\033[1m── MATRIX batch %s ──\033[0m ' "$tag"
  if [ -n "$pid" ]; then printf 'pid %s  up %s\n' "$pid" "$(ps -o etime= -p "$pid" | tr -d ' ')"
  else printf '\033[2mnot running\033[0m\n'; fi
  [ -d "$RD" ] || { printf '  (no run dir yet)\n'; continue; }

  # enhance phase
  tot=0
  for e in $ENHANCERS; do
    n=$(grep -cE "\[enh:$e\] [^ ]+: (OK|FALLBACK)" "$LOG" 2>/dev/null); n=${n:-0}
    ok=$(grep -cE "\[enh:$e\] [^ ]+: OK" "$LOG" 2>/dev/null); ok=${ok:-0}
    tot=$((tot+n))
    printf '  enh %-15s %s %2s/%-2s  %s ok\n' "$e" "$(bar "$n" "$N")" "$n" "$N" "$ok"
  done
  [ "$tot" -lt $((N*3)) ] && printf '  \033[2m(solving starts when all enhancers finish)\033[0m\n'

  # solve cells
  done_c=0; run_c=0
  for s in $SOLVERS; do for e in $ENHANCERS; do
    p="$RD/qwen3_32b/stage5/enh_${e}__solver_${s}/preds.json"
    w="$RD/qwen3_32b/stage5/enh_${e}__solver_${s}/work"
    if [ -f "$p" ]; then
      ne=$(python3 -c "
import json
try:
  d=json.load(open('$p')); print(sum(1 for v in d.values() if (v.get('model_patch') or '').strip()))
except Exception: print('?')" 2>/dev/null)
      printf '  cell %-28s \033[1mDONE\033[0m  %s non-empty\n' "enh:${e}->${s}" "$ne"
      done_c=$((done_c+1))
    elif [ -d "$w" ]; then
      c=$(ls -1 "$w" 2>/dev/null | wc -l)
      printf '  cell %-28s %s %2s/%-2s\n' "enh:${e}->${s}" "$(bar "$c" "$N")" "$c" "$N"
      run_c=$((run_c+1))
    fi
  done; done
  printf '  \033[1mcells %s/9 done\033[0m  (%s running)\n' "$done_c" "$run_c"
done

# scoring job
printf '\n\033[1m── SCORING (run-1 valid cells) ──\033[0m '
if pgrep -f score_run1.sh >/dev/null 2>&1; then printf 'running\n'; else printf '\033[2mfinished / not running\033[0m\n'; fi
if [ -f "$SCR/score_run1.log" ]; then
  grep -E "^m1_.*baseline .* enhanced .* delta" "$SCR/score_run1.log" 2>/dev/null | tail -6 | sed 's/^/  /'
  cur=$(grep -E "^Scoring m1_" "$SCR/score_run1.log" 2>/dev/null | tail -1 | awk '{print $2}' | tr -d ':')
  [ -n "$cur" ] && printf '  current: %s\n' "$cur"
fi

# queued targeted-60 (waits for exclusive use) + reaper health
printf '\n\033[1m── QUEUED targeted-60 + reaper ──\033[0m\n'
if pgrep -f reap_leaked.sh >/dev/null 2>&1; then printf '  reaper: \033[1mactive\033[0m'; else printf '  reaper: \033[2mNOT RUNNING\033[0m'; fi
if pgrep -f queue_targeted60.sh >/dev/null 2>&1; then printf '   queue: \033[1marmed\033[0m\n'; else printf '   queue: \033[2mnot armed\033[0m\n'; fi
[ -f "$SCR/queue_targeted60.status" ] && tail -1 "$SCR/queue_targeted60.status" | sed 's/^/  /'
[ -f "$SCR/reaper.log" ] && tail -1 "$SCR/reaper.log" 2>/dev/null | sed 's/^/  /'

# targeted localisation experiment (v2 only; v1 was invalidated by resource starvation)
printf '\n\033[1m── TARGETED-60 v2 (localisation hypothesis) ──\033[0m '
TRD=$(ls -1dt runs/targeted60v2_*/qwen3_32b 2>/dev/null | head -1)
TLOG="$SCR/targeted60_v2.log"
if [ -z "$TRD" ]; then
  printf '\033[2mnot started — queue is waiting for the box\033[0m\n'
else
  if pgrep -f "tag targeted60v2" >/dev/null 2>&1; then printf 'running\n'; else printf '\033[2mfinished\033[0m\n'; fi
  for ph in baseline__solver_openhands stage4_repo_grounded_work enh_repo_grounded__solver_openhands; do
    w="$TRD/$ph"; [ -d "$TRD/$ph/work" ] && w="$TRD/$ph/work"
    [ -d "$w" ] || continue
    c=$(ls -1 "$w" 2>/dev/null | wc -l)
    lbl=$(echo "$ph" | sed -e 's/__solver_openhands//' -e 's/stage4_//' -e 's/_work//')
    printf '  %-22s %s %2s/60\n' "$lbl" "$(bar "$c" 60)" "$c"
  done
  [ -f "$TLOG" ] && grep -E "^\[baseline\]|truly enhanced|^\[enhanced\]|^DONE " "$TLOG" 2>/dev/null | tail -3 | sed 's/^/  /'
fi
printf '  \033[2mv1 attempt (2026-08-28) invalid: 0/60 both arms, resource starvation\033[0m\n'

# 74-instance recovery
printf '\n\033[1m── RECOVERY (74 lost-artifact instances) ──\033[0m '
if pgrep -f recover_74.py >/dev/null 2>&1; then printf 'running\n'; else printf '\033[2mfinished / not running\033[0m\n'; fi
if [ -f "$SCR/recover74.log" ]; then
  done_n=$(grep -cE "^  \[.*\] [0-9]+/[0-9]+ resolved" "$SCR/recover74.log" 2>/dev/null); done_n=${done_n:-0}
  printf '  conditions scored: %s/12\n' "$done_n"
  grep -E "^  \[.*\] [0-9]+/[0-9]+ resolved" "$SCR/recover74.log" 2>/dev/null | tail -4 | sed 's/^/  /'
fi

printf '\n  containers %s   RAM free %sGB   disk free %s\n' \
  "$(docker ps -q 2>/dev/null | wc -l)" \
  "$(free -g | awk '/Mem:/{print $7}')" \
  "$(df -h / | tail -1 | awk '{print $4}')"
printf '  GPU'; nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader 2>/dev/null \
  | awk -F', ' '{printf " g%s:%s", $1, $2}'; printf '\n\n'
