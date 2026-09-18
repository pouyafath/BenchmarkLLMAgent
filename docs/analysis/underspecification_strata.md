# Does enhancement help where reports are thin? (2026-09-18)

This addresses the strongest objection to the paper's null. An execution benchmark keeps an
instance only if a fix was merged and its tests discriminate, so it selects for issues that
are already actionable, which is exactly where rewriting has least room to help. If the null
is an artifact of that selection, the effect should appear on the thinnest reports the corpus
does contain.

Reproduce with `scripts/analysis/underspecification_strata.py`. No containers, no GPU.

## The corpus is not uniformly well specified

Each original report is scored by how many of nine diagnostic elements it carries, taken from
what Bettenburg et al. identify as most wanted and most often missing, rather than from a
learned composite so the split stays interpretable.

| element | present in |
|---|---:|
| actual behaviour | 60.9% |
| code blocks | 60.2% |
| expected behaviour | 54.1% |
| environment info | 46.2% |
| logs | 31.5% |
| error message | 22.2% |
| **reproduction steps** | **17.6%** |
| **stack trace** | **15.8%** |

Median score is 4 of 9, and **75 of 279 instances carry two or fewer elements**. Whatever the
gate selects for, it does not select for complete reports.

## Enhancement does not help more on the thin ones

1,600 paired observations across 31 Qwen3-32B matrix cells and 80 instances. Only this
configuration is used, because the resample rates were measured in it; pooling in the
capability-spread runs, where weak models resolve almost nothing, would invalidate the
comparison.

| stratum | rescue rate | chance | breakage rate | chance |
|---|---:|---:|---:|---:|
| thin (0-2) | 0.109 | 0.199 | 0.328 | 0.408 |
| mid (3-5) | 0.104 | 0.199 | 0.355 | 0.408 |
| rich (6-9) | 0.147 | 0.199 | 0.351 | 0.408 |

**The rescue rate is below chance in every stratum.** There is no slice of this benchmark on
which enhancement rescues more often than re-running the solver.

## The apparent gradient does not survive the right unit of analysis

Pooling all 92 cells in the repository gives deltas of +3 (thin), -1 (mid) and -16 (rich),
which looks like a gradient. It is not one. Each instance recurs in roughly sixteen cells, so
those counts are pseudo-replicated. Taking the instance as the unit:

| stratum | instances | mean net benefit per cell |
|---|---:|---:|
| thin (0-2) | 20 | +0.040 |
| mid (3-5) | 38 | +0.000 |
| rich (6-9) | 22 | -0.025 |

Thin against rich, Mann-Whitney one-sided: **p = 0.179**. The direction is what regression to
the mean predicts from the higher baseline rate on rich reports, and it is not evidence of a
mechanism.

## What this settles, and what it does not

**Settles.** Within the range of report quality this benchmark contains, enhancement does not
help more where reports are thinner, and it rescues below chance in every stratum. The
selection objection cannot be sustained in the strong form that the null is purely an artifact
of testing only well-specified issues.

**Does not settle.** Two limits. At 20 against 22 instances the between-strata test excludes a
large gradient, not a modest one. And thin here means thin relative to a corpus in which
someone merged a fix; issues closed as unclear, or never answered, cannot enter an execution
benchmark at all. That population remains untested and is the honest subject of a separate
study.
