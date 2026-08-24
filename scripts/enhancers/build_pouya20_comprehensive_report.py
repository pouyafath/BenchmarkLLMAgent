#!/usr/bin/env python3
"""Build a comprehensive Pouya-20 cross-solver/enhancer report."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

RUNS = {
    "mini_swe_agent_solver": ROOT / "runs/pouya20_solver_comparison_v2/summary.json",
    "swe_agent_solver": ROOT / "runs/pouya20_sweagent_solver_comparison_20260511/summary.json",
    "aider_solver": ROOT / "runs/pouya20_aider_solver_comparison_20260511/summary.json",
}
CONDITIONS = ["baseline", "raw_llm", "aider", "trae", "openhands", "mini_swe_agent", "swe_agent"]
OUTPUT_DIR = ROOT / "runs/pouya20_comprehensive_solver_enhancer_report_20260511"
RAW_LLM_FOLLOWUP = ROOT / "runs/pouya20_raw_llm_solver_comparison_20260511/SUMMARY.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _empty_patch_ids(preds_path: Path) -> list[str]:
    if not preds_path.exists():
        return []
    data = _load(preds_path)
    rows = data.values() if isinstance(data, dict) else data
    return sorted(
        row["instance_id"]
        for row in rows
        if row.get("instance_id") and not (row.get("model_patch") or "").strip()
    )


def _report_eval(eval_dir: Path, instance_ids: list[str], empty_patch_ids: list[str]) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    for report_path in sorted(eval_dir.glob("*/report.json")):
        report = _load(report_path)
        iid = report.get("instance_id") or report_path.parent.name
        reports[iid] = report
    resolved_ids = sorted(iid for iid, report in reports.items() if report.get("resolved"))
    missing = sorted((set(instance_ids) - set(reports)) | set(empty_patch_ids))
    return {
        "resolved": len(resolved_ids),
        "total": len(instance_ids),
        "resolved_ids": resolved_ids,
        "missing_report_ids": missing,
        "empty_patch_ids": empty_patch_ids,
    }


def _condition_from_artifacts(run_dir: Path, condition: str) -> dict[str, Any]:
    if condition == "baseline":
        raise KeyError("baseline fallback is not supported")
    dataset_path = run_dir / "datasets" / f"{condition}.jsonl"
    preds_path = run_dir / "solver_runs" / condition / "preds.json"
    eval_dir = run_dir / "eval_runs" / condition
    failures = _load(run_dir / "enhancement_failures" / f"{condition}.json") if (run_dir / "enhancement_failures" / f"{condition}.json").exists() else []
    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()] if dataset_path.exists() else []
    input_ids = [row["instance_id"] for row in rows]
    prediction_ids = []
    if preds_path.exists():
        preds = _load(preds_path)
        prediction_ids = sorted(preds.keys()) if isinstance(preds, dict) else sorted(row["instance_id"] for row in preds)
    empty_patch_ids = _empty_patch_ids(preds_path)
    ev = _report_eval(eval_dir, prediction_ids or input_ids, empty_patch_ids)
    return {
        "solver_inputs": len(input_ids),
        "predictions": len(prediction_ids),
        "enhancement_failures": len(failures),
        "enhancement_failure_ids": [
            f["instance_id"] if isinstance(f, dict) else str(f) for f in failures
        ],
        "empty_patch_ids": ev["empty_patch_ids"],
        "missing_report_ids": ev["missing_report_ids"],
        "eval_error": "",
        "resolved": ev["resolved"],
        "evaluated_total": ev["total"],
        "effective_resolved": ev["resolved"],
        "resolved_ids": ev["resolved_ids"],
    }


def _condition(summary: dict[str, Any], condition: str, run_dir: Path) -> dict[str, Any]:
    if "conditions" in summary:
        data = summary["conditions"][condition]
        ev = data["eval"]
        return {
            "solver_inputs": len(data["input_instance_ids"]),
            "predictions": len(data["prediction_ids"]),
            "enhancement_failures": len(data.get("enhancement_failures") or []),
            "enhancement_failure_ids": [
                f["instance_id"] if isinstance(f, dict) else str(f)
                for f in (data.get("enhancement_failures") or [])
            ],
            "empty_patch_ids": ev.get("empty_patch_ids") or [],
            "missing_report_ids": ev.get("missing_report_ids") or [],
            "eval_error": data.get("eval_error") or "",
            "resolved": ev["resolved"],
            "evaluated_total": ev["total"],
            "effective_resolved": data.get("effective_resolved", ev["resolved"]),
            "resolved_ids": ev.get("resolved_ids") or [],
        }

    if condition == "baseline":
        data = summary["baseline"]
        return {
            "solver_inputs": data.get("total", 20),
            "predictions": data.get("total", 20),
            "enhancement_failures": 0,
            "enhancement_failure_ids": [],
            "empty_patch_ids": data.get("empty_patch_ids") or [],
            "missing_report_ids": data.get("missing_report_ids") or [],
            "eval_error": data.get("run_error") or data.get("eval_error") or "",
            "resolved": data["resolved"],
            "evaluated_total": data["total"],
            "effective_resolved": data["resolved"],
            "resolved_ids": data.get("resolved_ids") or [],
        }

    if condition not in summary["agents"]:
        return _condition_from_artifacts(run_dir, condition)

    data = summary["agents"][condition]
    ev = data["eval"]
    preds_path = run_dir / "solver_runs" / condition / "preds.json"
    eval_dir = run_dir / "eval_runs" / condition
    if preds_path.exists() and eval_dir.exists():
        prediction_ids = data.get("prediction_ids") or []
        if not prediction_ids:
            preds = _load(preds_path)
            prediction_ids = sorted(preds.keys()) if isinstance(preds, dict) else sorted(row["instance_id"] for row in preds)
        ev = _report_eval(eval_dir, prediction_ids, _empty_patch_ids(preds_path))
    failures = data.get("enhancement_failures") or []
    return {
        "solver_inputs": len(data.get("input_instance_ids") or []),
        "predictions": len(data.get("prediction_ids") or []),
        "enhancement_failures": len(failures),
        "enhancement_failure_ids": [
            f["instance_id"] if isinstance(f, dict) else str(f) for f in failures
        ],
        "empty_patch_ids": ev.get("empty_patch_ids") or [],
        "missing_report_ids": ev.get("missing_report_ids") or [],
        "eval_error": data.get("run_error") or data.get("eval_error") or "",
        "resolved": ev["resolved"],
        "evaluated_total": ev["total"],
        "effective_resolved": data.get("effective_resolved", ev["resolved"]),
        "resolved_ids": ev.get("resolved_ids") or [],
    }


def _raw_condition(raw_summary: dict[str, Any], solver: str) -> dict[str, Any]:
    data = raw_summary["solvers"][solver]
    return {
        "solver_inputs": data["denominator"],
        "predictions": data["predictions"],
        "enhancement_failures": 0,
        "enhancement_failure_ids": [],
        "empty_patch_ids": data.get("empty_patch_ids") or [],
        "missing_report_ids": data.get("missing_report_ids") or [],
        "eval_error": data.get("eval_error") or "",
        "resolved": data["resolved"],
        "evaluated_total": data["denominator"],
        "effective_resolved": data["effective_resolved"],
        "resolved_ids": data.get("resolved_ids") or [],
        "solver_missing_ids": data.get("missing_prediction_ids") or [],
        "status": data.get("status") or "",
    }


def _mk_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    loaded = {name: _load(path) for name, path in RUNS.items()}
    raw_summary = _load(RAW_LLM_FOLLOWUP) if RAW_LLM_FOLLOWUP.exists() else None
    matrix: dict[str, dict[str, Any]] = {}
    for solver, summary in loaded.items():
        run_dir = RUNS[solver].parent
        matrix[solver] = {}
        for condition in CONDITIONS:
            if condition == "raw_llm" and raw_summary is not None:
                matrix[solver][condition] = _raw_condition(raw_summary, solver)
            else:
                matrix[solver][condition] = _condition(summary, condition, run_dir)

    baseline_by_solver = {
        solver: data["baseline"]["effective_resolved"] for solver, data in matrix.items()
    }
    delta_by_condition: dict[str, list[int]] = defaultdict(list)
    resolved_counter: Counter[str] = Counter()
    for solver, data in matrix.items():
        base = baseline_by_solver[solver]
        for condition, result in data.items():
            if condition != "baseline":
                delta_by_condition[condition].append(result["effective_resolved"] - base)
            for iid in result["resolved_ids"]:
                resolved_counter[iid] += 1

    summary_out = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_runs": {name: str(path) for name, path in RUNS.items()},
        "conditions": CONDITIONS,
        "matrix": matrix,
        "baseline_by_solver": baseline_by_solver,
        "delta_by_condition": dict(delta_by_condition),
        "resolved_frequency": dict(sorted(resolved_counter.items())),
    }
    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary_out, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    display_solver = {
        "mini_swe_agent_solver": "mini-SWE-agent",
        "swe_agent_solver": "SWE-agent",
        "aider_solver": "Aider",
    }
    lines: list[str] = [
        "# Pouya-20 Comprehensive Solver x Enhancer Report",
        "",
        f"Generated: {summary_out['updated_at']}",
        "",
        "This report combines the three completed solver views over the same 20 validated Pouya instances: mini-SWE-agent, SWE-agent, and Aider. Each solver was evaluated on baseline issue text, fresh raw LLM-enhanced issue text, and the five native CLI enhancer outputs.",
        "",
        "## Executive Summary",
        "",
        "- Total solver/enhancer cells: 21 (3 solvers x baseline plus raw LLM and 5 native enhancer conditions).",
        "- Raw LLM and native-agent enhancement are not reliably beneficial across solvers. Most enhancer/solver pairings match or underperform their solver baseline.",
        "- The only positive resolved-count delta is `aider` enhancement with the Aider solver: 3/20 versus Aider baseline 2/20.",
        "- Enhanced issues often reduce empty patches for the Aider solver, but most additional non-empty patches still fail evaluation.",
        "- `amazon-science__chronos-forecasting-407` is a recurring evaluator-timeout case and should be treated as an evaluation-management caveat, not as evidence for a specific enhancer.",
        "",
        "## Resolved Count Matrix",
        "",
    ]

    rows = []
    for solver, data in matrix.items():
        rows.append(
            [
                display_solver[solver],
                *[
                    f"{data[condition]['effective_resolved']}/20"
                    for condition in CONDITIONS
                ],
            ]
        )
    lines.extend(_mk_table(["Solver", *CONDITIONS], rows))

    lines.extend(["", "## Delta Versus Solver Baseline", ""])
    rows = []
    for solver, data in matrix.items():
        base = baseline_by_solver[solver]
        rows.append(
            [
                display_solver[solver],
                "0",
                *[
                    f"{data[condition]['effective_resolved'] - base:+d}"
                    for condition in CONDITIONS[1:]
                ],
            ]
        )
    lines.extend(_mk_table(["Solver", *CONDITIONS], rows))

    lines.extend(["", "## Empty Patch Matrix", ""])
    rows = []
    for solver, data in matrix.items():
        rows.append(
            [
                display_solver[solver],
                *[str(len(data[condition]["empty_patch_ids"])) for condition in CONDITIONS],
            ]
        )
    lines.extend(_mk_table(["Solver", *CONDITIONS], rows))

    lines.extend(["", "## Resolved IDs By Cell", ""])
    for solver, data in matrix.items():
        lines.extend(["", f"### {display_solver[solver]}", ""])
        rows = [
            [
                condition,
                f"{data[condition]['effective_resolved']}/20",
                ", ".join(data[condition]["resolved_ids"]) or "-",
            ]
            for condition in CONDITIONS
        ]
        lines.extend(_mk_table(["Condition", "Resolved", "Resolved IDs"], rows))

    lines.extend(["", "## Main Interpretation", ""])
    lines.extend(
        [
            "1. The project hypothesis is not supported as a general claim on Pouya-20. Across three solvers, raw LLM and native-agent issue enhancement usually do not improve resolved count.",
            "2. There is one narrow positive result: Aider-enhanced issue text helps Aider solve `aws-powertools__powertools-lambda-python-7026`, raising Aider from 2/20 to 3/20.",
            "3. Raw LLM enhancement matches mini-SWE-agent and SWE-agent baselines at 3/20, but underperforms the Aider baseline at 1/20.",
            "4. The native-agent benefit is not enhancer-general or solver-general. The same `aider` enhancement does not improve mini-SWE-agent or SWE-agent, and other enhancers do not improve Aider.",
            "5. Enhanced prompts can change solver behavior substantially. For Aider, baseline had 9 empty patches, while enhanced conditions had 0-5 empty patches. More attempts did not usually mean more resolved issues.",
            "6. The next scientifically useful step is qualitative error analysis on the cells where behavior changed: Aider baseline empty patches, Aider-enhanced `aws-powertools` success, raw-LLM/Aider loss of `ag2ai__faststream-2495`, and regressions where enhanced text replaced a baseline-solvable issue with a failing patch.",
        ]
    )

    lines.extend(["", "## Raw LLM Follow-up Status", ""])
    if RAW_LLM_FOLLOWUP.exists():
        raw = _load(RAW_LLM_FOLLOWUP)
        mini = raw["solvers"]["mini_swe_agent_solver"]
        swe = raw["solvers"]["swe_agent_solver"]
        aider = raw["solvers"]["aider_solver"]
        lines.extend(
            [
                f"Fresh raw LLM enhancements were regenerated for {raw['raw_llm_enhancement']['dataset_rows']}/20 issues using `{raw['raw_llm_enhancement']['model']}` and the `{raw['raw_llm_enhancement']['strategy']}` strategy. Raw LLM results are now included in the matrix above: mini-SWE-agent {mini['effective_resolved']}/20, SWE-agent {swe['effective_resolved']}/20, Aider {aider['effective_resolved']}/20.",
                "",
                "Caveats: `amazon-science__chronos-forecasting-407` was manually terminated during SWE-agent and Aider evaluation after entering the known evaluator-hang path, and `PennyLaneAI__pennylane-7474` still lacks a mini-SWE-agent raw prediction. These cases are counted unresolved.",
                "",
                "Raw LLM follow-up artifacts:",
                "",
                "- `runs/raw_llm_pouya20_20260511_fresh/SUMMARY.json`",
                "- `runs/pouya20_raw_llm_solver_comparison_20260511/REPORT.md`",
                "- `docs/analysis/POUYA20_RAW_LLM_ENHANCER_2026-05-11.md`",
            ]
        )
    else:
        lines.append("No fresh raw LLM follow-up summary was found.")

    lines.extend(["", "## Source Artifacts", ""])
    for name, path in RUNS.items():
        lines.append(f"- {display_solver[name]}: `{path.relative_to(ROOT)}`")
    if RAW_LLM_FOLLOWUP.exists():
        lines.append(f"- raw LLM follow-up: `{RAW_LLM_FOLLOWUP.relative_to(ROOT)}`")
    lines.append(f"- Machine-readable combined summary: `{(OUTPUT_DIR / 'summary.json').relative_to(ROOT)}`")

    (OUTPUT_DIR / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUTPUT_DIR / "REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
