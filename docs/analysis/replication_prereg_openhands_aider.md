# Pre-registration — replicating the append-only breakage effect (2026-09-02)

Written before the run.

## Where the hypothesis comes from

Run-4 (the append-only matrix) is null on rescues across all nine cells: pooled rescue
rate 0.187 against a resample's 0.199. One cell nonetheless stood out on the *other*
margin. `enh_openhands -> sol:aider` broke **7 of 38** baseline solves where a resample of
the solver would break 15.5 (one-sided binomial p = 0.003, which clears a Bonferroni
threshold of 0.0083 for the six responsive cells).

The mechanism would be that preserving the reporter's text verbatim leaves the solver's
working trajectory intact, so added context cannot knock it off a path that was already
succeeding. The repo-grounded pilot saw the same shape: 1 breakage of 13 where a resample
predicts 5.3.

Against it: the other two enhancers on the same solver did not replicate it in run-4
(13/15.5 and 11/15.5, both n.s.). One cell in six at p = 0.003 is roughly what multiple
comparisons produce. This run exists to separate those two readings.

## Design

* **Cell** enh:openhands -> sol:aider, the single cell under test
* **Model** Qwen3-32B, 3-GPU budget · **Enhancer** OpenHands with repository access,
  append-only enforced · 30-step loops
* **Sample** `data/replication80_openhands_aider.jsonl` — 80 instances drawn with seed
  202609 from the 199 evaluable issues **not** used by run-4, so this is an out-of-sample
  replication rather than a re-analysis
* **Both arms run fresh.** A remembered baseline would import run-4's noise into the
  comparison the test is about.

## Primary test (pre-registered)

Breakages among instances the fresh baseline solved, against the resample rate:

> **Prediction:** breakages < Binomial(n_baseline_solves, 0.408), one-sided, p < 0.05.

With the ~38 baseline solves run-4 saw, chance expects 15.5 and the effect predicts ~7.

## Secondary test (pre-registered)

Rescues among instances the fresh baseline failed, against Binomial(n_baseline_fails,
0.199), one-sided. Run-4 gave 13 of 42 (p = 0.060). **This is expected to be null**; the
claim under test is reduced harm, not increased help.

## What each outcome means

| Primary | Secondary | Reading |
|---|---|---|
| holds | null | Append-only enhancement is protective but not helpful. Reportable, and it explains why append-only nulls are flatter than unconstrained ones. |
| holds | also holds | A real benefit. Would justify a powered study. |
| fails | either | The run-4 cell was a multiple-comparisons artifact. Drop it. |

## Standing constraint

Reduced breakage is not a reason to enhance. Best-of-2 at equal compute remains +13.2
points, and enhancement costs a full agent run. A protective effect changes the
explanation of the null; it does not overturn the recommendation.

---

# Outcome (2026-09-03) — the effect did not replicate

Run: `runs/replication80_20260903_014441`, 13.8 h, both arms fresh, 80 instances disjoint
from run-4.

|  | baseline | enhanced | delta |
|---|---:|---:|---:|
| resolved | 37/80 | 35/80 | -2 |

Discordant pairs: 12 rescues, 14 breakages. McNemar p = 0.845.

**Primary test — NOT SUPPORTED.**

| | breakages | rate | chance expects | one-sided p |
|---|---:|---:|---:|---:|
| run-4 (the claim) | 7/38 | 0.184 | 15.5 | **0.003** |
| replication-80 | 14/37 | 0.378 | 15.1 | **0.425** |

The breakage rate came back at 0.378 against a resample's 0.408. The protective effect is
absent.

**Secondary test — NOT SUPPORTED**, as pre-registered: rescues 12/43 = 0.279 against a
chance 0.199, one-sided p = 0.132.

## Reading, per the pre-registered table

Primary fails, so: *"The run-4 cell was a multiple-comparisons artifact. Drop it."*

One cell in six reaching p = 0.003 is what multiple comparisons produce, and the other two
enhancers on the same solver had already declined to show it. The reduced-breakage
observation from the repo-grounded pilot (1 of 13, p = 0.011) should be read the same way:
both were small-sample noise on the margin that happened to be looked at.

Nothing positive survives. Enhancement neither helps nor protects; it resamples.
