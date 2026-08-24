#!/usr/bin/env bash
# Reset SWE-agent solver runs and relaunch with top_p: null fix applied.
# Usage: bash /home/22pf2/BenchmarkLLMAgent/reset_and_relaunch_swea.sh

set -e

ROOT=/home/22pf2/BenchmarkLLMAgent
TS=20260505_150000
PY="$ROOT/bench_env/bin/python"
SCRIPT="$ROOT/scripts/workflows/run_pouya20_gpt54mini.py"
APIKEY="${OPENAI_API_KEY:-$(cat "$ROOT/.secrets/openai_api_key.txt")}"

echo "=== Step 0: Free disk space (remove dangling Docker images + build cache) ==="
df -h / | tail -1
docker image prune -f
docker container prune -f
docker builder prune -f
echo "Disk after prune:"
df -h / | tail -1

echo ""
echo "=== Step 1: Kill any lingering processes ==="
pkill -f "evaluation.py.*pouya_swea_solver" 2>/dev/null && echo "  killed evaluation.py" || echo "  no evaluation.py found"
pkill -f "run_pouya20_gpt54mini.py.*pouya_swea_solver" 2>/dev/null && echo "  killed run_pouya20" || echo "  no run_pouya20 found"
sleep 2

echo ""
echo "=== Step 2: Delete stale solver output dirs ==="
for NAME in baseline llm_append_analysis aider trae openhands mini_swe_agent swe_agent; do
  D="$ROOT/runs/pouya_swea_solver_${NAME}_${TS}"
  for SUB in solver_baseline solver_baseline_eval solver_enhanced solver_enhanced_eval summary.json; do
    P="$D/$SUB"
    if [ -d "$P" ]; then rm -rf "$P" && echo "  deleted dir : $NAME/$SUB"; fi
    if [ -f "$P" ]; then rm -f "$P" && echo "  deleted file: $NAME/$SUB"; fi
  done
done

echo ""
echo "=== Step 3: Reset progress.json files to gold_eval_done ==="
python3 - << 'PYEOF'
import json
from pathlib import Path
ROOT = Path("/home/22pf2/BenchmarkLLMAgent/runs")
TS = "20260505_150000"
NAMES = ["baseline", "llm_append_analysis", "aider", "trae", "openhands", "mini_swe_agent", "swe_agent"]
for name in NAMES:
    p = ROOT / f"pouya_swea_solver_{name}_{TS}" / "progress.json"
    prog = json.loads(p.read_text()) if p.exists() else {}
    prog["stage"] = "gold_eval_done"
    prog["done_steps"] = ["repolaunch", "gold_eval", "gold_eval_done"]
    prog.pop("baseline_resolved", None)
    prog.pop("enhanced_resolved", None)
    p.write_text(json.dumps(prog, indent=2))
    print(f"  reset: {name} → stage=gold_eval_done")
PYEOF

echo ""
echo "=== Step 4: Launch baseline (SWE-agent solver) ==="
nohup env OPENAI_API_KEY="$APIKEY" \
  SWEA_SOLVER_MODEL="gpt-5.4-mini" \
  SWEA_SOLVER_BASE_URL="https://api.openai.com/v1" \
  SWEA_SOLVER_MAX_STEPS="30" \
  "$PY" "$SCRIPT" \
  --run-dir "$ROOT/runs/pouya_swea_solver_baseline_$TS" \
  --limit 20 --skip-repolaunch --skip-gold-eval --skip-enhanced \
  --solver swe_agent \
  > "$ROOT/runs/pouya_swea_solver_baseline_$TS/launch.log" 2>&1 &
echo "  baseline PID: $!"

echo ""
echo "=== Step 5: Launch 6 enhanced runs (SWE-agent solver) ==="
for ENHANCER in llm_append_analysis aider trae openhands mini_swe_agent swe_agent; do
  RUN_DIR="$ROOT/runs/pouya_swea_solver_${ENHANCER}_${TS}"
  nohup env OPENAI_API_KEY="$APIKEY" \
    SWEA_SOLVER_MODEL="gpt-5.4-mini" \
    SWEA_SOLVER_BASE_URL="https://api.openai.com/v1" \
    SWEA_SOLVER_MAX_STEPS="30" \
    "$PY" "$SCRIPT" \
    --run-dir "$RUN_DIR" \
    --limit 20 --skip-repolaunch --skip-gold-eval --skip-baseline \
    --enhancer "$ENHANCER" --solver swe_agent \
    --load-enhanced-from "$RUN_DIR/solver_enhanced_dataset.jsonl" \
    > "$RUN_DIR/launch.log" 2>&1 &
  echo "  $ENHANCER PID: $!"
done

echo ""
echo "=== All 7 runs launched ==="
echo ""
echo "Monitor with:"
echo "  watch -n 30 'for N in baseline llm_append_analysis aider trae openhands mini_swe_agent swe_agent; do echo -n \"\$N: \"; tail -1 $ROOT/runs/pouya_swea_solver_\${N}_${TS}/launch.log 2>/dev/null || echo \"(no log)\"; done'"
