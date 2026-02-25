"""
Statistical Analysis Module for BenchmarkLLMAgent.

Implements paired framework comparisons with appropriate statistical tests,
effect sizes, and multiple comparison corrections.
"""

import logging
from dataclasses import dataclass
from itertools import combinations
from typing import Optional

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class PairwiseComparison:
    framework_a: str
    framework_b: str
    metric: str
    mean_a: float
    mean_b: float
    median_a: float
    median_b: float
    statistic: float
    p_value: float
    p_value_corrected: float
    effect_size: float
    effect_size_label: str  # negligible, small, medium, large
    ci_lower: float
    ci_upper: float
    significant: bool


class StatisticalAnalyzer:
    """Framework comparison with statistical rigor."""

    def __init__(self, alpha: float = 0.05, bootstrap_n: int = 10000):
        self.alpha = alpha
        self.bootstrap_n = bootstrap_n

    def compare_frameworks(
        self,
        results_by_framework: dict[str, list[float]],
        metric_name: str,
    ) -> list[PairwiseComparison]:
        """
        Run pairwise comparisons across all framework pairs for a given metric.
        Applies Bonferroni correction for multiple comparisons.
        """
        frameworks = sorted(results_by_framework.keys())
        pairs = list(combinations(frameworks, 2))
        n_comparisons = len(pairs)

        comparisons = []
        for fw_a, fw_b in pairs:
            vals_a = np.array(results_by_framework[fw_a])
            vals_b = np.array(results_by_framework[fw_b])

            min_len = min(len(vals_a), len(vals_b))
            vals_a_paired = vals_a[:min_len]
            vals_b_paired = vals_b[:min_len]

            stat, p_value = stats.wilcoxon(vals_a_paired, vals_b_paired, alternative="two-sided")

            p_corrected = min(p_value * n_comparisons, 1.0)

            effect = self._cliffs_delta(vals_a, vals_b)
            effect_label = self._effect_size_label(abs(effect))

            ci_low, ci_high = self._bootstrap_ci(vals_a, vals_b)

            comparisons.append(PairwiseComparison(
                framework_a=fw_a,
                framework_b=fw_b,
                metric=metric_name,
                mean_a=float(np.mean(vals_a)),
                mean_b=float(np.mean(vals_b)),
                median_a=float(np.median(vals_a)),
                median_b=float(np.median(vals_b)),
                statistic=float(stat),
                p_value=float(p_value),
                p_value_corrected=float(p_corrected),
                effect_size=float(effect),
                effect_size_label=effect_label,
                ci_lower=ci_low,
                ci_upper=ci_high,
                significant=p_corrected < self.alpha,
            ))

        return comparisons

    @staticmethod
    def _cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
        """Compute Cliff's delta effect size (non-parametric)."""
        n_x, n_y = len(x), len(y)
        if n_x == 0 or n_y == 0:
            return 0.0

        more = sum(1 for xi in x for yi in y if xi > yi)
        less = sum(1 for xi in x for yi in y if xi < yi)

        return (more - less) / (n_x * n_y)

    @staticmethod
    def _effect_size_label(d: float) -> str:
        if d < 0.147:
            return "negligible"
        elif d < 0.33:
            return "small"
        elif d < 0.474:
            return "medium"
        else:
            return "large"

    def _bootstrap_ci(self, x: np.ndarray, y: np.ndarray,
                      confidence: float = 0.95) -> tuple[float, float]:
        """Bootstrap confidence interval for the difference in means."""
        rng = np.random.default_rng(42)
        diffs = []
        for _ in range(self.bootstrap_n):
            x_sample = rng.choice(x, size=len(x), replace=True)
            y_sample = rng.choice(y, size=len(y), replace=True)
            diffs.append(np.mean(x_sample) - np.mean(y_sample))

        diffs = np.array(diffs)
        lower_pct = (1 - confidence) / 2 * 100
        upper_pct = (1 + confidence) / 2 * 100
        return float(np.percentile(diffs, lower_pct)), float(np.percentile(diffs, upper_pct))

    def stratified_analysis(
        self,
        results: list[dict],
        group_key: str,
        metric_key: str,
    ) -> dict[str, list[PairwiseComparison]]:
        """
        Run framework comparisons stratified by a grouping variable
        (e.g., issue_type, complexity, repo_language).
        """
        groups: dict[str, dict[str, list[float]]] = {}
        for r in results:
            group = r.get(group_key, "unknown")
            framework = r["framework"]
            value = r.get(metric_key, 0)

            if group not in groups:
                groups[group] = {}
            if framework not in groups[group]:
                groups[group][framework] = []
            groups[group][framework].append(value)

        stratified_results = {}
        for group, fw_data in groups.items():
            if len(fw_data) >= 2:
                stratified_results[group] = self.compare_frameworks(
                    fw_data, f"{metric_key}_by_{group_key}={group}"
                )

        return stratified_results

    def summary_table(self, comparisons: list[PairwiseComparison]) -> str:
        """Generate a formatted summary table of pairwise comparisons."""
        header = (
            f"{'Framework A':<20} {'Framework B':<20} {'Metric':<25} "
            f"{'Mean A':>8} {'Mean B':>8} {'p-corr':>8} {'Cliff d':>8} {'Effect':>12} {'Sig':>5}"
        )
        lines = [header, "-" * len(header)]
        for c in comparisons:
            sig = "***" if c.significant and abs(c.effect_size) >= 0.474 else \
                  "**" if c.significant and abs(c.effect_size) >= 0.33 else \
                  "*" if c.significant else ""
            lines.append(
                f"{c.framework_a:<20} {c.framework_b:<20} {c.metric:<25} "
                f"{c.mean_a:>8.3f} {c.mean_b:>8.3f} {c.p_value_corrected:>8.4f} "
                f"{c.effect_size:>8.3f} {c.effect_size_label:>12} {sig:>5}"
            )
        return "\n".join(lines)
