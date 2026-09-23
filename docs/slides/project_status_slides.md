---
marp: true
theme: default
paginate: true
---

# Benchmarking LLM-Based Agents for GitHub Issue Enhancement

**Pouya Fathollahzadeh** · Ying Zou
Queen's University · target venue IEEE TSE

Status as of 23 September 2026

<!-- Renders with Marp, reveal-md, or Pandoc. Plain `---` slide separators. -->

---

## Motivation

Developers have told us for twenty years what a good bug report contains.

Bettenburg et al. (2008) and Zimmermann et al. (2010): **steps to reproduce, stack traces
and test cases are the most valuable elements, and the most often missing.**

In our own corpus of 279 real issues:

| element | present in |
|---|---:|
| reproduction steps | **17.6%** |
| stack trace | **15.8%** |
| error message | 22.2% |

LLM agents can now read a repository and rewrite a report. If agents solve issues *from text*,
then better text should mean better fixes.

**That assumption has never been tested by executing the resulting patch.**

---

## The question

> **Does automatically enhancing a GitHub issue report improve an LLM agent's ability to
> produce a correct fix?**

Measured **extrinsically**: not by a text-quality score, but by whether the patch the solver
produces passes the repository's own tests.

Formally, for enhancer $E$ and solver $S$:

$$\Delta_{\text{resolved}} = \text{Resolved}(S, E(\text{issue})) - \text{Resolved}(S, \text{issue})$$

Three research questions:

- **RQ1** Does enhancement improve fix correctness?
- **RQ2** Which report features predict a better enhancement?
- **RQ3** What do the agents actually do to the text?

---

## The gap

Prior work stops one step short of the outcome that matters.

| work | what it does | how it validates |
|---|---|---|
| Bettenburg, Zimmermann | what makes a good report | developer survey |
| Duplicate detection, triage | route reports | retrieval rank |
| Acharya & Ginde (EASE'25) | LLM-generated bug reports | CTQRS, ROUGE, METEOR, SBERT |
| Al Fahim et al. (2025) | crash reports + repo exploration | similarity to developer patch |
| **This work** | **agentic enhancement** | **does the patch pass the tests** |

Prior work shows models can **raise a report's measured quality**.
None of it shows that gain **transfers to a correct fix**.

<!-- Al Fahim is the closest neighbour: same single-shot vs repo-exploring contrast we draw, but evaluated on patch similarity, not repair. -->

---

## Data collection

A SWE-bench-Live-style benchmark built from issues **after the models' training cutoffs**,
so results are not contaminated (cf. Zhou et al., leakage across 83 SE benchmarks).

```
10,609 repositories          stars > 1,000
     ↓                       language, forks, issue volume, recency
 3,285 instances             merged PR carrying code patch + test patch
     ↓                       613 repositories
   382 instances             environment builds, tests execute
     ↓                       ── GATE 1: gold patch passes (73.0%)
   279 instances             ← every condition reported on these
     ↓                       ── GATE 2: gold patch flips a test (30.5%)
    85 instances             ← scored on fixing
```

Two evaluability gates. The first makes a no-regression score trustworthy.
The second was added after we found the shipped labels had never been executed.

---

## Approach

**Issue states × solvers = 12 conditions**, model held fixed at Qwen3-32B.

| issue state | solver |
|---|---|
| no enhancement (baseline) | OpenHands |
| zero-shot prompt (Raw LLM) | SWE-agent |
| agentic enhancer × 3 (OpenHands, SWE-agent, Aider) | Aider |
| reward-gated CL-Enhanced | |

Every comparison is **paired** on the same issues, tested with an **exact McNemar test**.

**The critical design choice.** Solvers are randomised procedures, so we measured what a
*resample* does: re-running the same solver on the same issue with no change to the text.

> On Qwen3-32B: it fixes **19.9%** of what it previously failed, and breaks **40.8%** of what
> it previously solved.

Every result is judged against that, not against zero.

---

## Result 1 — RQ1: no enhancer improves any solver

$n = 279$ gold-evaluable issues. Resolved counts, McNemar $p$ in parentheses.

| solver (baseline) | enh: OpenHands | enh: SWE-agent | enh: Aider | Raw LLM |
|---|---|---|---|---|
| OpenHands (60, 22%) | 58 (−2, .910) | 66 (+6, .561) | 67 (+7, .489) | 61 (+1, 1.0) |
| SWE-agent (18, 6%) | 18 (0, 1.0) | 19 (+1, 1.0) | 19 (+1, 1.0) | 12 (−6, .031†) |
| Aider (124, 44%) | 125 (+1, 1.0) | 119 (−5, .649) | 124 (0, 1.0) | 112 (−12, .213) |

**No agentic enhancer × solver comparison reaches significance. Every $p \ge 0.489$.**
Largest absolute effect: 7 issues out of 279.

† the only $p<.05$ cell: a non-determinism artifact on a solver that fails ~86% of runs
at the agent–computer interface.

---

## Result 2 — enhancement *is* a resample

The deltas are not just small. They match what re-rolling the dice predicts.

| | observed | resample predicts |
|---|---:|---:|
| P(fix \| previously failed) | 0.199 | — |
| P(break \| previously passed) | 0.408 | — |
| ratio observed | **2.05** | **1.95** |

Agreement within **4.9%**.

**The direction is predicted too.** Pooling every replication cell by solver:

| solver | baseline rate | Δ | rescues / chance | breakages / chance |
|---|---:|---:|---|---|
| OpenHands | 0.21 | **+26** | 78 / 75.2 | 52 / 41.6 |
| Aider | 0.47 | **−31** | 46 / 50.1 | 77 / 93.0 |

Enhancement lifts whichever solver has room to rise and depresses whichever has more to lose.
**That is regression to the mean, not added information.**

---

## Result 3 — every objection to the null, tested

A negative result invites three specific objections. Each had a pre-registered experiment.

| objection | experiment | outcome |
|---|---|---|
| The enhancers **deleted** the reporter's text | append-only matrix, 6 cells, 80 issues | **165 → 164**, null |
| The metric wasn't measuring **fixing** | executed fix criterion, 16 comparisons | **75 → 66**, 0/16 significant |
| One cell showed **real protection** | out-of-sample replication, 80 fresh issues | **did not replicate**, p = 0.425 |

Append-only detail: **235 of 236** enhancements had to be repaired to stop them *replacing*
the report. After repair the original survives verbatim and the agents still add 1–2 KB.
Rescue rate **0.187** against a chance 0.199. Breakage **0.364** against 0.408.

**The confound was not concealing a benefit.**

---

## Result 4 — a benchmark correction

All 279 instances carried `f2p_p2p_derivation.method = offline_test_patch_diff_parse`.

**The fail-to-pass labels were parsed from the test patch's diff and never executed.**

| label source | instances with a fail-to-pass test |
|---|---:|
| parsed from the diff | 225 |
| **observed by execution** | **85** |
| the two agree on | 45 |

Rescoring the same stored patches under the corrected criterion:

| solver (4 arms each) | no-regression | executed fix |
|---|---:|---:|
| Aider | 27 | 25 |
| **OpenHands** | **15** | **0** |

Aider's solves are genuine. **All fifteen of OpenHands' disappear** — it fails by terminating
without a patch, and an untouched repository keeps the suite green.
The solver-capability gap we report is **understated, not overstated**.

---

## Result 5 — RQ3: what the agents actually do

90 enhancements open-coded, stratified 10 per enhancer × outcome cell.

| rewrite move | % | failure mode | % |
|---|---:|---|---:|
| restructure into sections | **91** | drops or buries content | **50** |
| add reproduction steps | 67 | none observed | 32 |
| add code context | 50 | abstained | 9 |
| **add root-cause hypothesis** | **10** | hallucinated specifics | 9 |
| surface a stack trace | 6 | over-specified | 2 |

The template is near-universal. **Real diagnosis is rare.**

**Nothing predicts helping.** Restructuring splits 26/28/28 across helped/hurt/unchanged;
reproduction steps 21/18/21; code context 14/16/15. All $p \ge 0.227$.

Also: **10 of 90** carry the enhancer's own scaffolding — unfilled template slots, a shell
heredoc terminator, the benchmark instance id pasted in as the title.

---

## Result 6 — the strongest objection, tested

> *"Execution benchmarks only keep issues someone already fixed, so you tested enhancement
> where it wasn't needed."*

We tested it on the thin reports the corpus does contain. **75 of 279** carry two or fewer
of nine diagnostic elements.

1,600 paired observations, 31 Qwen3-32B cells, 80 instances:

| stratum | rescue rate | chance |
|---|---:|---:|
| thin (0–2 elements) | **0.109** | 0.199 |
| mid (3–5) | 0.104 | 0.199 |
| rich (6–9) | 0.147 | 0.199 |

**Below chance in every stratum.** Instance-level thin-vs-rich: $p = 0.179$.

*Honest limit:* at 20 vs 22 instances this excludes a large gradient, not a modest one. And
"thin" means thin *relative to a corpus where a fix was merged*. The objection is **narrowed,
not answered**.

---

## Result 7 — closed-source models, and a lesson

GPT-5-mini on all 279: **155 → 159** (+4, McNemar $p = 0.712$). A null.

But its 66 discordant pairs looked strange against our chance rates:

| | observed | Qwen3's rate predicts | p |
|---|---:|---:|---:|
| breakages | 31 / 155 | 63.2 | **< 0.00001** |

That looked like a real protective effect. **It was a borrowed null.**

We ran a second, independent GPT-5-mini baseline draw (279 issues, ~$13–32, 5,966 LLM calls)
to measure *its own* resample rate:

| | Qwen3-32B | **GPT-5-mini (measured)** |
|---|---:|---:|
| P(break \| passed) | 0.408 | **0.161** |

Re-testing against the correct null: 31/155 = 0.200 vs own-chance 0.161, **$p = 0.919$**.
**The effect vanishes.** A stronger model simply reproduces its own results more often.

---

## What this means

**Enhancement is a resample of the solver.** Three independent pre-registered tests agree,
and the finding survives both objections a reviewer can raise.

The practical recommendation:

| strategy | resolved rate | at equal compute |
|---|---:|---|
| baseline, once | 33.9% | — |
| baseline **or** enhanced (best-of-2) | **47.1%** | **+13.2 points** |
| enhancement | −0.7 | costs a full agent run |

**Spend the second agent run on a second solve attempt, not on rewriting the issue.**

Any future enhancer has to clear best-of-2, not baseline-once.

---

## Contributions

1. **A large-scale extrinsic benchmark** and a rigorous negative result: no enhancement
   condition reliably improves fix correctness at any tested scale, and the one promising
   small-sample signal traced to sampling noise under replication.

2. **A feature-level and qualitative account** of what enhancement does, surfacing an
   *intrinsic-improves / extrinsic-flat* gap.

3. **An evaluation methodology**: a gold-patch-gated three-method evaluability gate (73.0%
   coverage), artifact-recovery discipline, and a procedure for deriving fail-to-pass labels
   **by execution** rather than by parsing a diff. The last matters beyond this study.

4. **A replication package**: benchmark, pipeline, stored patches, all analysis scripts.

---

## Status and what remains

**Manuscript** — 12 pages, 2 figures, 10 tables, 31 references, compiles clean, all numbers
audited against source data.

| remaining | owner |
|---|---|
| Revoke 16 GitHub tokens exposed in history | **urgent** |
| Second human coder for RQ3 (Cohen's κ) | you |
| Upload artifact to Zenodo, add DOI | you |
| Acknowledgements section | you |

**Known weaknesses, stated plainly:**

- Strict criterion rests on **85 instances**; well powered against a large effect, not a small one
- One model for the controlled matrix; GPT-5-mini is a single-cell cross-check
- SWE-agent is effectively inert (2–6 submissions per 80)
- RQ3 has no human coder yet

---

## Backup — why the resample null matters

Two independent baseline draws of **the same model on the same issues, no intervention**:

| | resolved |
|---|---:|
| GPT-5-mini draw 1 | 155 / 279 |
| GPT-5-mini draw 2 | **160 / 279** |

**+5 issues from doing nothing at all.**

Any study reporting a single-run delta of a few issues, without a measured chance baseline,
cannot distinguish its effect from this.

This is the methodological point the paper is built on, and it is why every number in the
study is reported against a measured resample rate rather than against zero.
