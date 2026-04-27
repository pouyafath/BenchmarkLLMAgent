"""
Convert solver outputs into SWE-bench harness prediction JSONL files.

Produces one directory per model/agent under output_dir:
- baseline_no_enhancement/all_preds.jsonl
- enhanced_<agent>/all_preds.jsonl
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SAMPLES = ROOT / "data" / "samples" / "swe_bench_live_10_samples.json"
DEFAULT_SOLVING_DIR = ROOT / "results" / "solving_after_enhancement"
DEFAULT_BASELINE_DIR = ROOT / "results" / "solving_baseline"
DEFAULT_OUTPUT_DIR = ROOT / "eval_results" / "swebench" / "iteration2_predictions"


def load_samples(samples_path: Path, max_issues: int | None) -> list[dict]:
    with open(samples_path) as f:
        data = json.load(f)

    issues = data["issues"] if isinstance(data, dict) and "issues" in data else data
    if max_issues is not None:
        issues = issues[:max_issues]
    return issues


def build_instance_lookup(issues: list[dict]) -> tuple[dict[tuple[str, str, int], str], dict[tuple[str, str, int], str]]:
    exact: dict[tuple[str, str, int], str] = {}
    lowered: dict[tuple[str, str, int], str] = {}

    for issue in issues:
        owner = issue["pr_owner"]
        repo = issue["pr_repo"]
        num = int(issue["issue_number"])
        instance_id = issue.get("_swe_live_instance_id") or issue.get("issue_id")
        if not instance_id:
            instance_id = f"{owner}__{repo}-{num}"

        exact[(owner, repo, num)] = instance_id
        lowered[(owner.lower(), repo.lower(), num)] = instance_id

    return exact, lowered


def _fix_hunk_headers(patch_lines: list[str]) -> list[str]:
    """Reconstruct bare @@ markers with proper line counts.

    LLM-generated patches often emit `@@` without `-start,count +start,count`.
    This function computes the correct counts from the hunk body lines and uses
    cumulative offsets for start lines so multi-hunk patches remain ordered.
    The SWE-bench harness falls back to `patch --fuzz=5` for positional matching.
    """
    files: list[dict] = []
    current_file_headers: list[str] = []
    current_hunks: list[dict] = []
    current_body: list[str] = []
    old_count = 0
    new_count = 0

    def flush_hunk():
        nonlocal old_count, new_count, current_body
        has_changes = any(l.startswith("+") or l.startswith("-") for l in current_body)
        if current_body and has_changes:
            current_hunks.append({
                "old_count": old_count,
                "new_count": new_count,
                "body": current_body,
            })
        current_body = []
        old_count = 0
        new_count = 0

    def flush_file():
        nonlocal current_file_headers, current_hunks
        flush_hunk()
        if current_file_headers or current_hunks:
            files.append({"headers": current_file_headers, "hunks": current_hunks})
        current_file_headers = []
        current_hunks = []

    for line in patch_lines:
        if line.startswith("diff --git"):
            flush_file()
            current_file_headers.append(line)
        elif line.startswith("--- ") or line.startswith("+++ "):
            flush_hunk()
            current_file_headers.append(line)
        elif line.rstrip() == "@@":
            flush_hunk()
        elif current_hunks or current_body or old_count > 0:
            if line.startswith("-"):
                old_count += 1
            elif line.startswith("+"):
                new_count += 1
            else:
                old_count += 1
                new_count += 1
            current_body.append(line)
        else:
            if line.startswith("-"):
                old_count += 1
            elif line.startswith("+"):
                new_count += 1
            else:
                old_count += 1
                new_count += 1
            current_body.append(line)

    flush_file()

    result: list[str] = []
    for f in files:
        result.extend(f["headers"])
        old_start = 1
        new_start = 1
        for hunk in f["hunks"]:
            result.append(f"@@ -{old_start},{hunk['old_count']} +{new_start},{hunk['new_count']} @@")
            result.extend(hunk["body"])
            old_start += hunk["old_count"] + 100
            new_start += hunk["new_count"] + 100
    return result


def normalize_patch(patch: str) -> str:
    """Normalize a patch for the SWE-bench harness.

    - Filters out non-diff content (LLM explanatory text)
    - Adds `diff --git` headers when missing
    - Reconstructs bare `@@` hunk markers with proper line counts
    """
    patch = (patch or "").strip()
    if not patch:
        return ""

    # Check if this looks like a diff at all
    if "--- a/" not in patch and "--- a\t" not in patch:
        return ""

    lines = patch.split("\n")

    # Strip LLM garbage lines
    lines = [l for l in lines if not l.startswith("***") and not l.startswith("... (")]

    # Add diff --git headers before each --- a/... line if missing
    if lines and not lines[0].startswith("diff --git"):
        new_lines = []
        for line in lines:
            if line.startswith("--- a/"):
                filepath = line[6:].strip()
                new_lines.append(f"diff --git a/{filepath} b/{filepath}")
            new_lines.append(line)
        lines = new_lines

    # Fix bare @@ markers (no line numbers)
    has_bare_hunks = any(l.rstrip() == "@@" for l in lines)
    if has_bare_hunks:
        lines = _fix_hunk_headers(lines)

    return "\n".join(lines).strip()


def lookup_instance_id(
    owner: str,
    repo: str,
    issue_num: int,
    exact_lookup: dict[tuple[str, str, int], str],
    lowered_lookup: dict[tuple[str, str, int], str],
) -> str | None:
    if (owner, repo, issue_num) in exact_lookup:
        return exact_lookup[(owner, repo, issue_num)]
    return lowered_lookup.get((owner.lower(), repo.lower(), issue_num))


def load_patch(path: Path) -> str:
    with open(path) as f:
        data = json.load(f)
    return normalize_patch(data.get("patch", ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=str, default=str(DEFAULT_SAMPLES))
    parser.add_argument("--max-issues", type=int, default=None)
    parser.add_argument("--solving-dir", type=str, default=str(DEFAULT_SOLVING_DIR))
    parser.add_argument("--baseline-dir", type=str, default=str(DEFAULT_BASELINE_DIR))
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--solver", type=str, default="openai_agents_sdk")
    parser.add_argument("--baseline-model-name", type=str, default="baseline_no_enhancement")
    args = parser.parse_args()

    samples_path = Path(args.samples)
    solving_dir = Path(args.solving_dir)
    baseline_dir = Path(args.baseline_dir)
    output_dir = Path(args.output_dir)

    issues = load_samples(samples_path, args.max_issues)
    expected_instances = {
        issue.get("_swe_live_instance_id") or issue.get("issue_id") or f"{issue['pr_owner']}__{issue['pr_repo']}-{issue['issue_number']}"
        for issue in issues
    }
    exact_lookup, lowered_lookup = build_instance_lookup(issues)

    records_by_model: dict[str, dict[str, dict]] = defaultdict(dict)

    enhanced_pat = re.compile(
        rf"^{re.escape(args.solver)}_after_enhancement__(.+?)__(.+?)__(.+?)__(\d+)\.json$"
    )
    baseline_pat = re.compile(rf"^{re.escape(args.solver)}__(.+?)__(.+?)__(\d+)\.json$")

    skipped: list[str] = []

    # Enhanced predictions
    if solving_dir.exists():
        for pred_file in sorted(solving_dir.glob(f"{args.solver}_after_enhancement__*.json")):
            match = enhanced_pat.match(pred_file.name)
            if not match:
                skipped.append(f"enhanced: bad filename {pred_file.name}")
                continue

            agent, owner, repo, num_raw = match.groups()
            issue_num = int(num_raw)
            instance_id = lookup_instance_id(owner, repo, issue_num, exact_lookup, lowered_lookup)
            if not instance_id:
                skipped.append(f"enhanced: unknown instance {owner}__{repo}__{issue_num}")
                continue

            patch = load_patch(pred_file)
            model_name = f"enhanced_{agent}"
            records_by_model[model_name][instance_id] = {
                "instance_id": instance_id,
                "model_patch": patch,
                "model_name_or_path": model_name,
            }

    # Baseline predictions
    if baseline_dir.exists():
        baseline_files = sorted(baseline_dir.glob(f"{args.solver}__*.json"))
        if not baseline_files and args.solver != "simple_solver":
            baseline_files = sorted(baseline_dir.glob("simple_solver__*.json"))

        for pred_file in baseline_files:
            match = baseline_pat.match(pred_file.name)
            if not match:
                alt_match = re.match(r"^simple_solver__(.+?)__(.+?)__(\d+)\.json$", pred_file.name)
                if not alt_match:
                    skipped.append(f"baseline: bad filename {pred_file.name}")
                    continue
                owner, repo, num_raw = alt_match.groups()
            else:
                owner, repo, num_raw = match.groups()

            issue_num = int(num_raw)
            instance_id = lookup_instance_id(owner, repo, issue_num, exact_lookup, lowered_lookup)
            if not instance_id:
                skipped.append(f"baseline: unknown instance {owner}__{repo}__{issue_num}")
                continue

            patch = load_patch(pred_file)
            model_name = args.baseline_model_name
            records_by_model[model_name][instance_id] = {
                "instance_id": instance_id,
                "model_patch": patch,
                "model_name_or_path": model_name,
            }

    output_dir.mkdir(parents=True, exist_ok=True)

    total_records = 0
    for model_name, records_map in sorted(records_by_model.items()):
        model_dir = output_dir / model_name
        model_dir.mkdir(parents=True, exist_ok=True)

        records = [records_map[iid] for iid in sorted(records_map)]
        total_records += len(records)

        out_file = model_dir / "all_preds.jsonl"
        with open(out_file, "w") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")

        missing = sorted(expected_instances - set(records_map.keys()))
        print(f"{model_name}: {len(records)} predictions -> {out_file}")
        if missing:
            print(f"  Missing instances ({len(missing)}):")
            for iid in missing:
                print(f"    - {iid}")

    combined = output_dir / "all_predictions.jsonl"
    with open(combined, "w") as f:
        for model_name in sorted(records_by_model):
            for instance_id in sorted(records_by_model[model_name]):
                f.write(json.dumps(records_by_model[model_name][instance_id]) + "\n")

    print(f"\nWrote {total_records} total predictions to {output_dir}")
    print(f"Combined file: {combined}")

    if skipped:
        print(f"\nSkipped {len(skipped)} entries:")
        for item in skipped:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
