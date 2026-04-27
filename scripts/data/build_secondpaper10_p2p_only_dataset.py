#!/usr/bin/env python3
"""Build a deterministic 10-issue second-paper dataset with P2P-only tests.

Selection rule:
- FAIL_TO_PASS_count == 0
- PASS_TO_PASS_count > 0

Inputs:
1) Derived Flask/Requests instances (already contain FAIL_TO_PASS/PASS_TO_PASS lists)
2) Scikit raw instances + baseline/gold run logs
3) No-sklearn raw instances + baseline/gold run logs

Outputs (under data/samples/second_paper_final_10_p2p_only):
- final_10_instances_p2p_only.jsonl
- secondpaper10_p2p_only_instance_ids.txt
- secondpaper10_p2p_only_samples.json
- derivation_summary.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _detect_repo_root() -> Path:
    script_path = Path(__file__).resolve()
    direct_root = script_path.parent.parent.parent
    if (direct_root / "scripts").exists() and (direct_root / "src").exists():
        return direct_root
    parent_root = direct_root.parent
    if (parent_root / "scripts").exists() and (parent_root / "src").exists():
        return parent_root
    raise RuntimeError(f"Could not detect repository root from {script_path}.")


ROOT = _detect_repo_root()
sys.path.insert(0, str(ROOT))

from swebench.harness.grading import get_logs_eval, test_failed, test_passed
from swebench.harness.test_spec.test_spec import make_test_spec


DEFAULT_OUTPUT_DIR = ROOT / "data" / "samples" / "second_paper_final_10_p2p_only"

DEFAULT_SKLEARN_INSTANCES = (
    ROOT / "data" / "samples" / "second_paper_sklearn_exact_f2p_p2p_v1" / "custom_instances_raw.jsonl"
)
DEFAULT_SKLEARN_BASELINE_RUN_ID = "secondpaper_custom_baseline_probe_second_paper_sklearn_exact_f2p_p2p_v1"
DEFAULT_SKLEARN_GOLD_RUN_ID = "secondpaper_custom_gold_probe_second_paper_sklearn_exact_f2p_p2p_v1"

DEFAULT_NO_SKLEARN_INSTANCES = (
    ROOT / "data" / "samples" / "second_paper_no_sklearn_exact_f2p_p2p_v1" / "custom_instances_raw.jsonl"
)
DEFAULT_NO_SKLEARN_BASELINE_RUN_ID = "secondpaper_custom_baseline_probe_second_paper_no_sklearn_exact_f2p_p2p_v2"
DEFAULT_NO_SKLEARN_GOLD_RUN_ID = "secondpaper_custom_gold_probe_second_paper_no_sklearn_exact_f2p_p2p_v2"

DEFAULT_FLASK_DERIVED_JSONL = (
    ROOT
    / "data"
    / "samples"
    / "second_paper_flask_requests_exact_f2p_p2p_v2"
    / "custom_instances_with_f2p_p2p.jsonl"
)

BASELINE_MODEL_NAME = "baseline_noop_patch_probe"
GOLD_MODEL_NAME = "gold_patch_probe"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _model_dir_name(model_name: str) -> str:
    return model_name.replace("/", "__")


def _derive_sets_from_runs(
    *,
    instances: list[dict[str, Any]],
    baseline_run_id: str,
    gold_run_id: str,
    source_name: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    baseline_dir = ROOT / "logs" / "run_evaluation" / baseline_run_id / _model_dir_name(BASELINE_MODEL_NAME)
    gold_dir = ROOT / "logs" / "run_evaluation" / gold_run_id / _model_dir_name(GOLD_MODEL_NAME)

    out_instances: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []

    for inst in instances:
        iid = inst["instance_id"]
        b_log = baseline_dir / iid / "test_output.txt"
        g_log = gold_dir / iid / "test_output.txt"

        if not b_log.exists() or not g_log.exists():
            summary.append(
                {
                    "instance_id": iid,
                    "source": source_name,
                    "error": "missing_test_output",
                    "baseline_log_exists": b_log.exists(),
                    "gold_log_exists": g_log.exists(),
                }
            )
            continue

        test_spec = make_test_spec(inst)
        b_status, b_ok = get_logs_eval(test_spec, str(b_log))
        g_status, g_ok = get_logs_eval(test_spec, str(g_log))

        if not b_ok or not g_ok:
            summary.append(
                {
                    "instance_id": iid,
                    "source": source_name,
                    "error": "unparseable_test_output",
                    "baseline_log_ok": b_ok,
                    "gold_log_ok": g_ok,
                }
            )
            continue

        all_tests = sorted(set(b_status.keys()) | set(g_status.keys()))
        fail_to_pass: list[str] = []
        pass_to_pass: list[str] = []
        fail_to_fail: list[str] = []
        pass_to_fail: list[str] = []

        for test_name in all_tests:
            b_pass = test_passed(test_name, b_status)
            g_pass = test_passed(test_name, g_status)
            b_fail = test_failed(test_name, b_status)
            g_fail = test_failed(test_name, g_status)

            if b_fail and g_pass:
                fail_to_pass.append(test_name)
            elif b_pass and g_pass:
                pass_to_pass.append(test_name)
            elif b_fail and g_fail:
                fail_to_fail.append(test_name)
            elif b_pass and g_fail:
                pass_to_fail.append(test_name)

        updated = dict(inst)
        updated.pop("_baseline_patch", None)
        updated["FAIL_TO_PASS"] = fail_to_pass
        updated["PASS_TO_PASS"] = pass_to_pass

        out_instances.append(updated)
        summary.append(
            {
                "instance_id": iid,
                "source": source_name,
                "FAIL_TO_PASS_count": len(fail_to_pass),
                "PASS_TO_PASS_count": len(pass_to_pass),
                "FAIL_TO_FAIL_count": len(fail_to_fail),
                "PASS_TO_FAIL_count": len(pass_to_fail),
            }
        )

    return out_instances, summary


def _normalize_repo_name(row: dict[str, Any]) -> str:
    repo = row.get("repo")
    if isinstance(repo, str) and "/" in repo:
        return repo
    owner = row.get("pr_owner")
    repo_name = row.get("pr_repo")
    if isinstance(owner, str) and isinstance(repo_name, str):
        return f"{owner}/{repo_name}"
    iid = row.get("instance_id", "")
    m = re.match(r"([^_]+)__([^-]+)-\d+$", iid)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return ""


def _extract_title(problem_statement: str) -> str:
    for line in (problem_statement or "").splitlines():
        line = line.strip()
        if line:
            return line[:200]
    return ""


def _parse_issue_number(instance_id: str, fallback: Any = None) -> int:
    m = re.search(r"-(\d+)$", instance_id or "")
    if m:
        return int(m.group(1))
    if isinstance(fallback, int):
        return fallback
    if isinstance(fallback, str) and fallback.isdigit():
        return int(fallback)
    raise ValueError(f"Cannot parse issue number for instance_id={instance_id}")


def _to_sample_issue(row: dict[str, Any]) -> dict[str, Any]:
    repo_name = _normalize_repo_name(row)
    if not repo_name:
        raise ValueError(f"Could not infer repo name for {row.get('instance_id')}")
    owner, repo = repo_name.split("/", 1)
    issue_number = _parse_issue_number(row.get("instance_id", ""), row.get("issue_number"))
    problem_statement = row.get("problem_statement", "") or row.get("body", "")

    return {
        "repo_name": repo_name,
        "issue_number": issue_number,
        "issue_id": f"{repo_name}#{issue_number}",
        "title": _extract_title(problem_statement),
        "body": problem_statement,
        "problem_statement": problem_statement,
        "pr_owner": owner,
        "pr_repo": repo,
        "pr_base_sha": row.get("base_commit", ""),
        "base_commit": row.get("base_commit", ""),
        "instance_id": row["instance_id"],
        "FAIL_TO_PASS": row.get("FAIL_TO_PASS", []),
        "PASS_TO_PASS": row.get("PASS_TO_PASS", []),
        "pr_files": row.get("pr_files", []),
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-issues", type=int, default=10)
    parser.add_argument("--sklearn-instances", type=Path, default=DEFAULT_SKLEARN_INSTANCES)
    parser.add_argument("--sklearn-baseline-run-id", type=str, default=DEFAULT_SKLEARN_BASELINE_RUN_ID)
    parser.add_argument("--sklearn-gold-run-id", type=str, default=DEFAULT_SKLEARN_GOLD_RUN_ID)
    parser.add_argument("--no-sklearn-instances", type=Path, default=DEFAULT_NO_SKLEARN_INSTANCES)
    parser.add_argument("--no-sklearn-baseline-run-id", type=str, default=DEFAULT_NO_SKLEARN_BASELINE_RUN_ID)
    parser.add_argument("--no-sklearn-gold-run-id", type=str, default=DEFAULT_NO_SKLEARN_GOLD_RUN_ID)
    parser.add_argument("--flask-derived-jsonl", type=Path, default=DEFAULT_FLASK_DERIVED_JSONL)
    args = parser.parse_args()

    flask_rows = _load_jsonl(args.flask_derived_jsonl) if args.flask_derived_jsonl.exists() else []
    flask_summary = [
        {
            "instance_id": row["instance_id"],
            "source": "flask_requests_v2",
            "FAIL_TO_PASS_count": len(row.get("FAIL_TO_PASS", []) or []),
            "PASS_TO_PASS_count": len(row.get("PASS_TO_PASS", []) or []),
        }
        for row in flask_rows
    ]

    sklearn_rows, sklearn_summary = _derive_sets_from_runs(
        instances=_load_jsonl(args.sklearn_instances),
        baseline_run_id=args.sklearn_baseline_run_id,
        gold_run_id=args.sklearn_gold_run_id,
        source_name="sklearn_v1",
    )

    no_sklearn_rows, no_sklearn_summary = _derive_sets_from_runs(
        instances=_load_jsonl(args.no_sklearn_instances),
        baseline_run_id=args.no_sklearn_baseline_run_id,
        gold_run_id=args.no_sklearn_gold_run_id,
        source_name="no_sklearn_v2",
    )

    merged_by_id: dict[str, dict[str, Any]] = {}
    merged_summary_by_id: dict[str, dict[str, Any]] = {}
    for row in flask_rows + sklearn_rows + no_sklearn_rows:
        merged_by_id[row["instance_id"]] = row
    for item in flask_summary + sklearn_summary + no_sklearn_summary:
        merged_summary_by_id[item["instance_id"]] = item

    p2p_only_rows = [
        row
        for row in merged_by_id.values()
        if len(row.get("FAIL_TO_PASS", []) or []) == 0 and len(row.get("PASS_TO_PASS", []) or []) > 0
    ]
    p2p_only_rows = sorted(p2p_only_rows, key=lambda r: r["instance_id"])

    if len(p2p_only_rows) < args.max_issues:
        raise RuntimeError(
            f"Only {len(p2p_only_rows)} P2P-only rows available; need {args.max_issues}. "
            "Complete more baseline+gold derivations first."
        )

    selected_rows = p2p_only_rows[: args.max_issues]
    selected_ids = [row["instance_id"] for row in selected_rows]
    sample_issues = [_to_sample_issue(row) for row in selected_rows]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    dataset_jsonl = args.output_dir / "final_10_instances_p2p_only.jsonl"
    selected_ids_path = args.output_dir / "secondpaper10_p2p_only_instance_ids.txt"
    samples_json = args.output_dir / "secondpaper10_p2p_only_samples.json"
    summary_json = args.output_dir / "derivation_summary.json"

    _write_jsonl(dataset_jsonl, selected_rows)
    selected_ids_path.write_text("\n".join(selected_ids) + "\n")
    samples_json.write_text(
        json.dumps(
            {
                "metadata": {
                    "description": "Second-paper P2P-only 10-issue dataset (FAIL_TO_PASS empty, PASS_TO_PASS non-empty)",
                    "count": len(sample_issues),
                    "selection_rule": "FAIL_TO_PASS_count == 0 and PASS_TO_PASS_count > 0",
                    "selection_order": "lexicographic instance_id",
                },
                "issues": sample_issues,
            },
            indent=2,
        )
    )

    summary_payload = {
        "generated_from": {
            "flask_derived_jsonl": str(args.flask_derived_jsonl),
            "sklearn_instances": str(args.sklearn_instances),
            "sklearn_baseline_run_id": args.sklearn_baseline_run_id,
            "sklearn_gold_run_id": args.sklearn_gold_run_id,
            "no_sklearn_instances": str(args.no_sklearn_instances),
            "no_sklearn_baseline_run_id": args.no_sklearn_baseline_run_id,
            "no_sklearn_gold_run_id": args.no_sklearn_gold_run_id,
        },
        "counts": {
            "merged_unique_instances": len(merged_by_id),
            "p2p_only_candidates": len(p2p_only_rows),
            "selected": len(selected_rows),
        },
        "selected_instance_ids": selected_ids,
        "per_instance_summary": sorted(merged_summary_by_id.values(), key=lambda x: x["instance_id"]),
        "output_files": {
            "dataset_jsonl": str(dataset_jsonl),
            "selected_ids": str(selected_ids_path),
            "samples_json": str(samples_json),
        },
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2))

    print(f"Wrote dataset: {dataset_jsonl}")
    print(f"Wrote IDs: {selected_ids_path}")
    print(f"Wrote samples: {samples_json}")
    print(f"Wrote summary: {summary_json}")
    print("Selected instance IDs:")
    for iid in selected_ids:
        print(f"  - {iid}")


if __name__ == "__main__":
    main()

