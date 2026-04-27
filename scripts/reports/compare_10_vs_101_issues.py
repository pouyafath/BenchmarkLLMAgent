"""
Compare 10-issue pilot results with 101-issue expansion results.

Analyzes how baseline resolution rates, enhancement effects, and variance
change when scaling from 10 to 101 issues.

Usage:
    python scripts/reports/compare_10_vs_101_issues.py
"""
import json
from pathlib import Path
from typing import Dict
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent.parent


def load_comparison_summary(results_dir: Path) -> Dict:
    """Load comparison_summary.json from experiment results directory."""
    summary_file = results_dir / "comparison_summary.json"
    if not summary_file.exists():
        return None

    with open(summary_file) as f:
        return json.load(f)


def extract_summary_metrics(data: Dict, section: str) -> Dict:
    """Extract key metrics from baseline or enhanced section."""
    sec = data.get(section, {})
    return {
        "num_issues": sec.get("num_issues", 0),
        "resolved_count": sec.get("resolved_issue_count", 0),
        "resolved_rate": sec.get("resolved_issue_rate", 0.0),
        "f2p_count": sec.get("fail_to_pass_issue_success_count", 0),
        "f2p_rate": sec.get("fail_to_pass_issue_success_rate", 0.0),
        "p2p_count": sec.get("pass_to_pass_issue_success_count", 0),
        "p2p_rate": sec.get("pass_to_pass_issue_success_rate", 0.0),
    }


def compute_variance_reduction(small_n: int, large_n: int, p: float) -> Dict:
    """
    Compute theoretical variance reduction from increasing sample size.

    For binomial proportion, variance = p(1-p)/n
    Standard error = sqrt(p(1-p)/n)

    Args:
        small_n: Small sample size (10)
        large_n: Large sample size (101)
        p: Estimated proportion (e.g., baseline resolve rate)

    Returns:
        Dict with variance metrics
    """
    if small_n == 0 or large_n == 0 or p < 0 or p > 1:
        return {
            "small_n_variance": 0.0,
            "large_n_variance": 0.0,
            "variance_reduction_factor": 0.0,
            "small_n_se": 0.0,
            "large_n_se": 0.0,
            "se_reduction_factor": 0.0,
        }

    var_small = p * (1 - p) / small_n
    var_large = p * (1 - p) / large_n
    var_reduction = var_small / var_large if var_large > 0 else 0.0

    se_small = var_small ** 0.5
    se_large = var_large ** 0.5
    se_reduction = se_small / se_large if se_large > 0 else 0.0

    return {
        "small_n_variance": var_small,
        "large_n_variance": var_large,
        "variance_reduction_factor": var_reduction,
        "small_n_se": se_small,
        "large_n_se": se_large,
        "se_reduction_factor": se_reduction,
    }


def print_comparison_table(agent: str, group_name: str, pilot_10: Dict, expansion_101: Dict):
    """Print detailed 10 vs 101 comparison table."""
    print(f"\n{'='*100}")
    print(f"{agent.upper()} - {group_name} - 10-Issue Pilot vs 101-Issue Expansion")
    print(f"{'='*100}")

    if not pilot_10 or not expansion_101:
        print("⚠ Insufficient data for comparison")
        return

    p10_baseline = extract_summary_metrics(pilot_10, "baseline")
    p10_enhanced = extract_summary_metrics(pilot_10, "enhanced")
    e101_baseline = extract_summary_metrics(expansion_101, "baseline")
    e101_enhanced = extract_summary_metrics(expansion_101, "enhanced")

    # Baseline comparison
    print(f"\n## BASELINE COMPARISON")
    print(f"{'Metric':<25} | {'10-Issue Pilot':<25} | {'101-Issue Expansion':<25} | {'Change':<15}")
    print("-" * 100)

    metrics = [
        ("Resolved Rate", "resolved_rate", True),
        ("F2P Success Rate", "f2p_rate", True),
        ("P2P Success Rate", "p2p_rate", True),
    ]

    for label, key, is_rate in metrics:
        p10_val = p10_baseline[key]
        e101_val = e101_baseline[key]
        change = e101_val - p10_val

        if is_rate:
            p10_str = f"{p10_val*100:.1f}%"
            e101_str = f"{e101_val*100:.1f}%"
            change_str = f"{change:+.1%}"
        else:
            p10_str = str(p10_val)
            e101_str = str(e101_val)
            change_str = f"{change:+.1f}"

        print(f"{label:<25} | {p10_str:<25} | {e101_str:<25} | {change_str:<15}")

    # Enhancement effect comparison
    print(f"\n## ENHANCEMENT EFFECT COMPARISON")
    print(f"{'Metric':<25} | {'10-Issue Δ':<25} | {'101-Issue Δ':<25} | {'Effect Δ':<15}")
    print("-" * 100)

    for label, key, is_rate in metrics:
        p10_delta = p10_enhanced[key] - p10_baseline[key]
        e101_delta = e101_enhanced[key] - e101_baseline[key]
        effect_change = e101_delta - p10_delta

        p10_delta_str = f"{p10_delta:+.1%}"
        e101_delta_str = f"{e101_delta:+.1%}"
        effect_change_str = f"{effect_change:+.1%}"

        print(f"{label:<25} | {p10_delta_str:<25} | {e101_delta_str:<25} | {effect_change_str:<15}")

    # Variance reduction analysis
    print(f"\n## STATISTICAL POWER ANALYSIS")
    print("-" * 100)

    # Use baseline resolved rate as reference proportion
    p_resolved = e101_baseline["resolved_rate"]
    var_metrics = compute_variance_reduction(10, 101, p_resolved)

    print(f"Reference proportion (101-issue baseline resolved rate): {p_resolved:.3f}")
    print(f"\nStandard Error:")
    print(f"  10-issue sample:   {var_metrics['small_n_se']:.3f} (±{var_metrics['small_n_se']*100:.1f}%)")
    print(f"  101-issue sample:  {var_metrics['large_n_se']:.3f} (±{var_metrics['large_n_se']*100:.1f}%)")
    print(f"  Reduction factor:  {var_metrics['se_reduction_factor']:.2f}x")
    print(f"\nVariance:")
    print(f"  10-issue sample:   {var_metrics['small_n_variance']:.4f}")
    print(f"  101-issue sample:  {var_metrics['large_n_variance']:.4f}")
    print(f"  Reduction factor:  {var_metrics['variance_reduction_factor']:.2f}x")

    print(f"\nInterpretation:")
    print(f"  - 101-issue sample has ~{var_metrics['se_reduction_factor']:.1f}x smaller standard error")
    print(f"  - Confidence intervals are ~{var_metrics['se_reduction_factor']:.1f}x narrower")
    print(f"  - Can detect smaller effect sizes with same statistical power")


def main():
    """Main entry point."""
    print("="*100)
    print("10-ISSUE PILOT vs 101-ISSUE EXPANSION COMPARISON")
    print(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*100)

    results_root = ROOT / "data/samples/101_issues_experiments"
    secondpaper_root = ROOT / "results/secondpaper10_baseline_vs_enhanced"
    verified10_root = ROOT / "results/verified10_baseline_vs_enhanced"

    # Map experiment directories
    pilot_experiments = {
        "Group A": {
            # The 10-issue pilot used "verified10" naming
            "trae": verified10_root / "trae__devstral_true_native_full10_trae_devstral_20260323",
            "aider": verified10_root / "aider__devstral_true_native_full10_aider_20260324",
            "swe_agent": verified10_root / "swe_agent__devstral_true_native_full10_swe_agent_20260324",
        },
        "Group B": {
            # The 10-issue pilot used "secondpaper10" naming
            "trae": secondpaper_root / "trae__devstral_true_native_p2p_only_full10_trae_devstral_w2_20260324",
            "aider": secondpaper_root / "aider__devstral_true_native_p2p_only_full10_aider_20260324",
            "swe_agent": secondpaper_root / "swe_agent__devstral_true_native_p2p_only_full10_swe_agent_20260324",
        }
    }

    expansion_experiments = {
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

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "comparisons": {}
    }

    # Compare each agent and group
    for group_name in ["Group A", "Group B"]:
        for agent_name in ["trae", "aider", "swe_agent"]:
            pilot_path = pilot_experiments[group_name][agent_name]
            expansion_path = expansion_experiments[group_name][agent_name]

            pilot_data = load_comparison_summary(pilot_path)
            expansion_data = load_comparison_summary(expansion_path)

            if pilot_data and expansion_data:
                print_comparison_table(agent_name, group_name, pilot_data, expansion_data)

                # Store structured comparison
                key = f"{group_name}_{agent_name}"
                output["comparisons"][key] = {
                    "pilot_10_baseline": extract_summary_metrics(pilot_data, "baseline"),
                    "pilot_10_enhanced": extract_summary_metrics(pilot_data, "enhanced"),
                    "expansion_101_baseline": extract_summary_metrics(expansion_data, "baseline"),
                    "expansion_101_enhanced": extract_summary_metrics(expansion_data, "enhanced"),
                }
            else:
                if not pilot_data:
                    print(f"\n⚠ Missing 10-issue pilot data: {agent_name} {group_name}")
                if not expansion_data:
                    print(f"\n⚠ Missing 101-issue expansion data: {agent_name} {group_name}")

    # Overall summary
    print(f"\n\n{'='*100}")
    print("OVERALL SUMMARY: KEY FINDINGS")
    print(f"{'='*100}")
    print("""
1. SAMPLE SIZE IMPACT:
   - 10-issue samples have ±30% standard error (for p≈0.5)
   - 101-issue samples have ±10% standard error (for p≈0.5)
   - ~3x reduction in confidence interval width

2. BASELINE RATE CHANGES:
   - Compare baseline resolve rates between 10-issue and 101-issue
   - Large changes suggest sampling variance or selection bias
   - Small changes validate effect reproducibility

3. ENHANCEMENT EFFECT STABILITY:
   - Compare enhancement deltas (enhanced - baseline)
   - Consistent deltas across sample sizes validate enhancement benefit
   - Diverging deltas suggest solver variance or overfitting to small sample

4. REPOSITORY COMPOSITION:
   - Group A 10-issue: 10 astropy issues only
   - Group A 101-issue: 22 astropy + 32 sklearn + 22 xarray + 19 pytest + 6 matplotlib
   - Group B 10-issue: Flask/Requests/sklearn mix
   - Group B 101-issue: 34 matplotlib + 32 sklearn + 26 sphinx + 8 requests + 1 flask
   - Composition differences affect direct comparability
""")

    # Save structured output
    output_file = results_root / "10_vs_101_issue_comparison.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Saved structured comparison to: {output_file}")
    print("="*100)


if __name__ == "__main__":
    main()
