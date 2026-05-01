# Error Analysis: Why Only 15/66 Evaluations Completed

## Summary
- **Total evaluations:** 66
- **Completed with test results:** 15 (22.7%)
- **Failed to apply patches:** 51 (77.3%)

---

## Root Cause: Missing Context Lines in Patches

The primary issue is **not** the bare `@@` markers (which we fixed), but rather that **LLM-generated patches are missing context lines**.

### What Unified Diff Context Lines Are

A proper unified diff hunk has this structure:
```diff
@@ -5,7 +5,8 @@
 line 4 (context - unchanged)
 line 5 (context - unchanged)
 line 6 (context - unchanged)
-line 7 (deletion)
+line 7 replacement (addition)
 line 8 (context - unchanged)
 line 9 (context - unchanged)
```

**Each change must have context lines before and after** to:
1. Help the patch tool find WHERE to apply the patch
2. Verify the patch matches the actual file at that location
3. Handle line number variations with `-p` flags

### Example: pytorch__torchtune-1697 (FAILED)

The generated patch:
```diff
@@ -1,14 +1,38 @@
         # Return the length of the first sample...
```

**Problem:** After the `@@` header, the patch should show lines 1-14 of the original file with context, then show changes. Instead, it jumps directly to middle-of-hunk content without any leading context.

**Correct format would be:**
```diff
@@ -1,14 +1,38 @@
 import torch  # ← context line before changes

 def some_function():
     x = 1  # ← more context
     # Return the length of the first sample...
         next_seq_len = (
             len(current_pack["tokens"][boundary:])
             ...
-        return {...}  # ← deletion
+        # NOTE: explanation...
+        next_seq_lens = [...]  # ← additions
+        return {...}  # ← replacement
```

---

## Error Breakdown by Type

### 1. Missing Context Lines (40 instances)
- **Count:** ~40 failures
- **Symptoms:**
  - "patch unexpectedly ends in middle of line"
  - "malformed patch at line X"
  - `git apply`, `patch --fuzz=5`, and `patch --batch` all fail
- **Why:** The solver generates diffs without the context lines needed for line matching
- **Agents affected:** All (5 enhanced agents)
- **Example instances:** pytorch__torchtune-1697, reflex-dev/reflex-3842, reflex-dev/reflex-4129

### 2. File Not Found (6 instances)
- **Count:** ~6 failures
- **Symptoms:**
  - "No file to patch. Skipping patch."
  - Patch targets file that doesn't exist in repo
- **Why:** Solver may generate patches targeting wrong file paths or deleted files
- **Agents affected:** baseline agents (cannot generate valid patches)
- **Example instances:** aws-cloudformation/cfn-lint-3764 (all agents fail)

### 3. Hunk Context Mismatch (5 instances)
- **Count:** ~5 failures
- **Symptoms:**
  - "Hunk #1 FAILED at line Y"
  - "Hunk #2 FAILED at line Z"
- **Why:** The hunk's context lines don't match the actual file due to:
  - Incorrect line numbers in the `@@ header
  - File has changed since patch was generated
  - Previous hunk application shifted line numbers
- **Agents affected:** Enhanced agents with harder instances
- **Example instances:** reflex-dev instances, some torch instances

---

## Why Only Enhanced Agents Got Results (15/15 from enhanced, 0/16 from baselines)

**Enhanced agents:** 20-40% patch apply rate
**Baseline agents:** 0% patch apply rate

Enhanced agents have an advantage:
- **Issue enhancement context:** Better prompt structure helps solver understand the code better
- **File hints in enhancement:** Enhanced agents include relevant file listings in the prompt
- **Better patch generation:** Solvers with context generate more complete diffs

But even enhanced agents fail 60-80% of the time due to context line issues.

---

## The Real Problem: Not Patch Headers, But Missing Context

Our earlier fix added proper `@@ -start,count +start,count @@` headers to bare `@@` markers. That fixed one class of errors, but the fundamental issue remains:

**The solver's diffs are generated without proper context lines.**

---

## Why This Happens

The solver is asked to generate a patch. It does so by:
1. Identifying what code needs to change
2. Writing the changed lines (with + and -)
3. NOT including the unchanged context lines

This might be because:
- The solver was trained on partial diff formats
- The prompt doesn't explicitly ask for context lines
- The solver doesn't have access to the actual file to get context

---

## Potential Fixes (in priority order)

### Option 1: Improve Solver Prompt (Best)
**Effort:** Medium | **Impact:** High

Explicitly instruct the solver:
```
When generating the patch:
- Include 3+ lines of unchanged context BEFORE each change
- Include 3+ lines of unchanged context AFTER each change
- Start the hunk from the beginning of the function/class where changes occur
- End the hunk after all related changes

Example of correct format:
@@ -120,10 +120,12 @@
     existing_line_1
     existing_line_2
     existing_line_3
-    old_code
+    new_code
+    additional_line
     existing_line_4
     existing_line_5
```

### Option 2: Post-Process Patches (Medium)
**Effort:** Medium | **Impact:** Medium-High

After the solver generates a patch:
1. Clone the target repo to a known state
2. For each hunk with missing context:
   - Look up the actual file in the repo
   - Extract context lines around the changes
   - Rebuild the hunk with proper context

```python
def add_context_to_patch(patch_str, repo_path):
    """Add missing context lines to a patch."""
    # Parse patch
    # For each hunk:
    #   - Find actual file in repo
    #   - Extract lines around change
    #   - Rebuild hunk with context
    # Return fixed patch
```

### Option 3: Use Different Diff Tool (Medium)
**Effort:** Low | **Impact:** Low-Medium

Some LLMs generate `unified diff` correctly but others don't. Try:
- Use more explicit prompt: "Generate a unified diff with `diff -u` format"
- Request patch in specific format with examples
- Post-process with `git diff` if we have the original and modified files

### Option 4: Enforce Git Diff Format (Medium)
**Effort:** Medium | **Impact:** Medium

If we have both original and modified code:
1. Write both versions to temp files
2. Run `git diff original modified > patch.diff`
3. Use the official git-generated patch

---

## What We Know Works (from 15 successful cases)

These instances succeeded, which tells us **what the solver CAN do**:

1. **koxudaxi/datamodel-code-generator-2334** (5/5 agents succeeded)
   - Multi-hunk patch with proper context
   - 75.4% content similarity with ground truth
   - Patch format: Clean `@@ -line,count +line,count @@` with full context

2. **keras-team/keras-20125** (5/5 agents succeeded)
   - Simple single-file change
   - Proper context lines present

3. **instructlab/instructlab-3135** (1/5 agents succeeded)
   - lived_swe_agent generated valid patch
   - Other agents failed (maybe due to different prompt handling)

4. **matplotlib/matplotlib-28734** (2/5 agents succeeded)
   - simple_enhancer and trae succeeded
   - Other agents likely had context issues

This proves **the solver CAN generate valid patches**, but it's inconsistent.

---

## Next Steps Recommendation

1. **Immediate (High Priority):**
   - Add explicit context line requirement to solver prompt
   - Example: Include the exact prompt you're sending to the solver, then modify it to say:
     ```
     "Generate a unified diff patch. Each hunk MUST include at least 3 lines
      of unchanged context before and after the changes. Use this format:
      @@ -start,count +start,count @@
      [3+ context lines before changes]
      -[deleted lines]
      +[added lines]
      [3+ context lines after changes]"
     ```

2. **Short Term:**
   - Implement Option 2 (post-processing with context addition)
   - This would turn the 40+ context-missing failures into successes

3. **Medium Term:**
   - Review why baseline agents generate invalid patches (maybe different solver settings?)
   - Baseline should still generate SOME valid patches even without enhancement

4. **Long Term:**
   - Evaluate different solvers/models (some may be better at patch generation)
   - Consider using ground truth files to auto-generate proper diffs from agent changes

---

## Files to Check

| Path | Purpose |
|------|---------|
| `scripts/swebench/convert_to_predictions.py` | Patch normalization - may need enhanced context restoration |
| `scripts/enhancers/run_solving_after_enhancement.py` | Solver prompt - needs context line instruction |
| `scripts/evaluate/build_predictions_jsonl.py` | Legacy solver - check how it generated patches |
| Solver agent code (OpenAI SDK) | Check actual prompt sent to LLM |

---

## Summary Table

| Category | Count | Cause |
|----------|-------|-------|
| Missing context lines | ~40 | Solver doesn't include context lines in diffs |
| File not found | ~6 | Solver targets wrong/non-existent files |
| Hunk context mismatch | ~5 | Line numbers wrong or file state mismatch |
| **Successfully applied** | **15** | Solver generated proper patches with context |
| **Total** | **66** | |
