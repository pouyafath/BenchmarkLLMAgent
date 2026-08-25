#!/usr/bin/env bash
# Live progress for every active enhancer/solver run.
# Usage:   bash scripts/ops/track_runs.sh
#   live:  watch -n 30 -c bash /home/22pf2/BenchmarkLLMAgent/scripts/ops/track_runs.sh
ROOT=/home/22pf2/BenchmarkLLMAgent
SCRATCH=/home/22pf2/tmp/claude-10136/-home-22pf2-BenchmarkLLMAgent/4e1bec19-55a0-47d5-80ca-555e473168e0/scratchpad
cd "$ROOT" || exit 1

printf '\n\033[1m== ACTIVE RUNS ==\033[0m  %s\n\n' "$(date '+%H:%M:%S')"

mapfile -t PROCS < <(ps -eo pid,etime,cmd --no-headers 2>/dev/null \
  | grep -E '[r]un_repo_grounded_cell|[r]un_ollama_cell|[r]un_openai_cell')

if [ ${#PROCS[@]} -eq 0 ]; then
  echo "  (no solver/enhancer process running)"
else
  printf '  %-10s %-22s %-10s %s\n' PID MODEL ELAPSED RUNDIR
  for p in "${PROCS[@]}"; do
    pid=$(awk '{print $1}' <<<"$p")
    el=$(awk '{print $2}' <<<"$p")
    model=$(grep -oP '(?<=--model )\S+' <<<"$p")
    tag=$(grep -oP '(?<=--tag )\S+' <<<"$p")
    rd=$(ls -1dt runs/"${tag}"_*/*/ 2>/dev/null | head -1)
    printf '  %-10s %-22s %-10s %s\n' "$pid" "${model:-?}" "$el" "${rd:-?}"
  done
fi

# Per-phase counts. "done" = the instance's agent log reached a terminal state.
count_done() {  # $1 = work dir
  local d="$1" done=0 tot=0 f
  [ -d "$d" ] || { echo "0 0"; return; }
  for f in "$d"/*/; do
    [ -d "$f" ] || continue
    tot=$((tot+1))
    if grep -qaE 'to AgentState\.(FINISHED|ERROR)|reached maximum iteration' \
         "$f/openhands.log" "$f/agent.log" 2>/dev/null; then
      done=$((done+1))
    fi
  done
  echo "$done $tot"
}

bar() {  # $1 done  $2 total  -> [####------]
  local d=$1 t=$2 w=20 filled
  [ "$t" -gt 0 ] 2>/dev/null || { printf '[%*s]' $w ''; return; }
  filled=$(( d * w / t ))
  printf '['; printf '#%.0s' $(seq 1 $filled 2>/dev/null); \
  printf -- '-%.0s' $(seq 1 $((w-filled)) 2>/dev/null); printf ']'
}

for rd in $(ls -1dt runs/rge*_*/*/ runs/ollama_*/*/ 2>/dev/null | head -6); do
  [ -d "$rd" ] || continue
  # only show runs touched in the last 3 hours
  [ -n "$(find "$rd" -maxdepth 1 -newermt '-3 hours' -print -quit 2>/dev/null)" ] || continue
  # expected instance count, from the runner's own banner ("... n=20 ...")
  tagdir=$(basename "$(dirname "${rd%/}")")
  n_exp=$(grep -hoP '(?<= n=)\d+' "$SCRATCH"/*.log 2>/dev/null | head -1)
  for lg in "$SCRATCH"/*.log; do
    [ -f "$lg" ] || continue
    grep -q "$tagdir" "$lg" 2>/dev/null && n_exp=$(grep -oP '(?<= n=)\d+' "$lg" | head -1) && break
  done
  printf '\n\033[1m%s\033[0m  (expected %s instances)\n' "$rd" "${n_exp:-?}"
  for phase in baseline__solver_openhands stage4_repo_grounded_work \
               enh_repo_grounded__solver_openhands enh_aider__solver_openhands; do
    w="$rd/$phase"
    [ -d "$w" ] || w="$rd/$phase/work"
    [ -d "$w" ] || continue
    [ -d "$rd/$phase/work" ] && w="$rd/$phase/work"
    read -r d t < <(count_done "$w")
    tgt=${n_exp:-$t}
    label=$(sed -e 's/__solver_openhands//' -e 's/stage4_//' -e 's/_work//' <<<"$phase")
    printf '  %-26s %s %3s/%-3s done, %3s left  (started %s)\n' \
      "$label" "$(bar "$d" "$tgt")" "$d" "$tgt" "$(( tgt - d ))" "$t"
  done
done

# ---- ETA, from observed per-instance rates in each run's own log ----
printf '\n\033[1m== ETA ==\033[0m\n'
python3 - "$SCRATCH" <<'PYEOF'
import re, sys, datetime, pathlib
S = pathlib.Path(sys.argv[1])
TS = re.compile(r'\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) UTC\].*\[enh:repo_grounded\]')
PHASE_ENH  = "=== ENHANCE"
PHASE_SOLV = "=== ENHANCED SOLVE"
now = datetime.datetime.utcnow()
for f in sorted(S.glob("rge20_*.log")):
    txt = f.read_text(errors="replace")
    if "DONE model=" in txt:
        print(f"  {f.stem:<16} COMPLETE"); continue
    m = re.search(r'\[baseline\] non-empty \d+/(\d+)\s+\(([\d.]+) min\)', txt)
    n_tot   = int(m.group(1)) if m else 20
    base_min= float(m.group(2)) if m else 60.0
    ts = [datetime.datetime.strptime(x, "%Y-%m-%d %H:%M:%S") for x in TS.findall(txt)]
    if PHASE_SOLV in txt:
        print(f"  {f.stem:<16} enhanced-solve running  ~{base_min:.0f} min for the phase")
    elif PHASE_ENH in txt and len(ts) >= 2:
        rate = (ts[-1]-ts[0]).total_seconds()/60/max(len(ts)-1, 1)
        left = n_tot - len(ts)
        rem  = left*rate + base_min
        eta  = (now + datetime.timedelta(minutes=rem)).strftime('%H:%M')
        print(f"  {f.stem:<16} enhance {len(ts)}/{n_tot} ({rate:.1f} min/inst) "
              f"+ solve ~{base_min:.0f}m  ->  ~{rem:.0f} min left, done ~{eta} UTC")
    elif not m:
        print(f"  {f.stem:<16} baseline running")
    else:
        print(f"  {f.stem:<16} enhance starting")
PYEOF

printf '\n  containers: %s   RAM free: %sGB   disk free: %s\n\n' \
  "$(docker ps -q 2>/dev/null | wc -l)" \
  "$(free -g | awk '/Mem:/{print $7}')" \
  "$(df -h / | tail -1 | awk '{print $4}')"
