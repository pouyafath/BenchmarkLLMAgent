# TSE Paper Outline

Date: 2026-06-02

## Title Candidates

1. From Live GitHub Issues to P2P-Gated Solver Benchmarks: A Multi-Stage Pipeline for Evaluating Issue Enhancement Agents
2. Benchmarking Issue Enhancement Through Downstream Solving: A RepoLaunch-to-Stage6 Pipeline
3. Evaluating Issue Enhancement Agents with a Frozen Stage Pipeline and P2P-Gated Re-evaluation
4. Building and Auditing a Live-Issue Benchmark for Issue Enhancement and Automated Solving

## Abstract Skeleton

Problem:

- Existing issue-enhancement studies often stop at text quality or use loosely coupled evaluation settings.
- End-to-end evaluation from live issue collection to downstream solver impact is operationally hard and methodologically fragile.

Approach:

- Build a staged pipeline spanning recent GitHub issue collection, P2P-oriented dataset preparation, Paul/RepoLaunch setup and organize, gold-patch validation, enhancement, solving, and final comparison.
- Enforce immutable handoff artifacts between upstream operational stages and downstream benchmark stages.
- Standardize a project-specific P2P-gated re-evaluation workflow for pilot40-style runs.

Dataset / setup:

- Current full-run operational dataset: `2,900` viable issues derived from `7,714` post-cutoff raw candidates.
- Current frozen downstream benchmark slice: `40` Stage 3-completed pilot instances from a `48 -> 41 -> 40` pilot funnel.

Main result:

- On the accepted pilot40 slice, OpenHands as a real native enhancer improves downstream solver success from `9/40` to `10/40`.
- A local `llm_append_analysis` enhancer on the same slice decreases solver success from `9/40` to `8/40`.

Methodological result:

- Raw evaluator output is not directly comparable on this branch; corrected P2P-gated re-evaluation is required for accepted reporting.

Scope / limitation:

- The current evidence is a validated pilot slice, not a completed full-scale benchmark.
- Agent coverage on the current slice remains narrow.

## Section-by-section Outline

| Section | Purpose | Main evidence | Cautions |
|---|---|---|---|
| 1. Introduction | Motivate issue enhancement as a downstream-solving problem rather than a text-only problem | pilot40 comparative results; gained case | do not oversell scale |
| 2. Background and Problem Setting | Explain SWE-bench-style evaluation and why this branch needed P2P gating | `PILOT40_EVALUATION_WORKFLOW.md`, `COMPARABILITY_AUDIT.md` | separate standard evaluator semantics from branch semantics |
| 3. System Overview | Present Paul plus BenchmarkLLMAgent as one connected research system | `paul-RepoLaunch/README.md`, `BenchmarkLLMAgent/README.md` | clarify that live runtime and frozen benchmark are different layers |
| 4. Dataset Lineage and Stage Model | Define Stage 0, 0.5, 1-6 with artifacts and handoffs | `PROJECT_STATUS_HANDOFF_2026-05-26.md`, `POUYA_DATASET_2026_WORKFLOW.md`, pilot export README/HANDOFF | fix the 7-stage versus Stage 0.5 naming inconsistency |
| 5. Methods: Upstream Pipeline | Describe collection, classification, viability pruning, Paul-localized RepoLaunch, organize, and validation | `DATA_COLLECTION.md`, `stage1_llm_classify.py`, `filter_infra_incompatible.py`, export script | do not imply the full 2,900 run is complete |
| 6. Methods: Downstream Evaluation | Describe Stage 4-6 runs, enhancer conditions, solver conditions, and re-evaluation | pilot workflow scripts, `PILOT40_EVALUATION_WORKFLOW.md` | emphasize corrected re-eval as mandatory |
| 7. Results | Report accepted pilot40 numbers, per-type breakdowns, enhancement coverage, and solver-sensitivity note | three Stage 6 reports and summaries | keep gpt-oss run separate from primary same-solver comparison |
| 8. Qualitative Analysis | Analyze `Diaoul__subliminal-1328` and the `Azure__azure-cli-32339` OpenHands failure | `GAINED_CASE_ANALYSIS.md`, `FAILURE_CLASSIFICATION.md` | keep causal wording conservative |
| 9. Agent Reality Boundary | Explain real native integrations, proxies, and unavailable agents | `REAL_AGENT_AUDIT_2026-06-01.md` | do not imply OpenClaw was benchmarked |
| 10. Threats to Validity | Address live-state, comparability, availability, scale, and non-determinism risks | `THREATS_TO_VALIDITY.md` | keep this section substantial, not perfunctory |
| 11. Discussion and Future Work | Explain what a next frozen Stage 3 export would unlock | owner matrix, follow-up prompts, open questions | future work must be clearly separated from current evidence |
| 12. Conclusion | Re-state the pipeline and methodology contribution plus pilot result | all accepted artifacts | do not overgeneralize the empirical finding |

## Mapping From Paper Sections To Repo Artifacts

### Core Methods sources

- `/home/22pf2/paul-RepoLaunch/docs/PROJECT_STATUS_HANDOFF_2026-05-26.md`
- `/home/22pf2/BenchmarkLLMAgent/docs/guides/POUYA_DATASET_2026_WORKFLOW.md`
- `/home/22pf2/BenchmarkLLMAgent/docs/DATA_COLLECTION.md`
- `/home/22pf2/paul-RepoLaunch/scripts/export_stage2_2026_pilot_artifacts.py`
- `/home/22pf2/BenchmarkLLMAgent/scripts/workflows/run_pilot40_openhands_enhancer.py`
- `/home/22pf2/BenchmarkLLMAgent/scripts/workflows/pilot40_reeval_lib.py`

### Core Results sources

- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_stage4_stage6_20260526/stage6_report/REPORT.md`
- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_stage4_stage6_20260526/stage6_report/summary.json`
- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_openhands_20260601/stage6_report/REPORT.md`
- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_openhands_20260601/stage6_report/summary.json`
- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_gptoss_solver_20260527/stage6_report/REPORT.md`
- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_gptoss_solver_20260527/stage6_report/summary.json`

### Core validity / boundary sources

- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_openhands_20260601/COMPARABILITY_AUDIT.md`
- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_openhands_20260601/GAINED_CASE_ANALYSIS.md`
- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_openhands_20260601/FAILURE_CLASSIFICATION.md`
- `/home/22pf2/BenchmarkLLMAgent/docs/analysis/REAL_AGENT_AUDIT_2026-06-01.md`

## Recommended Narrative Order

1. Start from the benchmark-construction problem, not from OpenHands.
2. Explain why immutable stage exports were necessary before discussing results.
3. Introduce the P2P-gated evaluation correction before presenting any numeric comparison.
4. Present OpenHands as the first positive result on the accepted current slice, not as universal proof.
5. Keep live full-run status in the system/roadmap story, not in the main results table.

