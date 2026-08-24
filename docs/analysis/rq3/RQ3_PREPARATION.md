# RQ3 — sample, codebook, and first-pass automated signal (2026-08-24)

RQ3 ("How Are Issue Reports Enhanced?") is the paper's one unstarted RQ: the section is a
written protocol with a preliminary finding, and the corpus was collected but never sampled or
coded. This prepares the machine-preparable half so that only the human open-coding remains.

## What exists now
- [`rq3_coding_sheet.csv`](rq3_coding_sheet.csv) — 90-item stratified sample, ready for two coders
- [`CODEBOOK.md`](CODEBOOK.md) — the coding scheme (7 pattern codes, 5 failure-mode codes)
- [`../../../scripts/analysis/build_rq3_coding_sheet.py`](../../../scripts/analysis/build_rq3_coding_sheet.py) — regenerates both, seeded

## Design
Solver held fixed at **OpenHands**, model at **Qwen3-32B** (the paper's controlled configuration),
enhancer varied over the three agentic conditions. Outcome labels come from the merged stage6
correctness matrices: `helped` = unresolved at baseline then resolved, `hurt` = the reverse,
`unchanged` = neither.

Population (279 evaluable instances per enhancer):

| Enhancer | helped | hurt | unchanged |
|---|---:|---:|---:|
| enh:aider | 30 | 23 | 226 |
| enh:openhands | 24 | 32 | 223 |
| enh:swe_agent | 33 | 28 | 218 |

Sample: **10 per enhancer × outcome cell = 90 items**, seed 42, rows shuffled so coders do not
see the cells grouped. Every cell is fully populated. Across the whole population helped (164)
and hurt (170) are near-identical — the "helps ≈ hurts" balance behind the RQ1 null, now visible
at the level of individual issues rather than aggregate counts.

## First-pass automated signal — the enhancers are *not* interchangeable

Regex cues over all 279 original → enhanced pairs per enhancer (a prior for the coders, not
ground truth):

| Enhancer | median length ratio | restructured | added hypothesis | returned identical |
|---|---:|---:|---:|---:|
| enh:aider | **2.47×** | 36.2% | 25.1% | 7.2% |
| enh:openhands | **0.92×** | 79.2% | 8.2% | **20.4%** |
| enh:swe_agent | 1.18× | **98.6%** | 28.3% | 0.7% |

This **refines the section's current preliminary claim**, which reads: *"Enhancement is a uniform
restructuring into Problem/Reproduction/Expected/Actual sections."* The imposed **template** is
uniform, but the behaviour producing it is not:

- **Aider expands** — 2.5× longer, but restructures least often (36%).
- **OpenHands compresses** — its median output is *shorter than the original*, while
  restructuring 79% of the time. It summarises and templates. It also abstains most (20%
  returned unchanged).
- **SWE-agent restructures almost universally** (99%) at near-neutral length.

### Why this matters for the paper's central thesis
The weekly report records that the OpenHands enhancer raises the reward-model quality score the
most (0.473 → 0.576) yet is null downstream, while Aider *lowers* quality and has the best
(still-null) delta. The length data supplies the mechanism: **OpenHands is compressing detail out
of the report while imposing a clean template.** A concrete case from the sample,
`aws-powertools__powertools-lambda-python-7253`, goes from 5,387 characters to 1,103 (ratio 0.20)
while gaining Summary / Steps to Reproduce / Expected / Actual headers.

That is the sharpest available statement of the paper's thesis: the template is what the reward
model rewards, and the template can be satisfied *by deleting content*. Intrinsic quality and
solver-actionable signal are not merely decoupled — the intrinsic metric can be improved by an
edit that destroys the very information the solver needs. Code `B3_signal_loss` is the one to
watch during coding.

## Remaining work (requires two humans)
1. Two coders label all 90 items independently against the codebook.
2. Report Cohen's κ per dimension.
3. Build the pattern × outcome cross-tabulation.
4. Fold into §RQ3, replacing the preliminary summary with coded results, and correct the
   "uniform" characterisation above.
