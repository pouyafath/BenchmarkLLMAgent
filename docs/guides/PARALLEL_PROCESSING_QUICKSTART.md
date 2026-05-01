# Parallel Processing Quick Start Guide

**Phase 2.1: Ready to Use** ⚡

This guide shows how to use the new parallel harness evaluation scripts for **3x faster evaluation** (70-100 min → 25-35 min).

---

## TL;DR - Use This Now

```bash
cd /home/22pf2/BenchmarkLLMAgent

# Recommended: 3 workers (3x speedup, balanced)
./scripts/run_parallel_evaluation_x3.sh 10
```

**Estimated time**: 25-35 minutes for 10 issues

---

## Choose Your Speed Level

### Conservative: 2 Workers (2x speedup)
```bash
./scripts/run_parallel_evaluation_x2.sh 10
# Estimated time: 35-50 minutes
# Use when: System is under load, want safe parallelism
```

### Balanced: 3 Workers (3x speedup) ⭐ **RECOMMENDED**
```bash
./scripts/run_parallel_evaluation_x3.sh 10
# Estimated time: 25-35 minutes
# Use when: Most situations, good balance of speed/stability
```

### Aggressive: 4 Workers (3.5x speedup)
```bash
./scripts/run_parallel_evaluation_x4.sh 10
# Estimated time: 20-30 minutes
# Use when: System has plenty of resources, need max speed
```

---

## Verify Before Running

```bash
# 1. Check predictions file exists
ls -lah eval_results/swebench/iteration4_final_predictions/all_predictions.jsonl

# 2. Check Docker is working
docker ps

# 3. Check disk space
df -h | grep -E "Mounted|/$"
```

---

## Monitor Parallel Evaluation

In another terminal, watch progress:

```bash
# Watch main log
tail -f logs/harness_full_run.log

# Watch individual instances
ls -lah logs/run_evaluation/iteration_parallel_x3/enhanced_trae/

# Check system resources
top
# Or
watch -n 1 'ps aux | grep python.*swebench'
```

---

## Measure Speedup (Optional)

After evaluation completes, benchmark the actual improvement:

```bash
./scripts/benchmark_parallel_performance.sh
# Runs x1, x2, x3 sequentially and reports speedup
# Estimated time: 2 hours (multiple runs)
```

---

## Troubleshooting

### "ERROR: Predictions file not found"
```bash
# Generate predictions first
./bench_env/bin/python scripts/enhancers/run_solving_after_enhancement.py \
  --solver openhands \
  --baseline-mode \
  --max-issues 10 \
  --output-dir results/iteration4_final_10_issues
```

### "Docker: permission denied"
```bash
# Check Docker daemon
docker ps

# May need to add user to docker group
# (Check with your system admin first)
```

### "High CPU/memory usage"
```bash
# Use fewer workers
./scripts/run_parallel_evaluation_x2.sh 10  # Use 2 instead of 3

# Or monitor during run
top  # Press 'q' to exit
```

### "Evaluation hangs or times out"
```bash
# Check if instances are running
docker ps | grep sweb.eval

# Check logs for errors
tail -100 logs/harness_full_run.log | grep -i error

# May need to increase timeout or try with fewer workers
```

---

## Understanding the Output

### While Running
```
Running 10 instances...
Evaluation: 25%|████▌             | 2.5/10 [00:15<?, ?it/s, error=0, ✓=1, ✖=1]
```
- `✓=1`: 1 instance passing
- `✖=1`: 1 instance failing
- `error=0`: 0 unrecoverable errors

### After Completion
```
Results saved to:
  - Logs: logs/run_evaluation/iteration_parallel_x3/
  - Aggregate: eval_results/swebench/iteration_parallel_x3_aggregate_report.json
  - Metrics: eval_results/swebench/iteration_parallel_x3_fix_rate_metrics.json
```

---

## Key Files

| File | Purpose |
|------|---------|
| `scripts/run_parallel_evaluation_x2.sh` | 2-worker variant |
| `scripts/run_parallel_evaluation_x3.sh` | 3-worker variant ⭐ |
| `scripts/run_parallel_evaluation_x4.sh` | 4-worker variant |
| `scripts/benchmark_parallel_performance.sh` | Measure speedup |
| `docs/PHASE_2_PARALLEL_PROCESSING.md` | Detailed design |
| `docs/PHASE_2_1_IMPLEMENTATION_SUMMARY.md` | Implementation details |

---

## Expected Results

### Speed Improvement
- Sequential (1 worker): 70-100 minutes
- Parallel-x3 (3 workers): 25-35 minutes
- **Speedup: ~3x faster** ⚡

### No Quality Loss
- Metrics are identical (F2P, P2P, fix rate)
- Only speed improves, quality unchanged

### Safe for Production
- Docker handles isolation automatically
- Each instance runs independently
- Failures in one instance don't block others

---

## Next: Model Comparison (Phase 2.2)

Now that you have parallel infrastructure, compare models faster:

```bash
# Test claude-3-sonnet with 3x faster feedback
# Instructions coming in Phase 2.2 guide
```

---

## Questions?

See:
- `docs/PHASE_2_PARALLEL_PROCESSING.md` - Design details
- `docs/PHASE_2_1_IMPLEMENTATION_SUMMARY.md` - Implementation guide
- `docs/WORKFLOW_STATUS_2026-03-17.md` - Current status

---

**Ready to go faster?** 🚀

```bash
cd /home/22pf2/BenchmarkLLMAgent
./scripts/run_parallel_evaluation_x3.sh 10
```

Sit back and watch 10 instances evaluate in parallel!
