#!/usr/bin/env python3
"""Run mini-SWE-agent solver on Pouya-5 native enhanced datasets.

Inputs are the native CLI validation raw results from
``runs/native_cli_pouya5_20260509``. Invalid enhancer outputs are skipped under
strict mode and counted as enhancer failures in the final comparison.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.workflows.run_pouya20_gpt54mini import (  # noqa: E402
    BENCH_ENV_PYTHON,
    EVAL_SCRIPT,
    GPT_OVERRIDE,
    PAUL_ENV_PYTHON,
    SOLVER_SCRIPT,
    SWEBENCH_CONFIG,
    _load_openai_api_key,
    _make_env,
)

DEFAULT_VALIDATED = ROOT / "runs/pouya_final20b_20260505_050130/validated_instances.jsonl"
DEFAULT_NATIVE_DIR = ROOT / "runs/native_cli_pouya5_20260509"
DEFAULT_BASELINE_RUN = ROOT / "runs/pouya_solver20_20260505_063614"
DEFAULT_OUTPUT_DIR = ROOT / "runs/pouya5_native_solver_comparison_20260509"
DEFAULT_RAW_LLM_DATASET = ROOT / "runs/raw_llm_pouya20_20260511_fresh/datasets/raw_llm.jsonl"
AGENTS = ["aider", "trae", "openhands", "mini_swe_agent", "swe_agent"]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _solver_ready(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    if out.get("docker_image"):
        out["image_name"] = out["docker_image"]
    return out


def _is_valid_enhancement(raw: dict[str, Any], original: dict[str, Any]) -> tuple[bool, str]:
    result = raw.get("result") or {}
    checks = raw.get("checks") or {}
    meta = result.get("enhancement_metadata") or {}
    if meta.get("enhancer_type") != "real":
        return False, str(meta.get("error") or "enhancer_type is not real")
    if checks.get("timeout_contaminated"):
        return False, "timeout-contaminated enhanced body"
    if not checks.get("body_changed"):
        return False, "enhanced body did not change"
    # title_changed is informational — a good enhancement can keep the original title
    if (checks.get("enhanced_body_len") or 0) < 300:
        return False, "enhanced body too short"
    # has_repro_or_steps and has_expected_actual are keyword heuristics that
    # reject genuinely good enhancements which use different wording.
    # Demoted to warnings — body_changed + len > 300 + no timeout is sufficient.
    enhanced_body = result.get("enhanced_body") or ""
    if enhanced_body.strip() == (original.get("problem_statement") or "").strip():
        return False, "enhanced body equals original problem_statement"
    # Detect unfilled prompt template (mini_swe_agent stdout leak via loose_markers parser)
    if "<summary>" in enhanced_body and "<steps>" in enhanced_body:
        return False, "enhanced body contains unfilled template placeholders"
    return True, ""


def _build_agent_dataset(
    *,
    agent: str,
    rows: list[dict[str, Any]],
    native_dir: Path,
    raw_llm_dataset: Path,
    output_dir: Path,
) -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]]]:
    if agent in {"raw_llm", "llm_append_analysis"}:
        if not raw_llm_dataset.exists():
            raise FileNotFoundError(f"missing raw LLM enhanced dataset: {raw_llm_dataset}")
        source_rows = {row["instance_id"]: row for row in _load_jsonl(raw_llm_dataset)}
        enhanced_rows: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for row in rows:
            iid = row["instance_id"]
            source = source_rows.get(iid)
            if source is None:
                failures.append({"instance_id": iid, "reason": f"missing raw LLM row in {raw_llm_dataset}"})
                continue
            out = _solver_ready(source)
            out["enhancement_metadata"] = {
                **(out.get("enhancement_metadata") or {}),
                "source_dataset": str(raw_llm_dataset),
                "enhancer_agent": "raw_llm",
            }
            enhanced_rows.append(out)

        dataset_path = output_dir / "datasets" / "raw_llm.jsonl"
        _write_jsonl(dataset_path, enhanced_rows)
        (output_dir / "enhancement_failures").mkdir(parents=True, exist_ok=True)
        (output_dir / "enhancement_failures" / "raw_llm.json").write_text(
            json.dumps(failures, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return dataset_path, enhanced_rows, failures

    raw_dir = native_dir / "raw_results"
    enhanced_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for row in rows:
        iid = row["instance_id"]
        raw_path = raw_dir / f"{agent}__{iid}.json"
        if not raw_path.exists():
            failures.append({"instance_id": iid, "reason": f"missing raw result {raw_path}"})
            continue
        raw = json.loads(raw_path.read_text())
        ok, reason = _is_valid_enhancement(raw, row)
        if not ok:
            failures.append(
                {
                    "instance_id": iid,
                    "reason": reason,
                    "raw_result": str(raw_path),
                    "metadata": (raw.get("result") or {}).get("enhancement_metadata") or {},
                }
            )
            continue

        result = raw["result"]
        out = dict(row)
        out["original_problem_statement"] = row.get("problem_statement", "")
        out["problem_statement"] = result["enhanced_body"]
        out["enhanced_title"] = result.get("enhanced_title")
        out["enhancement_metadata"] = {
            **((result.get("enhancement_metadata") or {})),
            "source_raw_result": str(raw_path),
            "enhancer_agent": agent,
        }
        enhanced_rows.append(_solver_ready(out))

    dataset_path = output_dir / "datasets" / f"{agent}.jsonl"
    _write_jsonl(dataset_path, enhanced_rows)
    (output_dir / "enhancement_failures").mkdir(parents=True, exist_ok=True)
    (output_dir / "enhancement_failures" / f"{agent}.json").write_text(
        json.dumps(failures, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return dataset_path, enhanced_rows, failures


def _run(cmd: list[str], *, env: dict[str, str], log_path: Path, timeout: int) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(cmd) + "\n\n")
        log.flush()
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"command failed with returncode {proc.returncode}: {' '.join(cmd)}")


def _run_solver(
    *,
    dataset: Path,
    output_dir: Path,
    instance_ids: list[str],
    env: dict[str, str],
    workers: int,
    timeout: int,
    redo: bool,
) -> None:
    preds = output_dir / "preds.json"
    if preds.exists() and not redo and set(_load_prediction_ids(preds)) >= set(instance_ids):
        return
    cmd = [
        str(BENCH_ENV_PYTHON),
        str(SOLVER_SCRIPT),
        "--dataset-jsonl",
        str(dataset),
        "-c",
        str(SWEBENCH_CONFIG),
        "-c",
        str(GPT_OVERRIDE),
        "--output",
        str(output_dir),
        "--workers",
        str(workers),
    ]
    if redo:
        cmd.append("--redo-existing")
    _run(cmd, env=env, log_path=output_dir / "solver_command.log", timeout=timeout)


def _run_eval(
    *,
    validated_dataset: Path,
    preds: Path,
    instance_ids: list[str],
    output_dir: Path,
    env: dict[str, str],
    workers: int,
    timeout: int,
    redo: bool,
) -> None:
    existing = {p.parent.name for p in output_dir.glob("*/report.json")}
    results_path = output_dir / "results.json"
    if results_path.exists():
        results = json.loads(results_path.read_text())
        existing.update(results.get("empty_patch_ids") or [])
        existing.update(results.get("error_ids") or [])
    if not redo and existing >= set(instance_ids):
        return
    cmd = [
        str(PAUL_ENV_PYTHON),
        str(EVAL_SCRIPT),
        "--dataset",
        str(validated_dataset),
        "--patch_dir",
        str(preds),
        "--platform",
        "linux",
        "--workers",
        str(workers),
        "--output_dir",
        str(output_dir),
        "--overwrite",
        "1",
        "--instance_ids",
        *instance_ids,
    ]
    _run(cmd, env=env, log_path=output_dir / "eval_command.log", timeout=timeout)


def _load_prediction_ids(preds: Path) -> list[str]:
    if not preds.exists():
        return []
    data = json.loads(preds.read_text())
    if isinstance(data, dict):
        return sorted(data)
    if isinstance(data, list):
        return sorted(row["instance_id"] for row in data if row.get("instance_id"))
    raise TypeError(f"Unsupported predictions format in {preds}: {type(data).__name__}")


def _collect_eval(eval_dir: Path, instance_ids: list[str]) -> dict[str, Any]:
    resolved: list[str] = []
    unresolved: list[str] = []
    missing: list[str] = []
    reports: dict[str, Any] = {}
    empty_patch_ids: list[str] = []
    error_ids: list[str] = []
    results_path = eval_dir / "results.json"
    if results_path.exists():
        results = json.loads(results_path.read_text())
        empty_patch_ids = sorted(results.get("empty_patch_ids") or [])
        error_ids = sorted(results.get("error_ids") or [])
    for iid in instance_ids:
        report_path = eval_dir / iid / "report.json"
        if not report_path.exists():
            if iid not in empty_patch_ids and iid not in error_ids:
                missing.append(iid)
            unresolved.append(iid)
            continue
        report = json.loads(report_path.read_text())
        reports[iid] = report
        if report.get("resolved"):
            resolved.append(iid)
        else:
            unresolved.append(iid)
    return {
        "resolved": len(resolved),
        "total": len(instance_ids),
        "resolved_ids": resolved,
        "unresolved_ids": unresolved,
        "missing_report_ids": missing,
        "empty_patch_ids": empty_patch_ids,
        "error_ids": error_ids,
        "reports": reports,
    }


def _copy_baseline_subset(output_dir: Path, baseline_run: Path, instance_ids: list[str]) -> dict[str, Any]:
    baseline_eval = baseline_run / "solver_baseline_eval"
    target = output_dir / "baseline_eval_subset"
    target.mkdir(parents=True, exist_ok=True)
    for iid in instance_ids:
        src = baseline_eval / iid
        dst = target / iid
        if src.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)
    return _collect_eval(target, instance_ids)


def _write_markdown_report(path: Path, summary: dict[str, Any]) -> None:
    total_issues = len(summary.get("instance_ids", []))
    lines = [
        f"# Native Enhancer Solver Comparison ({total_issues} issues)",
        "",
        f"Run updated: {summary['updated_at']}",
        "",
        f"This compares the canonical mini-SWE-agent solver on {total_issues} issues after raw LLM or native CLI issue enhancement.",
        "Invalid enhancements, missing solver predictions, and empty patches are counted separately and treated as unresolved in the effective score.",
        "",
        "## Results",
        "",
        f"| Condition | Solver Inputs | Predictions | Enhancement Failures | Solver Missing | Empty Patches | Resolved / Evaluated | Effective Resolved / {total_issues} | Resolved IDs |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    baseline = summary["baseline"]
    lines.append(
        f"| baseline | {total_issues} | {total_issues} | 0 | 0 | 0 | {baseline['resolved']}/{baseline['total']} | "
        f"{baseline['resolved']}/{total_issues} | {', '.join(baseline['resolved_ids']) or '-'} |"
    )
    for agent, data in summary["agents"].items():
        resolved = data["eval"]["resolved"]
        valid_total = data["eval"]["total"]
        effective = resolved
        lines.append(
            f"| {agent} | {len(data['valid_instance_ids'])} | {len(data.get('prediction_ids') or [])} | "
            f"{len(data['enhancement_failures'])} | {len(data.get('solver_missing_ids') or [])} | "
            f"{len(data['eval'].get('empty_patch_ids') or [])} | {resolved}/{valid_total} | {effective}/{total_issues} | "
            f"{', '.join(data['eval']['resolved_ids']) or '-'} |"
        )

    lines.extend(["", "## Enhancement Failures", ""])
    for agent, data in summary["agents"].items():
        failures = data["enhancement_failures"]
        if not failures:
            continue
        lines.append(f"### {agent}")
        for failure in failures:
            lines.append(f"- `{failure['instance_id']}`: {failure['reason']}")
        lines.append("")

    lines.extend(["", "## Solver/Evaluator Gaps", ""])
    for agent, data in summary["agents"].items():
        gaps: list[str] = []
        if data.get("solver_missing_ids"):
            gaps.append("solver missing: " + ", ".join(f"`{iid}`" for iid in data["solver_missing_ids"]))
        if data["eval"].get("empty_patch_ids"):
            gaps.append("empty patch: " + ", ".join(f"`{iid}`" for iid in data["eval"]["empty_patch_ids"]))
        if data.get("run_error"):
            gaps.append("run error: " + data["run_error"])
        if gaps:
            lines.append(f"### {agent}")
            lines.extend(f"- {gap}" for gap in gaps)
            lines.append("")

    lines.extend(["", "## Artifacts", ""])
    lines.append(f"- Summary JSON: `{summary['summary_json']}`")
    lines.append(f"- Run directory: `{summary['output_dir']}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validated", type=Path, default=DEFAULT_VALIDATED)
    parser.add_argument("--native-dir", type=Path, default=DEFAULT_NATIVE_DIR)
    parser.add_argument("--baseline-run", type=Path, default=DEFAULT_BASELINE_RUN)
    parser.add_argument("--raw-llm-dataset", type=Path, default=DEFAULT_RAW_LLM_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--agents", default=",".join(AGENTS))
    parser.add_argument("--solver-workers", type=int, default=2)
    parser.add_argument("--eval-workers", type=int, default=2)
    parser.add_argument("--solver-timeout", type=int, default=7200)
    parser.add_argument("--eval-timeout", type=int, default=3600)
    parser.add_argument("--redo-solver", action="store_true")
    parser.add_argument("--redo-eval", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("OPENAI_API_KEY_FILE", str(ROOT / ".claude/settings.local.json"))
    api_key = _load_openai_api_key()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY or OPENAI_API_KEY_FILE is required")
    env = _make_env(api_key)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = [_solver_ready(r) for r in _load_jsonl(args.validated)[: args.limit]]
    instance_ids = [r["instance_id"] for r in rows]
    validated_subset = args.output_dir / "validated_instances.jsonl"
    _write_jsonl(validated_subset, rows)

    summary: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(args.output_dir),
        "summary_json": str(args.output_dir / "summary.json"),
        "validated_subset": str(validated_subset),
        "native_dir": str(args.native_dir),
        "baseline_run": str(args.baseline_run),
        "instance_ids": instance_ids,
        "baseline": _copy_baseline_subset(args.output_dir, args.baseline_run, instance_ids),
        "agents": {},
    }

    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    for agent in agents:
        print(f"\n=== {agent} ===", flush=True)
        dataset, enhanced_rows, failures = _build_agent_dataset(
            agent=agent,
            rows=rows,
            native_dir=args.native_dir,
            raw_llm_dataset=args.raw_llm_dataset,
            output_dir=args.output_dir,
        )
        solver_dir = args.output_dir / "solver_runs" / agent
        eval_dir = args.output_dir / "eval_runs" / agent
        valid_ids = [r["instance_id"] for r in enhanced_rows]
        run_error = ""
        prediction_ids: list[str] = []
        solver_missing_ids: list[str] = []
        evaluated_ids: list[str] = []
        if enhanced_rows:
            try:
                _run_solver(
                    dataset=dataset,
                    output_dir=solver_dir,
                    instance_ids=valid_ids,
                    env=env,
                    workers=args.solver_workers,
                    timeout=args.solver_timeout,
                    redo=args.redo_solver,
                )
                prediction_ids = _load_prediction_ids(solver_dir / "preds.json")
                evaluated_ids = [iid for iid in valid_ids if iid in set(prediction_ids)]
                solver_missing_ids = [iid for iid in valid_ids if iid not in set(prediction_ids)]
                _run_eval(
                    validated_dataset=validated_subset,
                    preds=solver_dir / "preds.json",
                    instance_ids=evaluated_ids,
                    output_dir=eval_dir,
                    env=env,
                    workers=args.eval_workers,
                    timeout=args.eval_timeout,
                    redo=args.redo_eval,
                )
                eval_result = _collect_eval(eval_dir, evaluated_ids)
            except Exception as exc:
                run_error = str(exc)
                prediction_ids = _load_prediction_ids(solver_dir / "preds.json")
                evaluated_ids = [iid for iid in valid_ids if iid in set(prediction_ids)]
                solver_missing_ids = [iid for iid in valid_ids if iid not in set(prediction_ids)]
                eval_result = _collect_eval(eval_dir, evaluated_ids)
        else:
            eval_result = {
                "resolved": 0,
                "total": 0,
                "resolved_ids": [],
                "unresolved_ids": [],
                "missing_report_ids": [],
                "empty_patch_ids": [],
                "error_ids": [],
                "reports": {},
            }
        summary["agents"][agent] = {
            "dataset": str(dataset),
            "solver_dir": str(solver_dir),
            "eval_dir": str(eval_dir),
            "valid_instance_ids": valid_ids,
            "prediction_ids": prediction_ids,
            "solver_missing_ids": solver_missing_ids,
            "enhancement_failures": failures,
            "run_error": run_error,
            "eval": eval_result,
            "effective_total": len(instance_ids),
            "effective_resolved": eval_result["resolved"],
        }
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(
            f"{agent}: {eval_result['resolved']}/{eval_result['total']} resolved "
            f"({len(failures)} enhancement failures"
            f"{', run error: ' + run_error[:120] if run_error else ''})",
            flush=True,
        )

    _write_markdown_report(args.output_dir / "ANALYSIS.md", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
