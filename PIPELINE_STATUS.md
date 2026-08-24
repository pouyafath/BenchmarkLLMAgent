> ⚠️ **SUPERSEDED (as of 2026-06-17).** For the current two-part workflow + every script and
> which node it runs on, see **[WORKFLOW.md](WORKFLOW.md)**. For live status (running
> processes, results, timestamps) see **[PIPELINE_STATE.md](PIPELINE_STATE.md)**. The content
> below is retained as the 2026-06-15 historical snapshot.

# Pipeline Status — Updated 2026-06-15

## Pipeline Overview

| Stage | Name | LLM Used | Purpose |
|-------|------|----------|---------|
| **0** | Collection | None (GitHub API) | Crawl repos, collect task candidates from linked PRs |
| **0.5** | Classification | LLM (issue-type classifier) | Filter P2P>0, classify bug/feature/refactoring, prune infra-incompatible |
| **1** | RepoLaunch Setup | `gpt-oss:120b` (Ollama) | Build Docker images at correct commit via paul-RepoLaunch |
| **2** | RepoLaunch Organize | `gpt-oss:120b` (Ollama) | Extract test info, organize repo structure in containers |
| **3** | Gold Patch Validation | None (test execution) | Apply gold patch, run P2P/F2P tests, record pass counts |
| **4** | Enhancement | `qwen3:32b` (Ollama, :11435) | OpenHands agent rewrites issue description |
| **5** | Solving | `qwen3:32b` (Ollama, :11435) | OpenHands agent produces code patches (baseline + enhanced) |
| **6** | Evaluation | None (test execution) | SWE-bench eval on patches, compare resolution rates |

**Both Stage 4 and Stage 5 use the same model (`qwen3:32b`) and the same dedicated Ollama
endpoint (`:11435`, GPUs 3,4,5,7). The difference is the agent's task: Stage 4 rewrites the
issue text; Stage 5 writes a code patch. Model changed from `gpt-oss:120b` on 2026-06-11
(gpt-oss produced 0% patch rate; qwen3:32b produces ~50% at max_iter=30).**

## Issue Funnel

| Stage | Count | Notes |
|-------|------:|-------|
| **Stage 0** (raw candidates) | 7,714 | Post-cutoff candidate set |
| **Stage 0.5** (classified) | 3,285 | P2P > 0 filter |
| **Stage 0.5** (operational export) | 3,229 | Trimmed for paul-RepoLaunch |
| **Stage 0.5** (infra-compatible) | 2,950 | Removed PostgreSQL, Redis, etc. |
| **Stage 0.5** (viable) | 2,900 | Final viable set for RepoLaunch |
| **Stage 1-2** (Docker images built) | ~1,800+ | Split across two servers |
| **Stage 3** (validated, P2P > 0) | **1,388** | Node1: 510 + Node2: 878, zero overlap |
| **Ready for Stage 4** (Node1, GPU-01) | **383** | 510 − 127 missing Docker images |
| **Ready for Stage 5** (same set) | **383** | All 383 pass through (enhanced or fallback) |
| **Passed Stage 5** (non-empty patch) | **~50%** | Smoke estimate only (10 instances); full run pending |

## Server Split

### GPU-01 (this server) — Node1
- **Dataset**: `data/node1_all494_stage3_merged_20260610.jsonl` — 510 issues
- **Docker images locally**: 383/510 (127 missing — excluded from runs)
- **Stages 1-3**: Complete
- **Stages 4-5**: ✅ Smoke-validated, full 383 run pending

### GPU-02 — Node2
- **Dataset**: `data/node2_stage3_p2p878_20260610.jsonl` — 878 issues
- **Docker images on GPU-01**: 10/878 (868 only on GPU-02)
- **Stages 1-3**: Complete
- **Stages 4-5**: 7 runs completed — **ALL INVALID** (used gpt-oss:120b, 0% patch rate)

## Completed Runs

### smoke-2 (Node1, 10 instances) — 2026-06-15 ✅ COMPLETE
- **Run dir**: `runs/node1_full383_qwen3_20260615_164539/`
- **Config**: qwen3:32b @ :11435, max_iter=30, WORKERS=8, ENH_PARALLEL=4
- **Total time**: 2.03h (7,317s), avg 732s/instance
- **Stage 4**: 8/10 enhanced (80%), 2 fallback
- **Stage 5 Baseline**: 5/10 non-empty patches (50%)
- **Stage 5 Enhanced**: 3/10 non-empty patches (30%)
- **Truly-enhanced only** (8 inst): Baseline 4/8, Enhanced 3/8
- **Fallback only** (2 inst): Baseline 1/2, Enhanced 0/2
- **Peak Docker containers**: 3 | **Min disk free**: 167 GB | **Ollama timeouts**: 0
- **Verdict**: Pipeline fully validated end-to-end. GO for full 383 run.

### pilot-50 (Node1, 50 instances) — 2026-06-14/15 ⚠️ PARTIAL
- **Run dir**: `runs/test50_qwen3_w4_20260614_180126/`
- **Config**: qwen3:32b @ :11434 (shared), max_iter=30, WORKERS=4
- **Stage 4**: 31/50 enhanced (62%), 19 fallback — ✅ saved
- **Stage 5 Baseline**: 7/50 non-empty patches (14%) — ✅ saved (degraded by :11434 timeouts)
- **Stage 5 Enhanced**: ❌ Never ran — killed by ENOSPC (/tmp full)
- **Verdict**: Baseline data saved but degraded (shared Ollama timeouts). Enhanced data lost.

### smoke-1 (Node1, 10 instances) — 2026-06-15 ⚠️ PARTIAL
- **Run dir**: `runs/node1_full383_qwen3_20260615_004636/`
- **Stage 4**: 7/10 enhanced, 3 fallback — ✅ saved
- **Stage 5 Baseline**: 2/10 patches, DONE — ✅ saved
- **Stage 5 Enhanced**: ❌ Never ran — killed by ENOSPC
- **Verdict**: Partial data only.

### Node2 Runs — ALL INVALID (gpt-oss:120b)

All 7 node2 runs used `gpt-oss:120b`, which produces 0% patch rate:

| Run | Enhanced | BL Patches | ENH Patches |
|-----|----------|------------|-------------|
| node2_canary5_baseline | — | 0/5 | — |
| node2_baseline_openhands | — | 0/878 | — |
| node2_baseline_sweagent | — | 0/878 | — |
| node2_openhands_openhands | 8/878 | 0/878 | 0/8 |
| node2_openhands_sweagent | 4/878 | 0/878 | 0/4 |
| node2_sweagent_openhands | 157/878 | 0/878 | 0/157 |
| node2_sweagent_sweagent | 163/878 | 0/878 | 0/163 |

Need rerun with qwen3:32b on GPU-02.

## Infrastructure

- **Private Ollama `:11435`**: qwen3:32b, GPUs 3,4,5,7, KEEP_ALIVE=-1, NUM_PARALLEL=8
  - PID: check with `ss -ltnp | grep 11435`
  - Models dir: `/home/ollama_shared_models`
  - Log: `/tmp/ollama_private_11435.log`
- **Shared Ollama `:11434`**: GPU-0 only — DO NOT USE for Stage 4-5 (18mcs6 gpt-oss evicts qwen3)
- **Disk guard**: `/tmp` and `/` are same fs (`/dev/md0p1`, 1.8TB). Docker build cache can fill it.
  Run `docker builder prune -f` before launches. Preflight now checks both (added 2026-06-15).
- **CLAUDE_CODE_TMPDIR**: set to `/home/22pf2/tmp` in `~/.claude/settings.json` to keep
  Claude Code's harness off the root fs when it fills.

## Solver / LLM Findings (2026-06-15) → see `docs/SOLVER_LLM_FINDINGS_20260615.md`

- **qwen3:32b is a reasoning model, not an agentic/coder model.** It returns reasoning in a
  separate field and frequently emits **empty `content`** turns the solver can't act on.
- **OpenHands 1.4.0 does NOT grant qwen3:32b native function-calling** (only `qwen3-coder*`,
  `deepseek-chat`, Claude/GPT/Gemini/Kimi families qualify). It falls back to prompt-based FC
  that parses text `content` — empty content ⇒ wasted iteration against `max_iter=30`.
- **Disabling thinking** requires the litellm `ollama_chat/` provider + `think:false`; the `/v1`
  (openai) endpoint we use ignores `enable_thinking`.
- **Recommended:** A/B `qwen3:32b` vs **`qwen3-coder:30b`** (native FC, no thinking, same size)
  vs **`devstral`** (built for OpenHands) on the 10 smoke instances before the full 383 run.
  Switching is well-motivated and sunk cost is still low. Relative (baseline-vs-enhanced) results
  remain valid; absolute patch rates are suppressed by the current model fit.

## Known Issues

1. **127 node1 images missing** — 127/510 node1 issues excluded (no local Docker image).
2. **Node2 Docker images not on GPU-01** — 868/878 node2 images only on GPU-02.
3. **Concurrency budget**: Max 8 solver workers, max ~12 Docker containers on :11435.
   (See `CONCURRENCY_BUDGET.md` for details.)
4. **No resume/skip-stage flag** in `run_node1_full383_qwen3.py` — every launch reruns all stages.

## What Needs to Happen

1. ✅ ~~Complete smoke test end-to-end~~ — done 2026-06-15
2. **Run all 383 node1 instances** with qwen3:32b @ :11435 (~3.2 days at 732s/instance)
3. **Run Stage 6 evaluation** on completed solver results (SWE-bench harness)
4. **Rerun node2's 878 instances** with qwen3:32b on GPU-02
5. **Pull missing 127 node1 Docker images** (or formally exclude them)

## Key Commands

```bash
# Status dashboard (live)
cd /home/22pf2/BenchmarkLLMAgent && watch -n 5 python3 scripts/ops/smoke_status.py

# Launch full 383 run (GPU-01, Node1)
cd /home/22pf2/BenchmarkLLMAgent
nohup bench_env/bin/python scripts/workflows/run_node1_full383_qwen3.py > /tmp/node1_full383_full.log 2>&1 &

# Check private Ollama health
ss -ltnp | grep 11435 && curl -s localhost:11435/api/ps

# Free Docker build cache if disk is low
docker builder prune -f && docker container prune -f
```
