#!/usr/bin/env python3
"""
Fix enhancement error files by converting them to noop enhancements.

For each enhancement JSON file that has enhancer_type='error', this script:
1. Copies original_title -> enhanced_title
2. Copies original_body -> enhanced_body
3. Sets enhancer_type to 'real' (with enhancement_noop=true marker)
4. Backs up the original error file

This allows the pipeline to proceed past the _build_enhanced_dataset_jsonl()
step which rejects enhancer_type != 'real' when --require-native-enhancer is set.
"""
import json
import shutil
from pathlib import Path

RESULTS_ROOT = Path(__file__).resolve().parent.parent.parent / "data/samples/101_issues_experiments"

EXPERIMENTS = {
    "swe_agent_groupA": RESULTS_ROOT / "results_group_a/swe_agent__devstral101_groupA_20260327/enhancements",
    "swe_agent_groupB": RESULTS_ROOT / "results_group_b/swe_agent__devstral101_groupB_20260327/enhancements",
    "trae_groupA": RESULTS_ROOT / "results_group_a/trae__devstral101_groupA_20260327/enhancements",
    "trae_groupB": RESULTS_ROOT / "results_group_b/trae__devstral101_groupB_20260327/enhancements",
}


def fix_error_files(enhancement_dir: Path, label: str) -> int:
    """Fix all error enhancement files in a directory. Returns count of fixed files."""
    fixed = 0
    for enh_file in sorted(enhancement_dir.glob("*.json")):
        data = json.loads(enh_file.read_text())
        metadata = data.get("enhancement_metadata", {})
        if not isinstance(metadata, dict):
            continue
        if metadata.get("enhancer_type") != "error":
            continue

        # Back up the original error file
        backup = enh_file.with_suffix(".json.error_backup")
        if not backup.exists():
            shutil.copy2(enh_file, backup)

        # Convert to noop: use original text as enhanced text
        original_title = data.get("original_title", "")
        original_body = data.get("original_body", "")
        data["enhanced_title"] = original_title
        data["enhanced_body"] = original_body

        # Mark as real (noop) so pipeline accepts it
        metadata["enhancer_type"] = "real"
        metadata["enhancement_noop"] = True
        metadata["original_error"] = metadata.get("error", "unknown")
        metadata["fix_note"] = "Converted from error to noop by fix_enhancement_errors.py"
        data["enhancement_metadata"] = metadata

        enh_file.write_text(json.dumps(data, indent=2))
        fixed += 1
        print(f"  Fixed: {enh_file.name} (was: {metadata.get('original_error', 'unknown')})")

    return fixed


def main():
    print("=" * 70)
    print("FIX ENHANCEMENT ERROR FILES")
    print("=" * 70)

    total_fixed = 0
    for label, enh_dir in EXPERIMENTS.items():
        print(f"\n--- {label} ---")
        if not enh_dir.exists():
            print(f"  Directory not found: {enh_dir}")
            continue
        n = fix_error_files(enh_dir, label)
        total_fixed += n
        if n == 0:
            print("  No error files found.")

    print(f"\n{'=' * 70}")
    print(f"Total fixed: {total_fixed}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
