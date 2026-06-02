# Claim-Evidence Traceability

Date: 2026-06-02

Status labels:

- `evidenced`
- `partial`
- `not supported`

## Traceability Matrix

| Claim candidate | Status | Direct evidence | Conservative wording | Do not write |
|---|---|---|---|---|
| The project implements an end-to-end staged workflow from live issue collection to downstream solver evaluation | evidenced | lineage docs, handoff docs, workflow scripts, pilot exports | "We implement a staged workflow and demonstrate it on a frozen pilot slice." | "We fully completed the full-scale workflow end to end." |
| Immutable stage exports are necessary to prevent downstream drift from mutable RepoLaunch state | evidenced | `PROJECT_STATUS_HANDOFF_2026-05-26.md`, export script, pilot export directory | "We introduce immutable stage exports as the downstream handoff boundary." | "Mutable workspace state was safe enough for benchmarking." |
| The current branch requires P2P-gated corrected re-evaluation for comparable pilot40 reporting | evidenced | `PILOT40_EVALUATION_WORKFLOW.md`, `COMPARABILITY_AUDIT.md`, shared re-eval library | "We standardize a corrected re-evaluation procedure for P2P-gated pilot datasets." | "Raw evaluator output was already comparable." |
| OpenHands is a real native agent integration in this benchmark | evidenced | `REAL_AGENT_AUDIT_2026-06-01.md` | "OpenHands is benchmarked through a real native integration." | "OpenHands was simulated by prompting a generic LLM." |
| OpenClaw is part of the accepted current benchmark | not supported | same audit shows unavailable | "OpenClaw is currently unavailable and excluded." | "OpenClaw was benchmarked." |
| OpenHands improves downstream solver success on the accepted pilot40 slice | evidenced | OpenHands Stage 6 report and summary | "On the accepted pilot40 slice, OpenHands improves solver success from `9/40` to `10/40`." | "OpenHands generally improves issue solving." |
| `llm_append_analysis` improves downstream solver success on the accepted pilot40 slice | not supported | Stage 6 summary shows `9/40 -> 8/40` | "On the accepted pilot40 slice, `llm_append_analysis` decreases resolved count by one." | "Local LLM augmentation improved solver success." |
| Solver-facing issue restructuring may matter more than appended analysis in at least one gained case | evidenced for one case only | `GAINED_CASE_ANALYSIS.md` | "In one gained case, restructuring outperformed appended analysis." | "Restructuring is generally superior." |
| The full 2,900-instance live pipeline is already benchmark-complete | not supported | owner/status docs show active Stage 1-3 work | "The full live pipeline is still in progress." | "The benchmark is complete at full scale." |
| The paper already supports broad native-agent ranking on the new dataset | not supported | real-agent audit plus current run set | "Current same-slice native-agent evidence is narrow." | "We compare many real native enhancers on the new dataset." |
| Historical Pouya-20 results can contextualize current findings | partial | README/docs summaries | "Historical runs provide background but are cross-dataset and descriptive only." | "Historical runs are directly comparable to pilot40." |
| The gpt-oss solver variant provides solver-sensitivity evidence | partial | `paul_pilot40_gptoss_solver_20260527` artifacts | "A secondary solver-path run yielded `0/40` in both conditions." | "The gpt-oss run proves enhancement has no value." |
| The benchmark currently separates real agents, local framework-built enhancers, and proxy-only simulations | evidenced | `REAL_AGENT_AUDIT_2026-06-01.md` | "We distinguish native, local, and proxy classes explicitly." | "All listed agents are equally real benchmark integrations." |

