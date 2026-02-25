# BenchmarkLLMAgent — Roadmap & Handoff Guide

**For contributors and AI agents continuing this work.**

---

## Iterative Execution Strategy

We run the full workflow on a **small dataset first (10 issues)**, validate end-to-end, then scale to **200 issues** in the next iteration.

| Iteration | Dataset Size | Purpose |
|-----------|--------------|---------|
| **Iteration 1** | 10 issues | Validate pipeline end-to-end, fix bugs, tune configs |
| **Iteration 2** | 200 issues | Full-scale benchmark for paper results |

---

## Current State (as of handoff)

| Component | Status |
|-----------|--------|
| **Pilot solver benchmark** | ✅ Done — 10 issues × 6 frameworks, 4 working (OpenAI SDK, CrewAI, AutoGen, LangGraph) |
| **10-issue dataset** | ✅ Ready — `data/samples/pilot_10_samples.json` + `data/ground_truth/` |
| **Enhancement agents** | ⏳ Not started — `src/enhancers/` has placeholders only |
| **Enhancement scripts** | ⏳ Not started — `scripts/enhancers/` is empty |
| **Solver-after-enhancement runs** | ⏳ Not started — `results/solving_after_enhancement/` is empty |

---

## Iteration 1: Full Workflow on 10 Issues

**Goal:** Run enhancement + solving pipeline end-to-end on 10 issues. Validate that everything works before scaling.

### Steps (in order)

1. **Implement enhancement agents**
   - Category A: Add 1–3 ready-to-use agents (e.g., start with Aider, Sweep, or Cline — easiest to integrate)
   - Category B: Add 1–2 framework-built enhancers (e.g., LangGraph, CrewAI) — reuse solver frameworks
   - Create `scripts/enhancers/run_enhancement_benchmark.py` with `--max-issues 10`

2. **Run enhancement benchmark**
   - For each of 10 issues: run each enhancement agent → save to `results/enhancement_benchmark/`
   - Output: `{agent}__{owner}__{repo}__{issue}.json` with `enhanced_title`, `enhanced_body`, metadata

3. **Run solver benchmark (before vs after)**
   - Baseline: solver on original issue (can reuse `results/pilot_solver_benchmark/` for 4 working frameworks)
   - After: solver on each enhanced issue → save to `results/solving_after_enhancement/`
   - Compute deltas: patch quality (enhanced) − patch quality (original)

4. **Generate reports**
   - Add `scripts/reports/generate_enhancement_report.py` to summarize enhancement quality + downstream impact
   - Verify metrics make sense

5. **Document and fix**
   - Fix any bugs, tune prompts, update configs
   - Update `docs/research_plan.md` with any methodology changes
   - Update `README.md` with new scripts and current status

---

## Iteration 2: Scale to 200 Issues

**Prerequisite:** Iteration 1 complete and validated.

### Steps

1. **Select 200 issues**
   - Extend `scripts/data/select_samples.py` or add `scripts/data/select_200_samples.py`
   - Apply Phase 1 criteria: mix of quality/complexity, linked merged PRs, language diversity
   - Save to `data/samples/primary_200_samples.json`

2. **Prepare ground truth**
   - Fetch PR patches for all 200 issues → `data/ground_truth/`
   - Update `configs/benchmark_config.yaml` dataset paths

3. **Run full benchmark**
   - Same scripts as Iteration 1, but with `--max-issues 200` or `--samples primary_200_samples.json`
   - Enhancement runs: 16 agents × 200 issues = 3,200
   - Solving runs: 4 solvers × (1 + 16) × 200 = 13,600

4. **Evaluation & analysis**
   - Run statistical tests (Wilcoxon, Cliff's delta) per `src/evaluation/statistical_analysis.py`
   - Stratified analysis by issue type, complexity
   - Update `docs/pilot_study_report.md` or create `docs/enhancement_benchmark_report.md`

---

## Config / Script Conventions

- Use `--max-issues N` or `--samples <path>` in all benchmark scripts so the same code runs for 10 or 200 issues.
- Dataset paths:
  - Iteration 1: `data/samples/pilot_10_samples.json`
  - Iteration 2: `data/samples/primary_200_samples.json`
- Results:
  - Iteration 1: same dirs (`results/enhancement_benchmark/`, `results/solving_after_enhancement/`) — filenames include issue ID
  - Iteration 2: add subdirs if needed, e.g. `results/enhancement_benchmark/iteration2/`

---

## Files to Update After Changes

| What you did | Update |
|--------------|--------|
| Implemented enhancement agent | `README.md`, `CONTRIBUTING.md`, `ROADMAP.md` (current state) |
| Added enhancement/solving scripts | `README.md` Quick Start, `ROADMAP.md` steps |
| Changed dataset or config | `configs/benchmark_config.yaml`, `ROADMAP.md`, `docs/research_plan.md` |
| Finished Iteration 1 | `ROADMAP.md` current state, `README.md` status |
| Finished Iteration 2 | `docs/enhancement_benchmark_report.md`, paper drafts |

---

## One-Line Handoff Summary

> **Next agent:** Implement 1–3 enhancement agents, run the full enhancement + solving workflow on 10 issues (`data/samples/pilot_10_samples.json`), validate end-to-end, then scale to 200. See `ROADMAP.md` for step-by-step instructions.
