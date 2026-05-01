# Verified-10 Baseline vs Enhanced Workflow

## Goal

Run enhancement experiments on the same 10 SWE-bench Verified issues used in the replication baseline, then compare:

- `RESOLVED`
- `FAIL_TO_PASS`
- `PASS_TO_PASS`

against the fixed baseline from:

- `/home/22pf2/SWE-Bench_Replication/replication_report.md`
- `/home/22pf2/SWE-Bench_Replication/summary.json`
- `/home/22pf2/SWE-Bench_Replication/metrics_breakdown.json`

## Canonical Scripts

1. Prepare the aligned 10-issue sample:

```bash
/home/22pf2/SWE-Bench_Replication/.venv312/bin/python \
  scripts/data/prepare_verified_10_samples_from_replication.py
```

2. Run enhanced experiment + evaluation + comparison:

```bash
./bench_env/bin/python scripts/workflows/run_verified10_enhancement_vs_baseline.py \
  --enhancer-agent simple_enhancer \
  --output-tag run1
```

## Inputs

- Selected IDs: `data/samples/swe_bench_verified_10_instance_ids.txt`
- Enhancer sample: `data/samples/swe_bench_verified_10_samples.json`
- Solver stack: mini-SWE-agent + Devstral small (2512) from `/home/22pf2/SWE-Bench_Replication`

## Outputs

For each run:

- `results/verified10_baseline_vs_enhanced/<agent>__<tag>/commands_run.md`
- `results/verified10_baseline_vs_enhanced/<agent>__<tag>/enhanced_metrics.json`
- `results/verified10_baseline_vs_enhanced/<agent>__<tag>/comparison_summary.json`
- `results/verified10_baseline_vs_enhanced/<agent>__<tag>/comparison_summary.md`

## Baseline Reference (current)

- `RESOLVED`: `3/10 = 30.0%`
- `FAIL_TO_PASS` issue-level: `3/10 = 30.0%`
- `PASS_TO_PASS` issue-level: `5/10 = 50.0%`

## Latest Enhanced Run Snapshot (2026-03-18)

Run directory:

- `results/verified10_baseline_vs_enhanced/simple_enhancer__full10_20260318/`

Enhanced metrics:

- Attempted with report: `9/10`
- Evaluation failure: `1/10` (`astropy__astropy-13236`, solver timeout)
- `RESOLVED`: `4/10 = 40.0%`
- `FAIL_TO_PASS` issue-level: `4/10 = 40.0%`
- `PASS_TO_PASS` issue-level: `6/10 = 60.0%`

Delta vs baseline:

- `RESOLVED`: `+10.0` points
- `FAIL_TO_PASS`: `+10.0` points
- `PASS_TO_PASS`: `+10.0` points

## Notes

- This workflow intentionally uses the same 10 instance IDs as baseline to preserve comparability.
- If Docker/socket permissions are restricted, the SWE-bench evaluation step will fail; run with appropriate Docker access.
- If the local Devstral vLLM endpoint is not running, solver calls will fail; start the same server setup used in `SWE-Bench_Replication`.
