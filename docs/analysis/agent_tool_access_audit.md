# Agent tool-access audit — claimed vs. actual (2026-08-24)

What the paper claims each agent can do, what the code actually gives it, and whether it is used.

## The claim

§Methodology, "Enhancement Conditions":

> **Ready-to-use agents:** OpenHands, SWE-agent, and Aider, each a **~30-step agent loop given the
> issue and repository access** and instructed to enhance the description.

§Introduction reinforces it:

> An enhancement agent can **analyze the codebase, identify relevant source files, extract failing
> test information**, and restructure the issue description.

## Enhancers — the claim does not hold

| Agent | Claimed loop | **Actual loop** | Claimed repo access | **Actual repo access** | Tools actually available |
|---|---|---|---|---|---|
| **Aider** | ~30 steps | **1 message** — `--message <prompt>`, non-interactive, exits after one turn | yes | **none** — `--no-git`, temp dir containing a single `issue.md` | edit `issue.md`; nothing else exists |
| **OpenHands** | ~30 steps | **8** — `OPENHANDS_MAX_ITER` default `8` | yes | **none** — `runtime = "local"`, empty temp workspace | CodeAct tools, pointed at an empty directory |
| **SWE-agent** | ~30 steps | **10** — `SWEAGENT_MAX_STEPS` default `10` | yes | **none** — bare `python:3.12-slim`; source comment: *"no repo needed"* | shell in a container with no source |
| **Zero-Shot (Raw LLM)** | 1 call, no agent tools | 1 call | — | none | none — **claim is accurate** |

Three separate inaccuracies:

1. **Repository access: none of the three have it.** No enhancer can "analyze the codebase" or
   "identify relevant source files" — there is no codebase in scope. Any file reference an
   enhancer emits is generated from the issue text alone.
2. **Loop depth is 1, 8 and 10 — not ~30.** The stated figure overstates every enhancer, most
   severely Aider.
3. **Aider-as-enhancer is not an agent loop at all.** `aider --message <prompt> issue.md --no-git`
   is a single non-interactive LLM edit of one file.

Point 3 undermines a load-bearing contrast in the paper. RQ1 presents "the three agentic
enhancers" as *the controlled comparison* — "identical ~30-step agent loop, model held fixed" —
set against the zero-shot enhancer as a single-prompt reference. But **Aider is, operationally,
also a single prompt.** The agentic/zero-shot distinction collapses for one of the three, and the
three "identical loop" conditions are in fact 1, 8 and 10 steps.

`hints_text` is also listed in the enhancer prompt as `## Hints (files changed in fix)`, but the
runner calls `fn(inst)` with one argument so `changed_files` is always `""`, and 0 of 382 dataset
records carry `pr_files`. That channel was dead in every run.

## Solvers — the claims hold

| Agent | Claimed | Actual | Verified in logs |
|---|---|---|---|
| **OpenHands solver** | ~30-step loop with repository access | `OH_SOLVER_MAX_ITER` default **30**; per-instance RepoLaunch image; repo checked out at the target commit at `/testbed`; 1800 s timeout | ✔ `Tools updated for agent CodeActAgent, total 7: ['execute_bash', 'think', 'finish', 'browser', 'execute_ipython_cell', 'task_tracker', 'str_replace_editor']` |

Confirmed by inspecting the image directly — `/testbed` contains the full source tree
(e.g. 41 `.py` files for `adbar__trafilatura-808`). The solver's task prompt is standard
SWE-bench framing: *"cd /testbed, analyze the codebase, create a script to reproduce, edit the
source, verify your fix"*, submitting via `git diff`.

**Are the tools used?** Yes. GPT-5-mini's submissions are median 1.2 KB touching a single correct
file — impossible without reading and navigating the source. Conversely the weak-model failure
modes (`AgentStuckInLoopError`, iteration exhaustion) are precisely the signature of an agent
*using* a tool loop and failing to converge in it.

## Summary

**The solvers are exactly what the paper says they are: real SWE-bench-style agents with full
repository access and a 30-step loop. The enhancers are not.** They are text-to-text rewriters
with loop depths of 1–10 and no repository at all.

This is a factual error in the experimental description, not a framing preference, and it must be
corrected before submission. The measured null is still real — but it is a null about **text-only
rewriting**, which is a substantially weaker claim than the one the paper advances.

The `repo_grounded` enhancer added on 2026-08-24
([repo_grounded_enhancer.py](../../src/enhancers/ready_to_use/repo_grounded_enhancer.py)) is the
first enhancer that actually matches the description: same container as the solver, repo at
`/testbed`, same toolset, no oracle.

## Recommended corrections
1. §Methodology: state the true loop depths (1 / 8 / 10) and that these enhancers operate on the
   issue text **without** repository access.
2. §Introduction: reframe "an enhancement agent can analyze the codebase" as the *motivating
   hypothesis*, and note explicitly that the ready-to-use enhancers as configured do not do this.
3. RQ1: stop describing the three as an "identical ~30-step loop" controlled comparison; Aider is
   single-shot, so it belongs nearer the zero-shot reference.
4. Scope the RQ1 null to text-only enhancement, and report the repo-grounded result separately.
