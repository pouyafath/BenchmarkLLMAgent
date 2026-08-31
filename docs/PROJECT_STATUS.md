# Project Status — TSE paper (living document)

**Last updated:** 2026-08-31
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

**targeted-60 v2** — the localisation experiment, pre-registered in
`analysis/targeted_localisation_prereg.md`. 60 instances that Qwen3+OpenHands fails at baseline and
that some condition somewhere has solved. ETA ~2h. A first attempt on 2026-08-28 returned 0/60 in
both arms and was discarded: it was launched as a fifth concurrent job, the box reached 209
containers against a budget of 4, and 115 solver runs timed out.

Guards added so that cannot recur unattended: a load guard in all three runners (refuses above 60
containers), a container reaper on a 14h bound, and a 5400s cap on the evaluation harness call.
The harness hangs intermittently — three occurrences, one of 45h on a single cell — and an
unbounded `subprocess.run` let one hang stall every downstream job.

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
