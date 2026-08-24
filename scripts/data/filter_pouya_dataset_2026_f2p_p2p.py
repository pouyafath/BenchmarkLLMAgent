#!/usr/bin/env python3
"""Build a SWE-bench-style Pouya subset with non-empty F2P and P2P tests.

This is a deterministic, offline filter over
data/samples/pouya_dataset_2026/raw_candidates.jsonl.  It does not run
RepoLaunch or executable validation.  The FAIL_TO_PASS and PASS_TO_PASS labels
are derived from the row's test_patch:

- FAIL_TO_PASS: newly added pytest test functions in the test patch.
- PASS_TO_PASS: existing pytest test functions visible in unchanged diff
  context lines, excluding any F2P tests.

Rows are kept only when both lists are non-empty.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "data" / "samples" / "pouya_dataset_2026"
DEFAULT_INPUT = DATASET_DIR / "raw_candidates.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "samples" / "pouya_dataset_2026_swebench_style_f2p_p2p"

TEST_FILE_RE = re.compile(r"(?:^|/)tests?[/_]|test_[^/]*\.py$|_test\.py$", re.IGNORECASE)
TEST_DEF_RE = re.compile(r"(?:async\s+)?def\s+(test_\w+)")
CLASS_RE = re.compile(r"class\s+(\w+)")


def is_test_file(path: str) -> bool:
    return bool(TEST_FILE_RE.search(path))


def add_unique(values: list[str], value: str | None) -> None:
    if value and value not in values:
        values.append(value)


def test_node(file_path: str, func_name: str, class_name: str | None) -> str:
    if class_name:
        return f"{file_path}::{class_name}::{func_name}"
    return f"{file_path}::{func_name}"


def parse_test_patch(test_patch: str) -> tuple[list[str], list[str], list[str]]:
    """Return derived (f2p, p2p, changed_test_files) from a unified diff."""
    fail_to_pass: list[str] = []
    pass_to_pass: list[str] = []
    changed_files: list[str] = []

    current_file: str | None = None
    current_class: str | None = None

    for raw_line in test_patch.splitlines():
        if raw_line.startswith("diff --git"):
            current_file = None
            current_class = None
            match = re.search(r" b/(.+)$", raw_line)
            if match and is_test_file(match.group(1)):
                current_file = match.group(1)
                add_unique(changed_files, current_file)
            continue

        if raw_line.startswith("+++ b/"):
            path = raw_line[len("+++ b/") :]
            current_file = path if is_test_file(path) else None
            current_class = None
            if current_file:
                add_unique(changed_files, current_file)
            continue

        if not current_file:
            continue

        if raw_line.startswith("@@"):
            current_class = None
            tail = raw_line.split("@@", 2)[-1].strip() if raw_line.count("@@") >= 2 else ""
            class_match = CLASS_RE.search(tail)
            if class_match:
                current_class = class_match.group(1)
            continue

        if not raw_line or raw_line[0] not in " +":
            continue

        prefix = raw_line[0]
        content = raw_line[1:]
        stripped = content.strip()
        if not stripped:
            continue

        indent = len(content) - len(content.lstrip(" \t"))
        class_match = CLASS_RE.match(stripped)
        if class_match and indent == 0:
            current_class = class_match.group(1)
            continue

        test_match = TEST_DEF_RE.match(stripped)
        if not test_match:
            continue

        class_name = current_class if indent > 0 else None
        node = test_node(current_file, test_match.group(1), class_name)
        if prefix == "+":
            add_unique(fail_to_pass, node)
        else:
            add_unique(pass_to_pass, node)

    pass_to_pass = [node for node in pass_to_pass if node not in set(fail_to_pass)]
    return fail_to_pass, pass_to_pass, changed_files


def compute_difficulty(patch: str) -> dict[str, int]:
    files: set[str] = set()
    hunks = 0
    lines = 0
    for line in patch.splitlines():
        if line.startswith("diff --git"):
            parts = line.split(" b/", 1)
            if len(parts) == 2:
                files.add(parts[1])
        elif line.startswith("@@"):
            hunks += 1
        elif line.startswith("+") and not line.startswith("+++"):
            lines += 1
        elif line.startswith("-") and not line.startswith("---"):
            lines += 1
    return {"files": len(files), "hunks": hunks, "lines": lines}


def make_test_cmd(tests: list[str]) -> str:
    return "pytest -rA " + " ".join(tests)


def image_name(instance_id: str) -> str:
    name = instance_id.replace("__", "_1776_").lower()
    return f"starryzhang/sweb.eval.x86_64.{name}:latest"


def parse_pr_files_from_patch(patch: str) -> list[str]:
    files: list[str] = []
    for line in patch.splitlines():
        if not line.startswith("diff --git"):
            continue
        parts = line.split(" b/", 1)
        if len(parts) == 2:
            add_unique(files, parts[1])
    return files


def parse_owner_repo(instance_id: str, repo: str) -> tuple[str, str]:
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return owner, name
    match = re.match(r"^([^_]+)__([^-]+)", instance_id)
    if match:
        return match.group(1), match.group(2)
    return repo, repo


def parse_issue_number(instance_id: str, pull_number: Any, issue_numbers: Any) -> int:
    if isinstance(issue_numbers, list) and issue_numbers:
        try:
            return int(str(issue_numbers[0]).strip())
        except (TypeError, ValueError):
            pass
    try:
        return int(str(pull_number).strip())
    except (TypeError, ValueError):
        pass
    match = re.search(r"-(\d+)$", instance_id)
    return int(match.group(1)) if match else 0


def swe_live_to_sample(row: dict[str, Any]) -> dict[str, Any]:
    repo = row.get("repo", "")
    instance_id = row.get("instance_id", "")
    owner, repo_name = parse_owner_repo(instance_id, repo)
    issue_num = parse_issue_number(instance_id, row.get("pull_number", ""), row.get("issue_numbers") or [])
    problem_statement = row.get("problem_statement", "") or ""
    title_lines = [line.strip() for line in problem_statement.splitlines() if line.strip()]
    title = title_lines[0] if title_lines else instance_id
    try:
        pr_number = int(str(row.get("pull_number", "")).strip())
    except (TypeError, ValueError):
        pr_number = issue_num
    return {
        "repo_name": f"{owner}/{repo_name}",
        "issue_number": issue_num,
        "issue_id": instance_id,
        "title": title,
        "body": problem_statement,
        "pr_owner": owner,
        "pr_repo": repo_name,
        "pr_number": pr_number,
        "pr_base_sha": row.get("base_commit", "") or "",
        "pr_files": parse_pr_files_from_patch(row.get("patch", "") or ""),
        "ground_truth_patch": row.get("patch", "") or "",
        "_swe_live_instance_id": instance_id,
        "_swe_live_created_at": str(row.get("created_at", "")),
    }


def normalize_row(row: dict[str, Any], f2p: list[str], p2p: list[str], files: list[str]) -> dict[str, Any]:
    out = dict(row)
    out["FAIL_TO_PASS"] = f2p
    out["PASS_TO_PASS"] = p2p
    out["FAIL_TO_PASS_count"] = len(f2p)
    out["PASS_TO_PASS_count"] = len(p2p)
    out["log_parser"] = out.get("log_parser") or "pytest"
    out["version"] = out.get("version") or "live"
    out["environment_setup_commit"] = out.get("environment_setup_commit") or out.get("base_commit", "")
    out["image_name"] = out.get("image_name") or image_name(out["instance_id"])
    out["difficulty"] = out.get("difficulty") or compute_difficulty(out.get("patch", ""))
    out["commit_url"] = out.get("commit_url") or f"https://github.com/{out['repo']}/tree/{out.get('base_commit', '')}"
    out["all_hints_text"] = out.get("all_hints_text") or out.get("hints_text", "")
    out["test_cmds"] = out.get("test_cmds") or [make_test_cmd(f2p + p2p)]
    out["f2p_p2p_derivation"] = {
        "method": "offline_test_patch_diff_parse",
        "source_dataset": str(DEFAULT_INPUT.relative_to(ROOT)),
        "changed_test_files": files,
        "note": (
            "F2P/P2P were derived from test_patch structure without executable "
            "pre/post validation."
        ),
    }
    return out


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_readme(path: Path, summary: dict[str, Any]) -> None:
    text = f"""# Pouya Dataset 2026 SWE-bench-Style F2P/P2P Subset

This folder contains a filtered subset of `data/samples/pouya_dataset_2026/raw_candidates.jsonl`.

Rows are kept only when the offline parser can derive both:

- non-empty `FAIL_TO_PASS`
- non-empty `PASS_TO_PASS`

The labels are derived from each row's `test_patch`; they are not the result of
full RepoLaunch executable validation.

Important validation caveat:

- This subset is an input queue for RepoLaunch plus SWE-bench-Live validation,
  not a final validated benchmark split.
- The offline parser can miss pytest class qualification when a diff hunk is
  inside a class but the class line is not present in the hunk context.
- Some rows with derived P2P can still validate to zero executable P2P tests if
  the test patch causes pre-patch collection errors. Keep only rows whose
  executable validation output has both non-empty `FAIL_TO_PASS` and
  `PASS_TO_PASS`.

## Files

- `dataset.jsonl`: SWE-bench-style rows with F2P/P2P fields.
- `instance_ids.txt`: selected instance IDs.
- `samples.json`: issue-runner-friendly projection.
- `summary.json`: counts and filter metadata.

## Counts

- Input rows: {summary["input_rows"]}
- Output rows: {summary["output_rows"]}
- Unique output repos: {summary["unique_repos"]}
- Rows with derived F2P but no derived P2P: {summary["rejection_reasons"].get("no_p2p", 0)}
- Rows with no derived F2P: {summary["rejection_reasons"].get("no_f2p", 0)}

## Criteria

- Source row comes from the Pouya 2026 raw candidate set.
- Code patch and test patch are present.
- Linked issue date policy is inherited from the raw candidate set: `>= 2025-05-01`.
- No description-quality filter is applied.
- `FAIL_TO_PASS` and `PASS_TO_PASS` are both non-empty after offline derivation.
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-rows", type=int, default=None)
    args = parser.parse_args()

    rows = read_jsonl(args.input)
    selected: list[dict[str, Any]] = []
    rejection_reasons: Counter[str] = Counter()

    for row in rows:
        if not row.get("patch", "").strip():
            rejection_reasons["no_patch"] += 1
            continue
        if not row.get("test_patch", "").strip():
            rejection_reasons["no_test_patch"] += 1
            continue

        f2p, p2p, changed_files = parse_test_patch(row.get("test_patch", ""))
        if not f2p:
            rejection_reasons["no_f2p"] += 1
            continue
        if not p2p:
            rejection_reasons["no_p2p"] += 1
            continue

        selected.append(normalize_row(row, f2p, p2p, changed_files))
        if args.max_rows is not None and len(selected) >= args.max_rows:
            break

    args.output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = args.output_dir / "dataset.jsonl"
    ids_path = args.output_dir / "instance_ids.txt"
    samples_path = args.output_dir / "samples.json"
    summary_path = args.output_dir / "summary.json"
    readme_path = args.output_dir / "README.md"

    write_jsonl(dataset_path, selected)
    ids_path.write_text("\n".join(row["instance_id"] for row in selected) + "\n", encoding="utf-8")

    samples = [swe_live_to_sample(row) for row in selected]
    samples_payload = {
        "metadata": {
            "description": "Pouya Dataset 2026 SWE-bench-style subset with derived F2P/P2P tests",
            "source": str(args.input.relative_to(ROOT)),
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "count": len(samples),
            "filter": "FAIL_TO_PASS > 0 AND PASS_TO_PASS > 0, no description-quality filter",
            "derivation": "offline test_patch diff parse; not executable validation",
        },
        "issues": samples,
    }
    samples_path.write_text(json.dumps(samples_payload, indent=2, sort_keys=True), encoding="utf-8")

    repo_counts = Counter(row["repo"] for row in selected)
    quality_counts = Counter(row.get("quality_bucket", "unknown") for row in selected)
    summary = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": str(args.input.relative_to(ROOT)),
        "output_dir": str(args.output_dir.relative_to(ROOT)),
        "input_rows": len(rows),
        "output_rows": len(selected),
        "unique_repos": len(repo_counts),
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
        "quality_bucket_counts": dict(sorted(quality_counts.items())),
        "top_repos": repo_counts.most_common(25),
        "criteria": {
            "source": "pouya_dataset_2026 raw candidates",
            "issue_date_cutoff": ">= 2025-05-01 inherited from source",
            "description_quality_filter": False,
            "requires_non_empty_FAIL_TO_PASS": True,
            "requires_non_empty_PASS_TO_PASS": True,
            "validation_level": "offline heuristic from test_patch, not executable validation",
            "known_limitations": [
                "pytest class qualification can be missed when class context is absent from the diff hunk",
                "rows must still pass executable validation with non-empty F2P and P2P before use as benchmark instances",
            ],
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    build_readme(readme_path, summary)

    print(f"Input rows: {len(rows)}")
    print(f"Output rows: {len(selected)}")
    print(f"Unique repos: {len(repo_counts)}")
    print(f"Wrote: {dataset_path}")
    print(f"Wrote: {summary_path}")


if __name__ == "__main__":
    main()
