# Agent iteration budget: why 30, uniformly (2026-08-25)

## Decision
**Every agent in the pipeline — enhancer and solver alike — runs a 30-step loop.**

| Agent | Env var | Was | Now |
|---|---|---:|---:|
| OpenHands solver | `OH_SOLVER_MAX_ITER` | 30 | 30 |
| SWE-agent solver | `SWEA_SOLVER_MAX_STEPS` | 30 | 30 |
| OpenHands enhancer | `OPENHANDS_MAX_ITER` | **8** | 30 |
| SWE-agent enhancer | `SWEAGENT_MAX_STEPS` | **10** | 30 |
| TRAE enhancer | `TRAE_MAX_STEPS` | **10** | 30 |
| OpenClaw enhancer | `OPENCLAW_MAX_ITER` | **8** | 30 |
| repo-grounded enhancer | `RGE_MAX_ITER` | **20** | 30 |

Aider is the exception and cannot be set: `aider --message` is a single non-interactive
turn by CLI design. It is not an iterative agent and should not be described as one.

## Rationale

**1. Symmetry makes the design describable.** The paper's unit of study is
*enhancer agent + solver agent vs. solver agent alone*. If the enhancer gets 8 steps and the
solver 30, "agent" means two different things in the same sentence. Equal budgets make the
comparison stateable in one line, and make the compute accounting honest: enhancer+solver costs
**2× solver-alone**, which is precisely why best-of-2 is the correct baseline
(see [why_enhancement_fails_and_what_could_work.md](why_enhancement_fails_and_what_could_work.md)).

**2. Comparability with prior work.** 30 is the conventional budget in OpenHands' own SWE-bench
evaluations, so absolute resolve rates stay readable against published numbers. Deviating would
force every comparison to carry a caveat.

**3. It is empirically non-binding.** Measured on our own runs: agents that solve a task converge
well before the cap; agents that reach it are thrashing and fail regardless.

| | resolved | unresolved |
|---|---:|---:|
| GPT-5-mini — finished early | **10** | 4 |
| GPT-5-mini — exhausted 30 iters | 1 | 4 |
| Qwen3-32B — finished early | **7** | 5 |
| Qwen3-32B — exhausted 30 iters | 0 | 1 |
| Qwen3-32B — stuck in loop | 0 | 3 |

Across the full 279-instance run GPT-5-mini hits the cap on **22.2%** of instances, and those are
overwhelmingly failures. Raising the cap would buy little: reaching step 30 signals a lost
trajectory, not an almost-finished one. Lowering it toward ~15–20 would likely cost little either,
but 30 is retained for comparability.

**4. Prior work points the same way.** Successful SWE-agent trajectories typically complete in far
fewer than 30 steps, and Agentless (Xia et al., 2024) showed a fixed pipeline with *no* agentic
loop matching agent scaffolds on SWE-bench-lite — evidence that loop depth is not where the value
lies. (Treat these as directional; verify before citing.)

## The open question this raises
Budget is better spent on **more attempts than longer attempts**. Our own union analysis found
best-of-2 worth **+9.7 points** where enhancement was worth −0.5. A cap of ~15 with two samples
would plausibly dominate a single 30-step run at equal cost. That is a cheap experiment and a
genuine contribution, since the field mostly sets this knob by convention.

## Caveat on the pilot runs
The two 5-issue repo-grounded pilots launched 2026-08-24 used `--enh-max-iter 20` (the default at
the time). The solver arm was 30 in both. Given the evidence above that the enhancer cap is not
binding, this is unlikely to matter, but it must be stated if those pilot numbers are reported.
The default is now 30, so subsequent runs are uniform.
