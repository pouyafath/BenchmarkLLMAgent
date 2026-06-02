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

**Current:** Iteration 4 complete. See `runs/pouya20_native_solver_comparison_fixed/ANALYSIS.md`.

---

## Latest Results

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

> **BenchmarkLLMAgent:** Benchmarks LLM agents for GitHub issue enhancement. Current experiment: 5 native CLI agents (aider, trae, openhands, mini-SWE-agent, SWE-agent) on 20 issues with gpt-5.4-mini. Results: `runs/pouya20_native_solver_comparison_fixed/ANALYSIS.md`.
