# Data Collection Pipeline — Pouya-2026 Benchmark Dataset

**Generated:** 2026-05-05  
**Final dataset:** `data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/dataset.jsonl`  
**Collection script:** `scripts/data/pouya_dataset_2026.py`  
**Filter script:** `scripts/data/filter_pouya_dataset_2026_f2p_p2p.py`

---

## Overview

The Pouya-2026 dataset is a SWE-bench-style benchmark of GitHub Python bug-fix issues paired with ground-truth patches and test coverage labels (Fail-to-Pass and Pass-to-Pass tests). Collection started May 2026 and targets issues created on or after **2025-05-01**, ensuring recency and avoiding overlap with existing SWE-bench datasets.

**Final benchmark: 282 issues across 80 repositories.**

---

## Pipeline Funnel

| Stage | Filter Applied | Issues | Repos |
|---|---|---|---|
| **1. GitHub Crawl** | Stars ≥ 1,000 (all languages) | — | **10,609** |
| **2. Repo Filter** | Python primary language, Python ≥ 60% of code, Forks ≥ 200, Total PRs+Issues ≥ 200 | — | **3,621** |
| **3. Task Collection** | PR-to-issue linkage + test patch extraction | **1,275** | **179** |
| **4. Date Cutoff** | Issue created_at ≥ 2025-05-01 | **941** | **145** |
| **5. F2P/P2P Filter** | Both FAIL_TO_PASS and PASS_TO_PASS non-empty (heuristic from test patch) | **282** | **80** |

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
| `data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/dataset.jsonl` | **282-instance final benchmark** |
| `data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/summary.json` | Filter summary with rejection breakdown |
