#!/usr/bin/env bash
# Live tracker for the second GPT-5-mini baseline draw (279 issues, OpenAI spend).
ROOT=/home/22pf2/BenchmarkLLMAgent
SCR=/home/22pf2/tmp/claude-10136/-home-22pf2-BenchmarkLLMAgent/4e1bec19-55a0-47d5-80ca-555e473168e0/scratchpad
running(){ ps -eo cmd --no-headers | grep -qE "^[^ ]*python[^ ]*[ ].*run_openai_cell\.py"; }
while true; do
  clear
  R=$(ls -dt "$ROOT"/runs/gpt5mini_baseline2_279_*/gpt-5-mini 2>/dev/null | head -1)
  W="$R/baseline__solver_openhands/work"
  done_n=$(ls -1d "$W"/*/ 2>/dev/null | wc -l)
  echo "===== $(date '+%F %H:%M:%S') ====================================="
  running && echo "  status: RUNNING" || echo "  status: finished or stopped"
  echo "  instances started : $done_n / 279"
  # a finished instance leaves a patch file behind
  p=$(find "$W" -name 'oh_solution.patch' 2>/dev/null | wc -l)
  echo "  patches written   : $p"
  echo "  containers        : $(docker ps -q | wc -l)"
  echo
  echo "  --- cost so far, from the measured call rate ---"
  calls=$(grep -rc 'return self\.__pydantic_serializer__\.to_python(' "$W"/*/openhands.log 2>/dev/null \
          | awk -F: '{s+=$2} END{print s+0}')
  echo "  LLM calls         : $calls   (August run: 5,871 for all 279)"
  awk -v c="$calls" 'BEGIN{printf "  est. spend        : $%.2f - $%.2f\n", c*0.00216, c*0.00539}'
  echo
  tail -4 "$SCR/gpt5mini_b2.log" 2>/dev/null | sed 's/^/  /'
  sleep 30
done
