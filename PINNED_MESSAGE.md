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
| **3** | SWE-bench-Live 50 issues | Scale-up with 131k context window | **Done** |

**Current:** All iterations complete. See `docs/groupC_50_issue_experiment_report.md`.

---

## Latest Results

### 3x3 Experiment (2026-03-31) — 3 Agents x 3 Groups, 10 Issues Each

| Agent | Group A (Verified) | Group B (Community) | Group C (SWE-bench-Live) |
|-------|:---:|:---:|:---:|
| **TRAE** | 0% | **+30%** | 0% |
| **SWE-agent** | +10% | +10% | -10% |
| **Aider** | -30% | -10% | -10% |

Key finding: Enhancement effect depends on **both agent choice AND curation level** (2D interaction). TRAE is the only universally safe enhancer. Report: `docs/groupA_vs_groupB_vs_groupC_experiment_report.md`

### 50-Issue Scale-Up (2026-04-03) — SWE-bench-Live, 131k Context Window

| Agent | Baseline | Enhanced | Delta Resolved | Delta F2P | Status |
|-------|:--------:|:--------:|:--------------:|:---------:|--------|
| **TRAE** | 1/50 (2.0%) | 1/50 (2.0%) | 0.0% | +2.0% | Complete |
| **SWE-agent** | 1/50 (2.0%) | 0/50 (0.0%) | -2.0% | +2.0% | Complete |
| **Aider** | 1/50 (2.0%) | 0/50 (0.0%) | -2.0% | -14.0% | Complete |

Key finding: Context window fix (65k→131k) eliminated overflow errors but enhancement is **still never beneficial** on SWE-bench-Live. Aggressiveness of rewriting correlates with harm. Report: `docs/groupC_50_issue_experiment_report.md`

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

> **BenchmarkLLMAgent:** Benchmarks LLM agents for GitHub issue enhancement. Canonical 10-issue workflow now uses SWE-bench Verified IDs aligned with `/home/22pf2/SWE-Bench_Replication` baseline; run `scripts/workflows/run_verified10_enhancement_vs_baseline.py` for before/after comparison.
