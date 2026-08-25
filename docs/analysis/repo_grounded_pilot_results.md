# Repo-grounded enhancer — pilot results (2026-08-25)

First test of the paper's actual thesis: an enhancer agent with **the same repository access as
the solver** (per-instance container, repo at `/testbed`, same toolset, no oracle), versus
solver-alone.

## Design

5 issues, chosen for **maximum headroom**: provably solvable (GPT-5-mini resolves them) and
Qwen3-32B failed them at baseline *without* a timeout — i.e. genuine localization failures.

**Both arms run fresh in the same run.** The sample was selected on baseline failure, so scoring
against the remembered 0/5 would have manufactured a win through regression to the mean. This
precaution mattered: Qwen3-32B's fresh baseline came in at **1/5**, not 0/5.

Solver cap 30, enhancer cap 20 (the default at the time; now unified to 30).

## Results

| | ITT (n=5) | Per-protocol | helped-flips |
|---|---|---|---:|
| **GPT-5-mini** | 5/5 → 4/5, **Δ −1** | 4/4 → 4/4, **Δ 0** | **0** |
| **Qwen3-32B** | 1/5 → 1/5, **Δ 0** | 1/3 → 1/3, **Δ 0** | **0** |

**Across both models, not one instance went unresolved → resolved.** Zero rescues out of 10
model-instance pairs.

### The one flip was untreated
GPT-5-mini's Δ−1 comes entirely from `LearningCircuit-3024`, where the enhancer produced no output
so the "enhanced" arm ran the **identical original text** — and flipped resolved → unresolved
anyway. Same text, same model, same solver, different outcome. This is the resample phenomenon
observed **directly**, rather than inferred from the null model (ratio 3.16 vs 3.01 predicted).

## The enhancements were good — that is what makes this informative

This is not a case of the enhancer doing a poor job:

| Model | enhanced | append-only held | references verified | enrichment |
|---|---|---|---|---|
| GPT-5-mini | 4/5 | 4/4 | 3/3, 4/4, 4/4, 3/3 | 3.0–6.9× |
| Qwen3-32B | 3/5 | 3/3 | 1/1, 2/2, 6/6 | 1.9–2.6× |

**Zero hallucinated file paths across both models.** The original survived verbatim every time. The
outputs cite real functions with real line numbers and real code excerpts — the smoke test found
`src/crewai/agent.py::BaseAgent.execute_task`, the exact file the gold patch touches.

So a well-formed, repo-grounded, verified, append-only enhancement produced **zero rescues**.

## Interpretation

Consistent with the information-asymmetry account
([why_enhancement_fails_and_what_could_work.md](why_enhancement_fails_and_what_could_work.md)):
the solver already has the repository and the tools to search it. Telling it what is in the
repository adds nothing it could not obtain itself — even when the telling is accurate, verified
and well-structured. The enhancer performs localization work the solver simply redoes.

A secondary finding: **the capability cliff appears in the enhancer role too.** Qwen3-32B completed
the enhancement task on 3/5 versus GPT-5-mini's 4/5, and enriched less deeply (1.9–2.6× vs
3.0–6.9×). Sustaining a long tool-using task is the bottleneck regardless of which role the agent
occupies.

## What this does NOT establish

**n = 5. This is a pilot, not a powered test.** With 4 available rescues for Qwen3-32B and 0
observed, the 95% CI on the rescue rate still spans roughly 0–50%. A real effect of moderate size
could not be detected at this sample size.

GPT-5-mini additionally had **no headroom by construction** (baseline 5/5), so its arm can only
test "does it do harm". It did not — worth noting, since the *text-only* enhancers cost GPT-5-mini
two solves on the g5s20 sample (20 → 18).

## Next step
Scale to a sample with real headroom and enough power: the 20-issue g5s20 set with Qwen3-32B, whose
fresh baseline leaves ~13 rescuable instances. If repo-grounding rescues none of those either, the
null generalises from text-only to repo-grounded enhancement — which is a **stronger** paper, since
the redundancy argument becomes a demonstrated result rather than a conjecture.

## Artifacts
- `runs/rge_gpt5mini_20260824_235607/` · `runs/stage6_sample_rge_gpt5mini/result.json`
- `runs/rge_qwen3_20260824_234916/` · `runs/stage6_sample_rge_qwen3/result.json`
- Sample: `.secrets/sample5_rge.txt`
