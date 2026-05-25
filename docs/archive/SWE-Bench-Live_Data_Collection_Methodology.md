# SWE-bench-Live Data Collection Methodology

**Paper**: "SWE-bench Goes Live!"
**Authors**: Linghao Zhang et al., Microsoft
**Published**: May 2025 (arXiv:2505.23419v2)
**Source**: https://arxiv.org/pdf/2505.23419

---

## Overview

SWE-bench-Live is a **continuously-updated** benchmark for evaluating LLMs on real-world GitHub issue resolution. Unlike the original SWE-bench (static, 12 repos, manual curation), SWE-bench-Live introduces a **fully automated pipeline** that eliminates manual bottlenecks and enables scalable, contamination-resistant evaluation.

**Key Innovation**: **REPOLAUNCH** - An agentic framework that automatically creates Docker execution environments for each issue instance, removing the 200+ hours of manual setup required in prior benchmarks.

**Initial Release**:
- **1,319 task instances** from real GitHub issues created since 2024
- **93 repositories** (vs 12 in SWE-bench)
- **Fully automated** construction (0 manual effort)
- **Instance-level Docker images** for reproducible evaluation

---

## Motivation: Why SWE-bench-Live?

### Limitations of SWE-bench (Original)

1. **Staleness**: Not updated since release (Oct 2023)
   - Risk of data contamination in LLM training
   - Models may memorize solutions rather than generalize

2. **Limited Coverage**: Only 12 repositories
   - Narrow diversity in codebases, domains, practices
   - Weakens generalizability

3. **Manual Effort**:
   - Substantial human labor for instance construction
   - SWE-Gym reports >200 hours for environment setup
   - Multi-SWE-bench: 1 year + 68 annotators for 1,632 instances
   - Scalability bottleneck

### SWE-bench-Live Solution

✅ **Live-updating**: Monthly updates with fresh instances
✅ **Contamination-resistant**: Only includes issues created after 2024
✅ **Broad coverage**: 93 repositories (AI/ML, DevOps, Web, Database, CLI, Scientific)
✅ **Fully automated**: REPOLAUNCH pipeline removes manual bottlenecks
✅ **Scalable**: Can extend to any Python repository

---

## 3-Stage Collection Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│ Stage I: Repository Selection & Issue-PR Crawling           │
│   • Select 2,609 popular Python repos with open licenses    │
│   • Crawl issues created since 2024                         │
│   • Extract issue-PR pairs with test modifications          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage II: REPOLAUNCH - Automated Environment Setup          │
│   • Identify relevant files (CI/CD, README)                 │
│   • Select base Docker image (python:3.11, etc.)            │
│   • Interactive setup (agent-based, mimics developers)      │
│   • Verify tests pass in environment                        │
│   • Package as instance-level Docker image                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage III: Validating Task Instances                        │
│   • Apply test patch (new tests from PR)                    │
│   • Run tests BEFORE solution → Record results              │
│   • Apply fix patch (gold solution)                         │
│   • Run tests AFTER solution → Record results               │
│   • Compare: Identify F2P and P2P transitions               │
│   • Filter: Keep only instances with ≥1 F2P test            │
│   • Repeat multiple times to ensure consistency             │
└─────────────────────────────────────────────────────────────┘
                            ↓
         Valid SWE-bench-Live Instances (1,319)
```

---

## Stage I: Repository Selection & Raw Issue-PR Crawling

### Repository Selection Process

**Step 1: Initial Query** (via GitHub API, April 2025)
```python
filters = {
    "stars": "> 1,000",
    "language": "Python (primary)",
}
result = 8,577 repositories
```

**Step 2: Quality Filtering**
```python
filters = {
    "issues": "> 200",
    "pull_requests": "> 200",
    "forks": "> 200",
    "python_percentage": "> 60%",
}
result = 3,316 repositories
```

**Step 3: License Filtering**
```python
filters = {
    "license": "valid open-source license",
}
result = 2,609 repositories (final selection)
```

**Why These Criteria?**
- **Popularity** (>1,000 stars): Active development, maintained
- **Activity** (>200 issues/PRs): Sufficient data for extraction
- **Python-heavy** (>60%): Consistency with SWE-bench
- **Open license**: Legal compliance for benchmark

### Issue-PR Pair Extraction

**Adapted from SWE-bench** with improvements from SWE-Fixer:

**Requirements**:
1. ✅ Pull request **resolves a GitHub issue** (linked via "fixes #123", "closes #456")
2. ✅ Pull request **modifies test suite** (changes in test files)

**Temporal Filtering** (KEY for contamination resistance):
```python
# Only include issues created after January 1, 2024
issue_creation_date >= "2024-01-01"
```

**Why Post-2024?**
- Reduces data contamination risk (LLMs trained on data up to ~2023)
- Ensures fresh, unseen issues
- Enables "contamination-free" evaluation

**Improvements from SWE-Fixer**:
- More robust heuristics for issue-PR linking
- Reduces reliance on brittle string-matching
- Better identification of test-related changes

---

## Stage II: REPOLAUNCH - Automated Execution Environment Setup

### The Environment Setup Challenge

**Problem in Prior Benchmarks**:
- Manual environment setup is the **most labor-intensive** step
- SWE-bench: Manual setup per version tag (coarse granularity)
- SWE-Gym: >200 hours of manual effort
- Multi-SWE-bench: 1 year with 68 expert annotators

**Why So Hard?**
- Different commits need different dependencies
- Version compatibility issues ("dependency version drift")
- Manual installation steps from README/CI/CD
- Test suite configuration varies across repos
- Historical snapshots have outdated dependencies

### REPOLAUNCH: Agentic Automated Setup

**Definition**: An LLM-driven, agentic framework that mimics how human developers set up unfamiliar projects.

**Goal**: Create a **valid execution environment** = Docker container where:
1. Codebase is correctly installed from source
2. Repository's test suite passes (zero or tolerable failures)

**Architecture**: Agent-based workflow with 5 steps

---

### REPOLAUNCH Step-by-Step Process

#### **Step 1: Relevant Files Identification**

**Objective**: Find files with setup instructions

**Target Files**:
- CI/CD pipelines: `.github/workflows/*.yml`, `.travis.yml`, `Jenkinsfile`
- Documentation: `README.md`, `CONTRIBUTING.md`, `INSTALL.md`
- Configuration: `setup.py`, `pyproject.toml`, `requirements.txt`, `tox.ini`
- Scripts: `install.sh`, `Makefile`

**Method**: Pattern matching + file name heuristics

**Output**: List of relevant file paths + full contents

---

#### **Step 2: Base Image Selection**

**Objective**: Choose appropriate Docker base image

**Input**: Content of relevant files from Step 1

**Agent Task**:
```python
# Agent analyzes files to determine:
- Programming language: Python
- SDK version: e.g., Python 3.11, Python 3.9
- Base image: e.g., python:3.11, python:3.9-slim
```

**Example**:
```yaml
# From .github/workflows/ci.yml
python-version: ["3.11", "3.12"]
→ Agent selects: python:3.11 (lower version for compatibility)
```

**Action**: Instantiate Docker container, launch persistent bash session

---

#### **Step 3: Interactive Environment Setup** (Core Innovation)

**Objective**: Install dependencies and build project to pass tests

**Agent Design**: ReAct (Reason + Act) pattern
```
Loop:
  1. Thought: "Need to install dependencies"
  2. Action: Execute bash command (pip install -e .)
  3. Observation: Read exit code + output
  4. Thought: "Installation succeeded, now run tests"
  5. Action: Execute bash command (pytest)
  6. Observation: Check test results
  ... (iterate until tests pass or step limit reached)
```

**Agent Capabilities**:
- Execute bash commands in Docker container
- Read command outputs (stdout, stderr, exit codes)
- Search web for troubleshooting (e.g., "ImportError: X not found")
- Query issue tracker for known problems
- Iterative refinement (trial-and-error like developers)

**Example Session**:
```bash
# Agent iteration 1
$ pip install -e .
✅ Successfully installed package

# Agent iteration 2
$ pytest
❌ ERROR: ModuleNotFoundError: No module named 'numpy'

# Agent iteration 3 (reasoning: missing dependency)
$ pip install numpy
✅ Successfully installed numpy

# Agent iteration 4
$ pytest
✅ All tests passed
```

**Stopping Conditions**:
- All tests pass → Success
- Step limit reached (e.g., 50 iterations) → Transfer to verification

---

#### **Step 4: Verification**

**Objective**: Confirm environment is valid

**Verification Agent Tasks**:
1. Generate appropriate test command
   ```bash
   # Examples:
   pytest -rA                    # pytest with verbose output
   python -m unittest discover   # unittest
   tox -e py311                  # tox
   ```

2. Execute test command

3. Evaluate results:
   - All tests pass → Valid ✅
   - Some failures → Feed back to setup agent for refinement

**Validation Criteria**:
- Zero failures (ideal)
- OR tolerable failures (pre-existing, unrelated to issue)

**If validation fails**: Return control to Step 3 (setup agent)

---

#### **Step 5: Finalization**

**Objective**: Package as reusable Docker image

**Action**:
```bash
# Commit container state to image
docker commit <container_id> swebench-live/<instance_id>:latest

# Result: Instance-level execution environment
```

**Why Instance-Level?**
- **Original SWE-bench**: Version-level (one image per release, e.g., v1.2.0)
  - Coarse granularity
  - May not match exact commit state

- **SWE-bench-Live**: Instance-level (one image per issue)
  - Fine granularity
  - Exact snapshot at base commit
  - Handles commit-specific dependency differences

---

### Time-Machine Mechanism (Critical Innovation)

**Problem**: Dependency Version Drift

When setting up old repositories:
```python
# 2024 repository with unpinned dependencies
requirements.txt:
  numpy  # No version specified

# pip install numpy in 2025
→ Installs numpy 2.0 (latest)
→ But numpy 2.0 has breaking changes
→ 2024 code fails with 2025 numpy
```

**Solution**: Time-Machine Proxy for pip

```python
# Modified pip index server
# Only allows package versions released BEFORE base commit timestamp

base_commit_timestamp = "2024-06-15 10:30:00"

# When installing numpy:
pip install numpy
→ Proxy filters: Only numpy versions released ≤ 2024-06-15
→ Installs numpy 1.24.3 (compatible version)
→ Prevents "future" version incompatibilities
```

**Implementation**:
- Custom PyPI proxy server
- Filters package index by release date
- Ensures historical reproducibility
- **Dramatically improves setup success rates**

---

## Stage III: Validating Task Instances

### Objective

Confirm that each PR effectively resolves the issue through test-based validation.

### Validation Process

**For each candidate instance:**

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Setup Environment                                    │
│   • Use Docker image from REPOLAUNCH                         │
│   • Reset to base_commit                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Apply Test Patch                                     │
│   • Apply test changes from PR (new/modified tests)          │
│   • Command: git apply test.patch                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Run Tests BEFORE Solution                            │
│   • Execute test suite: pytest -rA                           │
│   • Parse results → Record test statuses                     │
│   • Example:                                                 │
│     - test_async_return_cmd → FAILED                         │
│     - test_space_sep → PASSED                                │
│     - test_bool_values → PASSED                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Apply Fix Patch                                      │
│   • Apply code changes from PR (the solution)                │
│   • Command: git apply fix.patch                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 5: Run Tests AFTER Solution                             │
│   • Execute test suite: pytest -rA                           │
│   • Parse results → Record test statuses                     │
│   • Example:                                                 │
│     - test_async_return_cmd → PASSED (Changed!)              │
│     - test_space_sep → PASSED                                │
│     - test_bool_values → PASSED                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 6: Identify Test Transitions                            │
│   • Compare before/after results                             │
│   • FAIL_TO_PASS (F2P):                                      │
│       test_async_return_cmd (FAILED → PASSED)                │
│   • PASS_TO_PASS (P2P):                                      │
│       test_space_sep (PASSED → PASSED)                       │
│       test_bool_values (PASSED → PASSED)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 7: Validation Decision                                  │
│   • KEEP if:                                                 │
│     - At least 1 FAIL_TO_PASS test ✅                        │
│     - Results consistent across multiple runs ✅             │
│   • REJECT if:                                               │
│     - Zero FAIL_TO_PASS tests ❌                             │
│     - Flaky tests (inconsistent results) ❌                  │
└─────────────────────────────────────────────────────────────┘
```

### Test Log Parsing

**Challenge**: Different testing frameworks produce different output formats

**Solution**: Framework-specific parsers

**Supported Frameworks**:
- **pytest**: Parses `pytest -rA` output
- **unittest**: Parses standard unittest output
- **tox**: Parses tox environment outputs
- **nose**: Parses nose test runner output

**Parser Outputs**:
```python
{
  "test_async_return_cmd": "FAILED",    # or "PASSED", "ERROR", "SKIPPED"
  "test_space_sep": "PASSED",
  "test_bool_values": "PASSED",
}
```

### Ensuring Consistency (Anti-Flaky)

**Problem**: Flaky tests produce inconsistent results

**Solution**: Multiple validation rounds

```python
# Run validation N times (e.g., N=3)
for i in range(3):
    results_before = run_tests_before_patch()
    results_after = run_tests_after_patch()
    f2p_set[i] = identify_fail_to_pass(results_before, results_after)

# Keep instance only if all runs agree
if len(set(f2p_set)) == 1:  # All runs produced same F2P set
    instance_valid = True
else:
    instance_valid = False  # Flaky tests, reject
```

**Why This Matters**: Ensures benchmark stability and reproducibility

---

## The Three Key Metrics (Same as SWE-bench)

### 1. RESOLVED (Primary Success Metric)

**Definition**: A task is RESOLVED if ALL three conditions are met:

```python
RESOLVED = (patch_applies == True) AND
           (all_F2P_tests == PASSED) AND
           (all_P2P_tests == PASSED)
```

**Requirements**:
- ✅ Model-generated patch applies cleanly (`git apply patch`)
- ✅ **ALL** fail-to-pass tests PASS (issue solved)
- ✅ **ALL** pass-to-pass tests PASS (no regressions)

**Benchmark Metric**:
```
Resolve Rate (%) = (# RESOLVED instances / Total instances) × 100
```

**SWE-bench-Live Results** (Initial Release):
- OpenHands + Claude 3.7 Sonnet: **19.25%** (best)
- SWE-agent + GPT-4.1: 18.57%
- SWE-agent + Claude 3.7 Sonnet: 17.13%

**Comparison to SWE-bench Verified**:
- Same agent/model on Verified: **43.20%**
- Same agent/model on Live: **19.25%**
- **Gap**: 2.2x harder on Live (likely due to contamination/overfitting on Verified)

---

### 2. Fail-to-Pass (F2P) Tests

**Definition**: Tests that were **FAILING** before the PR and **PASSING** after the PR.

**Labeling Process** (Automatic during Stage III):

```python
# Step 1: Run tests before solution
results_before = run_tests(codebase_at_base_commit)
# Example: {"test_A": "FAILED", "test_B": "PASSED", "test_C": "PASSED"}

# Step 2: Apply solution
apply_patch(fix_patch)

# Step 3: Run tests after solution
results_after = run_tests(codebase_with_patch)
# Example: {"test_A": "PASSED", "test_B": "PASSED", "test_C": "PASSED"}

# Step 4: Identify F2P
F2P = [test for test in results_before
       if results_before[test] in ["FAILED", "ERROR"]
       and results_after[test] == "PASSED"]
# Result: ["test_A"]
```

**Statistics** (SWE-bench-Live):
- **Average**: 5.4 F2P tests per instance
- **Median**: 1 F2P test
- **Minimum**: 1 (enforced by Stage III filter)

**Purpose**:
- Verifies the issue was actually resolved
- Tests the new functionality or bug fix
- Directly evaluates whether the patch addresses the problem

**Example**:
```python
# Issue: "sh 2.x doesn't preserve kwargs in async calls"
# F2P test (added in PR):
def test_async_return_cmd():
    """Test that async calls preserve return_cmd kwarg"""
    result = sh.ls(_async=True, _return_cmd=True)
    assert isinstance(result, Command)

# Before PR: FAILED (kwargs lost)
# After PR: PASSED (kwargs preserved)
```

---

### 3. Pass-to-Pass (P2P) Tests

**Definition**: Tests that were **PASSING** before the PR and must **remain PASSING** after the PR.

**Labeling Process** (Automatic during Stage III):

```python
# From same test runs as F2P:
P2P = [test for test in results_before
       if results_before[test] == "PASSED"
       and results_after[test] == "PASSED"]
# Result: ["test_B", "test_C"]
```

**Statistics** (SWE-bench-Live):
- **Average**: 2,953.4 P2P tests per instance
- **Median**: 1,865 P2P tests
- **Much larger** than F2P (most tests are P2P)

**Purpose**:
- Ensures no regressions
- Verifies existing functionality still works
- Tests that the fix doesn't break unrelated code

**Example**:
```python
# Issue: "Fix async kwargs"
# P2P tests (existing, must still pass):
def test_space_sep():
    """Test space-separated command arguments"""
    result = sh.ls("-l", "-a")
    assert result  # Must still work

def test_bool_values():
    """Test boolean flag conversion"""
    result = sh.command(_flag=True)
    assert "--flag" in result  # Must still work

# Before PR: PASSED
# After PR: Must remain PASSED (no regression)
```

---

## Visual Example: Complete Pipeline

```
Repository: amoffat/sh (shell command library)
Issue #744: "sh 2.x doesn't preserve return_cmd kwarg in async calls"
Created: 2024-03-15
PR #745: "Fix kwarg preservation in async execution"

┌─────────────────────────────────────────────────────────────┐
│ STAGE I: Repository Selection & Crawling                    │
│ ✅ sh has 7.4k stars (popular)                              │
│ ✅ >200 issues/PRs (active)                                 │
│ ✅ MIT license (open)                                       │
│ ✅ Issue created 2024-03-15 (post-2024)                     │
│ ✅ PR #745 resolves Issue #744                              │
│ ✅ PR modifies test files (test_sh.py)                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ STAGE II: REPOLAUNCH - Automated Setup                      │
│ Step 1: Identify relevant files                             │
│   • Found: README.rst, .github/workflows/ci.yml, setup.py   │
│ Step 2: Select base image                                   │
│   • Detected: Python 3.11 from CI config                    │
│   • Selected: python:3.11                                   │
│ Step 3: Interactive setup                                   │
│   Agent iteration 1:                                        │
│     $ pip install -e .                                       │
│     ✅ Success                                               │
│   Agent iteration 2:                                        │
│     $ pytest -rA                                             │
│     ✅ 142 passed                                            │
│ Step 4: Verification                                         │
│   • Test command: pytest -rA                                │
│   • All tests pass ✅                                        │
│ Step 5: Finalization                                         │
│   • Image: swebench-live/amoffat__sh-744:latest             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ STAGE III: Validation                                        │
│ Run 1 of 3:                                                 │
│   Step 1: Apply test patch (adds test_async_return_cmd)     │
│   Step 2: Run tests BEFORE solution                         │
│     test_async_return_cmd → ❌ FAILED                        │
│     test_space_sep → ✅ PASSED                               │
│     test_bool_values → ✅ PASSED                             │
│     ... 139 more tests → ✅ PASSED                           │
│   Step 3: Apply fix patch (modifies sh.py)                  │
│   Step 4: Run tests AFTER solution                          │
│     test_async_return_cmd → ✅ PASSED (F2P!)                 │
│     test_space_sep → ✅ PASSED (P2P)                         │
│     test_bool_values → ✅ PASSED (P2P)                       │
│     ... 139 more tests → ✅ PASSED (P2P)                     │
│   Step 5: Identify transitions                              │
│     F2P: ["test_async_return_cmd"]                          │
│     P2P: ["test_space_sep", "test_bool_values", ... +139]   │
│ Run 2 of 3: ✅ Same F2P/P2P sets                            │
│ Run 3 of 3: ✅ Same F2P/P2P sets                            │
│ Decision: ✅ KEEP (consistent results, 1 F2P test)          │
└─────────────────────────────────────────────────────────────┘

Final Task Instance:
{
  "instance_id": "amoffat__sh-744",
  "repo": "amoffat/sh",
  "base_commit": "a1b2c3d...",
  "created_at": "2024-03-15T10:30:00Z",
  "problem_statement": "When using sh 2.x with async...",
  "patch": "diff --git a/sh.py ...",
  "test_patch": "diff --git a/test_sh.py ...",
  "FAIL_TO_PASS": ["test_async_return_cmd"],
  "PASS_TO_PASS": ["test_space_sep", ... +141 tests],
  "image_key": "swebench-live/amoffat__sh-744:latest",
  "test_cmds": ["pytest -rA"],
  "log_parser": "pytest"
}
```

---

## Key Differences: SWE-bench vs SWE-bench-Live

| Aspect | SWE-bench (Original) | SWE-bench-Live |
|--------|---------------------|----------------|
| **Release Date** | Oct 2023 | May 2025 (ongoing) |
| **Instances** | 2,294 (static) | 1,319 (initial), continuously updated |
| **Repositories** | 12 | 93 |
| **Issue Creation** | Pre-2023 | Post-2024 (Jan 2024+) |
| **Contamination Risk** | High (static, public) | Low (fresh, rotating) |
| **Environment Setup** | Manual (version-level) | Automated (instance-level) |
| **Docker Images** | Per version tag | Per instance |
| **Human Effort** | Manual curation | 0 hours (fully automated) |
| **Scalability** | Limited (manual bottleneck) | High (automated pipeline) |
| **Update Frequency** | Never (static) | Monthly |
| **Solve Rates** | 43% (Verified, OpenHands+Claude) | 19% (Live, same setup) |

**Performance Gap**:
- Same agent + model achieves **2.2x higher** solve rate on SWE-bench Verified vs Live
- Suggests overfitting/contamination on static benchmarks
- Live benchmark is "contamination-resistant" and more challenging

---

## Dataset Statistics (Initial Release)

### Repository-Level Statistics

| Metric | Average | Median |
|--------|---------|--------|
| **Repositories** | 93 | - |
| **Lines of Code (Python)** | 85K | 52K |
| **Files (Python)** | 423 | 222 |

### Instance-Level Statistics

| Metric | Average | Median |
|--------|---------|--------|
| **Total Instances** | 1,319 | - |
| **Files Edited (gold patch)** | 3.3 | 2 |
| **Hunks (gold patch)** | 9.0 | 3 |
| **Lines Edited (gold patch)** | 102.6 | 24 |
| **Fail-to-Pass Tests** | 5.4 | 1 |
| **Pass-to-Pass Tests** | 2,953.4 | 1,865 |

### Repository Diversity

**Domain Distribution** (93 repos):
- **AI/ML**: 26 repos (keras, instructlab, pytorch/torchtune)
- **DevOps**: 23 repos (conan, pylint, sphinx)
- **Web**: 17 repos (reflex, flask, requests)
- **Database**: 8 repos (xarray, geopandas)
- **Scientific**: 8 repos (pvlib, shapely, sympy)
- **CLI**: 4 repos (streamlink, beets, yt-dlp)
- **Misc**: 3 repos (matplotlib, fonttools)
- **Cloud**: 2 repos (aws-cloudformation)
- **Desktop**: 2 repos (qtile, Solaar)

### Temporal Distribution

Issues evenly distributed from 2024-01 to 2025-04:
- 2024 Q1: ~250 instances
- 2024 Q2: ~280 instances
- 2024 Q3: ~260 instances
- 2024 Q4: ~270 instances
- 2025 Q1: ~259 instances

→ Consistent coverage over time

---

## Comparison with Other Benchmarks

| Benchmark | Date | Instances | Repos | Real/Synthetic | Curation |
|-----------|------|-----------|-------|----------------|----------|
| **SWE-bench** | Oct 2023 | 2,294 | 12 | Real | Manual |
| **SWE-bench Verified** | Aug 2024 | 500 | 12 | Real | Manual |
| **SWE-Gym** | Dec 2024 | 2,438 | 11 | Real | Manual |
| **Multi-SWE-bench** | Apr 2025 | 1,632 | 39 | Real | Manual |
| **SWE-smith** | Apr 2025 | 50,000 | 128 | Synthetic | Semi-manual |
| **SWE-bench-Live** | Apr 2025 | **1,319** | **93** | **Real** | **Automatic** |

**Unique Advantages**:
- ✅ Only live-updating benchmark
- ✅ Only fully automated construction
- ✅ Broadest repository coverage
- ✅ Contamination-resistant (post-2024 issues)
- ✅ Instance-level Docker environments

---

## Experimental Results

### Best Performing Combinations (Full Dataset)

| Agent | Model | Resolve Rate | Apply Rate | Localization Success |
|-------|-------|--------------|------------|---------------------|
| **OpenHands** | Claude 3.7 Sonnet | **19.25%** | 85.89% | 48.29% |
| **SWE-agent** | GPT-4.1 | 18.57% | 94.54% | 49.50% |
| **SWE-agent** | Claude 3.7 Sonnet | 17.13% | 89.15% | 45.86% |

### SWE-bench Repos vs Non-SWE-bench Repos

| Instance Source | Avg Repo Files | Avg Repo LoC | Resolve Rate |
|-----------------|----------------|--------------|--------------|
| **From SWE-bench Repos** | 744 | 223K | **22.96%** |
| **From Non-SWE-bench Repos** | 383 | 68K | 18.89% |

**Insight**: Higher solve rate on SWE-bench repos despite larger size → Suggests overfitting to original benchmarks

### Difficulty Analysis

**Patch Difficulty** (files × lines):
- **Single-file, <5 lines**: ~48% solve rate
- **Multi-file (3+)**: <10% solve rate
- **7+ files**: 0% solve rate
- **>100 lines**: <10% solve rate

**Repository Difficulty** (files × LoC):
- **<100 files, <20K LoC**: >20% solve rate
- **>500 files**: <5% solve rate

---

## Key Innovations Summary

### 1. **REPOLAUNCH - Automated Environment Setup**
- ✅ LLM-driven agentic workflow
- ✅ Mimics human developer setup process
- ✅ Time-machine mechanism for version compatibility
- ✅ Instance-level Docker images
- ✅ Eliminates 200+ hours of manual effort

### 2. **Continuous Updates**
- ✅ Monthly refresh with new instances
- ✅ Only post-2024 issues (contamination-resistant)
- ✅ Reflects evolving software landscape

### 3. **Scalability**
- ✅ Fully automated pipeline (0 manual hours)
- ✅ Can extend to any Python repository
- ✅ No annotation bottleneck

### 4. **Broad Coverage**
- ✅ 93 repositories (vs 12 in SWE-bench)
- ✅ Diverse domains (AI/ML, DevOps, Web, etc.)
- ✅ 1,319 instances (growing monthly)

---

## Limitations

### Current Limitations

1. **Language**: Python only (initial release)
   - Future: May extend to JavaScript, Java, Rust

2. **LLM Randomness**:
   - Experiments use temperature=0 to minimize
   - No multiple runs due to budget constraints

3. **Compute Resources**:
   - Requires substantial compute for validation
   - 128-core CPU, 2TB RAM for full pipeline

4. **License Requirements**:
   - Only open-source licensed repos
   - Excludes proprietary code

### Known Challenges

- **REPOLAUNCH success rate**: Not 100% (some repos too complex)
- **Test flakiness**: Multi-round validation helps but not perfect
- **Historical dependencies**: Time-machine helps but not infallible

---

## Future Plans

**Monthly Updates**:
- Add new instances from fresh issues
- Continuously expand repository coverage
- Maintain temporal freshness

**Language Expansion**:
- JavaScript/TypeScript
- Java
- Rust
- Go

**Infrastructure Open-Source**:
- REPOLAUNCH framework will be released
- Can assist developers in setting up unfamiliar codebases
- Broader applicability beyond benchmarking

---

## Citation

```bibtex
@article{zhang2025swebench,
  title={SWE-bench Goes Live!},
  author={Zhang, Linghao and He, Shilin and Zhang, Chaoyun and
          Kang, Yu and Li, Bowen and Xie, Chengxing and
          Wang, Junhao and Wang, Maoquan and Huang, Yufan and
          Fu, Shengyu and others},
  journal={arXiv preprint arXiv:2505.23419},
  year={2025}
}
```

---

## Links

- **Homepage**: https://swe-bench-live.github.io/
- **GitHub**: https://github.com/SWE-bench-Live
- **Dataset**: https://huggingface.co/SWE-bench-Live
- **Leaderboard**: https://swe-bench-live.github.io/

---

**End of Document**
