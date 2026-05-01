#!/bin/bash
set -e

echo "🧪 Testing Option 4 (Hybrid Approach) on 1 instance"
echo "=================================================="
echo ""

# Create output directory
mkdir -p results/test_option4

# Run generation on just 1 instance to test
echo "⏳ Generating patch with before/after code format..."
source .env && \
./bench_env/bin/python scripts/enhancers/run_solving_after_enhancement.py \
  --samples data/samples/swe_bench_live_10_tasks_for_harness.json \
  --max-issues 1 \
  --output-dir results/test_option4 \
  --baseline-mode \
  2>&1 | tee test_option4.log

echo ""
echo "✅ Generation complete!"
echo ""
echo "📋 Generated patch:"
if [ -f "results/test_option4/openhands__instructlab__instructlab__3135.json" ]; then
    echo "JSON file created. Checking patch content..."
    python3 << 'PYTHON'
import json
with open("results/test_option4/openhands__instructlab__instructlab__3135.json") as f:
    data = json.load(f)
    print("Patch content (first 500 chars):")
    print(data.get("patch", "NO PATCH")[:500])
    print("\n...")
    print("\nPatch ends with:")
    print(data.get("patch", "NO PATCH")[-200:])
PYTHON
else
    echo "❌ No JSON file generated"
fi
