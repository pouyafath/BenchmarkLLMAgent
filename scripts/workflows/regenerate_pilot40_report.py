#!/usr/bin/env python3
"""
Regenerate the Stage 6 report from existing Stage 4 and Stage 5 artifacts.

This is a standalone script that reads the immutable eval results and
produces an accurate report with the truly-enhanced vs unchanged distinction.

Usage:
    cd /home/22pf2/BenchmarkLLMAgent
    bench_env/bin/python scripts/workflows/regenerate_pilot40_report.py
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUN_DIR = Path("/home/22pf2/BenchmarkLLMAgent/runs/paul_pilot40_stage4_stage6_20260526")
STAGE3_EXPORT = Path(
    "/home/22pf2/paul-RepoLaunch/runs/"
    "stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/"
    "stage3_validation_completed40.jsonl"
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _issue_type_counts(rows: list[dict]) -> dict[str, int]:
    return dict(Counter(r.get("issue_type", "unknown") for r in rows))


def main() -> int:
    # Load inputs
    instances = _load_jsonl(RUN_DIR / "validated_instances.jsonl")
    baseline_rows = _load_jsonl(RUN_DIR / "stage4_enhanced/baseline.jsonl")
    enhanced_rows = _load_jsonl(RUN_DIR / "stage4_enhanced/llm_append_analysis.jsonl")

    all_ids = [r["instance_id"] for r in instances]
    type_map = {r["instance_id"]: r.get("issue_type", "unknown") for r in instances}
    n = max(len(all_ids), 1)

    # Determine truly enhanced vs unchanged
    baseline_ps = {r["instance_id"]: r.get("problem_statement", "") for r in baseline_rows}
    truly_enhanced_ids = set()
    unchanged_ids = set()
    for row in enhanced_rows:
        iid = row["instance_id"]
        meta = row.get("enhancement_metadata", {})
        if meta.get("enhancer_type") == "error":
            unchanged_ids.add(iid)
        elif row.get("problem_statement", "").strip() != baseline_ps.get(iid, "").strip():
            truly_enhanced_ids.add(iid)
        else:
            unchanged_ids.add(iid)

    print(f"Truly enhanced: {len(truly_enhanced_ids)}")
    print(f"Unchanged: {len(unchanged_ids)}")

    # Load eval results
    eval_baseline_path = RUN_DIR / "stage5_solver_eval/eval_baseline/eval_results.json"
    eval_enhanced_path = RUN_DIR / "stage5_solver_eval/eval_enhanced/eval_results.json"

    if eval_baseline_path.exists():
        baseline_result = json.loads(eval_baseline_path.read_text())
    else:
        baseline_result = {"resolved": 0, "total": len(all_ids),
                           "resolved_ids": [], "failed_ids": all_ids}

    if eval_enhanced_path.exists():
        enhanced_result = json.loads(eval_enhanced_path.read_text())
    else:
        enhanced_result = {"resolved": 0, "total": len(all_ids),
                           "resolved_ids": [], "failed_ids": all_ids}

    baseline_set = set(baseline_result.get("resolved_ids", []))
    enhanced_set = set(enhanced_result.get("resolved_ids", []))

    gained = sorted(enhanced_set - baseline_set)
    lost = sorted(baseline_set - enhanced_set)
    both = sorted(baseline_set & enhanced_set)

    # Per-type breakdown
    per_type: dict[str, dict[str, Any]] = {}
    for t in sorted(set(type_map.values())):
        t_ids = [iid for iid in all_ids if type_map.get(iid) == t]
        per_type[t] = {
            "total": len(t_ids),
            "truly_enhanced": len([iid for iid in t_ids if iid in truly_enhanced_ids]),
            "baseline_resolved": len([iid for iid in t_ids if iid in baseline_set]),
            "enhanced_resolved": len([iid for iid in t_ids if iid in enhanced_set]),
            "baseline_resolved_ids": sorted(iid for iid in t_ids if iid in baseline_set),
            "enhanced_resolved_ids": sorted(iid for iid in t_ids if iid in enhanced_set),
        }

    # Summary JSON
    report_dir = RUN_DIR / "stage6_report"
    report_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "timestamp": _now(),
        "source_dataset": str(STAGE3_EXPORT),
        "total_instances": len(all_ids),
        "issue_type_counts": _issue_type_counts(instances),
        "enhancer": "llm_append_analysis",
        "solver": "mini_swe_agent (gpt-5.4-mini via OpenAI)",
        "truly_enhanced_count": len(truly_enhanced_ids),
        "unchanged_count": len(unchanged_ids),
        "truly_enhanced_ids": sorted(truly_enhanced_ids),
        "unchanged_ids": sorted(unchanged_ids),
        "baseline": {
            "resolved": baseline_result["resolved"],
            "total": baseline_result["total"],
            "rate_pct": round(baseline_result["resolved"] / n * 100, 2),
            "resolved_ids": baseline_result.get("resolved_ids", []),
        },
        "enhanced": {
            "resolved": enhanced_result["resolved"],
            "total": enhanced_result["total"],
            "rate_pct": round(enhanced_result["resolved"] / n * 100, 2),
            "resolved_ids": enhanced_result.get("resolved_ids", []),
        },
        "comparison": {
            "improvement_pp": round(
                (enhanced_result["resolved"] - baseline_result["resolved"]) / n * 100, 2
            ),
            "gained_by_enhancement": gained,
            "lost_by_enhancement": lost,
            "resolved_by_both": both,
        },
        "per_issue_type": per_type,
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    # Markdown report
    bl = baseline_result
    en = enhanced_result
    imp = summary["comparison"]["improvement_pp"]

    lines = [
        "# Stage 6: Pilot-40 Enhancer+Solver Comparison Report",
        "",
        f"**Generated:** {_now()}",
        f"**Source dataset:** `{STAGE3_EXPORT.name}` ({len(all_ids)} instances)",
        f"**Issue types:** {summary['issue_type_counts']}",
        f"**Enhancer:** llm_append_analysis (gpt-oss:120b via Ollama)",
        f"**Solver:** mini-SWE-agent (gpt-5.4-mini via OpenAI)",
        "",
        "## Overall Results",
        "",
        "| Condition | Resolved | Total | Rate |",
        "|---|---:|---:|---:|",
        f"| Baseline (original) | {bl['resolved']} | {bl['total']} | {bl['resolved']/n*100:.1f}% |",
        f"| Enhanced (llm_append_analysis) | {en['resolved']} | {en['total']} | {en['resolved']/n*100:.1f}% |",
        "",
        f"**Improvement:** {imp:+.1f} percentage points",
        f"**Gained by enhancement:** {len(gained)} instances "
        f"({', '.join(f'`{g}`' for g in gained) or 'none'})",
        f"**Lost by enhancement:** {len(lost)} instances "
        f"({', '.join(f'`{l}`' for l in lost) or 'none'})",
        f"**Resolved by both:** {len(both)} instances",
        "",
        "## Per Issue Type",
        "",
        "| Issue Type | Count | Enhanced | Baseline Resolved | Enhanced Resolved |",
        "|---|---:|---:|---:|---:|",
    ]
    for t, data in per_type.items():
        lines.append(
            f"| {t} | {data['total']} | "
            f"{data['truly_enhanced']}/{data['total']} | "
            f"{data['baseline_resolved']}/{data['total']} | "
            f"{data['enhanced_resolved']}/{data['total']} |"
        )

    lines.extend([
        "",
        "## Enhancement Coverage",
        "",
        f"- Instances sent to enhancer: {len(all_ids)}",
        f"- Truly enhanced (body changed): {len(truly_enhanced_ids)}",
        f"- Unchanged (LLM error/empty): {len(unchanged_ids)}",
        "",
        "Note: Both baseline and enhanced solver ran on all "
        f"{len(all_ids)} instances for apples-to-apples comparison. "
        "For unchanged instances, the solver saw identical input in both conditions.",
        "",
    ])

    # Truly-enhanced-only sub-analysis
    te_baseline = len([iid for iid in truly_enhanced_ids if iid in baseline_set])
    te_enhanced = len([iid for iid in truly_enhanced_ids if iid in enhanced_set])
    uc_baseline = len([iid for iid in unchanged_ids if iid in baseline_set])
    uc_enhanced = len([iid for iid in unchanged_ids if iid in enhanced_set])

    lines.extend([
        "## Sub-Analysis: Truly Enhanced Only",
        "",
        "| Subset | Count | Baseline Resolved | Enhanced Resolved |",
        "|---|---:|---:|---:|",
        f"| Truly enhanced | {len(truly_enhanced_ids)} | {te_baseline} | {te_enhanced} |",
        f"| Unchanged | {len(unchanged_ids)} | {uc_baseline} | {uc_enhanced} |",
        f"| Total | {len(all_ids)} | {bl['resolved']} | {en['resolved']} |",
        "",
    ])

    # Solver patch quality metrics
    bl_preds_path = RUN_DIR / "stage5_solver_eval/solver_baseline/preds.json"
    en_preds_path = RUN_DIR / "stage5_solver_eval/solver_enhanced/preds.json"
    bl_nonempty = en_nonempty = 0
    bl_total_preds = en_total_preds = 0
    if bl_preds_path.exists():
        bl_preds = json.loads(bl_preds_path.read_text())
        bl_total_preds = len(bl_preds)
        bl_nonempty = sum(1 for v in bl_preds.values()
                          if isinstance(v, dict) and v.get("model_patch", "").strip()
                          or isinstance(v, str) and v.strip())
    if en_preds_path.exists():
        en_preds = json.loads(en_preds_path.read_text())
        en_total_preds = len(en_preds)
        en_nonempty = sum(1 for v in en_preds.values()
                          if isinstance(v, dict) and v.get("model_patch", "").strip()
                          or isinstance(v, str) and v.strip())

    lines.extend([
        "## Solver Patch Quality",
        "",
        "| Condition | Predictions | Non-empty | Patch Rate |",
        "|---|---:|---:|---:|",
        f"| Baseline | {bl_total_preds} | {bl_nonempty} | "
        f"{bl_nonempty/max(bl_total_preds,1)*100:.0f}% |",
        f"| Enhanced | {en_total_preds} | {en_nonempty} | "
        f"{en_nonempty/max(en_total_preds,1)*100:.0f}% |",
        "",
    ])

    # Eval diagnostics
    lines.extend([
        "## Evaluation Notes",
        "",
        "Results were re-evaluated with `reeval_pilot40.py` to fix two issues:",
        "1. **Test name normalization**: Parsed test names could have `/testbed/` prefix "
        "or parameterized suffixes `[param]` that didn't match the dataset's expected names.",
        "2. **Resolution criteria**: The standard SWE-bench evaluator requires FAIL_TO_PASS "
        "success > 0, but this dataset uses PASS_TO_PASS > 0 as the gate (FAIL_TO_PASS is "
        "metadata only). The corrected criteria: no P2P failures AND at least one P2P pass.",
        "",
    ])

    lines.extend([
        "## Resolved Instance Details",
        "",
    ])

    if baseline_result.get("resolved_ids"):
        lines.append("### Baseline resolved")
        for iid in sorted(baseline_result["resolved_ids"]):
            enhanced_flag = " (truly enhanced)" if iid in truly_enhanced_ids else " (unchanged)"
            lines.append(f"- `{iid}` ({type_map.get(iid, '?')}{enhanced_flag})")
        lines.append("")

    if enhanced_result.get("resolved_ids"):
        lines.append("### Enhanced resolved")
        for iid in sorted(enhanced_result["resolved_ids"]):
            enhanced_flag = " (truly enhanced)" if iid in truly_enhanced_ids else " (unchanged)"
            lines.append(f"- `{iid}` ({type_map.get(iid, '?')}{enhanced_flag})")
        lines.append("")

    if not baseline_result.get("resolved_ids") and not enhanced_result.get("resolved_ids"):
        lines.append("No instances resolved in either condition.")
        lines.append("")

    lines.extend([
        "## Artifacts",
        "",
        f"- Run directory: `{RUN_DIR}`",
        f"- Summary JSON: `{report_dir / 'summary.json'}`",
        f"- Stage 4 enhanced datasets: `{RUN_DIR / 'stage4_enhanced'}`",
        f"- Stage 5 solver outputs: `{RUN_DIR / 'stage5_solver_eval'}`",
        f"- This report: `{report_dir / 'REPORT.md'}`",
    ])

    (report_dir / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(f"\nReport written to {report_dir / 'REPORT.md'}")
    print(f"Summary written to {report_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
