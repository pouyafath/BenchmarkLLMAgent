#!/bin/bash
# Configure OpenAI API for BenchmarkLLMAgent
# Usage: source setup_openai.sh

# Set OpenAI model and endpoint
export OPENHANDS_SOLVER_MODEL="gpt-4o-mini"
export OPENHANDS_SOLVER_BASE_URL="https://api.openai.com/v1"
export OPENHANDS_SOLVER_TIMEOUT="300"

# Set API key - REPLACE WITH YOUR ACTUAL KEY
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  WARNING: OPENAI_API_KEY environment variable not set"
    echo "Please set it before running the solver:"
    echo "  export OPENAI_API_KEY=\"your-key-here\""
    echo "Or hardcode it in this script (not recommended for production)"
else
    export OPENHANDS_SOLVER_API_KEY="$OPENAI_API_KEY"
    echo "✓ OpenAI API configured:"
    echo "  Model: $OPENHANDS_SOLVER_MODEL"
    echo "  Base URL: $OPENHANDS_SOLVER_BASE_URL"
    echo "  Timeout: ${OPENHANDS_SOLVER_TIMEOUT}s"
    echo "  API Key: ${OPENHANDS_SOLVER_API_KEY:0:20}..."
fi
