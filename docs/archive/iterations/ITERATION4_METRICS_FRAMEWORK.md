# Iteration 4: Complete Metrics Framework with SWE-bench Evaluation

**Date**: 2026-03-16
**Status**: 🔄 Running (2-issue test in progress)
**Goal**: Measure full impact of patch quality improvements with comprehensive metrics

---

## What Changed in Iteration 4

### 1. **Workflow Improvements** ✅ Applied
- Fixed critical source code truncation bug (line 286)
- Changed from `... (N more lines)` → `[SOURCE TRUNCATED - N lines omitted]`
- Impact: Prevents LLM from learning truncation notation

### 2. **Enhanced Metrics Collection** ✅ Implemented
Now collecting **7 comprehensive metric categories**:

| Metric | Source | Why It Matters |
|--------|--------|----------------|
| **Resolution Rate** | SWE-bench harness | ✅ Binary: Issue fully resolved (all F2P pass, no P2P fail) |
| **Fix Rate (SWE-EVO)** | Computed from F2P/P2P | ✅ Nuanced: `(F2P_resolved/F2P_total) - (P2P_broken/P2P_total)` |
| **F2P Progress Rate** | SWE-bench harness | ✅ How many failing tests were fixed |
| **P2P Regression Rate** | SWE-bench harness | ✅ How many passing tests broke (lower is better) |
| **Patch Apply Rate** | Validation module | ✅ Can patch be applied via `git apply`? |
| **Token Usage** | Solver logs | Cost estimation |
| **Wall Clock Time** | Solver logs | Efficiency measurement |

---

## Full Evaluation Pipeline

```
[Step 1] Generate Patches
   ↓
   - OpenHands solver with gpt-oss:120b
   - Enhanced prompts (anti-truncation)
   - Validation + Sanitization + Retry
   - Output: results/iteration4_improved_patches/*.json

[Step 2] Convert to SWE-bench Format
   ↓
   - Extract patches from solver outputs
   - Format as SWE-bench predictions JSONL
   - Output: eval_results/swebench/iteration4_improved_predictions/*.jsonl

[Step 3] Run SWE-bench Harness
   ↓
   - Docker-based evaluation
   - Runs FAIL_TO_PASS tests (should pass after fix)
   - Runs PASS_TO_PASS tests (should remain passing)
   - Output: logs/run_evaluation/iteration4_improved/*/report.json

[Step 4] Compute Comprehensive Metrics
   ↓
   - Aggregates harness results
   - Computes file overlap, content similarity
   - Tracks efficiency metrics
   - Output: eval_results/swebench/iteration4_improved_comprehensive_metrics.json

[Step 5] Compute Fix Rate Metrics (SWE-EVO)
   ↓
   - Applies SWE-EVO formula
   - Penalizes regressions
   - Output: eval_results/swebench/iteration4_improved_fix_rate_metrics.json
```

---

## Expected Results vs. Iteration 3

| Metric | Iteration 3 (Baseline) | Iteration 4 (Expected) | Improvement |
|--------|------------------------|------------------------|-------------|
| **Patch Apply Rate** | 10-20% | **40-50%** | +100-150% |
| **Resolution Rate** | ~0-10% | 10-20% | +100%+ |
| **F2P Progress** | 0-25% | 20-40% | +60-100% |
| **Fix Rate (SWE-EVO)** | -50% to 0% | 10-30% | Positive fix rate! |
| **P2P Regression** | 99%+ | 60-80% | -20-39% |
| **Truncation Errors** | 80-90% | <10% | -80%+ |

**Key Hypothesis**: Fixing the truncation bug should cascade into better patches → higher apply rate → more testable → better F2P/P2P outcomes.

---

## Metrics Definitions

### A. Correctness Metrics

#### 1. **Resolution Rate** (Binary)
```python
resolved = (all F2P tests pass) AND (no P2P tests fail)
resolution_rate = resolved_issues / total_issues
```
- **Standard SWE-bench metric**
- Most conservative: issue is either fully fixed or not
- Used for comparison with published results

#### 2. **Fix Rate (SWE-EVO Formula)**
```python
fix_rate = (F2P_resolved / F2P_total) - (P2P_broken / P2P_total)
```
- **Research metric** - more nuanced than binary
- Rewards partial F2P progress
- Penalizes P2P regressions
- Range: -1.0 (all P2P broken) to +1.0 (all F2P fixed, no regressions)

#### 3. **F2P Progress Rate**
```python
f2p_progress = F2P_tests_passed / F2P_total_tests
```
- How many failing tests did we fix?
- Does NOT penalize regressions
- Shows forward progress even if regressions exist

#### 4. **P2P Regression Rate**
```python
p2p_regression = P2P_tests_failed / P2P_total_tests
```
- How many passing tests did we break?
- Lower is better (0% = no regressions)
- Critical for production deployment

### B. Patch Quality Metrics

#### 5. **Patch Apply Rate**
```python
patch_applies = successful_git_apply / total_patches
```
- **Gating metric** - if patch doesn't apply, F2P/P2P can't be measured
- Improved by our validation + sanitization pipeline
- Direct indicator of patch format correctness

### C. Efficiency Metrics

#### 6. **Token Usage**
```python
total_tokens = input_tokens + output_tokens
cost_usd = (input_tokens * $X/1K) + (output_tokens * $Y/1K)
```
- Practical deployment consideration
- Helps compare different models/approaches

#### 7. **Wall Clock Time**
```python
wall_clock_time = end_time - start_time  # seconds
```
- User-facing latency
- Includes LLM inference + retry attempts

---

## Test Plan

### Phase 1: 2-Issue Validation (Current)
**Status**: 🔄 Running
**Duration**: ~30-40 minutes
**Goal**: Verify full pipeline works end-to-end

**Validation Criteria**:
- ✅ Patches generate successfully
- ✅ Patches apply (validation passes)
- ✅ Harness evaluation completes
- ✅ All 7 metrics are collected
- ✅ No truncation errors

### Phase 2: Full 10-Issue Run (If Phase 1 succeeds)
**Duration**: ~2.5-3 hours
**Goal**: Complete benchmark with all agents

**Expected Outputs**:
1. `results/iteration4_improved_patches/` - All 10 patch JSONs
2. `logs/run_evaluation/iteration4_improved/` - Harness logs with F2P/P2P
3. `eval_results/swebench/iteration4_improved_comprehensive_metrics.json`
4. `eval_results/swebench/iteration4_improved_fix_rate_metrics.json`

---

## Analysis Plan

Once full results are available:

1. **Compare with Iteration 3**
   - Side-by-side metrics table
   - Statistical significance tests
   - Improvement percentages

2. **Error Analysis**
   - Which issues still fail?
   - What error types remain?
   - Are there new failure modes?

3. **Ablation Study**
   - Impact of truncation fix alone
   - Impact of validation alone
   - Impact of sanitization alone
   - Impact of retry mechanism alone

4. **Paper Contributions**
   - RQ1: Does issue enhancement improve resolution?
   - RQ2: Which enhancement strategies work best?
   - RQ3: What are the trade-offs?

---

## Files Updated

- ✅ `scripts/enhancers/run_solving_after_enhancement.py` (line 286 fix)
- ✅ `src/solvers/openhands/agent.py` (validation/sanitization/retry)
- ✅ `src/utils/patch_validator.py` (NEW - validation module)
- ✅ `src/utils/patch_sanitizer.py` (NEW - sanitization module)
- ✅ `scripts/run_full_evaluation_pipeline.sh` (NEW - end-to-end pipeline)

---

## Next Steps After Results

1. **Generate Analysis Report**
   - Iteration 3 vs 4 comparison
   - Metric breakdowns
   - Key findings

2. **Update Documentation**
   - MAIN.md
   - CHANGELOG.md
   - PATCH_IMPROVEMENT.md

3. **Prepare for Paper**
   - Results tables
   - Figures
   - Statistical tests
