#!/usr/bin/env python3
"""Run Aider solver on baseline and native-enhanced Pouya-20 datasets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.solvers import aider_solver  # noqa: E402

_SWE_COMP_PATH = ROOT / "scripts/enhancers/run_pouya20_sweagent_solver_comparison.py"
_SWE_COMP_SPEC = importlib.util.spec_from_file_location("sweagent_solver_comparison", _SWE_COMP_PATH)
if _SWE_COMP_SPEC is None or _SWE_COMP_SPEC.loader is None:
    raise RuntimeError(f"Cannot load comparison helpers from {_SWE_COMP_PATH}")
_SWE_COMP = importlib.util.module_from_spec(_SWE_COMP_SPEC)
_SWE_COMP_SPEC.loader.exec_module(_SWE_COMP)

EVAL_SCRIPT = _SWE_COMP.EVAL_SCRIPT
PAUL_ENV_PYTHON = _SWE_COMP.PAUL_ENV_PYTHON
_load_openai_api_key = _SWE_COMP._load_openai_api_key
_make_env = _SWE_COMP._make_env

DEFAULT_VALIDATED = ROOT / "runs/pouya_final20b_20260505_050130/validated_instances.jsonl"
DEFAULT_MINI_COMPARISON = ROOT / "runs/pouya20_solver_comparison_v2"
DEFAULT_SWE_COMPARISON = ROOT / "runs/pouya20_sweagent_solver_comparison_20260511"
DEFAULT_OUTPUT_DIR = ROOT / "runs/pouya20_aider_solver_comparison_20260511"
AGENTS = ["aider", "trae", "openhands", "mini_swe_agent", "swe_agent"]


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


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


def _prediction_ids(preds_path: Path) -> list[str]:
    if not preds_path.exists():
        return []
    data = json.loads(preds_path.read_text(encoding="utf-8"))
    rows = data.values() if isinstance(data, dict) else data
    return sorted(row["instance_id"] for row in rows if row.get("instance_id"))


def _empty_patch_ids(preds_path: Path) -> list[str]:
    if not preds_path.exists():
        return []
    data = json.loads(preds_path.read_text(encoding="utf-8"))
    rows = data.values() if isinstance(data, dict) else data
    return sorted(
        row["instance_id"]
        for row in rows
        if row.get("instance_id") and not (row.get("model_patch") or "").strip()
    )


def _run_eval(
    *,
    validated_dataset: Path,
    preds: Path,
    instance_ids: list[str],
    skip_ids: list[str],
    output_dir: Path,
    env: dict[str, str],
    workers: int,
    timeout: int,
    redo: bool,
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    if redo and output_dir.exists():
        for path in output_dir.iterdir():
            if path.name == "eval_command.log":
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    skip = set(skip_ids)
    failures: list[str] = []
    log_path = output_dir / "eval_command.log"
    log_dir = output_dir / "eval_logs"
    log_dir.mkdir(exist_ok=True)
    with log_path.open("a", encoding="utf-8") as main_log:
        main_log.write(f"\n# Per-instance evaluation started at {datetime.now(timezone.utc).isoformat()}\n")
        main_log.write(f"# timeout_per_instance={timeout}s workers={workers}\n")
        for iid in instance_ids:
            if iid in skip:
                main_log.write(f"SKIP empty patch: {iid}\n")
                continue
            if not redo and (output_dir / iid / "report.json").exists():
                main_log.write(f"SKIP existing report: {iid}\n")
                continue
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
                iid,
            ]
            instance_log_path = log_dir / f"{iid}.log"
            main_log.write("$ " + " ".join(cmd) + "\n")
            main_log.flush()
            with instance_log_path.open("w", encoding="utf-8") as log:
                log.write("$ " + " ".join(cmd) + "\n\n")
                log.flush()
                proc = subprocess.Popen(
                    cmd,
                    cwd=ROOT,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
                try:
                    returncode = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    failures.append(f"{iid}: evaluation timed out after {timeout}s")
                    main_log.write(f"TIMEOUT {iid}\n")
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                        proc.wait(timeout=30)
                    except Exception:
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except Exception:
                            pass
                    time.sleep(2)
                    continue
            if returncode != 0:
                failures.append(f"{iid}: evaluation exited with returncode {returncode}")
                main_log.write(f"FAIL {iid}: returncode {returncode}\n")
            else:
                main_log.write(f"DONE {iid}\n")
            main_log.flush()
    return "; ".join(failures)


def _collect_eval(eval_dir: Path, instance_ids: list[str], pred_empty_ids: list[str]) -> dict[str, Any]:
    resolved: list[str] = []
    unresolved: list[str] = []
    missing: list[str] = []
    reports: dict[str, Any] = {}
    results = _load_json(eval_dir / "results.json", {})
    eval_empty_ids = sorted(set(results.get("empty_patch_ids") or []) | set(pred_empty_ids))
    error_ids = sorted(results.get("error_ids") or [])
    for iid in instance_ids:
        report_path = eval_dir / iid / "report.json"
        if not report_path.exists():
            missing.append(iid)
            unresolved.append(iid)
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
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
        "empty_patch_ids": eval_empty_ids,
        "error_ids": error_ids,
        "reports": reports,
    }


def _load_condition_dataset(
    *,
    condition: str,
    rows: list[dict[str, Any]],
    mini_comparison_dir: Path,
    output_dir: Path,
) -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]]]:
    if condition == "baseline":
        dataset_path = output_dir / "datasets" / "baseline.jsonl"
        ready = [_solver_ready(row) for row in rows]
        _write_jsonl(dataset_path, ready)
        return dataset_path, ready, []

    source_dataset = mini_comparison_dir / "datasets" / f"{condition}.jsonl"
    if not source_dataset.exists():
        raise FileNotFoundError(f"missing enhanced dataset for {condition}: {source_dataset}")
    dataset_path = output_dir / "datasets" / f"{condition}.jsonl"
    ready = [_solver_ready(row) for row in _load_jsonl(source_dataset)]
    _write_jsonl(dataset_path, ready)
    failures = _load_json(mini_comparison_dir / "enhancement_failures" / f"{condition}.json", [])
    return dataset_path, ready, failures


def _load_reference(summary_path: Path) -> dict[str, Any]:
    summary = _load_json(summary_path, {})
    if not summary:
        return {}
    out: dict[str, Any] = {}
    if "baseline" in summary:
        baseline = summary.get("baseline") or {}
        out["baseline"] = {
            "resolved": baseline.get("resolved", 0),
            "total": baseline.get("total", 0),
            "resolved_ids": baseline.get("resolved_ids", []),
        }
    if "conditions" in summary:
        for condition, data in (summary.get("conditions") or {}).items():
            ev = data.get("eval") or {}
            out[condition] = {
                "resolved": ev.get("resolved", 0),
                "total": ev.get("total", 0),
                "resolved_ids": ev.get("resolved_ids", []),
            }
    for agent, data in (summary.get("agents") or {}).items():
        ev = data.get("eval") or {}
        out[agent] = {
            "resolved": ev.get("resolved", 0),
            "total": ev.get("total", 0),
            "resolved_ids": ev.get("resolved_ids", []),
        }
    return out


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    total = len(summary["instance_ids"])
    mini_ref = summary.get("mini_swe_solver_reference") or {}
    swe_ref = summary.get("swe_agent_solver_reference") or {}
    lines = [
        "# Aider Solver Comparison on Pouya-20",
        "",
        f"Run updated: {summary['updated_at']}",
        "",
        "This run uses native Aider CLI as the solver on the same 20 validated Pouya instances and the same native-enhanced datasets used by the mini-SWE-agent and SWE-agent solver comparisons.",
        "Enhancement failures, empty solver patches, evaluator errors, and missing reports are counted as unresolved in the effective score.",
        "",
        "## Results",
        "",
        f"| Condition | Solver Inputs | Predictions | Enhancement Failures | Empty Patches | Missing Reports | Eval Issues | Aider Resolved / Evaluated | Effective Resolved / {total} | mini-SWE Solver Ref | SWE-agent Solver Ref | Resolved IDs |",
        "|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    for condition, data in summary["conditions"].items():
        ev = data["eval"]
        mref = mini_ref.get(condition) or {}
        sref = swe_ref.get(condition) or {}
        eval_issue = data.get("eval_error") or "-"
        lines.append(
            f"| {condition} | {len(data['input_instance_ids'])} | {len(data['prediction_ids'])} | "
            f"{len(data['enhancement_failures'])} | {len(ev.get('empty_patch_ids') or [])} | "
            f"{len(ev.get('missing_report_ids') or [])} | {eval_issue} | "
            f"{ev['resolved']}/{ev['total']} | {ev['resolved']}/{total} | "
            f"{mref.get('resolved', '-')}/{mref.get('total', '-') if mref else '-'} | "
            f"{sref.get('resolved', '-')}/{sref.get('total', '-') if sref else '-'} | "
            f"{', '.join(ev['resolved_ids']) or '-'} |"
        )

    baseline = summary["conditions"].get("baseline", {}).get("eval", {})
    baseline_resolved = baseline.get("resolved", 0)
    lines.extend(["", "## Enhancer Effect With Aider Solver", ""])
    for condition, data in summary["conditions"].items():
        if condition == "baseline":
            continue
        ev = data["eval"]
        delta = ev["resolved"] - baseline_resolved
        direction = "improved" if delta > 0 else "regressed" if delta < 0 else "matched"
        lines.append(
            f"- `{condition}` {direction} baseline by {delta:+d} resolved issue(s): "
            f"{', '.join(ev['resolved_ids']) or 'none'}."
        )

    lines.extend(["", "## Known Gaps", ""])
    any_gap = False
    for condition, data in summary["conditions"].items():
        ev = data["eval"]
        gaps: list[str] = []
        if data.get("enhancement_failures"):
            gaps.append(
                "enhancement failure: "
                + ", ".join(f"`{f['instance_id']}`" for f in data["enhancement_failures"])
            )
        if ev.get("empty_patch_ids"):
            gaps.append("empty patch: " + ", ".join(f"`{iid}`" for iid in ev["empty_patch_ids"]))
        if ev.get("missing_report_ids"):
            gaps.append("missing report: " + ", ".join(f"`{iid}`" for iid in ev["missing_report_ids"]))
        if ev.get("error_ids"):
            gaps.append("evaluator error: " + ", ".join(f"`{iid}`" for iid in ev["error_ids"]))
        if data.get("eval_error"):
            gaps.append(data["eval_error"])
        if gaps:
            any_gap = True
            lines.append(f"### {condition}")
            lines.extend(f"- {gap}" for gap in gaps)
            lines.append("")
    if not any_gap:
        lines.append("No missing reports, empty patches, enhancement failures, or evaluator errors were recorded.")

    lines.extend(["", "## Artifacts", ""])
    lines.append(f"- Summary JSON: `{summary['summary_json']}`")
    lines.append(f"- Run directory: `{summary['output_dir']}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validated", type=Path, default=DEFAULT_VALIDATED)
    parser.add_argument("--mini-comparison-dir", type=Path, default=DEFAULT_MINI_COMPARISON)
    parser.add_argument("--swe-comparison-dir", type=Path, default=DEFAULT_SWE_COMPARISON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--conditions", default="baseline," + ",".join(AGENTS))
    parser.add_argument("--solver-model", default=os.environ.get("AIDER_SOLVER_MODEL", "openai/gpt-5.4-mini"))
    parser.add_argument("--solver-base-url", default=os.environ.get("AIDER_SOLVER_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--solver-workers", type=int, default=int(os.environ.get("AIDER_SOLVER_WORKERS", "1")))
    parser.add_argument("--solver-timeout", type=int, default=int(os.environ.get("AIDER_SOLVER_TIMEOUT", "1800")))
    parser.add_argument("--eval-workers", type=int, default=2)
    parser.add_argument("--eval-timeout", type=int, default=1800)
    parser.add_argument("--redo-solver", action="store_true")
    parser.add_argument("--redo-eval", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("OPENAI_API_KEY_FILE", str(ROOT / ".claude/settings.local.json"))
    api_key = os.environ.get("AIDER_SOLVER_API_KEY") or _load_openai_api_key()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY, AIDER_SOLVER_API_KEY, or OPENAI_API_KEY_FILE is required")

    env = _make_env(api_key)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = [_solver_ready(row) for row in _load_jsonl(args.validated)]
    instance_ids = [row["instance_id"] for row in rows]
    validated_copy = args.output_dir / "validated_instances.jsonl"
    _write_jsonl(validated_copy, rows)

    summary: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(args.output_dir),
        "summary_json": str(args.output_dir / "summary.json"),
        "validated_dataset": str(validated_copy),
        "source_validated_dataset": str(args.validated),
        "mini_comparison_dir": str(args.mini_comparison_dir),
        "swe_comparison_dir": str(args.swe_comparison_dir),
        "solver": {
            "name": "aider",
            "model": args.solver_model,
            "base_url": args.solver_base_url,
            "workers": args.solver_workers,
            "timeout": args.solver_timeout,
        },
        "instance_ids": instance_ids,
        "mini_swe_solver_reference": _load_reference(args.mini_comparison_dir / "summary.json"),
        "swe_agent_solver_reference": _load_reference(args.swe_comparison_dir / "summary.json"),
        "conditions": {},
    }

    for condition in [c.strip() for c in args.conditions.split(",") if c.strip()]:
        print(f"\n=== {condition} ===", flush=True)
        dataset, condition_rows, failures = _load_condition_dataset(
            condition=condition,
            rows=rows,
            mini_comparison_dir=args.mini_comparison_dir,
            output_dir=args.output_dir,
        )
        input_ids = [row["instance_id"] for row in condition_rows]
        solver_dir = args.output_dir / "solver_runs" / condition
        eval_dir = args.output_dir / "eval_runs" / condition
        preds_path = solver_dir / "preds.json"
        if args.redo_solver and preds_path.exists():
            preds_path.unlink()

        if set(_prediction_ids(preds_path)) >= set(input_ids):
            print(f"{condition}: solver predictions already complete", flush=True)
        else:
            aider_solver.run_batch(
                condition_rows,
                api_key,
                solver_dir / "work",
                preds_path,
                model=args.solver_model,
                base_url=args.solver_base_url,
                workers=args.solver_workers,
                timeout=args.solver_timeout,
            )

        prediction_ids = _prediction_ids(preds_path)
        evaluated_ids = [iid for iid in input_ids if iid in set(prediction_ids)]
        pred_empty_ids = _empty_patch_ids(preds_path)
        if args.skip_eval:
            eval_error = ""
            eval_result = _collect_eval(eval_dir, evaluated_ids, pred_empty_ids)
        else:
            eval_error = _run_eval(
                validated_dataset=validated_copy,
                preds=preds_path,
                instance_ids=evaluated_ids,
                skip_ids=pred_empty_ids,
                output_dir=eval_dir,
                env=env,
                workers=args.eval_workers,
                timeout=args.eval_timeout,
                redo=args.redo_eval,
            )
            eval_result = _collect_eval(eval_dir, evaluated_ids, pred_empty_ids)

        summary["conditions"][condition] = {
            "dataset": str(dataset),
            "solver_dir": str(solver_dir),
            "eval_dir": str(eval_dir),
            "input_instance_ids": input_ids,
            "prediction_ids": prediction_ids,
            "solver_missing_ids": [iid for iid in input_ids if iid not in set(prediction_ids)],
            "enhancement_failures": failures,
            "eval_error": eval_error,
            "eval": eval_result,
            "effective_total": len(instance_ids),
            "effective_resolved": eval_result["resolved"],
        }
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        _write_report(args.output_dir / "ANALYSIS.md", summary)
        print(
            f"{condition}: {eval_result['resolved']}/{eval_result['total']} resolved, "
            f"{len(pred_empty_ids)} empty patches"
            f"{', eval issue: ' + eval_error if eval_error else ''}",
            flush=True,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
