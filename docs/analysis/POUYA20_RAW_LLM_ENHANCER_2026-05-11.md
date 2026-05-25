# Pouya-20 Raw LLM Enhancer Follow-up

Generated: 2026-05-11T17:32:57.125109+00:00

This run uses freshly regenerated `raw_llm` issue enhancements. It does not reuse the older raw/LLM artifacts that were considered invalid.

## Fresh Raw LLM Enhancement

| Field | Value |
| --- | --- |
| Dataset | `runs/pouya_final20b_20260505_050130/validated_instances.jsonl` |
| Raw LLM run | `runs/raw_llm_pouya20_20260511_fresh` |
| Solver-ready dataset | `runs/raw_llm_pouya20_20260511_fresh/datasets/raw_llm.jsonl` |
| Model | `gpt-5.4-mini` |
| Strategy | `append_analysis` |
| Rows | 20/20 |
| Changed issues | 20/20 |
| Failures | 0 |

The generated rows have `agent_id: raw_llm`, `enhancer_type: llm_append`, and `fresh_run: true` in `enhancement_metadata`.

## Solver Results

| Solver | Status | Predictions | Reports | Empty patches | Effective resolved | Delta vs baseline | Resolved IDs | Notes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| mini-SWE-agent | complete_with_known_missing_prediction | 19/20 | 18/19 | 0 | 3/20 | +0 | a2aproject__a2a-python-683, ag2ai__faststream-2495, astropy__astropy-18753 | Missing prediction: PennyLaneAI__pennylane-7474; missing report: amazon-science__chronos-forecasting-407 |
| SWE-agent | complete | 20/20 | 15/20 | 4 | 3/20 | +0 | a2aproject__a2a-python-683, ag2ai__faststream-2495, astropy__astropy-18753 | Eval issue: amazon-science__chronos-forecasting-407: evaluation exited with returncode -15 |
| Aider | complete | 20/20 | 14/20 | 5 | 1/20 | -1 | a2aproject__a2a-python-683 | Eval issue: amazon-science__chronos-forecasting-407: evaluation exited with returncode -15 |

## Interpretation

Raw LLM enhancement does not improve resolved count for any solver in this Pouya-20 run. It matches mini-SWE-agent and SWE-agent baselines at 3/20, and underperforms the Aider baseline at 1/20 versus 2/20.

The common successful instances for mini-SWE-agent and SWE-agent are `a2aproject__a2a-python-683`, `ag2ai__faststream-2495`, and `astropy__astropy-18753`. Aider with raw LLM enhancement only resolves `a2aproject__a2a-python-683`, losing `ag2ai__faststream-2495` compared with Aider baseline.

## Caveats

- `amazon-science__chronos-forecasting-407` was manually terminated during evaluation for SWE-agent and Aider after it entered the known evaluator-hang path; both are counted unresolved.
- `PennyLaneAI__pennylane-7474` still lacks a mini-SWE-agent raw prediction from the earlier mini run and is counted unresolved.
- Empty patches are counted unresolved: SWE-agent has 4; Aider has 5.

## Source Artifacts

- Fresh raw LLM enhancements: `runs/raw_llm_pouya20_20260511_fresh/SUMMARY.json`
- Fresh raw LLM dataset: `runs/raw_llm_pouya20_20260511_fresh/datasets/raw_llm.jsonl`
- mini-SWE-agent raw run: `runs/pouya20_raw_llm_mini_solver_20260511/`
- SWE-agent raw run: `runs/pouya20_raw_llm_sweagent_solver_20260511/`
- Aider raw run: `runs/pouya20_raw_llm_aider_solver_20260511/`
- Machine-readable summary: `runs/pouya20_raw_llm_solver_comparison_20260511/SUMMARY.json`
