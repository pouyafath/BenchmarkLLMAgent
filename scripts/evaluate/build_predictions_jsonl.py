"""
Build a complete predictions JSONL for the SWE-bench harness.

Includes:
- Baseline (no enhancement): simple_solver patches from pilot_solver_benchmark/
- After enhancement: patches from solving_after_enhancement/ (5 enhancers)

Output: eval_results/swebench/all_predictions.jsonl

Patches are normalized to include `diff --git` headers when missing.
Non-diff content (e.g., LLM explanatory text) is filtered out.
"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLES_FILE = ROOT / "data" / "samples" / "swe_bench_live_10_samples.json"
BASELINE_DIR = ROOT / "results" / "pilot_solver_benchmark"
ENHANCED_DIR = ROOT / "results" / "solving_after_enhancement"
OUTPUT_FILE = ROOT / "eval_results" / "swebench" / "all_predictions.jsonl"

# Load sample mapping: (owner, repo, issue_number) -> instance_id
with open(SAMPLES_FILE) as f:
    samples = json.load(f)["issues"]

issue_to_instance = {}
for s in samples:
    key = f"{s['pr_owner']}__{s['pr_repo']}__{s['issue_number']}"
    instance_id = s["_swe_live_instance_id"]
    issue_to_instance[key] = instance_id

# Also handle case-insensitive repo names (e.g., theOehrly vs theoehrly)
key_lower = {k.lower(): v for k, v in issue_to_instance.items()}


def lookup_instance_id(owner, repo, issue_num):
    key = f"{owner}__{repo}__{issue_num}"
    if key in issue_to_instance:
        return issue_to_instance[key]
    if key.lower() in key_lower:
        return key_lower[key.lower()]
    return None


def _fix_hunk_headers(patch_lines: list[str]) -> list[str]:
    """Reconstruct bare @@ markers with proper line counts.

    LLM-generated patches often emit `@@` without `-start,count +start,count`.
    This function computes the correct counts from the hunk body lines and uses
    cumulative offsets for start lines so multi-hunk patches remain ordered.
    The SWE-bench harness falls back to `patch --fuzz=5` for positional matching.
    """
    # First pass: split into per-file sections, then per-hunk
    files: list[dict] = []  # [{header_lines, hunks: [{old_count, new_count, body}]}]
    current_file_headers = []
    current_hunks = []
    current_body = []
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
            # After file headers, first @@ seen — this line is part of first hunk body
            if line.startswith("-"):
                old_count += 1
            elif line.startswith("+"):
                new_count += 1
            else:
                old_count += 1
                new_count += 1
            current_body.append(line)

    flush_file()

    # Second pass: emit with cumulative start lines
    result = []
    for f in files:
        result.extend(f["headers"])
        old_start = 1
        new_start = 1
        for hunk in f["hunks"]:
            result.append(f"@@ -{old_start},{hunk['old_count']} +{new_start},{hunk['new_count']} @@")
            result.extend(hunk["body"])
            # Advance start lines past this hunk (assuming sequential, non-overlapping)
            old_start += hunk["old_count"] + 100  # gap between hunks
            new_start += hunk["new_count"] + 100
    return result


def normalize_patch(patch: str) -> str | None:
    """Normalize a patch for the SWE-bench harness.

    - Filters out non-diff content (LLM explanatory text)
    - Adds `diff --git` headers when missing
    - Reconstructs bare `@@` hunk markers with proper line counts
    """
    patch = patch.strip()
    if not patch:
        return None

    # Check if this looks like a diff at all (must contain --- and +++ lines)
    if "--- a/" not in patch and "--- a\t" not in patch:
        return None

    lines = patch.split("\n")

    # Strip LLM garbage lines (e.g., "*** End of File ***", "... (N more lines)")
    lines = [l for l in lines if not l.startswith("***") and not l.startswith("... (")]

    # Add diff --git headers before each --- a/... line if missing
    if not lines[0].startswith("diff --git"):
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

    return "\n".join(lines)


records = []
skipped = []

# 1. Baseline predictions (simple_solver, no enhancement)
for pred_file in sorted(BASELINE_DIR.glob("simple_solver__*.json")):
    parts = pred_file.stem.split("__")
    if len(parts) != 4:
        continue
    _, owner, repo, num = parts
    instance_id = lookup_instance_id(owner, repo, num)
    if not instance_id:
        continue

    with open(pred_file) as f:
        pred = json.load(f)
    patch = normalize_patch(pred.get("patch", ""))
    if not patch:
        skipped.append(f"baseline: {pred_file.name} (no valid patch)")
        continue

    records.append({
        "instance_id": instance_id,
        "model_patch": patch,
        "model_name_or_path": "baseline_no_enhancement",
    })

# 2. Enhanced predictions (from solving_after_enhancement)
for pred_file in sorted(ENHANCED_DIR.glob("openai_agents_sdk_after_enhancement__*.json")):
    parts = pred_file.stem.split("__")
    if len(parts) != 5:
        print(f"WARNING: unexpected filename format: {pred_file.name}")
        continue
    _, agent, owner, repo, num = parts
    instance_id = lookup_instance_id(owner, repo, num)
    if not instance_id:
        print(f"WARNING: no instance_id for {owner}__{repo}__{num}")
        continue

    with open(pred_file) as f:
        pred = json.load(f)
    patch = normalize_patch(pred.get("patch", ""))
    if not patch:
        skipped.append(f"enhanced_{agent}: {pred_file.name} (no valid patch)")
        continue

    records.append({
        "instance_id": instance_id,
        "model_patch": patch,
        "model_name_or_path": f"enhanced_{agent}",
    })

# Write output
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_FILE, "w") as out:
    for r in records:
        out.write(json.dumps(r) + "\n")

print(f"Written {len(records)} predictions to {OUTPUT_FILE}")
model_counts = Counter(r["model_name_or_path"] for r in records)
for model, count in sorted(model_counts.items()):
    print(f"  {model}: {count}")
if skipped:
    print(f"\nSkipped {len(skipped)} entries (no valid diff):")
    for s in skipped:
        print(f"  {s}")
