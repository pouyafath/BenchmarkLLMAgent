#!/bin/bash
# Complete workflow for iteration5_fixed: generation → conversion → harness

set -e
cd /home/22pf2/BenchmarkLLMAgent

echo "🚀 COMPLETE WORKFLOW (Fixed Format): Waiting for generation + Harness"
echo "=================================================================="
echo ""

# Step 1: Wait for generation to complete
echo "⏳ Step 1: Waiting for patch generation to complete..."
echo "   Current task: b01232f"
echo "   This may take 20-30 minutes..."
echo ""

while true; do
    OUTPUT="/tmp/claude-10136/-home-22pf2/tasks/b01232f.output"
    if [ -f "$OUTPUT" ] && tail -1 "$OUTPUT" 2>/dev/null | grep -q "^Done\." ; then
        echo "✅ Generation complete!"
        break
    fi

    # Show progress every 30 seconds
    if [ -f "$OUTPUT" ]; then
        count=$(grep -c "Time=" "$OUTPUT" 2>/dev/null || echo "0")
        echo "   Progress: $count/10 instances done..."
    fi
    sleep 30
done

echo ""
echo "=================================================================="
echo "✅ Step 1 DONE: All 10 patches generated with fixed format"
echo ""

# Step 2: Convert to predictions format
echo "⏳ Step 2: Converting results to SWE-bench predictions JSONL..."

python3 << 'PYTHON_EOF'
import json
from pathlib import Path

results_dir = Path("results/iteration5_fixed")
output_file = Path("eval_results/swebench/iteration5_fixed_predictions.jsonl")

predictions = []
output_file.parent.mkdir(parents=True, exist_ok=True)

result_files = sorted(results_dir.glob("openhands__*.json"))

if not result_files:
    print(f"❌ No result files found in {results_dir}")
    exit(1)

print(f"📋 Found {len(result_files)} result files")

for json_file in result_files:
    try:
        with open(json_file) as f:
            data = json.load(f)

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

with open(output_file, 'w') as f:
    for pred in predictions:
        f.write(json.dumps(pred) + '\n')

print(f"\n✅ Wrote {len(predictions)} predictions to {output_file}")
PYTHON_EOF

echo ""

# Step 3: Run harness evaluation
echo "=================================================================="
echo "⏳ Step 3: Running SWE-bench harness evaluation (parallel x3)..."
echo "   This will take ~5-6 minutes"
echo ""

/home/22pf2/BenchmarkLLMAgent/scripts/run_parallel_evaluation_x3.sh 10 iteration5_fixed_predictions

echo ""
echo "=================================================================="
echo "✅ WORKFLOW COMPLETE!"
echo ""
echo "📊 RESULTS READY:"
echo "   Logs: logs/run_evaluation/iteration_parallel_x3/"
echo "   Report: logs/run_evaluation/iteration_parallel_x3/openhands__gpt-4o-mini.*.json"
echo ""
echo "🔍 To view summary:"
echo "   cat logs/run_evaluation/iteration_parallel_x3/openhands__gpt-4o-mini.iteration5_fixed_predictions.json | jq '.'"
echo ""
