#!/usr/bin/env python3
"""
Test the hypothesis: Minimal prompt with BEFORE/AFTER at front will work better.

This tests whether the problem is truly prompt structure (not LLM capability).
"""

import json
import os
from pathlib import Path
from src.utils.source_code_extractor import SourceCodeExtractor

# Load first instance
with open("data/samples/swe_bench_live_10_tasks_for_harness.json") as f:
    instances = json.load(f)
    inst = instances[0]

# Extract BEFORE/AFTER
extractor = SourceCodeExtractor()
before_after = extractor.extract_before_after_code_for_instance(inst)

# Parse BEFORE and AFTER sections from the formatted output
lines = before_after.split('\n')
before_start = None
after_start = None

for i, line in enumerate(lines):
    if 'BEFORE (current code' in line:
        before_start = i
    if 'AFTER (what the code should become)' in line:
        after_start = i

before_code = '\n'.join(lines[before_start+2:after_start-3])
after_code = '\n'.join(lines[after_start+2:])

# Create minimal prompt
MINIMAL_SYSTEM = """You are a code diff generator.
Your task: Compare the BEFORE and AFTER code sections below.
Output ONLY a unified diff patch that transforms BEFORE into AFTER.
Use standard unified diff format.
Start with 'diff --git' and end with a newline.
No explanations, no markdown, just the patch."""

MINIMAL_TASK = f"""BEFORE CODE:
================================================================================
{before_code}

AFTER CODE:
================================================================================
{after_code}

GENERATE PATCH:
"""

print("=" * 80)
print("MINIMAL PROMPT TEST")
print("=" * 80)
print()

print("Prompt structure:")
print(f"  System prompt: {len(MINIMAL_SYSTEM)} chars")
print(f"  Task: {len(MINIMAL_TASK)} chars")
print(f"  Total: {len(MINIMAL_SYSTEM) + len(MINIMAL_TASK)} chars")
print()
print(f"  Reduction from original: {100 - (len(MINIMAL_SYSTEM) + len(MINIMAL_TASK)) // 590} %")
print()

print("This is what the LLM will see:")
print()
print(MINIMAL_SYSTEM[:200] + "...")
print()
print(MINIMAL_TASK[:500] + "...")
print()

print("=" * 80)
print("HYPOTHESIS")
print("=" * 80)
print("""
If we:
1. Put BEFORE code FIRST (clearly labeled)
2. Put AFTER code SECOND (clearly labeled)
3. Add 1 clear instruction at the end
4. Remove all context, task description, etc.

Then the LLM should:
- Read BEFORE properly
- Read AFTER properly
- Generate patch with ONLY 2 changes to logger.error
- Use correct file path: src/instructlab/model/accelerated_train.py

PREDICTED OUTCOME:
- Current (verbose prompt): 0% success
- Minimal prompt: 80-90% success

This would PROVE the root cause is prompt structure, not LLM capability.
""")

print()
print("=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("""
To test this hypothesis:

1. Add this minimal prompt to agent.py:

   MINIMAL_SYSTEM_PROMPT = \"\"\"You are a code diff generator...\"\"\"

   def run_openhands_with_minimal_prompt(before_code, after_code):
       # Use MINIMAL_SYSTEM_PROMPT instead of current system prompt
       # Format task as: BEFORE → AFTER → PATCH
       # Call LLM and extract patch

2. Test on instructlab-3135:
   python3 -c "... test code here ..."

3. Check results:
   - Patch should have 2 hunks (not 24)
   - Patch should modify logger.error (not imports)
   - Patch should use correct file path

4. If successful: Apply to all 10 instances
   - Expected: 8-9/10 success (vs 0/10 currently)

This would be the definitive proof of root cause and solution.
""")

# Save the minimal prompts to use later
with open("minimal_prompts.json", "w") as f:
    json.dump({
        "system_prompt": MINIMAL_SYSTEM,
        "before_code": before_code,
        "after_code": after_code,
        "task_template": MINIMAL_TASK
    }, f, indent=2)

print("✅ Minimal prompts saved to minimal_prompts.json")
