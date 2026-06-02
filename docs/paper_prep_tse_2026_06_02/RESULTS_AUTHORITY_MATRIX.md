# Results Authority Matrix

Date: 2026-06-02

Status labels:

- `accepted`: safe to use in the paper now
- `provisional`: operationally useful, not stable enough for main paper claims
- `superseded`: should not be used as the current result

## A. Accepted Results

| Result | Value | Source | Status | Caveat |
|---|---:|---|---|---|
| Post-cutoff raw candidate pool | `7,714` | `BenchmarkLLMAgent/docs/guides/POUYA_DATASET_2026_WORKFLOW.md`; `BenchmarkLLMAgent/data/samples/pouya_dataset_2026/raw_candidates.jsonl` | accepted | lineage count, not downstream benchmark size |
| P2P-positive classified dataset | `3,285` | `BenchmarkLLMAgent/docs/guides/POUYA_DATASET_2026_WORKFLOW.md`; `BenchmarkLLMAgent/data/samples/pouya_dataset_2026_stage1/dataset.jsonl` | accepted | includes issue-type classification and P2P filter |
| Operational export copied into Paul | `3,229` | `BenchmarkLLMAgent/docs/guides/POUYA_DATASET_2026_WORKFLOW.md`; `paul-RepoLaunch/data/stage2_2026_full.jsonl` | accepted | provenance of the `56` dropped rows is under-documented |
| Infra-compatible Paul subset | `2,950` | `BenchmarkLLMAgent/docs/guides/POUYA_DATASET_2026_WORKFLOW.md`; `BenchmarkLLMAgent/data/samples/pouya_dataset_2026_stage1/viable_for_paul.jsonl` | accepted | Paul viability filter, not benchmark completion |
| Live operational dataset | `2,900` | `BenchmarkLLMAgent/docs/guides/POUYA_DATASET_2026_WORKFLOW.md`; `paul-RepoLaunch/data/stage2_2026_viable.jsonl` | accepted | live upstream run still incomplete |
| Pilot Stage 1 setup-success export | `48` | `/home/22pf2/paul-RepoLaunch/runs/stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/stage1_setup_success48.jsonl` | accepted | pilot funnel only |
| Pilot Stage 2 organize-success export | `41` | `/home/22pf2/paul-RepoLaunch/runs/stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/stage2_organize_success41.jsonl` | accepted | `7` pilot rows remained pending at Stage 2 |
| Pilot Stage 3 completed export | `40` | `/home/22pf2/paul-RepoLaunch/runs/stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/stage3_validation_completed40.jsonl` | accepted | current authoritative downstream dataset |
| Pilot Stage 3 pending export | `1` | `/home/22pf2/paul-RepoLaunch/runs/stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/stage3_validation_pending1.jsonl` | accepted | pending ID: `Diaoul__subliminal-1330` |
| Pilot40 issue-type mix | `20 bug / 17 feature / 3 refactoring` | pilot export README/HANDOFF and all Stage 6 summaries | accepted | small refactoring count |
| Stage 3 dataset-level F2P-positive rows | `28/40` | `stage3_validation_completed40.jsonl` field `FAIL_TO_PASS_count` | accepted | metadata only in this branch |
| Stage 3 validation-observed F2P-positive rows | `11/40` | `stage3_validation_completed40.jsonl` field `stage3_fail_to_pass_observed_count` | accepted | not the same concept as dataset-level F2P metadata |
| `llm_append_analysis` with `gpt-5.4-mini` solver: baseline | `9/40` | `runs/paul_pilot40_stage4_stage6_20260526/stage6_report/summary.json` | accepted | accepted after P2P-gated re-eval |
| `llm_append_analysis` with `gpt-5.4-mini` solver: enhanced | `8/40` | same as above | accepted | lost `SWE-agent__mini-swe-agent-235` |
| `llm_append_analysis` truly enhanced coverage | `19/40` | same as above | accepted | `21/40` unchanged |
| `openhands` with `gpt-5.4-mini` solver: baseline | `9/40` | `runs/paul_pilot40_openhands_20260601/stage6_report/summary.json` | accepted | accepted after shared re-eval |
| `openhands` with `gpt-5.4-mini` solver: enhanced | `10/40` | same as above | accepted | gained `Diaoul__subliminal-1328` |
| `openhands` truly enhanced coverage | `39/40` | same as above | accepted | one unchanged runtime outlier |
| `llm_append_analysis` with `gpt-oss:120b` solver: baseline | `0/40` | `runs/paul_pilot40_gptoss_solver_20260527/stage6_report/summary.json` | accepted | same Stage 4 artifacts as 2026-05-26 run |
| `llm_append_analysis` with `gpt-oss:120b` solver: enhanced | `0/40` | same as above | accepted | best interpreted as solver-path sensitivity |

## B. Provisional Operational Counts

| Result | Value | Source | Status | Caveat |
|---|---:|---|---|---|
| Combined live Stage 1 setup success on 2026-05-29 17:24 UTC | `356/2900` | `paul-RepoLaunch/runs/project_status_snapshot_20260529_1724_utc.json` | provisional | historical live snapshot, not final |
| Node1 live setup success on 2026-06-01 15:16 UTC | `387` | `paul-RepoLaunch/runs/project_status_snapshot_20260601_1519_utc.json` | provisional | live upstream count |
| Node2 live setup success on 2026-06-01 15:16 UTC | `454` | same as above | provisional | live upstream count |
| Node1 Stage 2 subset checkpoint on 2026-06-02 | `99 true / 3 false / 252 pending` | `paul-RepoLaunch/docs/STAGE_TASK_OWNER_MATRIX_2026-06-02.md` | provisional | organize run still active |
| Total Node1 `organize_completed=true` on 2026-06-02 | `136` | same as above | provisional | mutable live state |
| Current Node1 Stage 3 validation batch | `43/123` completed | same as above | provisional | no new export frozen yet |
| Current Node1 Stage 3 rows with `FAIL_TO_PASS > 0` | `7` | same as above | provisional | in-flight batch only |
| Node2 retry queue checkpoint updated 2026-06-02 | `205 success / 101 failed / 640 missing` | `paul-RepoLaunch/docs/STAGE1_NODE2_RETRY_STATUS_2026-06-01.md` updated section | provisional | operational queue status, not benchmark metric |
| Isolated invalid-patch rerun outcome | `6 success / 18 failed / 0 pending` | same status note | provisional | operational recovery result, not benchmark result |

## C. Superseded Results Or Interpretations

| Result / interpretation | Value | Source | Status | Why superseded |
|---|---:|---|---|---|
| Raw OpenHands baseline before corrected re-eval | `1/40` | pre-audit OpenHands raw evaluation state | superseded | corrected to `9/40` by mandatory P2P-gated re-evaluation |
| Raw OpenHands enhanced before corrected re-eval | `1/40` | same context | superseded | corrected to `10/40` by mandatory P2P-gated re-evaluation |
| Downstream handoff filtered by `FAIL_TO_PASS > 0` | older 11-row assumption | older seed path `paul_stage4_stage6_from_stage3pilot_20260526/` | superseded | current branch uses full `40`-row Stage 3 completed export with P2P gating |
| Direct downstream use of mutable `workspace/organize.jsonl` | n/a | live workspace | superseded | immutable stage exports are the required handoff boundary |

## D. Practical Paper Rule

Use in the main paper:

- Section A results

Use only in Methods / discussion / future work with explicit live-state labels:

- Section B results

Do not use as the current accepted comparison:

- Section C results
