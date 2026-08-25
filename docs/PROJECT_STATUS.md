# Project Status — TSE paper (living document)

**Last updated:** 2026-08-25
**Repo:** `main` in sync with `origin/main` (github.com/pouyafath/BenchmarkLLMAgent)

---

## 1. Goal

**Research question.** Does an *enhancer agent* that rewrites a GitHub issue report improve a
downstream *solver agent*'s ability to produce a correct fix — measured extrinsically, by whether
the patch passes the repository's tests, not by any text-quality score?

**Thesis as originally designed.** Enhancer agent + solver agent — both with full repository
access — beats solver agent alone.

**What is actually established so far.** For **text-only** enhancement (no repository access), the
answer is a firm no: enhancement is statistically indistinguishable from re-running the solver with
a different random seed. The repo-grounded version of the thesis is **being tested now** and has
never been tested before.

**Target venue:** IEEE TSE. Draft: `papers/drafts/TSE_BenchmarkLLMAgent_2026.tex` (9 pages,
compiles clean).

---

## 2. Where the results stand

### Established (safe to report)
- **RQ1 null.** Across the controlled enhancer × solver matrix (Qwen3-32B, 279 gold-evaluable
  issues), no enhancer improves fix correctness for any solver; all McNemar p ≥ 0.489.
- **Robust to model capability.** Holds from Mixtral-8×7B up to GPT-5-mini — 19 models, Δ ∈ [−4, +2]
  as published, [−2, +2] counting only genuine patches.
- **Robust to dilution.** Per-protocol deltas (excluding instances where enhancement silently
  failed — 20.1% for the OpenHands enhancer) match intention-to-treat: +7→+5, −8→−6, −8→−8.
- **Solver capability dominates**: Aider 44% ≫ OpenHands 22% ≫ SWE-agent 6%.
- **Mechanism — the capability cliff is about *submission*, not fix quality.** GPT-5-mini emits a
  well-formed patch 20/20; every other model emits none on 13–20 of 20, dying by stuck-in-loop or
  iteration exhaustion. Not tool-calling (GPT-4.1-mini is native and still 19/20 empty), not code
  specialisation.
- **Enhancement ≡ resample.** P(fix\|failed)=12.9% vs P(break\|passed)=40.8%; ratio 3.16 against
  3.01 predicted by a pure-resample null (4.9% off). Net −8 over 1,674 paired trials.
- **Best-of-2 is worth +9.7 points** where enhancement is worth −0.5. Same compute, spent on a
  second attempt instead of a rewrite.
- **GPT-5-mini on unbiased random-20**: 11/20 → 10/20, Δ−1. Its 55% matches its 56% on the full
  279, so its dominance is not a selection artifact.

### Known problems in the current draft (must fix before submission)
1. **Methodology misstates the enhancers.** The paper says the three ready-to-use enhancers are
   "each a ~30-step agent loop given the issue and repository access". None had repository access;
   loop depths were 1 (Aider — a single non-interactive message), 8 (OpenHands) and 10 (SWE-agent).
   Code is now fixed; the **prose is not**. See `analysis/agent_tool_access_audit.md`.
2. **Δ-range claim.** Reported as −4 to +2; on genuine patches only it is **−2 to +2**. Llama-3.3-70B's
   Δ−4 rests on four non-applying submissions and should not be used as the illustrative example.
3. **Scope of the null.** It is a null about *text-only rewriting*. The draft advances it as a claim
   about issue enhancement generally.
4. **Δ is single-seed.** Qwen3-32B's Δ flips sign on rerun (−1 published vs +2 fresh).

---

## 3. Running right now

**Nothing is running.** Both repo-grounded pilots completed 2026-08-25.

### Repo-grounded pilot result (n=5, underpowered)
| | ITT | Per-protocol | helped-flips |
|---|---|---|---:|
| GPT-5-mini | 5/5 → 4/5, Δ −1 | 4/4 → 4/4, Δ 0 | **0** |
| Qwen3-32B | 1/5 → 1/5, Δ 0 | 1/3 → 1/3, Δ 0 | **0** |

Zero rescues across 10 model-instance pairs, despite the enhancements being verified,
append-only and correctly grounded (0 hallucinated paths). GPT-5-mini's single flip was an
**untreated** instance — same text, different outcome — the resample effect observed directly.
Full write-up: `analysis/repo_grounded_pilot_results.md`.

**Design.** 5 issues, chosen as provably solvable (GPT-5-mini resolves them) where Qwen3-32B failed
at baseline *without* a timeout — maximum headroom. **Both arms run fresh in the same run**, because
the sample was selected on baseline failure and comparing against a remembered 0/5 would manufacture
a win through regression to the mean. Sample: `.secrets/sample5_rge.txt`.

Monitors are armed on both; results land as milestones.

**Paused to free GPUs:** the seed-2 replication queue (Qwen3-32B random-20, Qwen2.5-32B seed 2,
GLM-4.7-flash seed 2). ~28 min of work lost, fully re-runnable. Script:
`scratchpad/run_queue.sh`.

---

## 4. What changed in the pipeline (2026-08-24/25)

- **`repo_grounded_enhancer`** — new. Gets the same container as the solver (repo at `/testbed`),
  no oracle, append-only, every cited path verified against `git ls-files`.
- **The three ready-to-use enhancers now match the paper's description**: instance container,
  repo at `/testbed`, repo-aware prompts. Aider gets the repo materialised via `docker cp` with git
  enabled so its repo map works.
- **All agent budgets unified to 30** — see `analysis/agent_iteration_budget.md`.
- **`score_sample.py` restored** (the doc referenced a deleted file, so the headline experiment was
  not reproducible) plus `data/stage6_all279_methods.json`.
- **Fixed a latent scoring bug**: harness crashes were silently scored as unresolved. Audited —
  0 occurrences across 36 historical evaluations, so no published number is affected.
- **Two live API keys removed** from tracked scripts; GitHub token removed from `.git/config`.

---

## 5. Next steps

**Blocked on the running pilots**
1. Score both repo-grounded pilots and decide whether repo-grounding moves the needle at all.
2. If it does → scale to the g5s20 set (20 issues) and then a full matrix re-run with the three
   fixed enhancers, which is what would let the paper's Table 1 stand as described.
3. If it does not → the null generalises from text-only to repo-grounded enhancement, which is a
   **stronger** paper: the redundancy argument (the solver already has the repo) becomes the
   headline rather than a conjecture.

**Independent of the pilots**
4. **Rewrite the paper** — agreed to do this after the runs finish. Fix the four problems in §2.
5. **RQ3** — the only unstarted RQ. Sample, codebook and first-pass signal are ready in
   `docs/analysis/rq3/`; needs two humans to code 90 items, Cohen's κ, pattern × outcome cross-tab.
6. **Seed-2 replication** — restart the paused queue to convert "Δ flips sign" from an anecdote
   into a measured variance.
7. **Budget experiment** — cap 15 with 2 samples vs cap 30 with 1, at equal compute. Cheap, and a
   real contribution.

**Housekeeping**
8. Rotate the exposed GitHub OAuth token and the OpenAI key still embedded in `runs/**/config.toml`.
9. Reap leaked OpenHands runtime containers after each run (the pipeline leaks them reliably).

---

## 6. Key documents

| Path | What it holds |
|---|---|
| `docs/analysis/why_enhancement_fails_and_what_could_work.md` | The diagnosis: information asymmetry, resample evidence, best-of-2, ranked fixes |
| `docs/analysis/agent_tool_access_audit.md` | Claimed vs actual tools for every agent |
| `docs/analysis/agent_iteration_budget.md` | Why 30, uniformly |
| `docs/why_gpt5_outperforms_open_models_20260824.md` | Trajectory forensics; the P2P-only validity finding |
| `docs/multimodel_capability_spread_experiment.md` | The 19-model capability spread |
| `docs/analysis/rq3/` | RQ3 sample, codebook, preparation notes |
| `docs/weekly_report_2026-08-18.md` | Last weekly report |

## 7. Operational notes
- **Shared server.** `CONCURRENCY_BUDGET.md` is binding: ≤4 solver workers, ≤4 containers, never
  two solver scripts at once (GPU contention — does not apply to API-only models). A past violation
  crashed the box and needed an admin reboot.
- Private Ollama on `:11435` (single pinned model), shared on `:11434` (multi-load).
- Scoring is Docker-only and costs no API credit. Both g5s20 and random-20 are subsets of the
  279-instance GPT-5-mini run, so GPT-5-mini numbers on either need **no new API spend**.
