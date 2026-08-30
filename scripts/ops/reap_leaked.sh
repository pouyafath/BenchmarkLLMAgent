#!/usr/bin/env bash
# Continuously reap leaked OpenHands runtime containers.
#
# OpenHands starts a runtime container per instance and does not always remove it. Over a
# long run these accumulate without bound: an unattended session reached 209 containers
# against a documented budget of 4, starved every job on the box, and produced 115 solver
# timeouts and zero usable patches.
#
# Safety rule: a legitimate solver container cannot outlive SOLVE_TIMEOUT (1800s). Anything
# older than MAX_AGE_MIN (default 60, i.e. 2x the cap) is therefore certainly abandoned.
# Nothing younger is ever touched, so this is safe to run beside live jobs.
#
#   nohup bash scripts/ops/reap_leaked.sh &
MAX_AGE_MIN=${MAX_AGE_MIN:-60}
INTERVAL=${INTERVAL:-300}
# Bounded lifetime so the reaper cannot outlive the work it protects.
MAX_HOURS=${MAX_HOURS:-14}
DEADLINE=$(( $(date +%s) + MAX_HOURS*3600 ))

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  now=$(date +%s)
  killed=0
  for id in $(docker ps --filter "name=openhands-runtime-" --format '{{.ID}}' 2>/dev/null); do
    started=$(docker inspect -f '{{.State.StartedAt}}' "$id" 2>/dev/null) || continue
    ts=$(date -d "$started" +%s 2>/dev/null) || continue
    age=$(( (now - ts) / 60 ))
    if [ "$age" -ge "$MAX_AGE_MIN" ]; then
      docker rm -f "$id" >/dev/null 2>&1 && killed=$((killed+1))
    fi
  done
  [ "$killed" -gt 0 ] && \
    echo "[$(date '+%F %T')] reaped $killed container(s) older than ${MAX_AGE_MIN}m; $(docker ps -q | wc -l) remain"
  sleep "$INTERVAL"
done
echo "[$(date '+%F %T')] reaper exiting after ${MAX_HOURS}h"
