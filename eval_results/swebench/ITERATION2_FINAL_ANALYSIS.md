# Iteration 2 Final Analysis Report

**Date:** 2026-03-10  
**Benchmark:** SWE-bench-Live (10 issues, seed=42, verified split)  
**Pipeline:** Issue Enhancement (5 agents) + Dual Baselines + SWE-bench Harness

---

## 1. Executive Summary

We evaluated **7 agent configurations** (**2 baselines + 5 enhanced**) across 10 real-world GitHub issues from SWE-bench-Live.

- **Total submitted evaluations:** 66
- **Completed evaluations (`report.json`):** 15
- **Errors:** 51
- **Resolved instances:** 0

After adding `baseline_simple_solver`, baseline coverage improved in submission count (from 6 baseline submissions to 16 across two baselines), but **completed baseline test reports remain 0** because both baselines still fail at patch-apply stage.

**Key findings:**
- **Fix Rate (SWE-EVO):** 0% across all evaluated agents with completed tests
- **F2P Progress:** up to 50% (enhanced agents can fix target tests on some instances)
- **Patch Apply Rate:** 0% for both baselines vs 20-40% for enhanced agents
- **Content Similarity:** 9.5%-75.4% on completed enhanced instances
- **Regression Rate:** 99.3%-100% (dominant blocker)

---

## 2. Agents Evaluated (7 Total)

| # | Agent ID | Type | Description |
|---|----------|------|-------------|
| 1 | `baseline_no_enhancement` | Baseline | OpenAI solver with original issue only |
| 2 | `baseline_simple_solver` | Baseline | Simple solver in baseline mode |
| 3 | `enhanced_live_swe_agent` | Enhanced | Live SWE Agent enhancement + solver |
| 4 | `enhanced_mini_swe_agent` | Enhanced | Mini SWE Agent enhancement + solver |
| 5 | `enhanced_openhands` | Enhanced | OpenHands enhancement + solver |
| 6 | `enhanced_simple_enhancer` | Enhanced | Simple Enhancer enhancement + solver |
| 7 | `enhanced_trae` | Enhanced | Trae enhancement + solver |

---

## 2.1 Workflow And LLMs

**Solver agent workflow**
- Input: issue text (title + body) and repo metadata; for enhanced runs, the solver receives the enhanced issue text.
- Process: generate a patch diff targeting the repo; outputs a JSON with a patch string.
- LLM used: `openai_agents_sdk` baseline uses the local Ollama `gpt-oss` model (as configured in `scripts/enhancers/run_solving_after_enhancement.py` output).

**Enhancement agents workflow**
- Input: the same raw issue (title + body) from the SWE-bench-Live sample set.
- Process: each enhancer rewrites/augments the issue into a solver-ready prompt (adds context, file hints, constraints), then the solver runs on that enhanced issue.
- LLMs used: each enhancer uses its own configured LLM backend (see `src/enhancers/ready_to_use/*_enhancer.py` and `configs/` for exact models).

**Input parity across enhancers**
- Yes. All enhancement agents receive the exact same issue text from the sample set.
- Differences come from each enhancer’s prompt template and model, not from different inputs.

---

## 3. Run Summary (Regenerated)

| Agent | Submitted | Completed | Errors | Patches Applied | Patch Apply Rate |
|-------|----------:|----------:|-------:|----------------:|-----------------:|
| baseline_no_enhancement | 6 | 0 | 6 | 0 | 0% |
| baseline_simple_solver | 10 | 0 | 10 | 0 | 0% |
| enhanced_live_swe_agent | 10 | 3 | 7 | 3 | 30% |
| enhanced_mini_swe_agent | 10 | 2 | 8 | 2 | 20% |
| enhanced_openhands | 10 | 2 | 8 | 2 | 20% |
| enhanced_simple_enhancer | 10 | 4 | 6 | 4 | 40% |
| enhanced_trae | 10 | 4 | 6 | 4 | 40% |

**Totals:** 66 submitted, 15 completed, 51 errors, 15 applied patches.

---

## 4. Patch Apply Matrix (Dual Baselines)

| Issue | OpenAI Baseline | Simple Baseline | Live SWE | Mini SWE | OpenHands | Simple Enhancer | Trae |
|-------|------------------|-----------------|----------|----------|-----------|-----------------|------|
| aws-cloudformation/cfn-lint-3764 | FAILED | FAILED | FAILED | FAILED | FAILED | FAILED | FAILED |
| instructlab/instructlab-1762 | FAILED | FAILED | FAILED | FAILED | FAILED | FAILED | FAILED |
| instructlab/instructlab-3135 | FAILED | FAILED | **APPLIED** | FAILED | FAILED | FAILED | FAILED |
| keras-team/keras-20125 | FAILED | FAILED | **APPLIED** | **APPLIED** | **APPLIED** | **APPLIED** | **APPLIED** |
| koxudaxi/datamodel-code-generator-2334 | EMPTY | FAILED | **APPLIED** | **APPLIED** | **APPLIED** | **APPLIED** | **APPLIED** |
| matplotlib/matplotlib-28734 | FAILED | FAILED | FAILED | FAILED | FAILED | **APPLIED** | **APPLIED** |
| pytorch/torchtune-1697 | EMPTY | FAILED | FAILED | FAILED | FAILED | **APPLIED** | **APPLIED** |
| reflex-dev/reflex-3842 | EMPTY | FAILED | FAILED | FAILED | FAILED | FAILED | FAILED |
| reflex-dev/reflex-4129 | EMPTY | FAILED | FAILED | FAILED | FAILED | FAILED | FAILED |
| theoehrly/fast-f1-701 | FAILED | FAILED | FAILED | FAILED | FAILED | FAILED | FAILED |

`EMPTY` means not submitted (no prediction entry for that instance).

### Patch Apply Rate by Agent

| Agent | Applied | Total (non-empty) | Rate |
|-------|--------:|------------------:|-----:|
| baseline_no_enhancement | 0 | 6 | 0.0% |
| baseline_simple_solver | 0 | 10 | 0.0% |
| enhanced_live_swe_agent | 3 | 10 | 30.0% |
| enhanced_mini_swe_agent | 2 | 10 | 20.0% |
| enhanced_openhands | 2 | 10 | 20.0% |
| enhanced_simple_enhancer | 4 | 10 | 40.0% |
| enhanced_trae | 4 | 10 | 40.0% |

---

## 5. Core Test Metrics (Completed Evaluations)

Summary table below includes all agents. Detailed per-metric tables focus on enhanced agents because baselines have 0 completed harness reports.

### 5.0 Definitions (All Metrics)

| Metric | Definition |
|--------|------------|
| Fix Rate (SWE-EVO) | F2P_passed / F2P_total if P2P_failures == 0, else 0 |
| F2P Progress Rate | F2P_passed / F2P_total (ignoring regressions) |
| Regression Rate | P2P_failures / P2P_total |
| No-Regression Rate | % instances with 0 P2P failures |
| F2P Rate | Total F2P successes / total F2P tests |
| P2P Rate | Total P2P successes / total P2P tests |
| Patch Apply Rate | patches_applied / patches_non_empty |
| File Overlap (Jaccard) | |agent_files ∩ gt_files| / |agent_files ∪ gt_files| |
| Content Similarity | SequenceMatcher(agent_patch, gt_patch).ratio() |
| Efficiency | Tokens, cost, wall-clock time |
| Trajectory | Turns, tool calls |
| Resolved Rate | resolved / completed (all F2P pass and 0 P2P failures) |

### 5.0 Summary Results (All Agents)

| Agent | Fix | F2P Prog | Reg | No-Reg | F2P Rate | P2P Rate | Patch Apply | Resolved | File Overlap | Content Sim |
|-------|----:|---------:|----:|-------:|---------:|---------:|------------:|---------:|-------------:|------------:|
| baseline_no_enhancement | 0.000 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.000 | 0.000 |
| baseline_simple_solver | 0.000 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.000 | 0.000 |
| enhanced_live_swe_agent | 0.000 | 33.3% | 99.8% | 0.0% | 33.3% | 0.0% | 30.0% | 0.0% | 1.000 | 0.355 |
| enhanced_mini_swe_agent | 0.000 | 50.0% | 99.7% | 0.0% | 50.0% | 0.0% | 20.0% | 0.0% | 1.000 | 0.449 |
| enhanced_openhands | 0.000 | 50.0% | 99.7% | 0.0% | 50.0% | 0.0% | 20.0% | 0.0% | 1.000 | 0.449 |
| enhanced_simple_enhancer | 0.000 | 25.0% | 99.7% | 0.0% | 9.1% | 0.3% | 40.0% | 0.0% | 0.875 | 0.270 |
| enhanced_trae | 0.000 | 25.0% | 99.7% | 0.0% | 9.1% | 0.3% | 40.0% | 0.0% | 0.875 | 0.270 |

### 5.1 Fix Rate (SWE-EVO)

| Agent | Mean Fix Rate | Max Fix Rate | No-Regression % |
|-------|--------------:|-------------:|----------------:|
| enhanced_live_swe_agent | 0.000 | 0.000 | 0.0% |
| enhanced_mini_swe_agent | 0.000 | 0.000 | 0.0% |
| enhanced_openhands | 0.000 | 0.000 | 0.0% |
| enhanced_simple_enhancer | 0.000 | 0.000 | 0.0% |
| enhanced_trae | 0.000 | 0.000 | 0.0% |

### 5.2 F2P Progress Rate

| Agent | Mean F2P Progress | Best Instance |
|-------|------------------:|---------------|
| enhanced_live_swe_agent | 33.3% | koxudaxi (100%) |
| enhanced_mini_swe_agent | 50.0% | koxudaxi (100%) |
| enhanced_openhands | 50.0% | koxudaxi (100%) |
| enhanced_simple_enhancer | 25.0% | koxudaxi (100%) |
| enhanced_trae | 25.0% | koxudaxi (100%) |

### 5.3 Regression Rate

| Agent | Mean Regression Rate | Best Instance |
|-------|---------------------:|---------------|
| enhanced_live_swe_agent | 99.78% | koxudaxi (99.34%) |
| enhanced_mini_swe_agent | 99.67% | koxudaxi (99.34%) |
| enhanced_openhands | 99.67% | koxudaxi (99.34%) |
| enhanced_simple_enhancer | 99.69% | koxudaxi (99.34%) |
| enhanced_trae | 99.69% | koxudaxi (99.34%) |


### 5.4 Additional Rates (F2P, P2P, Patch Apply, Resolved)

| Agent | F2P Rate | P2P Rate | Patch Apply Rate | Resolved Rate |
|-------|---------:|---------:|-----------------:|--------------:|
| baseline_no_enhancement | 0.0% | 0.0% | 0.0% | 0.0% |
| baseline_simple_solver | 0.0% | 0.0% | 0.0% | 0.0% |
| enhanced_live_swe_agent | 33.3% | 0.0% | 30.0% | 0.0% |
| enhanced_mini_swe_agent | 50.0% | 0.0% | 20.0% | 0.0% |
| enhanced_openhands | 50.0% | 0.0% | 20.0% | 0.0% |
| enhanced_simple_enhancer | 9.1% | 0.3% | 40.0% | 0.0% |
| enhanced_trae | 9.1% | 0.3% | 40.0% | 0.0% |

Notes: F2P/P2P rates are aggregated across all executed tests (total successes / total tests). Resolved rate = resolved / completed, where resolved requires all F2P passing and zero P2P failures.

---

## 6. Alignment Metrics

### 6.1 File Overlap (Jaccard)

| Agent | Mean File Overlap | # Completed Instances |
|-------|------------------:|----------------------:|
| enhanced_live_swe_agent | 1.000 | 3 |
| enhanced_mini_swe_agent | 1.000 | 2 |
| enhanced_openhands | 1.000 | 2 |
| enhanced_simple_enhancer | 0.875 | 4 |
| enhanced_trae | 0.875 | 4 |

### 6.2 Content Similarity

| Agent | Mean Content Similarity | Best Instance |
|-------|------------------------:|---------------|
| enhanced_live_swe_agent | 35.5% | koxudaxi (75.4%) |
| enhanced_mini_swe_agent | 44.9% | koxudaxi (75.4%) |
| enhanced_openhands | 44.9% | koxudaxi (75.4%) |
| enhanced_simple_enhancer | 27.0% | koxudaxi (75.4%) |
| enhanced_trae | 27.0% | koxudaxi (75.4%) |

---

## 7. Per-Instance Outcome Snapshot

| Instance | Applied (7 agents total) | F2P | P2P Failures | Regression | Content Similarity |
|----------|--------------------------:|-----|--------------|------------|--------------------|
| koxudaxi/datamodel-code-generator-2334 | 5/7 | **1/1 (100%)** | 602/606 | 99.3% | **75.4%** |
| keras-team/keras-20125 | 5/7 | 0/1 (0%) | 7423/7423 | 100% | 11.9%-14.3% |
| instructlab/instructlab-3135 | 1/7 | 0/1 (0%) | 307/307 | 100% | 16.6% |
| matplotlib/matplotlib-28734 | 2/7 | 0/1 (0%) | 8100/8146 | 99.4% | 9.5% |
| pytorch/torchtune-1697 | 2/7 | 0/8 (0%) | 528/528 | 100% | 11.2% |
| aws-cloudformation/cfn-lint-3764 | 0/7 | - | - | - | - |
| instructlab/instructlab-1762 | 0/7 | - | - | - | - |
| reflex-dev/reflex-3842 | 0/7 | - | - | - | - |
| reflex-dev/reflex-4129 | 0/7 | - | - | - | - |
| theoehrly/fast-f1-701 | 0/7 | - | - | - | - |

---

## 8. Dual-Baseline Comparison

### 8.1 OpenAI Baseline (`baseline_no_enhancement`) vs Enhanced

- Submitted: 6 (4 instances not submitted)
- Applied: 0/6
- Completed reports: 0
- Enhanced agents: 20%-40% apply rate and all 15 completed reports

### 8.2 Simple Baseline (`baseline_simple_solver`) vs Enhanced

- Submitted: 10/10
- Applied: 0/10
- Completed reports: 0
- Enhanced agents still dominate in apply success and downstream evaluation coverage

### 8.3 What changed after adding the second baseline

- Baseline submission coverage increased (6 -> 16 total baseline submissions)
- Baseline completion did **not** increase (still 0)
- Main conclusion remains unchanged: enhancement is necessary to reach evaluable patches in this setup

---

## 9. Baseline Reference in Derived Metrics

`comprehensive_metrics.py` keeps `baseline_no_enhancement` as the baseline reference for baseline comparisons.

In this run:
- `eval_results/swebench/iteration2_full_comprehensive_metrics.json` contains an empty `baseline_comparison` object because the baseline has no completed test reports.
- `eval_results/swebench/iteration2_full_fix_rate_metrics.json` still provides per-agent delta fix-rate summaries (all zero here due zero fix rates throughout).

---

## 10. Integrity Checks (New Baseline)

- `baseline_simple_solver/all_preds.jsonl` lines: **10**
- Unique `model_name_or_path`: **`baseline_simple_solver`**
- `instance_id` set matches expected 10 sampled issues: **Yes**
- `find logs/run_evaluation/iteration2_full/baseline_simple_solver -name report.json | wc -l`: **0**

---

## 11. Key Insights

1. Enhancement remains the differentiator for generating evaluable patches (20%-40% apply rate vs 0% for both baselines).
2. The pipeline can fix target failures (`koxudaxi` F2P=100%), but all successful applies still trigger large regressions.
3. **Regression control** remains the core blocker to non-zero Fix Rate, not only patch-format quality.
4. Adding `baseline_simple_solver` improves baseline coverage accounting, but not baseline performance.

---

## 12. Iteration 1 vs Iteration 2 (Current State)

| Metric | Iteration 1 (v3) | Iteration 2 (dual baseline) |
|--------|------------------|-----------------------------|
| Agents in final comparison | 6 | **7** |
| Harness evaluations with results | 0 (patch-format block) | **15** |
| Report.json files generated | 0 | **15** |
| Best patch apply rate | Unknown | **40%** |
| Best F2P Progress | Unknown | **50%** |
| Fix Rate | 0% | 0% |
| Content similarity range | 14.3%-44.9%* | 9.5%-75.4% |

*Iteration 1 similarity was computed from raw patch files, not harness-completed evaluations.

---

## 13. Generated Artifacts

| File | Description |
|------|-------------|
| `eval_results/swebench/iteration2_full_aggregate_report.json` | 7-agent aggregate summary + patch apply matrix |
| `eval_results/swebench/iteration2_full_comprehensive_metrics.json` | Comprehensive metric set |
| `eval_results/swebench/iteration2_full_fix_rate_metrics.json` | SWE-EVO fix-rate breakdown + deltas |
| `eval_results/swebench/iteration2_predictions/*/all_preds.jsonl` | 7 agent prediction folders (+ combined file) |
| `logs/run_evaluation/iteration2_full/*/report.json` | 15 completed harness reports |
| `baseline_no_enhancement.iteration2_full.json` | Baseline summary (OpenAI) |
| `baseline_simple_solver.iteration2_full.json` | Baseline summary (simple solver) |
| `enhanced_*.iteration2_full.json` | Per-enhanced-agent summaries |
