# Workflow Improvement Plan (Verified-10 Canonical Track)

## Baseline Context

- Canonical run:
  - `results/verified10_baseline_vs_enhanced/simple_enhancer__full10_20260318/`
- Current result:
  - Baseline: RESOLVED `3/10`, F2P issue success `3/10`, P2P issue success `5/10`
  - Enhanced (`simple_enhancer`): RESOLVED `4/10`, F2P `4/10`, P2P `6/10`
- Reliability caveat:
  - One timeout-driven missing report (`astropy__astropy-13236`)

## Implementation Status (2026-03-19)

Implemented in code and validated through two new full runs:

- Timeout retry loop for solver `Timeout` statuses
- Deterministic eval model-dir selection
- True partial-run behavior for skip modes
- Baseline slicing by selected IDs
- Config-aware enhancement cache keys
- Attempted-only rate reporting
- Reproducibility manifest per run
- No-report fallback metrics when harness skips per-instance reports

See:

- `scripts/workflows/run_verified10_enhancement_vs_baseline.py`
- `scripts/enhancers/run_enhancement_benchmark.py`
- `src/utils/llm_client.py`

## Priority Improvements

1. Reliability-first execution
   - Add targeted rerun for instances with solver `Timeout` exit status.
   - Keep worker count at `1` for solver/eval until timeout rate is near zero.
   - Goal: eliminate missing evaluation reports.

2. Deterministic metrics ingestion
   - Select evaluation model directory by explicit model name, not `model_dirs[0]`.
   - Validate expected `report.json` count before metric computation.
   - Goal: prevent wrong or partial metric reads.

3. Correct partial-run semantics
   - Make `--skip-eval` and `--skip-solver` true no-op skip paths.
   - For `--max-issues < 10`, slice baseline metrics to same IDs before delta computation.
   - Goal: trustworthy smoke-test comparisons.

4. Enhancement quality gating
   - Reject enhancement outputs that are near-identical to original issue text.
   - Enforce schema + body-length checks before writing enhanced JSONL.
   - Goal: ensure solver always receives meaningful enhanced prompts.

5. Failure taxonomy in final reports
   - Split failure counts into infrastructure, model/provider, and evaluation.
   - Add per-instance failure reason map in `comparison_summary.json`.
   - Goal: faster debugging and cleaner paper reporting.

## Secondary Improvements

1. Representativeness
   - Keep fixed astropy-heavy baseline set for strict comparability.
   - Add a second stratified Verified-10 set to estimate generalization.

2. Throughput
   - Raise enhancer parallelism from `1` to `2` only after reliability targets are met.
   - Keep solver and evaluator at `1` worker for reproducibility.

3. Reproducibility packaging
   - Emit run manifest with git commit, dependency versions, model endpoint config, and command hashes.
   - Store alongside each run directory.
