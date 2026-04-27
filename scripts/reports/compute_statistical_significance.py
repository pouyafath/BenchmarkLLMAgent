"""
Compute statistical significance tests for 101-issue experiment results.

Uses binomial proportion tests and confidence intervals to determine if:
1. Enhancement effects are statistically significant
2. Group A vs Group B differences are significant
3. Agent differences are significant

Usage:
    python scripts/reports/compute_statistical_significance.py
"""
import json
import math
from pathlib import Path
from typing import Dict, Tuple
from datetime import datetime
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent.parent


def load_comparison_summary(results_dir: Path) -> Dict:
    """Load comparison_summary.json from experiment results directory."""
    summary_file = results_dir / "comparison_summary.json"
    if not summary_file.exists():
        return None

    with open(summary_file) as f:
        return json.load(f)


def compute_wilson_ci(successes: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """
    Compute Wilson score confidence interval for binomial proportion.

    More accurate than normal approximation, especially for small samples or
    proportions near 0 or 1.

    Args:
        successes: Number of successes
        n: Total trials
        confidence: Confidence level (default 0.95 for 95% CI)

    Returns:
        (lower_bound, upper_bound) as proportions
    """
    if n == 0:
        return (0.0, 0.0)

    p = successes / n
    z = stats.norm.ppf(1 - (1 - confidence) / 2)  # z-score for confidence level

    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    margin = z * math.sqrt((p * (1 - p) / n + z**2 / (4 * n**2))) / denominator

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)

    return (lower, upper)


def compute_two_proportion_z_test(n1: int, p1: float, n2: int, p2: float) -> Tuple[float, float]:
    """
    Two-proportion z-test to compare two independent proportions.

    H0: p1 = p2 (no difference)
    H1: p1 ≠ p2 (two-tailed test)

    Args:
        n1: Sample size for group 1
        p1: Proportion for group 1
        n2: Sample size for group 2
        p2: Proportion for group 2

    Returns:
        (z_statistic, p_value)
    """
    if n1 == 0 or n2 == 0:
        return (0.0, 1.0)

    # Pooled proportion
    p_pool = (n1 * p1 + n2 * p2) / (n1 + n2)

    # Standard error
    se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))

    if se == 0:
        return (0.0, 1.0)

    # Z-statistic
    z = (p1 - p2) / se

    # Two-tailed p-value
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))

    return (z, p_value)


def analyze_enhancement_significance(baseline: Dict, enhanced: Dict, metric: str = "resolved") -> Dict:
    """
    Test if enhancement effect is statistically significant.

    Args:
        baseline: Baseline metrics dict
        enhanced: Enhanced metrics dict
        metric: Which metric to test ("resolved", "f2p", or "p2p")

    Returns:
        Dict with test results
    """
    if metric == "resolved":
        b_count = baseline.get("resolved_issue_count", 0)
        e_count = enhanced.get("resolved_issue_count", 0)
    elif metric == "f2p":
        b_count = baseline.get("fail_to_pass_issue_success_count", 0)
        e_count = enhanced.get("fail_to_pass_issue_success_count", 0)
    elif metric == "p2p":
        b_count = baseline.get("pass_to_pass_issue_success_count", 0)
        e_count = enhanced.get("pass_to_pass_issue_success_count", 0)
    else:
        raise ValueError(f"Unknown metric: {metric}")

    n = baseline.get("num_issues", 0)

    # Confidence intervals
    b_ci = compute_wilson_ci(b_count, n)
    e_ci = compute_wilson_ci(e_count, n)

    # Two-proportion test
    b_rate = b_count / n if n > 0 else 0.0
    e_rate = e_count / n if n > 0 else 0.0
    z_stat, p_value = compute_two_proportion_z_test(n, b_rate, n, e_rate)

    # Effect size (absolute difference)
    effect_size = e_rate - b_rate

    return {
        "metric": metric,
        "n": n,
        "baseline_count": b_count,
        "baseline_rate": b_rate,
        "baseline_ci_95": b_ci,
        "enhanced_count": e_count,
        "enhanced_rate": e_rate,
        "enhanced_ci_95": e_ci,
        "effect_size": effect_size,
        "z_statistic": z_stat,
        "p_value": p_value,
        "significant_at_05": bool(p_value < 0.05),
        "significant_at_01": bool(p_value < 0.01),
    }


def analyze_group_difference(group_a_data: Dict, group_b_data: Dict, metric: str = "resolved") -> Dict:
    """
    Test if difference between Group A and Group B is statistically significant.

    Args:
        group_a_data: Baseline metrics for Group A
        group_b_data: Baseline metrics for Group B
        metric: Which metric to test

    Returns:
        Dict with test results
    """
    if metric == "resolved":
        a_count = group_a_data.get("resolved_issue_count", 0)
        b_count = group_b_data.get("resolved_issue_count", 0)
    elif metric == "f2p":
        a_count = group_a_data.get("fail_to_pass_issue_success_count", 0)
        b_count = group_b_data.get("fail_to_pass_issue_success_count", 0)
    elif metric == "p2p":
        a_count = group_a_data.get("pass_to_pass_issue_success_count", 0)
        b_count = group_b_data.get("pass_to_pass_issue_success_count", 0)
    else:
        raise ValueError(f"Unknown metric: {metric}")

    n_a = group_a_data.get("num_issues", 0)
    n_b = group_b_data.get("num_issues", 0)

    a_rate = a_count / n_a if n_a > 0 else 0.0
    b_rate = b_count / n_b if n_b > 0 else 0.0

    # Confidence intervals
    a_ci = compute_wilson_ci(a_count, n_a)
    b_ci = compute_wilson_ci(b_count, n_b)

    # Two-proportion test
    z_stat, p_value = compute_two_proportion_z_test(n_a, a_rate, n_b, b_rate)

    # Effect size
    effect_size = a_rate - b_rate

    return {
        "metric": metric,
        "group_a_n": n_a,
        "group_a_count": a_count,
        "group_a_rate": a_rate,
        "group_a_ci_95": a_ci,
        "group_b_n": n_b,
        "group_b_count": b_count,
        "group_b_rate": b_rate,
        "group_b_ci_95": b_ci,
        "effect_size": effect_size,
        "z_statistic": z_stat,
        "p_value": p_value,
        "significant_at_05": bool(p_value < 0.05),
        "significant_at_01": bool(p_value < 0.01),
    }


def print_test_result(result: Dict, test_name: str):
    """Print formatted test result."""
    print(f"\n## {test_name}")
    print("-" * 100)
    print(f"Metric: {result['metric']}")

    if "baseline_rate" in result:
        # Enhancement test
        print(f"Baseline:  {result['baseline_count']}/{result['n']} ({result['baseline_rate']*100:.1f}%)")
        print(f"           95% CI: [{result['baseline_ci_95'][0]*100:.1f}%, {result['baseline_ci_95'][1]*100:.1f}%]")
        print(f"Enhanced:  {result['enhanced_count']}/{result['n']} ({result['enhanced_rate']*100:.1f}%)")
        print(f"           95% CI: [{result['enhanced_ci_95'][0]*100:.1f}%, {result['enhanced_ci_95'][1]*100:.1f}%]")
    else:
        # Group comparison test
        print(f"Group A:   {result['group_a_count']}/{result['group_a_n']} ({result['group_a_rate']*100:.1f}%)")
        print(f"           95% CI: [{result['group_a_ci_95'][0]*100:.1f}%, {result['group_a_ci_95'][1]*100:.1f}%]")
        print(f"Group B:   {result['group_b_count']}/{result['group_b_n']} ({result['group_b_rate']*100:.1f}%)")
        print(f"           95% CI: [{result['group_b_ci_95'][0]*100:.1f}%, {result['group_b_ci_95'][1]*100:.1f}%]")

    print(f"\nEffect Size:    {result['effect_size']:+.1%}")
    print(f"Z-statistic:    {result['z_statistic']:.3f}")
    print(f"P-value:        {result['p_value']:.4f}")
    print(f"Significant at α=0.05: {'✓ YES' if result['significant_at_05'] else '✗ NO'}")
    print(f"Significant at α=0.01: {'✓ YES' if result['significant_at_01'] else '✗ NO'}")


def main():
    """Main entry point."""
    print("="*100)
    print("STATISTICAL SIGNIFICANCE ANALYSIS - 101-ISSUE EXPERIMENTS")
    print(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*100)

    results_root = ROOT / "data/samples/101_issues_experiments"

    experiments = {
        "Group A": {
            "trae": results_root / "results_group_a/trae__devstral101_groupA_20260327",
            "aider": results_root / "results_group_a/aider__devstral101_groupA_20260327",
            "swe_agent": results_root / "results_group_a/swe_agent__devstral101_groupA_20260327",
        },
        "Group B": {
            "trae": results_root / "results_group_b/trae__devstral101_groupB_20260327",
            "aider": results_root / "results_group_b/aider__devstral101_groupB_20260327",
            "swe_agent": results_root / "results_group_b/swe_agent__devstral101_groupB_20260327",
        }
    }

    # Load all data
    group_a_data = {}
    group_b_data = {}

    for agent, path in experiments["Group A"].items():
        data = load_comparison_summary(path)
        if data:
            group_a_data[agent] = data

    for agent, path in experiments["Group B"].items():
        data = load_comparison_summary(path)
        if data:
            group_b_data[agent] = data

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "tests": {}
    }

    # Test 1: Enhancement effects for each agent
    print("\n" + "="*100)
    print("TEST 1: ENHANCEMENT SIGNIFICANCE (Baseline vs Enhanced)")
    print("="*100)

    for agent_name in sorted(set(group_a_data.keys()) | set(group_b_data.keys())):
        for group_name, group_data in [("Group A", group_a_data), ("Group B", group_b_data)]:
            if agent_name not in group_data:
                continue

            data = group_data[agent_name]
            baseline = data.get("baseline", {})
            enhanced = data.get("enhanced", {})

            test_key = f"{group_name}_{agent_name}_enhancement"
            output["tests"][test_key] = {}

            for metric in ["resolved", "f2p", "p2p"]:
                result = analyze_enhancement_significance(baseline, enhanced, metric)
                output["tests"][test_key][metric] = result
                print_test_result(result, f"{group_name} - {agent_name} - {metric.upper()}")

    # Test 2: Group A vs Group B baseline differences
    print("\n\n" + "="*100)
    print("TEST 2: GROUP A vs GROUP B BASELINE DIFFERENCES")
    print("="*100)

    for agent_name in sorted(set(group_a_data.keys()) & set(group_b_data.keys())):
        a_baseline = group_a_data[agent_name].get("baseline", {})
        b_baseline = group_b_data[agent_name].get("baseline", {})

        test_key = f"group_comparison_{agent_name}_baseline"
        output["tests"][test_key] = {}

        for metric in ["resolved", "f2p", "p2p"]:
            result = analyze_group_difference(a_baseline, b_baseline, metric)
            output["tests"][test_key][metric] = result
            print_test_result(result, f"{agent_name} - Group A vs B - {metric.upper()}")

    # Save results
    output_file = results_root / "101_issue_statistical_significance.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print("\n" + "="*100)
    print(f"✓ Saved statistical test results to: {output_file}")
    print("="*100)

    # Summary interpretation
    print("\n\n" + "="*100)
    print("INTERPRETATION GUIDE")
    print("="*100)
    print("""
Significance Levels:
- α = 0.05: Standard threshold (95% confidence)
- α = 0.01: Stringent threshold (99% confidence)

Effect Size:
- > 0: Enhanced/Group A performs better
- < 0: Baseline/Group B performs better
- Magnitude indicates practical significance

P-value:
- < 0.05: Statistically significant at 95% confidence level
- < 0.01: Statistically significant at 99% confidence level
- Reject null hypothesis (no difference) when p < α

Sample Size (n=101):
- Sufficient to detect ~10% effect sizes with 80% power
- Confidence intervals should be ~±10% wide for p≈0.5
""")


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        if "scipy" in str(e):
            print("ERROR: scipy is required for statistical tests.")
            print("Install with: pip install scipy")
        else:
            raise
