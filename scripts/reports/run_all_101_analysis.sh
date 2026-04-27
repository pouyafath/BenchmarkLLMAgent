#!/bin/bash
# Master script to run all 101-issue analysis scripts in sequence

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=================================================================================================="
echo "RUNNING ALL 101-ISSUE ANALYSIS SCRIPTS"
echo "=================================================================================================="
echo ""
echo "Repository root: $REPO_ROOT"
echo "Python environment: bench_env/bin/python"
echo ""

cd "$REPO_ROOT"

# Activate virtual environment if not already active
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "bench_env" ]; then
        echo "Activating bench_env virtual environment..."
        source bench_env/bin/activate
    else
        echo "Warning: bench_env not found, using system Python"
    fi
fi

# Check for required dependencies
echo "Checking dependencies..."
python -c "import scipy" 2>/dev/null || {
    echo "Warning: scipy not found. Installing..."
    pip install scipy
}
echo "✓ All dependencies available"
echo ""

# Script 1: Main aggregate analysis
echo "=================================================================================================="
echo "SCRIPT 1/4: Aggregate Results Analysis"
echo "=================================================================================================="
bench_env/bin/python scripts/reports/analyze_101_issue_results.py
echo ""

# Script 2: Per-repository breakdown
echo "=================================================================================================="
echo "SCRIPT 2/4: Per-Repository Analysis"
echo "=================================================================================================="
bench_env/bin/python scripts/reports/per_repository_analysis.py
echo ""

# Script 3: Statistical significance tests
echo "=================================================================================================="
echo "SCRIPT 3/4: Statistical Significance Tests"
echo "=================================================================================================="
bench_env/bin/python scripts/reports/compute_statistical_significance.py
echo ""

# Script 4: 10 vs 101 issue comparison
echo "=================================================================================================="
echo "SCRIPT 4/4: 10-Issue vs 101-Issue Comparison"
echo "=================================================================================================="
bench_env/bin/python scripts/reports/compare_10_vs_101_issues.py
echo ""

# Summary
echo "=================================================================================================="
echo "ALL ANALYSIS COMPLETE"
echo "=================================================================================================="
echo ""
echo "Output files generated:"
echo "  • data/samples/101_issues_experiments/101_issue_aggregate_results.json"
echo "  • data/samples/101_issues_experiments/101_issue_per_repository_analysis.json"
echo "  • data/samples/101_issues_experiments/101_issue_statistical_significance.json"
echo "  • data/samples/101_issues_experiments/10_vs_101_issue_comparison.json"
echo ""
echo "Next steps:"
echo "  1. Review the analysis output above"
echo "  2. Update documentation with final 101-issue results"
echo "  3. Generate presentation-ready tables and figures"
echo ""
