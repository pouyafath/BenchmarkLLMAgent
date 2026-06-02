# Threats To Validity

Date: 2026-06-02

Scope: current TSE-paper candidate built around the Paul plus BenchmarkLLMAgent pipeline and the accepted pilot40 results.

## Internal Validity

| Threat | Evidence in repo | Current mitigation | Residual risk |
|---|---|---|---|
| Live pipeline incompleteness | Stage 1 remains active; Stage 2 and Stage 3 remain active upstream; no newer frozen Stage 3 export exists yet | paper-safe claims can be restricted to the frozen pilot40 slice | high if authors blur live status and frozen benchmark evidence |
| Mutable-workspace drift | handoff docs explicitly warn against using `workspace/organize.jsonl` and `playground/*/result.json` downstream | immutable stage exports were introduced and are now the authoritative boundary | medium; future contributors can still accidentally cite mutable state |
| Organize-only scoping bug | Developer 03 docs report that organize-only mode reads `workspace/stage2_2026_full/setup.jsonl` instead of trusting the scoped dataset | workaround rebuilds `setup.jsonl` before scoped runs | medium; this is a real operational hazard for future batches |
| Node2 host-level failures and retries | Node2 required host cleanup, retry subsets, and invalid-patch reruns | shared-code fixes landed and infra failures were isolated | medium; upstream operational stability is improved but not irrelevant |
| Patch-induced and infra-induced retries | invalid `24`-row rerun and broader retry queues show setup results can change after fixes | rerun outcomes were documented separately | medium; live Stage 1 counts are not final |
| Single OpenHands enhancement failure | `Azure__azure-cli-32339` remained unchanged due likely runtime/tooling outlier | comparison kept identical text for that instance in baseline and enhanced conditions | low to medium; one failure does not invalidate the run, but it weakens claims about perfect robustness |
| Solver non-determinism | comparability audit observed different solver patches across runs even when final pass/fail patterns matched | audit showed the main 9-to-1 discrepancy was criteria drift, not solver drift | medium; non-determinism still limits exact reproducibility of issue-level patches |

## Construct Validity

| Threat | Evidence in repo | Current mitigation | Residual risk |
|---|---|---|---|
| Resolved semantics differ from standard SWE-bench semantics | pilot40 workflow doc and comparability audit both show raw evaluator semantics were wrong for this branch | shared re-eval library standardizes corrected logic | medium; reviewers may challenge custom semantics if not carefully justified |
| `FAIL_TO_PASS` ambiguity | project contains both dataset-level `FAIL_TO_PASS_count` metadata and Stage 3 observed `stage3_fail_to_pass_observed_count` | this paper package explicitly separates them | medium; easy to conflate without careful terminology |
| Heuristic F2P/P2P derivation in Stage 0.5 | `DATA_COLLECTION.md` states early F2P/P2P counts come from offline diff parsing, not executable Docker validation | executable validation is later introduced at Stage 3 | medium; early filtering still depends on heuristic test-structure extraction |
| Enhancement quality measured indirectly through solving | current accepted empirical outcome is solver success delta, not human enhancement grading | gained-case and failure analyses add qualitative interpretation | medium; solving is a useful proxy but not a complete construct of issue quality |
| "Real agent" versus proxy classification | some agents are native, some are local framework-built, some are proxy simulations | `REAL_AGENT_AUDIT_2026-06-01.md` explicitly separates the classes | low to medium; claims remain vulnerable if categories are collapsed in prose |

## External Validity

| Threat | Evidence in repo | Current mitigation | Residual risk |
|---|---|---|---|
| Pilot40 is small | accepted current slice is `40` instances | paper can frame results as pilot evidence | high for broad empirical generalization |
| Pilot40 issue mix is limited | `20 bug / 17 feature / 3 refactoring` | report per-type breakdowns, keep conclusions modest | medium to high, especially for refactoring |
| Current same-slice agent coverage is narrow | OpenHands accepted; OpenClaw unavailable; broader same-slice native comparisons missing | real-agent audit defines the boundary honestly | high if paper is framed as a broad native-agent ranking |
| Current primary accepted comparison uses one main solver path | strongest accepted comparison uses mini-SWE-agent with `gpt-5.4-mini` | gpt-oss solver variant can be included as secondary sensitivity evidence | medium |
| Dataset is Python-only and Paul-compatible | Stage 0 and 0.5 filters restrict repo language and operational viability | paper can state scope clearly | medium |
| Viability filter excludes externally dependent repos | `335` rows removed as infra-incompatible in the Paul viability step | document filter rationale explicitly | medium; the benchmark slice is operationally biased toward Paul-compatible cases |

## Conclusion Validity

| Threat | Evidence in repo | Current mitigation | Residual risk |
|---|---|---|---|
| No statistical testing on the accepted pilot40 study | current artifacts report counts, deltas, and case IDs, not inferential tests | a future draft can add paired tests and confidence intervals where meaningful | high |
| Cross-dataset comparisons are only descriptive | OpenHands report itself warns that the 20-issue native CLI benchmark uses a different dataset | paper can demote cross-dataset comparisons to contextual background | medium |
| gpt-oss zero-result run can be over-interpreted | `0/40` baseline and enhanced on the alternate solver path | treat it as solver-path sensitivity, not as enhancer evidence | medium |
| Future larger exports could change the narrative | active Stage 2 and Stage 3 work may create new validated slices | freeze the paper scope explicitly around the current pilot40 slice unless a new export is intentionally adopted | high until scope is frozen |

## Most Important Threats To State Explicitly In The Paper

If space is limited, the paper must still state these five:

1. The current strongest evidence is a frozen `40`-instance pilot slice, not the completed `2,900`-instance live pipeline.
2. P2P-gated corrected re-evaluation is mandatory for this branch and differs from raw evaluator semantics.
3. The benchmark currently has asymmetric native-agent availability on the new slice.
4. Upstream operational state is live and mutable, which is why immutable exports are part of the contribution.
5. Statistical power is low and conclusions must remain pilot-scale.

