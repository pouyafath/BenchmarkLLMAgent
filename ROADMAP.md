# BenchmarkLLMAgent Roadmap

## Current Canonical Scope

The active paper workflow is the **Verified-10 baseline-vs-enhanced experiment**:

1. Use fixed 10 IDs from `/home/22pf2/SWE-Bench_Replication/selected_instances.txt`
2. Keep `/home/22pf2/SWE-Bench_Replication` as fixed baseline
3. Run enhancement in this repo
4. Solve enhanced issues with mini-SWE-agent + Devstral 2512
5. Evaluate with SWE-bench harness and compare metrics

Entrypoint:

```bash
./bench_env/bin/python scripts/workflows/run_verified10_enhancement_vs_baseline.py \
  --enhancer-agent simple_enhancer \
  --output-tag run1
```

## Latest Verified-10 Snapshot (2026-03-19)

- Runs:
  - `results/verified10_baseline_vs_enhanced/simple_enhancer__bugfix_full10_simple_20260318/`
  - `results/verified10_baseline_vs_enhanced/swe_agent__bugfix_full10_swe_agent_20260318/`
- Baseline: RESOLVED `3/10`, FAIL_TO_PASS `3/10`, PASS_TO_PASS `5/10`
- `simple_enhancer`: RESOLVED `3/10`, FAIL_TO_PASS `3/10`, PASS_TO_PASS `6/10`
- `swe_agent`: RESOLVED `3/10`, FAIL_TO_PASS `3/10`, PASS_TO_PASS `7/10`
- Reliability: both bugfix runs completed with `10/10` attempted and no evaluation failures.

## Near-Term Priorities

1. Reliability hardening
   - Add rerun logic for `Timeout` solver exits.
   - Make `--skip-eval` and `--skip-solver` true partial-run modes.
2. Metrics robustness
   - Deterministically select model evaluation directory.
   - Report attempted-only rates alongside 10-issue denominator rates.
3. Experiment comparability
   - Keep fixed IDs for baseline comparability.
   - Add a second stratified Verified-10 set for representativeness.

## Medium-Term Plan

1. Multi-enhancer comparison on same 10 IDs
   - Run `simple_enhancer` + selected Category A/B enhancers.
2. Stabilize throughput
   - Increase enhancer parallelism only after timeout rate is near zero.
3. Expand sample size
   - Move from 10 to larger Verified subsets once reliability is stable.

## Historical Tracks

Older SWE-bench-Live and patch-generation tracks remain in `docs/iterations/`, `docs/investigation/`, and `docs/archive/` for reference only.
