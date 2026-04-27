"""
Run complete pipeline for a single issue with comprehensive metrics.

Workflow:
1. Extract single issue
2. Run enhancement agents
3. Run solver agents
4. Run SWE-bench harness evaluation
5. Compute all comprehensive metrics
"""
import json
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent


def extract_single_issue(issue_index: int = 0, output_name: str = "single_issue") -> Path:
    """Extract a single issue from the 10-sample file."""
    logger.info(f"Extracting issue at index {issue_index}...")

    samples_path = ROOT / "data/samples/swe_bench_live_10_samples.json"
    with open(samples_path) as f:
        data = json.load(f)

    if issue_index >= len(data["issues"]):
        raise ValueError(f"Issue index {issue_index} out of range (max: {len(data['issues'])-1})")

    issue = data["issues"][issue_index]
    issue_id = issue["issue_id"]

    logger.info(f"Selected issue: {issue_id}")
    logger.info(f"  Title: {issue['title']}")
    logger.info(f"  Repo: {issue['repo_name']}")

    # Create single-issue file
    single_issue_data = {
        "metadata": {
            "description": f"Single issue for testing: {issue_id}",
            "source": "SWE-bench-Live/SWE-bench-Live",
            "count": 1
        },
        "issues": [issue]
    }

    output_path = ROOT / f"data/samples/{output_name}.json"
    with open(output_path, "w") as f:
        json.dump(single_issue_data, f, indent=2)

    logger.info(f"✓ Saved single issue to: {output_path}")
    return output_path, issue_id


def run_enhancement_pipeline(sample_file: Path, iteration_name: str):
    """Run enhancement pipeline on the sample."""
    logger.info("=" * 80)
    logger.info("STEP 1: Running Enhancement Pipeline")
    logger.info("=" * 80)

    cmd = [
        sys.executable,
        str(ROOT / "scripts/run_benchmark_enhancement.py"),
        "--sample-file", str(sample_file),
        "--iteration-name", iteration_name,
        "--log-dir", str(ROOT / "logs/enhancement_benchmark"),
    ]

    logger.info(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        logger.error("Enhancement pipeline failed!")
        return False

    logger.info("✓ Enhancement pipeline completed")
    return True


def run_solver_pipeline(iteration_name: str):
    """Run solver agents on enhanced issues."""
    logger.info("=" * 80)
    logger.info("STEP 2: Running Solver Pipeline")
    logger.info("=" * 80)

    # Create predictions directory
    predictions_dir = ROOT / "logs/run_evaluation" / iteration_name
    predictions_dir.mkdir(parents=True, exist_ok=True)

    # Run baseline
    logger.info("\n--- Running BASELINE (no enhancement) ---")
    cmd_baseline = [
        sys.executable,
        str(ROOT / "scripts/run_solver_swe_agent.py"),
        "--iteration-name", iteration_name,
        "--agent-type", "baseline",
        "--enhanced-issues-dir", str(ROOT / "logs/enhancement_benchmark" / iteration_name),
    ]
    logger.info(f"Command: {' '.join(cmd_baseline)}")
    subprocess.run(cmd_baseline, cwd=ROOT)

    # Run enhanced agents
    enhanced_agents = [
        "enhanced_live_swe_agent",
        "enhanced_mini_swe_agent",
        "enhanced_openhands",
        "enhanced_simple_enhancer",
        "enhanced_trae"
    ]

    for agent in enhanced_agents:
        logger.info(f"\n--- Running {agent} ---")
        enhancer = agent.replace("enhanced_", "")

        cmd = [
            sys.executable,
            str(ROOT / "scripts/run_solver_swe_agent.py"),
            "--iteration-name", iteration_name,
            "--agent-type", "enhanced",
            "--enhancer-name", enhancer,
            "--enhanced-issues-dir", str(ROOT / "logs/enhancement_benchmark" / iteration_name),
        ]
        logger.info(f"Command: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=ROOT)

    logger.info("✓ Solver pipeline completed")
    return True


def run_swebench_harness(iteration_name: str):
    """Run SWE-bench harness evaluation."""
    logger.info("=" * 80)
    logger.info("STEP 3: Running SWE-bench Harness Evaluation")
    logger.info("=" * 80)

    predictions_dir = ROOT / "logs/run_evaluation" / iteration_name

    # Ensure swebench is installed
    logger.info("Checking swebench installation...")
    check_cmd = [
        "./bench_env/bin/python",
        "-c",
        "import swebench; print(swebench.__version__)"
    ]
    result = subprocess.run(check_cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("swebench not installed! Install with: ./bench_env/bin/pip install swebench")
        return False

    logger.info(f"✓ swebench version: {result.stdout.strip()}")

    # Find all prediction files
    prediction_files = list(predictions_dir.glob("*/all_preds.jsonl"))

    if not prediction_files:
        logger.error(f"No prediction files found in {predictions_dir}")
        return False

    logger.info(f"Found {len(prediction_files)} prediction files")

    # Run evaluation for each
    for pred_file in prediction_files:
        agent_name = pred_file.parent.name
        logger.info(f"\n--- Evaluating {agent_name} ---")

        cmd = [
            "./bench_env/bin/python",
            "-m", "swebench.harness.run_evaluation",
            "--predictions_path", str(pred_file),
            "--swe_bench_tasks", str(ROOT / "data/samples/swe_bench_live_10_samples.json"),
            "--log_dir", str(pred_file.parent),
            "--testbed", str(ROOT / "testbed"),
            "--skip_existing", "False",
            "--timeout", "900",
            "--verbose"
        ]

        logger.info(f"Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=ROOT)

        if result.returncode == 0:
            logger.info(f"✓ Evaluation completed for {agent_name}")
        else:
            logger.warning(f"⚠ Evaluation may have encountered issues for {agent_name}")

    logger.info("✓ SWE-bench harness evaluation completed")
    return True


def generate_summary_reports(iteration_name: str):
    """Generate summary reports for each agent."""
    logger.info("=" * 80)
    logger.info("STEP 4: Generating Summary Reports")
    logger.info("=" * 80)

    cmd = [
        sys.executable,
        str(ROOT / "scripts/reports/generate_summary_reports.py"),
        "--iteration-name", iteration_name,
    ]

    logger.info(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)

    if result.returncode == 0:
        logger.info("✓ Summary reports generated")
        return True
    else:
        logger.error("Failed to generate summary reports")
        return False


def generate_aggregate_report(iteration_name: str):
    """Generate aggregate report across all agents."""
    logger.info("=" * 80)
    logger.info("STEP 5: Generating Aggregate Report")
    logger.info("=" * 80)

    cmd = [
        sys.executable,
        str(ROOT / "scripts/reports/aggregate_multi_agent_results.py"),
        "--iteration-name", iteration_name,
    ]

    logger.info(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)

    if result.returncode == 0:
        logger.info("✓ Aggregate report generated")
        return True
    else:
        logger.error("Failed to generate aggregate report")
        return False


def compute_comprehensive_metrics(iteration_name: str):
    """Compute all comprehensive metrics."""
    logger.info("=" * 80)
    logger.info("STEP 6: Computing Comprehensive Metrics")
    logger.info("=" * 80)

    # First update the comprehensive_metrics.py to use the correct paths
    aggregate_path = ROOT / f"eval_results/swebench/{iteration_name}_aggregate_report.json"
    ground_truth_path = ROOT / "data/samples/swe_bench_live_10_samples.json"
    logs_dir = ROOT / "logs/run_evaluation" / iteration_name

    # Import and run
    sys.path.insert(0, str(ROOT / "scripts/reports"))
    from comprehensive_metrics import ComprehensiveMetrics, print_comprehensive_report

    logger.info(f"Loading aggregate report from: {aggregate_path}")
    logger.info(f"Loading ground truth from: {ground_truth_path}")
    logger.info(f"Loading logs from: {logs_dir}")

    metrics_computer = ComprehensiveMetrics(aggregate_path, ground_truth_path)
    results = metrics_computer.compute_all_metrics(logs_dir)

    # Save results
    output_path = ROOT / f"eval_results/swebench/{iteration_name}_comprehensive_metrics.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"✓ Saved comprehensive metrics to: {output_path}")

    # Print report
    print("\n")
    print_comprehensive_report(results)

    return results


def main():
    """Run complete pipeline for first issue."""
    logger.info("=" * 100)
    logger.info("SINGLE ISSUE FULL PIPELINE WITH COMPREHENSIVE METRICS")
    logger.info("=" * 100)

    # Configuration
    issue_index = 0  # First issue
    iteration_name = "single_issue_test"

    try:
        # Step 0: Extract single issue
        sample_file, issue_id = extract_single_issue(issue_index, f"{iteration_name}_sample")

        # Step 1: Run enhancement pipeline
        if not run_enhancement_pipeline(sample_file, iteration_name):
            logger.error("Pipeline failed at enhancement stage")
            return 1

        # Step 2: Run solver pipeline
        if not run_solver_pipeline(iteration_name):
            logger.error("Pipeline failed at solver stage")
            return 1

        # Step 3: Run SWE-bench harness
        if not run_swebench_harness(iteration_name):
            logger.error("Pipeline failed at harness evaluation stage")
            return 1

        # Step 4: Generate summary reports
        if not generate_summary_reports(iteration_name):
            logger.warning("Warning: Summary report generation had issues")

        # Step 5: Generate aggregate report
        if not generate_aggregate_report(iteration_name):
            logger.warning("Warning: Aggregate report generation had issues")

        # Step 6: Compute comprehensive metrics
        results = compute_comprehensive_metrics(iteration_name)

        logger.info("=" * 100)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY!")
        logger.info("=" * 100)
        logger.info(f"Issue evaluated: {issue_id}")
        logger.info(f"Results saved to: eval_results/swebench/{iteration_name}_*")

        return 0

    except Exception as e:
        logger.error(f"Pipeline failed with error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
