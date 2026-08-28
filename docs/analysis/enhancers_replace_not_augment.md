# Enhancers replace the report; they do not augment it (2026-08-28)

## Finding
Across **236 successful enhancements** by three different coding agents (OpenHands,
trae, mini-SWE-agent), each given repository access and asked to enrich a GitHub issue:

| Enhancer | n | preserved the original **verbatim** | retained **≥90%** of its substantial lines | median length ratio |
|---|---:|---:|---:|---:|
| OpenHands | 77 | **1** | **1** | 1.11× |
| trae | 80 | **0** | **0** | 1.43× |
| mini-SWE-agent | 79 | **0** | **0** | 0.69× |
| **total** | **236** | **1** | **1** | |

**Exactly one enhancement out of 236 kept 90% of what the reporter wrote.**

## This is rewriting, not summarising
The length ratios rule out the simple reading. trae's output is on median **43% longer**
than the original and still retains under 90% of its lines — it is not compressing, it is
restating the issue in its own words and discarding the reporter's. mini-SWE-agent does
shorten (0.69× median), and one measured trae case returned **199 characters for a 6,619
character issue** — a 0.03× ratio, dropping 97% of the report including its reproduction
steps.

## Why it matters for the experiment
Every enhancement condition therefore changes **two** things at once: it adds agent-derived
context *and* removes reporter-written content. A negative or null delta is then
unreadable — it could mean "the added context does not help" or "the deletion hurt as much
as the addition helped", and the design cannot distinguish them.

This confound is present in **all** prior enhancement results in this project, including
the published Table 1, because no enhancer was ever constrained to preserve its input.

## The fix
`_repo_export.enforce_append_only()` guarantees the original survives verbatim, with
whatever the agent produced appended under a heading. It is applied **centrally in the
runner**, so every enhancer is treated identically and the treatment is isolated to
*added* context.

Applied to the run-3 enhancements, it repaired **235 of 236** rows — consistent with the
table above.

Because the agents' added content is unaffected by the repair, the corrected experiment
does not require re-running the enhancers: `MATRIX_ENHANCED_DIR` reuses the existing
enhanced rows, repairs them, and re-solves. That converts a ~4-hour re-enhancement into a
file read.

## Reporting consequence
Two claims should be separated in the paper:

1. **Agents do not augment issue reports; they rewrite them.** A behavioural result about
   coding agents used outside their design purpose, standing on 236 observations.
2. **Whether *added* repository context improves fix correctness** — measurable only under
   the append-only constraint, which is what run 4 tests.
