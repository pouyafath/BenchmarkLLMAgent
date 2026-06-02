# TSE Paper Readiness Assessment

Date: 2026-06-02

Scope: `/home/22pf2/paul-RepoLaunch` plus `/home/22pf2/BenchmarkLLMAgent`

## Bottom Line

Readiness judgment: `draftable with caveats`

Go / no-go:

- Go for a full paper outline, Methods draft, artifact-backed Results draft, and a conservative Discussion draft now.
- No-go for a submission-ready TSE draft if it claims a mature large-scale benchmark comparison, stable full-pipeline completion, or broad native-agent coverage on the current branch.

Why:

1. The project already has a coherent end-to-end architecture, a frozen pilot dataset handoff, accepted pilot40 downstream runs, and a corrected evaluation methodology.
2. The strongest current evidence is still a 40-instance validated slice, not the full 2,900-instance live pipeline.
3. The accepted current-dataset native-agent evidence is narrow: OpenHands is real and accepted; OpenClaw is unavailable; the main same-slice comparison is OpenHands versus one local LLM-based enhancer workflow.

## Authority Rules For This Paper

Paper-safe evidence should come from:

- immutable pilot stage exports under `/home/22pf2/paul-RepoLaunch/runs/stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/`
- accepted Stage 6 reports and summaries under:
  - `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_stage4_stage6_20260526/`
  - `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_gptoss_solver_20260527/`
  - `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_openhands_20260601/`
- methodology and comparability docs:
  - `/home/22pf2/BenchmarkLLMAgent/docs/guides/PILOT40_EVALUATION_WORKFLOW.md`
  - `/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_openhands_20260601/COMPARABILITY_AUDIT.md`
- real-agent scope boundary:
  - `/home/22pf2/BenchmarkLLMAgent/docs/analysis/REAL_AGENT_AUDIT_2026-06-01.md`

Operational-only evidence should stay clearly labeled as live or provisional:

- `workspace/stage2_2026_full/`
- live `playground/<instance_id>/result.json`
- owner matrices, handoff notes, and machine snapshots
- active Stage 2 / Stage 3 / Node2 retry counts

Do not use as current authoritative paper evidence:

- the raw OpenHands `1/40 -> 1/40` pre-reeval reading
- the older 11-row downstream seed that was built around `FAIL_TO_PASS > 0`
- direct downstream counting from mutable `workspace/organize.jsonl` or `playground/*/result.json`

## Terminology Correction Needed In The Paper

The repos repeatedly call this a "7-stage" workflow while also explicitly listing `Stage 0`, `Stage 0.5`, and `Stage 1-6`. That is eight labeled checkpoints if counted literally.

For the paper, use one of these two consistent formulations:

- "a seven-stage workflow with a Stage 0.5 pre-processing substage"
- "an eight-label pipeline from Stage 0 through Stage 6, with Stage 0.5 separating collection from operational readiness"

Do not mix the two phrasings inside the paper.

## 1. What The Paper Is Actually About

### One-paragraph version

This paper is about an end-to-end benchmark construction and evaluation workflow that starts from recent live GitHub issue/PR pairs, converts them into a Paul/RepoLaunch-compatible validated benchmark slice, and then measures whether issue-enhancement agents improve downstream issue-solving success. The current strongest evidence is a frozen 40-instance pilot derived from a larger 2,900-instance live pipeline, where the benchmark required a project-specific P2P-gated re-evaluation procedure rather than raw SWE-bench resolution semantics, and where a real OpenHands integration improved solver success from `9/40` to `10/40` while a local `llm_append_analysis` enhancer decreased it from `9/40` to `8/40`.

### One-page version

The paper should be framed as a systems-and-evaluation paper, not as a pure leaderboard paper. The core system contribution is the operational bridge between live issue collection and downstream solver benchmarking. Upstream, the project inherits task collection from SWE-bench-Live-style assets, then adds a P2P-oriented classification and viability pipeline so that issues can be executed inside a local RepoLaunch environment. Midstream, Paul localizes RepoLaunch by replacing cloud dependencies with local infrastructure and turns mutable runtime state into explicit stage-bounded artifacts. Downstream, BenchmarkLLMAgent consumes a frozen Stage 3 export, applies enhancement agents, runs solver baselines and enhanced conditions, and produces comparative reports.

The paper should not pretend the full 2,900-instance run has already finished end to end. That is not true. The full run is still operationally active upstream. What is finished is a frozen pilot path: `48` setup-success pilot rows, `41` organize-success rows, and `40` Stage 3 validation-completed rows. That pilot40 slice is the current benchmark-ready dataset for Stage 4-6 claims.

The most publishable methodological point is that the branch being evaluated is not using standard SWE-bench resolved semantics as-is. The downstream slice is P2P-gated: `PASS_TO_PASS > 0` is the gate, `FAIL_TO_PASS` is metadata only, and raw evaluator output can produce false negatives because of both criterion drift and test-name parsing drift. The project therefore had to standardize a corrected re-evaluation procedure that reads `status.json`, normalizes parsed test names, and marks an instance resolved when all observed P2P tests pass and at least one P2P test is actually observed. This is not a cosmetic implementation detail; it changes the accepted pilot40 baseline from `1/40` back to `9/40` in the OpenHands run and is necessary for cross-run comparability.

The main current empirical result is intentionally modest. On the same 40-row validated slice, OpenHands as a real native enhancer increased solver success from `9/40` to `10/40`, gaining one bug instance: `Diaoul__subliminal-1328`. On the same slice, `llm_append_analysis` with the same primary solver decreased performance from `9/40` to `8/40`. A gpt-oss solver variant using reused Stage 4 artifacts yielded `0/40` in both baseline and enhanced conditions, which is better interpreted as solver-path sensitivity than as evidence about enhancement value alone.

The paper should present this as a promising pilot with a defensible methodological contribution, not as a mature large-scale comparative study. The current evidence is enough to argue that: the benchmark pipeline exists; frozen stage boundaries matter; P2P-gated evaluation must be corrected explicitly; and one real native enhancer can produce a positive downstream effect on this validated slice. The current evidence is not enough to argue that native issue enhancement generally helps, that OpenHands broadly dominates alternatives, or that the full live pipeline has already been benchmarked end to end at scale.

### Section-outline form

Recommended section logic:

1. Introduction and motivation for evaluating issue enhancement through downstream solving.
2. Background: SWE-bench-style evaluation versus this branch's P2P-gated semantics.
3. System and data pipeline: Stage 0 through Stage 6, with immutable handoff boundaries.
4. Experimental design: pilot40 slice, enhancer conditions, solver conditions, corrected re-evaluation procedure.
5. Results: accepted pilot40 comparisons plus qualitative gained-case analysis.
6. Validity and scope limits: pipeline incompleteness, live-state risks, agent availability asymmetry, small sample size.
7. Conclusion and roadmap: what is evidenced now and what requires the next frozen export.

## 2. Actual System Contributions

### Contributions already evidenced

| Candidate contribution | Evidence status | Conservative claim wording |
|---|---|---|
| Multi-stage live-issue to solver-benchmark pipeline | evidenced on the pilot slice | "We implement and operationalize a staged pipeline from recent GitHub issue collection to downstream solver evaluation." |
| Immutable stage-export boundary between RepoLaunch and downstream benchmarking | evidenced | "We show that downstream benchmarking must consume frozen stage exports rather than mutable workspace state." |
| P2P-gated evaluation correction for this branch | evidenced | "We define and standardize a re-evaluation workflow required for P2P-gated pilot datasets." |
| Solving-as-evaluation for issue enhancement | evidenced on pilot40 | "We evaluate issue enhancement indirectly through solver success before and after enhancement." |
| Real native OpenHands integration in the benchmark | evidenced | "OpenHands is integrated as a real native agent runtime, not a prompt-style proxy." |
| One positive enhancement delta on the validated current slice | evidenced | "OpenHands gains one additional resolved instance on the accepted pilot40 dataset." |

### Contributions only partially evidenced

| Candidate contribution | Current status | Why it is only partial |
|---|---|---|
| Comparison between ready-to-use native agents and framework-built enhancers | partial | The current same-slice accepted comparison is OpenHands versus `llm_append_analysis`; OpenClaw is unavailable and broader same-slice native coverage is missing. |
| Full operational pipeline from 2,900 live issues to large validated benchmark | partial | Stage 1 is live; Stage 2 and Stage 3 are still active upstream; only the pilot export is frozen downstream. |
| Issue-type-sensitive conclusions | partial | Pilot40 has issue-type metadata and per-type breakdowns, but only `40` instances total (`20 bug / 17 feature / 3 refactoring`). |
| Robust solver-sensitivity analysis | partial | There is a gpt-oss solver variant, but it is a single alternate solver path and yielded `0/40` across conditions. |

### Contributions not yet evidenced and should not be claimed

| Over-strong claim | Why it is not supported |
|---|---|
| "Issue enhancement generally improves automated issue solving" | Current evidence is mixed; only one accepted positive delta exists on `40` instances. |
| "OpenHands outperforms other ready-to-use agents on the new benchmark" | Only OpenHands is accepted on the current pilot40 slice; OpenClaw is not integrated. |
| "The full 2,900-instance pipeline has been benchmarked end to end" | False; upstream stages remain live and incomplete. |
| "This work delivers a large-scale statistically supported benchmark comparison already" | False with current sample size and experiment breadth. |

## 3. Current Authoritative Results

### Accepted pilot40 results

Same validated `40`-row dataset:

1. `llm_append_analysis` + mini-SWE-agent solver (`gpt-5.4-mini`):
   - baseline `9/40`
   - enhanced `8/40`
   - delta `-1`
   - truly enhanced `19/40`
2. `openhands` + mini-SWE-agent solver (`gpt-5.4-mini`):
   - baseline `9/40`
   - enhanced `10/40`
   - delta `+1`
   - gained instance: `Diaoul__subliminal-1328`
   - truly enhanced `39/40`
   - one unchanged instance: `Azure__azure-cli-32339`
3. `llm_append_analysis` + mini-SWE-agent solver (`gpt-oss:120b` solver path):
   - baseline `0/40`
   - enhanced `0/40`
   - uses the same Stage 4 artifacts as the 2026-05-26 `llm_append_analysis` run

### Current live pipeline status

As of the 2026-06-02 owner/status docs:

- Node1 Stage 1 remains active.
- Node1 Stage 2 organize remains active under Developer 03.
- Node1 Stage 3 validation remains active under Developer 03.
- Node2 Stage 1 retry work remains active on `docjk-gpu-02`.
- Developer 04 is closed on new Stage 4-6 work until a new frozen Stage 3 export exists.
- No newer `stage3_validation_completed*.jsonl` export exists under `/home/22pf2/paul-RepoLaunch/runs/`.

### Results final enough for a paper now

Paper-safe now:

- dataset lineage through the current `2,900`-row live viable set
- frozen pilot stage counts `48 -> 41 -> 40`
- accepted pilot40 downstream comparisons
- corrected P2P-gated evaluation methodology
- OpenHands real-agent status and OpenClaw exclusion rationale

Still provisional:

- live Stage 1 completion counts
- current Stage 2 organize totals on Node1
- current Stage 3 in-flight validation batch totals
- Node2 retry queue health
- any downstream claims based on future validated exports not yet frozen

## 4. Exact Stage Model

The table below is the paper-facing version of the current stage model.

| Stage | Input | Transformation | Output | Current artifact(s) | Mutable or immutable? | Paper section |
|---|---|---|---|---|---|---|
| Stage 0 | filtered GitHub repos and linked PR/issue candidates | crawl repos, filter repos, collect linked tasks, apply date cutoff | post-cutoff raw candidate pool | `data/samples/pouya_dataset_2026/raw_candidates.jsonl` (`7,714`) | treat as frozen lineage input | Methods |
| Stage 0.5 | Stage 0 candidate pool | keep `PASS_TO_PASS_count > 0`, classify issue type, prune infra-incompatible rows, align with Paul operational export | Paul-ready live dataset | `data/samples/pouya_dataset_2026_stage1/dataset.jsonl` (`3,285`), `paul-RepoLaunch/data/stage2_2026_full.jsonl` (`3,229`), `data/samples/pouya_dataset_2026_stage1/viable_for_paul.jsonl` (`2,950`), `paul-RepoLaunch/data/stage2_2026_viable.jsonl` (`2,900`) | treat as frozen research inputs, not runtime mutable | Methods |
| Stage 1 | `stage2_2026_viable.jsonl` split across Node1 and Node2 | Paul-localized RepoLaunch setup, Docker build, environment verification | per-instance setup state | live `workspace/stage2_2026_full/playground/<id>/result.json`; frozen pilot `stage1_setup_success48.jsonl` | live state is mutable; pilot export is immutable | Methods and Evaluation |
| Stage 2 | Stage 1 setup-success rows | RepoLaunch organize/test command discovery, rebuild command extraction, scoped collect step | organize-success rows plus pending rows | live `workspace/stage2_2026_full/organize.jsonl` and `result.json`; frozen pilot `stage2_organize_success41.jsonl` and `stage2_organize_pending7.jsonl` | live state is mutable; pilot export is immutable | Methods and Evaluation |
| Stage 3 | Stage 2 organize-success rows | gold-patch validation via `evaluation.validation`; record observed pre/post test status | validated completed rows plus pending rows | validation logs; frozen pilot `stage3_validation_completed40.jsonl` and `stage3_validation_pending1.jsonl` | validation logs are mutable-ish runtime outputs; frozen export is immutable | Methods and Evaluation |
| Stage 4 | frozen Stage 3 completed export | issue enhancement agent rewrites or restructures `problem_statement` | baseline and enhanced datasets | per-run `stage4_enhanced/*.jsonl`, failures, summaries | immutable per run | Evaluation |
| Stage 5 | Stage 4 baseline and enhanced datasets | solver runs, raw SWE-bench evaluation, then pilot40 P2P-gated re-evaluation | corrected condition-level eval results | per-run `stage5_solver_eval/`; corrected `report.json` and `eval_results.json` | immutable per run after completion | Evaluation |
| Stage 6 | Stage 5 corrected results plus Stage 4 metadata | comparison, issue-type breakdowns, gained/lost analysis, cross-run references | report and summary | `stage6_report/REPORT.md`, `summary.json`, plus audit docs | immutable per run | Evaluation |

Important Stage 3 note:

- The frozen Stage 3 completed export preserves the dataset-level `PASS_TO_PASS` and `FAIL_TO_PASS` metadata from earlier stages.
- It also records validation-observed fields such as `stage3_fail_to_pass_observed_count`.
- These should not be collapsed into one concept in the paper.

## 5. Evaluation Methodology

### Standard SWE-bench-style semantics

Standard evaluator behavior assumes:

1. an instance is evaluated with expected `FAIL_TO_PASS` and `PASS_TO_PASS` tests
2. resolved status is tied to the standard evaluator's rules
3. exact parsed test names are matched directly

That is the baseline evaluator behavior, but it is not the accepted final semantics for this branch.

### Project-specific P2P-gated semantics

For the current pilot40 branch:

1. dataset gating is based on `PASS_TO_PASS > 0`
2. `FAIL_TO_PASS` is preserved as metadata
3. downstream handoff must not filter the Stage 3 completed export by `FAIL_TO_PASS > 0`

This is an explicit branch rule, not an informal interpretation.

### Corrected pilot40 re-evaluation logic

The standardized pilot40 re-evaluation procedure:

1. reads existing `status.json` files from Stage 5 evaluation outputs
2. does not re-run tests
3. strips `/testbed/` prefixes from parsed test names
4. matches parameterized tests such as `test_x[param]` against base expected names
5. marks an instance resolved if:
   - no matched `PASS_TO_PASS` test fails
   - at least one expected `PASS_TO_PASS` test is actually found and passes
6. records `FAIL_TO_PASS` success/failure as informational output only

### What counts as resolved in this branch

Resolved means:

- `PASS_TO_PASS` clean
- and `PASS_TO_PASS` observed
- regardless of `FAIL_TO_PASS` outcome

### Where FAIL_TO_PASS is metadata versus gate

`FAIL_TO_PASS` is metadata in these places:

- Stage 3 handoff for the current P2P branch
- pilot40 re-evaluation and accepted Stage 6 reporting
- current paper-safe pilot40 comparison claims

`FAIL_TO_PASS` is still relevant as:

- historical dataset metadata
- analysis signal
- part of raw evaluator output

But it is not the final resolved gate for the accepted pilot40 comparison.

## 6. Main Threats To Validity

Short form only here; see `THREATS_TO_VALIDITY.md` for the full version.

Major threats:

1. The full upstream pipeline is still live and incomplete; the current paper-safe downstream evidence is only a 40-instance validated slice.
2. Mutable workspace state can drift away from frozen exports if contributors read `workspace/*` rather than immutable stage artifacts.
3. The P2P-gated corrected evaluator was standardized only after comparability drift was discovered.
4. Agent availability is asymmetric: OpenHands is real and accepted; OpenClaw is unavailable; several other "agents" are proxy-only.
5. The sample size is small and solver non-determinism is real, so broad empirical claims would be underpowered.

## 7. What Still Blocks A TSE-ready Draft

Hard blockers for a submission-quality draft:

1. No larger frozen Stage 3 export yet exists beyond the current 40-row pilot slice.
2. The current same-slice accepted enhancer comparison breadth is narrow.
3. No statistical analysis plan or inferential reporting is in place for the accepted pilot40 study.
4. The provenance of the `3,285 -> 3,229` operational export trim is still under-documented.
5. The paper scope decision is unresolved: pilot40-only paper, methodology paper with pilot evidence, or wait-for-next-export paper.

Non-blockers for drafting but blockers for strong claims:

1. Better figure/table packaging is still needed.
2. Historical tracks need explicit scoping if included.
3. The stage-numbering inconsistency must be normalized in prose.
4. The live operational story should be separated cleanly from frozen benchmark claims.

## Recommended Paper Framing

The most defensible TSE framing right now is:

"an end-to-end benchmark pipeline and evaluation methodology paper with pilot evidence"

not:

- "a finished large-scale benchmark leaderboard paper"
- "a broad native-agent comparison paper on the current dataset"
- "a full-scale proof that issue enhancement generally helps"
