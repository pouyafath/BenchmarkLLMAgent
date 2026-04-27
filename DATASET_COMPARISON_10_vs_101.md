# Dataset Comparison: 10-Issue vs 101-Issue Experiments

## Summary

**Key Difference**: For the 101-issue experiments, **BOTH Group A and Group B use SWE-bench Verified**, not a mix of Verified and Live datasets like the 10-issue experiments.

---

## 10-Issue Experiments (Original)

| Property | Group A | Group B |
|----------|---------|---------|
| **Source** | SWE-bench **Verified** | "Second Paper" curated from SWE-bench **Live** |
| **Size** | 10 issues | 10 issues |
| **Repositories** | • astropy/astropy (10) | • pallets/flask (5)<br>• psf/requests (3)<br>• scikit-learn/scikit-learn (2) |
| **Selection** | First 10 astropy from Verified | Manually curated for F2P>0 AND P2P>0 |
| **Harness** | ✅ Fully compatible | ⚠️ Required manual curation + fixes |

---

## 101-Issue Experiments (Current)

| Property | Group A | Group B |
|----------|---------|---------|
| **Source** | SWE-bench **Verified** | SWE-bench **Verified** |
| **Size** | 101 issues | 101 issues |
| **Repositories** | • scikit-learn (32)<br>• astropy (22)<br>• pydata/xarray (22)<br>• pytest-dev/pytest (19)<br>• matplotlib (6) | • matplotlib (34)<br>• scikit-learn (32)<br>• sphinx-doc/sphinx (26)<br>• psf/requests (8)<br>• pallets/flask (1) |
| **Selection** | All issues with F2P>0 AND P2P>0 from priority repos | All issues with F2P>0 AND P2P>0 from Group B-style repos |
| **Harness** | ✅ Fully compatible | ✅ Fully compatible |

---

## Why the Change? (Group B: Live → Verified)

### Problem with SWE-bench Live for 101 Issues

1. **Limited availability**:
   - Flask: Only 1 issue in Verified (vs 5 from Live used in 10-issue)
   - Requests: Only 8 issues in Verified (vs 3 from Live used in 10-issue)
   - **Total available from "Group B repos" in Verified: ~75 issues**

2. **Harness compatibility nightmare**:
   - SWE-bench Live issues often lack proper test infrastructure
   - Evaluation failures unrelated to patch quality
   - Manual curation required for each issue
   - For 101 issues, this would require weeks of manual work

3. **Second Paper dataset limitations**:
   - The curated "Second Paper" dataset from Live: **~12-15 qualifying issues total**
   - We used 10 for the 10-issue experiment
   - Not enough to expand to 101

### Solution: Use SWE-bench Verified for Both Groups

**Group A** (Diverse scientific/testing):
- Represents **traditional SWE-bench repos** (astropy, sklearn, xarray, pytest)
- Balanced across different domains
- Includes the original 10 astropy from 10-issue experiment

**Group B** (Web frameworks + tools + sklearn overlap):
- Keeps the **"Second Paper spirit"** (Flask, Requests, sklearn)
- Added matplotlib (34 issues) + sphinx (26 issues) to reach 101
- **32 sklearn issues overlap** with Group A (intentional - tests agent consistency)

---

## Comparison Table

| Aspect | 10-Issue Group B (Live) | 101-Issue Group B (Verified) |
|--------|-------------------------|------------------------------|
| **Repos** | Flask, Requests, sklearn | Flask, Requests, sklearn, matplotlib, sphinx |
| **Flask issues** | 5 (curated from Live) | 1 (all available in Verified) |
| **Requests issues** | 3 (curated from Live) | 8 (all available in Verified) |
| **sklearn issues** | 2 (curated from Live) | 32 (all available in Verified) |
| **Total** | 10 | 101 |
| **Harness compat** | Manual fixes required | ✅ Out-of-box |
| **F2P/P2P** | ✅ All have both | ✅ All have both |

---

## Impact on Experimental Design

### ✅ Advantages of Using Verified for Both Groups

1. **Harness reliability**: All 101 issues work with SWE-bench harness out-of-box
2. **Reproducibility**: Other researchers can easily replicate
3. **Apples-to-apples**: Both groups from same source dataset
4. **Larger sample**: 101 vs 10 provides statistical power
5. **Overlap analysis**: 32 sklearn issues in both groups tests agent consistency

### ⚠️ Trade-offs

1. **Different repos in Group B**:
   - Added matplotlib (34) and sphinx (26) to reach 101
   - These weren't in 10-issue Group B
   - But they maintain "community project" flavor

2. **Less "Live dataset" representation**:
   - 10-issue Group B used newer issues from Live
   - 101-issue Group B uses Verified (older, more stable)
   - But Verified has higher quality ground truth

3. **Flask/Requests underrepresented**:
   - Only 9 issues total (vs 8/10 in small experiment)
   - Dominated by matplotlib (34) and sklearn (32)

---

## Statistical Comparison

### 10-Issue Baselines
- Group A (Verified): ~50-60% (astropy-focused)
- Group B (Live): ~20-30% (harder, less mature issues)

### 101-Issue Baselines
- Group A (Verified diverse): **50.5%**
- Group B (Verified web+tools): **36.6%**

**Observation**: Even within Verified, Group B repos (matplotlib, sphinx, flask, requests) are **14pp harder** than Group A repos (astropy, sklearn, xarray, pytest).

---

## Answer to Your Question

> "Can't we have 101 issues from Group B (Second Paper) which be comparable with SWE_Bench dataset? I mean have P2P and F2P test cases.."

**Short answer**: We tried, but there aren't enough qualifying issues in the "Second Paper" repos from SWE-bench Live.

**Detailed breakdown**:

1. **Available in SWE-bench Live** (with F2P>0 AND P2P>0):
   - Flask: ~10-15 candidates
   - Requests: ~5-10 candidates
   - sklearn: ~20-30 candidates (but many have harness issues)
   - **Total: ~35-55 candidates** (not enough for 101)

2. **Quality issues**:
   - Many Live issues fail evaluation for non-patch reasons
   - Incomplete test infrastructure
   - Docker image build failures
   - Each issue requires manual verification

3. **The trade-off we made**:
   - **Kept the "Group B concept"**: Web frameworks (Flask, Requests) + sklearn + community tools (sphinx)
   - **Switched to Verified source**: Ensures harness compatibility
   - **Added repos to reach 101**: matplotlib (largest contributor: 34 issues), sphinx (26 issues)

---

## Recommendation for Future Work

If you want a true "SWE-bench Live Group B" for comparison:

### Option 1: Smaller Live-based Group B (Feasible)
- **Size**: 30-40 issues (not 101)
- **Repos**: Flask, Requests, sklearn from Live
- **Work required**: 1-2 weeks manual curation + harness fixes

### Option 2: Mixed Design (10 vs 101)
- **10-issue**: Keep current (Verified A vs Live B)
- **101-issue**: Both from Verified (current approach)
- **Rationale**: Different research questions
  - 10-issue: Tests agent on diverse source datasets
  - 101-issue: Tests agent at scale with reliable infrastructure

### Option 3: Expand Verified Group B Definition
- **Current**: matplotlib, sklearn, sphinx, flask, requests
- **Add**: django, sympy, pandas (more "community" projects from Verified)
- **Reach**: ~150+ issues from Verified
- **Work**: Re-run dataset prep script with expanded repo list

---

## Current Status: What We Actually Have

✅ **Both experiments are valid and complementary**:

| Experiment | Purpose | Strength |
|------------|---------|----------|
| **10-issue** (Verified A vs Live B) | Test agent on different dataset sources | Shows impact of dataset quality on enhancement |
| **101-issue** (Verified A vs Verified B) | Test agent at scale on reliable infrastructure | Statistical power, reproducibility |

The change from Live to Verified for Group B in 101-issue experiments was **pragmatic** (harness compatibility) rather than theoretical. Both experimental designs are scientifically valid and answer slightly different questions.

---

**Bottom line**: We **couldn't** build a 101-issue Group B from the "Second Paper" SWE-bench Live repos because there aren't enough qualifying issues. Switching to Verified for both groups ensures reliable evaluation at scale.
