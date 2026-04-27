"""
Enrich the Pouya-SWE-bench-Live-style dataset with all fields that
SWE-bench-Live has but our crawl omitted.

Fields added / fixed:
  - test_cmds          ["pytest -rA"]
  - log_parser         "pytest"
  - version            "live" (harness normalizes None -> "live")
  - difficulty         {files, hunks, lines} computed from patch
  - commit_url         https://github.com/{repo}/tree/{base_commit}
  - commit_urls        [https://github.com/{repo}/commit/{merge_sha}]  (from GH API)
  - all_hints_text     same as hints_text (or "" if empty)
  - pull_number        cast to str to match SWE-bench-Live format

Also re-writes pouya_50_samples.json with the updated data.

Usage:
    python scripts/data/enrich_pouya_dataset.py [--fetch-commits]

    --fetch-commits   Hit GitHub API to get PR merge commit SHAs for commit_urls
                      (rate-limited; skip if you just need structural fields)
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from scripts.data.prepare_swe_bench_live_samples import swe_live_to_sample

DATA_DIR = ROOT / "data" / "samples" / "pouya_swebench_live_style_50"
JSONL_IN  = DATA_DIR / "pouya_50_dataset.jsonl"
JSONL_OUT = DATA_DIR / "pouya_50_dataset.jsonl"  # overwrite in-place

try:
    from secrets import GITHUB_TOKENS as TOKENS
except ImportError:
    raise ImportError("secrets.py not found. Copy secrets_example.py to secrets.py and add your GitHub PATs.")
_token_idx = 0


def _next_token():
    global _token_idx
    t = TOKENS[_token_idx % len(TOKENS)]
    _token_idx += 1
    return t


def gh_get(url, params=None, retries=3):
    """Simple GitHub API GET with token rotation."""
    if params:
        url = f"{url}?{urlencode(params)}" if "?" not in url else f"{url}&{urlencode(params)}"
    for attempt in range(retries):
        tok = _next_token()
        req = Request(url, headers={
            "Authorization": f"token {tok}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Pouya-Dataset-Enricher",
        })
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            if e.code == 403:
                time.sleep(2 ** attempt)
                continue
            raise
    return None


# ── Difficulty computation ────────────────────────────────────────────────

def compute_difficulty(patch: str) -> dict:
    """Compute {files, hunks, lines} from a unified diff (same as SWE-bench-Live)."""
    files = set()
    hunks = 0
    lines = 0
    for line in patch.splitlines():
        if line.startswith("diff --git"):
            # extract b/ path
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


# ── Main enrichment ──────────────────────────────────────────────────────

def enrich(rows: list[dict], fetch_commits: bool = False) -> list[dict]:
    enriched = []
    for i, row in enumerate(rows):
        iid = row["instance_id"]
        repo = row["repo"]
        base = row["base_commit"]

        # test_cmds — all Python projects use pytest
        if "test_cmds" not in row:
            row["test_cmds"] = ["pytest -rA"]

        # log_parser
        if "log_parser" not in row:
            row["log_parser"] = "pytest"

        # version — harness normalizes None to "live"
        row["version"] = "live"

        # difficulty
        if "difficulty" not in row:
            row["difficulty"] = compute_difficulty(row.get("patch", ""))

        # commit_url
        if "commit_url" not in row:
            row["commit_url"] = f"https://github.com/{repo}/tree/{base}"

        # commit_urls — fetch merge commit SHA from GitHub API
        if "commit_urls" not in row:
            if fetch_commits:
                pr_num = row.get("pull_number")
                if pr_num:
                    pr_data = gh_get(f"https://api.github.com/repos/{repo}/pulls/{pr_num}")
                    if pr_data and pr_data.get("merge_commit_sha"):
                        row["commit_urls"] = [
                            f"https://github.com/{repo}/commit/{pr_data['merge_commit_sha']}"
                        ]
                    else:
                        row["commit_urls"] = []
                    time.sleep(0.5)  # be nice
                else:
                    row["commit_urls"] = []
            else:
                row["commit_urls"] = []

        # all_hints_text — SWE-bench-Live has this; use hints_text or ""
        if "all_hints_text" not in row:
            row["all_hints_text"] = row.get("hints_text", "")

        # pull_number — SWE-bench-Live stores as string
        if isinstance(row.get("pull_number"), int):
            row["pull_number"] = str(row["pull_number"])

        # issue_numbers — SWE-bench-Live stores as list of strings
        if isinstance(row.get("issue_numbers"), list):
            row["issue_numbers"] = [str(n) for n in row["issue_numbers"]]

        enriched.append(row)
        print(f"  [{i+1}/{len(rows)}] {iid}: +difficulty={row['difficulty']}")
    return enriched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-commits", action="store_true",
                        help="Fetch merge commit SHAs from GitHub API for commit_urls")
    args = parser.parse_args()

    # Read
    rows = []
    with open(JSONL_IN) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    print(f"Read {len(rows)} instances from {JSONL_IN}")

    # Enrich
    rows = enrich(rows, fetch_commits=args.fetch_commits)

    # Write JSONL
    with open(JSONL_OUT, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print(f"\nWrote enriched JSONL: {JSONL_OUT}")

    # Also regenerate samples JSON
    samples = [swe_live_to_sample(row) for row in rows]
    samples_data = {
        "metadata": {
            "description": "50-issue Pouya-SWE-bench-Live-style dataset (no description quality filter)",
            "source": "GitHub API crawl",
            "collection_date": "2026-04-16",
            "selection_seed": 99,
            "count": len(samples),
            "filter": "F2P > 0 AND P2P > 0, NO description quality filter",
            "swebench_live_overlap": 0,
        },
        "issues": samples,
    }
    samples_path = DATA_DIR / "pouya_50_samples.json"
    with open(samples_path, "w") as f:
        json.dump(samples_data, f, indent=2)
    print(f"Wrote samples JSON: {samples_path}")

    # Summary
    print(f"\nField check on first instance:")
    r0 = rows[0]
    for field in ["test_cmds", "log_parser", "version", "difficulty",
                   "commit_url", "commit_urls", "all_hints_text",
                   "pull_number", "issue_numbers"]:
        print(f"  {field}: {r0.get(field, 'MISSING')}")


if __name__ == "__main__":
    main()
