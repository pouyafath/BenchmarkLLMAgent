# Verified-10 Multi-Enhancer Bugfix Results (2026-03-19)

## Objective

Validate the fixed/improved Verified-10 workflow using two enhancer agents with the same solver stack, then compare both against the fixed replication baseline.

## Fixed Workflow Runs

- `simple_enhancer`:
  - `/home/22pf2/BenchmarkLLMAgent/results/verified10_baseline_vs_enhanced/simple_enhancer__bugfix_full10_simple_20260318/`
- `swe_agent`:
  - `/home/22pf2/BenchmarkLLMAgent/results/verified10_baseline_vs_enhanced/swe_agent__bugfix_full10_swe_agent_20260318/`
- Aggregated comparison:
  - `/home/22pf2/BenchmarkLLMAgent/results/verified10_baseline_vs_enhanced/multi_enhancer_bugfix_full10_20260318.json`
  - `/home/22pf2/BenchmarkLLMAgent/results/verified10_baseline_vs_enhanced/multi_enhancer_bugfix_full10_20260318.md`

## Metrics (Issue-Level, 10 IDs)

- Baseline:
  - RESOLVED: `3/10` (30.0%)
  - FAIL_TO_PASS: `3/10` (30.0%)
  - PASS_TO_PASS: `5/10` (50.0%)
- Enhanced (`simple_enhancer`):
  - RESOLVED: `3/10` (30.0%)
  - FAIL_TO_PASS: `3/10` (30.0%)
  - PASS_TO_PASS: `6/10` (60.0%)
- Enhanced (`swe_agent`):
  - RESOLVED: `3/10` (30.0%)
  - FAIL_TO_PASS: `3/10` (30.0%)
  - PASS_TO_PASS: `7/10` (70.0%)

## Notes

- All three rows used the same 10 Verified IDs from replication.
- All runs completed `10/10` attempted with `0` model/provider failures and `0` evaluation failures.
- Compared to baseline, both enhancers improved PASS_TO_PASS while RESOLVED stayed unchanged.

## Workflow Fixes Applied Before These Runs

1. Deterministic eval model-dir selection and robust no-report fallback
2. True skip-eval/skip-solver semantics
3. Baseline denominator slicing by selected IDs
4. Solver timeout retry loop for `Timeout` statuses
5. Config-aware enhancement cache keys
6. Attempted-only rate reporting in addition to full-denominator rates
7. Reproducibility manifest emission per run
