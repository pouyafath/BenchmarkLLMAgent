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

## Iterative roadmap (10 → 200 issues)

| Iteration | Dataset | Purpose |
|-----------|---------|---------|
| **1** | 10 issues | Full workflow end-to-end, validate pipeline |
| **2** | 200 issues | Full-scale benchmark for paper |

**Next step:** Implement enhancement agents, run on 10 issues, then scale. See **`ROADMAP.md`** for handoff instructions.

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
| Data schema (samples, ground truth) | `docs/research_plan.md` (dataset section), any script that consumes it |
| Research direction / methodology | `docs/research_plan.md` |
| Completed Iteration 1 or 2 | `ROADMAP.md` (current state), `README.md` (status) |
| Pilot study results / analysis | `docs/pilot_study_report.md` |
| Dependencies | `requirements.txt` |
| New directory or module | `README.md` (project structure), `CONTRIBUTING.md` (structure section) |

**Golden rule:** If you add, rename, or remove something, update the docs. Prefer `README.md`, `ROADMAP.md`, `CONTRIBUTING.md`, or `docs/research_plan.md` depending on scope.

---

## One-line summary for quick reference

> **BenchmarkLLMAgent:** Benchmarks LLM agents for GitHub issue enhancement. Iteration 1 = 10 issues, Iteration 2 = 200. Read `ROADMAP.md` for handoff. After changes, update `README`, `ROADMAP`, and/or `docs/research_plan.md`.
