# Iteration 3 Setup: OpenHands LLM Solver

**Date:** 2026-03-12
**Status:** COMPLETED
**Change:** Replaced simple_solver with OpenHands LLM module for direct inference

---

## What Changed

### 1. New Solver: OpenHands LLM (`src/solvers/openhands/agent.py`)

**Before (Iteration 2):** Two solvers available:
- `openai_agents_sdk` — OpenAI Agents SDK with Ollama/vLLM backend
- `simple_solver` — Direct LLM call (Gemma 3 12B)

**After (Iteration 3):** OpenHands replaces simple_solver:
- `openhands` (NEW, DEFAULT) — OpenHands LLM module for direct inference
- `openai_agents_sdk` — kept but no longer default
- `simple_solver` — **commented out** (code preserved but disabled)

**Note:** CodeAct agent mode was tested first but abandoned — it ignored task instructions with gpt-oss:120b (created Flask apps, explored randomly). The final implementation uses `openhands.llm.llm.LLM` for direct inference.

### 2. How OpenHands Solver Works

```
Issue + Context + Exact File Paths → OpenHands LLM module → Patch
                                     (direct inference)
```

1. Takes issue text, exact file paths from `pr_files`, and source code
2. Builds a detailed prompt with EXACT file paths and source code
3. Calls `openhands.llm.llm.LLM` with `gpt-oss:120b` via Ollama
4. Post-processes patch with `_fix_patch_paths()` to correct any wrong paths
5. Extracts unified diff via `extract_patch_from_response()`
6. Returns patch + metadata (elapsed time, model, errors)

### 3. Configuration

Environment variables for OpenHands solver:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENHANDS_SOLVER_MODEL` | `gpt-oss:120b` | LLM model name |
| `OPENHANDS_SOLVER_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible API base URL |
| `OPENHANDS_SOLVER_API_KEY` | `ollama` | API key |
| `OPENHANDS_SOLVER_TIMEOUT` | `600` | Timeout in seconds |
| `OPENHANDS_MAX_ITERATIONS` | `15` | Max agent iteration steps |

### 4. Files Modified

| File | Change |
|------|--------|
| `src/solvers/openhands/__init__.py` | New (empty init) |
| `src/solvers/openhands/agent.py` | New OpenHands solver implementation |
| `scripts/enhancers/run_solving_after_enhancement.py` | Added `openhands` solver option, commented out `simple_solver`, improved solver prompt |

### 5. Why This Change

- **OpenHands LLM module provides structured inference:** Uses `openhands.core.config.LLMConfig` for clean LLM configuration
- **Critical bug fix:** `pr_files` was incorrectly read from ground truth files (always empty); now correctly sourced from samples JSON
- **Explicit file path prompting:** Solver now receives exact file paths and instructs LLM to use them verbatim
- **Path post-processing:** `_fix_patch_paths()` catches and corrects any remaining path mismatches
- **Already installed:** `openhands-ai 1.4.0` is in `bench_env`

### 6. Updated Agent Lineup (7 agents)

| # | Agent ID | Type | Solver |
|---|----------|------|--------|
| 1 | `baseline_no_enhancement` | Baseline | OpenHands (no enhancement) |
| 2 | `baseline_simple_solver` | Baseline | OpenHands (no enhancement, simple baseline) |
| 3 | `enhanced_live_swe_agent` | Enhanced | OpenHands (with Live SWE enhancement) |
| 4 | `enhanced_mini_swe_agent` | Enhanced | OpenHands (with Mini SWE enhancement) |
| 5 | `enhanced_openhands` | Enhanced | OpenHands (with OpenHands enhancement) |
| 6 | `enhanced_simple_enhancer` | Enhanced | OpenHands (with Simple Enhancer) |
| 7 | `enhanced_trae` | Enhanced | OpenHands (with Trae enhancement) |

### 7. Running Iteration 3

```bash
# Step 1: Re-run solving with OpenHands solver (enhanced mode)
cd /home/22pf2/BenchmarkLLMAgent
bench_env/bin/python scripts/enhancers/run_solving_after_enhancement.py \
  --solver openhands --max-issues 10

# Step 2: Re-run solving with OpenHands solver (baseline mode)
bench_env/bin/python scripts/enhancers/run_solving_after_enhancement.py \
  --solver openhands --max-issues 10 --baseline-mode

# Step 3: Convert to predictions
bench_env/bin/python scripts/swebench/convert_to_predictions.py \
  --solving-dir results/solving_after_enhancement \
  --baseline-dir results/solving_baseline \
  --output-dir eval_results/swebench/iteration3_predictions \
  --solver openhands \
  --samples data/samples/swe_bench_live_10_samples.json \
  --max-issues 10

# Step 4: Run SWE-bench harness
for pred in eval_results/swebench/iteration3_predictions/*/all_preds.jsonl; do
  agent=$(basename "$(dirname "$pred")")
  bench_env/bin/python -m swebench.harness.run_evaluation \
    --predictions_path "$pred" \
    --dataset_name data/samples/swe_bench_live_10_tasks_for_harness.json \
    --max_workers 2 --timeout 900 \
    --run_id iteration3 --cache_level env --namespace none \
    --report_dir "logs/run_evaluation/iteration3/$agent"
done

# Step 5: Generate metrics
bench_env/bin/python scripts/reports/generate_summary_reports.py \
  --iteration-name iteration3 \
  --logs-dir logs/run_evaluation/iteration3 \
  --samples data/samples/swe_bench_live_10_samples.json

bench_env/bin/python scripts/reports/aggregate_multi_agent_results.py \
  --iteration-name iteration3 \
  --logs-dir logs/run_evaluation/iteration3 \
  --samples data/samples/swe_bench_live_10_samples.json \
  --output eval_results/swebench/iteration3_aggregate_report.json

bench_env/bin/python scripts/reports/comprehensive_metrics.py \
  --aggregate-report eval_results/swebench/iteration3_aggregate_report.json \
  --ground-truth data/samples/swe_bench_live_10_samples.json \
  --logs-dir logs/run_evaluation/iteration3 \
  --output eval_results/swebench/iteration3_comprehensive_metrics.json
```

---

## 8. Results Summary

**Status: COMPLETED** — All 70 evaluations ran, 11 completed, metrics generated.

| Agent | Completed | Patch Apply | F2P Prog | Content Sim | Fix Rate |
|-------|----------:|------------:|---------:|------------:|---------:|
| baseline_no_enhancement | 1 | 10% | 100% | 68.5% | 0% |
| baseline_simple_solver | 0 | 0% | — | — | 0% |
| enhanced_live_swe_agent | 2 | 20% | 0% | 11.7% | 0% |
| enhanced_mini_swe_agent | 2 | 20% | 50% | 31.6% | 0% |
| enhanced_openhands | 2 | 20% | 50% | 31.6% | 0% |
| enhanced_simple_enhancer | 2 | 20% | 50% | 31.6% | 0% |
| enhanced_trae | 2 | 20% | 50% | 31.6% | 0% |

**Full analysis:** See [ITERATION3_FINAL_ANALYSIS.md](../eval_results/swebench/ITERATION3_FINAL_ANALYSIS.md)
