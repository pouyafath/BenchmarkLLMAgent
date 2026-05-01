# Quick Start Guide - Re-run Full Pipeline with All Metrics

**Read the full handoff**: [`COMPREHENSIVE_METRICS_HANDOFF.md`](COMPREHENSIVE_METRICS_HANDOFF.md)

---

## 🎯 Goal
Re-run all 10 SWE-bench-Live issues with 5 enhancers + 1 solver + baseline, then analyze with all 9 metrics.

**Total evaluations**: 60 (6 agents × 10 issues)

---

## ⚡ Fast Track (3 Commands)

If scripts are ready and environment configured:

```bash
cd /home/22pf2/BenchmarkLLMAgent

# 1. Run enhancements (1-2 hours)
./bench_env/bin/python scripts/enhancers/run_enhancement_benchmark.py \
  --samples data/samples/swe_bench_live_10_samples.json \
  --max-issues 10 --agents all --parallel 4

# 2. Run solver (2-4 hours)
./bench_env/bin/python scripts/enhancers/run_solving_after_enhancement.py \
  --max-issues 10 --solver openai_agents_sdk

# 3. Run full evaluation pipeline (create master script or run steps 4-10 from handoff)
```

**Then**: Run metrics analysis (steps 6-10 in handoff document)

---

## 📊 What Metrics Will Be Computed

### ✅ Ready (7/9 metrics with real data):
1. **Fix Rate** - Partial progress with regression penalty
2. **F2P Progress** - Shows 25-50% improvement for enhanced agents
3. **Regression Rate** - Currently 99.7%, aim to reduce
4. **Patch Apply Rate** - 50-100% success
5. **File Overlap** - 87.5-100% accuracy
6. **Content Similarity** - **44.9% vs 14.3% (+214% improvement)** ⭐
7. **Resolution Rate** - Standard SWE-bench metric

### ⚠️ Framework ready (2/9 metrics, need solver logs):
8. **Efficiency** - Tokens, cost, time
9. **Trajectory** - Turns, tool calls

---

## 🎓 Key Results from Previous Run (iteration1_v3)

- **Content Similarity**: Enhanced agents **3.1× better** than baseline (44.9% vs 14.3%)
- **F2P Progress**: Enhanced shows **25-50%** progress vs baseline **0%**
- **Best Agents**: mini_swe_agent & openhands (both 44.9% content sim)

---

## 📂 Key Files

**Input**:
- `data/samples/swe_bench_live_10_samples.json` - 10 issues to evaluate

**Scripts**:
- `scripts/enhancers/run_enhancement_benchmark.py` - Run enhancers
- `scripts/enhancers/run_solving_after_enhancement.py` - Run solver
- `scripts/reports/comprehensive_metrics.py` - Compute all metrics

**Previous Results** (for reference):
- `eval_results/swebench/ALL_METRICS_ITERATION1_V3_SUMMARY.md`
- `eval_results/swebench/iteration1_v3_comprehensive_metrics.json`

---

## ⚠️ Before Starting

1. ✅ Check Ollama/vLLM is running: `curl http://localhost:11434/api/tags`
2. ✅ Check Docker is running: `docker ps`
3. ✅ Check disk space: `df -h` (need ~50GB free)
4. ✅ Set environment variables for solver model

---

## 🔍 Monitor Progress

```bash
# Check enhancement progress
watch -n 30 'ls results/enhancement_benchmark/ | wc -l'
# Target: 50 files

# Check solving progress
watch -n 30 'ls results/solving_after_enhancement/ | wc -l'
# Target: 50 files

# Check evaluation progress
watch -n 60 'find logs/run_evaluation/iteration2_full -name "report.json" | wc -l'
# Target: 60 files
```

---

## 📈 Final Analysis

After completing all steps:

```bash
# Generate comprehensive metrics
./bench_env/bin/python scripts/reports/comprehensive_metrics.py

# Output files:
# - eval_results/swebench/iteration2_full_comprehensive_metrics.json
# - Console tables with all metrics
```

**Look for**:
- Content Similarity: Enhanced > 40% (baseline ~14%)
- F2P Progress: Enhanced > 25%
- Regression Rate: Hopefully < 100%

---

## ❓ Problems?

See **Section 9: Troubleshooting** in the full handoff document.

Quick fixes:
- **Agent fails**: Reduce `--parallel 2`
- **Docker fails**: `docker system prune -a`
- **Timeouts**: Use faster model or increase timeout

---

**Estimated Total Time**: 6-12 hours for complete pipeline

**Questions?** Read: `docs/COMPREHENSIVE_METRICS_HANDOFF.md`
