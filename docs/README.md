# BenchmarkLLMAgent Documentation

Project docs are organized around the **current canonical workflow**.

## Current Stage 2 Full Track (2026-05-24, running)

- Dataset: 3,285 total collected -> 3,229 passed basic filters -> 2,900 classified as viable (Bug: 1896, Feature: 855, Refactoring: 149)
- Workflow: Enhancer+Solver Agentic Workflow (7 Stages)
  - Stage 0: Dataset Collection & Filtering (Completed, 3,229 issues)
  - Stage 0.5: Classification & Viability (Completed, 2,900 issues)
  - Stage 1: RepoLaunch Setup (In Progress, running locally with `paul-RepoLaunch`)
  - Stage 2: RepoLaunch Organize (Waiting)
  - Stage 3: Gold Patch Validation (Not Started)
  - Stage 4: Enhancement Agents (Not Started)
  - Stage 5: Solver Evaluation (Not Started)
  - Stage 6: Final Comparison (Not Started)
- Configuration: Using local Ollama with 4 workers and 900s request timeouts to ensure GPU stability during heavy setup loads.

## Historical Pouya-20 Track (2026-05-11)

- Dataset: `runs/pouya_final20b_20260505_050130/validated_instances.jsonl` (20 instances, all `docker_image` updated)
- Baseline: `runs/pouya_solver20_20260505_063614/` (mini-SWE-agent + gpt-5.4-mini, 3/20 resolved)
- **Authoritative v2 comparison** (clean, all dlt-hub images working): `runs/pouya20_solver_comparison_v2/ANALYSIS.md`
- **Second-solver check** (SWE-agent as solver): `runs/pouya20_sweagent_solver_comparison_20260511/ANALYSIS.md`
- **Third-solver check** (Aider as solver): `runs/pouya20_aider_solver_comparison_20260511/ANALYSIS.md`
- **Comprehensive 3-solver x 7-condition report**: `runs/pouya20_comprehensive_solver_enhancer_report_20260511/REPORT.md`
- **Qualitative changed-behavior analysis**: `docs/analysis/POUYA20_QUALITATIVE_ERROR_ANALYSIS_2026-05-11.md`
- **Fresh raw LLM enhancer follow-up**: `docs/analysis/POUYA20_RAW_LLM_ENHANCER_2026-05-11.md`
- Original comparison: `runs/pouya20_native_solver_comparison_fixed/ANALYSIS.md`
- Main workflow: `scripts/workflows/run_pouya20_gpt54mini.py`
- Paul/RepoLaunch guide: `archive/PAUL_REPOLAUNCH_GUIDE.md`

**Final results (v2):** Baseline 3/20 | aider 3/20 | trae 2/20 | openhands 2/20 | mini_swe_agent 2/20 | swe_agent 1/20. Enhancement does not improve solver success rate.

**SWE-agent solver check (2026-05-11):** Baseline 3/20 | aider 3/20 | trae 3/20 | openhands 2/20 | mini_swe_agent 1/20 | swe_agent 1/20. This second solver also shows no enhancement-driven resolved-score gain; `amazon-science__chronos-forecasting-407` was conservatively counted unresolved after repeated evaluator hangs.

**Aider solver check (2026-05-11):** Baseline 2/20 | aider 3/20 | trae 2/20 | openhands 1/20 | mini_swe_agent 2/20 | swe_agent 1/20. This is the first solver where one enhancer improves resolved count (`aider`, +1 via `aws-powertools__powertools-lambda-python-7026`), but the effect is narrow and not consistent across enhancers.

**Comprehensive cross-solver result:** Across 21 cells (3 solvers x baseline plus raw LLM and five native enhanced conditions), only `aider` enhancement with Aider solver improves over that solver's baseline. Treat this as a narrow positive case, not general support for the enhancer hypothesis.

**Raw LLM enhancer follow-up:** Fresh raw LLM enhancements were regenerated for all 20 issues using `gpt-5.4-mini` and `append_analysis`; the old raw artifacts are not used. Raw LLM matches mini-SWE-agent and SWE-agent baselines at 3/20, and underperforms Aider baseline at 1/20.

**Key confound identified:** All 20 instances are `detailed` quality_bucket. See `archive/POUYA20_EXPERIMENT.md` § "Planned Next Experiment" for the quality-stratified follow-up design using vague/moderate issues from the 282 dataset, and the refactoring/feature dataset extension plan.

**Typed sub-datasets collected (2026-05-11):** The 282-issue base dataset is now split into three typed sub-datasets by issue type (Bug/Feature/Refactoring) using GitHub labels + title text classification. See `archive/DATA_COLLECTION.md` for full breakdown. Summary:
- Bug: **216 issues** (`data/samples/pouya_dataset_2026_bug/dataset.jsonl`) — F2P>0, P2P>0, Docker-ready
- Feature: **58 issues** (`data/samples/pouya_dataset_2026_feature/dataset.jsonl`) — F2P>0, P2P>0, Docker-ready; 84% vague/moderate
- Refactoring (validated): **8 issues** (`data/samples/pouya_dataset_2026_refactoring/dataset.jsonl`) — F2P>0, P2P>0
- Refactoring candidates: **20 issues** (`data/samples/pouya_dataset_2026_refactoring_candidates/candidates.jsonl`) — need Docker validation with F2P≥0, P2P>0

The corrected 2026-05-09 Pouya-5 validation confirmed all five native enhancers returned real native enhancements on 5/5 issues each. `swe_agent` now accepts trajectory content only for benchmark parsing, rejects timeout-contaminated weak bodies, scans multiple trajectory schemas, and preserves valid trajectory output when the CLI times out after writing the enhancement.

The 2026-05-09 Pouya-5 solver comparison found no resolved-score improvement before the full 20-issue rerun. All five enhancers completed the enhancer-solver-evaluator loop with 5/5 solver predictions; `swe_agent` has one empty patch.

## Historical Verified-10 Track

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
- `archive/iterations/`: historical snapshots and phase notes.
- `archive/investigation/`: historical root-cause investigations.
- `archive/`: deprecated/superseded docs.

## Start Here

1. `guides/POUYA_DATASET_2026_WORKFLOW.md`
2. `paul-RepoLaunch/README.md`
3. `paul-RepoLaunch/docs/server_8gpu_setup.md`
4. `analysis/POUYA20_QUALITATIVE_ERROR_ANALYSIS_2026-05-11.md`
5. `archive/POUYA20_EXPERIMENT.md`
6. `archive/WORKFLOW_SCRIPT_REFERENCE.md`
7. `archive/API_KEY_HANDLING.md`

## Notes

- Older SWE-bench-Live and Verified-10 docs are kept in `archive/` for historical context.
- For Pouya-20 operational commands, trust `archive/POUYA20_EXPERIMENT.md` and `archive/WORKFLOW_SCRIPT_REFERENCE.md`.
