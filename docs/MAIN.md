# Documentation Index

## Canonical Experiment Track

- Workflow script: `scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py`
- Baseline source: `/home/22pf2/SWE-Bench_Replication`
- Latest dataset: 50 SWE-bench-Live issues (`data/samples/groupC_swebenchlive_50/`)

### Solver Stack (Verified Against SWE-bench Leaderboard)

| Component | Value |
|-----------|-------|
| **Agent** | mini-SWE-agent v2.2.7 |
| **Model** | Devstral-Small-2-24B-Instruct-2512 (via local vLLM) |
| **Benchmark Config** | `swebench_backticks.yaml` (standard, matches leaderboard) |
| **Custom Config** | `swebench_backticks_regression_guard.yaml` (our addition, +5 F2P / +2 P2P) |
| **SWE-bench Verified Score** | 56.40% (official leaderboard, top open-source entry) |
| **SWE-bench-Live Baseline** | 2.0% (expected — Live is ~28x harder than Verified) |

### Latest Runs

| Experiment | Result Directory | Status |
|-----------|-----------------|:------:|
| TRAE (Devstral, 50 issues) | `results/groupC50_baseline_vs_enhanced/trae__native_groupC50_20260401/` | Complete |
| SWE-agent (Devstral, 50 issues) | `results/groupC50_baseline_vs_enhanced/swe_agent__native_groupC50_20260401/` | Complete |
| Aider (Devstral, 50 issues) | `results/groupC50_baseline_vs_enhanced/aider__native_groupC50_20260401/` | Complete |
| Code-context (Devstral, 50 issues) | `results/groupC50_code_context/code_context__code_context_groupC50_20260411/` | Complete |
| Code-context+TP (GPT-4o-mini, 50 issues) | `results/groupC50_code_context_gpt4omini/code_context__code_context_gpt4omini_groupC50_20260412/` | Complete |
| Code-context+TP (Devstral, 50 issues) | `results/groupC50_code_context_devstral_tp/` | Complete |
| P2P Approach A (TP + P2P names) | `results/groupC50_p2p_approachA/` | Complete |
| **P2P Approach B (TP + reg guard)** | `results/groupC50_p2p_approachB/` | **Best** |
| P2P Approach C (TP + retry) | `results/groupC50_p2p_approachC/` | Complete |

## Primary Reading Order

1. `groupC_50_issue_experiment_report.md` — Main 50-issue experiment report (all 9 experiments)
2. `groupA_vs_groupB_vs_groupC_experiment_report.md` — 3x3 cross-group comparison
3. `COMPREHENSIVE_PROBLEM_ANALYSIS.md` — System-wide audit and root causes
4. `analysis/VERIFIED10_MULTI_ENHANCER_BUGFIX_RESULTS_2026-03-19.md` — Verified-10 baselines
5. `guides/WORKFLOW_IMPROVEMENT_PLAN.md`

## Current Metrics Snapshot (2026-04-14)

### 50-Issue SWE-bench-Live (Group C) — Full Results

| Enhancer | F2P | P2P | Resolved | F2P Delta vs Baseline |
|----------|:---:|:---:|:--------:|:-----:|
| **Baseline** (no enhancement) | 14/50 (28%) | 2/50 (4%) | 1/50 (2%) | — |
| TRAE | 15/50 (30%) | 2/50 (4%) | 1/50 (2%) | +2% |
| SWE-agent | 15/50 (30%) | 1/50 (2%) | 0/50 (0%) | +2% |
| Aider | 7/50 (14%) | 2/50 (4%) | 0/50 (0%) | -14% |
| Code-context (Devstral, no TP) | 17/50 (34%) | 2/50 (4%) | 1/50 (2%) | +6% |
| Code-context+TP (GPT-4o-mini) | 19/50 (38%) | 2/50 (4%) | 1/50 (2%) | +10% |
| Code-context+TP (Devstral) | 22/50 (44%) | 2/50 (4%) | 1/50 (2%) | +16% |
| **Code-context+TP+RegGuard (Devstral)** | **27/50 (54%)** | **4/50 (8%)** | 1/50 (2%) | **+26%** |

**Key findings**:
1. Code-context is the **only enhancer** producing net-positive F2P effects
2. Regression guard prompt (+5 F2P, +2 P2P) is our custom contribution, not in official mini-SWE-agent
3. P2P remains the bottleneck: 23/27 F2P-passing instances still fail P2P
4. Oracle file selection caveat: source files come from ground-truth patch (see Section 12.2 of report)

### Verified-10 (Group A)

- Baseline: RESOLVED `3/10`, FAIL_TO_PASS `3/10`, PASS_TO_PASS `5/10`
- Enhanced (`simple_enhancer`): RESOLVED `3/10`, FAIL_TO_PASS `3/10`, PASS_TO_PASS `6/10`
- Enhanced (`swe_agent`): RESOLVED `3/10`, FAIL_TO_PASS `3/10`, PASS_TO_PASS `7/10`

## Historical Material

- `investigation/`, `iterations/`, and `archive/` remain available for prior workflow tracks.
- Treat them as reference only; do not use them as canonical run instructions.
