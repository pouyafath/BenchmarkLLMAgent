# BenchmarkLLMAgent Documentation

Project docs are organized around the **current canonical workflow**:

- Dataset: `SWE-bench/SWE-bench_Verified` (`test`)
- Fixed instance set: 10 IDs aligned with `/home/22pf2/SWE-Bench_Replication/selected_instances.txt`
- Baseline: `/home/22pf2/SWE-Bench_Replication` (mini-SWE-agent + Devstral small 2512)
- Enhanced run workflow: `scripts/workflows/run_verified10_enhancement_vs_baseline.py`

## Latest Canonical Result (2026-03-19)

Run directory:

- `results/verified10_baseline_vs_enhanced/simple_enhancer__bugfix_full10_simple_20260318/`
- `results/verified10_baseline_vs_enhanced/swe_agent__bugfix_full10_swe_agent_20260318/`

Issue-level metrics on the same 10 IDs:

- Baseline: RESOLVED `3/10`, FAIL_TO_PASS success `3/10`, PASS_TO_PASS success `5/10`
- Enhanced (`simple_enhancer`): RESOLVED `3/10`, FAIL_TO_PASS success `3/10`, PASS_TO_PASS success `6/10`
- Enhanced (`swe_agent`): RESOLVED `3/10`, FAIL_TO_PASS success `3/10`, PASS_TO_PASS success `7/10`
- Both bugfix runs completed `10/10` with `0` evaluation failures.

## Folder Guide

- `analysis/`: result summaries and debugging audits.
- `guides/`: runnable workflow guides and improvement plans.
- `handoff/`: current handoff and continuation instructions.
- `iterations/`: historical snapshots and phase notes.
- `investigation/`: historical root-cause investigations.
- `archive/`: deprecated/superseded docs.

## Start Here

1. `analysis/VERIFIED10_BASELINE_ENHANCED_RESULTS_2026-03-18.md`
2. `analysis/VERIFIED10_WORKFLOW_BUG_AUDIT_2026-03-18.md`
3. `analysis/VERIFIED10_MULTI_ENHANCER_BUGFIX_RESULTS_2026-03-19.md`
4. `guides/VERIFIED10_BASELINE_ENHANCED_WORKFLOW.md`
5. `handoff/HANDOFF_TO_NEXT_AGENT.md`

## Notes

- Older SWE-bench-Live docs are kept for historical context only.
- For operational commands and metrics, trust the Verified-10 docs above.
