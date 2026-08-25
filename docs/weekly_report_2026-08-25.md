# Weekly Progress Report — Pouya Fathollahzadeh
**Week:** 2026-08-18 → 2026-08-25
**Project:** LLM-Based Agents for GitHub Issue Enhancement (TSE draft)

## Summary
This week answered the question the paper had never actually tested. Auditing the pipeline against
the paper's own description revealed that the three "agentic" enhancers **never had repository
access** — they are text-to-text rewriters running in an empty directory, while the solver runs in a
container with the full repository. The paper's thesis (enhancer agent + solver agent, both with
repo access, beats solver alone) had therefore never been run. I built that enhancer and tested it.
**It does not rescue the null.** Alongside this, the diagnosis of *why* enhancement fails sharpened
into a quantitative account, and a reproducibility audit caught errors in both the pipeline and my
own analysis.

## Completed

### 1. Diagnosis: enhancement behaves as an information-free resample
Conditioning flips on the baseline outcome over 1,230 paired trials: P(fix | baseline failed)
= 19.9%, P(break | baseline passed) = 40.8%, ratio **2.05** against **1.95** predicted by a pure
resample at the 33.9% base rate — **4.9% agreement**. If enhancement carried information the ratio
would fall below the prediction. It does not.

The root cause is an information asymmetry: `enhancer output = f(issue text)` while
`solver input = issue text + repository`. Anything the enhancer derives, the solver derives from a
strict superset by reading the code. Enhancement cannot add information; it can only re-word.

**Actionable corollary:** since enhancement is a resample, baseline-OR-enhanced *is* best-of-2 —
which scores **47.1% vs 33.9%** baseline (**+13.2 points**) where enhancement scores −0.7. The same
compute spent on a second solver attempt beats rewriting the issue. This reframes the contribution
from "enhancement does not work" to "**this compute is misallocated**", and sets the correct bar for
future work: beat best-of-2 at equal compute.

### 2. Audit: the paper misdescribes its own enhancers
The draft states the three enhancers are "each a ~30-step agent loop given the issue and repository
access". Verified against the code: **none has repository access**; loop depths are 1 (Aider — a
single non-interactive message, not a loop at all), 8 (OpenHands), 10 (SWE-agent). The one grounding
channel in the prompt was empty in every run. The **solvers**, by contrast, check out exactly as
described — repo at `/testbed`, 30 steps, 7 tools, verified in logs and images.
Methodology section now corrected in the draft.

### 3. Built and tested the repo-grounded enhancer — the paper's actual thesis
New enhancer gets **exactly what the solver gets**: same container, repo at `/testbed`, same 30-step
tool loop. No oracle (never the gold patch, test patch, hints, or F2P names). Two constraints from
the diagnostics: **append-only** (original preserved verbatim) and **every cited path verified** to
exist before the output is accepted.

*It works as engineering.* On GPT-5-mini it enriched 17/20 reports, cited **50/50 verified file
references with zero invented paths**, median enrichment 5.96× (one 234-char issue became a 7.5 KB
report with real functions and line numbers). One case where the agent dropped 15 stack-trace lines
was caught by the append-only guard and repaired.

*It does not change correctness.* **13/20 → 12/20** (per-protocol 11/17 → 10/17). Of the 7 issues
the baseline failed, it rescued **zero**, against a pre-registered threshold of ≥4. Nineteen of
twenty instances had identical outcomes in both arms.

This is the strongest form of the negative result: a well-formed, repository-grounded, verified,
non-destructive enhancement rescued nothing — exactly what the redundancy argument predicts.

### 4. A secondary finding pointing the other way on *harm*
Enhancement broke only **1 of 13** working solves where a resample would break 5.3
(**p = 0.011**). Preserving the original verbatim appears to leave the solver's trajectory intact,
so the append-only constraint removes the perturbation the unconstrained text-only enhancers
introduce — without supplying benefit. **Not pre-registered**; the replication test on the second
arm was fixed in advance and is pending.

### 5. Reproducibility and correctness fixes
- **Restored `score_sample.py`**, which the capability-spread doc referenced but which no longer
  existed — the headline experiment was not reproducible. Recovered the per-instance gold-probe
  method map as a versioned artifact.
- **Latent scoring bug**: harness crashes were silently scored as unresolved (unchecked return
  code). Audited: 0 occurrences across 36 historical evaluations, so no published number is
  affected. Now fails loudly.
- **Corrected my own analysis error**: a merged outcome set had included an all-zero *failed*
  scoring matrix, adding 74 phantom instances and deflating every rate. Conclusions unchanged
  (agreement stayed 4.9%), but the rates are now right.
- **Three false-positive bugs in the reference verifier**, each of which would have reported a real
  file as a hallucination: git-tracked-only checking, `lstrip("./")` mangling `.venv/…`, and dotted
  module notation. Corrected counts: GPT-5-mini **50/50, zero hallucinations**; Qwen3-32B 42/43,
  **one** genuine invented path. Citation fidelity tracks capability.
- **Unified all agent budgets to 30 steps** (were 1/8/10/20/30). Measured: solved runs use a median
  of 18 steps, two needed all 30; cutting to 25 would cost 22% of solves for 7% compute. 30 stays.

## In progress
**Qwen3-32B repo-grounded arm** (20 issues, 13 rescuable — the better-powered rescue test,
threshold ≥6). In its final solve phase. It also independently tests whether the low-breakage effect
replicates.

## Next
1. Fold the Qwen3 arm into the repo-grounded section and settle the scope of the null.
2. Recover 74 instances whose scoring artifacts were lost (solver outputs intact; 343 Docker
   evaluations, no API cost) and finish the Table 1 audit.
3. **RQ3** — 90-item stratified sample and codebook are ready; needs two coders and Cohen's κ.
4. Seed-2 replication to convert "Δ flips sign on rerun" into measured variance.
5. Rotate the exposed GitHub token and the OpenAI key embedded in old run configs.
