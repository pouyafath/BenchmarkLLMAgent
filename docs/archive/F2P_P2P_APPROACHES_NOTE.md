# F2P / P2P Test Derivation — Approaches & Trade-offs

**Created:** 2026-05-15
**Purpose:** Reference note on what F2P and P2P tests are, where they come from, and
the spectrum of approaches for deriving them — from cheapest to most rigorous.

---

## What F2P and P2P Are

Both come from the **same single merged PR** that closed the GitHub issue.
That PR has two diffs stored in our dataset:

```
Merged PR
├── patch         → source code changes (what the solver must replicate)
└── test_patch    → test file changes only (source of F2P and P2P)
```

| Test type | Definition | How derived |
|---|---|---|
| **F2P** (Fail-to-Pass) | Tests that FAILED before the PR, PASS after | Lines starting with `+def test_*` in test_patch diff |
| **P2P** (Pass-to-Pass) | Tests that PASSED before AND after the PR | Context lines ` def test_*` in test_patch diff (unchanged, existing tests) |

**Critical point:** F2P tests are tests the developer **wrote as part of the fix PR**, knowing
the solution. They are not independently verified. P2P tests are tests already in the file that
the developer left untouched while making changes.

**Neither type is confirmed executable** until Paul/RepoLaunch runs them in Docker.

---

## Timeline of a Single Issue

```
  Issue opened        Developer writes fix       Issue closed
       │                       │                      │
       ▼                       ▼                      ▼
  "app crashes"     commit: fix src/ + test/     PR merged → our dataset
                               │                      │
                    test_patch diff                   │
                    ┌──────────────────┐              ▼
                    │ +def test_login  │ ← F2P    patch (source diff)
                    │  def test_logout │ ← P2P    stored separately
                    └──────────────────┘
```

Both F2P and P2P are derived from **one snapshot in time**: the commit that closed the issue.
There is no earlier test collection, no separate test generation, no independent curation.

---

## The Four Approaches (Weakest → Strongest)

### Approach 1 — Static Diff Parse (heuristic)

**How:** Parse `test_patch` text. `+def test_*` → F2P. Context ` def test_*` → P2P.
No execution. Takes seconds per instance.

**Weaknesses:**
- P2P test may have already been failing before the PR (we assume it was passing — could be wrong)
- Only sees tests in files the developer touched (untouched test files invisible)
- Parametrized tests (`test_foo[param1]`) get wrong node IDs — need post-hoc repair
- F2P tests not independently verified (developer wrote them knowing the solution)

**When to use:** Cheap first-pass filter over large candidate pools (e.g., 941 → 387).

**Issue type classification at this stage:** Done by `gpt-oss:120b` via Ollama (4 workers).
The LLM reads title + labels + problem_statement body, responds with `bug`, `feature`, or
`refactoring`. Temperature=0, seed=42. Produces 0 unknowns (vs 33 with keyword heuristics).
Script: `scripts/data/p2p_pipeline/stage1_llm_classify.py`

---

### Approach 2 — Executable Verification via Paul/RepoLaunch

**How:** Build a Docker image at `base_commit` (before the PR). Run the heuristic F2P/P2P test
IDs inside Docker. Verify:
- P2P tests actually **PASS** at base_commit (confirms they were genuinely passing before)
- F2P tests actually **FAIL** at base_commit (confirms they were genuinely failing before — i.e.,
  the behavior didn't exist yet)

**What Paul/RepoLaunch does:**
1. Clones repo at `base_commit`
2. Installs dependencies via LLM agent
3. Runs `pytest -v -rA <F2P_tests> <P2P_tests>` inside container
4. Verifies outcomes match expectations (F2P fail, P2P pass)
5. Commits container as named Docker image

**Why this is better than Approach 1:**
- Confirms test outcomes are real, not assumed
- Catches wrong pytest node IDs (test not found → Paul reports failure, instance dropped)
- Docker image becomes the evaluation environment for the solver

**Typical dropout rate:** ~40–60% of Approach 1 candidates fail at this stage.

**LLM used:** `gpt-oss:120b` via Ollama (4 parallel workers).

---

### Approach 3 — Full Test Suite Before and After Patch

**How:** At `base_commit`, run the **entire test suite** of the repo. Record every test's
outcome. Apply the gold patch. Run the full suite again. Derive F2P/P2P from the actual diff
of outcomes across ALL tests — not just the ones in changed files.

**Why this is the strongest:**
- F2P and P2P are ground truth from execution, not diff parsing
- Catches regressions in test files the developer never touched
- No heuristic classification of test node IDs
- Closest to what SWE-bench-Verified uses for its human-curated 500 instances

**Why it's expensive:**
- Full test suite per repo: 10–60+ minutes
- Requires working environment for every repo (databases, external services, etc.)
- Not scalable to thousands of instances

**When to use:** Final validation of the small (~20–50) experiment subsets before running
the expensive Enhancer+Solver experiments.

**LLM used:** `gpt-oss:120b` via Ollama for any environment setup; pytest runs natively in Docker.

---

### Approach 4 — Independent Test Generation (ideal, rarely done)

**How:** A separate agent reads only the issue description (not the gold patch) and writes
tests from scratch. Those independently-written tests are used as F2P ground truth.

**Why strongest:** Tests are not designed knowing the solution — genuine verification.
**Why not done at scale:** Requires a test-writing agent per instance; quality depends on issue
clarity (vague issues produce bad tests).

**Status in this project:** Not implemented. Potential future extension.

---

## Summary Table

| Approach | Execution | Infrastructure | Dropout from prev | Confidence |
|---|---|---|---|---|
| 1 — Static parse | None | None | — (from 941 raw) | Low |
| 2 — Paul/RepoLaunch | Docker per instance | Ollama gpt-oss:120b, 4 workers | ~40–60% | High |
| 3 — Full test suite | Docker, full suite | Same as Approach 2 | ~10–30% | Very High |
| 4 — Independent tests | LLM + Docker | Full agent per instance | N/A | Highest |

---

## Why We Dropped F2P as a Required Filter

Original pipeline required **both** F2P > 0 AND P2P > 0, which excluded:
- Pure refactoring PRs (F2P = 0 by definition — no new behavioral tests)
- Feature PRs that only added tests without regression coverage
- Any PR where test structure didn't align with our heuristic parser

**New pipeline requires only P2P > 0** (regression guard). F2P is stored for reference but
not used as a gate. This:
- Includes all 3 issue types (Bug, Feature, Refactoring) in one unified pipeline
- Increases candidate pool from 282 → 387 (+37%)
- Lets test structure be an *observed attribute* rather than a *filter criterion*

F2P = 0 → likely Refactoring
F2P > 0, P2P > 0 → likely Bug fix
F2P > 0, P2P varies → likely Feature

---

## Reference

- `scripts/data/filter_pouya_dataset_2026_f2p_p2p.py` — original Approach 1 parser (F2P+P2P)
- `scripts/data/p2p_pipeline/` — new P2P-only pipeline scripts
- `data/samples/pouya_p2p_pipeline/` — staged datasets from the new pipeline
- `docs/P2P_PIPELINE_PLAN.md` — full pipeline design and execution plan
- Paul/RepoLaunch guide: `docs/PAUL_REPOLAUNCH_GUIDE.md`
