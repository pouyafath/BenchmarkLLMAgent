# Pre-registration — targeted localisation experiment (2026-08-28)

Written before the run. This is the first experiment in the project designed *from* a
measured mechanism rather than testing enhancement generically.

## Where the hypothesis comes from
The only measured benefit of enhancement so far was mechanical. On the Qwen3-32B pilot,
**all six rescues were instances where the baseline solver submitted nothing at all**;
submissions went 6/20 → 12/20 and step-cap exhaustion fell 4 → 1. Separately, the
trajectory forensics showed weak models fail by *never producing a patch* — dying to
repeated actions or step exhaustion — which is a **localisation** failure, not a
code-writing one.

**Hypothesis.** Repo-grounded enhancement helps a solver that cannot localise, by
supplying the file/symbol targeting it would otherwise have to derive itself. It should
therefore help *most* exactly where the baseline produced no patch, and little elsewhere.

## Design
- **Solver** OpenHands · **Model** Qwen3-32B · 30-step loop
- **Enhancer** `repo_grounded` — same container as the solver, repo at `/testbed`, no
  oracle, **append-only**, every cited path verified to exist
- **Sample** 60 instances (`data/targeted60.jsonl`, seed 11), drawn from the 140 that are
  both (a) **failed by Qwen3+OpenHands at baseline** in the full 279 matrix and
  (b) **provably solvable** — resolved by at least one condition somewhere in that matrix.
  This avoids the GPT-5-mini sampling error, where six of seven "rescuable" instances had
  never been solved by anything and the arm could not have produced a result.
- **Both arms run fresh.** The sample is selected on baseline failure, so a remembered
  baseline would manufacture a win through regression to the mean.

## Primary test (pre-registered)
Threshold is the smallest *k* with P(≥*k*) < 0.05 under Binomial(n_rescuable, 0.199),
where 0.199 is the measured resample rescue rate and n_rescuable comes from the **fresh**
baseline in this run:

| if n_rescuable is | chance expects | threshold |
|---|---:|---:|
| 45 | 9.0 | **≥ 15** |
| 50 | 10.0 | **≥ 16** |
| 55 | 10.9 | **≥ 17** |
| 60 | 11.9 | **≥ 18** |

## Secondary test — the mechanism (pre-registered)
This is the claim that distinguishes "enhancement helps" from "enhancement helps *because
it localises*". Partition the rescuable instances by whether the **fresh baseline**
submitted a patch:

> **Prediction:** the rescue rate among instances where the baseline submitted **nothing**
> exceeds the rate among those where it submitted a patch that simply did not resolve.
> Tested with a one-sided Fisher exact test; supported if p < 0.05.

The prior is 6/6 from the pilot. If rescues are instead spread evenly across both strata,
the localisation account is wrong even if the primary test passes, and should be dropped.

## What each outcome means
| Result | Reading |
|---|---|
| Primary passes **and** mechanism holds | Enhancement helps, and we know why. Directly actionable: target weak solvers, supply verified localisation. |
| Primary passes, mechanism fails | Real effect, wrong explanation. Report the effect, withdraw the mechanism. |
| Primary fails, mechanism holds | Under-powered but directionally consistent. Grounds for a larger run, not for a claim. |
| Both fail | The localisation account does not survive. Report it as closed. |

## Standing constraint
The bar for practical value remains **best-of-2 at equal compute** (+13.2 points measured).
Enhancement costs a full agent run; beating baseline-once is not sufficient to recommend it.
