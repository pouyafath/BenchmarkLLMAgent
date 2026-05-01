#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from src.utils.source_code_extractor import SourceCodeExtractor

# Load sample
with open("data/samples/swe_bench_live_10_tasks_for_harness.json") as f:
    issues = json.load(f)
    issue = [i for i in issues if i.get("issue_number") == 3135 and "instructlab" in i.get("pr_repo", "")][0]

# Test extraction
extractor = SourceCodeExtractor()
result = extractor.extract_before_after_code_for_instance(issue)

print("=== EXTRACTION TEST ===")
print(f"Total length: {len(result)} chars")

# Check if BEFORE and AFTER sections are different
lines = result.split('\n')
before_start = None
after_start = None

for i, line in enumerate(lines):
    if 'BEFORE' in line:
        before_start = i
    if 'AFTER' in line and before_start is not None:
        after_start = i
        break

if before_start and after_start:
    before_section = '\n'.join(lines[before_start:after_start])
    after_section = '\n'.join(lines[after_start:])
    
    print(f"\nBEFORE section size: {len(before_section)} chars")
    print(f"AFTER section size: {len(after_section)} chars")
    
    if before_section == after_section:
        print("\n❌ BEFORE and AFTER are IDENTICAL!")
    else:
        print(f"\n✅ BEFORE and AFTER are DIFFERENT")
        # Find first difference
        for i, (b, a) in enumerate(zip(before_section, after_section)):
            if b != a:
                print(f"First difference at position {i}:")
                print(f"  BEFORE: ...{before_section[max(0,i-50):i+50]}...")
                print(f"  AFTER:  ...{after_section[max(0,i-50):i+50]}...")
                break

print("\n=== FIRST 500 CHARS ===")
print(result[:500])
