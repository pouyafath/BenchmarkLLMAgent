# Data Collection Pipeline — Pouya-2026 Benchmark Dataset

**Generated:** 2026-05-05 (typed sub-datasets: 2026-05-11)  
**Base dataset:** `data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/dataset.jsonl` (282 issues)  
**Collection script:** `scripts/data/pouya_dataset_2026.py`  
**Filter script:** `scripts/data/filter_pouya_dataset_2026_f2p_p2p.py`

---

## Overview

The Pouya-2026 dataset is a SWE-bench-style benchmark of GitHub Python issues paired with ground-truth patches and test coverage labels (Fail-to-Pass and Pass-to-Pass tests). Collection started May 2026 and targets issues created on or after **2025-05-01**, ensuring recency and avoiding overlap with existing SWE-bench datasets.

**Base benchmark: 282 issues across 80 repositories**, further typed into Bug / Feature / Refactoring sub-datasets.

---

## Issue Type Taxonomy

Issue type is determined by **two independent dimensions** that must be understood separately:

### Dimension 1 — GitHub Label/Title Classification (what the developer called it)

Priority order (highest priority first):

| Priority | Assigned type | Trigger keywords |
|---|---|---|
| 1 | `refactoring` | Labels: *refactor, refactoring, cleanup, clean-up, tech-debt, technical debt, code quality, maintenance, type: refactor, kind/refactoring* |
| 2 | `feature` | Labels: *feature, enhancement, improvement, feature-request, feat, new feature, type: feature, kind/feature, feature-enhancement, type: enhancement* |
| 3 | `bug` | Labels: *bug, defect, fix, error, crash, regression, type: bug, bug report, bugfix, kind: bug* |
| 4–6 | (same order) | Title text fallback: *refactor/cleanup/tech debt* → *feature/enhancement/add support* → *bug/fix/error/crash* |
| 7 | `unknown` | No keyword matches |

Label data from cached GitHub API responses in `data/samples/pouya_dataset_2026/cache/issues/` (1,320 files).

### Dimension 2 — Test Structure Classification (what the patch does to tests)

| Structural type | F2P | P2P | Interpretation |
|---|---|---|---|
| bug-like | > 0 | > 0 | Failing tests now pass; regression tests still pass |
| feature-like | > 0 | = 0 | New behavioral tests added; no regression tests required |
| refactoring-like | = 0 | > 0 | No new behavioral tests; existing tests still pass |
| no signal | = 0 | = 0 | No test coverage at all — not usable for SWE-bench |

F2P/P2P counts are derived by heuristic (offline diff parse of `test_patch`), NOT Docker execution.

### The Two Dimensions Are Independent

The key finding is that label classification and test structure classification **do not align well**:

| Pool | Label=feature | Label=bug | Label=refactoring | Label=unknown |
|---|---:|---:|---:|---:|
| 282 dataset (all bug-like: F2P>0, P2P>0) | 58 | 216 | 8 | 0 |
| 342 candidates (feature-like: F2P>0, P2P=0) — after A+B | **112** | 193 | 4 | 33 |
| 105 candidates (refactoring-like: F2P=0, P2P>0) — after A+B | 26 | 60 | **5** | 14 |

**"Pure" typed issues** (both dimensions agree, after expanded A+B classification):
- **Pure Feature: 170 issues** — label=feature AND F2P>0, P2P≥0 (58 from 282 with P2P>0 + 112 from 342 candidates with P2P=0)
- **Pure Refactoring: 5 issues** — label=refactoring AND F2P=0, P2P>0 (from 105 f2p0 candidates)
- **Bug: 216 issues** — label=bug AND F2P>0, P2P>0 (from 282 dataset)

**Note on feature test structure:** Feature is defined as F2P>0, P2P≥0 (not P2P=0). Requiring P2P=0 was overly restrictive and selected lower-quality PRs. A feature PR that also includes regression tests (P2P>0) is still a feature. Evaluation is identical: solver must pass all F2P tests + all P2P tests (vacuously true if P2P is empty).

**Note on refactoring count (5):** Low count is expected — developers rarely label issues as "refactoring" on GitHub. The 105 f2p0 pool has the right test structure (F2P=0, P2P>0) but mostly carries "bug" labels (60/105). Pure refactoring count can only be increased by collecting from more repos.

This means most GitHub issues labeled "bug" have refactoring-like or feature-like test structure — developers call things "bug" regardless of whether they add new tests or restructure code.

**Classification method (A+B):** Priority order: (1) expanded GitHub label sets, (2) issue title text, (3) `problem_statement` body text. Fields added per row: `issue_type`, `issue_labels`, `issue_title`.

---

## Issue Type Distribution Across Pipeline Stages

| Stage | Total | Bug | Feature | Refactoring |
|---|---:|---:|---:|---:|
| Raw candidates (941, date-filtered) | 941 | 704 (74.8%) | 209 (22.2%) | 28 (3.0%) |
| Validated dataset (F2P>0, P2P>0) | 282 | 216 (76.6%) | 58 (20.6%) | 8 (2.8%) |
| Refactoring candidates (need Docker validation) | 20 | — | — | 20 |

Feature requests survive Docker validation at a similar rate to bugs (~28%). Refactoring issues are rare (3%) and mostly excluded by the F2P>0 filter (since pure refactoring has no behavioral test changes).

**Quality bucket × type (282 validated):**

| | Bug | Feature | Refactoring |
|---|---:|---:|---:|
| Vague (46 total) | 19 | 22 | 5 |
| Moderate (112 total) | 83 | 27 | 2 |
| Detailed (124 total) | 114 | 9 | 1 |

Feature requests are disproportionately vague/moderate (49/58 = 84%) compared to bugs (102/216 = 47%) — consistent with the observation that feature requests often lack detailed reproduction steps.

---

## Typed Sub-Datasets

All typed datasets use the same SWE-bench instance format, with added `issue_type`, `issue_labels`, `issue_title` fields. **None of these datasets have real Docker images** — all have placeholder `docker_image=None`. Docker images must be built via Paul/RepoLaunch before SWE-bench evaluation.

| Dataset | Path | Count | Classification basis | F2P | P2P |
|---|---|---:|---|---|---|
| **Bug** | `data/samples/pouya_dataset_2026_bug/dataset.jsonl` | **216** | Label=bug AND test-structure bug-like | > 0 | > 0 |
| **Feature (from 282)** | `data/samples/pouya_dataset_2026_feature/dataset.jsonl` | **58** | Label=feature; F2P>0, P2P>0 — qualifies under F2P>0, P2P≥0 | > 0 | > 0 |
| **Feature candidates** | `data/samples/pouya_dataset_2026_feature_p2p0_candidates/candidates.jsonl` | **342** (112 pure) | Label=feature (112) by A+B; F2P>0, P2P=0 | > 0 | = 0 |
| **Refactoring (from 282)** | `data/samples/pouya_dataset_2026_refactoring/dataset.jsonl` | **8** | Label=refactoring; F2P>0 — NOT pure (mixed) | > 0 | > 0 |
| **Pure Refactoring candidates** | `data/samples/pouya_dataset_2026_refactoring_f2p0_candidates/candidates.jsonl` | **105** (5 pure) | Label=refactoring (5) by A+B; F2P=0, P2P>0 | = 0 | > 0 |

**Final counts (both dimensions agree, all need Paul/RepoLaunch for Docker images):**
- **Bug: 216** — label=bug AND F2P>0, P2P>0 (from 282, Docker placeholder)
- **Feature: 170** — label=feature AND F2P>0, P2P≥0 (58 from 282 + 112 from 342 candidates)
- **Pure Refactoring: 5** — label=refactoring AND F2P=0, P2P>0 (from 105 candidates)

See `docs/NEW_TYPED_DATASETS_ROADMAP.md` for next steps to make these evaluation-ready.

### Bug Dataset (216 issues)
- Both dimensions agree: label=bug AND test-structure bug-like (F2P>0, P2P>0)
- Quality: 114 detailed / 83 moderate / 19 vague
- The primary benchmark; the current Pouya-20 experiment draws from this pool (all 20 are detailed bugs)

### Feature Dataset — Label Only (58 issues)
- Label=feature but test-structure is bug-like (F2P>0, P2P>0) — NOT "pure feature"
- Quality: 9 detailed / 27 moderate / 22 vague
- These feature requests happened to include regression tests in their PRs

### Pure Feature Candidates (342 issues, 72 pure)
- Test-structure feature-like: F2P>0, P2P=0 (new tests added, no regression tests)
- Of 342: 72 also labeled feature (pure), 180 labeled bug, 89 unknown, 1 refactoring
- Quality (all 342): 66 vague / 134 moderate / 142 detailed
- Need Paul/RepoLaunch + SWE-bench harness with F2P>0, P2P≥0 to validate

### Refactoring Dataset — Label Only (8 issues)
- Label=refactoring but test-structure is bug-like (F2P>0, P2P>0) — NOT "pure refactoring"
- PRs included test changes alongside structural refactoring
- Quality: 1 detailed / 2 moderate / 5 vague

### Pure Refactoring Candidates (105 issues, 0 pure)
- Test-structure refactoring-like: F2P=0, P2P>0 (no new behavioral tests, regression tests pass)
- Of 105: 0 labeled refactoring, 54 labeled bug, 19 labeled feature, 32 unknown
- Quality: 19 vague / 50 moderate / 36 detailed
- Need Paul/RepoLaunch + SWE-bench harness with F2P≥0, P2P>0 to validate

---

## Pipeline Funnel

| Stage | Filter Applied | Issues | Repos |
|---|---|---|---|
| **1. GitHub Crawl** | Stars ≥ 1,000 (all languages) | — | **10,609** |
| **2. Repo Filter** | Python primary language, Python ≥ 60% of code, Forks ≥ 200, Total PRs+Issues ≥ 200 | — | **3,621** |
| **3. Task Collection** | PR-to-issue linkage + test patch extraction | **1,275** | **179** |
| **4. Date Cutoff** | Issue created_at ≥ 2025-05-01 → stored as `raw_candidates.jsonl` | **941** | **145** |
| **5. F2P/P2P Filter** | Both FAIL_TO_PASS and PASS_TO_PASS non-empty (from Docker test execution) | **282** | **80** |

> **Important:** The date cutoff happens at Stage 4 (1,275 → 941). The `raw_candidates.jsonl` file (941 issues) already satisfies the LLM-unseen guarantee — all 941 issues were created ≥ 2025-05-01. The further reduction to 282 at Stage 5 is a **test structure filter only** (659 rejected because F2P=0 or P2P=0). This means the 659 non-validated candidates are still date-valid and can be revisited with a relaxed F2P/P2P filter to collect refactoring or feature datasets without violating the unseen-data guarantee.

---

## Stage 1 — Repository Crawl

**Tool:** `SWE-bench-Live-Collection/curation/crawl_repo.py`

GitHub's repository search API was queried for all public repositories with **≥ 1,000 stars** (regardless of language). This yielded **10,609 repositories**.

The 1,000-star floor follows the SWE-bench-Live methodology and targets active, well-maintained projects with sufficient issue/PR activity to produce quality benchmark instances.

---

## Stage 2 — Repository Filter

**Tool:** `SWE-bench-Live-Collection/curation/filter_repo.py`

Each of the 10,609 crawled repos was checked against four criteria (via GitHub API):

| Criterion | Threshold | Rationale |
|---|---|---|
| Primary language | **Python** | Dataset scope: Python bug fixes only |
| Python code percentage | **≥ 60%** of total code bytes | Exclude repos that are mostly non-Python |
| Fork count | **≥ 200** | Proxy for community adoption and maturity |
| Total PRs + Issues | **≥ 200** | Ensure sufficient activity for PR-linked issue collection |

**Result: 3,621 repositories** (6,988 rejected — 65.9%)

---

## Stage 3 — Task Collection (PR → Issue Linkage)

**Tool:** `SWE-bench-Live-Collection/curation/build_dataset.py` (via `collect-tasks`)

For each of the 3,621 filtered repos, closed pull requests were fetched and matched to linked GitHub issues. A task instance requires:
- A merged PR that explicitly closes or fixes a linked issue
- A non-empty `test_patch` (diff of test files changed in the PR)
- A valid `patch` (diff of source files)

Collection outcome across 3,621 repos:
- **278 repos** had at least one PR with a linked issue
- **2,515 repos** had PRs but no linked issue found (no keyword "fixes #N", "closes #N", etc.)
- **828 repos** had errors (API rate limits, private repos, no PRs at all)
- **179 repos** produced ≥ 1 valid task instance
- **1,275 total task instances** collected across 179 repos

> Note: The `collect-tasks` progress log reports `task_instances: 801` for 109 repos — this reflects a partial run count. The full merged total in `tasks/merged_raw_tasks.jsonl` is 1,275 across 179 repos.

---

## Stage 4 — Date Cutoff Filter

Issues with `created_at < 2025-05-01` were excluded to ensure the dataset contains only recent, previously-unseen issues.

- **334 instances rejected** (all labeled `issue_before_cutoff`)
- **941 instances retained** across **145 repositories**

Quality metadata was recorded but **not used as a filter**:

| Quality Bucket | Criteria | Count (of 941) |
|---|---|---|
| Detailed | ≥ 200 words AND ≥ 2 quality signals (code block, traceback, repro steps, expected behavior) | 370 |
| Moderate | ≥ 50 words AND ≥ 1 quality signal | 376 |
| Vague | < 50 words OR no quality signals | 195 |

---

## Stage 5 — F2P / P2P Heuristic Filter

**Tool:** `scripts/data/filter_pouya_dataset_2026_f2p_p2p.py`

Each of the 941 raw candidates was analyzed via **offline heuristic parsing** of its `test_patch` diff to derive test labels:

- **FAIL_TO_PASS (F2P):** Newly added `def test_*` functions (lines starting with `+`) — tests that did not exist before the fix and are expected to fail on the original code.
- **PASS_TO_PASS (P2P):** Existing `def test_*` functions visible in unchanged diff context lines (not added, not removed) — tests that passed before and must continue to pass after the fix.

An instance is retained **only if both FAIL_TO_PASS and PASS_TO_PASS are non-empty**.

### Rejection Breakdown (941 → 282)

| Category | Issues Rejected | Description |
|---|---|---|
| **No F2P** (has P2P, lacks new tests) | 105 | Test patch touches existing tests but adds no new `test_*` functions |
| **No P2P** (has F2P, no existing test context) | 342 | Test patch only adds new tests, no existing tests visible in diff context |
| **Neither F2P nor P2P** | 212 | Test patch has no `def test_*` lines at all |
| **Total rejected** | **659** | |
| **Kept** | **282** | Both F2P and P2P non-empty |

> **Note on rejection counts:** The `summary.json` reports `no_f2p: 317` and `no_p2p: 342`. These counts are from a different labeling convention where "no_f2p" = has no F2P regardless of P2P status (105 + 212 = 317 ✓), and "no_p2p" counts only issues that have F2P but no P2P (342 ✓ — the 212 "neither" cases were labeled "no_f2p" first).

---

## Final Dataset: 282 Issues, 80 Repositories

### Test Coverage Breakdown

Since the filter **requires both F2P and P2P to be non-empty**, all 282 instances in the final dataset have both:

| Category | Issues | Repos |
|---|---|---|
| **Both F2P and P2P** | **282** | **80** |
| F2P only (no P2P) | 0 | 0 |
| P2P only (no F2P) | 0 | 0 |

> This is by construction: the filter script (`filter_pouya_dataset_2026_f2p_p2p.py`) drops any row where either list is empty.

### Test Count Statistics

| Metric | FAIL_TO_PASS | PASS_TO_PASS |
|---|---|---|
| Total tests across all instances | 1,348 | 932 |
| Average per issue | 4.8 | 3.3 |
| Median per issue | 2 | 1 |
| Min per issue | 1 | 1 |
| Max per issue | 60 | 76 |

### Quality Distribution (Final 282)

| Quality Bucket | Count | % |
|---|---|---|
| Detailed | 124 | 44% |
| Moderate | 112 | 40% |
| Vague | 46 | 16% |

### Repository Distribution (Top 25 by Issue Count)

| Repository | Issues |
|---|---|
| huggingface/transformers | 50 |
| dlt-hub/dlt | 18 |
| schemathesis/schemathesis | 10 |
| sdv-dev/SDV | 10 |
| aws-powertools/powertools-lambda-python | 9 |
| sooperset/mcp-atlassian | 8 |
| PennyLaneAI/pennylane | 7 |
| NVIDIA-NeMo/RL | 6 |
| SQLMesh/sqlmesh | 6 |
| a2aproject/a2a-python | 6 |
| dgtlmoon/changedetection.io | 6 |
| pytorch/rl | 6 |
| quantumlib/Cirq | 6 |
| ag2ai/faststream | 5 |
| Azure/azure-sdk-for-python | 4 |
| GeoNode/geonode | 4 |
| astropy/astropy | 4 |
| beeware/toga | 4 |
| django-import-export/django-import-export | 4 |
| jelmer/dulwich | 4 |
| mne-tools/mne-python | 4 |
| nautobot/nautobot | 4 |
| pgmpy/pgmpy | 4 |
| pybamm-team/PyBaMM | 4 |
| stickerdaniel/linkedin-mcp-server | 4 |
| *(55 more repos, 1–3 issues each)* | 55–78 |

---

## Benchmark Subset: 20 Gold-Validated Instances

The Pouya-20 benchmark is a 20-instance subset of the 282 that additionally passed **executable gold evaluation** (running the gold patch in Docker and verifying all F2P tests pass with no P2P regressions).

Selection applied additional exclusions on top of the 282:
- Known-bad instances (cloud credentials required, Poetry install hangs, infrastructure-heavy repos)
- At most 2 instances per repository (diversity cap)
- First 20 instances meeting all criteria

Gold-validated canonical file: `runs/pouya_final20b_20260505_050130/validated_instances.jsonl`

See [`docs/POUYA20_EXPERIMENT.md`](POUYA20_EXPERIMENT.md) for the complete 20-instance list and experiment results.

---

## Key Files

| File | Description |
|---|---|
| `data/samples/pouya_dataset_2026/repos/raw_repos.jsonl` | 10,609 crawled repos (stars ≥ 1,000) |
| `data/samples/pouya_dataset_2026/repos/filtered_repos.jsonl` | 3,621 repos after Python/forks/activity filter |
| `data/samples/pouya_dataset_2026/tasks/merged_raw_tasks.jsonl` | 1,275 raw task instances (pre-date-cutoff) |
| `data/samples/pouya_dataset_2026/raw_candidates.jsonl` | 941 candidates after date cutoff (≥ 2025-05-01) |
| `data/samples/pouya_dataset_2026/rejected_candidates.jsonl` | 334 instances rejected for pre-cutoff dates |
| `data/samples/pouya_dataset_2026/collection_summary.json` | Collection metadata and quality bucket counts |
| `data/samples/pouya_dataset_2026/cache/issues/` | GitHub API cache (1,320 files): labels, titles, bodies |
| `data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/dataset.jsonl` | **282-instance base benchmark** (F2P>0, P2P>0) |
| `data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/summary.json` | Filter summary with rejection breakdown |
| `data/samples/pouya_dataset_2026_bug/dataset.jsonl` | **216 Bug issues** (typed sub-dataset, Docker-ready) |
| `data/samples/pouya_dataset_2026_feature/dataset.jsonl` | **58 Feature issues** (typed sub-dataset, Docker-ready) |
| `data/samples/pouya_dataset_2026_refactoring/dataset.jsonl` | **8 Refactoring issues** (typed sub-dataset, Docker-ready, F2P>0) |
| `data/samples/pouya_dataset_2026_refactoring_candidates/candidates.jsonl` | **20 Refactoring candidates** (not validated, need Docker) |
