# Project Status — TSE paper (living document)

**Last updated:** 2026-09-10
**Repo:** `main` in sync with `origin/main` (github.com/pouyafath/BenchmarkLLMAgent)

---

## 1. Goal

**Research question.** Does an *enhancer agent* that rewrites a GitHub issue report improve a
downstream *solver agent*'s ability to produce a correct fix — measured extrinsically, by whether
the patch passes the repository's tests, not by any text-quality score?

**Thesis as originally designed.** Enhancer agent + solver agent — both with full repository
access — beats solver agent alone.

**What is established.** The answer is a firm no, and the experimental programme is closed. The
repo-grounded version of the thesis was the last open form of it and was tested in full: enhancement
is statistically indistinguishable from re-running the solver with a different random seed. This
survives both objections a reviewer can raise, namely that the enhancers were deleting the
reporter's text and that the metric was not measuring fixing. Details in
[`analysis/final_results_2026-09-03.md`](analysis/final_results_2026-09-03.md).

**Target venue:** IEEE TSE. Draft: `papers/drafts/TSE_BenchmarkLLMAgent_2026.tex` (10 pages,
compiles clean, one figure and nine tables).

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

### Matrix re-run with working enhancers (2026-08-25 → 31)
The three ready-to-use enhancers were repaired to match the paper's description and the matrix
re-run on 80 instances (two disjoint 40-instance samples).

- **Run 1** gave valid `baseline` and `enh:swe_agent` cells (74/80 enriched). All six scored; all
  six null. Closest is enh:swe_agent → OpenHands at 9 rescues of 29 against 5.8 expected, p=0.106.
- **Run 3** added openhands (39/40, 38/40), trae (40/40) and mini-SWE-agent (39/40, 40/40).
  16 of 18 cells scored before a harness hang.
- **Run 4** repaired those enhancements to append-only and re-solved, reusing the enhanced rows
  rather than paying for enhancement again.
- Aider was **dropped**: median 1147s per instance, max 2927s, and half still timed out at a 1800s
  budget. The cost is its repo map, not I/O (export is 6.6s). Worth reporting as a practical limit.

### Enhancers rewrite rather than augment
Across 236 successful enhancements, **one** preserved the original verbatim and **one** retained
≥90% of the original's substantial lines. Median length ratios 1.11× / 1.43× / 0.69×, so this is
not summarisation: trae returns longer text while dropping most of the reporter's lines. Every
enhancement condition therefore changes two things at once, which is now recorded as a construct
threat in the draft. `enforce_append_only()` is applied centrally so the treatment isolates added
context.

### Table 1 fully verified
All twelve cells and all nine McNemar p-values reproduce exactly from the stored patches, after
recovering 74 instances whose scoring artifacts had been lost. The recovery independently produced
the 15 OpenHands and 30 Aider resolves implied by the published table. **The paper's headline table
is sound**; the discrepancy chased earlier was an artifact of a partial reconstruction.

### F2P is blocked on label quality, not missing data
F2P labels exist for 225/279 instances but do not resolve to runnable tests: 600 of 650 gold-probe
reports have no F2P labels at all, and where they resolve the gold patch itself fails 15/50. On the
9% of evaluations where F2P is testable, 6 of 20 P2P-credited solves also pass F2P. Re-deriving
labels from execution is the fix and needs no solver time.

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

**Nothing.** All experiments are complete and every result is committed. The GPU footprint is
capped at three of the server's eight cards (see `scripts/ops/start_private_ollama.sh`).

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

Ordered by what actually gates submission.

1. **RQ3 needs human coding.** The section still reads "(Qualitative analysis in progress)" with a
   preliminary finding box, which cannot be submitted. Everything machine-preparable is done: a
   90-item stratified sample (seed 42, 10 per enhancer x outcome cell), a codebook of 7 pattern and
   5 failure-mode codes, and the automated signal columns. See
   [`analysis/rq3/RQ3_PREPARATION.md`](analysis/rq3/RQ3_PREPARATION.md). The paper promises two
   independent coders and Cohen's kappa; using an LLM for either pass is a methodological decision
   that has to be disclosed, and on a paper whose contribution is measurement rigour that trade is
   worth making deliberately.
2. **Revoke 16 GitHub tokens.** They were hard-coded in four tracked files and pushed on 2026-06-02.
   The files are fixed (`9eaec77b1`), but rewriting HEAD does not remove them from the published
   history, so the tokens themselves are still live until revoked at github.com/settings/tokens.
3. **Publish the replication package.** `scripts/release/build_artifact.sh` assembles it and
   [`REPRODUCE.md`](REPRODUCE.md) maps every table and figure to the command that regenerates it.
   The abstract and conclusion promise a release, so a DOI has to exist before submission.
4. **Author metadata and acknowledgements** in the manuscript.

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
