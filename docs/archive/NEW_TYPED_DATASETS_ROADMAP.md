# New Typed Datasets: Feature & Refactoring — Roadmap to Evaluation-Ready

**Date:** 2026-05-11
**Author:** Pouya Fathollahzadeh / SEAL Lab

This document describes the current state of the two new typed datasets (Feature and Refactoring),
what needs to be done to make them evaluation-ready for SWE-bench experiments, and includes a
self-contained developer agent prompt for the next session.

---

## 1. Background

The 282-issue dataset (`data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/dataset.jsonl`)
was produced by an offline heuristic filter from 941 raw candidates (all post-2025-05-01).
The filter kept only issues where **both F2P > 0 AND P2P > 0** (heuristic, not Docker-validated).
All 282 issues have placeholder `docker_image = None` — no real Docker images exist for them.

From these 282 issues, three typed sub-datasets were classified using GitHub issue labels + title text:
- **Bug:** 216 issues (in 282) — `data/samples/pouya_dataset_2026_bug/dataset.jsonl`
- **Feature:** 58 issues (in 282) — `data/samples/pouya_dataset_2026_feature/dataset.jsonl`
- **Refactoring:** 8 issues (in 282) — `data/samples/pouya_dataset_2026_refactoring/dataset.jsonl`

Additionally, two pools of new candidates were collected from the **941 raw candidates NOT in 282**:
- **Feature candidates (P2P=0):** 342 issues — `data/samples/pouya_dataset_2026_feature_p2p0_candidates/candidates.jsonl`
- **Refactoring candidates (F2P=0):** 105 issues — `data/samples/pouya_dataset_2026_refactoring_f2p0_candidates/candidates.jsonl`

---

## 2. Current State by Dataset

### 2a. Feature Dataset

| File | Count | F2P filter | P2P filter | Docker images | Issue type classification | Status |
|------|------:|-----------:|-----------:|:--------------|:--------------------------|:-------|
| `pouya_dataset_2026_feature/dataset.jsonl` | 58 | >0 (heuristic) | >0 (heuristic) | None (placeholder) | feature (label/text) | Heuristic only |
| `pouya_dataset_2026_feature_p2p0_candidates/candidates.jsonl` | 342 | >0 (heuristic) | =0 (heuristic) | None | not yet classified | Candidate pool |

**Quality distribution of 342 candidates:**
- vague: 66 | moderate: 134 | detailed: 142

**Pure Feature (label=feature AND F2P>0, P2P≥0):** 58 + 112 = **170**
(112 of the 342 candidates are labeled feature after A+B expanded classification)

**Why F2P>0, P2P≥0 for features:** New features add new tests (F2P>0). Regression tests (P2P) are
welcome but not required since the feature didn't exist before. Requiring P2P=0 was overly
restrictive — it excluded higher-quality PRs that also added regression coverage. Evaluation is
identical regardless: solver must pass all F2P tests + all P2P tests (vacuously true if P2P empty).

### 2b. Refactoring Dataset

| File | Count | F2P filter | P2P filter | Docker images | Issue type classification | Status |
|------|------:|-----------:|-----------:|:--------------|:--------------------------|:-------|
| `pouya_dataset_2026_refactoring/dataset.jsonl` | 8 | >0 (heuristic) | >0 (heuristic) | None (placeholder) | refactoring (label/text) | Heuristic only |
| `pouya_dataset_2026_refactoring_f2p0_candidates/candidates.jsonl` | 105 | =0 (heuristic) | >0 (heuristic) | None | mixed (see below) | Candidate pool |

**Quality distribution of 105 f2p0 candidates:**
- vague: 19 | moderate: 50 | detailed: 36

**Issue type labels of 105 f2p0 candidates:**
- 3 have explicit refactoring labels
- 102 are classified as bug/feature/other by label — but their test structure (F2P=0, P2P>0)
  is the refactoring signal: they change implementation without adding new behavioral tests

**Pure Refactoring (label=refactoring AND F2P=0, P2P>0):** **5 issues** (from 105 f2p0 pool, after A+B)
(The 8 from 282 have F2P>0 — they are "mixed refactoring+test" not pure refactoring.)

**Why only 5:** GitHub developers rarely label issues as "refactoring". The 105 f2p0 pool has the
right test structure but 60/105 carry "bug" labels. To increase this count, more repos must be
collected — label expansion and body text (A+B) only recovers 5 from the existing 941 candidates.

**Note on the 20-issue label-based pool** (`pouya_dataset_2026_refactoring_candidates/candidates.jsonl`):
These 20 are label-classified refactoring issues. Only 3 overlap with the 105 f2p0 set.
The remaining 17 have F2P=0 AND P2P=0 (no test signal) — not useful for SWE-bench evaluation.
**Do not use the 20-issue label-based file as your primary refactoring pool** — use the 105 f2p0 set.

---

## 3. What Needs to Happen (Step-by-Step)

Both the 58 feature issues and the 342 feature candidates (and similarly for refactoring) currently
have **placeholder Docker images only**. Before they can be used in SWE-bench experiments, each
instance needs a real Docker image built by Paul/RepoLaunch, followed by SWE-bench harness validation
with the correct relaxed filter, and then gold patch evaluation.

### Track A: Feature Dataset (400 instances)

**Goal:** Final validated feature dataset with real Docker images, verified F2P > 0, P2P ≥ 0,
gold patch resolves (gold patch = PR diff in `patch` field).

#### Step A1 — Build Docker images for 342 feature_p2p0_candidates

```bash
cd /home/22pf2/paul-RepoLaunch
# Create a config pointing to the 342 candidates file
python paul.py --config configs/feature_p2p0_run.json
```

Config file `configs/feature_p2p0_run.json` should follow the same pattern as
`configs/dlt_hub_rebuild_config.json` with:
- `"dataset_path": "/home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026_feature_p2p0_candidates/candidates.jsonl"`
- `"run_name": "feature_p2p0_docker_build_20260511"`
- `"llm_provider_name": "OpenAI"` (recommended for complex repos)
- `"image_prefix": "pouya/feature_p2p0"` (or similar)

After run: read `workspace/feature_p2p0_docker_build_20260511/organize.jsonl` to get `docker_image`
per instance.

#### Step A2 — Build Docker images for 58 feature issues already in 282

These 58 issues have the same placeholder issue. Run Paul for them too:
- `"dataset_path": "/home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026_feature/dataset.jsonl"`

#### Step A3 — SWE-bench harness validation on feature candidates

For each instance with a built Docker image, run the SWE-bench evaluator with the **gold patch**
(`patch` field from the dataset) to verify:
- **F2P > 0**: at least one test goes from fail to pass (new feature behavior)
- **P2P ≥ 0**: regression tests acceptable even if zero (relaxed for feature requests)

Use the existing evaluation scripts under `scripts/` (e.g., `evaluate.py` or the harness runner).
Reference: `docs/WORKFLOW_SCRIPT_REFERENCE.md` for the evaluation command pattern.

#### Step A4 — Filter and save final feature dataset

Keep instances where Docker build succeeded AND gold patch evaluation passes F2P > 0 constraint.
Save to `data/samples/pouya_dataset_2026_feature_validated/dataset.jsonl`.

---

### Track B: Refactoring Dataset (113 instances)

**Goal:** Final validated refactoring dataset with real Docker images, verified F2P ≥ 0, P2P > 0,
gold patch resolves.

#### Step B1 — Build Docker images for 105 f2p0 candidates

```bash
cd /home/22pf2/paul-RepoLaunch
python paul.py --config configs/refactoring_f2p0_run.json
```

Config file `configs/refactoring_f2p0_run.json`:
- `"dataset_path": "/home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026_refactoring_f2p0_candidates/candidates.jsonl"`
- `"run_name": "refactoring_f2p0_docker_build_20260511"`
- `"llm_provider_name": "OpenAI"`
- Use relaxed test commands (P2P tests only, since F2P=0 these instances have no F2P tests)

#### Step B2 — Build Docker images for 8 refactoring issues in 282

- `"dataset_path": "/home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026_refactoring/dataset.jsonl"`

#### Step B3 — SWE-bench harness validation on refactoring candidates

For each instance with a built Docker image, run evaluator with gold patch:
- **F2P ≥ 0**: zero new behavioral tests is fine (pure refactoring)
- **P2P > 0**: at least one existing test must continue passing (regression guard)

#### Step B4 — (Optional) Refactoring quality metrics

For validated refactoring instances, run static analysis on the base commit and after gold patch:
- `pylint` — lint score before/after
- `radon` — cyclomatic complexity before/after
- Compute **SRR (Smell Removal Rate)** as in Cordeiro et al. TOSEM 2026

This produces baseline metrics to verify that the gold patch improves code quality
(not just passing tests). Useful for paper narrative ("enhancement agent improves refactoring quality").

#### Step B5 — Filter and save final refactoring dataset

Keep instances where Docker build succeeded AND gold patch passes P2P > 0 constraint.
Save to `data/samples/pouya_dataset_2026_refactoring_validated/dataset.jsonl`.

---

## 4. Priority Recommendation

Given limited compute and time, recommended order:

1. **Feature dataset first** — 400 candidates, many vague/moderate (84% of 58 in 282 are vague/moderate),
   directly supports the quality-stratified Pouya-20-v2 experiment.
2. **Refactoring dataset second** — 105 f2p0 candidates, interesting for paper novelty,
   but lower priority than the main enhancement experiment.

For the quality-stratified experiment, you may not need the full 400 features validated —
a sample of 20–30 feature instances (with diverse quality buckets) is sufficient to run
the next round of enhancement experiments.

---

## 5. Key File Reference

| File | Count | Purpose |
|------|------:|:--------|
| `data/samples/pouya_dataset_2026_feature/dataset.jsonl` | 58 | Feature issues from 282 (heuristic, no Docker) |
| `data/samples/pouya_dataset_2026_feature_p2p0_candidates/candidates.jsonl` | 342 | Feature candidates (F2P>0, P2P=0, no Docker) |
| `data/samples/pouya_dataset_2026_refactoring/dataset.jsonl` | 8 | Refactoring issues from 282 (F2P>0, heuristic, no Docker) |
| `data/samples/pouya_dataset_2026_refactoring_f2p0_candidates/candidates.jsonl` | 105 | Refactoring candidates (F2P=0, P2P>0, no Docker) |
| `data/samples/pouya_dataset_2026_refactoring_candidates/candidates.jsonl` | 20 | Label-only refactoring candidates — 17 have no test signal, use f2p0 file instead |
| `data/samples/pouya_dataset_2026_bug/dataset.jsonl` | 216 | Bug issues from 282 (F2P>0, P2P>0, no Docker) |
| `data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/dataset.jsonl` | 282 | Full heuristic-filtered dataset (all types combined) |
| `data/samples/pouya_dataset_2026/raw_candidates.jsonl` | 941 | All raw post-2025-05-01 candidates |

---

## 6. Developer Agent Prompt

Use this prompt verbatim to brief a new Claude Code / developer agent in a fresh session:

---

```
You are continuing work on the BenchmarkLLMAgent project at /home/22pf2/BenchmarkLLMAgent/.
Read docs/NEW_TYPED_DATASETS_ROADMAP.md first — it is the authoritative guide for this task.

## Your Goal

Build evaluation-ready Feature and Refactoring typed datasets for use in SWE-bench enhancement
experiments. "Evaluation-ready" means: real Docker images exist per instance, SWE-bench harness
gold-patch evaluation has been run, and the instance passes the appropriate relaxed filter.

## Context Summary

We have a 282-issue dataset (offline heuristic, placeholder Docker images only).
From these 282 + the 941 raw candidates pool, we have two typed candidate pools:

FEATURE (target: F2P > 0, P2P >= 0):
  - 58 already in 282: data/samples/pouya_dataset_2026_feature/dataset.jsonl
  - 342 new candidates: data/samples/pouya_dataset_2026_feature_p2p0_candidates/candidates.jsonl
  - Total: 400 feature candidates, ALL need real Docker images from Paul/RepoLaunch

REFACTORING (target: F2P >= 0, P2P > 0):
  - 8 already in 282: data/samples/pouya_dataset_2026_refactoring/dataset.jsonl
  - 105 new candidates: data/samples/pouya_dataset_2026_refactoring_f2p0_candidates/candidates.jsonl
  - Total: 113 refactoring candidates, ALL need real Docker images from Paul/RepoLaunch
  - NOTE: do NOT use data/samples/pouya_dataset_2026_refactoring_candidates/candidates.jsonl
    (20-issue file) as the primary pool — 17 of those 20 have no test signal at all.

## Step 1: Understand Paul/RepoLaunch

Read docs/PAUL_REPOLAUNCH_GUIDE.md. Paul is at /home/22pf2/paul-RepoLaunch/.
It takes a JSONL dataset and builds one Docker image per instance.
The config pattern is in configs/dlt_hub_rebuild_config.json (use as template).
After a Paul run, read workspace/<run_name>/organize.jsonl to get docker_image per instance.

## Step 2: Build Docker images (Feature, priority first)

Create configs/feature_p2p0_run.json using dlt_hub_rebuild_config.json as template:
  - dataset_path: /home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026_feature_p2p0_candidates/candidates.jsonl
  - run_name: feature_p2p0_docker_build_20260511
  - llm_provider_name: OpenAI (OPENAI_API_KEY must be set)

Run: cd /home/22pf2/paul-RepoLaunch && python paul.py --config configs/feature_p2p0_run.json

Do the same for the 58 feature issues already in 282 (separate run).

## Step 3: SWE-bench harness validation

After Docker images are built, run the SWE-bench evaluator with the gold patch (patch field)
on each instance. Apply relaxed filters:
  - Feature: keep if gold patch yields F2P > 0 (P2P >= 0 is fine)
  - Refactoring: keep if gold patch yields P2P > 0 (F2P >= 0 is fine)

Use existing evaluation scripts. Reference: docs/WORKFLOW_SCRIPT_REFERENCE.md.

## Step 4: Save validated datasets

Feature: data/samples/pouya_dataset_2026_feature_validated/dataset.jsonl
Refactoring: data/samples/pouya_dataset_2026_refactoring_validated/dataset.jsonl

Update docs/DATA_COLLECTION.md and docs/README.md with final counts.

## Important context

- All 941 raw candidates are post-2025-05-01 (LLM-unseen). Date cutoff is already applied.
- The 282 heuristic filter (1275→941 = date cutoff; 941→282 = F2P/P2P heuristic filter).
- docker_image=None and image_name=starryzhang/... are PLACEHOLDERS for all 282 issues.
  No real Docker images exist for ANY of the 282, despite passing the heuristic filter.
- Paul/RepoLaunch requires OPENAI_API_KEY for complex repos. Check API_KEY_HANDLING.md.
- The existing Pouya-20 instances (runs/pouya_final20b_20260505_050130/) DO have real Docker
  images — those were already built by Paul. Use them as a reference for what success looks like.
- For the quality-stratified Pouya-20-v2 experiment (next enhancement run), we want
  ~7 vague + 7 moderate + 6 detailed issues. Feature instances are 84% vague/moderate,
  making them ideal for this experiment. Bug instances skew detailed (68% detailed in 282).

## After completion

The final feature dataset (even a partial validated set of 20-30) can immediately be used
to run the quality-stratified enhancement experiment. Run it following the pattern in
scripts/workflows/run_pouya20_gpt54mini.py with the new instance IDs.
```

---

## 7. Open Questions

1. **Paul/RepoLaunch capacity**: Can the 400 feature instances all be run in one batch?
   The Pouya-20 run used `configs/dlt_hub_rebuild_config.json` for 2 instances. Check if
   Paul supports batching all 400 or needs to be chunked (e.g., 50 per run).

2. **OpenAI quota**: The raw-LLM enhancer run hit quota limits. Check current quota before
   starting Paul runs for 400+ instances.

3. **Relaxed evaluation harness**: Does the existing SWE-bench harness script support
   F2P ≥ 0 (i.e., accepting resolved even with zero F2P tests)? May need a small patch.

4. **Refactoring metrics**: Implementing SRR (Cordeiro et al.) requires per-instance
   pylint/radon runs. This is optional for the next experiment but needed for a refactoring
   paper contribution.
