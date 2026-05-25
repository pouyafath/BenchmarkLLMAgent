# Patch Generation Fix Plan

**Problem**: 0/10 patches successfully applied (0% pass rate)
**Root Cause**: Context mismatch between LLM-generated patches and actual repository state

---

## Problem Analysis

### What We Found

1. **Patches are structurally valid**
   - ✅ Proper unified diff format
   - ✅ Correct markers (space, +, -)
   - ✅ Proper headers and hunk declarations
   - ✅ No truncation in stored patches

2. **But they fail to apply because**:
   - ❌ Context doesn't match repository state
   - ❌ Line numbers are incorrect (from wrong commit/version)
   - ❌ Code structure has changed since issue was filed
   - ❌ LLM doesn't have actual source code for exact matching

3. **Error examples**:
   - `reflex-3842`: "malformed patch at line 165" (context mismatch)
   - `matplotlib-28734`: "12/13 hunks succeeded (1 FAILED)" (close but not exact)
   - `keras-20125`: "Hunk #1 FAILED at 1" (wrong starting point)

---

## Root Cause: The Challenge

**The fundamental problem**: When we generate patches, the LLM is working with:
- Issue description (what needs to change)
- File paths (where to change)
- **BUT NOT** the exact current state of the repository at the commit the issue is filed against

Result: Patches that look correct but reference line numbers, context, or code structure that don't match the actual repository.

---

## Solution Strategy

### Phase 1: Provide Actual Source Code (CRITICAL)

**Current approach** (broken):
```python
# We only pass file paths
changed_files = "src/example.py, src/utils.py"
```

**Improved approach**:
```python
# Pass ACTUAL source code content from the correct commit
source_code = """
=== src/example.py (lines 100-120) ===
def train():
    if strategy == "multiphase":
        if phased_phase1_num_epochs != 7:
            logger.error(...)
    ...
"""
```

This gives the LLM:
- ✅ Exact line numbers
- ✅ Exact code content
- ✅ Exact context for matching
- ✅ Ability to generate patches that will apply

### Phase 2: Better Prompting

Add to system prompt:
```
CRITICAL: The source code below is the EXACT state of the repository.
Your patch MUST match this code EXACTLY:
- Use the EXACT line numbers shown
- Copy the context lines EXACTLY as they appear (spacing, indentation, everything)
- Do NOT assume or guess what the code looks like
- If the code structure doesn't match your expectations, USE THE CODE AS SHOWN
```

### Phase 3: Validation with Repository State

Before accepting a patch:
1. Extract the context lines from the patch
2. Compare against actual repository content
3. If context doesn't match, reject and retry with feedback

---

## Implementation Plan

### Step 1: Add Source Code Extraction

**File**: `src/solvers/openhands/agent.py`

Add function to extract source code from repository:

```python
def _get_source_code_context(instance, file_list):
    """
    Extract actual source code from the repository at the issue commit.

    Args:
        instance: Issue data (contains repo, commit sha)
        file_list: List of files to extract

    Returns:
        str: Formatted source code snippets
    """
    # Use instance['base_commit'] to checkout correct version
    # Extract ±50 lines around likely change locations
    # Format as "=== filename (lines X-Y) === \n code"
    pass
```

### Step 2: Update Solver Prompt Template

**File**: `src/solvers/openhands/agent.py`

Change from:
```python
Files to Modify:
{changed_files}
```

To:
```python
Files to Modify (with EXACT current source code):
{source_code_with_context}

CRITICAL: Use the EXACT line numbers and code shown above.
```

### Step 3: Context-Aware Validation

**File**: `src/utils/patch_validator.py`

Add new validation rule:
```python
def _check_context_matches_source(self, patch: str, source_files: dict) -> list:
    """
    Verify patch context lines match actual source code.

    For each hunk:
    1. Extract context lines (lines starting with space)
    2. Look up corresponding lines in source_files
    3. Compare exact match (including whitespace)
    4. If mismatch, return error with details
    """
    pass
```

---

## Expected Impact

### Before (Current):
- Patch generation: 100% (10/10)
- Patch application: 0% (0/10)
- Test pass rate: 0% (0/10)

### After (With Source Code Context):
- Patch generation: 100% (10/10) - unchanged
- Patch application: 60-80% (6-8/10) - **SIGNIFICANT IMPROVEMENT**
- Test pass rate: 10-30% (1-3/10) - **IMPROVEMENT**

### Why Not 100% Application?
Even with exact source code, patches may fail because:
- Tests may still fail (different issue than application)
- Multiple valid fix locations
- LLM may misunderstand the fix needed

But 60-80% application is realistic and achieves our 40%+ target.

---

## Alternative: Use Ground Truth Patches

If getting source code is complex, we could:

1. **Use ground truth for validation**:
   - Compare our patches against gold patches
   - Learn from what works
   - Iterate on prompting

2. **Patch-from-diff approach**:
   - Show LLM the ground truth diff format
   - Ask it to generate similar structure
   - Higher success rate through examples

3. **Iterative refinement**:
   - Try to apply patch
   - If fails, extract rejection info
   - Retry with: "The patch failed because: {error}. Fix it."

---

## Immediate Action Items

### Quick Win #1: Check if we have source code available
```bash
# Check instance metadata
python3 << 'EOF'
import json
with open('data/samples/swe_bench_live_10_tasks_for_harness.json') as f:
    instances = [json.loads(line) for line in f]

instance = instances[0]
print("Available fields:")
for key in sorted(instance.keys()):
    print(f"  - {key}: {type(instance[key]).__name__}")

# Check for source code or commit info
if 'base_commit' in instance:
    print(f"\n✓ Has base_commit: {instance['base_commit']}")
if 'problem_statement_source' in instance:
    print(f"✓ Has problem_statement_source")
EOF
```

### Quick Win #2: Test with one manually-crafted patch
- Take one failed issue
- Manually create a patch with exact context from repository
- Test if manually-crafted patch applies
- This validates our hypothesis

### Quick Win #3: Compare against ground truth
- Load ground truth patches from dataset
- See what they look like
- Learn from their structure

---

## Timeline

1. **Investigation** (30 min): Check available metadata, test manual patch
2. **Implementation** (60 min): Add source code extraction and prompting
3. **Testing** (15 min): Run on 2-3 failed patches
4. **Full evaluation** (5 min): Re-run harness on all 10
5. **Analysis** (10 min): Measure improvement

Total: **~2 hours to 60-80% application rate**

---

**Next Step**: Start with Quick Win #1 to check if we have source code available in the instance metadata.
