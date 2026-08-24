# Documentation Index

## Canonical Experiment Track

### Current Stage 2 Full Track (2026-05-24)

- Workflow: 7-Stage Enhancer+Solver Agentic Workflow
- Dataset lineage: `7,714 raw_candidates -> 3,285 P2P>0 classified -> 3,229 operational export -> 2,950 infra-compatible -> 2,900 live Paul subset`
- Stage 0 & 0.5: Collection, classification, and viability pruning (live run uses `paul-RepoLaunch/data/stage2_2026_viable.jsonl`)
- Stage 1: Node1 (`docjk-gpu-01`) still running; Node2 (`docjk-gpu-02`) **closed** — 961 success / 489 failed / 0 missing
- Stages 2-3: Organize and image-recovery now run in parallel on both nodes; frozen batch123 Stage 3 export complete, 55-row P2P>0 subset already available
- Stages 4-6: Pilot-40 all 3 runs accepted; batch2 Stage 4 complete (54/55), Stage 5/6 snapshot complete on 29 runnable rows, final manifest now 30 runnable
- Status: Node1 Stage 1 live; Node1 and Node2 both running Stage 2 plus targeted image recovery; Developer04 now needs only the final 29 -> 30 closure decision for batch2.

### Pilot-40 Stage 4-6 Runs (2026-05-26 to 2026-06-01)

- OpenHands enhancer (2026-06-01): `runs/paul_pilot40_openhands_20260601/stage6_report/REPORT.md`
  - Result: Baseline 9/40 | openhands 10/40 (+2.5 pp, 39/40 truly enhanced, gained `Diaoul__subliminal-1328`)
  - Comparability audit: `runs/paul_pilot40_openhands_20260601/COMPARABILITY_AUDIT.md`
  - Gained case analysis: `runs/paul_pilot40_openhands_20260601/GAINED_CASE_ANALYSIS.md`
  - Failure classification: `runs/paul_pilot40_openhands_20260601/FAILURE_CLASSIFICATION.md`
  - Status: accepted and directly comparable after shared P2P-gated re-eval
  - Caveat: `Azure__azure-cli-32339` remains a likely runtime/tooling outlier, not a fully root-caused failure
  - Driver: `scripts/workflows/run_pilot40_openhands_enhancer.py`
- **Evaluation methodology**: `docs/guides/PILOT40_EVALUATION_WORKFLOW.md`
  - Reusable re-eval utility: `scripts/workflows/pilot40_reeval_lib.py`
- llm_append_analysis + gpt-5.4-mini (2026-05-26): `runs/paul_pilot40_stage4_stage6_20260526/stage6_report/REPORT.md`
  - Result: Baseline 9/40 | enhanced 8/40 (-1); accepted after P2P-gated re-eval
- llm_append_analysis + gpt-oss:120b (2026-05-27): `runs/paul_pilot40_gptoss_solver_20260527/stage6_report/REPORT.md`
  - Result: Baseline 0/40 | enhanced 0/40 (0); accepted after P2P-gated re-eval

### Pouya-20 Track (current as of 2026-05-09)

- Main workflow: `scripts/workflows/run_pouya20_gpt54mini.py`
- Dataset: `runs/pouya_final20b_20260505_050130/validated_instances.jsonl`
- Baseline: `runs/pouya_solver20_20260505_063614/`
- Native CLI validation: `runs/native_cli_pouya5_20260509/SUMMARY.json`
- Validation report: `analysis/NATIVE_CLI_POUYA5_VALIDATION_2026-05-09.md`
- Pouya-5 solver comparison: `runs/pouya5_native_solver_comparison_20260509/summary.json`
- Solver comparison report: `analysis/POUYA5_NATIVE_SOLVER_COMPARISON_2026-05-09.md`

The corrected Pouya-5 native CLI validation confirms 25/25 real native enhancements across `aider`, `trae`, `openhands`, `mini_swe_agent`, and `swe_agent`. SWE-agent now parses benchmark enhancements from trajectory only, rejects weak timeout-contaminated bodies, scans multiple trajectory schemas, and preserves valid trajectory output when the CLI times out after writing the enhancement.

The 2026-05-09 Pouya-5 solver comparison found 0 resolved issues for baseline and all native-enhanced conditions. All five enhancers now run end to end with 5/5 solver predictions; `swe_agent` has one empty solver patch.

### Historical GroupC Track

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

1. `archive/groupC_50_issue_experiment_report.md` — Main 50-issue experiment report (all 9 experiments)
2. `archive/groupA_vs_groupB_vs_groupC_experiment_report.md` — 3x3 cross-group comparison
3. `archive/COMPREHENSIVE_PROBLEM_ANALYSIS.md` — System-wide audit and root causes
4. `archive/analysis/VERIFIED10_MULTI_ENHANCER_BUGFIX_RESULTS_2026-03-19.md` — Verified-10 baselines
5. `archive/guides/WORKFLOW_IMPROVEMENT_PLAN.md`

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

- `archive/investigation/`, `archive/iterations/`, and `archive/` remain available for prior workflow tracks.
- Treat them as reference only; do not use them as canonical run instructions.
