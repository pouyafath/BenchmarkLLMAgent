# SWE-bench Dataset Collection & Labeling Methodology

**Paper**: "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?"
**Authors**: Carlos E. Jimenez et al., Princeton University
**Published**: ICLR 2024
**Source**: https://arxiv.org/pdf/2310.06770

---

## Dataset Collection: 3-Stage Pipeline

SWE-bench uses a sophisticated pipeline to filter from ~90,000 GitHub pull requests down to 2,294 high-quality task instances.

### Stage I: Repository Selection and Data Scraping

**Approach**:
- Selected 12 popular open-source Python repositories on GitHub
- Criteria for repository selection:
  - **Popular** (well-maintained, high download counts)
  - **>90% Python code**
  - **Clear contributor guidelines**
  - **Good test coverage**

**Repositories** (with task counts):
- django (850)
- sympy (386)
- scikit-learn (229)
- matplotlib (184)
- sphinx (187)
- pytest (119)
- xarray (110)
- astropy (95)
- pylint (57)
- requests (44)
- seaborn (22)
- flask (11)

**Total scraped**: ~90,000 pull requests

---

### Stage II: Attribute-Based Filtering

**Filter Criteria**: PRs must satisfy BOTH conditions:

1. **Resolves a GitHub Issue**
   - PR is linked to an issue (bug report or feature request)
   - Ensures there's a clear problem statement

2. **Contributes Tests**
   - PR makes changes to the repository's test files
   - Indicates the contributor likely added tests to verify their fix
   - Critical for having ground-truth verification

**Rationale**: These two filters ensure each task has:
- A clear problem description (the issue)
- A verified solution (the PR)
- Test infrastructure (contributed tests)

---

### Stage III: Execution-Based Filtering (The Critical Step)

This is where the **3 key metrics** are determined and instances are validated.

**Process**:
1. **Apply PR's test content** to the codebase
2. **Run tests BEFORE applying the PR's code changes**
3. **Run tests AFTER applying the PR's code changes**
4. **Log test results** for both states

**Filter Requirements** - Keep only PRs where:

1. **At least one Fail-to-Pass test exists**
   - Status changes from FAIL → PASS after applying PR
   - This is the **critical success indicator**

2. **No installation or runtime errors**
   - Codebase installs successfully
   - Tests execute without infrastructure failures

**Result**: Final 2,294 task instances from original 90,000 PRs (~2.5% pass rate)

---

## The 3 Key Metrics Explained

### 1. **RESOLVED** (Primary Metric)

**Definition**: A task instance is considered RESOLVED if and only if:
- ✅ Generated patch **applies successfully** (using unix `patch` program)
- ✅ **ALL** fail-to-pass tests **PASS**
- ✅ **ALL** pass-to-pass tests **remain PASS**

**Formula**:
```
RESOLVED = (patch_applies == True) AND
           (all_F2P_tests == PASS) AND
           (all_P2P_tests == PASS)
```

**Benchmark Metric**: `% Resolved = (Number of RESOLVED instances) / (Total instances)`

**Paper Results**:
- Claude 2: 1.96% resolved (45/2,294)
- GPT-4: 1.31% resolved
- ChatGPT-3.5: 0.17% resolved
- SWE-Llama 13b: 0.70% resolved

---

### 2. **Fail-to-Pass (F2P)** Tests

**Definition**: Tests that were **FAILING** before the PR and **PASSING** after the PR.

**How Labeled**:
1. Run test suite on codebase at PR's base commit → record failures
2. Apply PR's code changes
3. Run test suite again → record passes
4. **F2P tests** = tests that transitioned FAIL → PASS

**Characteristics**:
- **Average per instance**: 9.1 F2P tests
- **Maximum**: 1,633 F2P tests in one instance
- **Minimum requirement**: At least 1 F2P test (filter in Stage III)
- **40% of instances** have ≥2 F2P tests

**Purpose**: F2P tests directly verify that the **issue was actually resolved**. They test the new functionality or bug fix.

**Example** (from paper):
```
Issue: "data leak in GBDT due to warm start"
F2P test: test_warm_start_prevents_data_leak()
  - Before PR: FAIL (data leak occurs)
  - After PR: PASS (data leak fixed)
```

**In Your Experiments**:
- **F2P Success Rate**: % of instances where all F2P tests pass
- If F2P < 100%, the patch didn't fully solve the issue

---

### 3. **Pass-to-Pass (P2P)** Tests

**Definition**: Tests that were **PASSING** before the PR and must **remain PASSING** after the PR.

**How Labeled**:
1. Run test suite on codebase at PR's base commit → record all passes
2. Apply PR's code changes
3. Run test suite again
4. **P2P tests** = tests that were passing before and must still pass

**Characteristics**:
- **Average per instance**: 120.8 total tests (median: 51)
- **Maximum**: 9,459 tests in one instance
- Most tests in any instance are P2P tests

**Purpose**: P2P tests ensure **no regressions** — the fix doesn't break existing functionality.

**Example**:
```
Issue: "Fix bug in function calculate_mean()"
F2P test: test_calculate_mean_with_empty_list() (new test for the bug)
P2P tests: All 50 existing tests for other functions
  - Before PR: PASS
  - After PR: Must still PASS (no regressions)
```

**In Your Experiments**:
- **P2P Success Rate**: % of instances where all P2P tests pass
- If P2P < 100%, the patch caused regressions (broke existing code)

---

## Visual Summary of Labeling Process

```
┌─────────────────────────────────────────────────────────┐
│ Stage III: Execution-Based Filtering & Labeling         │
└─────────────────────────────────────────────────────────┘

PR #12345: "Fix bug in calculate_mean()"
├── Codebase at base commit (BEFORE PR)
│   ├── Run test suite
│   │   ├── test_calculate_mean_with_empty_list() → ❌ FAIL
│   │   ├── test_calculate_mean_normal_case()     → ✅ PASS
│   │   ├── test_other_function_1()               → ✅ PASS
│   │   └── test_other_function_2()               → ✅ PASS
│   └── Record: 1 FAIL, 3 PASS
│
├── Apply PR code changes
│
├── Codebase after PR (AFTER PR)
│   ├── Run test suite again
│   │   ├── test_calculate_mean_with_empty_list() → ✅ PASS (F2P!)
│   │   ├── test_calculate_mean_normal_case()     → ✅ PASS (P2P)
│   │   ├── test_other_function_1()               → ✅ PASS (P2P)
│   │   └── test_other_function_2()               → ✅ PASS (P2P)
│   └── Record: 4 PASS, 0 FAIL
│
└── LABELING RESULT:
    ├── Fail-to-Pass (F2P): 1 test
    ├── Pass-to-Pass (P2P): 3 tests
    ├── Total tests: 4
    └── ✅ KEEP this instance (has F2P tests + all pass)

METRICS FOR THIS INSTANCE:
- RESOLVED: True (if model patch also achieves this)
- F2P Success: 100% (1/1 F2P tests pass)
- P2P Success: 100% (3/3 P2P tests pass)
```

---

## Robust Evaluation Features

### Multi-Level Verification

**From the paper**:
> "For each task instance, there is at least one fail-to-pass test which was used to test the reference solution, and 40% of instances have at least two fail-to-pass tests. These tests evaluate whether the model addressed the problem in the issue. In addition, a median of 51 additional tests run to check whether prior functionality is properly maintained."

**What this means**:
1. **F2P tests** (avg 9.1) → Verify the issue is solved
2. **P2P tests** (median 51) → Verify no regressions
3. **Total** (median 60+) → Comprehensive quality gate

### Stringent RESOLVED Criterion

To be RESOLVED, a patch must:
- ✅ Apply cleanly (no merge conflicts, correct format)
- ✅ Pass ALL F2P tests (solve the issue completely)
- ✅ Pass ALL P2P tests (no regressions)

**Why so strict?**
- Mirrors real-world software engineering standards
- Partial fixes that break other code are unacceptable
- Ensures benchmark measures true problem-solving ability

---

## SWE-bench vs SWE-bench Verified

**SWE-bench** (original):
- 2,294 instances
- All have F2P > 0 (from Stage III filtering)
- All have P2P tests (from test suite)
- **Challenge**: Some instances may have flaky tests or unclear issues

**SWE-bench Verified** (refined subset):
- 500 instances (from the 2,294)
- Manually verified for quality
- Clearer issue descriptions
- More stable test infrastructure
- **Your 101-issue experiments use this**

**SWE-bench Lite** (intro subset):
- 300 instances
- Sampled for self-containment
- Focus on functional bug fixes
- Easier entry point for new systems

---

## Key Statistics from Paper

### Dataset Composition

| Metric | Average | Max |
|--------|---------|-----|
| **Issue text length** | 195 words | 4,477 words |
| **Codebase files** | 3,010 files | 5,890 files |
| **Codebase lines** | 438K lines | 886K lines |
| **Gold patch lines edited** | 32.8 lines | 5,888 lines |
| **Gold patch files edited** | 1.7 files | 31 files |
| **Gold patch functions edited** | 3.0 functions | 36 functions |
| **Fail-to-Pass tests** | 9.1 tests | 1,633 tests |
| **Total tests** | 120.8 tests | 9,459 tests |

### Model Performance (F2P & P2P)

From your experiments, these metrics matter:

**Example - SWE-agent Group A**:
- Baseline F2P: 56.4% (56/101 instances pass all F2P tests)
- Baseline P2P: 70.3% (70/101 instances pass all P2P tests)
- Baseline RESOLVED: 51.5% (52/101 instances pass BOTH F2P and P2P)

**Interpretation**:
- 56 instances solved the issue (F2P pass)
- 70 instances had no regressions (P2P pass)
- Only 52 instances achieved BOTH (RESOLVED)
- 4 instances solved issue but broke something (F2P pass, P2P fail)
- 18 instances had no regressions but didn't solve issue (P2P pass, F2P fail)

---

## Why These Metrics Matter for Your Research

### 1. RESOLVED (Overall Quality)
- **What it tells you**: Did the enhancement help the solver produce a complete, correct solution?
- **Your finding**: Aider -45.5%, SWE-agent -5.0% → enhancements hurt overall success

### 2. F2P (Issue Resolution)
- **What it tells you**: Did the solver actually address the reported issue?
- **Your finding**: Enhancement degradation appears in F2P too
- **Implication**: Enhanced issue descriptions confuse the solver about the actual problem

### 3. P2P (Regression Prevention)
- **What it tells you**: Did the solver avoid breaking existing functionality?
- **Your finding**: P2P degradation is smaller than F2P degradation
- **Implication**: Solvers can still avoid regressions, but struggle to solve the core issue

### Combined Insight
If F2P drops more than P2P, it means **enhancements make it harder to understand what needs fixing**, not just harder to avoid breaking things.

---

## Comparison: SWE-bench Methodology vs Your Approach

| Aspect | SWE-bench Paper | Your 101-Issue Experiments |
|--------|----------------|---------------------------|
| **Dataset Source** | 12 repos, 90K PRs → 2,294 | SWE-bench Verified (500) → 101 |
| **F2P Labeling** | Automated via Stage III | Inherited from SWE-bench |
| **P2P Labeling** | Automated via Stage III | Inherited from SWE-bench |
| **RESOLVED Definition** | Patch applies + all F2P + all P2P | Same |
| **Enhancement** | Not in original paper | **Your innovation**: Test if enhancing issue descriptions helps |
| **Key Finding** | Models struggle (1.96% Claude 2) | **Enhancements hurt** (-5% to -45.5%) |

---

## Conclusion

**SWE-bench's contribution**: A rigorous, execution-based benchmark that automatically labels tasks with three critical metrics:

1. **F2P**: Measures if the issue is solved
2. **P2P**: Measures if regressions are avoided
3. **RESOLVED**: Measures overall success (F2P ∩ P2P)

**Your contribution**: Showing that **enhancing issue descriptions before solving** can actually **degrade** performance, with the degradation severity depending on the enhancement strategy (Aider -45.5%, SWE-agent -5.0%, TRAE ±0%).

The combination of SWE-bench's robust metrics + your enhancement experiments provides a comprehensive understanding of how issue description quality affects autonomous software engineering agents.
