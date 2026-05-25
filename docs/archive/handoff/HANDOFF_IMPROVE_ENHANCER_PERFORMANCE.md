# Agent Handoff: Improve Code-Context Enhancer Performance on 50-Issue SWE-bench-Live

**Date**: 2026-04-14
**Project**: `/home/22pf2/BenchmarkLLMAgent`
**Python env**: `bench_env/` (Python 3.12, swebench 4.1.0)

---

## Situation Summary

We have a pipeline that enhances GitHub issue descriptions before feeding them to an automated bug-fixing agent (mini-SWE-agent). The pipeline runs on 50 SWE-bench-Live issues. Our best configuration so far:

| Metric | Value |
|--------|-------|
| **F2P (fail-to-pass)** | 27/50 (54%) — the solver produces a patch that fixes the bug |
| **P2P (pass-to-pass)** | 4/50 (8%) — the solver's patch doesn't break existing tests |
| **Resolved (F2P AND P2P)** | 1/50 (2%) — fully correct patches |

**The bottleneck is P2P**: 23 of 27 F2P-passing instances break existing tests. We need the solver to produce patches that fix bugs WITHOUT introducing regressions.

---

## Solver Stack (Verified Against Official SWE-bench Leaderboard)

Our solver exactly matches the official leaderboard entry for **mini-SWE-agent + Devstral Small (2512)**, which scores **56.40% on SWE-bench Verified** (top open-source entry).

| Component | Config File | Value |
|-----------|------------|-------|
| **Agent** | mini-SWE-agent v2.2.7 | `/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/` |
| **Standard benchmark config** | `swebench_backticks.yaml` | `/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks.yaml` |
| **Custom regression-guard config** | `swebench_backticks_regression_guard.yaml` | `/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks_regression_guard.yaml` |
| **Model override** | `devstral_vllm_override.yaml` | `/home/22pf2/SWE-Bench_Replication/config/devstral_vllm_override.yaml` |
| **Model** | Devstral-Small-2-24B-Instruct-2512 | Served via local vLLM at `http://127.0.0.1:18000/v1` |
| **Temperature** | 0.0 | Deterministic |
| **Step limit** | 250 | Max solver turns |
| **Cost limit** | $3.00 | Per issue |

### Important: Standard vs Custom Config

The **standard** `swebench_backticks.yaml` (used on the leaderboard) has a 5-step recommended workflow:
1. Analyze codebase
2. Reproduce issue
3. Edit source code
4. Verify fix
5. Test edge cases

Our **custom** `swebench_backticks_regression_guard.yaml` adds:
- **Step 6**: "Run the project's test suite to verify your changes don't break existing tests"
- A `<CRITICAL_REGRESSION_GUARD>` block (lines 54–70) with explicit instructions to identify test commands, run the test suite, and revise patches if regressions are detected

This custom prompt is **NOT part of upstream mini-SWE-agent** — it is our contribution. It accounts for +5 F2P and +2 P2P improvement (Approach B results).

### SWE-bench Verified vs SWE-bench-Live

Our low 2% baseline resolved rate is NOT a bug — it reflects the dataset difficulty:
- **SWE-bench Verified**: 56.40% (Devstral baseline) — curated Python issues, well-known repos
- **SWE-bench-Live**: 2.0% (our baseline) — recent, unseen issues, diverse repos, ~28x harder

---

## Current Best Configuration (Approach B)

The best run uses code-context enhancement with test_patch + regression guard prompt:

- **Enhancer**: `code_context` with `CODE_CONTEXT_INCLUDE_TEST_PATCH=1`
- **Solver prompt**: `swebench_backticks_regression_guard.yaml`
- **Result dir**: `results/groupC50_p2p_approachB/code_context__code_context_devstral_tp_regguard_groupC50_20260414/`

### What the Enhancer Does (No LLM)

The `code_context` enhancer is deterministic — no LLM involved. It appends to the issue body:

1. **Source code** of files that need to change (from Docker container, max 200 lines/file)
2. **Developer hints** (`hints_text` field from SWE-bench dataset)
3. **Failing test names** (`FAIL_TO_PASS` field)
4. **Test specification** (`test_patch` field) — the actual test code that validates the fix

**Oracle caveat**: Source files are selected by parsing filenames from the ground-truth patch. A real-world tool wouldn't know which files to change. This is disclosed in the report (Section 12.2). Relative comparisons remain valid.

Implementation: `src/enhancers/ready_to_use/code_context_enhancer.py`

---

## All Experiment Results (for context)

| Config | F2P | P2P | Resolved | F2P Δ vs Baseline |
|--------|:---:|:---:|:--------:|:-----:|
| **Baseline** (no enhancement) | 14/50 (28%) | 2/50 (4%) | 1/50 (2%) | — |
| TRAE (LLM paraphrasing) | 15/50 (30%) | 2/50 (4%) | 1/50 (2%) | +2% |
| SWE-agent (LLM paraphrasing) | 15/50 (30%) | 1/50 (2%) | 0/50 (0%) | +2% |
| Aider (LLM paraphrasing) | 7/50 (14%) | 2/50 (4%) | 0/50 (0%) | -14% |
| Code-context (no test_patch) | 17/50 (34%) | 2/50 (4%) | 1/50 (2%) | +6% |
| Code-context+TP (GPT-4o-mini) | 19/50 (38%) | 2/50 (4%) | 1/50 (2%) | +10% |
| Code-context+TP (Devstral) | 22/50 (44%) | 2/50 (4%) | 1/50 (2%) | +16% |
| TP + P2P test names (Approach A) | 22/50 (44%) | 1/50 (2%) | 1/50 (2%) | +16% |
| **TP + reg guard (Approach B)** | **27/50 (54%)** | **4/50 (8%)** | 1/50 (2%) | **+26%** |
| TP + retry loop (Approach C) | 17/21 F2P | 0/21 P2P | 0/21 | — |

---

## What Has Already Been Tried for P2P

### Approach A: Include P2P Test Names in Description
Added up to 20 regression test names to the enhanced body. **Result**: No improvement — P2P dropped from 2 to 1. Simply telling the solver which tests exist doesn't help.

### Approach B: Regression Guard Prompt (BEST)
Modified the solver prompt with explicit regression testing instructions. **Result**: +5 F2P, +2 P2P. The solver needs to be *instructed* to test, not just *told* which tests exist.

### Approach C: Retry Loop with Failure Feedback
Re-ran 21 F2P-pass/P2P-fail instances with specific failure info appended. **Result**: Lost 4 F2P, gained 0 P2P. Counterproductive — non-deterministic retries produce different (worse) patches.

### Key Insight
**Prompt engineering > data engineering for P2P.** Modifying the solver's behavior (Approach B) was far more effective than providing data (Approach A) or post-hoc retry (Approach C).

---

## Your Tasks

### Task 1: Analyze the 23 F2P-pass / P2P-fail Instances

The 23 instances that fix the bug but break existing tests are the primary opportunity. Understanding WHY they fail P2P can guide improvements.

**Steps**:
1. Read the comparison summary: `results/groupC50_p2p_approachB/code_context__code_context_devstral_tp_regguard_groupC50_20260414/comparison_summary.json`
2. For each F2P-pass / P2P-fail instance, examine:
   - The solver's generated patch (in `enhanced_solver_run/<instance_id>/patch.txt`)
   - The evaluation log (search for `FAIL` in eval results)
   - What P2P tests are failing and why
3. Categorize failure modes:
   - **Overly broad changes** — patch modifies more than needed
   - **Missing imports/side effects** — patch fixes the bug but breaks dependencies
   - **Test infrastructure** — tests fail due to environment, not code
   - **Fundamental conflicts** — fixing the bug inherently conflicts with existing tests
4. Write findings to `docs/analysis/p2p_failure_analysis.md`

### Task 2: Improve the Regression Guard Prompt

Based on Task 1 findings, refine `swebench_backticks_regression_guard.yaml` to address common P2P failure patterns. Ideas:

- **Targeted test instructions**: If most failures are in specific test patterns (e.g., import changes), add explicit guidance
- **Pre-patch test baseline**: Instruct solver to run relevant tests BEFORE making changes, then verify they still pass after
- **Patch minimality**: Stronger instructions to make minimal changes
- **Two-phase approach**: Fix bug first, then verify nothing breaks, then refine if needed

**File to edit**: `/home/22pf2/SWE-Bench_Replication/mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks_regression_guard.yaml`

### Task 3: Re-run with Improved Prompt

After modifying the prompt, re-run the full pipeline:

```bash
# Ensure vLLM is running with Devstral
# Server should be at http://127.0.0.1:18000/v1

bench_env/bin/python scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py \
  --enhancer-agent code_context \
  --output-tag code_context_devstral_tp_regguard_v2_groupC50_$(date +%Y%m%d) \
  --dataset-jsonl data/samples/groupC_swebenchlive_50/groupC50_dataset.jsonl \
  --selected-ids-file data/samples/groupC_swebenchlive_50/groupC50_instance_ids.txt \
  --samples-json data/samples/groupC_swebenchlive_50/groupC50_samples.json \
  --max-issues 50 \
  --namespace starryzhang \
  --allow-identical-enhancements \
  --max-enhanced-body-chars 30000 \
  --solver-workers 4 \
  --eval-workers 4 \
  --skip-baseline \
  --results-root results/groupC50_p2p_improved \
  --benchmark-config swebench_backticks_regression_guard.yaml
```

**IMPORTANT**: `--skip-baseline` reuses the existing baseline. Copy the `baseline_solver_run/` directory from any previous experiment's output dir to the new output dir before running.

### Task 4 (Optional): Try a Stronger Solver Model

If a stronger model is available (e.g., GPT-4o, Claude Sonnet), it might follow the regression guard instructions more effectively. To use a different model:

1. Create a new model override YAML in `/home/22pf2/SWE-Bench_Replication/config/`
2. Pass it via `--model-override-config <filename>.yaml`

---

## Environment Setup

### Required Environment Variables for Code-Context Enhancer

```bash
export CODE_CONTEXT_DATASET_JSONL=data/samples/groupC_swebenchlive_50/groupC50_dataset.jsonl
export CODE_CONTEXT_INCLUDE_SOURCE=1
export CODE_CONTEXT_INCLUDE_HINTS=1
export CODE_CONTEXT_INCLUDE_FAILING_TESTS=1
export CODE_CONTEXT_INCLUDE_TEST_PATCH=1
export CODE_CONTEXT_MAX_LINES_PER_FILE=200
export CODE_CONTEXT_MAX_TOTAL_CHARS=25000
```

These are set automatically by the workflow script when `--enhancer-agent code_context` is used.

### vLLM Server

The Devstral model must be served via vLLM:
```bash
# 4-way data parallel, 131k context, 0.85 GPU utilization
# Server endpoint: http://127.0.0.1:18000/v1
# Check if running: curl http://127.0.0.1:18000/v1/models
```

---

## Key Files

| File | Purpose |
|------|---------|
| `src/enhancers/ready_to_use/code_context_enhancer.py` | Code-context enhancer (deterministic, no LLM) |
| `src/enhancers/dispatcher.py` | Enhancer dispatch — maps agent IDs to functions |
| `scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py` | Main workflow script |
| `swebench_backticks_regression_guard.yaml` (in SWE-Bench_Replication) | Solver prompt with regression guard |
| `swebench_backticks.yaml` (in SWE-Bench_Replication) | Standard solver prompt (no regression guard, matches leaderboard) |
| `devstral_vllm_override.yaml` (in SWE-Bench_Replication/config) | Model config for local Devstral vLLM |
| `data/samples/groupC_swebenchlive_50/` | 50-issue dataset (samples JSON, JSONL, instance IDs) |
| `docs/groupC_50_issue_experiment_report.md` | Full experiment report (Sections 12.12–12.16 most relevant) |
| `docs/MAIN.md` | Documentation index with metrics snapshot |
| `results/groupC50_p2p_approachB/` | Best result so far (Approach B) |

---

## Success Criteria

| Metric | Current (Approach B) | Target |
|--------|:---:|:---:|
| **F2P** | 27/50 (54%) | Maintain or improve |
| **P2P** | 4/50 (8%) | **>8/50 (>16%)** |
| **Resolved** | 1/50 (2%) | **>2/50 (>4%)** |

The primary goal is improving P2P without losing F2P. Even gaining 2-3 more P2P instances would be a significant improvement.

---

## What NOT to Do

1. **Do NOT change the code-context enhancer** — it works well. Focus on the solver prompt.
2. **Do NOT use the standard `swebench_backticks.yaml`** — always use the regression guard version as baseline.
3. **Do NOT try retry loops** (Approach C) — they were counterproductive.
4. **Do NOT modify the ground-truth patches or test specs** — these are fixed data.
5. **Do NOT change the model override** unless intentionally testing a different model.
