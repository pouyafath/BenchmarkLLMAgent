# Pre-registered interpretation — repo-grounded scale-up (2026-08-25)

Written **before** the result is known, so the decision rule cannot be chosen after seeing the
data. Run: `runs/rge20_qwen3_20260825_021626/` — Qwen3-32B, repo-grounded enhancer vs baseline,
20 g5s20 issues, both caps 30, both arms fresh.

## Design facts fixed in advance
- Fresh baseline on this set previously resolved **7/20** → **13 rescuable** instances, and
  **7 exposed** instances that enhancement could break.
- Both arms run fresh in the same run (the sample was selected on baseline failure, so a
  remembered baseline would manufacture a win through regression to the mean).

## The null: enhancement behaves as a resample
Rates measured over 1,674 paired trials in the main matrix:
P(fix | baseline failed) = **12.9%**, P(break | baseline passed) = **40.8%**.

Applied to this design:

| | expected under the null |
|---|---|
| rescues | **1.7** of 13 |
| breakages | **2.9** of 7 |
| **net Δ** | **−1.2** |

**The null already predicts a negative delta here.** Seven resolved instances are exposed at a
40.8% break rate while thirteen failures are exposed at only a 12.9% fix rate. So Δ ≈ −1 is the
*expected outcome of pure noise*, not evidence that enhancement causes harm. This also
retrospectively explains the GPT-5-mini pilot's Δ−1.

## Decision rule

P(observing ≥ k rescues) under the resample null, k ~ Binomial(13, 0.129):

| k | 0 | 1 | 2 | 3 | 4 | **5** | 6 |
|---|---|---|---|---|---|---|---|
| P(≥k) | 1.000 | 0.834 | 0.514 | 0.230 | 0.076 | **0.019** | 0.004 |

**Pre-registered thresholds:**

| rescues | verdict |
|---:|---|
| **≥ 5** | Repo-grounding beats the resample null (p < 0.05). **Real effect** — scale further and this becomes the paper's positive result. |
| **2–4** | Indistinguishable from resample. **Null holds**; report as such. |
| **0–1** | Null holds, and below even the resample rate. |

The delta alone is **not** the criterion — rescues are. A Δ of −1 with 2 rescues is the null; a Δ of
−1 with 6 rescues would be a real effect masked by breakages on the exposed set, and would call for
a larger exposed sample rather than a negative conclusion.

## Why this is pre-registered
The main risk to this line of work is reading whatever number arrives as confirmation. Fixing the
threshold in advance means a positive result is credible and a negative result is honest. If the
outcome is 2–4 rescues, that is a genuine null and will be reported as one, not as "a trend
toward improvement".
