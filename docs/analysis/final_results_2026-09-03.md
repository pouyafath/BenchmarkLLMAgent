# Final results (2026-09-03)

Every stored condition, rescored under an executed fix criterion, plus the last
outstanding replication. Nothing positive survives.

## 1. Enhancement is null under a real fix criterion

`scripts/analysis/strict_rescore_all.py`, using the executed FAIL_TO_PASS labels:

| comparison | n | baseline | enhanced | delta | McNemar |
|---|---:|---:|---:|---:|---:|
| Qwen3 enh:aider -> aider | 71 | 11 | 10 | -1 | 1.000 |
| Qwen3 enh:openhands -> aider | 75 | 11 | 10 | -1 | 1.000 |
| Qwen3 enh:swe_agent -> aider | 71 | 11 | 12 | +1 | 1.000 |
| Qwen3 zero-shot -> aider | 73 | 11 | 5 | -6 | 0.070 |
| Qwen3 CL(gated) -> aider | 81 | 11 | 10 | -1 | 1.000 |
| Qwen3 any enhancer -> openhands | 50-57 | 0 | 0-1 | ~0 | 1.000 |
| GPT-5-mini enh:aider -> openhands | 79 | 20 | 18 | -2 | 0.754 |
| **pooled, 16 comparisons** | **738** | **75** | **66** | **-9** | **0.222** |

**0 of 16 comparisons reach significance.** Every enhancer (three agentic, one zero-shot,
one reward-gated), every solver, and both a weak open model and a frontier one.

## 2. The direction of each null is what a resample predicts

Pooling every scored 40-instance rerun cell by solver:

| solver | baseline rate | delta | rescues/failures | chance | breakages/solves | chance |
|---|---:|---:|---|---:|---|---:|
| openhands | 0.21 | **+26** | 78/378 | 75.2 | 52/102 | 41.6 |
| aider | 0.47 | **-31** | 46/252 | 50.1 | 77/228 | 93.0 |
| swe_agent | 0.07 | +0 | 0/444 | 88.4 | 0/36 | 14.7 |

Enhancement lifts the weak solver and drags the strong one, with both margins within a
rescue or two of chance. That is regression to the mean. It also explains the encouraging
individual cells seen earlier: they were all on the low-baseline solver, where a resample
can only push upward.

## 3. The one surviving positive did not replicate

Run-4's `enh:openhands -> sol:aider` broke 7 of 38 baseline solves where a resample breaks
15.5 (p = 0.003). A pre-registered, out-of-sample replication on 80 fresh instances
returned 14 of 37, rate 0.378 against chance 0.408, p = 0.425. Dropped as a
multiple-comparisons artifact. See `replication_prereg_openhands_aider.md`.

## 4. The metric was inflating results

Executed labels replace diff-parsed ones (`f2p_rederivation_2026-09-01.md`). On the main
matrix, the criterion change is not uniform:

| solver | published (P2P dispatch) | executed F2P |
|---|---:|---:|
| Aider, 4 arms | 27 | 25 |
| OpenHands, 4 arms | 15 | **0** |

Aider's solves are genuine fixes. Every one of OpenHands' credited solves was an artifact
of the no-regression criterion, which credits a patch that never applied. The
solver-capability gap the paper reports is understated.

## Coverage and limits

* 85 of 279 instances carry an executed fail->pass test; only those can be scored on
  fixing. Cells report their own n.
* The first tranche's per-test artifacts were regenerated over its 28 gradeable instances
  (`rescore_tranche100.py`); the other tranches' survived.
* SWE-agent is inert throughout (2-6 submissions per 80), so its zeros carry no
  information either way.

## What this means for the paper

Three independent, pre-registered tests now agree: the resample null, targeted-60 (8
rescues against 8.0 expected), and run-4's purely additive matrix. Enhancement is a
resample of the solver. Best-of-2 at equal compute remains +13.2 points.

The negative result is well-powered, pre-registered, robust to the strongest objection
available (that enhancement was deleting content), and robust to the metric objection
(that P2P-only is not fixing). That is the paper.
