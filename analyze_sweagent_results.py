#!/usr/bin/env python3
"""
Analyze SWE-Agent baseline test results
Compares patch application rate to OpenHands baseline
"""

import os
import json
import glob
from pathlib import Path
from collections import defaultdict

PROJECT_DIR = Path("/home/22pf2/BenchmarkLLMAgent")
RESULTS_DIR = PROJECT_DIR / "results/sweagent_gpt4o_test"

def analyze_results():
    """Analyze SWE-agent results across all instances"""

    print("=" * 60)
    print("SWE-Agent Baseline Test Results Analysis")
    print("=" * 60)
    print()

    if not RESULTS_DIR.exists():
        print("❌ ERROR: Results directory not found")
        print(f"Expected: {RESULTS_DIR}")
        return

    # Find all instance directories
    instance_dirs = sorted([d for d in RESULTS_DIR.iterdir() if d.is_dir()])

    if not instance_dirs:
        print("⚠️ No instance results found yet")
        print("Test may still be running...")
        return

    print(f"Found {len(instance_dirs)} instance results")
    print()

    results = defaultdict(dict)
    resolved_count = 0
    failed_count = 0
    error_count = 0

    # Analyze each instance
    for inst_dir in instance_dirs:
        instance_id = inst_dir.name

        # Look for trajectory file (main result)
        traj_file = inst_dir / f"{instance_id}.traj"
        log_file = inst_dir / f"{instance_id}.debug.log"

        status = "UNKNOWN"
        details = ""

        if traj_file.exists():
            try:
                with open(traj_file, 'r') as f:
                    traj_data = json.load(f)

                    # Check if test passed
                    if isinstance(traj_data, dict):
                        # Check for pass/fail indicators
                        if 'test_result' in traj_data:
                            test_result = traj_data['test_result']
                            if test_result.get('passed'):
                                status = "RESOLVED ✅"
                                resolved_count += 1
                            else:
                                status = "FAILED ❌"
                                details = test_result.get('failure_reason', 'Unknown')
                                failed_count += 1
                        else:
                            # If no explicit test_result, check trajectory messages
                            messages = traj_data.get('messages', [])
                            if any('submit' in str(m).lower() for m in messages):
                                status = "RESOLVED ✅"
                                resolved_count += 1
                            else:
                                status = "IN PROGRESS 🔄"
                                failed_count += 1
            except json.JSONDecodeError:
                status = "ERROR (corrupt) ⚠️"
                error_count += 1
        elif log_file.exists():
            # Check log file for errors
            with open(log_file, 'r') as f:
                log_content = f.read()
                if 'CRITICAL' in log_content or 'ERROR' in log_content:
                    status = "ERROR ⚠️"
                    error_count += 1
                    # Extract error message
                    for line in log_content.split('\n'):
                        if 'ERROR' in line or 'CRITICAL' in line:
                            details = line.strip()
                            break
                else:
                    status = "IN PROGRESS 🔄"
        else:
            status = "NO RESULTS 🔄"

        results[instance_id] = {
            'status': status,
            'details': details
        }

        # Print result
        print(f"{instance_id}")
        print(f"  Status: {status}")
        if details:
            print(f"  Details: {details[:100]}")
        print()

    # Summary statistics
    print("=" * 60)
    print("Summary Statistics")
    print("=" * 60)
    print()

    total = len(instance_dirs)
    print(f"Total instances: {total}")
    print(f"  ✅ Resolved: {resolved_count} ({100*resolved_count/total:.1f}%)")
    print(f"  ❌ Failed: {failed_count} ({100*failed_count/total:.1f}%)")
    print(f"  ⚠️  Errors: {error_count} ({100*error_count/total:.1f}%)")
    print()

    # Comparison to OpenHands baseline
    print("Comparison to Baselines:")
    print("=" * 60)
    print(f"OpenHands baseline (gpt-4o-mini): 0%")
    print(f"SWE-agent test results: {100*resolved_count/total:.1f}%")
    print()

    if resolved_count > 0:
        print("✅ CONCLUSION: SWE-agent performs better than OpenHands")
        print("   Action: Consider switching to SWE-agent as primary solver")
    elif resolved_count == 0 and error_count == 0:
        print("❌ CONCLUSION: SWE-agent also fails on our dataset")
        print("   Action: Problem is likely architectural, not solver-specific")
        print("   Recommendations:")
        print("   1. Try better model (Claude 3 or GPT-4 Turbo)")
        print("   2. Try different task framing (direct instruction vs. comparison)")
        print("   3. Try Option 5 (iterative refinement with feedback)")
    else:
        print("⚠️  INCONCLUSIVE: Some instances had errors")
        print("   Action: Debug errors and re-run failed instances")

    print()
    print("=" * 60)

if __name__ == "__main__":
    analyze_results()
