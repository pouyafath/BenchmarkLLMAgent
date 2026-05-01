# Verified-10 Workflow Bug Audit (2026-03-18)

## Confirmed Bugs

Status update (2026-03-19): items 1-5 below have been addressed in code.  
This file is preserved as the audit record that drove those fixes.

1. Non-deterministic model-dir selection in metrics loader  
   - File: `scripts/workflows/run_verified10_enhancement_vs_baseline.py`  
   - Location: `_compute_metrics_from_reports()`, around lines 159-163  
   - Detail: picks `model_dirs[0]` without validating which model directory matches the run.  
   - Risk: Wrong metrics if multiple model dirs exist under the same `run_id`.

2. `--skip-eval` is not a true skip path  
   - File: `scripts/workflows/run_verified10_enhancement_vs_baseline.py`  
   - Location: evaluation skip flag at lines 446-468, followed by unconditional metrics call at lines 470-474  
   - Detail: even with `--skip-eval`, code still calls `_compute_metrics_from_reports()` and fails unless reports already exist.  
   - Risk: Misleading CLI behavior; partial workflows crash.

3. Baseline denominator mismatch for smoke runs  
   - File: `scripts/workflows/run_verified10_enhancement_vs_baseline.py`  
   - Location: selected subset is sliced at line 380, baseline still read from full summary at lines 476-489  
   - Detail: baseline metrics are always read from 10-issue replication summary, while enhanced run may use `--max-issues < 10`.  
   - Risk: Delta values become non-comparable in smoke/partial runs.

4. Timeout-driven incomplete evaluation not handled by harness summary parser  
   - Files: workflow script + run logs  
   - Detail: Harness completed 9/10 reports (`Instances completed: 9`) while 10 predictions were submitted. One missing `report.json` caused post-processing failure before fix.  
   - Current state: crash is fixed; missing reports are now counted as evaluation failures.

5. Singleton LLM client can retain stale backend/model settings  
   - File: `src/utils/llm_client.py`  
   - Location: global `_client` and `get_client()` near end of file  
   - Detail: `get_client()` caches a global `_client` and ignores new kwargs after first initialization.  
   - Risk: Multi-agent or multi-backend runs in one process may silently use the wrong model/backend.

## Observed Reliability Issue (Not a code crash)

- Solver experienced repeated LiteLLM 600s request timeouts on `astropy__astropy-13236` and ended with one `Timeout` exit status.
- Evidence:
  - `results/verified10_baseline_vs_enhanced/simple_enhancer__full10_20260318/logs/run_mini_swe_agent_solver.stderr.log`
  - `solver_run/exit_statuses_*.yaml`

## Priority Fix Order

1. Fix model-dir selection deterministically (high)
2. Make `--skip-eval` and `--skip-solver` true partial-workflow modes (high)
3. Align baseline slicing with `--max-issues` for smoke tests (medium)
4. Remove or parameterize LLM singleton caching (medium)
5. Add explicit timeout/retry policy knobs for solver model calls (medium)
