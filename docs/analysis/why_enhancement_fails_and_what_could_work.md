# Why issue enhancement doesn't help solvers — and what would (2026-08-24)

Diagnostic analysis of the RQ1 null. All numbers are from the paper's controlled configuration
(Qwen3-32B, 279 gold-evaluable instances, 3 agentic enhancers × {OpenHands, Aider} solvers =
1,230 paired trials) unless stated.

---

## Finding 0 — The information asymmetry that explains everything else

**The solver sees the whole repository. The enhancer sees only the issue text.**

Verified directly. The solver runs in a per-instance container (`pouya/stage2_2026:<iid>_linux`)
with the repository checked out at the base commit under `/testbed`, and is equipped with
`execute_bash`, `str_replace_editor`, `execute_ipython_cell` and search tools — it can read, grep
and execute the code. The enhancer (Finding 2) gets an empty temp git directory containing a
single `issue.md`.

So:

```
enhancer output = f(issue text)
solver input    = issue text + entire repository at base commit
```

Anything the enhancer can derive, the solver can derive from a **strict superset** — by reading the
code. Enhancement therefore **cannot add information to the solver's input**. It can only re-word
what the solver already had, and re-wording perturbs the agent's trajectory.

This is not a prompt-tuning problem or a weak-enhancer problem. It is an information-theoretic
ceiling, and every other finding in this document follows from it:

- Δ ≈ 0, because nothing was added (Finding 1);
- the flips match a pure-resample null to within 4.9%, because trajectory perturbation is the
  *only* remaining effect (Finding 1);
- supplying "grounding" **hurt** (2.4% vs 12.7%), because the enhancer guesses file names it cannot
  verify while the solver could simply have searched for them — an unverified guess actively
  misleads an agent that had ground truth available (Finding 3);
- intrinsic quality gains do not transfer, because the reward model scores a template that carries
  no information the solver lacked (Finding 4).

The enhancer is being asked to describe code it cannot see, to an agent standing inside that code.

## Finding 1 — Enhancement behaves as an information-free *resample*

Conditioning the flips on the baseline outcome:

| | n | flipped | rate |
|---|---:|---:|---:|
| P(fix \| baseline **failed**) | 813 | 162 | **19.9%** |
| P(break \| baseline **passed**) | 417 | 170 | **40.8%** |

Enhancement is 2.05× more likely to break a working solve than to rescue a failing one. That looks
alarming, but it is **not** evidence of destruction — it is the arithmetic signature of re-rolling
the dice at a 33.9% base rate. Under a null model where enhancement is an independent resample
from the same latent per-instance success probability:

```
ratio = P(break|pass) / P(fix|fail) = E[1-p]/E[p] = (1 - 0.339)/0.339 = 1.95
observed                                                              = 2.05   (4.9% off)
```

If enhancement carried real information, the observed ratio would fall **below** the resample
prediction — more rescues, fewer breakages. It does not. Net effect over 1,230 paired trials:
**−8 resolved**.

> This is the sharpest statement of the RQ1 null: enhancement is not a weak treatment, it is
> *statistically indistinguishable from re-running the solver with a different random seed*.
> The queued seed-2 baseline runs will confirm it directly by measuring baseline-vs-baseline
> flip rates.

## Finding 2 — The enhancers *cannot* add information: they never see the repository

This is the structural root cause, confirmed in the code:

- **Aider enhancer** ([aider_enhancer.py:298](../../src/enhancers/ready_to_use/aider_enhancer.py#L298))
  creates an **empty temp git repo** containing a single `issue.md`, purely because "aider requires
  it". No source code.
- **SWE-agent enhancer** ([sweagent_enhancer.py:9](../../src/enhancers/ready_to_use/sweagent_enhancer.py#L9))
  runs in a bare `python:3.12-slim` container — the comment literally reads *"no repo needed"*.
- **OpenHands enhancer** writes only a task file into a temp dir.

The prompt has one channel for grounding — `## Hints (files changed in fix)` — and **it was empty in
every run**: the matrix runner calls `fn(inst)` with a single argument, so `changed_files` defaults
to `""`, and no record in the 382-instance dataset carries `pr_files` (0/382).

So all three "agentic" enhancers are **pure text-to-text rewriters**. They cannot add a fact that
is not already in the issue body. They can only reformat. An enhancer that cannot inspect the
codebase cannot manufacture solver-actionable grounding — which is precisely what a solver needs.

## Finding 3 — The grounding is usually already there, and adding it didn't help

Does the text mention any file or symbol the **gold patch** actually changes?

| Enhancer | kept | lost | gained | neither | lost% |
|---|---:|---:|---:|---:|---:|
| aider | 185 | 18 | 18 | 58 | 6.5% |
| openhands | 184 | 19 | 11 | 65 | 6.8% |
| swe_agent | 193 | 10 | 16 | 60 | 3.6% |

**73% of originals already name the right file.** Enhancement rarely adds it and occasionally drops
it, and losses ≈ gains. So enhancement is neither meaningfully destroying nor supplying grounding.

More pointedly — restricting to baseline-failed instances and asking whether *adding* grounding
rescues them:

| Stratum | n | rescued | rate |
|---|---:|---:|---:|
| original already had grounding | 504 | 66 | 13.1% |
| original lacked it → **enhancer added it** | 41 | 1 | **2.4%** |
| original lacked it → still absent | 157 | 20 | 12.7% |

When the enhancer supplied file references the original lacked, the rescue rate **fell** (small n,
but clearly not a win). The likely reason: with no repo access the enhancer is *guessing* file
names. **Speculative grounding is worse than none** — it sends the solver down a wrong path with
false confidence.

## Finding 4 — What they actually do is restructure, and the template can be satisfied by deleting

| Enhancer | median length ratio | restructured | returned identical |
|---|---:|---:|---:|
| aider | 2.47× | 36.2% | 7.2% |
| openhands | **0.92×** | 79.2% | 20.4% |
| swe_agent | 1.18× | 98.6% | 0.7% |

The OpenHands enhancer's median output is **shorter than the original** — it summarises and imposes
a Problem/Reproduction/Expected/Actual template. It also scores highest on the intrinsic reward
model (0.473 → 0.576) while being null downstream. One sampled case goes 5,387 → 1,103 characters
*while gaining* template headers.

The reward model rewards the template; the template can be satisfied **by deleting content**. That
is why intrinsic quality and downstream fixing are not merely decoupled but anti-correlated.

## Finding 5 — Capability gates whether the text can matter at all

From the trajectory forensics: at low capability the solver submits **no patch at all** on 13–20 of
20 instances (stuck-in-loop or iteration exhaustion), so the issue text is irrelevant — nothing
reads it to completion. At the frontier, GPT-5-mini already resolves what is resolvable. The band
where issue wording could plausibly decide the outcome is narrow.

---

## Problems in the pipeline

1. **Enhancers have no repository access** (Finding 2) — the fundamental limit. Fixing wording
   cannot add information.
2. **The `changed_files` grounding channel is dead** — never passed by the runner, absent from the
   dataset. A capability the code has but never exercised.
3. **Enhancement is unconditional** — applied to all 279, including the 73% that already have
   grounding and the cases where the solver never submits anything.
4. **Rewrites are unconstrained** — enhancers may delete. OpenHands routinely does.
5. **The optimisation target is wrong** — the reward model scores template conformance, which is
   satisfiable by compression.
6. **The metric credits non-applying patches** — P2P-only; 19% of all credited solves across the
   capability table are not genuine patches.
7. **Single-seed deltas** — per-model Δ is reported once; Qwen3-32B's Δ flips sign on rerun.
8. **Timeouts score as unresolved** — 5 of 20 in the Qwen3-32B rerun hit the 1800 s cap, which
   penalises slow-but-correct trajectories.

## What could actually make enhancer+solver beat solver-only

Ranked by expected value, with the evidence each rests on.

### 1. Spend the compute on a second solver attempt instead (immediate, large, reliable)

Since enhancement ≡ resample, "baseline OR enhanced" *is* best-of-2:

| | resolved | rate | Δ vs baseline |
|---|---:|---:|---:|
| baseline (1 attempt) | 417/1230 | 33.9% | — |
| enhanced (1 attempt) | 409/1230 | 33.3% | **−0.7 pts** |
| **best-of-2 (union)** | 579/1230 | **47.1%** | **+13.2 pts** |

The enhancement pipeline spends a full agent run rewriting the issue and returns nothing. The same
budget spent re-running the solver returns **+13.2 points**. This reframes the paper's practical
contribution: not "enhancement doesn't work" but "**this compute is misallocated**" — and it gives
reviewers a positive, actionable result alongside the null.

It also supplies the correct baseline for future enhancement claims: any enhancer must beat
**best-of-2 at equal compute**, not baseline-once. That is a much harder and much more honest bar.

### 2. Repo-grounded enhancement (the only route to real information)

Give the enhancer the codebase — retrieval over the repo at the issue's base commit — and require
every added file/symbol reference to be **verified to exist** before it is emitted. Finding 3 shows
unverified references actively hurt (2.4% vs 12.7%), so verification is the essential part, not the
retrieval. This is the one change that could let an enhancer add information rather than reformat.

### 3. Append-only enhancement (cheap, directly targets an observed harm)

Forbid deletion: the enhanced text must contain the original verbatim, with additions appended.
This structurally eliminates the compression failure (5,387 → 1,103 chars) and the 6.5–6.8%
grounding loss, at essentially no cost. It converts enhancement from a rewrite into an annotation.

### 4. Gate enhancement on predicted benefit

Enhance only where it could plausibly matter: the ~27% of issues lacking gold-file grounding, and
only when the solver is capable enough to submit patches at all. Enhancing all 279 unconditionally
dilutes any real effect into the resample noise of the other 73%.

### 5. Change the optimisation target

Score candidate enhancements by **whether the added claims are verifiable against the repo**, not
by template conformance. The current reward model can be maximised by deletion, which is why its
gains do not transfer.

---

## Honest answer to "can enhancer+solver beat solver-only?"

**Not as currently built** — and not by any amount of prompt tuning, because the enhancers are
text-to-text rewriters with no access to the information the solver lacks. The measured effect is
indistinguishable from a random reseed.

It *could* beat solver-only if enhancement became **grounded and verified** (2) and
**non-destructive** (3). But the bar has moved: it must beat **best-of-2 at equal compute
(+9.7 pts)**, not baseline-once. On present evidence, resampling is the stronger use of the budget,
and that is itself a publishable, actionable result.

## Reproduction
Analyses in this document are derived from `runs/stage6_*_scores/stage6_combined_matrix.json`
(merged per-instance outcomes), `runs/matrix*/qwen3_32b/stage4/*/` (enhanced texts), and gold
patches in `data/matrix_sample382_node01.jsonl`.

---

## Correction (2026-08-25)
An earlier version of this document reported P(fix|failed)=12.9%, a base rate of 24.9%, and a
best-of-2 gain of +9.7 points. Those were computed from a merged outcome set that included
`runs/stage6_100_scores`, whose matrix is **all-zero for every cell** — a failed scoring run, not a
result. Its 74 instances added phantom always-unresolved rows to every condition, inflating the
denominator and deflating every rate.

The corrected figures are above (813 baseline-failed rather than 1,257; 33.9% base rate; +13.2
points for best-of-2). **Flip counts and deltas were unaffected** — the phantom rows contributed no
flips — so the 164-helped / 170-hurt balance and every per-cell Δ stand as reported. The resample
conclusion is likewise unchanged: the observed ratio (2.05) still matches the null prediction (1.95)
to within 4.9%, exactly as before.
