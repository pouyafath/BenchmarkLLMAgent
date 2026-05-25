# Feasibility Analysis: Dataset for Issue Enhancement Benchmark

## Research Goal

Create a dataset for benchmarking **issue enhancement agents** that:
- **Includes varying quality** issue descriptions (poor, mediocre, good)
- **Does NOT filter** for high-quality issues like SWE-bench Verified
- Enables analysis of **when enhancement helps vs hurts**
- Follows SWE-bench methodology for F2P/P2P/RESOLVED metrics

---

## Why This Dataset is Needed

### Problem with Current SWE-bench (Verified)

**SWE-bench Verified Bias**:
- Manually curated for "clearer issue descriptions"
- Filters FOR high-quality issues
- Your experiments use Verified (101 issues)

**Result**: Enhancement mostly **hurts** because:
```
Good Issue (clear, detailed)
  ↓ Enhancement (Aider rewrites)
  ↓ Degraded Issue (loses critical details)
  ↓ Solver fails (-45.5%)
```

### What We Actually Need to Test

**Enhancement should help different quality levels differently**:

| Issue Quality | Enhancement Effect | Hypothesis |
|---------------|-------------------|------------|
| **Poor** (vague, brief) | Should **HELP** ✅ | Add missing details → Solver succeeds |
| **Mediocre** (decent but incomplete) | Should be **NEUTRAL** ± | Some help, some hurt |
| **Good** (clear, detailed) | Should **HURT** ❌ | Rewrite loses details → Solver fails |

**Your Current Finding**: Enhancement hurts overall (-5% to -45%)
**Why**: Testing only on good issues (Verified subset)

**What We Need**: Mixed-quality dataset to measure enhancement across quality spectrum.

---

## Proposed Dataset: "SWE-bench-Mixed-Quality"

### Dataset Specification

```yaml
Name: SWE-bench-MQ (Mixed Quality)
Size: 2,000-3,000 instances
Quality Distribution:
  - Poor quality: 30-40% (600-1,200 instances)
  - Mediocre quality: 30-40% (600-1,200 instances)
  - Good quality: 20-40% (400-1,200 instances)

Methodology: SWE-bench 3-stage pipeline with modifications
Metrics: RESOLVED, F2P, P2P (same as SWE-bench)
New Analysis: Issue quality correlation with enhancement effectiveness
```

---

## Three Approaches (Ranked by Feasibility)

### **Option 1: Use Full SWE-bench (2,294) Instead of Verified (500)**

#### Description
Simply use the original SWE-bench dataset without Verified filtering.

#### Why It Works
- SWE-bench (full) was **NOT** filtered for issue quality
- Only Stage III validation (tests work)
- Includes mix of poor, mediocre, good issues
- Verified is a **subset** with manual quality curation
- Using full dataset = getting the unfiltered quality mix

#### Effort Required

| Aspect | Effort |
|--------|--------|
| **Human labeling** | **0 hours** ⭐ |
| **Data collection** | **0 hours** (already exists) ⭐ |
| **Infrastructure setup** | **0 hours** (your setup works) ⭐ |
| **Time to deploy** | **Immediate** ⭐ |
| **Compute cost** | **$0** (dataset exists) ⭐ |

#### Advantages
✅ Zero effort - dataset exists
✅ Immediate availability
✅ 2,294 instances (10x larger than your 101)
✅ Same repos as your current work
✅ Already has F2P/P2P labels
✅ All your analysis scripts work immediately

#### Disadvantages
❌ Quality distribution unknown (no labels)
❌ Still biased toward "popular repos" (Stage I filter)
❌ May not have enough truly poor issues

#### How to Implement

**Step 1**: Download full SWE-bench
```bash
from datasets import load_dataset
dataset = load_dataset("princeton-nlp/SWE-bench", split="test")
# Get all 2,294 instances (not just Verified)
```

**Step 2**: Sample 200-300 for manual quality labeling
```python
# Random sample for quality analysis
sample = dataset.sample(n=250)
# Manual labeling: poor/mediocre/good
# Time: ~5 minutes per issue × 250 = ~20 hours
```

**Step 3**: Run your experiments on full dataset
```bash
# Use same pipeline, just point to full SWE-bench
--dataset-jsonl swe_bench_full_2294.jsonl
```

#### Quality Estimation (Hypothesis)
Based on "Verified" being 500/2,294 (22%):
```
Full SWE-bench (2,294):
  - Good quality: ~500 (22%) [Verified subset]
  - Mediocre quality: ~1,200 (52%)
  - Poor quality: ~600 (26%)
```

#### Cost-Benefit Analysis
- **Cost**: $0, 0 hours
- **Benefit**: 10x more data, mixed quality
- **Risk**: Low (safe, reversible)
- **Recommendation**: **START HERE** ⭐⭐⭐

---

### **Option 2: Extend SWE-bench Pipeline to More Repos**

#### Description
Run the original SWE-bench collection pipeline on 50-100 repositories instead of 12, including less-maintained repos.

#### Changes to SWE-bench Pipeline

**Modified Stage I**: Repository Selection
```diff
- Top 12 most popular Python repos
- Focus on "well-maintained, clear guidelines"
+ Top 50-100 Python repos
+ Include medium-popularity repos (10K-100K downloads/month)
+ Relax "clear guidelines" requirement
```

**Keep Stage II & III**: Same filters
- PR resolves issue ✓
- PR contributes tests ✓
- At least 1 F2P test ✓

**Result**: More instances from less-maintained repos → More poor-quality issues

#### Effort Required

| Aspect | Effort |
|--------|--------|
| **Human labeling** | **0 hours** (automated) ⭐ |
| **Data collection time** | **4-8 weeks** |
| **Infrastructure setup** | **40-60 hours** |
| **Compute cost** | **$500-1,000** (AWS/cloud) |
| **GitHub API rate limits** | Need authenticated requests |

#### Detailed Breakdown

**Week 1-2: Setup and Scraping**
- Clone/modify SWE-bench collection scripts (8 hours)
- Select 50-100 target repositories (4 hours)
- Scrape PRs via GitHub API (automated, but slow)
  - Rate limit: 5,000 requests/hour
  - ~50 repos × 2,000 PRs each = 100K PRs
  - Scraping time: ~20 hours of API calls

**Week 3-6: Execution-Based Validation (Stage III)**
- For each of 100K PRs:
  - Create Docker environment
  - Install dependencies
  - Run tests before/after
  - Record F2P/P2P
- **Bottleneck**: Test execution
  - ~5-10 minutes per PR
  - 100K PRs → 8,000-16,000 compute hours
  - Need parallel execution (10-50 machines)

**Parallelization Options**:
```
Single machine: 6 months ❌
10 machines: 20 days ✅
50 machines: 4 days ⭐
```

**Compute Resources**:
- AWS EC2: c5.2xlarge × 20 instances × 24 hours/day × 20 days
- Cost: ~$0.34/hour × 20 × 24 × 20 = ~$3,264

**Optimization**: Use spot instances
- Cost: ~$0.10/hour × 20 × 24 × 20 = ~$960

#### Advantages
✅ Automated collection (no manual labeling)
✅ Larger dataset (5,000-10,000 instances)
✅ More diverse repos
✅ Same F2P/P2P methodology
✅ Likely more poor-quality issues

#### Disadvantages
❌ Significant time investment (4-8 weeks)
❌ High compute cost ($500-1,000)
❌ Infrastructure complexity
❌ May introduce unstable/flaky tests

#### How to Implement

**Repository Selection Strategy**:
```python
# Target repos with lower maintenance quality
selection_criteria = {
    "downloads": (10_000, 100_000),  # Medium popularity
    "stars": (500, 5000),
    "contributors": (5, 50),
    "last_commit": "< 6 months",
    "test_coverage": "> 50%",  # Still need tests
}

# Expected repos (examples):
medium_repos = [
    "httpx", "pydantic", "fastapi", "typer",
    "click", "rich", "textual", "pytest-cov",
    # ... 50+ more
]
```

**Quality Distribution Hypothesis**:
```
Extended SWE-bench (5,000-10,000):
  - Good quality: ~20%
  - Mediocre quality: ~45%
  - Poor quality: ~35% ← MORE than Option 1
```

#### Cost-Benefit Analysis
- **Cost**: $500-1,000, 4-8 weeks, 60 hours setup
- **Benefit**: 2-4x more data, higher poor-quality ratio
- **Risk**: Medium (infrastructure, flaky tests)
- **Recommendation**: **If you have budget/time** ⭐⭐

---

### **Option 3: Actively Target Low-Quality Issues**

#### Description
Deliberately collect issues with poor descriptions by inverting quality filters.

#### Modified Pipeline

**Stage I: Anti-Quality Repository Selection**
```python
# Target repos with poor documentation
selection_criteria = {
    "README_length": "< 500 words",
    "CONTRIBUTING.md": "missing",
    "issue_template": "missing",
    "median_issue_length": "< 100 words",
}
```

**Stage II: Issue Quality Filtering**
```python
# SELECT FOR poor quality
quality_filters = {
    "issue_length": "< 150 words",
    "has_code_example": False,
    "has_reproduction_steps": False,
    "has_expected_behavior": False,
}
```

**Stage III**: Same (tests must work)

#### Effort Required

| Aspect | Effort |
|--------|--------|
| **Human labeling** | **40-80 hours** (quality verification) |
| **Data collection time** | **8-12 weeks** |
| **Infrastructure setup** | **80-100 hours** |
| **Compute cost** | **$1,000-2,000** |
| **Risk of unsolvable issues** | **HIGH** ⚠️ |

#### Detailed Breakdown

**Weeks 1-2: Target Identification**
- Analyze 1,000+ repos for poor documentation (20 hours)
- Build quality detection heuristics (20 hours)
- Manual verification of target repos (10 hours)

**Weeks 3-4: Issue Quality Classifier**
```python
# Build ML classifier or rule-based system
def is_poor_quality_issue(issue):
    score = 0
    if len(issue.body.split()) < 100: score += 2
    if "```" not in issue.body: score += 2  # No code
    if "reproduce" not in issue.body.lower(): score += 1
    if "expected" not in issue.body.lower(): score += 1
    return score >= 4

# Time: 30-40 hours to build + validate
```

**Weeks 5-10: Collection + Validation**
- Run SWE-bench pipeline on filtered issues
- High rejection rate (many issues unsolvable)
  - Normal rejection: 97.5%
  - With poor issues: 99%+ rejection
- Need to process 200K PRs to get 1,000 instances

**Weeks 11-12: Manual Quality Verification**
- Verify issues are actually poor quality (40 hours)
- Verify issues are still solvable (40 hours)

#### Major Risk: Unsolvable Issues

**Problem**: Poor issue descriptions might mean:
- Issue is genuinely unsolvable (missing context)
- Original contributor had domain knowledge not in description
- Issue requires visual information (screenshots)

**Mitigation**:
```python
# Keep Stage III validation
# Only accept if:
#   1. Poor quality issue
#   2. BUT still has 1+ F2P test
#   3. AND gold patch solves it
#
# This ensures solvability despite poor description
```

#### Advantages
✅ Maximum poor-quality issue concentration
✅ Perfect for testing enhancement effectiveness
✅ Novel dataset contribution

#### Disadvantages
❌ Extremely high effort (80-100 hours)
❌ Very high compute cost ($1,000-2,000)
❌ Risk of unsolvable issues
❌ May not reflect real-world distribution
❌ Questionable scientific validity

#### Quality Distribution (Target)
```
Actively-Poor Dataset (1,000-2,000):
  - Poor quality: ~70% ← VERY HIGH
  - Mediocre quality: ~25%
  - Good quality: ~5%
```

#### Cost-Benefit Analysis
- **Cost**: $1,000-2,000, 12 weeks, 100 hours
- **Benefit**: Ideal test for enhancement, but artificial
- **Risk**: High (unsolvable issues, validity concerns)
- **Recommendation**: **Only if Options 1 & 2 insufficient** ⭐

---

## Analysis Capabilities: Can We Analyze Like SWE-bench?

### Yes - All SWE-bench Metrics Work

**Core Metrics** (Automatic from pipeline):
```python
✅ RESOLVED rate
✅ Fail-to-Pass (F2P) success rate
✅ Pass-to-Pass (P2P) success rate
✅ Patch applicability rate
✅ Baseline vs Enhanced comparison
✅ Statistical significance tests (t-test, bootstrap)
```

**Your Existing Analysis Scripts**:
```bash
✅ scripts/reports/aggregate_swebench_results.py
✅ scripts/reports/compute_statistical_significance.py
✅ scripts/reports/per_repository_analysis.py
✅ scripts/reports/comprehensive_metrics.py
```

All work **unchanged** on new dataset.

---

### New Analyses Enabled by Mixed-Quality Dataset

#### 1. **Issue Quality Stratification**

Manual label 200-300 issues:
```python
# Quality labels: poor/mediocre/good
quality_labels = {
    "instance_id": "quality_level",
    "django__django-12345": "poor",
    "sympy__sympy-67890": "good",
    # ...
}
```

Stratified analysis:
```python
# Enhancement effectiveness by quality
poor_issues = dataset.filter(quality="poor")
good_issues = dataset.filter(quality="good")

print(f"Poor: {enhancement_helps(poor_issues)}")
print(f"Good: {enhancement_helps(good_issues)}")
```

**Expected Results**:
```
Issue Quality    Baseline    Enhanced    Delta    Interpretation
─────────────────────────────────────────────────────────────────
Poor (30%)       20%         35%        +15% ✅   Enhancement HELPS
Mediocre (40%)   45%         43%        -2%  ±   Slight hurt
Good (30%)       70%         50%        -20% ❌   Enhancement HURTS

Overall          45%         42%        -3%       Net negative
```

**Insight**: Enhancement helps poor issues but hurts good issues more.

#### 2. **Issue Feature Correlation**

Automatic feature extraction:
```python
issue_features = {
    "length_words": len(issue.split()),
    "has_code_example": "```" in issue,
    "has_reproduction": "reproduce" in issue.lower(),
    "has_expected_behavior": "expected" in issue.lower(),
    "has_error_traceback": "Traceback" in issue,
    "num_code_blocks": issue.count("```") // 2,
    "sentiment_score": analyze_sentiment(issue),
}
```

Correlation analysis:
```python
import pandas as pd
import seaborn as sns

df = pd.DataFrame({
    "instance_id": [...],
    "baseline_resolved": [...],
    "enhanced_resolved": [...],
    "enhancement_delta": [...],
    **issue_features
})

# Correlation heatmap
sns.heatmap(df.corr(), annot=True)

# Find which features predict enhancement success
regression = LinearRegression()
regression.fit(df[feature_cols], df["enhancement_delta"])
print(f"Top predictors: {regression.coef_.argsort()[-5:]}")
```

**Expected Insights**:
```
Feature                    Correlation with Enhancement Success
────────────────────────────────────────────────────────────────
length_words               -0.45 (shorter = more help)
has_code_example           -0.32 (no code = more help)
has_reproduction           -0.28 (no repro = more help)
num_code_blocks            -0.51 (fewer blocks = more help)

→ Enhancement helps when issue lacks structure/examples
```

#### 3. **Agent Comparison Across Quality Levels**

```python
results = {
    "Aider": {
        "poor": {"baseline": 18, "enhanced": 32, "delta": +14},
        "good": {"baseline": 72, "enhanced": 25, "delta": -47},
    },
    "SWE-agent": {
        "poor": {"baseline": 15, "enhanced": 20, "delta": +5},
        "good": {"baseline": 68, "enhanced": 60, "delta": -8},
    },
    "TRAE": {
        "poor": {"baseline": 16, "enhanced": 16, "delta": 0},
        "good": {"baseline": 70, "enhanced": 70, "delta": 0},
    },
}

# Insight: Aider hurts good issues most, helps poor issues most
# SWE-agent is more conservative
# TRAE is neutral (control)
```

#### 4. **Enhancement Type Effectiveness**

```python
# Categorize enhancement strategies
enhancement_types = {
    "Aider": "aggressive_rewrite",
    "SWE-agent": "moderate_augmentation",
    "TRAE": "noop",
    "Custom-1": "add_missing_context",
    "Custom-2": "fix_grammar_only",
}

# Measure which strategy works for which quality
strategy_effectiveness = pd.pivot_table(
    df,
    values="enhancement_delta",
    index="issue_quality",
    columns="enhancement_type",
)

print(strategy_effectiveness)
```

**Expected Results**:
```
                 aggressive  moderate  add_context  grammar_only  noop
issue_quality
poor                  +12%      +8%         +15%          +3%     0%
mediocre               -5%      -2%          +2%          +1%     0%
good                  -35%     -10%          -8%          -2%     0%
```

**Insight**: Different strategies work for different quality levels.

---

## Recommended Approach: Hybrid Strategy

### Phase 1: Quick Start (Option 1)
**Timeline**: Immediate
**Effort**: 20 hours (quality labeling of 250 samples)
**Cost**: $0

```bash
# Use full SWE-bench (2,294)
1. Download full dataset
2. Run experiments (reuse your pipeline)
3. Manually label 250 random samples for quality
4. Stratified analysis by quality
```

**Deliverable**: Paper with 2,294 instances + quality analysis

### Phase 2: Extended Dataset (Option 2) - Optional
**Timeline**: 3-4 months later
**Effort**: 60 hours + 4-8 weeks compute
**Cost**: $500-1,000

```bash
# If Phase 1 shows promising results
1. Extend to 50 more repos
2. Collect 5,000-10,000 instances
3. Larger-scale validation
```

**Deliverable**: Extended paper / follow-up publication

### Phase 3: Specialized Dataset (Option 3) - If Needed
**Timeline**: 6-12 months later
**Effort**: 100 hours + 12 weeks compute
**Cost**: $1,000-2,000

```bash
# Only if specific poor-quality issues needed
1. Target low-quality repos
2. Filter for poor descriptions
3. Specialized benchmark
```

**Deliverable**: Specialized benchmark for edge cases

---

## Scientific Validity Considerations

### Strengths of Mixed-Quality Dataset

✅ **Realistic**: Real-world has quality variation
✅ **Unbiased**: No cherry-picking for quality
✅ **Comprehensive**: Tests enhancement across spectrum
✅ **Actionable**: Shows when enhancement helps vs hurts

### Potential Concerns

⚠️ **Reviewer Question**: "Why not use Verified?"
**Answer**: Verified is biased toward good issues; we need quality variation to test enhancement effectiveness.

⚠️ **Reviewer Question**: "How do you ensure quality labels are reliable?"
**Answer**:
- Inter-annotator agreement (2-3 labelers per issue)
- Clear rubric (length, code examples, reproduction steps)
- Public release of quality labels for reproducibility

⚠️ **Reviewer Question**: "Is the dataset too hard/easy?"
**Answer**:
- Use same F2P/P2P metrics as SWE-bench
- Baseline solve rates show appropriate difficulty
- Stratified by quality to isolate enhancement effect

---

## Timeline and Resource Summary

### Option 1: Full SWE-bench (RECOMMENDED)

| Phase | Time | Effort | Cost |
|-------|------|--------|------|
| Download dataset | 1 day | 2 hours | $0 |
| Quality labeling (250 samples) | 1 week | 20 hours | $0 |
| Run experiments | 2-3 weeks | 0 hours | $0 |
| Analysis | 1 week | 40 hours | $0 |
| **TOTAL** | **5-6 weeks** | **62 hours** | **$0** |

### Option 2: Extended Dataset

| Phase | Time | Effort | Cost |
|-------|------|--------|------|
| Setup infrastructure | 1-2 weeks | 40 hours | $0 |
| Scrape PRs | 1 week | 4 hours | $0 |
| Stage III validation | 3-4 weeks | 0 hours | $500-1,000 |
| Quality labeling (500 samples) | 2 weeks | 40 hours | $0 |
| Analysis | 2 weeks | 60 hours | $0 |
| **TOTAL** | **9-11 weeks** | **144 hours** | **$500-1,000** |

### Option 3: Low-Quality Targeted

| Phase | Time | Effort | Cost |
|-------|------|--------|------|
| Target identification | 2 weeks | 40 hours | $0 |
| Quality classifier | 2 weeks | 40 hours | $0 |
| Stage III validation | 6-8 weeks | 0 hours | $1,000-2,000 |
| Manual verification | 2 weeks | 80 hours | $0 |
| Analysis | 2 weeks | 60 hours | $0 |
| **TOTAL** | **14-16 weeks** | **220 hours** | **$1,000-2,000** |

---

## Expected Publications

### With Option 1 Dataset
**Venue**: Top-tier SE/AI conference (ICSE, FSE, NeurIPS, ICLR)

**Contributions**:
1. First benchmark for issue enhancement agents
2. Analysis showing enhancement helps poor issues, hurts good issues
3. Guidelines for when to use enhancement
4. Open-source dataset with quality labels

**Title**: "When Does Issue Enhancement Help? A Large-Scale Study on Mixed-Quality GitHub Issues"

### With Option 2 Dataset
**Venue**: Same + journal extension

**Additional Contributions**:
1. Larger-scale validation (5K-10K instances)
2. Cross-repository generalization
3. More diverse issue types
4. Broader agent evaluation

**Title**: "SWE-bench-MQ: A Large-Scale Mixed-Quality Benchmark for Evaluating Issue Enhancement Agents"

---

## Conclusion

### Direct Answers to Your Questions

**Q1: Can we produce this dataset?**
**A**: ✅ YES - Multiple approaches with varying effort/cost.

**Q2: How hard and time-consuming?**
**A**:
- Option 1: 6 weeks, 62 hours, $0 ⭐ **RECOMMENDED**
- Option 2: 11 weeks, 144 hours, $500-1,000
- Option 3: 16 weeks, 220 hours, $1,000-2,000

**Q3: How much human labeling effort?**
**A**:
- Collection: 0 hours (fully automated like SWE-bench)
- Quality labeling: 20-80 hours (for analysis only)

**Q4: Can we analyze like SWE-bench?**
**A**: ✅ YES - All SWE-bench metrics work unchanged
- PLUS new analyses (quality stratification, feature correlation)

### Recommendation

**START WITH OPTION 1**:
1. Use full SWE-bench (2,294) immediately
2. Label 250 samples for quality (20 hours)
3. Run your experiments (existing pipeline)
4. Publish results

**Benefits**:
- Zero cost
- Immediate start
- Low risk
- Still publishable
- 10x more data than your current 101

**If successful, extend to Option 2 later.**

---

**End of Feasibility Analysis**
