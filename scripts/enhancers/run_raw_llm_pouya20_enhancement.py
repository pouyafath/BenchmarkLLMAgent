#!/usr/bin/env python3
"""Generate fresh raw-LLM enhanced Pouya-20 issue text.

This is intentionally not a native agent. It calls the direct LLM enhancer once
per issue and writes raw evidence plus a solver-ready enhanced dataset.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.workflows.run_pouya20_gpt54mini import _load_openai_api_key  # noqa: E402

DEFAULT_VALIDATED = ROOT / "runs/pouya_final20b_20260505_050130/validated_instances.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "runs/raw_llm_pouya20_20260511"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def _checks(original: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    original_body = original.get("problem_statement") or original.get("body") or ""
    enhanced_body = result.get("enhanced_body") or ""
    meta = result.get("enhancement_metadata") or {}
    return {
        "enhancer_type": meta.get("enhancer_type"),
        "agent_id": meta.get("agent_id"),
        "body_changed": enhanced_body.strip() != original_body.strip(),
        "enhanced_body_len": len(enhanced_body),
        "original_body_len": len(original_body),
        "original_preserved": bool(meta.get("original_preserved")),
        "timeout_contaminated": "timed out" in enhanced_body.lower() or "timeout" in str(meta.get("error", "")).lower(),
    }


def _enhance_one(issue: dict[str, Any], output_dir: Path, strategy: str) -> dict[str, Any]:
    enhancer_mod = importlib.import_module("src.enhancers.ready_to_use.llm_append_enhancer")
    instance_id = issue["instance_id"]
    start = time.time()
    try:
        result = enhancer_mod.enhance_issue(issue, strategy=strategy)
    except Exception as exc:
        result = {
            "enhanced_title": issue.get("title") or instance_id,
            "enhanced_body": issue.get("problem_statement") or issue.get("body") or "",
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "raw_llm",
                "strategy": strategy,
                "error": str(exc),
            },
        }
    meta = result.setdefault("enhancement_metadata", {})
    meta["agent_id"] = "raw_llm"
    meta["raw_llm_strategy"] = strategy
    meta["fresh_run"] = True
    meta["generated_at"] = datetime.now(timezone.utc).isoformat()
    meta["wall_elapsed_s"] = time.time() - start

    raw = {
        "instance_id": instance_id,
        "agent": "raw_llm",
        "strategy": strategy,
        "original_title": issue.get("title") or instance_id,
        "original_body": issue.get("problem_statement") or issue.get("body") or "",
        "result": result,
        "checks": _checks(issue, result),
    }
    raw_path = output_dir / "raw_results" / f"raw_llm__{instance_id}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validated", type=Path, default=DEFAULT_VALIDATED)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model", default=os.environ.get("RAW_LLM_MODEL", "gpt-5.4-mini"))
    parser.add_argument("--base-url", default=os.environ.get("RAW_LLM_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--strategy", default="append_analysis", choices=["append_analysis", "extract_highlight", "hybrid"])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-body-chars", type=int, default=int(os.environ.get("RAW_LLM_MAX_BODY_CHARS", "120000")))
    parser.add_argument("--instance-ids", default="", help="Optional comma-separated subset to regenerate")
    parser.add_argument("--redo", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("OPENAI_API_KEY_FILE", str(ROOT / ".claude/settings.local.json"))
    api_key = _load_openai_api_key()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY or OPENAI_API_KEY_FILE is required")
    os.environ["OPENAI_COMPAT_BASE_URL"] = args.base_url.rstrip("/")
    os.environ["OPENAI_COMPAT_API_KEY"] = api_key
    os.environ["OPENAI_COMPAT_MODEL"] = args.model
    os.environ["USE_OLLAMA"] = "0"
    os.environ["LLM_APPEND_MAX_BODY_CHARS"] = str(args.max_body_chars)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = [_solver_ready(row) for row in _load_jsonl(args.validated)]
    requested_ids = {iid.strip() for iid in args.instance_ids.split(",") if iid.strip()}
    rows_to_run = [row for row in rows if not requested_ids or row["instance_id"] in requested_ids]
    raw_by_id: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []

    def run_or_load(row: dict[str, Any]) -> dict[str, Any]:
        raw_path = args.output_dir / "raw_results" / f"raw_llm__{row['instance_id']}.json"
        if raw_path.exists() and not args.redo:
            return json.loads(raw_path.read_text(encoding="utf-8"))
        return _enhance_one(row, args.output_dir, args.strategy)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_or_load, row): row for row in rows_to_run}
        for idx, future in enumerate(as_completed(futures), start=1):
            row = futures[future]
            raw = future.result()
            raw_by_id[row["instance_id"]] = raw
            checks = raw.get("checks") or {}
            ok = (
                checks.get("enhancer_type") != "error"
                and checks.get("body_changed")
                and checks.get("enhanced_body_len", 0) >= checks.get("original_body_len", 0)
                and not checks.get("timeout_contaminated")
            )
            if not ok:
                failures.append({"instance_id": row["instance_id"], "checks": checks})
            print(
                f"[{idx}/{len(rows_to_run)}] {row['instance_id']} "
                f"type={checks.get('enhancer_type')} len={checks.get('enhanced_body_len')} "
                f"changed={checks.get('body_changed')}",
                flush=True,
            )

    for row in rows:
        if row["instance_id"] in raw_by_id:
            continue
        raw_path = args.output_dir / "raw_results" / f"raw_llm__{row['instance_id']}.json"
        if raw_path.exists():
            raw_by_id[row["instance_id"]] = json.loads(raw_path.read_text(encoding="utf-8"))
        else:
            failures.append({"instance_id": row["instance_id"], "checks": {"missing_raw_result": True}})

    enhanced_rows: list[dict[str, Any]] = []
    for row in rows:
        raw = raw_by_id[row["instance_id"]]
        result = raw["result"]
        out = dict(row)
        out["original_problem_statement"] = row.get("problem_statement", "")
        out["problem_statement"] = result.get("enhanced_body") or row.get("problem_statement", "")
        out["enhanced_title"] = result.get("enhanced_title") or row.get("title") or row["instance_id"]
        out["enhancement_metadata"] = {
            **(result.get("enhancement_metadata") or {}),
            "source_raw_result": str(args.output_dir / "raw_results" / f"raw_llm__{row['instance_id']}.json"),
            "enhancer_agent": "raw_llm",
        }
        enhanced_rows.append(_solver_ready(out))

    dataset_path = args.output_dir / "datasets/raw_llm.jsonl"
    _write_jsonl(dataset_path, enhanced_rows)
    summary = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(args.output_dir),
        "validated": str(args.validated),
        "dataset": str(dataset_path),
        "model": args.model,
        "base_url": args.base_url,
        "strategy": args.strategy,
        "total": len(rows),
        "failures": failures,
        "raw_results_dir": str(args.output_dir / "raw_results"),
    }
    (args.output_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(dataset_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
