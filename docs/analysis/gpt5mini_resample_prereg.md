# Pre-registration — GPT-5-mini's own resample rate (2026-09-21)

Written before the run.

## Why this run exists

The project calibrates every enhancement result against a measured resample rate: on
Qwen3-32B, re-running the solver on the same issue fixes 19.9% of what it previously failed
and breaks 40.8% of what it previously solved. Those two numbers are what turn a raw delta
into a verdict.

They were measured on Qwen3-32B only, and the paper has been applying them across models.
That is wrong, and the GPT-5-mini cross-model run shows why it matters. On the 279 evaluable
issues that run went 155 -> 159 ($\Delta+4$, McNemar $p = 0.712$), which reads as a null. But
its 66 discordant pairs decompose oddly against the Qwen3 rates:

| | observed | Qwen3 rate predicts | one-sided p |
|---|---:|---:|---:|
| rescues | 35 | 24.7 | 0.016 |
| breakages | 31 | 63.2 | <0.00001 |

Rescues above chance and breakages at half of chance is not what a resample looks like. The
obvious explanation is not a protective effect but a mis-specified null: a stronger, more
consistent model re-run on the same issue reproduces its own previous result more often, so
**both** of its true resample rates should be lower than Qwen3's. Until GPT-5-mini's own rates
are measured, the 35/31 split is uncalibrated and cannot be interpreted either way.

## Design

Draw a **second, independent baseline** for GPT-5-mini on the same 279 evaluable issues: the
original issue text, the OpenHands solver, the same 30-step cap, the same configuration as
`runs/oai_aider_oh_279eval_20260805_203247`, differing only in being a fresh sample from the
same stochastic process. No enhancement arm; it would add cost and answer nothing.

Comparing baseline draw 1 against baseline draw 2 gives the resample rates directly:

    P(fix | failed)   = |resolved in draw 2 but not draw 1| / |failed in draw 1|
    P(break | passed) = |resolved in draw 1 but not draw 2| / |resolved in draw 1|

## Primary test (pre-registered)

With GPT-5-mini's own rates in hand, re-test the enhancement arm's 66 discordant pairs:

> **Prediction under the mis-specified-null explanation:** the enhanced arm's 31 breakages of
> 155 are *not* significantly below what GPT-5-mini's own resample produces. If the measured
> breakage rate is near 31/155 = 0.200, the apparent protection dissolves and was an artifact
> of borrowing Qwen3's 0.408.

> **Prediction under the protective-effect explanation:** GPT-5-mini's own breakage rate is
> materially above 0.200, and the enhanced arm's 31/155 sits significantly below it
> (one-sided binomial, $p < 0.05$).

## Secondary test (pre-registered)

The same for rescues: is 35/124 = 0.282 above GPT-5-mini's own P(fix|failed)? Run-1 versus
run-2 supplies that rate. This is expected to be null, because a resample that reproduces
results more often should also rescue less often, which would push the comparison the other
way.

## What each outcome means

| Primary | Reading |
|---|---|
| Not supported | The cross-model flip asymmetry was a borrowed-null artifact. The paper gains a correction: resample calibration is model-specific, and every cross-model comparison against the Qwen3 rates must say so. |
| Supported | A genuine reduction in harm on a frontier model, measured against that model's own null. This is the first positive result in the project and would need a replication before being claimed. |

## Constraints and cost

Roughly 5,900 LLM calls, about 21 per instance, estimated at \$13-32 depending on prompt-cache
hit rate. Token usage is recorded this time; the August run logged none, which is why the
estimate has that range.

## Standing constraint

Unchanged. Reduced harm is not a reason to enhance. Best-of-2 at equal compute remains the bar,
and enhancement costs a full agent run. A protective effect would change the explanation of the
null, not the recommendation.

---

# Outcome (2026-09-22) — primary NOT supported, the effect was a borrowed null

Run: `runs/gpt5mini_baseline2_279_20260921_183948`, 279 issues, 213 min, 5,966 LLM calls,
211 non-empty patches against draw 1's 210. Scored with `scripts/evaluate/score_one_arm.py`.

## The two draws

| | resolved |
|---|---:|
| baseline draw 1 (August) | 155 / 279 |
| baseline draw 2 (September) | 160 / 279 |

**Five issues separate two runs of the same model on the same inputs with no intervention.**

## GPT-5-mini's own resample rates

| | Qwen3-32B | GPT-5-mini | Wilson 95% |
|---|---:|---:|---|
| P(fix \| failed) | 0.199 | 0.242 | [0.175, 0.324] |
| P(break \| passed) | 0.408 | **0.161** | [0.112, 0.227] |

The breakage rate is less than half Qwen3's, which is exactly the direction predicted above:
a stronger, more self-consistent model reproduces its own result more often.

## Primary test — NOT SUPPORTED

Enhanced arm: 31 breakages of 155 baseline solves, rate 0.200.

| tested against | expects | one-sided p |
|---|---:|---:|
| Qwen3's rate, 0.408 (borrowed) | 63.2 | **< 0.00001** |
| its own rate, 0.161 (correct) | 25.0 | **0.919** |

Against the correct null the rate is not low, it is marginally high. The apparent protective
effect disappears completely.

## Secondary test — NOT SUPPORTED, as predicted

Rescues 35/124 = 0.282 against an own rate of 0.242, one-sided p = 0.172.

## Reading, per the pre-registered table

*"Not supported → the cross-model flip asymmetry was a borrowed-null artifact. The paper gains
a correction: resample calibration is model-specific."*

That is what the paper now says, in a new Section "The resample rate is model-specific". This
is the second time in this project that a mis-specified baseline produced a phantom signal,
after the append-only cell that failed replication in September. Both were caught by testing
rather than by argument.

## Limit

This is one resample pair. It gives each rate with a 95% interval roughly ±8 points wide,
enough to separate 0.161 from 0.408 decisively but not to pin either value precisely.
