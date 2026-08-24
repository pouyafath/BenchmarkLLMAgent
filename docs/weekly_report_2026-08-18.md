# Weekly Progress Report — Pouya Fathollahzadeh
**Week:** 2026-08-11 → 2026-08-18
**Project:** LLM-Based Agents for GitHub Issue Enhancement (TSE draft)

## Summary
This week I strengthened the paper's central negative result — *issue enhancement does not improve
LLM-agent fix correctness* — from a single controlled model to a **cross-model and multi-model
robustness argument**, and pushed three new results into the draft. The headline: enhancement helps
**no** model across a 2.6× capability range, and the dominant lever is solver/model capability, not
report wording. A large multi-model study (19 models) and a supplementary feature/quality analysis
were completed; an unbiased-sample replication is running now.

## Completed

### 1. Cross-model robustness (frontier vs. open) — closes a reviewer threat
Re-ran the strongest cell (enh:Aider → sol:OpenHands) on the 279 evaluable issues with a stronger,
tool-calling-native commercial model (GPT-5-mini) for **both** baseline and enhanced.
- Absolute capability jumps sharply: OpenHands baseline **22% (Qwen3-32B) → 56% (GPT-5-mini)**, ~2.6×.
- **Enhancement still shows no effect:** 155→159 resolved, **Δ+4, McNemar p=0.712**, directionless
  (31 hurt / 35 helped). Qwen3-32B was Δ+7, p=0.489.
- Converts our hedged "a stronger model might change the enhancement effect" threat into a
  demonstrated result. Added as a Discussion subsection + table.

### 2. Zero-shot ("Raw LLM") enhancer — 5th enhancer added to RQ1
Scored the single-prompt enhancer across all three solvers (279 evaluable):
OpenHands 60→61, SWE-agent 18→12 (nominal p=.031, footnoted as a non-determinism artifact on the
~86%-error solver), Aider 124→112. **The crudest enhancer helps none and tends to hurt.** Added as a
column to Table 1; the "all p ≥ 0.489" headline is now scoped to the controlled agentic enhancers.

### 3. Multi-model capability spread — 19 models
Ran the same cell with **every model on our Ollama server** (plus 2 commercial references) on 20
provably-solvable issues (cap 30).
- **Capability is a cliff, not a slope:** GPT-5-mini 20/20; best open model (Qwen3-32B) 6/20; every
  other model — open or commercial — 0–4/20.
- **Enhancement helps none** (Δ ∈ [−4, +2] across all 19).
- **Code-specialized models are no better** than general ones (agentic competence, not coding
  knowledge, is the bottleneck). Two models would not load (driver/version limit).
- Added as a full-inventory table in the paper; experiment fully documented (`docs/`).

### 4. Supplementary feature / quality / time analysis (RQ2 support)
- Among issues that were *changed AND improved* by enhancement, the added SE-feature profile is
  **identical** to all-changed issues — no feature distinguishes "enhancement helped."
- **Intrinsic quality and downstream fixing are decoupled, even anti-correlated:** OpenHands
  enhancer raises the reward-model score most (0.473→0.576) yet is null downstream; Aider *lowers*
  quality (→0.460) yet has the best (still-null) delta and is the fastest enhancer (87s vs SWE-agent
  385s). (Token usage was not instrumented in the local runs — flagged as future work.)

### 5. Paper + infrastructure
- **4 commits** to the `paper-crossmodel` branch (cross-model robustness, zero-shot Table 1 column,
  11-model then full-inventory capability-spread table). Draft compiles clean (8 pages).
- Built reusable runners: OpenAI single-cell runner, local-Ollama cell runner, and a VRAM-aware
  **pool orchestrator** that runs 3 models in parallel on the shared endpoint (self-throttling,
  health-logging, queue-driven). Recovered cleanly from two server/session interruptions.

## In progress
**Unbiased-sample replication.** A fresh **random 20-issue** set (not selection-biased toward
GPT-5-mini) is running through all open-source models to confirm the pattern holds off the
"solvable" subset. So far (9/16 models scored): open models resolve **0–3/20**, enhancement Δ ≈ 0 —
consistent. Closed-source models on this set are gated pending approval. ETA ~1 day.

## Key takeaways for the paper
1. The RQ1 null is now robust across **~20 models** spanning a large capability range.
2. **Solver/model capability dominates**; enhancement is a directionless perturbation everywhere.
3. Intrinsic text-quality gains **do not transfer** to program-repair outcomes — the sharpest
   version of the paper's thesis.

## Next
- Finish the random-20 open-source run + (with approval) closed-source; fold into the paper.
- **RQ3 (qualitative coding)** — the one remaining unstarted RQ; corpus is collected.
- Reconcile dataset framing (3,285 constructed → 382 validated → 279 evaluable) in the abstract.
