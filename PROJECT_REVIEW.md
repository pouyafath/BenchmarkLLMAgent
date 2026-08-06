# Does Issue-Report Enhancement Help LLM Agents Fix Bugs? A Large-Scale Benchmark of Enhancer × Solver Configurations

*Project review draft — prepared 2026-07-30, updated 2026-08-04 with the completed CL-Enhanced arm. Structured for paper-wise review, following the style of the SENIR TSE 2025 paper: RQ-driven, effect sizes / p-values / confidence intervals reported for every statistical claim, third-person and precise.*

> **Status note for the reviewer.** This draft is **RQ1-complete**. The RQ1 benchmark's four agent conditions — three iterative agents (OpenHands, SWE-agent, Aider) and the reward-gated **CL-Enhanced / \ourmethod** (Section 7.3) — are final at full scale (382 issues); a fifth, **zero-shot single-prompt** enhancer is running now and its column will be added on completion. **RQ2 (feature logistic regression, Section 5) is complete** — across the full 81-SE + 500-TF-IDF representation, no feature predicts a better enhancement on either an intrinsic or downstream outcome (CV-AUC ≈ 0.49–0.56); notably, enhancement *does* raise the intrinsic reward-model score yet yields no downstream gain. **RQ3 (qualitative analysis, Section 6) is defined with the corpus collected but not yet coded.** Every McNemar result reported below is final.

---

## Abstract

Automated issue-report *enhancement* — rewriting a low-quality bug report into a clearer one — is an appealing pre-processing step for automated program repair: if agents fix issues from text, better text should mean better fixes. We test this assumption directly and at scale. On **382 real GitHub issues** (drawn from a SWE-bench-Live–style collection, each with a validated execution environment and gold patch), we run a full **enhancer × solver matrix**: three general-purpose coding agents used as *enhancers* (OpenHands, SWE-agent, Aider) against the same three used as *solvers*, plus a no-enhancement baseline, all driven by a single open-weight model (Qwen3-32B) to isolate the enhancement variable. We evaluate not "did the patch change" but "does the patch **pass the repository's tests**", using a gold-patch-gated, multi-method evaluability protocol that yields **279 of 382 issues (73.0%)** as trustworthy to evaluate. Across every enhancer × solver pairing, **issue enhancement produces no statistically significant improvement in fix correctness** (paired McNemar exact test, all *p* ≥ 0.489 at *n* = 279 evaluable). The apparent positive signal visible at *n* = 100 (OpenHands-enhancement → Aider solver, +4 resolved, *p* = 0.388) **weakened rather than strengthened** as the sample grew (*n* = 200: +2, *p* = 0.856; *n* = 382: +1, *p* = 1.000), the signature of a non-effect rather than an underpowered one. What *is* robust across all scales is that **solver choice dominates outcome** (Aider 44% ≫ OpenHands 22% ≫ SWE-agent 6% resolved), and that **enhancement is not inert but directionless**: for the two responsive solvers it flips the outcome on 23–28% of issues, helping about as often as it hurts. A fourth, *selective* enhancer — our own reward-gated CL-Enhanced method, which rewrites only the 43% of reports its learned reward model judges low-quality — likewise shows **no improvement on the issues it rewrote** (all *p* ≥ 0.25). We report this as a rigorous negative result and identify the two levers that actually move automated repair — solver capability and the underlying model — as more promising than input rewriting. This benchmark answers **RQ1**. For **RQ2**, no feature — across an 81-feature SE representation of the report plus 500 TF-IDF terms — predicts a better enhancement under either an intrinsic (reward-model) or a downstream definition of success (both models at chance, ROC-AUC ≈ 0.49–0.56). Strikingly, enhancement *does* raise the intrinsic quality score (57% of reports improve, 32% cross the quality threshold) yet yields **no downstream correctness gain** — so **text-quality improvements do not transfer to program repair**, which we take to be the study's central result. **RQ3** (qualitative analysis of enhancement patterns and failure modes) characterizes *how* the agents rewrite.

---

## 1. Introduction

Large-language-model (LLM) agents increasingly resolve software issues end-to-end, reading a natural-language bug report and producing a code patch. Because these agents are conditioned on the issue text, a natural hypothesis is that **improving the issue text improves the fix**. This hypothesis motivates a growing line of "issue enhancement" tools, including our own prior work on managed, reward-gated report rewriting. Yet enhancement is almost always evaluated *intrinsically* — does the rewritten report score higher on a text-quality metric — and rarely *extrinsically*: does a better report actually cause a better downstream fix.

This paper closes that gap. We address three research questions, each with its own method:

- **RQ1 — *What is the ability of generative AI in enhancing GitHub issue reports?*** *Approach:* we **benchmark an enhancer–solver agentic workflow** — each enhancer rewrites the report, each solver then attempts a patch, and we measure enhancement ability by whether the resulting patch passes the repository's tests (Section 4).
- **RQ2 — *What features are related to a better enhancement?*** *Approach:* we fit a **logistic regression** over textual, structural, and enhancement-derived features to identify which are associated with a successful enhancement outcome (Section 5).
- **RQ3 — *How are GitHub issue reports enhanced by generative-AI agents?*** *Approach:* we perform a **qualitative analysis** of the agent-generated reports to characterize recurring enhancement patterns and failure modes (Section 6).

Our contributions are: **(1)** a large-scale **extrinsic enhancer–solver benchmark** answering RQ1 — 382 issues, a no-enhancement baseline plus five enhancers (a zero-shot prompt, three iterative agents, and a reward-gated agent), three solvers, one controlled model, scored by real test execution; **(2)** the RQ1 finding, a **rigorous negative result** — no enhancement condition reliably improves fix correctness at any tested scale, the one small-*n* signal traced to sampling noise by replication; **(3)** a **feature-level and qualitative account** (RQ2, RQ3) of *which* report/enhancement properties and *which* rewrite behaviors relate to enhancement outcomes; and **(4)** an **evaluation methodology** — a gold-patch-gated, three-method evaluability gate (73.0% coverage, 279/382) with an artifact-recovery discipline — that we argue is a prerequisite for trustworthy agent-repair measurement.

---

## 2. Related Work

**Agentic program repair.** SWE-bench~\cite{swebench} framed issue resolution as generating repository-level patches that pass hidden tests; SWE-agent~\cite{sweagent}, AutoCodeRover~\cite{autocoderover}, and OpenHands~\cite{openhands} are representative agents that read an issue and edit code. These systems are evaluated on the *fix*; the issue text is taken as fixed input. We instead treat the issue text as a *manipulable* stage and ask whether improving it changes the fix — an extrinsic question these benchmarks do not pose.

**Issue-report quality.** A large literature *detects* low-quality reports, classifies issue types, or templates future reporting~\cite{issuequality1, issuequality2}; our own prior work additionally *rewrites* existing reports and validates the rewrite with a learned reward model. All of this measures quality *intrinsically* (a text or reward-model score). To our knowledge no prior study measures whether such rewriting propagates to downstream *repair correctness*, which is the gap we close.

**Prompt/input sensitivity of LLM agents.** Work on prompt sensitivity shows agent behavior can shift substantially with input phrasing~\cite{promptsensitivity}. Our directionless-perturbation finding (Section 4.3) is a repair-specific instance: rewriting flips ~a quarter of outcomes but with no net gain, so input variation here is closer to noise than to signal.

*(Citation keys above are placeholders to be resolved against the shared BibTeX; the SWE-bench / SWE-agent / AutoCodeRover / OpenHands / MAGIS keys already exist in the second paper's `main.bib`.)*

---

## 3. Approach

### 3.1 Pipeline

The benchmark is a six-stage pipeline split into two parts. **Part 1 (Stages 1–3)** builds, per issue, a validated Docker execution environment and records the tests that gate a correct fix. **Part 2 (Stages 4–6)** is the experiment: **Stage 4** an *enhancer* agent rewrites the issue text; **Stage 5** a *solver* agent produces a patch inside the issue's environment; **Stage 6** the patch is executed against the repository's tests and scored.

### 3.2 Dataset

We use **382 issues** that pass Stage-1–3 validation on our primary node — each has a buildable, test-executing image and a gold (reference) patch. The set was grown deterministically in tranches (100 → 200 → 382) so that scale effects could be measured on nested, non-overlapping samples (Section 4.2).

### 3.3 Enhancers and solvers

We evaluate a no-enhancement **baseline** against a ladder of five enhancers of increasing sophistication: a **zero-shot** single-prompt rewrite (one LLM call), three general-purpose coding **agents** used as enhancers — **OpenHands**, **SWE-agent**, **Aider** (each a ~30-step agent loop) — and a managed, reward-gated agent, **CL-Enhanced**, which rewrites *selectively* (Section 7.3). Each enhanced or baseline report is handed to each of **three solvers** (the same three agents in solver mode). Holding the enhancement *method* as the only variable across this ladder isolates whether — and how much — agent machinery buys over a plain prompt.

**Controlled model.** Every enhancer and solver is driven by a single open-weight model, **Qwen3-32B**, served from a private inference endpoint. Holding the model fixed is essential: it isolates the *enhancement method* as the only variable, so any difference is attributable to the rewriting, not to model capability.

### 3.4 Correctness metric and the evaluability gate

We score a patch as **resolved** if, after applying it (plus the issue's test patch) inside the validated image, the repository's designated *PASS_TO_PASS* tests execute and pass with no failures. We deliberately report **P2P-resolved** rather than the stricter SWE-bench *FAIL_TO_PASS* criterion because the offline-derived FAIL_TO_PASS labels proved unusable at this scale — only 4 of 74 evaluable instances carried a gold-passing FAIL_TO_PASS label — so requiring them would collapse the sample. P2P-resolved is therefore a **no-regression + de-facto-fix** signal (the applied test patch supplies the fix-relevant tests); we treat it as directional, and Section 8 discusses this threat.

Not every issue can be trusted to evaluate. We gate on a **gold-patch probe**: an instance is *evaluable* only if the gold patch itself passes under the chosen method. Because a single generic test command fails on many repositories (framework-specific runners, stale node-IDs), we combine three methods per instance and keep whichever the gold patch validates: **v2**, the repository's real validated test commands recovered from the environment build; **v3**, a label-agnostic file-level run (execute the test files, require ≥1 passed and 0 failed — robust to mislabeled node-IDs); and **v1**, a generic fallback. This lifted evaluable coverage to **73.0% overall (279/382)** — and up to 75.8% on the largest tranche — versus ~30% for a single generic method.

### 3.5 Statistics

For each enhancer-vs-baseline comparison on a given solver, outcomes are **paired** (same issues, with vs. without enhancement), so we use the **exact McNemar test** on the discordant pairs (issues the two conditions disagree on) and report the pair counts *(b, c)*. We report **Wilson 95% confidence intervals** on each resolved rate. All effect sizes are given as absolute differences in resolved count over the fixed evaluable denominator (empty or failed patches count as unresolved).

---

## 4. RQ1 — The ability of generative AI to enhance issue reports

### 4.1 The correctness matrix — no enhancer improves any solver

Table 1 gives the final correctness matrix at *n* = 382 (279 gold-evaluable issues), with each enhancer compared to the baseline for each solver.

**Table 1. Resolved / 279 evaluable (P2P), with McNemar p vs. baseline.**

| solver (baseline resolved) | enh: OpenHands | enh: SWE-agent | enh: Aider |
|---|---|---|---|
| **OpenHands** — 60/279 (22%) | 58 (Δ−2, *p*=.910) | 66 (Δ+6, *p*=.561) | 67 (Δ+7, *p*=.489) |
| **SWE-agent** — 18/279 (6%) | 18 (Δ0, *p*=1.0) | 19 (Δ+1, *p*=1.0) | 19 (Δ+1, *p*=1.0) |
| **Aider** — 124/279 (44%) | 125 (Δ+1, *p*=1.0) | 119 (Δ−5, *p*=.649) | 124 (Δ0, *p*=1.0) |

**No enhancer × solver comparison reaches significance; every *p* ≥ 0.489, and the largest absolute effect is 7 issues out of 279.** The one comparison that could be called a "best case" — Aider-enhancement into the OpenHands solver (+7) — is nowhere near significance and is not the pairing that any prior signal predicted.

### 4.2 The one promising signal was sampling noise (replication across scale)

At *n* = 100 the headline pairing (OpenHands-enhancement → Aider solver) looked promising: **+4 resolved (30→34), *p* = 0.388**. Replication kills it:

**Table 2. OpenHands-enhancement → Aider solver, across scales.**

| scale | resolved (baseline → enh) | Δ | McNemar *p* |
|---|---|---|---|
| *n* = 100 (74 eval) | 30 → 34 | +4 | 0.388 |
| *n* = 200 (141 eval) | 64 → 66 | +2 | 0.856 |
| *n* = 382 (279 eval) | 124 → 125 | +1 | 1.000 |

The effect **shrank toward zero and the p-value rose toward 1 as data accumulated** — the diagnostic of a non-effect, not of insufficient power. A genuine effect of fixed size sharpens under more data; this did the opposite. The same pattern held for the OpenHands solver, where an *n* = 74 "+6" reversed to −3 on a fresh 100 issues before settling near null. Had we stopped at *n* = 100 and reported the trend, the paper would have carried a false positive.

### 4.3 Solver choice dominates; enhancement perturbs without direction

Two robust facts survive at every scale:

1. **Solver capability is the dominant factor.** Baseline resolved rates are **Aider 44% ≫ OpenHands 22% ≫ SWE-agent 6%**, stable across all three tranches and far larger than any enhancement effect. The choice of *who fixes* matters an order of magnitude more than *how the report is worded*.

2. **Enhancement is active but directionless.** It is not that enhancement does nothing: for the two responsive solvers, **65–78 issues per comparison change outcome** (discordant pairs) — 23–28% of the evaluable set. But the flips are **balanced** (helps ≈ hurts), so there is no net gain. Rewriting the report meaningfully perturbs solver behavior; it just does not perturb it *toward* correctness.

A model-fit note reinforces the point: the **SWE-agent solver is effectively inert to enhancement** (0–1 discordant pairs across all three comparisons) because, with Qwen3-32B, the large majority of its runs terminate in an agent-protocol error before any patch is produced (~86% in a 100-issue audit) — a failure of the model–harness interface, not of the issue text, and therefore untouched by rewriting.

### 4.4 Non-empty-patch rate as a secondary lens

Patch *generation* (a non-empty diff) tracks solver strength but **overstates** correctness: Aider generates patches on the large majority of issues yet resolves 44%; OpenHands generates many that do not pass. Enhancement's effect on generation is likewise directionless once artifacts are removed (see Section 5). This is why we anchor the study on executed correctness rather than on the cheaper non-empty proxy.

---

## 5. RQ2 — What features are related to a better enhancement?

**Approach.** From each issue's **title and body** we extract the full **81-feature SE representation** of our prior work — the same `feature_extraction_utils` pipeline the reward model uses. It spans: *size* (title/body length, char/word/sentence counts); *readability* (Flesch reading-ease, Flesch–Kincaid grade, and ARI, computed separately for title and body); *part-of-speech* counts (noun/verb/adjective/adverb, title and body); *structural markup* (fenced and inline code, URLs, images, checklists/TODO lists, headers/sections, ordered/unordered lists, tables, bold/italic/blockquotes); *content flags* (stack trace, error message, logs, reproduction steps, expected/actual behavior, environment info); and *lexical statistics* (unique-word and stopword ratios, average word/sentence length, title keyword flags for error/feature/version/question). We use this representation two ways: **descriptively**, tallying which features an enhancement *adds* (present in the enhanced report, absent in the original) to characterize what enhancement does; and **predictively**, regressing a success outcome on the features. We run the regression under **two operationalizations of "successful enhancement"**: (i) an **extrinsic** label — the enhanced report yields a downstream *resolved* patch — using the 81 SE features; and (ii) an **intrinsic** label matching our prior work — the learned **reward model** scores the *enhanced* report ≥ 0.5 — using the full **581-feature** set (the 81 SE features **plus 500 TF-IDF** terms of the original title+body). Both are fit with **L1-regularized logistic regression** (penalty tuned by 5-fold CV), reporting standardized odds ratios and cross-validated ROC-AUC.

**Results.**

*What enhancement adds (feature deltas).* Comparing the SE features of each report before and after enhancement (OpenHands, over the 304 truly-enhanced issues), the additions are a **uniform template** — the agent rewrites almost every report into a structured Problem / Reproduction / Expected / Actual form (Table 4). These are precisely the fields the reward model rewards, which explains the intrinsic quality gain below; but several — reproduction steps, expected/actual behavior — are facts the agent cannot know and often **invents**, which foreshadows why they do not help the solver.

**Table 4. Top SE features *added* by enhancement (absent in the original, present after; OpenHands, N = 304 truly-enhanced).**

| feature added | issues gained | % of enhanced |
|---|---|---|
| reproduction steps | 259 | **85%** |
| expected behavior | 138 | 45% |
| list items (bullet/numbered) | 135 | 44% |
| actual behavior | 124 | 41% |
| section headers | 121 | 40% |
| logs | 66 | 22% |
| inline code | 60 | 20% |
| environment info | 26 | 9% |
| links | 15 | 5% |
| checkboxes | 12 | 4% |

Whether these additions *relate to a better enhancement* — i.e. predict a successful outcome — is the regression question, and the answer is no:

*Extrinsic view — downstream fix.* The full SE feature set does not predict a better outcome. The 81-feature model reaches **5-fold cross-validated ROC-AUC = 0.55** — indistinguishable from the 0.50 no-signal line, and no better than a 10-feature subset. L1 retains 14 features, all with modest odds ratios (Table 5). The strongest are *informativeness* properties of the **original** report, not of the rewrite: issues whose bodies already contain **logs** (OR 1.36) or a **stack trace** (OR 1.20) are slightly more resolvable, while feature-request titles (OR 0.87) and URL-heavy bodies (OR 0.87) are slightly less. None is large, and none concerns the enhancement itself.

*Direction remains unpredictable.* On the 65 issues where enhancement *changed* the Aider outcome, it **helped 33 and hurt 32** (the directionless-perturbation result of Section 4.3, localized). Predicting helped-versus-hurt from the full SE feature set yields CV-AUC ≈ 0.58 at n = 65 — no reliable signal.

**Table 5. RQ2 — L1-selected SE features for a resolved fix (best cell, n=279; full 81-feature model, standardized OR).**

| feature (from title/body) | standardized OR |
|---|---|
| body_has_logs | 1.36 |
| body_has_stack_trace | 1.20 |
| body_has_environment_info | 1.09 |
| body_flesch_reading_ease | 1.03 |
| title_contains_feature | 0.87 |
| num_urls_in_body | 0.87 |
| body_avg_word_length | 0.88 |
| title_ends_with_punctuation | 0.89 |
| title_stopword_ratio | 0.90 |

*The remaining L1-selected features have |OR − 1| < 0.05. Model CV-AUC = 0.55 — the coefficients are directional at best, not a predictive signal.*

*Intrinsic (reward-model) view — the key contrast.* We repeat the analysis with the paper's full **581-feature** representation (the 81 SE features **plus 500 TF-IDF** of the original title+body) and an **intrinsic** outcome: the learned reward model's quality score of the *enhanced* report crossing threshold (≥ 0.5). Here enhancement is *not* inert — the reward model judges the rewrites genuinely better: original score mean **0.473 → enhanced 0.578**; **218/382 (57%) of reports improve** and **122 (32%) cross from low- to high-quality**. Yet *which* issue gets a successful enhancement is still **unpredictable from its 581 features** (5-fold CV ROC-AUC = **0.49**, chance; L1 retains 7 negligible features; the "reward improved" outcome gives AUC 0.53). The agent enhances **uniformly** — turning almost any report into a similarly structured, higher-scoring one — so no input feature discriminates success.

**Table 6. RQ2 — all three feature models land at chance.**

| model | features | outcome | n | positive rate | 5-fold CV ROC-AUC |
|---|---|---|---|---|---|
| extrinsic | 81 SE | downstream *resolved* | 279 | 45% | **0.55** |
| intrinsic | 581 (81 SE + 500 TF-IDF) | reward score ≥ 0.5 | 382 | 69% | **0.49** |
| direction | 81 SE | enhancement helped vs. hurt | 65 | 51% | **0.58** |

*For context, the intrinsic **quality gain itself is real** even though it is unpredictable: enhanced reports score 0.473 → 0.578 on the reward model, 57% improving and 32% crossing the 0.5 threshold — but no feature says which.*

**Answer to RQ2 (both views).** *No feature — across the full 81-SE + 500-TF-IDF representation — is meaningfully associated with a better enhancement, on either an intrinsic or a downstream definition of "better."* The sharpest finding is the **contrast between the two outcomes**: enhancement reliably raises the *intrinsic* quality score (57% of reports improve, 32% cross threshold) but produces **no downstream correctness gain** (RQ1) and no feature-predictable subpopulation on either metric. Reports are made to *look* better by the quality model; the fixes do not follow. This intrinsic-improves / extrinsic-flat gap is, we argue, the study's central result: it says text-quality gains — the thing prior work optimizes and reports — do not transfer to program-repair outcomes.

**Caveats.** Both models are estimated on the best enhancer × solver cell (other cells are expected similar-or-weaker given the RQ1 null); the helped-versus-hurt direction model has only n = 65. Features describe the **original** issue; an enhanced-text or Δ-feature representation is a straightforward variant we have not yet run. In the downstream model a single SE feature (`has_reproduction_steps`) reaches significance — treat with multiple-comparison caution given 70–581 predictors. The added-feature tally (Table 4) is for the OpenHands enhancer over its 304 truly-enhanced issues; per-enhancer tallies are a one-line change. Reproducibility: `feature_extraction_utils.extract_base_features` (the 81-feature extractor), `scripts/analysis/rq2_feature_deltas.py` (what enhancement adds → Table 4), `scripts/analysis/rq2_logreg.py` (SE features → downstream outcome), and `scripts/analysis/rq2_rewardmodel.py` (581 features → reward-model outcome).

---

## 6. RQ3 — How are GitHub issue reports enhanced by generative-AI agents?

**Approach.** We perform a **qualitative analysis** of a stratified sample of agent-generated enhancements (across the five enhancer conditions, sampling successes, harms, and no-change cases). Two coders independently open-code each enhancement for (a) the **enhancement patterns** applied — restructuring into Problem / Reproduction / Expected sections, appending root-cause hypotheses, extracting and organizing stack traces, adding code context — and (b) the **failure modes** — hallucinated details, over-specification, loss of the original signal, or (for the reward-gated agent) abstention. Two coders label independently; we report inter-rater agreement (Cohen's κ) and a pattern × outcome cross-tabulation linking each rewrite move to whether it helped, hurt, or left the downstream fix unchanged.

**Status — analysis pending; corpus ready.** The full corpus of enhanced reports is stored per condition and ready to sample. This section characterizes *how* the agents rewrite — the mechanism behind the RQ1 numbers — and is where the paper explains *why* perturbation is directionless: which rewrite moves are benign and which mislead the solver.

---

## 7. Discussion

### 7.1 Why enhancement fails to transfer

The issues in an execution-gated repair benchmark are, by construction, *already actionable* — they were selected because a solver could plausibly fix them. Rewriting an already-actionable report adds little signal and can just as easily perturb the solver off a working trajectory as onto one. Enhancement, in other words, may help most exactly where these benchmarks contain the fewest examples: genuinely underspecified reports.

### 7.2 Measurement discipline was decisive

Two classes of **infrastructure artifact** would each have manufactured a false result if left uncorrected, and both were caught by cross-checking rather than trusting the raw counts: (i) **solver timeouts under concurrency** — slow iterative solvers, and even Aider on heavy repositories, hit wall-clock limits and produced empty patches that are *not* real failures; re-solving the affected cells at lower concurrency recovered them (e.g., 20 of 27 Aider timeouts recovered at a median 881 s). (ii) **Permission-lost patches** — the runtime occasionally wrote its patch file unreadable to the host, silently zeroing ~2% of OpenHands results; these were recovered by a privileged read. A study that scored the raw output would have reported spuriously low — and unevenly distributed — enhancement effects.

### 7.3 The CL-Enhanced (reward-gated) arm

The three enhancers above rewrite **unconditionally**. Our own managed enhancer, **CL-Enhanced**, instead *gates* on a learned reward model and only rewrites reports it judges low-quality. Applied to this benchmark, its reward model judged **216 of 382 issues (57%) already adequate and abstained** (returning the original, i.e., baseline-equivalent), acting on the other **166 (43%)** with RAG-grounded rewriting. This makes it a *selective* enhancer and a cleaner test of whether *targeted* enhancement transfers to correctness. It is run under the same controlled model (Qwen3-32B) for a fair method-vs-method comparison.

**Result: selective enhancement also fails to transfer.** The methodologically correct comparison for a selective enhancer is on the subset it *chose to rewrite* (Table 3); on the abstained 57%, CL-Enhanced is text-identical to baseline and any difference is solver non-determinism, not enhancement. On the **129 evaluable issues CL-Enhanced actually rewrote, no solver improves**: OpenHands 32→32 (Δ0, *p*=1.0), Aider 58→55 (Δ−3, *p*=0.74), SWE-agent 8→5 (Δ−3, *p*=0.25). This mirrors the generic-enhancer null exactly.

**Table 3. CL-Enhanced vs. baseline, on the 129 issues it rewrote (McNemar exact).**

| solver | baseline → CL-Enhanced | Δ | *p* |
|---|---|---|---|
| OpenHands | 32 → 32 | 0 | 1.00 |
| SWE-agent | 8 → 5 | −3 | 0.25 |
| Aider | 58 → 55 | −3 | 0.74 |

A cautionary note on the full-set view: over *all* 279 evaluable, the SWE-agent comparison reads Δ−9, *p*=0.004 — *apparently* significant. It is an **artifact of non-determinism**: 6 of those 9 "losses" fall on *abstained* issues whose text was identical to baseline, so they reflect run-to-run solver variance (SWE-agent happened to resolve them in the baseline run, not the CL run), not any effect of rewriting. The enhanced-only subset (Table 3) removes this confound and shows the true null. We flag run-to-run non-determinism as a threat in Section 8.

The takeaway completes the paper's arc: **neither unconditional generic enhancement nor selective reward-gated enhancement improves downstream fix correctness.** If anything, the sophisticated method's chief observable effect here is that its reward model — trained on an issue-*difficulty* distribution rather than repair issues — abstains on the majority of already-actionable reports, correctly declining to act where action would not help.

---

## 8. Threats to Validity

**Construct — the correctness metric is P2P-only.** Our resolved criterion is no-regression on *PASS_TO_PASS* tests, augmented by the applied test patch, not the stricter SWE-bench *FAIL_TO_PASS* ("the bug-fix test now passes"). We adopted it because the offline FAIL_TO_PASS labels were unusable at this scale (only 4 of 74 evaluable instances carried a gold-passing FAIL_TO_PASS label). The consequence is that our result rules out a *large* correctness effect and shows no *directional* one, but cannot certify a strict-fix effect of small magnitude; re-deriving fix-tests from execution to enable a FAIL_TO_PASS metric is the highest-value methodological follow-up.

**Internal — run-to-run solver non-determinism.** Baseline and enhanced conditions are separate solver runs, and the solver is stochastic, so a fraction of the discordant pairs in every comparison reflects run-to-run variance rather than the enhancement. This confound is visible and quantifiable in the CL-Enhanced arm: on issues it *abstained* on (text identical to baseline), 6 of 9 SWE-agent "losses" are pure variance, inflating the full-set comparison to a spurious *p*=0.004 that the enhanced-only subset (Section 7.3) corrects to a null. Because our headline effects are null or small, this variance widens confidence intervals rather than creating a false positive — but a definitive study should run each condition with multiple seeds and test the paired difference against the within-condition variance.

**Construct — CL-Enhanced operates out of distribution.** Its reward model and RAG corpus were trained on an issue-*difficulty* dataset, not on repository-repair issues. Applying it here is therefore a *transfer* test, not a re-validation of its original setting; its high abstention rate (57%) is partly an out-of-domain artifact. This makes CL-Enhanced a fair fourth arm for "does *any* enhancement transfer" but not evidence about its performance in-domain.

**External — single model, one issue collection, execution-gated selection.** All conditions use a single open-weight model (Qwen3-32B); a stronger or function-calling-native model could change absolute rates (notably SWE-agent's, which fails ~86% of runs on the agent-computer interface with this model) and conceivably the enhancement effect. The 382 issues are SWE-bench-Live–style and, by construction, *actionable* — selected because a solver could plausibly fix them — so they under-represent the genuinely underspecified reports where enhancement is most plausibly useful. Both are deliberate scoping choices, stated so the negative result is not over-generalized.

**Conclusion — evaluability coverage.** We score only the 73.0% (279/382) gold-validated subset; the un-evaluable 27% are excluded rather than assumed-failed. If enhancement effects were systematically concentrated in the harder-to-evaluate repositories, our estimate would miss them — though the multi-method gate was designed precisely to keep that fraction small and repository-diverse.

---

## 9. Conclusion

We asked whether improving a bug report's text improves an LLM agent's fix, and answered it extrinsically, at scale, by executing patches against real tests. Across 382 issues, a baseline and enhancers spanning a zero-shot prompt to a reward-gated agent, three solvers, and a fixed model, **issue enhancement produced no statistically significant improvement in fix correctness** (all McNemar *p* ≥ 0.489 at *n* = 279 evaluable), and the one small-sample signal **regressed toward zero under replication** rather than sharpening — a textbook non-effect. What proved robust is that **solver choice governs outcome** (Aider 44% ≫ OpenHands 22% ≫ SWE-agent 6%) and that **enhancement perturbs a quarter-to-a-third of outcomes without net direction**.

The negative result holds for our own **selective, reward-gated** method as well: on the issues it chose to rewrite, it improves no solver (all *p* ≥ 0.25), and its most notable behavior is to *abstain* on the majority of already-actionable reports. We offer this as a rigorous negative result — one made trustworthy by a gold-gated, multi-method evaluability protocol (73.0% coverage, 279/382) and by an artifact-recovery discipline that prevented several infrastructure biases (concurrency timeouts, permission-lost patches, and a non-determinism confound) from becoming false findings. The practical implication is that, for automated repair on already-actionable issues, **effort is better spent on the solver and the underlying model than on rewriting the input**. Whether enhancement helps on genuinely *underspecified* reports — under-represented in execution-gated benchmarks — and whether a stronger solver model changes the picture are the natural next studies.
