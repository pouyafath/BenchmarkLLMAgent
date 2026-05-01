#!/usr/bin/env python3
"""
Convert solver results to SWE-bench predictions JSONL format.
Ready to run after patch generation completes.
"""

import json
from pathlib import Path
import sys

def convert_results_to_predictions(results_dir: Path, output_file: Path):
    """Convert solver JSON results to SWE-bench predictions JSONL format."""

    predictions = []
    results_dir = Path(results_dir)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"📂 Reading results from: {results_dir}")

    # Find all solver result files
    result_files = sorted(results_dir.glob("openhands__*.json"))

    if not result_files:
        print(f"❌ No result files found in {results_dir}")
        return 0

    print(f"📋 Found {len(result_files)} result files")

    for json_file in result_files:
        try:
            with open(json_file) as f:
                data = json.load(f)

            # Extract prediction
            instance_id = data.get("issue_id") or json_file.stem
            patch = data.get("patch", "")
            model = data.get("model", "openhands")

            prediction = {
                "instance_id": instance_id,
                "model_patch": patch,
                "model_name_or_path": f"openhands__{model}"
            }

            predictions.append(prediction)
            print(f"  ✅ {instance_id}: {len(patch)} chars")

        except Exception as e:
            print(f"  ❌ Failed to read {json_file}: {e}")

    # Write predictions JSONL
    with open(output_file, 'w') as f:
        for pred in predictions:
            f.write(json.dumps(pred) + '\n')

    print(f"\n✅ Wrote {len(predictions)} predictions to {output_file}")
    return len(predictions)

if __name__ == "__main__":
    results_dir = Path("results/iteration5_with_source_code")
    output_file = Path("eval_results/swebench/iteration5_with_source_code_predictions.jsonl")

    count = convert_results_to_predictions(results_dir, output_file)

    if count > 0:
        print(f"\n📊 Ready for harness evaluation!")
        print(f"   Run: ./scripts/run_parallel_evaluation_x3.sh 10 iteration5_with_source_code_predictions")
    else:
        print(f"\n⚠️  No predictions to evaluate")
        sys.exit(1)
