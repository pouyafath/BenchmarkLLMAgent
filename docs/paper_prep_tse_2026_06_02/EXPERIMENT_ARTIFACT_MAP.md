# Experiment Artifact Map

Date: 2026-06-02

## Authority Rule

For paper claims, prefer immutable exports and completed run directories over mutable workspace files.

As of this review:

- exactly one frozen `stage3_validation_completed*.jsonl` exists under `/home/22pf2/paul-RepoLaunch/runs/`
- that file is:
  - `/home/22pf2/paul-RepoLaunch/runs/stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/stage3_validation_completed40.jsonl`

## Stage-by-stage Map

| Stage | Purpose | Input | Transformation | Authoritative artifacts | Mutable? | Paper use |
|---|---|---|---|---|---|---|
| Stage 0 | recent live issue/task collection | filtered repo universe and linked PR/issue candidates | crawl repos, filter repos, collect tasks, apply issue-date cutoff | `/home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026/raw_candidates.jsonl`; `/home/22pf2/BenchmarkLLMAgent/docs/DATA_COLLECTION.md` | no live runtime mutation; treat as frozen lineage input | Methods |
| Stage 0.5 | classification plus Paul viability | Stage 0 candidates | `PASS_TO_PASS > 0` retention, issue-type classification, infra pruning, operational export alignment | `/home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026_stage1/dataset.jsonl`; `/home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026_stage1/viable_for_paul.jsonl`; `/home/22pf2/paul-RepoLaunch/data/stage2_2026_full.jsonl`; `/home/22pf2/paul-RepoLaunch/data/stage2_2026_viable.jsonl` | no live runtime mutation; treat as frozen research inputs | Methods |
| Stage 1 | RepoLaunch setup | `stage2_2026_viable.jsonl` | Docker build and environment setup via Paul-localized RepoLaunch | live: `/home/22pf2/paul-RepoLaunch/workspace/stage2_2026_full/playground/*/result.json`; pilot export: `/home/22pf2/paul-RepoLaunch/runs/stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/stage1_setup_success48.jsonl` | live workspace mutable; pilot export immutable | Methods and pilot funnel reporting |
| Stage 2 | organize/test discovery | Stage 1 setup-success rows | collect real organize results and test commands | live: `/home/22pf2/paul-RepoLaunch/workspace/stage2_2026_full/organize.jsonl`; pilot exports: `stage2_organize_success41.jsonl`, `stage2_organize_pending7.jsonl` | live mutable; pilot export immutable | Methods and pilot funnel reporting |
| Stage 3 | gold-patch validation | Stage 2 organize-success rows | validation against gold patch, record pre/post test status | live logs: `/home/22pf2/paul-RepoLaunch/workspace/stage2_2026_full/validation_logs_*`; pilot exports: `stage3_validation_completed40.jsonl`, `stage3_validation_pending1.jsonl`; metadata: `HANDOFF.json`, `README.md` | logs mutable-ish runtime output; export immutable | Methods and benchmark input definition |
| Stage 4 | issue enhancement | frozen Stage 3 completed export | enhancer rewrites or restructures `problem_statement`; preserve baseline copy | per-run `stage4_enhanced/`; especially: `baseline.jsonl`, `llm_append_analysis.jsonl`, `openhands.jsonl`, `stage4_summary.json`, `enhancement_failures.json` | immutable per run | Evaluation |
| Stage 5 | solver plus evaluator | Stage 4 baseline and enhanced datasets | run mini-SWE-agent; run evaluator; then pilot40 re-eval if applicable | per-run `stage5_solver_eval/solver_*`, `eval_*`, `status.json`, corrected `report.json`, corrected `eval_results.json` | immutable per run after completion | Evaluation |
| Stage 6 | comparison and reporting | Stage 5 corrected outputs plus Stage 4 metadata | summarize resolved counts, deltas, gained/lost IDs, per-type breakdowns | `stage6_report/REPORT.md`, `stage6_report/summary.json`, plus `COMPARABILITY_AUDIT.md`, `GAINED_CASE_ANALYSIS.md`, `FAILURE_CLASSIFICATION.md` where applicable | immutable per run | Results and Discussion |

## Paper-safe Run Directories

### Frozen upstream handoff

- `/home/22pf2/paul-RepoLaunch/runs/stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/`

Use:

- `README.md`
- `HANDOFF.json`
- `stage1_setup_success48.jsonl`
- `stage2_organize_success41.jsonl`
- `stage2_organize_pending7.jsonl`
- `stage3_validation_completed40.jsonl`
- `stage3_validation_pending1.jsonl`

### Accepted Stage 4-6 run directories

- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_stage4_stage6_20260526/`
- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_gptoss_solver_20260527/`
- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_openhands_20260601/`

### Accepted methodology and audit docs

- `/home/22pf2/BenchmarkLLMAgent/docs/guides/PILOT40_EVALUATION_WORKFLOW.md`
- `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_openhands_20260601/COMPARABILITY_AUDIT.md`
- `/home/22pf2/BenchmarkLLMAgent/docs/analysis/REAL_AGENT_AUDIT_2026-06-01.md`

## Operational Artifacts That Need Explicit Caution Labels

These are useful for project-state reporting but should not be treated as frozen benchmark evidence:

- `/home/22pf2/paul-RepoLaunch/workspace/stage2_2026_full/`
- `/home/22pf2/paul-RepoLaunch/runs/project_status_snapshot_20260529_1724_utc.json`
- `/home/22pf2/paul-RepoLaunch/runs/project_status_snapshot_20260601_0918_utc.json`
- `/home/22pf2/paul-RepoLaunch/runs/project_status_snapshot_20260601_1519_utc.json`
- `/home/22pf2/paul-RepoLaunch/docs/STAGE_TASK_OWNER_MATRIX_2026-06-02.md`
- `/home/22pf2/paul-RepoLaunch/docs/AGENT_ASSIGNMENTS_2026-06-01.md`
- `/home/22pf2/paul-RepoLaunch/docs/STAGE1_NODE2_RETRY_STATUS_2026-06-01.md`

Recommended paper handling:

- use them to describe operational status and future work
- do not convert them into stable benchmark totals

## Superseded Or Non-authoritative Paths

Do not use these as primary evidence for the paper:

- mutable `workspace/organize.jsonl` as a downstream benchmark input
- mutable `playground/*/result.json` as a downstream benchmark input
- `/home/22pf2/BenchmarkLLMAgent/runs/paul_stage4_stage6_from_stage3pilot_20260526/`
  - older `11`-row seed built on the wrong `FAIL_TO_PASS > 0` assumption
- raw pre-reeval pilot40 resolution counts where a corrected re-eval exists

