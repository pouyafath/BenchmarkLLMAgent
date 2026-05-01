# SWE-Bench Data Collection Methodology

**Paper**: "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?"
**Authors**: Carlos E. Jimenez et al., Princeton University
**Published**: ICLR 2024
**Source**: https://arxiv.org/pdf/2310.06770

---

## Overview

SWE-bench uses a **3-stage automated pipeline** to filter from ~90,000 GitHub pull requests down to 2,294 high-quality task instances. The key innovation is **execution-based filtering** that automatically labels tasks with three critical metrics: RESOLVED, Fail-to-Pass, and Pass-to-Pass.

---

## Stage I: Repository Selection and Data Scraping

### Objective
Collect pull requests from high-quality, well-maintained Python repositories.

### Process

**Repository Selection Criteria**:
1. **Popular** repositories (high download counts, well-maintained)
2. **>90% Python code** (language consistency)
3. **Clear contributor guidelines** (structured development)
4. **Good test coverage** (enables execution-based validation)

**Data Source**:
- Top 5,000 most downloaded PyPI libraries (August 2023)
- Selected top 100 packages
- Identified corresponding GitHub repositories
- Verified free software licenses

**Pull Request Collection**:
- Collected via GitHub Developer API
- All merged PRs from selected repositories
- **Result**: ~90,000 pull requests

### Selected Repositories (Final Task Counts)

| Repository | Task Count |
|------------|------------|
| django | 850 |
| sympy | 386 |
| scikit-learn | 229 |
| matplotlib | 184 |
| sphinx | 187 |
| pytest | 119 |
| xarray | 110 |
| astropy | 95 |
| pylint | 57 |
| requests | 44 |
| seaborn | 22 |
| flask | 11 |
| **Total** | **2,294** |

### Repository Mirrors

To ensure reproducibility:
- Created **mirror repositories** under SWE-bench GitHub organization
- Mirrors preserve commit hashes, history, branches, tags
- Protects against future changes/deletions in original repos
- Naming convention: `owner__name` (e.g., `django__django`)

---

## Stage II: Attribute-Based Filtering

### Objective
Select PRs that have both a clear problem statement and test infrastructure.

### Filter Criteria (BOTH required)

#### Filter 1: PR Resolves a GitHub Issue
- PR must be linked to one or more GitHub issues
- Issue = bug report or feature request
- Linking detected via:
  - PR title: "fixes #123"
  - PR body: "closes #456"
  - Commit messages: "resolves #789"
- Keywords: "fixes", "closes", "resolves", "addresses"

**Rationale**: Ensures clear problem description exists.

#### Filter 2: PR Contributes Tests
- PR must modify test files
- Test files identified by keywords in path:
  - "test", "tests", "testing", "test_"
- Indicates contributor added verification tests

**Rationale**: Ensures test infrastructure for evaluation.

### Issue Problem Statement Construction

**Components**:
1. All linked issue titles
2. All linked issue bodies
3. Issue comments created **before** PR's initial commit timestamp

**Purpose of timestamp cutoff**: Avoid solution leakage from comments posted after the fix was implemented.

### PR Code Changes Parsing

**Separation into two patches**:
1. **Test Patch**: All changes to test files
2. **Gold Patch**: All changes to non-test files (the solution)

**Format**: `.patch` files (unified diff format)
```diff
--- a/file.py
+++ b/file.py
@@ -10,3 +10,4 @@
 def foo():
-    return 1
+    return 2
+    # Fixed bug
```

---

## Stage III: Execution-Based Filtering (Critical Step)

### Objective
Validate that each task instance is solvable and has measurable success criteria through automated test execution.

### Process

```
For each candidate task:
  1. Create virtual environment for the repository
  2. Clone repository mirror at PR's base commit
  3. Install dependencies (setup.py / requirements.txt)
  4. Apply test patch (new tests from PR)
  5. Run tests BEFORE applying gold patch → Log results
  6. Apply gold patch (the solution)
  7. Run tests AFTER applying gold patch → Log results
  8. Compare before/after test results
  9. Determine F2P and P2P test sets
```

### Detailed Steps

#### Step 1-3: Environment Setup
- Docker containers for isolation
- Python version from repository configuration
- Install via: `pip install -e .` or `python setup.py install`

#### Step 4: Apply Test Patch
- Uses `patch` command: `patch -p1 < test.patch`
- Adds new tests that verify the fix

#### Step 5: Run Tests BEFORE Solution
```bash
# Example: pytest for most repos
pytest <test_file_paths> --json-report --json-report-file=before.json
```
- Records: PASSED, FAILED, SKIPPED, ERROR for each test
- Example results:
  ```
  test_calculate_mean_with_empty_list() FAILED
  test_calculate_mean_normal_case() PASSED
  test_other_function_1() PASSED
  test_other_function_2() PASSED
  ```

#### Step 6: Apply Gold Patch
- Applies the actual solution: `patch -p1 < gold.patch`

#### Step 7: Run Tests AFTER Solution
```bash
pytest <test_file_paths> --json-report --json-report-file=after.json
```
- Example results:
  ```
  test_calculate_mean_with_empty_list() PASSED  ← Changed!
  test_calculate_mean_normal_case() PASSED
  test_other_function_1() PASSED
  test_other_function_2() PASSED
  ```

#### Step 8-9: Label Test Categories

**Fail-to-Pass (F2P) Tests**:
```python
F2P = {test for test in all_tests
       if before[test] == FAILED and after[test] == PASSED}
```

**Pass-to-Pass (P2P) Tests**:
```python
P2P = {test for test in all_tests
       if before[test] == PASSED and after[test] == PASSED}
```

### Filter Requirements

**A candidate task is KEPT if**:
1. ✅ Installation succeeds (no errors in steps 1-3)
2. ✅ Tests run successfully (no infrastructure failures)
3. ✅ **At least ONE fail-to-pass test exists** (`len(F2P) >= 1`)
4. ✅ Gold patch passes all tests (validation check)

**A candidate task is REJECTED if**:
1. ❌ Installation fails
2. ❌ Test execution crashes
3. ❌ Zero fail-to-pass tests (`len(F2P) == 0`)
4. ❌ Tests invoke newly created functions/classes (arbitrary naming issue)
5. ❌ Gold patch doesn't fix the issue

### Result Statistics

From ~90,000 PRs to 2,294 tasks:
- **Pass rate**: ~2.5%
- **Average F2P tests**: 9.1 per instance
- **Average P2P tests**: 120.8 per instance
- **Average total tests**: ~130 per instance

---

## The Three Key Metrics

### 1. RESOLVED (Primary Success Metric)

**Definition**:
```python
RESOLVED = (patch_applies == True) AND
           (all(F2P_tests) == PASSED) AND
           (all(P2P_tests) == PASSED)
```

**Requirements**:
- ✅ Model-generated patch applies cleanly
- ✅ ALL fail-to-pass tests PASS (issue solved)
- ✅ ALL pass-to-pass tests PASS (no regressions)

**Benchmark Metric**:
```
Resolve Rate = (# RESOLVED instances) / (Total instances) × 100%
```

**Original Paper Results**:
- Claude 2: 1.96% (45/2,294)
- GPT-4: 1.31%
- ChatGPT-3.5: 0.17%
- SWE-Llama 13b: 0.70%

---

### 2. Fail-to-Pass (F2P) Tests

**Purpose**: Verify the issue was actually solved.

**Labeling Process** (Automatic):
```
Step 1: Run tests on base commit
Step 2: Apply solution patch
Step 3: Run tests again
Step 4: F2P = tests that went FAIL → PASS
```

**Characteristics**:
- **Mean**: 9.1 tests per instance
- **Max**: 1,633 tests (one extreme instance)
- **Min**: 1 test (required by Stage III filter)
- **Distribution**: 40% of instances have ≥2 F2P tests

**Example**:
```python
# Issue: "data leak in GBDT due to warm start"
# F2P test added in PR:
def test_warm_start_prevents_data_leak():
    """Verify no data leakage with warm_start=True"""
    model = GradientBoostingClassifier(warm_start=True)
    model.fit(X_train, y_train)
    assert not check_data_leak(model)  # Before PR: FAIL → After PR: PASS
```

**What F2P Success Rate Measures**:
- Did the model solve the core issue?
- Does the solution address the bug/feature request?
- Independent of regression testing

---

### 3. Pass-to-Pass (P2P) Tests

**Purpose**: Ensure no regressions (don't break existing functionality).

**Labeling Process** (Automatic):
```
Step 1: Run tests on base commit → Record PASSes
Step 2: Apply solution patch
Step 3: Run tests again
Step 4: P2P = tests that stayed PASS → PASS
```

**Characteristics**:
- **Mean**: 120.8 tests per instance
- **Median**: 51 tests per instance
- **Max**: 9,459 tests (large test suites)
- **Majority** of tests in any instance are P2P

**Example**:
```python
# Issue: "Fix calculate_mean() with empty list"
# F2P test (new):
def test_calculate_mean_empty_list():
    assert calculate_mean([]) == 0  # Added in PR

# P2P tests (existing, must still pass):
def test_calculate_mean_normal():
    assert calculate_mean([1,2,3]) == 2.0  # Must remain PASS

def test_calculate_sum():
    assert calculate_sum([1,2,3]) == 6  # Unrelated, must remain PASS

def test_other_module_function():
    assert other_function() works  # Must remain PASS
```

**What P2P Success Rate Measures**:
- Did the solution introduce regressions?
- Does existing functionality still work?
- Code quality and carefulness indicator

---

## Visual Example: Complete Labeling Process

```
Repository: scikit-learn/scikit-learn
PR #12345: "Fix data leak in GBDT warm start"
Issue #12340: "GradientBoostingClassifier leaks training data when warm_start=True"

┌─────────────────────────────────────────────────────────────────┐
│ STAGE I: Repository Selected (scikit-learn is popular, >90% Python) │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ STAGE II: Attribute Filtering                                    │
│ ✅ PR #12345 resolves Issue #12340                              │
│ ✅ PR modifies sklearn/ensemble/tests/test_gradient_boosting.py │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ STAGE III: Execution-Based Validation & Labeling                │
└─────────────────────────────────────────────────────────────────┘

Step 1-3: Environment Setup
  ✅ Clone sklearn at commit abc123 (base commit)
  ✅ Install dependencies: numpy, scipy, pytest
  ✅ Install sklearn in development mode

Step 4: Apply Test Patch (new tests from PR)
  + def test_warm_start_no_data_leak():
  +     """Test that warm_start doesn't leak training data"""
  +     ...

Step 5: Run Tests BEFORE Solution
  📊 Test Results:
     test_warm_start_no_data_leak()           → ❌ FAIL
     test_gradient_boosting_classifier()      → ✅ PASS
     test_gradient_boosting_regressor()       → ✅ PASS
     test_feature_importances()               → ✅ PASS
     test_early_stopping()                    → ✅ PASS
     ... 47 more tests ...                    → ✅ PASS

Step 6: Apply Gold Patch (the solution)
  sklearn/ensemble/_gb.py:
    - if self.warm_start:
    -     self._init_state()
    + if self.warm_start:
    +     self._init_state()
    +     self._clear_training_data()  # Fix: clear data

Step 7: Run Tests AFTER Solution
  📊 Test Results:
     test_warm_start_no_data_leak()           → ✅ PASS (Fixed!)
     test_gradient_boosting_classifier()      → ✅ PASS
     test_gradient_boosting_regressor()       → ✅ PASS
     test_feature_importances()               → ✅ PASS
     test_early_stopping()                    → ✅ PASS
     ... 47 more tests ...                    → ✅ PASS

Step 8-9: Label Test Categories
  📋 Fail-to-Pass (F2P): 1 test
     - test_warm_start_no_data_leak() (FAIL → PASS)

  📋 Pass-to-Pass (P2P): 51 tests
     - All other tests (PASS → PASS)

  📋 Total: 52 tests

Step 10: Validation
  ✅ At least 1 F2P test exists
  ✅ All tests pass after solution
  ✅ No installation errors

  → ✅ KEEP THIS INSTANCE

┌─────────────────────────────────────────────────────────────────┐
│ FINAL TASK INSTANCE                                              │
└─────────────────────────────────────────────────────────────────┘

instance_id: scikit-learn__scikit-learn-12345
repo: scikit-learn/scikit-learn
base_commit: abc123def456...
problem_statement: "GradientBoostingClassifier leaks training data..."
patch: <gold patch contents>
test_patch: <test patch contents>
FAIL_TO_PASS: ["test_warm_start_no_data_leak"]
PASS_TO_PASS: ["test_gradient_boosting_classifier", ... 50 more]

→ Ready for benchmark evaluation
```

---

## Task Instance Structure

Each final task instance contains:

```json
{
  "instance_id": "repo__repo-12345",
  "repo": "owner/repository",
  "base_commit": "abc123...",
  "created_at": "2023-06-15T10:30:00Z",
  "version": "1.2.0",
  "problem_statement": "Issue description + comments",
  "hints_text": "PR comments before initial commit",
  "patch": "diff --git a/file.py...",
  "test_patch": "diff --git a/test_file.py...",
  "FAIL_TO_PASS": ["test_foo", "test_bar"],
  "PASS_TO_PASS": ["test_existing_1", "test_existing_2", ...]
}
```

---

## Key Features of SWE-bench

### 1. Fully Automated Collection
- **Human labeling**: 0 hours for main dataset
- **Only manual work**: Creating "Verified" subset (500/2,294)
- **Scalability**: Can extend to any Python repository
- **Maintenance**: Can continuously add new instances

### 2. Execution-Based Validation
- **Objective evaluation**: Run tests, no subjective judgment
- **Automatic metric labeling**: F2P and P2P determined by execution
- **Robust verification**: Every instance validated before inclusion

### 3. Real-World Complexity
- **Large codebases**: Average 438K lines, 3,010 files
- **Long contexts**: Average 195-word issues
- **Multi-file edits**: Average 1.7 files, 3.0 functions edited
- **Comprehensive testing**: Median 51 tests per instance

### 4. Temporal Robustness
- **Continuously updatable**: New PRs = new instances
- **Post-training evaluation**: Can use PRs created after model training
- **No data contamination risk**: Always fresh tasks available

---

## Limitations and Design Choices

### What SWE-bench DOES Filter For:
1. ✅ Repository quality (popular, well-maintained)
2. ✅ Issue existence (PR must resolve an issue)
3. ✅ Test existence (PR must contribute tests)
4. ✅ Test executability (must run without errors)
5. ✅ Non-trivial solutions (at least 1 F2P test)

### What SWE-bench DOES NOT Filter For:
1. ❌ **Issue description quality** (no quality threshold)
2. ❌ Issue clarity or completeness
3. ❌ Presence of code examples in issues
4. ❌ Presence of reproduction steps
5. ❌ Issue length (varies 10-4,477 words)
6. ❌ Issue structure or formatting

### Implicit Quality Assumption

**Assumption**: Popular, well-maintained repositories → Better issue descriptions

**Reality**: Significant quality variation:
- Some issues: Detailed, with code examples, clear repro steps
- Some issues: Brief, vague, missing context
- No explicit filtering to ensure uniform quality

### SWE-bench Verified (Refined Subset)

**Purpose**: Address quality concerns in main dataset

**Process**:
- Manual review of 500 instances (from 2,294)
- Criteria:
  - ✅ Clearer issue descriptions
  - ✅ More stable test infrastructure
  - ✅ Better self-containment
  - ✅ Focus on functional bug fixes

**Implication**: Original dataset acknowledged to have quality issues

---

## Dataset Statistics Summary

| Metric | Value |
|--------|-------|
| **Initial PRs scraped** | ~90,000 |
| **After Stage II filtering** | ~15,000 (est.) |
| **Final dataset (Stage III)** | 2,294 |
| **Pass rate** | ~2.5% |
| **Repositories** | 12 |
| **Average issue length** | 195 words |
| **Average F2P tests** | 9.1 |
| **Average P2P tests** | 120.8 |
| **Average codebase size** | 438K lines, 3,010 files |
| **Average patch size** | 32.8 lines, 1.7 files, 3.0 functions |

---

## Comparison: SWE-bench vs SWE-bench Verified vs SWE-bench Lite

| Feature | SWE-bench | Verified | Lite |
|---------|-----------|----------|------|
| **Size** | 2,294 | 500 | 300 |
| **Source** | Automated | Manual review | Sampled |
| **Quality** | Mixed | High | High |
| **Focus** | All issues | Clearer issues | Bug fixes |
| **Repos** | 12 | 12 | 11 |
| **Use Case** | Long-term benchmark | Stable evaluation | Entry point |

---

## Reproducibility and Availability

**Data Availability**:
- Dataset: https://huggingface.co/datasets/princeton-nlp/SWE-bench
- Code: https://github.com/princeton-nlp/SWE-bench
- Leaderboard: https://www.swebench.com

**Repository Mirrors**:
- Organization: https://github.com/SWE-bench
- All 12 repositories mirrored
- Preserves commit history for reproducibility

---

## Citation

```bibtex
@inproceedings{jimenez2024swebench,
  title={SWE-bench: Can Language Models Resolve Real-World GitHub Issues?},
  author={Carlos E. Jimenez and John Yang and Alexander Wettig and
          Shunyu Yao and Kexin Pei and Ofir Press and Karthik Narasimhan},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2024}
}
```

---

**End of Document**
