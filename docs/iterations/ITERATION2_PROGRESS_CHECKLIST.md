# Iteration2 Full Pipeline - Progress Checklist

**Start Date**: _________
**Completion Target**: All 10 issues × 6 agents = 60 evaluations
**Current Iteration Name**: `iteration2_full`

---

## 📋 Pre-Flight Checklist

- [ ] Read `COMPREHENSIVE_METRICS_HANDOFF.md`
- [ ] Read `QUICK_START_GUIDE.md`
- [ ] Verified Ollama/vLLM running: `curl http://localhost:11434/api/tags`
- [ ] Verified Docker running: `docker ps`
- [ ] Checked disk space: `df -h` (need >50GB free)
- [ ] Environment variables set (model, API endpoint)
- [ ] Activated virtual environment: `source bench_env/bin/activate`

---

## 🔄 Pipeline Execution

### STEP 1: Enhancement (Target: 50 files)

**Command**:
```bash
./bench_env/bin/python scripts/enhancers/run_enhancement_benchmark.py \
  --samples data/samples/swe_bench_live_10_samples.json \
  --max-issues 10 --agents all --parallel 4
```

**Progress**:
- [ ] Started: _____ (time)
- [ ] Completed: _____ (time)
- [ ] Files created: _____ / 50
- [ ] Location verified: `results/enhancement_benchmark/`
- [ ] Sample file checked: Opens correctly and has expected structure

**Issues encountered**:
```
(Note any errors or timeouts here)

```

---

### STEP 2: Solving Enhanced Issues (Target: 50 files)

**Command**:
```bash
./bench_env/bin/python scripts/enhancers/run_solving_after_enhancement.py \
  --max-issues 10 --solver openai_agents_sdk
```

**Progress**:
- [ ] Started: _____ (time)
- [ ] Completed: _____ (time)
- [ ] Files created: _____ / 50
- [ ] Location verified: `results/solving_after_enhancement/`
- [ ] Sample patch checked: Contains valid diff

**Issues encountered**:
```
(Note any errors or timeouts here)

```

---

### STEP 3: Baseline Solving (Target: 10 files)

**Command**:
```bash
./bench_env/bin/python scripts/enhancers/run_solving_after_enhancement.py \
  --max-issues 10 --solver openai_agents_sdk --baseline-mode
```
*(or equivalent baseline script)*

**Progress**:
- [ ] Started: _____ (time)
- [ ] Completed: _____ (time)
- [ ] Files created: _____ / 10
- [ ] Location verified: `results/solving_baseline/`

**Issues encountered**:
```
(Note any errors or timeouts here)

```

---

### STEP 4: Convert to SWE-bench Predictions (Target: 6 JSONL files)

**Command**:
```bash
./bench_env/bin/python scripts/swebench/convert_to_predictions.py \
  --solving-dir results/solving_after_enhancement/ \
  --baseline-dir results/solving_baseline/ \
  --output-dir eval_results/swebench/iteration2_predictions/
```
*(or manual conversion)*

**Progress**:
- [ ] Conversion completed
- [ ] 6 agent directories created in `iteration2_predictions/`
- [ ] Each `all_preds.jsonl` has 10 lines
- [ ] JSONL format validated (valid JSON per line)

**Agent Files**:
- [ ] `baseline_no_enhancement/all_preds.jsonl` (10 lines)
- [ ] `enhanced_live_swe_agent/all_preds.jsonl` (10 lines)
- [ ] `enhanced_mini_swe_agent/all_preds.jsonl` (10 lines)
- [ ] `enhanced_openhands/all_preds.jsonl` (10 lines)
- [ ] `enhanced_simple_enhancer/all_preds.jsonl` (10 lines)
- [ ] `enhanced_trae/all_preds.jsonl` (10 lines)

---

### STEP 5: SWE-bench Harness Evaluation (Target: 60 report.json)

**Command** (run for each agent):
```bash
for agent_dir in eval_results/swebench/iteration2_predictions/*/; do
  agent_name=$(basename $agent_dir)
  ./bench_env/bin/python -m swebench.harness.run_evaluation \
    --predictions_path ${agent_dir}/all_preds.jsonl \
    --swe_bench_tasks data/samples/swe_bench_live_10_samples.json \
    --log_dir logs/run_evaluation/iteration2_full/${agent_name} \
    --testbed testbed --skip_existing False --timeout 900 --num_workers 4
done
```

**Progress by Agent**:

| Agent | Started | Completed | Reports | Patches | Issues |
|-------|---------|-----------|---------|---------|--------|
| baseline_no_enhancement | _____ | _____ | __/10 | __/10 | _____ |
| enhanced_live_swe_agent | _____ | _____ | __/10 | __/10 | _____ |
| enhanced_mini_swe_agent | _____ | _____ | __/10 | __/10 | _____ |
| enhanced_openhands | _____ | _____ | __/10 | __/10 | _____ |
| enhanced_simple_enhancer | _____ | _____ | __/10 | __/10 | _____ |
| enhanced_trae | _____ | _____ | __/10 | __/10 | _____ |

**Overall**:
- [ ] All 60 evaluations completed
- [ ] All `report.json` files exist
- [ ] Most `patch.diff` files exist (document missing ones)

**Issues encountered**:
```
(Docker errors, timeouts, etc.)

```

---

### STEP 6: Generate Summary Reports

**Command**:
```bash
./bench_env/bin/python scripts/reports/generate_summary_reports.py \
  --iteration-name iteration2_full
```

**Progress**:
- [ ] Script executed successfully
- [ ] 6 summary JSON files created in project root
- [ ] Files contain expected fields (submitted, completed, resolved, etc.)

**Files**:
- [ ] `baseline_no_enhancement.iteration2_full.json`
- [ ] `enhanced_live_swe_agent.iteration2_full.json`
- [ ] `enhanced_mini_swe_agent.iteration2_full.json`
- [ ] `enhanced_openhands.iteration2_full.json`
- [ ] `enhanced_simple_enhancer.iteration2_full.json`
- [ ] `enhanced_trae.iteration2_full.json`

---

### STEP 7: Generate Aggregate Report

**Command**:
```bash
./bench_env/bin/python scripts/reports/aggregate_multi_agent_results.py \
  --iteration-name iteration2_full
```

**Progress**:
- [ ] Script executed successfully
- [ ] File created: `eval_results/swebench/iteration2_full_aggregate_report.json`
- [ ] Contains `summary`, `patch_apply_matrix`, `test_metrics` sections
- [ ] All 60 agent-instance pairs present in `test_metrics`

**Quick Stats from Aggregate**:
- Total Submissions: _____
- Total Completed: _____
- Total Resolved: _____
- Overall Patch Apply Rate: _____%

---

### STEP 8: Comprehensive Metrics

**Command**:
```bash
./bench_env/bin/python scripts/reports/comprehensive_metrics.py
```

**Progress**:
- [ ] Script executed successfully
- [ ] File created: `eval_results/swebench/iteration2_full_comprehensive_metrics.json`
- [ ] Console tables displayed all 9 metrics
- [ ] All agents have non-zero data (not all 0.000)

**Key Metrics Snapshot**:

| Metric | Baseline | Best Enhanced | Delta |
|--------|----------|---------------|-------|
| Content Similarity | _____ | _____ | _____ |
| F2P Progress | _____ | _____ | _____ |
| File Overlap | _____ | _____ | _____ |
| Fix Rate | _____ | _____ | _____ |
| Regression Rate | _____ | _____ | _____ |
| Resolution Rate | _____ | _____ | _____ |

---

### STEP 9: Fix Rate Metrics

**Command**:
```bash
./bench_env/bin/python scripts/reports/compute_fix_rate_metrics.py
```

**Progress**:
- [ ] Script executed successfully
- [ ] File created: `eval_results/swebench/iteration2_full_fix_rate_metrics.json`
- [ ] Report showed delta metrics (enhanced - baseline)
- [ ] Statistical analysis section populated

---

### STEP 10: Final Analysis & Visualization

**Tasks**:
- [ ] Created analysis markdown document
- [ ] Generated visualization plots (bar charts, comparison graphs)
- [ ] Computed statistical significance tests
- [ ] Calculated effect sizes (Cohen's d)
- [ ] Identified best performing agents
- [ ] Documented key insights for paper

**Analysis Files Created**:
- [ ] `eval_results/swebench/ITERATION2_FULL_ANALYSIS.md`
- [ ] `eval_results/swebench/metrics_comparison.png`
- [ ] `eval_results/swebench/agent_rankings.csv`
- [ ] (Add others as created)

---

## 📊 Quality Checks

### Data Completeness
- [ ] All 50 enhancement files exist
- [ ] All 50 solving files exist
- [ ] All 10 baseline solving files exist
- [ ] All 60 report.json files exist
- [ ] At least 50 patch.diff files exist (document missing)

### Metrics Quality
- [ ] Content Similarity: Enhanced > Baseline by >10%
- [ ] F2P Progress: Enhanced > 0%
- [ ] File Overlap: Mean > 80%
- [ ] Patch Apply Rate: >70% for most agents
- [ ] Regression Rate: <100% (preferably <50%)
- [ ] At least 1 instance fully resolved

### Statistical Rigor
- [ ] Paired t-test computed (p-value: _____)
- [ ] Wilcoxon test computed (p-value: _____)
- [ ] Effect size computed (Cohen's d: _____)
- [ ] All p-values documented
- [ ] Confidence intervals calculated

---

## 🏆 Final Results Summary

**Best Agent Overall**: _____________________

**Top 3 by Content Similarity**:
1. _____________________ (____%)
2. _____________________ (____%)
3. _____________________ (____%)

**Top 3 by F2P Progress**:
1. _____________________ (____%)
2. _____________________ (____%)
3. _____________________ (____%)

**Issues Fully Resolved**: _____ / 10
- List: _____________________

**Key Finding for Paper**:
```
(1-2 sentence summary of most important result)

```

---

## 📝 Issues & Notes

### Blockers Encountered
```
(Major issues that stopped progress)

```

### Workarounds Applied
```
(Solutions to problems encountered)

```

### Improvements for Next Iteration
```
(Ideas for iteration3 or paper revision)

```

---

## ✅ Sign-Off

**Pipeline Status**: [ ] Complete / [ ] Partial / [ ] Failed

**Completion Date**: _____

**Total Time**: _____ hours

**Data Quality**: [ ] Excellent / [ ] Good / [ ] Needs Review

**Ready for Paper**: [ ] Yes / [ ] Needs More Work

**Handoff to Next Agent**: [ ] Not needed / [ ] See notes below

**Additional Notes**:
```
(Any important context for next steps)

```

---

**Next Steps**:
1. [ ] Draft paper section 5 (Results)
2. [ ] Create all figures and tables
3. [ ] Run statistical tests
4. [ ] Scale to 100+ issues (optional)
5. [ ] Compare with SWE-bench-Live leaderboard

---

**Checklist Version**: 1.0
**Last Updated**: 2026-03-10
