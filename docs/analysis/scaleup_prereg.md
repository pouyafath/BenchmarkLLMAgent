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

---

# Second scale-up: GPT-5-mini on random-20

Run: `runs/rge20_gpt5mini_20260825_023548/`. Same enhancer, same design, both arms fresh.
Random-20 is used rather than g5s20 because GPT-5-mini resolves all of g5s20 by construction
and would have zero headroom there.

Fresh-scored baseline on this set: **11/20** → **9 rescuable**, **11 exposed**.

| | expected under the resample null |
|---|---|
| rescues | **1.2** of 9 |
| breakages | **4.5** of 11 |
| **net Δ** | **−3.3** |

The negative-delta prediction is even stronger here: with 11 resolved instances exposed at a
40.8% break rate and only 9 failures exposed at 12.9%, **pure noise predicts Δ ≈ −3**. A result
of Δ −2 or −3 on this arm is the null, not harm.

P(≥ k rescues), k ~ Binomial(9, 0.129):

| k | 0 | 1 | 2 | 3 | **4** | 5 |
|---|---|---|---|---|---|---|
| P(≥k) | 1.000 | 0.711 | 0.327 | 0.099 | **0.020** | 0.003 |

**Pre-registered thresholds:**

| rescues | verdict |
|---:|---|
| **≥ 4** | Beats the resample null (p = 0.020). **Real effect** at the frontier. |
| **1–3** | Indistinguishable from resample. **Null holds.** |
| **0** | Null holds, below the resample rate. |

## Combined reading
The two arms test different regimes: Qwen3-32B asks whether repo-grounding lifts a *weak* solver
(13 rescuable), GPT-5-mini whether it lifts a *frontier* one (9 rescuable). If both land in their
null bands, the null generalises across the capability range for repo-grounded enhancement, and
the redundancy argument becomes the paper's demonstrated headline rather than a conjecture.

---

# CORRECTION to the null rates (2026-08-25, before either run finished)

The rates above were computed from an outcome set that wrongly included
`runs/stage6_100_scores`, whose matrix is **all-zero for every cell** — a failed scoring run. Its
74 phantom always-unresolved instances inflated the baseline-failed denominator and deflated
P(fix|failed).

| | as first written | **corrected** |
|---|---|---|
| P(fix \| baseline failed) | 12.9% | **19.9%** (162/813) |
| P(break \| baseline passed) | 40.8% | 40.8% (unchanged) |
| baseline pass rate | 24.9% | **33.9%** |
| resample-null ratio | 3.01 predicted / 3.16 observed | **1.95 predicted / 2.05 observed** |

The agreement with the resample null is **still 4.9%**, so the underlying conclusion is unchanged.
Flip counts and deltas were never affected — phantom rows contribute no flips.

## Corrected thresholds, same pre-specified rule
Smallest k with P(≥k) < 0.05 under Binomial(n_rescuable, **0.199**):

| Run | n_rescuable | null expects | old threshold | **corrected threshold** |
|---|---:|---|---:|---:|
| Qwen3-32B / g5s20 | 13 | 2.6 rescues, 2.9 breakages, net −0.3 | ≥5 | **≥6** |
| GPT-5-mini / random-20 | 9 | 1.8 rescues, 4.5 breakages, net −2.7 | ≥4 | **≥5** |

These corrected thresholds are **stricter**, and they are recorded while both runs are still in
their enhance phase — no result has been seen. The rule (smallest k with P<0.05) is unchanged; only
a mis-measured input was fixed. `scripts/analysis/verdict.py` now uses P_FIX = 0.199.

Note the null's expected net delta for Qwen3 moves from −1.2 to **−0.3**, so a delta near zero is
the null there; for GPT-5-mini it remains strongly negative at −2.7.

---

# Secondary hypothesis, pre-registered before the Qwen3 result (2026-08-25)

The GPT-5-mini arm produced an unplanned finding on the **breakage** side: 1 breakage of 13
exposed instances where the resample null expects 5.3.
P(≤1 | Binomial(13, 0.408)) = **0.011**.

Reading: append-only repo-grounded enhancement perturbs the solver **less** than a resample does,
because the original text is preserved verbatim and only appended to. Two separable effects that
the aggregate Δ hides — no rescues, but also markedly fewer breakages.

This was **not** pre-registered; it is a secondary analysis found after the fact and must be
treated as a hypothesis, not a result.

**Pre-registered replication test on the Qwen3-32B arm** (result not yet seen; that run is still
in its enhanced-solve phase):

> Let `n_exposed` be the count of baseline-resolved instances and `b` the observed breakages.
> Compute P(≤ b | Binomial(n_exposed, 0.408)). The low-breakage effect is **replicated** if
> p < 0.05, and **not replicated** otherwise.

Reporting rule fixed in advance: if it replicates, it is reported as a finding about the
append-only constraint. If it does not, the GPT-5-mini observation is reported as a single
unreplicated result and nothing more.

