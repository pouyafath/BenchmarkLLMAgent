# Figure And Table Candidates

Date: 2026-06-02

## Figure Candidates

| Candidate | Message | Evidence source | Readiness |
|---|---|---|---|
| Pipeline overview diagram | show Paul plus BenchmarkLLMAgent as one connected system from Stage 0 to Stage 6 | README files, handoff docs, workflow scripts | ready |
| Dataset lineage funnel | show `7,714 -> 3,285 -> 3,229 -> 2,950 -> 2,900` | `POUYA_DATASET_2026_WORKFLOW.md`, counted JSONL files | ready |
| Pilot funnel diagram | show `48 -> 41 -> 40` | pilot export README/HANDOFF | ready |
| Mutable-versus-frozen boundary diagram | show why immutable stage exports matter | `PROJECT_STATUS_HANDOFF_2026-05-26.md`, export script | ready |
| Pilot40 result comparison bar chart | compare `llm_append_analysis`, `openhands`, and gpt-oss solver variant on the same or reused slice | accepted Stage 6 summaries | ready |
| Comparability audit correction figure | show raw OpenHands `1/40 -> 1/40` versus corrected `9/40 -> 10/40` | `COMPARABILITY_AUDIT.md` | ready |
| Gained-case schematic | show original issue, appended analysis, OpenHands restructuring, and gained resolution | `GAINED_CASE_ANALYSIS.md` | ready |
| Live status roadmap diagram | distinguish frozen pilot evidence from still-running full pipeline | owner matrix and status handoff docs | ready with caution |

## Table Candidates

| Candidate | Message | Evidence source | Readiness |
|---|---|---|---|
| Stage model table | define Stage 0, 0.5, 1-6 with inputs and outputs | artifact map and handoff docs | ready |
| Artifact authority table | distinguish immutable evidence from mutable operational state | artifact map | ready |
| Dataset lineage table | list counts and rationale for each filter step | workflow guide and data counts | ready |
| Pilot40 accepted results table | baseline, enhanced, delta, gained/lost, enhancement coverage | Stage 6 summaries | ready |
| Issue-type breakdown table | bug/feature/refactoring counts and per-type resolved outcomes | Stage 6 summaries | ready |
| Real-agent inventory table | real native, local framework-built, proxy-only, unavailable | `REAL_AGENT_AUDIT_2026-06-01.md` | ready |
| Threats-to-validity table | summarize internal, construct, external, and conclusion risks | `THREATS_TO_VALIDITY.md` | ready |
| Claim-versus-evidence table | separate evidenced, partial, and unsupported contributions | traceability doc | ready |

## Suggested Main-paper Set

If the paper needs a compact figure/table set, start with:

1. Figure: end-to-end pipeline overview
2. Figure: dataset lineage plus pilot funnel
3. Figure: pilot40 accepted-results comparison
4. Table: stage model and artifact authority
5. Table: pilot40 results
6. Table: threats to validity

## Suggested Appendix Set

Good appendix candidates:

1. comparability-audit correction figure
2. gained-case schematic
3. real-agent inventory table
4. claim-versus-evidence traceability table

