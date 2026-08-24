# BenchmarkLLMAgent — Pinned Project Brief

**Pin this in your contributors group so everyone (including AI agents) knows the project, how to scale it, and what to update after changes.**

---

## What is this project?

**BenchmarkLLMAgent** benchmarks LLM-based agents for **GitHub issue enhancement**. It's Paper 3 of a research trilogy (Paper 1: TSE, Paper 2: ASE 2026, Paper 3: TSE target).

**Research questions:**
- **RQ1:** How do ready-to-use agents (OpenHands, SWE-Agent, Copilot, Sweep, etc.) compare at enhancing issues?
- **RQ2:** How do framework-built agents (LangGraph, AutoGen, CrewAI, etc.) compare under controlled conditions?
- **RQ3:** Does enhancement improve solver performance? (We measure solving *before* vs *after* enhancement)
- **RQ4:** How do results vary by issue type, quality, and complexity?

**Two agent categories:** Category A (ready-to-use) and Category B (framework-built). Solvers from our pilot study are reused as the evaluation mechanism.

---

## Iterative roadmap

| Iteration | Dataset | Purpose | Status |
|-----------|---------|---------|--------|
| **1** | Verified 10 | Baseline-vs-enhanced validation | Done |
| **2** | 3 Groups x 10 issues | 3-agent x 3-group experiment (A=Verified, B=Community, C=SWE-bench-Live) | Done |
| **3** | SWE-bench-Live 50 issues | Scale-up with 131k context window | Done |
| **4** | Pouya-20 (gpt-5.4-mini) | 5 native CLI agents, full solver comparison | **Done** |

**Current:** Iteration 4 complete. Pilot-40 all 3 accepted runs complete. Batch2 (55-row) Stage 4 is complete, Stage 5/6 snapshot exists on a 29-row runnable subset, final upstream manifest is now 30 runnable, and a small 29->30 expansion decision remains.

RepoLaunch (Stage 1/2/3 pipeline) live operational handoff is tracked at:
`/home/22pf2/paul-RepoLaunch/docs/PROJECT_STATUS_HANDOFF_2026-05-26.md`

Current pilot continuation input for Stage 4-6:
`/home/22pf2/paul-RepoLaunch/runs/stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/stage3_validation_completed40.jsonl`

---

## Latest Results

### Pilot-40 Accepted Benchmark Results — 40 issues, P2P-gated re-eval applied

| Enhancer | LLM / Solver | Baseline → Enhanced | Delta | Status |
|----------|:---:|:---:|:---:|:---:|
| **OpenHands** | gpt-5.4-mini | **9/40 → 10/40** | **+1** | Accepted |
| **llm_append_analysis** | gpt-5.4-mini | **9/40 → 8/40** | **-1** | Accepted |
| **llm_append_analysis** | gpt-oss:120b | **0/40 → 0/40** | **0** | Accepted |
| **OpenClaw** | — | — | — | Not integrated (no local runtime on docjk-gpu-01) |

All accepted comparisons use the shared P2P-gated re-eval workflow (`scripts/workflows/pilot40_reeval_lib.py`).

#### OpenHands detail (2026-06-01)
- Enhancement coverage: 39/40 truly enhanced (1 OpenHands CLI error: `Azure__azure-cli-32339`)
- Gained: `Diaoul__subliminal-1328` (bug); Lost: none
- Caveat: `Azure__azure-cli-32339` is treated as a likely runtime outlier; exact root cause not fully proven
- Report: `runs/paul_pilot40_openhands_20260601/stage6_report/REPORT.md`

#### llm_append_analysis + gpt-5.4-mini detail (2026-05-26)
- Report: `runs/paul_pilot40_stage4_stage6_20260526/stage6_report/REPORT.md`

#### llm_append_analysis + gpt-oss:120b detail (2026-05-27)
- Report: `runs/paul_pilot40_gptoss_solver_20260527/stage6_report/REPORT.md`

### Batch2 (55-row) Current Status (2026-06-05)
- Stage 4 full 55-row run complete: **54/55 truly enhanced** (1 failure: `HKUDS__nanobot-3578`, same class as pilot40 outlier)
- Final upstream manifest now fixed; `runnable_ids.json` currently shows:
  - `confirmed_runnable`: 30
  - `timeout_unrestored`: 9
  - `launch_failed_unrestored`: 13
  - `bad_target`: 3
  - `still_pending`: 0
- Stage 5/6 snapshot already completed on the earlier 29-row runnable snapshot:
  - baseline: `19 / 29`
  - enhanced: `21 / 29`
  - not_evaluated in that snapshot: `26`
- Remaining downstream decision:
  - whether to execute a minimal 29 -> 30 evaluation expansion so the batch2
    Stage 6 artifacts fully match the final manifest

### 20-Issue Native CLI Agent Comparison (2026-05-10) — 5 Agents, gpt-5.4-mini

LLM: **gpt-5.4-mini** (OpenAI API). Solver: **mini-SWE-agent**. Dataset: **Pouya-20** (20 curated issues from SWE-bench).

| Condition | Enh. Failures | Resolved / 20 | Delta vs Baseline | Resolved IDs |
|-----------|:---:|:---:|:---:|---|
| **Baseline** (no enhancement) | 0 | **3/20 (15%)** | -- | a2a-683, faststream-2495, astropy-18753 |
| **aider** | 0 | **3/20 (15%)** | 0 | a2a-683, faststream-2495, astropy-18753 |
| **trae** | 0 | **2/20 (10%)** | -1 | a2a-683, faststream-2495 |
| **openhands** | 0 | **2/20 (10%)** | -1 | faststream-2495, astropy-18753 |
| **mini_swe_agent** | 3 | **2/20 (10%)** | -1 | faststream-2495, astropy-18753 |
| **swe_agent** | 1 | **1/20 (5%)** | -2 | a2a-683 |

Key findings:
- Enhancement does **not** improve solver success rate -- enhancers match or slightly underperform baseline
- All 5 enhancers are **native CLI agents** (subprocess-based, no LLM proxy or fallback)
- The same 3 baseline-solvable issues dominate; no enhancer unlocks new resolutions
- `dlt-hub` issues produce empty solver patches due to missing Docker images (infrastructure, not agent quality)

Report: `runs/pouya20_native_solver_comparison_fixed/ANALYSIS.md`

### Previous Results (Iterations 1-3)

| Experiment | Dataset | Key Finding |
|-----------|---------|-------------|
| 3x3 (2026-03-31) | 3x10 issues | Enhancement effect depends on agent choice AND curation level |
| 50-issue (2026-04-03) | SWE-bench-Live 50 | Enhancement never beneficial; aggressiveness correlates with harm |
| 101-issue (2026-03-30) | 2x101 issues | Aider shows catastrophic -35 to -46pp degradation |

---

## How to scale the project

| Action | Where to add |
|--------|--------------|
| New enhancement agent (Category A or B) | `src/enhancers/ready_to_use/` or `src/enhancers/framework_built/` |
| New solver framework | `src/solvers/<framework>/` + register in `scripts/solvers/run_full_benchmark.py` |
| More benchmark issues | `data/samples/` + update `configs/benchmark_config.yaml` |
| New metrics or evaluation logic | `src/evaluation/` |
| New scripts (data, runs, reports) | `scripts/data/`, `scripts/solvers/`, `scripts/enhancers/`, or `scripts/reports/` |

---

## After each modification — update these files

| What you changed | Files to update |
|------------------|-----------------|
| New agent or framework | `README.md`, `ROADMAP.md` (current state), `CONTRIBUTING.md` (if conventions change) |
| New script | `README.md` (Quick Start), `ROADMAP.md` (steps), `CONTRIBUTING.md` (if workflow changes) |
| Config keys / paths | `configs/benchmark_config.yaml`, any script that reads config |
| Data schema (samples, selected IDs, evaluation outputs) | `docs/README.md`, `docs/MAIN.md`, and affected guide/analysis docs |
| Research direction / methodology | `ROADMAP.md` + relevant files in `docs/guides/` and `docs/analysis/` |
| Completed run milestone | `ROADMAP.md`, `README.md`, `CHANGELOG.md`, and `docs/analysis/*` |
| Bug findings and debugging notes | `docs/analysis/VERIFIED10_WORKFLOW_BUG_AUDIT_2026-03-18.md` |
| Dependencies | `requirements.txt` |
| New directory or module | `README.md` (project structure), `CONTRIBUTING.md` (structure section) |

**Golden rule:** If you add, rename, or remove something, update the canonical docs first (`README.md`, `ROADMAP.md`, `CONTRIBUTING.md`, `docs/README.md`, `docs/MAIN.md`).

---

## One-line summary for quick reference

> **BenchmarkLLMAgent:** Benchmarks LLM agents for GitHub issue enhancement. Pilot-40 accepted: OpenHands 9→10/40 (+1); llm_append+gpt-5.4-mini 9→8/40 (-1); llm_append+gpt-oss 0→0/40; OpenClaw not integrated. Batch2 Stage 4 complete (54/55), Stage 5/6 snapshot exists at 19/29 -> 21/29, and the final runnable manifest is now 30. Report: `runs/paul_pilot40_openhands_20260601/stage6_report/REPORT.md`.
