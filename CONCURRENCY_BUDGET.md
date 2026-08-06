# Concurrency Budget — MUST READ BEFORE RUNNING PIPELINES

**Date**: 2026-06-11
**Reason**: GPU-02 OOM crash and server freeze from uncontrolled parallel OpenHands workers.
Admin (Tufail Malik) had to reboot GPU-02 and kill 1200+ zombie sessions on GPU-01.

## Hard Limits (Shared Server — 1.5TB RAM, Multi-Core CPU)

| Resource                          | Limit                          |
|-----------------------------------|--------------------------------|
| tmux sessions                     | max 2 active at once           |
| Paul setup workers                | max 2 (as before, this was fine) |
| BenchmarkLLMAgent solver workers  | max 2 (was unlimited — this caused the OOM) |
| Docker containers                 | max 4 concurrent               |
| Ollama                            | 1 instance, already fine       |

## What Happened

The 510-instance pilot run (`node1_2agent_pilot_openhands_20260611`) with 4 parallel solver
workers spawned cascading Docker containers and OpenHands child processes. Each solver
invocation creates:
- 1 Docker sandbox container
- Multiple child processes inside the container
- OpenHands session state directories (~150KB each)

With 4 workers × 510 instances × 2 conditions (baseline + enhanced), this created 2000+
sequential OpenHands invocations that accumulated:
- 3,581 session directories (531MB)
- 52 Docker containers
- 116 run directories (6GB)

The server ran out of memory and froze.

## Rules for Pipeline Scripts

1. **WORKERS ≤ 4** in solver scripts (tested safe at 4 with 114/1510GB RAM).
2. **Check before launching**: `tmux ls | wc -l`, `docker ps | wc -l`, `df -h /`
3. **Clean up after runs**: `docker container prune -f`, `docker builder prune -f`, remove old session dirs
4. **Never run two solver scripts simultaneously** — they compete for GPU and Docker resources.
5. **For large runs (>50 instances)**: run in batches, monitor resource usage between batches.
6. **Monitor root partition**: `df -h /` — if below 50GB free, run `docker builder prune --all -f`

## Dedicated Private Ollama + WORKERS=8 (2026-06-14)

To remove GPU contention from user `18mcs6`'s mini-swe-agent jobs (which share the
system Ollama on `:11434` / GPU-0 and caused repeated "Model health-check timed out"
in the solver), we run a **dedicated private Ollama** for the full node1 run:

```
OLLAMA_HOST=127.0.0.1:11435 \
OLLAMA_MODELS=/home/ollama_shared_models \
CUDA_VISIBLE_DEVICES=3,4,5,7 \
OLLAMA_SCHED_SPREAD=1 OLLAMA_NUM_PARALLEL=8 \
OLLAMA_KEEP_ALIVE=-1 OLLAMA_MAX_LOADED_MODELS=1 \
nohup /usr/local/bin/ollama serve > /tmp/ollama_private_11435.log 2>&1 &
```

- qwen3:32b spreads across the 4 idle GPUs (3,4,5,7), ~26GB each (~101GB total incl.
  KV cache for 8 parallel × 40k ctx). Does NOT touch GPU-0 (system Ollama) or the
  busy GPUs 1,2,6.
- The full-run script `run_node1_full383_qwen3.py` points at `:11435` exclusively.

**WORKERS raised 4 → 8** for this run. This exceeds the old "max 4 Docker containers"
limit, sanctioned because:
- The GPU side now matches (NUM_PARALLEL=8 on a dedicated 4-GPU endpoint).
- RAM is the real OOM constraint, and it is not close: 8 OpenHands containers ≈ 16GB
  of ~1.3TB free. Earlier OOM was from *unlimited* workers + accumulated zombies, not 8.
- Guardrails kept: preflight aborts if `/` has <50GB free; resource log now records
  `disk_free_gb`; still prune zombies/exited containers between/after runs.

**GPU caveat:** GPUs 3,4,5,7 are idle *now* but other users' jobs (e.g. 25fxvd vLLM)
shuffle across GPUs. If one reclaims 3/4/5/7, the private daemon's model may get
evicted — re-check `nvidia-smi` and `curl :11435/api/ps` before/at the start of the run.

## Disk Space Incident (2026-06-12 to 2026-06-14)

Root partition (`/dev/md0p1`, 1.8TB) hit 100% full. Docker build cache accumulated 349GB,
Docker images used 1.6TB. Two solver runs crashed silently (ENOSPC — containers couldn't start).

Fixed by: `docker builder prune --all -f` (freed ~240GB). The SWE-bench Docker images
(`pouya/stage2_2026:*`) were NOT affected — only intermediate build cache was removed.
