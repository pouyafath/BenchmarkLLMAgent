# Iteration 2 → Iteration 3: Improvement Plan

## Problem Summary

**Why only 15/66 evaluations completed (22.7%)?**

The solver generates patches **without context lines**. Unified diff requires context lines before and after each change so the patch tool knows WHERE to apply the patch and can verify it matches the actual file.

Example of problem:
```diff
@@ -1,14 +1,38 @@
         # This starts in the middle of a function!
         next_seq_len = (
-        return {...}  # No context before this
+        return {...}  # No context after this
```

Example of proper format:
```diff
@@ -1,14 +1,38 @@
 # These are context lines - they haven't changed
 def function_name():
     x = 1
-    return {...}  # deletion
+    return {...}  # addition
     y = 2  # context after
```

---

## What We Fixed in Iteration 2
✅ **Bare `@@` markers** — Fixed in `convert_to_predictions.py` by porting `_fix_hunk_headers()`
- Before: `@@` (bare)
- After: `@@ -1,14 +1,38 @@` (proper format)

## What's Still Broken
❌ **Missing context lines** — ~40 patches fail because no unchanged lines in hunks
❌ **File targeting errors** — ~6 patches fail because target file doesn't exist
❌ **Context mismatch** — ~5 patches fail because hunk context doesn't match file

---

## Fix Applied: Improved Solver Prompt (COMPLETED)

**File:** `scripts/enhancers/run_solving_after_enhancement.py`
**Change:** Updated `SYSTEM_PROMPT` and `TASK_TEMPLATE` to explicitly require context lines

### Before:
```
"Produce a unified diff patch. Output ONLY the patch."
```

### After:
```
"CRITICAL: The patch MUST be in proper unified diff format with CONTEXT LINES:
- Each hunk must include at least 3 lines of unchanged context BEFORE the changes
- Each hunk must include at least 3 lines of unchanged context AFTER the changes
- Context lines start with a single space

Example format:
@@ -10,10 +10,12 @@
 context line (unchanged)
 context line (unchanged)
 context line (unchanged)
-old code to remove
+new code to add
+additional new code
 context line (unchanged)
 context line (unchanged)
 context line (unchanged)"
```

**Expected Impact:** 20-40% improvement in patch apply rate (should reach 50%+ success)

---

## Next Steps (Iteration 3)

### 1. Re-run the Pipeline with Improved Prompts (HIGH PRIORITY)

Since we've already improved the solver prompt, the next run should generate better patches.

**Command to re-run everything:**
```bash
# Clear old results
rm -rf results/solving_after_enhancement results/solving_baseline
rm -rf logs/run_evaluation/iteration3_improved
rm -rf eval_results/swebench/iteration3_*
rm -rf eval_results/swebench/iteration3_predictions

# Re-run enhancement (uses same enhanced issues, but solver now has better prompt)
./scripts/run_enhancement_and_solving.sh

# Re-run SWE-bench harness
for pred in eval_results/swebench/iteration3_predictions/*/all_preds.jsonl; do
  agent=$(basename "$(dirname "$pred")")
  ./bench_env/bin/python -m swebench.harness.run_evaluation \
    --predictions_path "$pred" \
    --dataset_name data/samples/swe_bench_live_10_tasks_for_harness.json \
    --max_workers 2 --timeout 900 \
    --run_id iteration3_improved --cache_level env --namespace none \
    --report_dir "logs/run_evaluation/iteration3_improved/$agent"
done

# Regenerate all metrics
./bench_env/bin/python scripts/reports/generate_summary_reports.py \
  --iteration-name iteration3_improved --logs-dir logs/run_evaluation/iteration3_improved \
  --samples data/samples/swe_bench_live_10_samples.json

./bench_env/bin/python scripts/reports/aggregate_multi_agent_results.py \
  --iteration-name iteration3_improved --logs-dir logs/run_evaluation/iteration3_improved \
  --samples data/samples/swe_bench_live_10_samples.json \
  --output eval_results/swebench/iteration3_improved_aggregate_report.json

./bench_env/bin/python scripts/reports/comprehensive_metrics.py \
  --aggregate-report eval_results/swebench/iteration3_improved_aggregate_report.json \
  --ground-truth data/samples/swe_bench_live_10_samples.json \
  --logs-dir logs/run_evaluation/iteration3_improved \
  --output eval_results/swebench/iteration3_improved_comprehensive_metrics.json
```

### 2. Monitor Improvement Metrics

Compare iteration3 vs iteration2:

| Metric | Iter2 | Iter3 Target |
|--------|-------|-------------|
| Patches applied | 15/60 (25%) | **40+/60 (67%)** |
| Test completions | 15 | **40+** |
| Fix Rate | 0% | Still likely 0% but more data |
| F2P Progress | 0-50% | Same range but more instances |

### 3. If Still Insufficient (Fall Back Plan)

If improved prompts don't work well enough, implement **post-processing** to add context:

**File to create:** `scripts/swebench/add_context_to_patches.py`

```python
def add_context_to_patch(patch_str: str, repo_path: str) -> str:
    """
    Given a patch and a repository path, add missing context lines.

    1. Clone/checkout repo to a known state
    2. For each hunk with insufficient context:
       - Find the file mentioned in the patch
       - Locate the change in the file
       - Extract 3+ lines before and after
       - Rebuild the hunk
    3. Return fixed patch
    """
    # Parse patch hunks
    # For each hunk:
    #   - If < 3 context lines before change: fetch from file
    #   - If < 3 context lines after change: fetch from file
    #   - Rebuild hunk with context
    # Return reconstructed patch
```

**Usage in pipeline:**
```python
# In convert_to_predictions.py
from add_context_to_patches import add_context_to_patch

patch = normalize_patch(agent_patch)
patch = add_context_to_patch(patch, repo_checkout_path)  # ← NEW
```

---

## Success Criteria for Iteration 3

| Criterion | Target |
|-----------|--------|
| Patch apply rate (best agent) | 50%+ (was 40%) |
| Total completed evaluations | 40+ (was 15) |
| Instances with results | 8/10 (was 5) |
| F2P Progress improvements | Measurable on new completed instances |

---

## Files Modified This Session

| File | Change | Impact |
|------|--------|--------|
| `scripts/enhancers/run_solving_after_enhancement.py` | Enhanced solver prompt with context line instructions | Should improve patch generation quality |
| `scripts/swebench/convert_to_predictions.py` | Added `_fix_hunk_headers()` function | Fixed bare `@@` markers (iteration 2) |
| `eval_results/swebench/ITERATION2_FINAL_ANALYSIS.md` | New analysis document | Documents iteration 2 results |
| `docs/ERROR_ANALYSIS_ITERATION2.md` | New error analysis | Explains why 51 evaluations failed |

---

## Key Learnings for Future Work

1. **Unified diff is precise:** Patches MUST have context lines. There's no way around this - the patch tool needs them to work correctly.

2. **LLMs struggle with exact formats:** Even well-prompting sometimes doesn't guarantee the format. We may need post-processing fallback.

3. **Enhancement matters:** 0% baseline → 20-40% enhanced shows enhancement provides crucial code context.

4. **Some instances are easier:** koxudaxi proves the pipeline CAN work end-to-end when patches are valid.

5. **Regression is the ultimate blocker:** Even when patches apply perfectly, 99%+ test regressions prevent any "resolved" issues.

---

## Questions for the User

Before re-running iteration 3, consider:

1. **Should we prioritize regression fixes next?** Even with 100% patch apply rate, we still get 0% Fix Rate due to regressions.

2. **Should we test the improved prompt on a smaller sample first?** Maybe run on 1-2 issues to validate before full pipeline.

3. **Do you want to experiment with different solvers?** Some models might be naturally better at patch generation.

4. **Should we extend to full SWE-bench-Live?** Currently using only 10 issues. More data would validate improvements.
