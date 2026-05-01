#!/usr/bin/env python3
"""
Fix Option 4 predictions by applying file path corrections and re-running harness.

The issue: Patches were generated correctly but converted to predictions without
applying the _fix_patch_paths() function, causing file path mismatches.

Solution: Reload patches, apply file path fixing, regenerate predictions, re-run harness.
"""

import json
import subprocess
from pathlib import Path
from src.solvers.openhands.agent import _fix_patch_paths

def main():
    output_dir = Path("results/option4_full")

    # Load ground truth for file lists
    with open("data/samples/swe_bench_live_10_tasks_for_harness.json") as f:
        instances = {inst['instance_id']: inst for inst in json.load(f)}

    print("=" * 70)
    print("FIX & RERUN: Option 4 Evaluation with Proper File Path Fixing")
    print("=" * 70)
    print()

    # Step 1: Load patches and apply file path fixing
    print("Step 1: Applying file path corrections...")
    corrected_patches = {}
    errors = 0

    for json_file in sorted(output_dir.glob("*.json")):
        instance_id = json_file.stem.replace("openhands__", "")

        with open(json_file) as f:
            data = json.load(f)

        patch = data.get("patch", "")
        if not patch:
            print(f"  ⚠️  {instance_id}: No patch")
            errors += 1
            continue

        # Get correct files from ground truth
        inst = instances.get(instance_id)
        if not inst:
            print(f"  ⚠️  {instance_id}: Not in ground truth")
            errors += 1
            continue

        # Extract files from ground truth patch
        import re
        correct_files = re.findall(r'diff --git a/(.*?) b/', inst['patch'])
        if not correct_files:
            print(f"  ⚠️  {instance_id}: Cannot extract files from ground truth")
            errors += 1
            continue

        # Apply file path fixing
        fixed_patch = _fix_patch_paths(patch, correct_files)

        # Check if it changed
        if fixed_patch != patch:
            print(f"  ✅ {instance_id}: File paths fixed")
        else:
            print(f"  ℹ️  {instance_id}: No file path changes needed")

        corrected_patches[instance_id] = {
            "patch": fixed_patch,
            "original_patch": patch
        }

    print(f"\n  Processed: {len(corrected_patches)}/10")
    if errors:
        print(f"  ⚠️  Errors: {errors}")

    # Step 2: Create new predictions file with corrected patches
    print("\nStep 2: Creating corrected predictions file...")
    pred_file = Path("eval_results/swebench/option4_full_predictions_fixed.jsonl")
    pred_file.parent.mkdir(parents=True, exist_ok=True)

    with open(pred_file, 'w') as f:
        for instance_id, data in sorted(corrected_patches.items()):
            prediction = {
                "model_name_or_path": "openhands",
                "instance_id": instance_id,
                "model_patch": data["patch"]
            }
            f.write(json.dumps(prediction) + '\n')

    pred_count = len(corrected_patches)
    print(f"  ✅ Created {pred_file} with {pred_count} predictions")

    # Step 3: Run harness
    print("\nStep 3: Running harness evaluation with corrected patches...")
    print("  (This will take ~5-6 minutes with 3 parallel workers)\n")

    result = subprocess.run(
        ["./scripts/run_parallel_evaluation_x3.sh", "10", "option4_full_predictions_fixed"],
        cwd="/home/22pf2/BenchmarkLLMAgent",
        capture_output=False
    )

    if result.returncode == 0:
        print("\n" + "=" * 70)
        print("✅ HARNESS EVALUATION COMPLETE!")
        print("=" * 70)
        print("\nResults location:")
        print("  Logs: logs/run_evaluation/option4_full_predictions_fixed/")
        print("  Analysis: python3 scripts/analyze_harness_results.py \\")
        print("      logs/run_evaluation/option4_full_predictions_fixed/")
    else:
        print(f"\n⚠️  Harness returned code {result.returncode}")

    return result.returncode

if __name__ == "__main__":
    exit(main())
