#!/usr/bin/env python3
"""Aggregate baseline + multiple enhanced runs into one comparison artifact."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _load_comparison(path: Path) -> dict:
    if path.is_dir():
        path = path / "comparison_summary.json"
    if not path.exists():
        raise FileNotFoundError(f"Comparison summary not found: {path}")
    return json.loads(path.read_text())


def _run_row(name: str, metrics: dict | None) -> dict[str, Any]:
    if not metrics:
        return {
            "name": name,
            "num_issues": 0,
            "attempted_issue_count": 0,
            "resolved_issue_count": 0,
            "resolved_issue_rate": 0.0,
            "resolved_issue_rate_attempted": 0.0,
            "fail_to_pass_issue_success_count": 0,
            "fail_to_pass_issue_success_rate": 0.0,
            "pass_to_pass_issue_success_count": 0,
            "pass_to_pass_issue_success_rate": 0.0,
            "infrastructure_failure_count": 0,
            "model_provider_failure_count": 0,
            "evaluation_failure_count": 0,
        }
    return {
        "name": name,
        "num_issues": int(metrics.get("num_issues", 0)),
        "attempted_issue_count": int(metrics.get("attempted_issue_count", metrics.get("num_issues", 0))),
        "resolved_issue_count": int(metrics.get("resolved_issue_count", 0)),
        "resolved_issue_rate": float(metrics.get("resolved_issue_rate", 0.0)),
        "resolved_issue_rate_attempted": float(
            metrics.get("resolved_issue_rate_attempted", metrics.get("resolved_issue_rate", 0.0))
        ),
        "fail_to_pass_issue_success_count": int(metrics.get("fail_to_pass_issue_success_count", 0)),
        "fail_to_pass_issue_success_rate": float(metrics.get("fail_to_pass_issue_success_rate", 0.0)),
        "pass_to_pass_issue_success_count": int(metrics.get("pass_to_pass_issue_success_count", 0)),
        "pass_to_pass_issue_success_rate": float(metrics.get("pass_to_pass_issue_success_rate", 0.0)),
        "infrastructure_failure_count": int(metrics.get("infrastructure_failure_count", 0)),
        "model_provider_failure_count": int(metrics.get("model_provider_failure_count", 0)),
        "evaluation_failure_count": int(metrics.get("evaluation_failure_count", 0)),
    }


def _to_markdown(payload: dict) -> str:
    lines = [
        "# Verified-10 Multi-Enhancer Comparison",
        "",
        f"Generated at: {payload['generated_at_utc']}",
        f"Dataset: `{payload['dataset_name']}` ({payload['split']})",
        "",
        "## Metrics Table",
        "",
        "| Run | Attempted | RESOLVED | RESOLVED % | RESOLVED % (attempted) | F2P % | P2P % | Infra Fail | Model Fail | Eval Fail |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for row in payload["rows"]:
        lines.append(
            "| {name} | {attempted}/{num} | {resolved}/{num} | {resolved_pct:.1f}% | "
            "{resolved_att_pct:.1f}% | {f2p_pct:.1f}% | {p2p_pct:.1f}% | {infra} | {model} | {evalf} |".format(
                name=row["name"],
                attempted=row["attempted_issue_count"],
                num=row["num_issues"],
                resolved=row["resolved_issue_count"],
                resolved_pct=row["resolved_issue_rate"] * 100,
                resolved_att_pct=row["resolved_issue_rate_attempted"] * 100,
                f2p_pct=row["fail_to_pass_issue_success_rate"] * 100,
                p2p_pct=row["pass_to_pass_issue_success_rate"] * 100,
                infra=row["infrastructure_failure_count"],
                model=row["model_provider_failure_count"],
                evalf=row["evaluation_failure_count"],
            )
        )

    lines.extend(
        [
            "",
            "## Notes",
            "- Baseline row comes from replication-aligned baseline metrics inside each comparison summary.",
            "- Enhanced rows are sorted by RESOLVED rate descending.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-dirs",
        nargs="+",
        required=True,
        help="Run directories (or comparison_summary.json paths) to aggregate.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/verified10_baseline_vs_enhanced/multi_enhancer_comparison.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("results/verified10_baseline_vs_enhanced/multi_enhancer_comparison.md"),
    )
    args = parser.parse_args()

    comparisons = [_load_comparison(Path(p)) for p in args.run_dirs]
    if not comparisons:
        raise ValueError("No comparisons provided")

    baseline = comparisons[0]["baseline"]
    dataset_name = comparisons[0].get("dataset_name", "")
    split = comparisons[0].get("split", "")

    enhanced_rows = []
    for comp in comparisons:
        name = comp.get("enhancer_agent", "unknown")
        enhanced_rows.append(_run_row(name, comp.get("enhanced")))
    enhanced_rows.sort(key=lambda r: r["resolved_issue_rate"], reverse=True)

    rows = [_run_row("baseline", baseline)] + enhanced_rows
    payload = {
        "generated_at_utc": _utc_now(),
        "dataset_name": dataset_name,
        "split": split,
        "instance_ids": comparisons[0].get("instance_ids", []),
        "rows": rows,
        "sources": [str(Path(p)) for p in args.run_dirs],
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2))
    args.output_md.write_text(_to_markdown(payload))
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
