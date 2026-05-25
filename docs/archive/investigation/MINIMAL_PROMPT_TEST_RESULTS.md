# Minimal Prompt Test Results - March 17, 2026

## Investigation Outcome

**Status**: ❌ Minimal prompt approach did NOT fix the issue

## Key Findings

### 1. Extraction IS Working Perfectly ✅

- BEFORE/AFTER extraction correctly produces different code blocks
- File: `src/instructlab/model/accelerated_train.py`
- First difference: Line 235 logger.error format change
  ```
  BEFORE: logger.error("Failed during training loop: ", e)
  AFTER:  logger.error("Failed during training loop: %s", e, exc_info=True)
  ```
- Total difference: 34 chars (AFTER is 28,085 chars vs BEFORE 28,051 chars)

### 2. LLM Is Still Generating Wrong Patches ❌

Despite receiving correct BEFORE/AFTER content:
- Generated patch for WRONG file: `instructlab/cli/train_accelerated.py` (not `src/instructlab/model/accelerated_train.py`)
- Patch structure is malformed:
  - Missing `diff --git` header
  - Incomplete hunk headers (missing line numbers)
  - Patch ends with `(the rest of the original file omitted for brevity)` - NOT valid unified diff
- Total size: 23,639 chars (seems too large for just logger.error changes)

### 3. Prompt Updates Made

Tested multiple prompt versions:
1. **Ultra-minimal** (3 lines system prompt): Generated identical -/+ pairs (do-nothing patch)
2. **Explicit format** (with diff format rules): Still generates wrong files and truncation
3. **Instructions-heavy** (with step-by-step): Same hallucination patterns

### 4. Root Cause Analysis

The problem is NOT prompt structure or token length. The issue is:

**The gpt-oss:120b model via Ollama is fundamentally unable to reliably:**
1. Compare two large code blocks (757 lines each)
2. Generate proper unified diff format
3. Resist hallucinating based on training data patterns
4. Generate code that looks like the actual changes (e.g., small logger.error updates)

Instead, it:
- Invents file names and changes (training data priors)
- Generates do-nothing patches (safe fallback when confused)
- Truncates output with ellipsis (avoids large output)
- Fails to maintain diff format standards

## Implications

The "minimal prompt fixes hallucination" hypothesis from COMPREHENSIVE_FINDINGS_AND_SOLUTION.md **was incorrect**. The real bottleneck is **model capability**, not prompt engineering.

## What Would Actually Help

1. **Better Model**: Use Claude 3 or GPT-4 which have better code reasoning
2. **Simpler Task Framing**: Instead of "compare BEFORE and AFTER", try:
   - "Here's the change you need to make: on line 235, change X to Y"
   - "Apply this specific modification to this file"
   - Direct instruction instead of implicit comparison
3. **Iterative Approach** (Option 5): Generate → validate → feedback → regenerate
4. **Template-Based**: Instead of LLM generating from scratch, provide patches with gaps to fill

## Test Results Summary

| Approach | Outcome | Patch Quality |
|----------|---------|---------------|
| Original Option 4 (verbose prompt) | 0/10 ❌ | Wrong files, phantom pairs |
| Ultra-minimal prompt | 0/10 ❌ | Identical -/+ lines |
| Explicit format prompt | 0/10 ❌ | Wrong files, malformed headers |
| Instruction-heavy prompt | 0/10 ❌ | Same hallucination patterns |

**All approaches with gpt-oss:120b fail.**

## Next Steps

Option 5 (Iterative Refinement) would involve:
1. Generate initial patch
2. Validate structure
3. If invalid: provide explicit feedback + ground truth fragment
4. Regenerate with feedback
5. Repeat up to 3 times

Expected improvement: 30-50% (vs current 0%)

---

**Conclusion**: Prompt engineering alone cannot fix model capability limitations. Need either better model or different task framing entirely.
