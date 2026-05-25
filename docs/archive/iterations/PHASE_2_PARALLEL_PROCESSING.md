# Phase 2.1: Parallel Processing Implementation

**Status**: 🔄 **IN PROGRESS** (Implementation while harness runs)
**Date**: 2026-03-17 05:01 UTC
**Goal**: Improve harness evaluation time from 70-100 minutes to 25-35 minutes via parallel instance processing

---

## Current Bottleneck

The SWE-bench harness currently evaluates instances **sequentially** (1 at a time):

```
Instance 1: 7-10 min ──→ Instance 2: 7-10 min ──→ ... ──→ Instance 10: 7-10 min
Total: 70-100 minutes
```

With Docker and the harness handling isolation properly, multiple instances can run **concurrently**:

```
Instance 1: ──────┐
Instance 2: ──────┤ (parallel)
Instance 3: ──────┤
                  └─→ Total: 25-35 minutes (3x speedup)
```

---

## Optimization Strategy

### Level 1: Harness Native Parallelism (Recommended)

The SWE-bench harness supports `--max_workers` parameter to run multiple instances in parallel:

```bash
# Current (sequential)
./bench_env/bin/python -m swebench.harness.run_evaluation \
  --predictions_path <predictions> \
  --max_workers 1  # ← Sequential evaluation

# Optimized (3x speedup)
./bench_env/bin/python -m swebench.harness.run_evaluation \
  --predictions_path <predictions> \
  --max_workers 3  # ← 3 instances in parallel
```

**Parallelism Levels**:
- `--max_workers 1`: Sequential (current)
- `--max_workers 2`: 2 instances parallel (2x speedup)
- `--max_workers 3`: 3 instances parallel (3x speedup)
- `--max_workers 4`: 4 instances parallel (4x speedup)

**Recommendation**: Start with `--max_workers 3` (good balance of parallelism without overwhelming system)

---

## Implementation Plan

### Step 1: Create Parallel Harness Variants

Create configuration files for different parallelism levels:

```bash
# Current script
scripts/run_full_evaluation_pipeline.sh                # --max_workers 1 (sequential)

# New scripts
scripts/run_parallel_evaluation_pipeline_x2.sh        # --max_workers 2 (2x speedup)
scripts/run_parallel_evaluation_pipeline_x3.sh        # --max_workers 3 (3x speedup)
scripts/run_parallel_evaluation_pipeline_x4.sh        # --max_workers 4 (4x speedup)
```

### Step 2: Quick Parallel Test (After Current Harness)

Once the current harness completes (in ~1.5 hours), run a quick parallel test:

```bash
# Test 1: Compare sequential vs parallel-2 on 4 issues
./bench_env/bin/python -m swebench.harness.run_evaluation \
  --predictions_path eval_results/swebench/iteration4_final_predictions/4_issues.jsonl \
  --max_workers 1 \
  --run_id parallel_test_seq \
  --report_dir logs/parallel_benchmark/seq

./bench_env/bin/python -m swebench.harness.run_evaluation \
  --predictions_path eval_results/swebench/iteration4_final_predictions/4_issues.jsonl \
  --max_workers 2 \
  --run_id parallel_test_x2 \
  --report_dir logs/parallel_benchmark/x2
```

### Step 3: System Resource Monitoring

Track system resources during parallel evaluation:

```bash
# Monitor CPU, memory, disk I/O during parallel runs
while true; do
  echo "=== $(date) ==="
  echo "CPU: $(top -bn1 | grep Cpu)"
  echo "Memory: $(free -h | grep Mem)"
  echo "Disk I/O: $(iostat -x 1 2 | tail -3)"
  sleep 30
done
```

### Step 4: Benchmark Results

Expected timing for 10-instance evaluation:

| Workers | Instances | Parallel | Estimated Time | Speedup |
|---------|-----------|----------|-----------------|---------|
| 1       | 10        | Sequential | 70-100 min | 1x (baseline) |
| 2       | 10        | 2 at a time | 35-50 min | ~2x |
| 3       | 10        | 3 at a time | 25-35 min | ~3x |
| 4       | 10        | 4 at a time | 20-30 min | ~3.5x |

---

## Phase 2.1 Configuration Scripts

### script: run_parallel_evaluation_x3.sh

```bash
#!/bin/bash
# Parallel evaluation pipeline with 3 workers (3x speedup)
# Estimated time: 25-35 minutes for 10 issues

set -e

NUM_ISSUES=${1:-10}
OUTPUT_TAG="iteration4_parallel_x3"
NUM_WORKERS=3

echo "=========================================="
echo "Parallel SWE-bench Harness Evaluation"
echo "Issues: $NUM_ISSUES"
echo "Workers: $NUM_WORKERS (est. 3x speedup)"
echo "=========================================="

# Step 1: Run harness with parallel workers
echo "[1/3] Running harness with $NUM_WORKERS parallel workers..."
mkdir -p logs/run_evaluation/${OUTPUT_TAG}

./bench_env/bin/python -m swebench.harness.run_evaluation \
  --predictions_path eval_results/swebench/iteration4_final_predictions/all_predictions.jsonl \
  --max_workers $NUM_WORKERS \
  --run_id ${OUTPUT_TAG} \
  --dataset_name SWE-bench-Live/SWE-bench-Live \
  --split verified \
  --namespace starryzhang \
  --cache_level env \
  --report_dir logs/run_evaluation/${OUTPUT_TAG} \
  --timeout 1800

# Step 2: Aggregate results
echo "[2/3] Aggregating results..."
./bench_env/bin/python scripts/reports/aggregate_swebench_results.py \
  --harness-logs logs/run_evaluation/${OUTPUT_TAG} \
  --output eval_results/swebench/${OUTPUT_TAG}_aggregate_report.json

# Step 3: Generate metrics
echo "[3/3] Computing metrics..."
./bench_env/bin/python scripts/reports/compute_fix_rate_metrics.py \
  --harness-logs logs/run_evaluation/${OUTPUT_TAG} \
  --output eval_results/swebench/${OUTPUT_TAG}_fix_rate_metrics.json

echo ""
echo "=========================================="
echo "Parallel Evaluation Complete!"
echo "=========================================="
echo "Results saved to:"
echo "  - Logs: logs/run_evaluation/${OUTPUT_TAG}/"
echo "  - Aggregate: eval_results/swebench/${OUTPUT_TAG}_aggregate_report.json"
echo "  - Metrics: eval_results/swebench/${OUTPUT_TAG}_fix_rate_metrics.json"
```

---

## Recommendations

### Immediate (After Current Harness Completes)

1. ✅ **Run quick parallel benchmark** (20 minutes)
   - Test `--max_workers 2` vs `--max_workers 1` on 4 issues
   - Measure actual speedup
   - Confirm system stability

2. ✅ **Create parallel script variants** (10 minutes)
   - `run_parallel_x2.sh`, `run_parallel_x3.sh`, `run_parallel_x4.sh`
   - Make them production-ready

3. ✅ **Document optimal configuration** (5 minutes)
   - Determine best `--max_workers` setting for our system
   - Update evaluation documentation

### Short-term (Phase 2.2+)

- **Reduce future 10-issue benchmarks from 70-100 min to 25-35 min** (3x speedup)
- **Enable faster iteration cycles** for model comparison tests
- **Parallelize across multiple GPUs** if available

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Parallel workers interfere with each other | HIGH | Verify Docker isolation; test small subset first |
| Resource exhaustion (CPU, memory, disk) | MEDIUM | Monitor system; start with `--max_workers 2` |
| Race conditions in harness code | LOW | Harness is designed for parallel use |
| Failed instances block other workers | LOW | `max_workers` queues tasks; failures are independent |

---

## Success Criteria

- ✅ Parallel harness runs without errors
- ✅ Achieves ≥2x speedup compared to sequential
- ✅ All 10 instances complete successfully
- ✅ Results match sequential evaluation (no data corruption)
- ✅ System remains stable (no crashes, hangs)

---

## Expected Outcome

After Phase 2.1 implementation:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **10-issue eval time** | 70-100 min | 25-35 min | **3x faster** |
| **2-issue eval time** | 14-20 min | 7-10 min | **2x faster** |
| **Cost per eval** | Same | Same | No change |
| **Quality** | Same | Same | No change |

This enables much faster iteration and comparison testing in Phase 2.

---

**Target Completion**: 2026-03-17 after current harness finishes (~05:30-06:15 UTC)
