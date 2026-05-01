#!/bin/bash
set -e

echo "🚀 Option 4 Full Evaluation: Before/After Code Approach"
echo "======================================================="
echo ""

# Create output directory
mkdir -p results/option4_full

echo "⏳ Step 1: Generating patches for all 10 instances..."
echo "   (This will take ~15-20 minutes with gpt-4o-mini API)"
echo ""

source .env && \
./bench_env/bin/python scripts/enhancers/run_solving_after_enhancement.py \
  --samples data/samples/swe_bench_live_10_tasks_for_harness.json \
  --max-issues 10 \
  --output-dir results/option4_full \
  --baseline-mode

echo ""
echo "✅ Generation complete!"
echo ""

# Step 2: Convert to predictions
echo "⏳ Step 2: Converting to SWE-bench predictions format..."
python3 << 'PYTHON'
import json
import os
from pathlib import Path

output_dir = Path("results/option4_full")
predictions = []

for json_file in sorted(output_dir.glob("*.json")):
    with open(json_file) as f:
        data = json.load(f)
    
    # Create prediction entry
    prediction = {
        "model_name_or_path": "openhands",
        "instance_id": json_file.stem.replace("openhands__", ""),
        "model_patch": data.get("patch", "")
    }
    predictions.append(prediction)

# Save predictions
pred_file = Path("eval_results/swebench/option4_full_predictions.jsonl")
pred_file.parent.mkdir(parents=True, exist_ok=True)
with open(pred_file, 'w') as f:
    for pred in predictions:
        f.write(json.dumps(pred) + '\n')

print(f"✅ Saved {len(predictions)} predictions to {pred_file}")
PYTHON

echo ""
echo "⏳ Step 3: Running SWE-bench harness evaluation..."
echo "   (This will take ~5-6 minutes with 3 parallel workers)"
echo ""

./scripts/run_parallel_evaluation_x3.sh 10 option4_full_predictions

echo ""
echo "========================================================="
echo "✅ OPTION 4 EVALUATION COMPLETE!"
echo "========================================================="
echo ""
echo "📊 Results Summary:"
echo "   Logs: logs/run_evaluation/option4_full_predictions/"
echo "   Report: logs/run_evaluation/option4_full_predictions/openhands__gpt-4o-mini.*.json"
echo ""
echo "🔍 To analyze results:"
echo "   python3 scripts/analyze_harness_results.py logs/run_evaluation/option4_full_predictions/"
echo ""
