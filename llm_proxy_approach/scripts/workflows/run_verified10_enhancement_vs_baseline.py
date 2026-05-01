#!/usr/bin/env python3
"""Run Verified-10 enhancement experiment against an existing baseline.

Workflow:
1. Prepare the fixed Verified sample from replication-selected IDs
2. Run enhancer on those issues (cache-aware)
3. Build enhanced JSONL dataset with schema/quality checks
4. Run mini-SWE-agent solver on enhanced statements
5. Retry timeout-only solver instances (configurable)
6. Evaluate with SWE-bench harness
7. Compare enhanced metrics vs sliced baseline metrics
8. Persist reproducibility manifest and run artifacts
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import re
import shlex
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from datasets import load_dataset


def _detect_repo_root() -> Path:
    """Resolve repository root whether this script lives in root/scripts or llm_proxy_approach/scripts."""
    script_path = Path(__file__).resolve()
    direct_root = script_path.parent.parent.parent
    if (direct_root / "scripts").exists() and (direct_root / "src").exists():
        return direct_root
    parent_root = direct_root.parent
    if (parent_root / "scripts").exists() and (parent_root / "src").exists():
        return parent_root
    raise RuntimeError(
        f"Could not detect repository root from {script_path}. "
        "Expected to find both 'scripts' and 'src' directories."
    )


ROOT = _detect_repo_root()

DEFAULT_REPLICATION_DIR = Path("/home/22pf2/SWE-Bench_Replication")
DEFAULT_REPLICATION_SELECTED_IDS = DEFAULT_REPLICATION_DIR / "selected_instances.txt"
DEFAULT_SELECTED_IDS = ROOT / "data" / "samples" / "swe_bench_verified_10_instance_ids.txt"
DEFAULT_SAMPLES_JSON = ROOT / "data" / "samples" / "swe_bench_verified_10_samples.json"
DEFAULT_DATASET = "SWE-bench/SWE-bench_Verified"
DEFAULT_SPLIT = "test"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            return json.loads(value)
        except Exception:
            try:
                return ast.literal_eval(value)
            except Exception:
                return [value]
    return []


def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def _append_command(commands_file: Path, title: str, cmd: list[str], cwd: Path) -> None:
    commands_file.parent.mkdir(parents=True, exist_ok=True)
    with commands_file.open("a") as f:
        f.write(f"\n## {title}\n")
        f.write("```bash\n")
        f.write(f"cd {cwd}\n")
        f.write(" ".join(shlex.quote(c) for c in cmd) + "\n")
        f.write("```\n")


def _run_cmd(
    title: str,
    cmd: list[str],
    cwd: Path,
    log_dir: Path,
    commands_file: Path,
    env: dict | None = None,
    check: bool = True,
) -> tuple[Path, Path]:
    _append_command(commands_file, title, cmd, cwd)
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{title.replace(' ', '_').lower()}.stdout.log"
    stderr_path = log_dir / f"{title.replace(' ', '_').lower()}.stderr.log"
    with stdout_path.open("w") as out, stderr_path.open("w") as err:
        proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=out, stderr=err, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"{title} failed with exit code {proc.returncode}. "
            f"See {stdout_path} and {stderr_path}."
        )
    return stdout_path, stderr_path


def _load_ids(ids_path: Path) -> list[str]:
    ids = [line.strip() for line in ids_path.read_text().splitlines() if line.strip()]
    if not ids:
        raise ValueError(f"No instance IDs found in {ids_path}")
    return ids


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _get_git_commit(root: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or None
    except Exception:
        return None


def _safe_load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text()) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _build_filter_regex(instance_ids: list[str]) -> str:
    if not instance_ids:
        return "^$"
    escaped = [re.escape(i) for i in instance_ids]
    return "^(" + "|".join(escaped) + ")$"


def _expected_model_dir_name_from_override(path: Path) -> str | None:
    config = _safe_load_yaml(path)
    model_name = (
        config.get("model", {}).get("model_name")
        if isinstance(config.get("model"), dict)
        else None
    )
    if not model_name or not isinstance(model_name, str):
        return None
    return model_name.replace("/", "__")


def _select_model_dir(
    run_eval_dir: Path,
    instance_ids: list[str],
    expected_model_dir_name: str | None,
) -> Path:
    model_dirs = sorted([p for p in run_eval_dir.iterdir() if p.is_dir()], key=lambda p: p.name)
    if not model_dirs:
        raise FileNotFoundError(f"No model output directories found under {run_eval_dir}")

    if expected_model_dir_name:
        for path in model_dirs:
            if path.name == expected_model_dir_name:
                return path

    if len(model_dirs) == 1:
        return model_dirs[0]

    # Deterministic fallback: choose dir with highest coverage of requested reports.
    scored = []
    for path in model_dirs:
        coverage = sum(1 for iid in instance_ids if (path / iid / "report.json").exists())
        scored.append((coverage, path.name, path))
    scored.sort(reverse=True)
    return scored[0][2]


def _parse_harness_summary_from_log(log_path: Path | None) -> dict:
    if not log_path or not log_path.exists():
        return {}

    patterns = {
        "total_instances": r"^Total instances:\s+(\d+)$",
        "instances_submitted": r"^Instances submitted:\s+(\d+)$",
        "instances_completed": r"^Instances completed:\s+(\d+)$",
        "instances_incomplete": r"^Instances incomplete:\s+(\d+)$",
        "instances_resolved": r"^Instances resolved:\s+(\d+)$",
        "instances_unresolved": r"^Instances unresolved:\s+(\d+)$",
        "instances_with_empty_patches": r"^Instances with empty patches:\s+(\d+)$",
        "instances_with_errors": r"^Instances with errors:\s+(\d+)$",
    }
    result: dict[str, int] = {}
    for line in log_path.read_text().splitlines():
        text = line.strip()
        for key, pattern in patterns.items():
            m = re.match(pattern, text)
            if m:
                result[key] = int(m.group(1))
    return result


def _latest_exit_status_file(output_dir: Path) -> Path | None:
    files = list(output_dir.glob("exit_statuses_*.yaml"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _load_exit_status_by_instance(exit_status_path: Path | None) -> dict[str, str]:
    if not exit_status_path or not exit_status_path.exists():
        return {}

    payload = _safe_load_yaml(exit_status_path)
    by_status = payload.get("instances_by_exit_status")
    if not isinstance(by_status, dict):
        return {}

    out: dict[str, str] = {}
    for status, ids in by_status.items():
        if not isinstance(ids, list):
            continue
        for iid in ids:
            if isinstance(iid, str):
                out[iid] = str(status)
    return out


def _classify_solver_failures(status_map: dict[str, str], instance_ids: list[str]) -> dict:
    infra: set[str] = set()
    model: set[str] = set()
    ok_status = {"submitted", "completed", "success", "resolved", "done"}

    for iid in instance_ids:
        status = status_map.get(iid, "")
        if not status:
            continue
        s = status.lower()
        if s in ok_status:
            continue
        if any(token in s for token in ("timeout", "rate", "api", "model", "connection")):
            model.add(iid)
        else:
            infra.add(iid)

    return {
        "infrastructure_failure_ids": sorted(infra),
        "model_provider_failure_ids": sorted(model),
        "infrastructure_failure_count": len(infra),
        "model_provider_failure_count": len(model),
    }


def _attempted_rate(count: int, attempted: int) -> float:
    return (count / attempted) if attempted else 0.0


def _validate_enhancement_payload(
    *,
    original_title: str,
    original_body: str,
    enhanced_title: Any,
    enhanced_body: Any,
    max_body_chars: int,
    max_similarity: float,
    allow_identical: bool,
) -> dict:
    if not isinstance(enhanced_title, str):
        raise ValueError("enhanced_title must be a string")
    if not isinstance(enhanced_body, str):
        raise ValueError("enhanced_body must be a string")
    if len(enhanced_body) > max_body_chars:
        raise ValueError(
            f"enhanced_body length {len(enhanced_body)} exceeds max {max_body_chars}"
        )

    title_similarity = SequenceMatcher(
        None, _normalize_text(original_title), _normalize_text(enhanced_title)
    ).ratio()
    body_similarity = SequenceMatcher(
        None, _normalize_text(original_body), _normalize_text(enhanced_body)
    ).ratio()
    near_identical = title_similarity >= max_similarity and body_similarity >= max_similarity
    if near_identical and not allow_identical:
        raise ValueError(
            f"enhancement rejected by quality gate (title_similarity={title_similarity:.3f}, "
            f"body_similarity={body_similarity:.3f})"
        )

    return {
        "title_similarity": title_similarity,
        "body_similarity": body_similarity,
        "near_identical": near_identical,
    }


def _build_enhanced_dataset_jsonl(
    *,
    instance_ids: list[str],
    dataset_name: str,
    split: str,
    enhancement_dir: Path,
    enhancer_agent: str,
    samples_json: Path,
    output_jsonl: Path,
    max_body_chars: int,
    max_similarity: float,
    allow_identical: bool,
    require_native: bool,
) -> tuple[dict[str, dict], dict]:
    rows = load_dataset(dataset_name, split=split)
    rows_by_id = {row["instance_id"]: row for row in rows}

    with samples_json.open() as f:
        sample_payload = json.load(f)
    sample_issues = sample_payload["issues"]
    sample_by_id = {issue["instance_id"]: issue for issue in sample_issues}

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    selected_rows: dict[str, dict] = {}
    quality_rows: list[dict] = []
    with output_jsonl.open("w") as f:
        for iid in instance_ids:
            if iid not in rows_by_id:
                raise ValueError(f"Instance {iid} not found in dataset {dataset_name}/{split}")
            if iid not in sample_by_id:
                raise ValueError(f"Instance {iid} not found in samples JSON {samples_json}")

            sample = sample_by_id[iid]
            owner = sample["pr_owner"]
            repo = sample["pr_repo"]
            issue_number = sample["issue_number"]
            enh_file = enhancement_dir / f"{enhancer_agent}__{owner}__{repo}__{issue_number}.json"
            if not enh_file.exists():
                raise FileNotFoundError(
                    f"Missing enhancement result for {iid}: {enh_file}. "
                    "Run enhancement step first or use --skip-enhancement only when files exist."
                )

            enh = json.loads(enh_file.read_text())
            metadata = enh.get("enhancement_metadata", {})
            enhancer_type = metadata.get("enhancer_type") if isinstance(metadata, dict) else None
            if require_native and enhancer_type != "real":
                raise ValueError(
                    f"native enhancer required, but {iid} has enhancer_type={enhancer_type!r} "
                    f"in {enh_file}"
                )
            enhanced_title = enh.get("enhanced_title", "")
            enhanced_body = enh.get("enhanced_body", "")
            quality = _validate_enhancement_payload(
                original_title=sample.get("title", "") or "",
                original_body=sample.get("body", "") or "",
                enhanced_title=enhanced_title,
                enhanced_body=enhanced_body,
                max_body_chars=max_body_chars,
                max_similarity=max_similarity,
                allow_identical=allow_identical,
            )
            quality_rows.append({"instance_id": iid, **quality})

            enhanced_problem_statement = f"{enhanced_title.strip()}\n\n{enhanced_body.strip()}".strip()
            row = dict(rows_by_id[iid])
            row["problem_statement"] = enhanced_problem_statement
            row["enhancement_agent"] = enhancer_agent
            row["enhancement_source_file"] = str(enh_file)
            row["enhancement_quality"] = quality

            f.write(json.dumps(row) + "\n")
            selected_rows[iid] = row

    near_identical_count = sum(1 for x in quality_rows if x["near_identical"])
    quality_summary = {
        "num_issues": len(quality_rows),
        "near_identical_count": near_identical_count,
        "near_identical_rate": (near_identical_count / len(quality_rows)) if quality_rows else 0.0,
        "avg_title_similarity": (
            sum(x["title_similarity"] for x in quality_rows) / len(quality_rows)
            if quality_rows
            else 0.0
        ),
        "avg_body_similarity": (
            sum(x["body_similarity"] for x in quality_rows) / len(quality_rows)
            if quality_rows
            else 0.0
        ),
        "per_instance": quality_rows,
    }
    return selected_rows, quality_summary


def _compute_metrics_from_reports(
    *,
    run_id: str,
    instance_ids: list[str],
    dataset_rows_by_id: dict[str, dict],
    expected_model_dir_name: str | None,
    harness_summary: dict,
    solver_status_by_instance: dict[str, str],
) -> dict:
    run_eval_dir = ROOT / "logs" / "run_evaluation" / run_id
    if not run_eval_dir.exists():
        raise FileNotFoundError(f"Evaluation log directory not found: {run_eval_dir}")

    model_dir = _select_model_dir(
        run_eval_dir=run_eval_dir,
        instance_ids=instance_ids,
        expected_model_dir_name=expected_model_dir_name,
    )

    resolved_issue_count = 0
    f2p_issue_success_count = 0
    p2p_issue_success_count = 0
    f2p_tests_passed = 0
    f2p_tests_total = 0
    p2p_tests_passed = 0
    p2p_tests_total = 0
    attempted_issue_count = 0
    evaluation_failure_ids: list[str] = []

    per_instance = []
    resolved_ids = []

    for iid in instance_ids:
        report_path = model_dir / iid / "report.json"
        expected_f2p = _normalize_list(dataset_rows_by_id[iid]["FAIL_TO_PASS"])
        expected_p2p = _normalize_list(dataset_rows_by_id[iid]["PASS_TO_PASS"])

        if not report_path.exists():
            evaluation_failure_ids.append(iid)
            f2p_tests_total += len(expected_f2p)
            p2p_tests_total += len(expected_p2p)
            per_instance.append(
                {
                    "instance_id": iid,
                    "resolved": False,
                    "fail_to_pass_issue_success": False,
                    "pass_to_pass_issue_success": False,
                    "fail_to_pass_passed": 0,
                    "fail_to_pass_total": len(expected_f2p),
                    "pass_to_pass_passed": 0,
                    "pass_to_pass_total": len(expected_p2p),
                    "evaluation_report_missing": True,
                }
            )
            continue

        report_payload = json.loads(report_path.read_text())
        report = report_payload.get(iid) or next(iter(report_payload.values()))
        tests_status = report["tests_status"]
        attempted_issue_count += 1

        f2p_success = tests_status["FAIL_TO_PASS"]["success"]
        f2p_failure = tests_status["FAIL_TO_PASS"]["failure"]
        p2p_success = tests_status["PASS_TO_PASS"]["success"]
        p2p_failure = tests_status["PASS_TO_PASS"]["failure"]

        resolved = bool(report["resolved"])
        f2p_issue_success = len(f2p_failure) == 0 and len(f2p_success) == len(expected_f2p)
        p2p_issue_success = len(p2p_failure) == 0 and len(p2p_success) == len(expected_p2p)

        if resolved:
            resolved_issue_count += 1
            resolved_ids.append(iid)
        if f2p_issue_success:
            f2p_issue_success_count += 1
        if p2p_issue_success:
            p2p_issue_success_count += 1

        f2p_tests_passed += len(f2p_success)
        f2p_tests_total += len(expected_f2p)
        p2p_tests_passed += len(p2p_success)
        p2p_tests_total += len(expected_p2p)

        per_instance.append(
            {
                "instance_id": iid,
                "resolved": resolved,
                "fail_to_pass_issue_success": f2p_issue_success,
                "pass_to_pass_issue_success": p2p_issue_success,
                "fail_to_pass_passed": len(f2p_success),
                "fail_to_pass_total": len(expected_f2p),
                "pass_to_pass_passed": len(p2p_success),
                "pass_to_pass_total": len(expected_p2p),
            }
        )

    n = len(instance_ids)
    solver_failure = _classify_solver_failures(solver_status_by_instance, instance_ids)
    return {
        "num_issues": n,
        "attempted_issue_count": attempted_issue_count,
        "resolved_issue_count": resolved_issue_count,
        "resolved_issue_rate": resolved_issue_count / n if n else 0.0,
        "resolved_issue_rate_attempted": _attempted_rate(resolved_issue_count, attempted_issue_count),
        "fail_to_pass_issue_success_count": f2p_issue_success_count,
        "fail_to_pass_issue_success_rate": f2p_issue_success_count / n if n else 0.0,
        "fail_to_pass_issue_success_rate_attempted": _attempted_rate(
            f2p_issue_success_count, attempted_issue_count
        ),
        "pass_to_pass_issue_success_count": p2p_issue_success_count,
        "pass_to_pass_issue_success_rate": p2p_issue_success_count / n if n else 0.0,
        "pass_to_pass_issue_success_rate_attempted": _attempted_rate(
            p2p_issue_success_count, attempted_issue_count
        ),
        "fail_to_pass_tests_passed": f2p_tests_passed,
        "fail_to_pass_tests_total": f2p_tests_total,
        "fail_to_pass_test_pass_rate": (f2p_tests_passed / f2p_tests_total) if f2p_tests_total else 0.0,
        "pass_to_pass_tests_passed": p2p_tests_passed,
        "pass_to_pass_tests_total": p2p_tests_total,
        "pass_to_pass_test_pass_rate": (p2p_tests_passed / p2p_tests_total) if p2p_tests_total else 0.0,
        "evaluation_failure_count": len(evaluation_failure_ids),
        "evaluation_failure_ids": evaluation_failure_ids,
        "resolved_ids": resolved_ids,
        "model_dir": str(model_dir),
        "per_instance": per_instance,
        "harness_summary": harness_summary,
        **solver_failure,
    }


def _compute_metrics_without_reports(
    *,
    instance_ids: list[str],
    dataset_rows_by_id: dict[str, dict],
    harness_summary: dict,
    solver_status_by_instance: dict[str, str],
    reason: str,
) -> dict:
    f2p_tests_total = 0
    p2p_tests_total = 0
    per_instance = []
    for iid in instance_ids:
        expected_f2p = _normalize_list(dataset_rows_by_id[iid]["FAIL_TO_PASS"])
        expected_p2p = _normalize_list(dataset_rows_by_id[iid]["PASS_TO_PASS"])
        f2p_tests_total += len(expected_f2p)
        p2p_tests_total += len(expected_p2p)
        per_instance.append(
            {
                "instance_id": iid,
                "resolved": False,
                "fail_to_pass_issue_success": False,
                "pass_to_pass_issue_success": False,
                "fail_to_pass_passed": 0,
                "fail_to_pass_total": len(expected_f2p),
                "pass_to_pass_passed": 0,
                "pass_to_pass_total": len(expected_p2p),
                "evaluation_report_missing": True,
            }
        )

    attempted_issue_count = int(harness_summary.get("instances_completed", 0))
    solver_failure = _classify_solver_failures(solver_status_by_instance, instance_ids)
    return {
        "num_issues": len(instance_ids),
        "attempted_issue_count": attempted_issue_count,
        "resolved_issue_count": 0,
        "resolved_issue_rate": 0.0,
        "resolved_issue_rate_attempted": 0.0,
        "fail_to_pass_issue_success_count": 0,
        "fail_to_pass_issue_success_rate": 0.0,
        "fail_to_pass_issue_success_rate_attempted": 0.0,
        "pass_to_pass_issue_success_count": 0,
        "pass_to_pass_issue_success_rate": 0.0,
        "pass_to_pass_issue_success_rate_attempted": 0.0,
        "fail_to_pass_tests_passed": 0,
        "fail_to_pass_tests_total": f2p_tests_total,
        "fail_to_pass_test_pass_rate": 0.0,
        "pass_to_pass_tests_passed": 0,
        "pass_to_pass_tests_total": p2p_tests_total,
        "pass_to_pass_test_pass_rate": 0.0,
        "evaluation_failure_count": len(instance_ids),
        "evaluation_failure_ids": list(instance_ids),
        "resolved_ids": [],
        "model_dir": None,
        "per_instance": per_instance,
        "harness_summary": harness_summary,
        "metrics_fallback_reason": reason,
        **solver_failure,
    }


def _compute_baseline_metrics(replication_dir: Path, instance_ids: list[str]) -> dict:
    baseline_summary = json.loads((replication_dir / "summary.json").read_text())
    baseline_metrics = json.loads((replication_dir / "metrics_breakdown.json").read_text())

    per_instance = baseline_metrics.get("per_instance", [])
    per_instance_by_id = {row["instance_id"]: row for row in per_instance if "instance_id" in row}
    if not per_instance_by_id:
        # Fallback for legacy files without per-instance details.
        n = len(instance_ids)
        return {
            "num_issues": int(baseline_summary["num_issues"]),
            "attempted_issue_count": int(baseline_summary.get("attempted_count", baseline_summary["num_issues"])),
            "resolved_issue_count": int(baseline_summary["resolved_count"]),
            "resolved_issue_rate": float(baseline_summary["resolved_rate"]),
            "resolved_issue_rate_attempted": float(baseline_summary["resolved_rate"]),
            "fail_to_pass_issue_success_count": int(baseline_metrics["fail_to_pass_issue_success_count"]),
            "fail_to_pass_issue_success_rate": float(baseline_metrics["fail_to_pass_issue_success_rate"]),
            "fail_to_pass_issue_success_rate_attempted": float(
                baseline_metrics["fail_to_pass_issue_success_rate"]
            ),
            "pass_to_pass_issue_success_count": int(baseline_metrics["pass_to_pass_issue_success_count"]),
            "pass_to_pass_issue_success_rate": float(baseline_metrics["pass_to_pass_issue_success_rate"]),
            "pass_to_pass_issue_success_rate_attempted": float(
                baseline_metrics["pass_to_pass_issue_success_rate"]
            ),
            "fail_to_pass_tests_passed": int(baseline_metrics["fail_to_pass_tests_passed"]),
            "fail_to_pass_tests_total": int(baseline_metrics["fail_to_pass_tests_total"]),
            "fail_to_pass_test_pass_rate": float(baseline_metrics["fail_to_pass_test_pass_rate"]),
            "pass_to_pass_tests_passed": int(baseline_metrics["pass_to_pass_tests_passed"]),
            "pass_to_pass_tests_total": int(baseline_metrics["pass_to_pass_tests_total"]),
            "pass_to_pass_test_pass_rate": float(baseline_metrics["pass_to_pass_test_pass_rate"]),
            "evaluation_failure_count": int(baseline_summary.get("evaluation_failures", 0)),
            "evaluation_failure_ids": [],
            "resolved_ids": baseline_summary.get("resolved_ids", []),
            "infrastructure_failure_count": int(baseline_summary.get("infrastructure_failures", 0)),
            "model_provider_failure_count": int(baseline_summary.get("model_provider_failures", 0)),
            "infrastructure_failure_ids": [],
            "model_provider_failure_ids": [],
            "per_instance": [],
            "baseline_slice_warning": (
                "Per-instance baseline metrics missing; using full summary for comparison."
            ),
            "num_issues_slice": n,
        }

    missing = [iid for iid in instance_ids if iid not in per_instance_by_id]
    if missing:
        raise ValueError(f"Baseline per-instance metrics missing IDs: {missing}")

    rows = [per_instance_by_id[iid] for iid in instance_ids]
    n = len(rows)
    resolved_count = sum(1 for x in rows if x.get("resolved"))
    f2p_issue_success_count = sum(1 for x in rows if x.get("fail_to_pass_issue_success"))
    p2p_issue_success_count = sum(1 for x in rows if x.get("pass_to_pass_issue_success"))
    f2p_tests_passed = sum(int(x.get("fail_to_pass_passed", 0)) for x in rows)
    f2p_tests_total = sum(int(x.get("fail_to_pass_total", 0)) for x in rows)
    p2p_tests_passed = sum(int(x.get("pass_to_pass_passed", 0)) for x in rows)
    p2p_tests_total = sum(int(x.get("pass_to_pass_total", 0)) for x in rows)
    resolved_ids = [x["instance_id"] for x in rows if x.get("resolved")]

    return {
        "num_issues": n,
        "attempted_issue_count": n,
        "resolved_issue_count": resolved_count,
        "resolved_issue_rate": (resolved_count / n) if n else 0.0,
        "resolved_issue_rate_attempted": (resolved_count / n) if n else 0.0,
        "fail_to_pass_issue_success_count": f2p_issue_success_count,
        "fail_to_pass_issue_success_rate": (f2p_issue_success_count / n) if n else 0.0,
        "fail_to_pass_issue_success_rate_attempted": (f2p_issue_success_count / n) if n else 0.0,
        "pass_to_pass_issue_success_count": p2p_issue_success_count,
        "pass_to_pass_issue_success_rate": (p2p_issue_success_count / n) if n else 0.0,
        "pass_to_pass_issue_success_rate_attempted": (p2p_issue_success_count / n) if n else 0.0,
        "fail_to_pass_tests_passed": f2p_tests_passed,
        "fail_to_pass_tests_total": f2p_tests_total,
        "fail_to_pass_test_pass_rate": (f2p_tests_passed / f2p_tests_total) if f2p_tests_total else 0.0,
        "pass_to_pass_tests_passed": p2p_tests_passed,
        "pass_to_pass_tests_total": p2p_tests_total,
        "pass_to_pass_test_pass_rate": (p2p_tests_passed / p2p_tests_total) if p2p_tests_total else 0.0,
        "evaluation_failure_count": int(baseline_summary.get("evaluation_failures", 0)),
        "evaluation_failure_ids": [],
        "resolved_ids": resolved_ids,
        "infrastructure_failure_count": int(baseline_summary.get("infrastructure_failures", 0)),
        "model_provider_failure_count": int(baseline_summary.get("model_provider_failures", 0)),
        "infrastructure_failure_ids": [],
        "model_provider_failure_ids": [],
        "per_instance": rows,
        "baseline_slice_source": str(replication_dir / "metrics_breakdown.json"),
    }


def _comparison_markdown(comparison: dict) -> str:
    baseline = comparison["baseline"]
    enhanced = comparison.get("enhanced")
    lines = [
        "# Verified-10 Baseline vs Enhanced Comparison",
        "",
        f"Generated at: {comparison['generated_at_utc']}",
        f"Enhancer agent: `{comparison['enhancer_agent']}`",
        "",
        "## Baseline (Sliced to Selected IDs)",
        f"- RESOLVED: {baseline['resolved_issue_count']}/{baseline['num_issues']} ({baseline['resolved_issue_rate']*100:.1f}%)",
        f"- FAIL_TO_PASS: {baseline['fail_to_pass_issue_success_count']}/{baseline['num_issues']} ({baseline['fail_to_pass_issue_success_rate']*100:.1f}%)",
        f"- PASS_TO_PASS: {baseline['pass_to_pass_issue_success_count']}/{baseline['num_issues']} ({baseline['pass_to_pass_issue_success_rate']*100:.1f}%)",
        "",
    ]

    if not enhanced:
        lines.extend(
            [
                "## Enhanced",
                "- Evaluation skipped and no existing reports were found.",
                "",
                "## Notes",
                "- Comparison deltas are unavailable without evaluation reports.",
            ]
        )
        return "\n".join(lines) + "\n"

    delta = comparison["delta"]
    lines.extend(
        [
            "## Enhanced",
            f"- Attempted (reports present): {enhanced['attempted_issue_count']}/{enhanced['num_issues']}",
            f"- RESOLVED: {enhanced['resolved_issue_count']}/{enhanced['num_issues']} ({enhanced['resolved_issue_rate']*100:.1f}%)",
            f"- RESOLVED (attempted-only): {enhanced['resolved_issue_rate_attempted']*100:.1f}%",
            f"- FAIL_TO_PASS: {enhanced['fail_to_pass_issue_success_count']}/{enhanced['num_issues']} ({enhanced['fail_to_pass_issue_success_rate']*100:.1f}%)",
            f"- PASS_TO_PASS: {enhanced['pass_to_pass_issue_success_count']}/{enhanced['num_issues']} ({enhanced['pass_to_pass_issue_success_rate']*100:.1f}%)",
            f"- Infrastructure failures: {enhanced['infrastructure_failure_count']}",
            f"- Model/provider failures: {enhanced['model_provider_failure_count']}",
            f"- Evaluation failures: {enhanced['evaluation_failure_count']}",
            "",
            "## Delta (Enhanced - Baseline)",
            f"- RESOLVED delta: {delta['resolved_issue_rate_delta']*100:+.1f} points",
            f"- FAIL_TO_PASS delta: {delta['fail_to_pass_issue_success_rate_delta']*100:+.1f} points",
            f"- PASS_TO_PASS delta: {delta['pass_to_pass_issue_success_rate_delta']*100:+.1f} points",
            "",
            "## Notes",
            f"- Baseline artifacts loaded from `{comparison['baseline_source']}`.",
            "- Enhanced run uses mini-SWE-agent + Devstral 2512 replication stack.",
        ]
    )
    return "\n".join(lines) + "\n"


def _derive_enhancement_cache_key(args: argparse.Namespace, instance_ids: list[str]) -> str:
    payload = {
        "enhancer_agent": args.enhancer_agent,
        "enhancer_model": args.enhancer_model,
        "enhancer_api_base": args.enhancer_api_base,
        "enhancer_parallel": args.enhancer_parallel,
        "instance_ids": instance_ids,
        "samples_json": str(args.samples_json.resolve()),
    }
    return _sha256_text(json.dumps(payload, sort_keys=True))[:16]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enhancer-agent", type=str, default="simple_enhancer")
    parser.add_argument("--max-issues", type=int, default=10)
    parser.add_argument("--output-tag", type=str, default="latest")
    parser.add_argument("--replication-dir", type=Path, default=DEFAULT_REPLICATION_DIR)
    parser.add_argument("--replication-selected-ids", type=Path, default=DEFAULT_REPLICATION_SELECTED_IDS)
    parser.add_argument("--dataset-name", type=str, default=DEFAULT_DATASET)
    parser.add_argument("--split", type=str, default=DEFAULT_SPLIT)
    parser.add_argument("--samples-json", type=Path, default=DEFAULT_SAMPLES_JSON)
    parser.add_argument("--selected-ids-file", type=Path, default=DEFAULT_SELECTED_IDS)
    parser.add_argument(
        "--results-root",
        type=Path,
        default=ROOT / "results" / "verified10_baseline_vs_enhanced",
    )
    parser.add_argument("--skip-prepare-samples", action="store_true")
    parser.add_argument("--skip-enhancement", action="store_true")
    parser.add_argument("--skip-solver", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--enhancer-api-base", type=str, default="http://127.0.0.1:18000/v1")
    parser.add_argument("--enhancer-api-key", type=str, default="local-devstral")
    parser.add_argument("--enhancer-model", type=str, default="Devstral-Small-2-24B-Instruct-2512")
    parser.add_argument("--enhancer-parallel", type=int, default=1)
    parser.add_argument("--enhancement-cache-key", type=str, default="")
    parser.add_argument("--disable-enhancement-cache", action="store_true")
    parser.add_argument("--solver-workers", type=int, default=1)
    parser.add_argument("--eval-workers", type=int, default=1)
    parser.add_argument("--eval-timeout", type=int, default=1800)
    parser.add_argument("--solver-timeout-retries", type=int, default=1)
    parser.add_argument("--solver-timeout-retry-delay-seconds", type=int, default=0)
    parser.add_argument("--max-enhanced-body-chars", type=int, default=2000)
    parser.add_argument("--max-enhancement-similarity", type=float, default=0.995)
    parser.add_argument("--allow-identical-enhancements", action="store_true")
    parser.add_argument("--require-native-enhancer", action="store_true")
    parser.add_argument("--expected-model-dir-name", type=str, default="")
    parser.add_argument(
        "--swebench-python",
        type=Path,
        default=DEFAULT_REPLICATION_DIR / ".venv312" / "bin" / "python",
    )
    parser.add_argument(
        "--mini-benchmark-config",
        type=Path,
        default=DEFAULT_REPLICATION_DIR
        / "mini-SWE-agent"
        / "src"
        / "minisweagent"
        / "config"
        / "benchmarks"
        / "swebench_backticks.yaml",
    )
    parser.add_argument(
        "--mini-model-override-config",
        type=Path,
        default=DEFAULT_REPLICATION_DIR / "config" / "devstral_vllm_override.yaml",
    )
    parser.add_argument(
        "--mini-model-class",
        type=str,
        default="minisweagent.models.litellm_textbased_model.LitellmTextbasedModel",
    )
    parser.add_argument(
        "--mini-extra-config",
        action="append",
        default=[],
        help="Additional mini-SWE-agent config specs appended as -c <spec>.",
    )
    args = parser.parse_args()

    experiment_dir = args.results_root / f"{args.enhancer_agent}__{args.output_tag}"
    log_dir = experiment_dir / "logs"
    commands_file = experiment_dir / "commands_run.md"
    enhancement_dir = experiment_dir / "enhancements"
    solver_output_dir = experiment_dir / "solver_run"
    enhanced_dataset_jsonl = experiment_dir / f"verified10_enhanced_{args.enhancer_agent}.jsonl"
    eval_report_dir = experiment_dir / "eval_reports"
    manifest_path = experiment_dir / "reproducibility_manifest.json"
    comparison_json = experiment_dir / "comparison_summary.json"
    comparison_md = experiment_dir / "comparison_summary.md"
    metrics_json = experiment_dir / "enhanced_metrics.json"

    experiment_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    if commands_file.exists():
        commands_file.unlink()
    commands_file.write_text("# Commands Run\n")

    run_id = f"verified10_{args.enhancer_agent}_{args.output_tag}".replace("-", "_")
    expected_model_dir_name = (
        args.expected_model_dir_name.strip()
        or _expected_model_dir_name_from_override(args.mini_model_override_config)
    )

    manifest: dict[str, Any] = {
        "started_at_utc": _utc_now(),
        "run_id": run_id,
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version,
        "git_commit": _get_git_commit(ROOT),
        "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        "paths": {
            "experiment_dir": str(experiment_dir),
            "log_dir": str(log_dir),
            "commands_file": str(commands_file),
            "enhanced_dataset_jsonl": str(enhanced_dataset_jsonl),
            "solver_output_dir": str(solver_output_dir),
            "eval_report_dir": str(eval_report_dir),
            "comparison_json": str(comparison_json),
            "comparison_md": str(comparison_md),
            "metrics_json": str(metrics_json),
        },
        "model_override_sha256": _sha256_file(args.mini_model_override_config),
        "benchmark_config_sha256": _sha256_file(args.mini_benchmark_config),
        "expected_model_dir_name": expected_model_dir_name,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))

    if not args.skip_prepare_samples:
        prep_cmd = [
            str(args.swebench_python),
            str(ROOT / "scripts" / "data" / "prepare_verified_10_samples_from_replication.py"),
            "--selected-ids",
            str(args.replication_selected_ids),
            "--dataset-name",
            args.dataset_name,
            "--split",
            args.split,
            "--output-samples",
            str(args.samples_json),
            "--output-instance-ids",
            str(args.selected_ids_file),
        ]
        _run_cmd("prepare_verified_sample", prep_cmd, ROOT, log_dir, commands_file)

    instance_ids = _load_ids(args.selected_ids_file)[: args.max_issues]
    manifest["selected_instance_ids"] = instance_ids

    enhancement_cache_key = args.enhancement_cache_key.strip() or _derive_enhancement_cache_key(
        args, instance_ids
    )
    manifest["enhancement_cache_key"] = enhancement_cache_key
    manifest_path.write_text(json.dumps(manifest, indent=2))

    if not args.skip_enhancement:
        enhance_env = dict(os.environ)
        enhance_env["OPENAI_COMPAT_BASE_URL"] = args.enhancer_api_base
        enhance_env["OPENAI_COMPAT_API_KEY"] = args.enhancer_api_key
        enhance_env["OPENAI_COMPAT_MODEL"] = args.enhancer_model
        # Native agent env vars
        enhance_env["TRAE_PROVIDER"] = "openai"
        enhance_env["TRAE_BASE_URL"] = args.enhancer_api_base
        enhance_env["TRAE_API_KEY"] = args.enhancer_api_key
        enhance_env["TRAE_MODEL"] = args.enhancer_model
        enhance_env["AIDER_MODEL"] = f"openai/{args.enhancer_model}"
        enhance_env["AIDER_API_BASE"] = args.enhancer_api_base
        enhance_env["AIDER_API_KEY"] = args.enhancer_api_key
        enhance_env["OPENAI_API_KEY"] = args.enhancer_api_key
        enhance_env["OPENAI_API_BASE"] = args.enhancer_api_base
        enhance_env["SWEAGENT_BASE_URL"] = args.enhancer_api_base
        enhance_env["SWEAGENT_API_KEY"] = args.enhancer_api_key
        enhance_env["SWEAGENT_MODEL"] = args.enhancer_model
        enhance_cmd = [
            sys.executable,
            str(ROOT / "scripts" / "enhancers" / "run_enhancement_benchmark.py"),
            "--agents",
            args.enhancer_agent,
            "--max-issues",
            str(len(instance_ids)),
            "--parallel",
            str(args.enhancer_parallel),
            "--samples",
            str(args.samples_json),
            "--output-dir",
            str(enhancement_dir),
            "--cache-key",
            enhancement_cache_key,
        ]
        if args.disable_enhancement_cache:
            enhance_cmd.append("--disable-cache")
        _run_cmd("run_enhancement", enhance_cmd, ROOT, log_dir, commands_file, env=enhance_env)

    selected_rows, enhancement_quality = _build_enhanced_dataset_jsonl(
        instance_ids=instance_ids,
        dataset_name=args.dataset_name,
        split=args.split,
        enhancement_dir=enhancement_dir,
        enhancer_agent=args.enhancer_agent,
        samples_json=args.samples_json,
        output_jsonl=enhanced_dataset_jsonl,
        max_body_chars=args.max_enhanced_body_chars,
        max_similarity=args.max_enhancement_similarity,
        allow_identical=args.allow_identical_enhancements,
        require_native=args.require_native_enhancer,
    )
    manifest["enhancement_quality"] = enhancement_quality

    filter_regex = _build_filter_regex(instance_ids)
    solver_status_by_instance: dict[str, str] = {}
    solver_timeout_retry_history: list[dict] = []

    if not args.skip_solver:
        solver_cmd = [
            str(args.swebench_python),
            str(ROOT / "scripts" / "solvers" / "run_mini_sweagent_jsonl.py"),
            "--dataset-jsonl",
            str(enhanced_dataset_jsonl),
            "--filter",
            filter_regex,
            "--workers",
            str(args.solver_workers),
            "--redo-existing",
            "--output",
            str(solver_output_dir),
            "--model-class",
            args.mini_model_class,
            "-c",
            str(args.mini_benchmark_config),
            "-c",
            str(args.mini_model_override_config),
        ]
        for cfg_spec in args.mini_extra_config:
            solver_cmd.extend(["-c", str(cfg_spec)])
        _run_cmd("run_mini_swe_agent_solver", solver_cmd, ROOT, log_dir, commands_file)

        latest_exit_file = _latest_exit_status_file(solver_output_dir)
        solver_status_by_instance.update(_load_exit_status_by_instance(latest_exit_file))
        timeout_ids = sorted(
            iid for iid in instance_ids if solver_status_by_instance.get(iid, "").lower() == "timeout"
        )

        for attempt_idx in range(1, args.solver_timeout_retries + 1):
            if not timeout_ids:
                break
            if args.solver_timeout_retry_delay_seconds > 0:
                time.sleep(args.solver_timeout_retry_delay_seconds)
            retry_cmd = list(solver_cmd)
            retry_cmd[retry_cmd.index("--filter") + 1] = _build_filter_regex(timeout_ids)
            _run_cmd(
                f"run_mini_swe_agent_solver_retry_{attempt_idx}",
                retry_cmd,
                ROOT,
                log_dir,
                commands_file,
            )
            latest_retry_exit = _latest_exit_status_file(solver_output_dir)
            retry_map = _load_exit_status_by_instance(latest_retry_exit)
            for iid in timeout_ids:
                if iid in retry_map:
                    solver_status_by_instance[iid] = retry_map[iid]
            timeout_ids = sorted(
                iid for iid in timeout_ids if solver_status_by_instance.get(iid, "").lower() == "timeout"
            )
            solver_timeout_retry_history.append(
                {
                    "attempt": attempt_idx,
                    "remaining_timeout_ids": timeout_ids,
                }
            )
    else:
        latest_exit_file = _latest_exit_status_file(solver_output_dir)
        solver_status_by_instance.update(_load_exit_status_by_instance(latest_exit_file))

    manifest["solver_status_by_instance"] = solver_status_by_instance
    manifest["solver_timeout_retry_history"] = solver_timeout_retry_history

    preds_json = solver_output_dir / "preds.json"
    if not preds_json.exists():
        raise FileNotFoundError(f"Missing predictions file: {preds_json}")

    eval_stdout_log: Path | None = None
    if not args.skip_eval:
        eval_cmd = [
            str(args.swebench_python),
            "-m",
            "swebench.harness.run_evaluation",
            "--dataset_name",
            args.dataset_name,
            "--split",
            args.split,
            "--predictions_path",
            str(preds_json),
            "--instance_ids",
            *instance_ids,
            "--max_workers",
            str(args.eval_workers),
            "--timeout",
            str(args.eval_timeout),
            "--run_id",
            run_id,
            "--report_dir",
            str(eval_report_dir),
        ]
        eval_stdout_log, _ = _run_cmd(
            "run_swebench_evaluation", eval_cmd, ROOT, log_dir, commands_file
        )
    else:
        candidate = log_dir / "run_swebench_evaluation.stdout.log"
        if candidate.exists():
            eval_stdout_log = candidate

    harness_summary = _parse_harness_summary_from_log(eval_stdout_log)
    run_eval_dir = ROOT / "logs" / "run_evaluation" / run_id
    has_eval_reports = run_eval_dir.exists() and any(p.is_dir() for p in run_eval_dir.iterdir())

    enhanced_metrics: dict | None = None
    if has_eval_reports:
        enhanced_metrics = _compute_metrics_from_reports(
            run_id=run_id,
            instance_ids=instance_ids,
            dataset_rows_by_id=selected_rows,
            expected_model_dir_name=expected_model_dir_name,
            harness_summary=harness_summary,
            solver_status_by_instance=solver_status_by_instance,
        )
    elif args.skip_eval:
        # True skip mode: do not fail if reports do not exist.
        enhanced_metrics = None
    else:
        enhanced_metrics = _compute_metrics_without_reports(
            instance_ids=instance_ids,
            dataset_rows_by_id=selected_rows,
            harness_summary=harness_summary,
            solver_status_by_instance=solver_status_by_instance,
            reason=(
                "No evaluation reports found for run_id; harness likely skipped per-instance "
                "evaluation (e.g., empty patches)."
            ),
        )

    baseline = _compute_baseline_metrics(args.replication_dir, instance_ids)

    comparison: dict[str, Any] = {
        "generated_at_utc": _utc_now(),
        "enhancer_agent": args.enhancer_agent,
        "instance_ids": instance_ids,
        "dataset_name": args.dataset_name,
        "split": args.split,
        "baseline_source": str(args.replication_dir),
        "baseline": baseline,
        "enhanced": enhanced_metrics,
        "harness_summary": harness_summary,
        "notes": [],
    }

    if enhanced_metrics:
        comparison["delta"] = {
            "resolved_issue_rate_delta": enhanced_metrics["resolved_issue_rate"]
            - baseline["resolved_issue_rate"],
            "fail_to_pass_issue_success_rate_delta": enhanced_metrics[
                "fail_to_pass_issue_success_rate"
            ]
            - baseline["fail_to_pass_issue_success_rate"],
            "pass_to_pass_issue_success_rate_delta": enhanced_metrics[
                "pass_to_pass_issue_success_rate"
            ]
            - baseline["pass_to_pass_issue_success_rate"],
            "resolved_issue_rate_attempted_delta": enhanced_metrics[
                "resolved_issue_rate_attempted"
            ]
            - baseline["resolved_issue_rate_attempted"],
        }
    else:
        comparison["delta"] = None
        comparison["notes"].append(
            "Evaluation was skipped and no existing reports were found; delta metrics unavailable."
        )

    comparison_json.write_text(json.dumps(comparison, indent=2))
    if enhanced_metrics is not None:
        metrics_json.write_text(json.dumps(enhanced_metrics, indent=2))
    else:
        metrics_json.write_text(json.dumps({"status": "evaluation_skipped_no_reports"}, indent=2))
    comparison_md.write_text(_comparison_markdown(comparison))

    manifest["ended_at_utc"] = _utc_now()
    manifest["commands_sha256"] = _sha256_file(commands_file)
    manifest["comparison_sha256"] = _sha256_file(comparison_json)
    manifest["metrics_sha256"] = _sha256_file(metrics_json)
    manifest["run_eval_dir"] = str(run_eval_dir)
    manifest["harness_summary"] = harness_summary
    manifest["enhanced_metrics_available"] = enhanced_metrics is not None
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(f"Experiment directory: {experiment_dir}")
    print(f"Instance IDs: {instance_ids}")
    print(
        f"Baseline RESOLVED: {baseline['resolved_issue_count']}/{baseline['num_issues']} "
        f"({baseline['resolved_issue_rate']*100:.1f}%)"
    )
    if enhanced_metrics:
        print(
            f"Enhanced RESOLVED: {enhanced_metrics['resolved_issue_count']}/{enhanced_metrics['num_issues']} "
            f"({enhanced_metrics['resolved_issue_rate']*100:.1f}%)"
        )
        print(
            f"Enhanced RESOLVED attempted-only: "
            f"{enhanced_metrics['resolved_issue_rate_attempted']*100:.1f}%"
        )
    else:
        print("Enhanced metrics unavailable (evaluation skipped and no reports found).")
    print(f"Comparison summary: {comparison_json}")
    print(f"Markdown summary: {comparison_md}")
    print(f"Reproducibility manifest: {manifest_path}")


if __name__ == "__main__":
    main()
