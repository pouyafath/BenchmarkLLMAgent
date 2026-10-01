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
