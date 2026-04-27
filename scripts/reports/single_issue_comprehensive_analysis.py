"""
Comprehensive metrics analysis for a single issue.
Shows all 9 metric categories for one specific issue.
"""
import json
import logging
from pathlib import Path
from difflib import SequenceMatcher
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent


def extract_files_from_patch(patch: str) -> set:
    """Extract modified file paths from patch."""
    files = set()
    for line in patch.splitlines():
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            filepath = line.split(" ", 1)[1]
            if filepath.startswith("a/") or filepath.startswith("b/"):
                filepath = filepath[2:]
            if filepath != "/dev/null":
                files.add(filepath)
    return files


def compute_file_overlap(agent_patch: str, gt_patch: str) -> float:
    """Compute Jaccard similarity of modified files."""
    agent_files = extract_files_from_patch(agent_patch)
    gt_files = extract_files_from_patch(gt_patch)

    if not agent_files and not gt_files:
        return 1.0
    if not agent_files or not gt_files:
        return 0.0

    intersection = agent_files & gt_files
    union = agent_files | gt_files
    return len(intersection) / len(union)


def compute_content_similarity(agent_patch: str, gt_patch: str) -> float:
    """Compute content similarity using SequenceMatcher."""
    if not agent_patch.strip() and not gt_patch.strip():
        return 1.0
    if not agent_patch.strip() or not gt_patch.strip():
        return 0.0

    matcher = SequenceMatcher(None, agent_patch, gt_patch)
    return matcher.ratio()


def analyze_single_issue(issue_id: str, iteration_name: str = "iteration1_v3"):
    """Comprehensive analysis of all metrics for a single issue."""

    # Load aggregate report
    aggregate_path = ROOT / f"eval_results/swebench/{iteration_name}_aggregate_report.json"
    with open(aggregate_path) as f:
        aggregate = json.load(f)

    # Load ground truth
    samples_path = ROOT / "data/samples/swe_bench_live_10_samples.json"
    with open(samples_path) as f:
        samples_data = json.load(f)

    # Find the issue in ground truth
    gt_issue = None
    for issue in samples_data["issues"]:
        if issue["issue_id"] == issue_id:
            gt_issue = issue
            break

    if not gt_issue:
        logger.error(f"Issue {issue_id} not found in samples")
        return

    logger.info("=" * 120)
    logger.info(f"COMPREHENSIVE ANALYSIS: {issue_id}")
    logger.info("=" * 120)
    logger.info(f"Repository: {gt_issue['repo_name']}")
    logger.info(f"Title: {gt_issue['title']}")
    logger.info(f"PR Number: {gt_issue['pr_number']}")
    logger.info(f"Files Changed: {', '.join(f['filename'] for f in gt_issue.get('pr_files', []))}")
    logger.info("")

    # Collect results for this issue across all agents
    results = {}
    logs_dir = ROOT / "logs/run_evaluation" / iteration_name

    for key, test_data in aggregate.get("test_metrics", {}).items():
        agent, inst_id = key.split("|")
        if inst_id != issue_id:
            continue

        # Load report.json
        report_path = logs_dir / agent / issue_id / "report.json"
        report_data = None
        if report_path.exists():
            try:
                with open(report_path) as f:
                    report_data = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load {report_path}: {e}")

        # Extract all metrics
        f2p_success = test_data["f2p_success"]
        f2p_failure = test_data["f2p_failure"]
        f2p_total = f2p_success + f2p_failure

        p2p_success = test_data["p2p_success"]
        p2p_failure = test_data["p2p_failure"]
        p2p_total = p2p_success + p2p_failure

        # 1. Fix Rate
        fix_rate = 0.0
        if f2p_total > 0 and p2p_failure == 0:
            fix_rate = f2p_success / f2p_total

        # 2. F2P Progress Rate
        f2p_progress = f2p_success / f2p_total if f2p_total > 0 else 0.0

        # 3. Regression Rate
        regression_rate = p2p_failure / p2p_total if p2p_total > 0 else 0.0

        # 4. Patch Apply Rate (from aggregate)
        patch_status = aggregate["patch_apply_matrix"].get(issue_id, {}).get(agent, "unknown")
        patch_applied = (patch_status == "applied")

        # 5-9. Alignment, Efficiency, Trajectory
        agent_patch = ""
        file_overlap = 0.0
        content_sim = 0.0
        tokens = 0
        cost = 0.0
        wall_clock_ms = 0.0
        turns = 0
        tool_calls = 0

        # Load patch from patch.diff file
        patch_file = logs_dir / agent / issue_id / "patch.diff"
        if patch_file.exists():
            try:
                with open(patch_file) as f:
                    agent_patch = f.read()
            except Exception as e:
                logger.warning(f"Could not read {patch_file}: {e}")

        gt_patch = gt_issue.get("ground_truth_patch", "")

        if agent_patch and gt_patch:
            # 6. File Overlap
            file_overlap = compute_file_overlap(agent_patch, gt_patch)

            # 7. Content Similarity
            content_sim = compute_content_similarity(agent_patch, gt_patch)

            # 8. Efficiency
            info = report_data.get("info", {})
            tokens = info.get("total_tokens", 0)
            wall_clock_ms = info.get("total_time_ms", 0.0)

            # Estimate cost
            model = info.get("model_name", "gpt-4o")
            cost_rates = {
                "gpt-4o": (0.0025, 0.01),
                "claude-3-5-sonnet": (0.003, 0.015),
                "claude-sonnet-4": (0.003, 0.015),
            }
            input_rate, output_rate = cost_rates.get(model, (0.005, 0.015))
            cost = (input_rate * tokens * 0.6 + output_rate * tokens * 0.4) / 1000

            # 9. Trajectory
            turns = info.get("total_turns", 0)
            tool_calls = info.get("total_tool_calls", 0)

        results[agent] = {
            # Core metrics
            "fix_rate": fix_rate,
            "f2p_progress_rate": f2p_progress,
            "regression_rate": regression_rate,
            "no_regression": (p2p_failure == 0),
            "patch_applied": patch_applied,

            # Test details
            "f2p_success": f2p_success,
            "f2p_total": f2p_total,
            "p2p_failures": p2p_failure,
            "p2p_total": p2p_total,

            # Alignment
            "file_overlap": file_overlap,
            "content_similarity": content_sim,

            # Efficiency
            "tokens": tokens,
            "cost_usd": cost,
            "wall_clock_ms": wall_clock_ms,

            # Trajectory
            "turns": turns,
            "tool_calls": tool_calls,

            # Resolution
            "resolved": (f2p_success == f2p_total and f2p_total > 0 and p2p_failure == 0)
        }

    # Print comprehensive report
    print("\n" + "=" * 120)
    print("METRIC 1: FIX RATE (SWE-EVO)")
    print("=" * 120)
    print(f"{'Agent':<40} {'Fix Rate':>12} {'F2P Success':>12} {'F2P Total':>12} {'P2P Failures':>15}")
    print("-" * 120)
    for agent in sorted(results.keys()):
        m = results[agent]
        print(f"{agent:<40} {m['fix_rate']:>12.3f} {m['f2p_success']:>12} {m['f2p_total']:>12} {m['p2p_failures']:>15}")

    print("\n" + "=" * 120)
    print("METRIC 2: F2P PROGRESS RATE (without regression penalty)")
    print("=" * 120)
    print(f"{'Agent':<40} {'F2P Progress':>15} {'F2P Passed':>12} {'F2P Total':>12}")
    print("-" * 120)
    for agent in sorted(results.keys()):
        m = results[agent]
        print(f"{agent:<40} {m['f2p_progress_rate']:>15.3f} {m['f2p_success']:>12} {m['f2p_total']:>12}")

    print("\n" + "=" * 120)
    print("METRIC 3: REGRESSION RATE")
    print("=" * 120)
    print(f"{'Agent':<40} {'Regression Rate':>18} {'P2P Failures':>15} {'P2P Total':>12} {'No Regress':>12}")
    print("-" * 120)
    for agent in sorted(results.keys()):
        m = results[agent]
        no_reg_sym = "✓" if m['no_regression'] else "✗"
        print(f"{agent:<40} {m['regression_rate']:>18.3f} {m['p2p_failures']:>15} {m['p2p_total']:>12} {no_reg_sym:>12}")

    print("\n" + "=" * 120)
    print("METRIC 4: PATCH APPLY RATE")
    print("=" * 120)
    print(f"{'Agent':<40} {'Patch Applied':>15}")
    print("-" * 120)
    for agent in sorted(results.keys()):
        m = results[agent]
        status = "✓ Yes" if m['patch_applied'] else "✗ No"
        print(f"{agent:<40} {status:>15}")

    print("\n" + "=" * 120)
    print("METRIC 5 & 6: FILE OVERLAP & CONTENT SIMILARITY")
    print("=" * 120)
    print(f"{'Agent':<40} {'File Overlap':>15} {'Content Sim':>15}")
    print("-" * 120)
    for agent in sorted(results.keys()):
        m = results[agent]
        print(f"{agent:<40} {m['file_overlap']:>15.3f} {m['content_similarity']:>15.3f}")

    print("\n" + "=" * 120)
    print("METRIC 7: EFFICIENCY (Tokens, Cost, Time)")
    print("=" * 120)
    print(f"{'Agent':<40} {'Tokens':>12} {'Cost (USD)':>15} {'Time (s)':>12}")
    print("-" * 120)
    for agent in sorted(results.keys()):
        m = results[agent]
        time_s = m['wall_clock_ms'] / 1000 if m['wall_clock_ms'] > 0 else 0.0
        print(f"{agent:<40} {m['tokens']:>12} ${m['cost_usd']:>14.4f} {time_s:>12.1f}")

    print("\n" + "=" * 120)
    print("METRIC 8: TRAJECTORY (Turns, Tool Calls)")
    print("=" * 120)
    print(f"{'Agent':<40} {'Turns':>12} {'Tool Calls':>15}")
    print("-" * 120)
    for agent in sorted(results.keys()):
        m = results[agent]
        print(f"{agent:<40} {m['turns']:>12} {m['tool_calls']:>15}")

    print("\n" + "=" * 120)
    print("METRIC 9: RESOLUTION (Binary Pass/Fail)")
    print("=" * 120)
    print(f"{'Agent':<40} {'Resolved':>12}")
    print("-" * 120)
    for agent in sorted(results.keys()):
        m = results[agent]
        status = "✓ RESOLVED" if m['resolved'] else "✗ UNRESOLVED"
        print(f"{agent:<40} {status:>12}")

    # Baseline comparison
    baseline = "baseline_no_enhancement"
    if baseline in results:
        print("\n" + "=" * 120)
        print("BASELINE COMPARISON (Enhanced - Baseline)")
        print("=" * 120)
        print(f"{'Agent':<40} {'ΔFix':>10} {'ΔF2P Prog':>12} {'ΔReg':>10} {'ΔFile':>10} {'ΔCont':>10}")
        print("-" * 120)

        base = results[baseline]
        for agent in sorted(results.keys()):
            if agent == baseline:
                continue
            m = results[agent]
            delta_fix = m['fix_rate'] - base['fix_rate']
            delta_f2p = m['f2p_progress_rate'] - base['f2p_progress_rate']
            delta_reg = m['regression_rate'] - base['regression_rate']
            delta_file = m['file_overlap'] - base['file_overlap']
            delta_cont = m['content_similarity'] - base['content_similarity']

            print(f"{agent:<40} {delta_fix:>+10.3f} {delta_f2p:>+12.3f} {delta_reg:>+10.3f} {delta_file:>+10.3f} {delta_cont:>+10.3f}")

    # Summary
    print("\n" + "=" * 120)
    print("KEY INSIGHTS FOR THIS ISSUE")
    print("=" * 120)

    # Find best performing agent
    best_f2p = max(results.items(), key=lambda x: x[1]['f2p_progress_rate'])
    best_content = max(results.items(), key=lambda x: x[1]['content_similarity'])
    min_regress = min(results.items(), key=lambda x: x[1]['regression_rate'])

    print(f"1. Best F2P Progress: {best_f2p[0]} ({best_f2p[1]['f2p_progress_rate']:.1%})")
    print(f"2. Best Content Similarity: {best_content[0]} ({best_content[1]['content_similarity']:.3f})")
    print(f"3. Lowest Regression: {min_regress[0]} ({min_regress[1]['regression_rate']:.1%})")

    resolved_agents = [a for a, m in results.items() if m['resolved']]
    if resolved_agents:
        print(f"4. Resolved by: {', '.join(resolved_agents)}")
    else:
        print(f"4. ⚠ Issue NOT resolved by any agent")

    print("=" * 120)

    # Save detailed results
    output_path = ROOT / f"eval_results/swebench/{issue_id}_comprehensive_analysis.json"
    with open(output_path, "w") as f:
        json.dump({
            "issue_id": issue_id,
            "issue_title": gt_issue['title'],
            "repo": gt_issue['repo_name'],
            "metrics_by_agent": results
        }, f, indent=2)

    logger.info(f"\n✓ Saved detailed analysis to: {output_path}")


def main():
    """Run single issue comprehensive analysis."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-id", type=str,
                        default="instructlab__instructlab-3135",
                        help="Issue ID to analyze")
    parser.add_argument("--iteration", type=str,
                        default="iteration1_v3",
                        help="Iteration name")
    args = parser.parse_args()

    analyze_single_issue(args.issue_id, args.iteration)


if __name__ == "__main__":
    main()
