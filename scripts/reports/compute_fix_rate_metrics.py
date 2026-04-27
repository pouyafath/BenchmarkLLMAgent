"""
Compute Fix Rate and enhanced metrics from SWE-bench harness results.

Fix Rate (from SWE-EVO paper):
- Measures partial progress on FAIL_TO_PASS tests
- Penalizes regressions (any P2P failure → Fix Rate = 0)
- More granular than binary Resolved Rate

This script computes:
1. Fix Rate per instance per agent
2. Regression Rate
3. No-Regression Rate
4. Delta Fix Rate (enhanced - baseline)
5. Statistical significance tests
"""
import argparse
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
import statistics

ROOT = Path(__file__).resolve().parent.parent.parent


def compute_fix_rate(f2p_success: int, f2p_total: int, p2p_failures: int) -> float:
    """
    Compute Fix Rate as defined in SWE-EVO paper.

    Fix Rate = (F2P_passed / F2P_total) if no P2P regressions, else 0

    Args:
        f2p_success: Number of FAIL_TO_PASS tests that now pass
        f2p_total: Total number of FAIL_TO_PASS tests
        p2p_failures: Number of PASS_TO_PASS tests that now fail (regressions)

    Returns:
        Fix rate between 0.0 and 1.0
    """
    if f2p_total == 0:
        return 0.0

    # If there are any regressions, Fix Rate = 0
    if p2p_failures > 0:
        return 0.0

    # Otherwise, compute fraction of F2P tests fixed
    return f2p_success / f2p_total


def load_aggregate_report(report_path: Path) -> dict:
    """Load aggregate report JSON."""
    with open(report_path) as f:
        return json.load(f)


def compute_all_metrics(report_path: Path, iteration_name: str):
    """Compute Fix Rate and related metrics for all agents and instances."""

    aggregate = load_aggregate_report(report_path)

    # Results structure
    results = {
        "metadata": {
            "description": f"Fix Rate and enhanced metrics for {iteration_name}",
            "formula": "Fix_Rate = (F2P_passed / F2P_total) if P2P_failures == 0 else 0",
            "source": "SWE-EVO: Benchmarking Coding Agents (arXiv:2512.18470)"
        },
        "per_agent_summary": {},
        "per_instance_metrics": {},
        "delta_metrics": {},
        "statistical_analysis": {}
    }

    # Extract metrics for each agent-instance pair
    agent_fix_rates = defaultdict(list)
    agent_regression_rates = defaultdict(list)
    agent_no_regression_counts = defaultdict(lambda: {"total": 0, "no_regression": 0})

    instance_metrics = defaultdict(dict)

    for key, metrics in aggregate.get("test_metrics", {}).items():
        agent, instance = key.split("|")

        f2p_success = metrics["f2p_success"]
        f2p_failure = metrics["f2p_failure"]
        f2p_total = f2p_success + f2p_failure

        p2p_success = metrics["p2p_success"]
        p2p_failure = metrics["p2p_failure"]
        p2p_total = p2p_success + p2p_failure

        # Compute Fix Rate
        fix_rate = compute_fix_rate(f2p_success, f2p_total, p2p_failure)

        # Compute Regression Rate
        regression_rate = p2p_failure / p2p_total if p2p_total > 0 else 0.0

        # Track no-regression instances
        agent_no_regression_counts[agent]["total"] += 1
        if p2p_failure == 0:
            agent_no_regression_counts[agent]["no_regression"] += 1

        # Store metrics
        instance_metrics[instance][agent] = {
            "fix_rate": fix_rate,
            "f2p_success": f2p_success,
            "f2p_total": f2p_total,
            "regression_rate": regression_rate,
            "p2p_failures": p2p_failure,
            "p2p_total": p2p_total,
            "resolved": (f2p_success == f2p_total and f2p_total > 0 and p2p_failure == 0)
        }

        agent_fix_rates[agent].append(fix_rate)
        agent_regression_rates[agent].append(regression_rate)

    # Compute per-agent summary statistics
    for agent in sorted(agent_fix_rates.keys()):
        fix_rates = agent_fix_rates[agent]
        regression_rates = agent_regression_rates[agent]
        no_reg = agent_no_regression_counts[agent]

        results["per_agent_summary"][agent] = {
            "mean_fix_rate": statistics.mean(fix_rates),
            "median_fix_rate": statistics.median(fix_rates),
            "max_fix_rate": max(fix_rates),
            "instances_with_nonzero_fix_rate": sum(1 for fr in fix_rates if fr > 0),
            "total_instances": len(fix_rates),
            "mean_regression_rate": statistics.mean(regression_rates),
            "no_regression_rate": no_reg["no_regression"] / no_reg["total"] if no_reg["total"] > 0 else 0.0,
            "instances_no_regression": no_reg["no_regression"],
            "instances_total": no_reg["total"]
        }

    # Store per-instance metrics
    results["per_instance_metrics"] = dict(instance_metrics)

    # Compute Delta Fix Rate (enhanced - baseline)
    baseline_agent = "baseline_no_enhancement"
    enhanced_agents = [a for a in agent_fix_rates.keys() if a != baseline_agent]

    delta_fix_rates = defaultdict(list)

    for instance, agents_data in instance_metrics.items():
        baseline_fix_rate = agents_data.get(baseline_agent, {}).get("fix_rate", 0.0)

        for enhanced_agent in enhanced_agents:
            if enhanced_agent in agents_data:
                enhanced_fix_rate = agents_data[enhanced_agent]["fix_rate"]
                delta = enhanced_fix_rate - baseline_fix_rate
                delta_fix_rates[enhanced_agent].append({
                    "instance": instance,
                    "baseline_fix_rate": baseline_fix_rate,
                    "enhanced_fix_rate": enhanced_fix_rate,
                    "delta": delta
                })

    # Compute delta summary statistics
    for agent, deltas in delta_fix_rates.items():
        delta_values = [d["delta"] for d in deltas]

        results["delta_metrics"][agent] = {
            "mean_delta_fix_rate": statistics.mean(delta_values),
            "median_delta_fix_rate": statistics.median(delta_values),
            "positive_deltas": sum(1 for d in delta_values if d > 0),
            "zero_deltas": sum(1 for d in delta_values if d == 0),
            "negative_deltas": sum(1 for d in delta_values if d < 0),
            "max_improvement": max(delta_values),
            "max_degradation": min(delta_values),
            "per_instance": deltas
        }

    # Compute statistical significance (Wilcoxon signed-rank test would go here)
    # For now, just provide summary
    if baseline_agent in results["per_agent_summary"]:
        baseline_mean_fix = results["per_agent_summary"][baseline_agent]["mean_fix_rate"]

        results["statistical_analysis"]["baseline_mean_fix_rate"] = baseline_mean_fix
        results["statistical_analysis"]["enhanced_agents_comparison"] = {}

        for agent in enhanced_agents:
            if agent in results["per_agent_summary"]:
                enhanced_mean_fix = results["per_agent_summary"][agent]["mean_fix_rate"]
                delta = enhanced_mean_fix - baseline_mean_fix
                lift = (enhanced_mean_fix / baseline_mean_fix - 1) * 100 if baseline_mean_fix > 0 else float('inf')

                results["statistical_analysis"]["enhanced_agents_comparison"][agent] = {
                    "mean_fix_rate": enhanced_mean_fix,
                    "absolute_improvement": delta,
                    "relative_lift_percent": lift,
                    "better_than_baseline": enhanced_mean_fix > baseline_mean_fix
                }

    return results


def print_report(results: dict):
    """Print a human-readable report."""
    print("=" * 100)
    print("FIX RATE METRICS REPORT (SWE-EVO)")
    print("=" * 100)

    print("\n## Formula")
    print(f"  {results['metadata']['formula']}")
    print(f"  Source: {results['metadata']['source']}")

    print("\n## Per-Agent Summary")
    print("-" * 100)
    print(f"{'Agent':<35} {'Mean Fix':>10} {'Max Fix':>10} {'#Non-0':>8} {'#Total':>8} {'No-Reg%':>10}")
    print("-" * 100)

    for agent, metrics in sorted(results["per_agent_summary"].items()):
        print(f"{agent:<35} "
              f"{metrics['mean_fix_rate']:>10.3f} "
              f"{metrics['max_fix_rate']:>10.3f} "
              f"{metrics['instances_with_nonzero_fix_rate']:>8} "
              f"{metrics['total_instances']:>8} "
              f"{metrics['no_regression_rate']*100:>9.1f}%")

    print("\n## Delta Fix Rate (Enhanced - Baseline)")
    print("-" * 100)
    print(f"{'Agent':<35} {'Mean Δ':>10} {'Median Δ':>10} {'Max ↑':>10} {'Max ↓':>10} {'+/=/−':>10}")
    print("-" * 100)

    for agent, metrics in sorted(results["delta_metrics"].items()):
        pos_neg = f"{metrics['positive_deltas']}/{metrics['zero_deltas']}/{metrics['negative_deltas']}"
        print(f"{agent:<35} "
              f"{metrics['mean_delta_fix_rate']:>10.3f} "
              f"{metrics['median_delta_fix_rate']:>10.3f} "
              f"{metrics['max_improvement']:>10.3f} "
              f"{metrics['max_degradation']:>10.3f} "
              f"{pos_neg:>10}")

    print("\n## Statistical Analysis")
    print("-" * 100)
    if "baseline_mean_fix_rate" in results["statistical_analysis"]:
        baseline_fix = results["statistical_analysis"]["baseline_mean_fix_rate"]
        print(f"Baseline Mean Fix Rate: {baseline_fix:.3f}")
        print()
        print(f"{'Agent':<35} {'Mean Fix':>10} {'Abs Δ':>10} {'Rel Lift%':>12} {'Better?':>10}")
        print("-" * 100)

        for agent, comp in sorted(results["statistical_analysis"]["enhanced_agents_comparison"].items()):
            better = "✓" if comp["better_than_baseline"] else "✗"
            lift_str = f"{comp['relative_lift_percent']:+.1f}%" if comp['relative_lift_percent'] != float('inf') else "∞"
            print(f"{agent:<35} "
                  f"{comp['mean_fix_rate']:>10.3f} "
                  f"{comp['absolute_improvement']:>+10.3f} "
                  f"{lift_str:>12} "
                  f"{better:>10}")

    print("\n## Top Instances by Fix Rate")
    print("-" * 100)

    # Find instances with highest fix rates
    instance_best_fix = {}
    for instance, agents_data in results["per_instance_metrics"].items():
        max_fix = max((data["fix_rate"] for data in agents_data.values()), default=0.0)
        instance_best_fix[instance] = max_fix

    top_instances = sorted(instance_best_fix.items(), key=lambda x: x[1], reverse=True)[:5]

    for instance, max_fix in top_instances:
        print(f"{instance}: {max_fix:.3f}")
        agents_with_fix = [agent for agent, data in results["per_instance_metrics"][instance].items()
                          if data["fix_rate"] > 0]
        if agents_with_fix:
            print(f"  Fixed by: {', '.join(agents_with_fix)}")

    print("\n" + "=" * 100)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--aggregate-report",
        type=Path,
        default=ROOT / "eval_results/swebench/iteration1_v3_aggregate_report.json",
        help="Path to aggregate report JSON",
    )
    parser.add_argument(
        "--iteration-name",
        type=str,
        default="iteration1_v3",
        help="Iteration name for metadata",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "eval_results/swebench/iteration1_v3_fix_rate_metrics.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    print("Computing Fix Rate metrics...")
    results = compute_all_metrics(args.aggregate_report, args.iteration_name)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, indent=2, fp=f)

    print(f"✓ Saved detailed metrics to: {args.output}")
    print()
    print_report(results)

    return results


if __name__ == "__main__":
    main()
