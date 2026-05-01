#!/bin/bash
set -e

# SWE-Agent Baseline Test Script
# Purpose: Run official SWE-agent solver on 10 sample GitHub issues
# to determine if 0% patch rate is due to OpenHands or architectural issues

PROJECT_DIR="/home/22pf2/BenchmarkLLMAgent"
SWEAGENT_DIR="/home/22pf2/SWE-agent"

echo "=================================================="
echo "🤖 SWE-Agent Baseline Test"
echo "=================================================="
echo ""
echo "Configuration:"
echo "  Solver: SWE-agent v1.1.0 (official)"
echo "  Model: gpt-4o-2024-08-06 (latest GPT-4o)"
echo "  Instances: 10 sample GitHub issues"
echo "  Output: results/sweagent_gpt4o_test/"
echo ""

# Verify environment
echo "Step 1: Verifying environment..."
if [ ! -d "$SWEAGENT_DIR" ]; then
  echo "❌ ERROR: SWE-agent directory not found at $SWEAGENT_DIR"
  exit 1
fi

if [ ! -f "$PROJECT_DIR/our_10_instances_fixed.json" ]; then
  echo "❌ ERROR: Instance file not found at $PROJECT_DIR/our_10_instances_fixed.json"
  exit 1
fi

if [ ! -f "$PROJECT_DIR/.env" ]; then
  echo "❌ ERROR: .env file not found (needs OpenAI API key)"
  exit 1
fi

echo "✅ All prerequisites verified"
echo ""

# Create output directory
mkdir -p "$PROJECT_DIR/results/sweagent_gpt4o_test"
echo "✅ Output directory ready: results/sweagent_gpt4o_test/"
echo ""

# Change to SWE-agent directory
cd "$SWEAGENT_DIR"

# Activate conda environment
echo "Step 2: Activating Python 3.11 environment..."
eval "$(conda shell.bash hook)"
conda activate sweagent 2>&1 | grep -v "^(sweagent)" | head -3

# Verify Python version
python_version=$(python --version 2>&1)
if [[ "$python_version" != *"3.11"* ]]; then
  echo "❌ ERROR: Python 3.11 not active. Got: $python_version"
  exit 1
fi
echo "✅ Python 3.11 active"
echo ""

# Source API keys
echo "Step 3: Loading API configuration..."
source "$PROJECT_DIR/.env"
export OPENAI_API_KEY="$OPENHANDS_SOLVER_API_KEY"
echo "✅ API configuration loaded"
echo ""

# Run SWE-agent
echo "Step 4: Starting SWE-agent baseline test..."
echo "This may take 30-60 minutes per instance (10 instances total)"
echo ""
echo "=================================================="

python -m sweagent.run \
  --agent_model gpt-4o-2024-08-06 \
  --environment_name docker \
  --instances.type file \
  --instances.path "$PROJECT_DIR/our_10_instances_fixed.json" \
  --instances.limit 10 \
  --output_dir "$PROJECT_DIR/results/sweagent_gpt4o_test" \
  --skip_existing

echo ""
echo "=================================================="
echo "✅ SWE-agent test completed!"
echo ""
echo "Results location: results/sweagent_gpt4o_test/"
echo ""
echo "To analyze results, run:"
echo "  python $PROJECT_DIR/analyze_sweagent_results.py"
echo ""
