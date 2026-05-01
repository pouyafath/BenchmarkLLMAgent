# Verified-10 Baseline vs Enhanced Results (2026-03-18)

> Historical snapshot for the 2026-03-18 run.
>
> Latest bugfix multi-enhancer results are in:
> `VERIFIED10_MULTI_ENHANCER_BUGFIX_RESULTS_2026-03-19.md`

## Scope

- Dataset: `SWE-bench/SWE-bench_Verified` (`test`)
- Instances: fixed 10 IDs from `/home/22pf2/SWE-Bench_Replication/selected_instances.txt`
- Baseline: replication run (`mini-SWE-agent + Devstral-Small-2-24B-Instruct-2512`)
- Enhanced run: `simple_enhancer` -> mini-SWE-agent solver on enhanced text

Run directory:

- `/home/22pf2/BenchmarkLLMAgent/results/verified10_baseline_vs_enhanced/simple_enhancer__full10_20260318/`

## Metrics (Issue-Level)

- Baseline:
  - RESOLVED: `3/10` (30.0%)
  - FAIL_TO_PASS success: `3/10` (30.0%)
  - PASS_TO_PASS success: `5/10` (50.0%)
- Enhanced:
  - RESOLVED: `4/10` (40.0%)
  - FAIL_TO_PASS success: `4/10` (40.0%)
  - PASS_TO_PASS success: `6/10` (60.0%)

Delta (Enhanced - Baseline):

- RESOLVED: `+10.0` points
- FAIL_TO_PASS: `+10.0` points
- PASS_TO_PASS: `+10.0` points

## Model/Agent/Timeout Configuration Used

- Baseline (from `/home/22pf2/SWE-Bench_Replication`):
  - Solver scaffold: mini-SWE-agent (`LitellmTextbasedModel`)
  - Solver model: `hosted_vllm/Devstral-Small-2-24B-Instruct-2512`
  - mini-SWE-agent config: `agent.step_limit=250`, `environment.timeout=60`
  - SWE-bench evaluation timeout: `--timeout 1800` (per instance)
  - Run parallelism: solver workers `1`, eval workers `1`

- Enhanced run (`simple_enhancer__full10_20260318`):
  - Enhancer agent: `simple_enhancer` via `src/utils/llm_client.py` (`openai_compat` backend)
  - Enhancer model: `Devstral-Small-2-24B-Instruct-2512`
  - Enhancer HTTP timeout: `600` seconds
  - Solver model and config: same as baseline
  - Run parallelism: enhancement `--parallel 1`, solver `--workers 1`, eval `--max_workers 1`
  - Observed solver timeout behavior: repeated LiteLLM request timeout at `600.0s`

## Caveats

- Solver timeout on `astropy__astropy-13236`
- SWE-bench harness wrote reports for 9/10 instances (one missing `report.json`)
- Enhanced metrics conservatively treat the missing report as failure

## Artifacts

- `comparison_summary.json`
- `comparison_summary.md`
- `enhanced_metrics.json`
- `run_report.md`
- `logs/run_mini_swe_agent_solver.stderr.log` (timeout evidence)
- `logs/run_swebench_evaluation.stdout.log` (9/10 completed evidence)
