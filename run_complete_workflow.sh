#!/bin/bash
# Complete workflow: generation → conversion → harness evaluation

set -e

cd /home/22pf2/BenchmarkLLMAgent

echo "🚀 COMPLETE WORKFLOW: Patch Generation + Harness Evaluation"
echo "================================================================"
echo ""

# Step 1: Wait for generation to complete
echo "⏳ Step 1: Waiting for patch generation to complete..."
echo "   Task ID: b1ee0f1"
echo "   This may take 20-30 minutes..."
echo ""

# Monitor the generation task
while true; do
    OUTPUT="/tmp/claude-10136/-home-22pf2/tasks/b1ee0f1.output"
    if tail -1 "$OUTPUT" 2>/dev/null | grep -q "^Done\." ; then
        echo "✅ Generation complete!"
        break
    fi

    # Show progress every 30 seconds
    if [ -f "$OUTPUT" ]; then
        count=$(grep -c "\[.*\] baseline_no_enhancement" "$OUTPUT" 2>/dev/null || echo "0")
        echo "   Progress: Checking status... (checking every 30 sec)"
    fi
    sleep 30
done

echo ""
echo "================================================================"
echo "✅ Step 1 DONE: All 10 patches generated"
echo ""

# Step 2: Convert to predictions format
echo "⏳ Step 2: Converting results to SWE-bench predictions JSONL..."
python3 convert_results_to_predictions.py
echo ""

# Check if conversion succeeded
if [ ! -f "eval_results/swebench/iteration5_with_source_code_predictions.jsonl" ]; then
    echo "❌ Conversion failed!"
    exit 1
fi

PRED_COUNT=$(wc -l < eval_results/swebench/iteration5_with_source_code_predictions.jsonl)
echo "✅ Step 2 DONE: $PRED_COUNT predictions created"
echo ""

# Step 3: Run harness evaluation
echo "================================================================"
echo "⏳ Step 3: Running SWE-bench harness evaluation (parallel x3)..."
echo "   This will take ~5-6 minutes"
echo ""

./scripts/run_parallel_evaluation_x3.sh 10 iteration5_with_source_code_predictions

echo ""
echo "================================================================"
echo "✅ WORKFLOW COMPLETE!"
echo ""
echo "📊 RESULTS READY:"
echo "   Logs: logs/run_evaluation/iteration5_with_source_code_predictions/"
echo "   Report: logs/run_evaluation/iteration5_with_source_code_predictions/openhands__gpt-4o-mini.*.json"
echo ""
echo "🔍 To view results:"
echo "   cat logs/run_evaluation/iteration5_with_source_code_predictions/openhands__gpt-4o-mini.iteration5_with_source_code_predictions.json | jq '.'"
echo ""
