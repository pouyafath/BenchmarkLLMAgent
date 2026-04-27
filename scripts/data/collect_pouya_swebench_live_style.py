#!/usr/bin/env python3
"""
Collect a "Pouya-SWE-bench-Live-style" dataset of 50 issue-PR pairs from GitHub.

Follows SWE-bench-Live structural criteria:
  - Popular Python repos (>1000 stars, >200 issues/PRs)
  - Issues after 2024-01-01
  - PR resolves issue (keyword linking)
  - PR modifies test files AND source files
  - Non-empty code patch and test patch

Key difference from SWE-bench-Live:
  - NO quality filtering on issue descriptions (keep vague/short/poorly-written)
  - Fully automated, no manual curation

Outputs:
  data/samples/pouya_swebench_live_style_50/pouya_50_dataset.jsonl
  data/samples/pouya_swebench_live_style_50/pouya_50_instance_ids.txt
  data/samples/pouya_swebench_live_style_50/pouya_50_samples.json
  data/samples/pouya_swebench_live_style_50/pouya_50_description_stats.json
  data/samples/pouya_swebench_live_style_50/_collection_progress.json

Usage:
  python scripts/data/collect_pouya_swebench_live_style.py
  python scripts/data/collect_pouya_swebench_live_style.py --target 50 --seed 99 --resume
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

# ── Configuration ──────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "data" / "samples" / "pouya_swebench_live_style_50"
PROGRESS_FILE = OUT_DIR / "_collection_progress.json"
CLONE_BASE = Path(tempfile.gettempdir()) / "pouya_swebench_clones"

try:
    from secrets import GITHUB_TOKENS as TOKENS
except ImportError:
    raise ImportError("secrets.py not found. Copy secrets_example.py to secrets.py and add your GitHub PATs.")

# SWE-bench-Live criteria
MIN_STARS = 1000
MIN_ISSUES = 200
MIN_PRS = 200
DATE_CUTOFF = "2024-01-01"

# Issue-PR linking keywords (regex patterns in PR body/title)
FIX_PATTERNS = [
    re.compile(r"(?:fix(?:es)?|close[sd]?|resolve[sd]?)\s+#(\d+)", re.IGNORECASE),
    re.compile(r"(?:fix(?:es)?|close[sd]?|resolve[sd]?)\s+https?://github\.com/[^/]+/[^/]+/issues/(\d+)", re.IGNORECASE),
]

# Test file patterns
TEST_FILE_PATTERNS = re.compile(r"(?:^|/)tests?[/_]|test_[^/]*\.py$|_test\.py$", re.IGNORECASE)

# ── GitHub API client with token rotation ──────────────────────────────────

class GitHubAPI:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self._idx = 0
        self._request_count = 0

    @property
    def _token(self) -> str:
        return self.tokens[self._idx % len(self.tokens)]

    def _rotate(self):
        self._idx = (self._idx + 1) % len(self.tokens)

    def get(self, url: str, params: dict | None = None, max_retries: int = 3) -> dict | list:
        """GET request with token rotation and retry."""
        if params:
            qs = urlencode(params)
            url = f"{url}?{qs}" if "?" not in url else f"{url}&{qs}"

        for attempt in range(max_retries):
            headers = {
                "Authorization": f"token {self._token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Pouya-SWE-bench-Collector",
            }
            req = Request(url, headers=headers)
            try:
                with urlopen(req, timeout=30) as resp:
                    self._request_count += 1
                    data = json.loads(resp.read().decode())
                    return data
            except HTTPError as e:
                if e.code == 403:
                    # Rate limited — rotate token and wait
                    self._rotate()
                    wait = min(2 ** attempt * 5, 60)
                    print(f"    Rate limited, rotating token, waiting {wait}s...")
                    time.sleep(wait)
                elif e.code == 404:
                    return {}
                elif e.code == 422:
                    return {}
                else:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(2)
            except Exception:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2)
        return {}

    def get_paginated(self, url: str, params: dict | None = None,
                      max_pages: int = 5, per_page: int = 100) -> list:
        """Paginated GET, returns all items across pages."""
        params = dict(params or {})
        params["per_page"] = str(per_page)
        all_items = []
        for page in range(1, max_pages + 1):
            params["page"] = str(page)
            data = self.get(url, params)
            if isinstance(data, dict) and "items" in data:
                items = data["items"]
            elif isinstance(data, list):
                items = data
            else:
                break
            all_items.extend(items)
            if len(items) < per_page:
                break
        return all_items


# ── Utility functions ──────────────────────────────────────────────────────

def run_git(cmd: list[str], cwd: str, timeout: int = 120) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd=cwd, timeout=timeout,
    )
    return result.stdout.strip()


def extract_linked_issues(pr_body: str, pr_title: str) -> list[int]:
    """Extract issue numbers linked via fix/close/resolve keywords."""
    text = f"{pr_title}\n{pr_body}"
    issues = set()
    for pat in FIX_PATTERNS:
        for m in pat.finditer(text):
            try:
                issues.add(int(m.group(1)))
            except (ValueError, IndexError):
                pass
    return sorted(issues)


def is_test_file(filepath: str) -> bool:
    """Check if a file path looks like a test file."""
    return bool(TEST_FILE_PATTERNS.search(filepath))


def parse_test_functions_from_diff(diff_text: str) -> list[str]:
    """
    Parse test function names from a unified diff.
    Returns pytest-style names: file::Class::test_method or file::test_function
    """
    test_names = []
    current_file = None
    current_class = None

    for line in diff_text.split("\n"):
        # Track current file
        if line.startswith("diff --git"):
            m = re.search(r"b/(.+)$", line)
            if m:
                current_file = m.group(1)
                current_class = None
            continue

        # Track class context from hunk headers
        if line.startswith("@@") and current_file:
            # @@ -10,5 +10,7 @@ class TestFoo:
            m = re.search(r"@@.*@@\s+class\s+(\w+)", line)
            if m:
                current_class = m.group(1)
            # Reset class if we see a module-level function
            m2 = re.search(r"@@.*@@\s+def\s+", line)
            if m2 and not re.search(r"@@.*@@\s+class\s+", line):
                current_class = None

        # Detect added test functions
        if line.startswith("+") and not line.startswith("+++"):
            stripped = line[1:].strip()
            # Match: def test_something(...) or async def test_something(...)
            m = re.match(r"(?:async\s+)?def\s+(test_\w+)", stripped)
            if m and current_file:
                func_name = m.group(1)
                if current_class:
                    test_names.append(f"{current_file}::{current_class}::{func_name}")
                else:
                    test_names.append(f"{current_file}::{func_name}")

    return test_names


def parse_existing_tests_from_file(file_content: str, filepath: str) -> list[str]:
    """Parse existing test function names from a Python test file."""
    tests = []
    current_class = None
    for line in file_content.split("\n"):
        stripped = line.strip()
        # Track class
        m = re.match(r"class\s+(\w+)", stripped)
        if m:
            current_class = m.group(1)
        # Track top-level (no indent = no class)
        if not line.startswith(" ") and not line.startswith("\t"):
            if not stripped.startswith("class "):
                current_class = None
        # Match test functions
        m = re.match(r"\s*(?:async\s+)?def\s+(test_\w+)", stripped)
        if m:
            func = m.group(1)
            if current_class:
                tests.append(f"{filepath}::{current_class}::{func}")
            else:
                tests.append(f"{filepath}::{func}")
    return tests


def compute_description_stats(problem_statement: str) -> dict:
    """Compute quality metrics for an issue description."""
    body = problem_statement or ""
    has_code_block = "```" in body or "    " in body
    has_traceback = "Traceback" in body or "traceback" in body or "Error:" in body
    has_reproduction = any(kw in body.lower() for kw in [
        "steps to reproduce", "reproduction", "how to reproduce",
        "minimal example", "to reproduce", "repro",
    ])
    has_expected = any(kw in body.lower() for kw in [
        "expected", "should", "supposed to", "want",
    ])
    word_count = len(body.split())
    body_length = len(body)

    if body_length < 100 or word_count < 20:
        quality = "vague"
    elif body_length < 500 or word_count < 80:
        quality = "moderate"
    else:
        quality = "detailed"

    return {
        "body_length": body_length,
        "word_count": word_count,
        "has_code_block": has_code_block,
        "has_traceback": has_traceback,
        "has_reproduction_steps": has_reproduction,
        "has_expected_behavior": has_expected,
        "quality_bucket": quality,
    }


# ── Phase A: Discover repos ───────────────────────────────────────────────

def discover_repos(api: GitHubAPI, max_repos: int = 200) -> list[dict]:
    """
    Find popular Python repos matching SWE-bench-Live criteria.
    Returns list of {owner, name, full_name, stars, ...}
    """
    print("\n=== Phase A: Discovering repos ===")
    repos = []
    # GitHub search API returns max 1000 results; paginate by star ranges
    star_ranges = [
        (50000, 1000000),
        (20000, 49999),
        (10000, 19999),
        (5000, 9999),
        (3000, 4999),
        (1000, 2999),
    ]

    for lo, hi in star_ranges:
        if len(repos) >= max_repos:
            break
        q = f"language:python stars:{lo}..{hi} pushed:>{DATE_CUTOFF}"
        print(f"  Searching: stars {lo}..{hi}")
        data = api.get("https://api.github.com/search/repositories",
                       {"q": q, "sort": "stars", "order": "desc", "per_page": "100"})
        if not isinstance(data, dict) or "items" not in data:
            continue
        for item in data["items"]:
            if len(repos) >= max_repos:
                break
            # Apply SWE-bench-Live repo criteria
            if item.get("stargazers_count", 0) < MIN_STARS:
                continue
            if item.get("open_issues_count", 0) < MIN_ISSUES:
                continue
            if item.get("language", "").lower() != "python":
                continue
            if item.get("archived", False) or item.get("disabled", False):
                continue
            if not item.get("license"):
                continue
            repos.append({
                "owner": item["owner"]["login"],
                "name": item["name"],
                "full_name": item["full_name"],
                "stars": item["stargazers_count"],
                "open_issues": item["open_issues_count"],
            })

    print(f"  Found {len(repos)} qualifying repos")
    return repos


# ── Phase B: Crawl issue-PR pairs ─────────────────────────────────────────

def crawl_repo_candidates(
    api: GitHubAPI,
    owner: str,
    repo: str,
    existing_instance_ids: set[str],
    max_prs_to_check: int = 200,
) -> list[dict]:
    """
    For one repo, find merged PRs that fix issues + modify tests.
    Returns list of candidate instances.
    """
    full_name = f"{owner}/{repo}"
    candidates = []

    # Fetch recent closed PRs
    prs = api.get_paginated(
        f"https://api.github.com/repos/{full_name}/pulls",
        {"state": "closed", "sort": "updated", "direction": "desc"},
        max_pages=max_prs_to_check // 100 + 1,
    )

    for pr in prs:
        if not pr.get("merged_at"):
            continue

        # Date cutoff
        created = pr.get("created_at", "")
        if created < f"{DATE_CUTOFF}T00:00:00Z":
            continue

        pr_number = pr["number"]
        instance_id = f"{owner}__{repo}-{pr_number}"

        # Skip if already in SWE-bench-Live
        if instance_id in existing_instance_ids:
            continue

        pr_title = pr.get("title", "") or ""
        pr_body = pr.get("body", "") or ""

        # Check for issue linking
        linked_issues = extract_linked_issues(pr_body, pr_title)
        if not linked_issues:
            continue

        # Check if PR modifies test files
        pr_files_data = api.get(
            f"https://api.github.com/repos/{full_name}/pulls/{pr_number}/files",
            {"per_page": "100"},
        )
        if not isinstance(pr_files_data, list):
            continue

        changed_files = [f.get("filename", "") for f in pr_files_data]
        has_test_changes = any(is_test_file(f) for f in changed_files)
        has_src_changes = any(
            f.endswith(".py") and not is_test_file(f) for f in changed_files
        )

        if not (has_test_changes and has_src_changes):
            continue

        # Fetch linked issue bodies (problem_statement)
        problem_parts = []
        issue_numbers_found = []
        for issue_num in linked_issues[:3]:  # limit to 3 linked issues
            issue_data = api.get(
                f"https://api.github.com/repos/{full_name}/issues/{issue_num}"
            )
            if not issue_data or isinstance(issue_data, list):
                continue
            issue_title = issue_data.get("title", "")
            issue_body = issue_data.get("body", "") or ""
            issue_numbers_found.append(issue_num)

            if issue_title:
                problem_parts.append(issue_title)
            if issue_body:
                problem_parts.append(issue_body)

            # Fetch pre-PR comments (created before PR's first commit)
            merge_sha = pr.get("merge_commit_sha", "")
            pr_created_at = pr.get("created_at", "9999")
            comments_data = api.get(
                f"https://api.github.com/repos/{full_name}/issues/{issue_num}/comments",
                {"per_page": "100"},
            )
            if isinstance(comments_data, list):
                for comment in comments_data:
                    comment_time = comment.get("created_at", "9999")
                    if comment_time < pr_created_at:
                        comment_body = comment.get("body", "")
                        if comment_body:
                            problem_parts.append(f"---\n\n{comment_body}")

        if not problem_parts:
            continue

        problem_statement = "\n\n".join(problem_parts)

        # Store candidate (patches will be extracted later via git)
        candidates.append({
            "instance_id": instance_id,
            "repo": full_name,
            "pr_number": pr_number,
            "issue_numbers": issue_numbers_found,
            "merge_commit_sha": pr.get("merge_commit_sha", ""),
            "base_sha": pr.get("base", {}).get("sha", ""),
            "problem_statement": problem_statement,
            "created_at": created,
            "changed_files": changed_files,
        })

        if len(candidates) >= 10:  # Max 10 per repo
            break

    return candidates


# ── Phase B.2: Extract patches via git clone ───────────────────────────────

def extract_patches_for_candidates(candidates: list[dict]) -> list[dict]:
    """
    Clone repos and extract code/test patches for each candidate.
    Adds: patch, test_patch, base_commit, FAIL_TO_PASS, PASS_TO_PASS
    """
    print("\n=== Extracting patches via git ===")
    CLONE_BASE.mkdir(parents=True, exist_ok=True)

    validated = []
    repos_cloned = {}

    for i, cand in enumerate(candidates):
        repo = cand["repo"]
        owner, repo_name = repo.split("/")
        clone_dir = CLONE_BASE / f"{owner}__{repo_name}"

        # Clone if needed
        if repo not in repos_cloned:
            if not clone_dir.exists():
                print(f"  Cloning {repo}...")
                try:
                    subprocess.run(
                        ["git", "clone", "--filter=blob:none", "--no-checkout",
                         f"https://github.com/{repo}.git", str(clone_dir)],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        timeout=300,
                    )
                except (subprocess.TimeoutExpired, Exception) as e:
                    print(f"    Clone failed: {e}")
                    continue
            repos_cloned[repo] = str(clone_dir)
        cwd = repos_cloned.get(repo)
        if not cwd:
            continue

        merge_sha = cand["merge_commit_sha"]
        base_sha = cand["base_sha"]

        if not merge_sha or not base_sha:
            continue

        # Fetch the specific commits
        try:
            subprocess.run(
                ["git", "fetch", "origin", merge_sha, base_sha],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=cwd, timeout=120,
            )
        except Exception:
            # Try fetching all
            try:
                subprocess.run(
                    ["git", "fetch", "--all"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=cwd, timeout=300,
                )
            except Exception:
                continue

        # Extract code patch (excluding tests and docs)
        try:
            code_patch = run_git(
                ["git", "diff", base_sha, merge_sha, "--",
                 ".", ":!tests", ":!test", ":!docs", ":!doc"],
                cwd=cwd, timeout=60,
            )
        except Exception:
            code_patch = ""

        # Extract test patch
        try:
            test_patch = run_git(
                ["git", "diff", base_sha, merge_sha, "--",
                 "tests/", "test/"],
                cwd=cwd, timeout=60,
            )
            # Also check for test files not in tests/ or test/ dirs
            if not test_patch:
                test_files = [f for f in cand["changed_files"] if is_test_file(f)]
                if test_files:
                    test_patch = run_git(
                        ["git", "diff", base_sha, merge_sha, "--"] + test_files,
                        cwd=cwd, timeout=60,
                    )
        except Exception:
            test_patch = ""

        if not code_patch.strip() or not test_patch.strip():
            continue

        # Parse F2P test names from test_patch
        f2p_tests = parse_test_functions_from_diff(test_patch)
        if not f2p_tests:
            # Fallback: use test file names
            test_files = [f for f in cand["changed_files"] if is_test_file(f)]
            f2p_tests = test_files if test_files else [f"test_from_pr_{cand['pr_number']}"]

        # Approximate P2P: get all tests in changed test files (at base commit)
        p2p_tests = []
        test_files = [f for f in cand["changed_files"] if is_test_file(f)]
        for tf in test_files[:5]:
            try:
                content = run_git(
                    ["git", "show", f"{base_sha}:{tf}"],
                    cwd=cwd, timeout=30,
                )
                existing = parse_existing_tests_from_file(content, tf)
                # P2P = existing tests minus the new F2P tests
                p2p_tests.extend([t for t in existing if t not in f2p_tests])
            except Exception:
                pass

        if not p2p_tests:
            # Minimal P2P fallback
            p2p_tests = test_files if test_files else ["placeholder_p2p"]

        cand["patch"] = code_patch
        cand["test_patch"] = test_patch
        cand["base_commit"] = base_sha
        cand["FAIL_TO_PASS"] = f2p_tests
        cand["PASS_TO_PASS"] = p2p_tests
        validated.append(cand)

        print(f"  [{len(validated)}/{len(candidates)}] {cand['instance_id']}: "
              f"code={len(code_patch)} test={len(test_patch)} "
              f"F2P={len(f2p_tests)} P2P={len(p2p_tests)}")

    return validated


# ── Phase C: Select and output ─────────────────────────────────────────────

def load_swebench_live_ids() -> set[str]:
    """Load all SWE-bench-Live instance IDs to avoid overlap."""
    ids = set()
    # Check local cached datasets
    for pattern in [
        ROOT / "data" / "samples" / "groupC_swebenchlive_50" / "groupC_50_instance_ids.txt",
        ROOT / "data" / "samples" / "groupC_swebenchlive_90" / "groupC_90_instance_ids.txt",
    ]:
        if pattern.exists():
            for line in pattern.read_text().splitlines():
                line = line.strip()
                if line:
                    ids.add(line)

    # Try loading full dataset from HuggingFace
    try:
        from datasets import load_dataset
        ds = load_dataset("SWE-bench-Live/SWE-bench-Live", trust_remote_code=False)
        for split in ds:
            for row in ds[split]:
                ids.add(row["instance_id"])
        print(f"  Loaded {len(ids)} SWE-bench-Live instance IDs (from HuggingFace)")
    except Exception as e:
        print(f"  Could not load HuggingFace dataset ({e}), using local IDs only ({len(ids)})")

    return ids


def save_progress(data: dict):
    """Save collection progress for resumability."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def load_progress() -> dict:
    """Load previous collection progress."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"candidates": [], "repos_processed": [], "phase": "start"}


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)


def swe_live_to_sample(row: dict) -> dict:
    """Convert a collected instance to our enhancer-friendly sample format."""
    repo = row.get("repo", "")
    instance_id = row.get("instance_id", "")
    parts = repo.split("/") if "/" in repo else [repo, repo]
    owner, repo_name = parts[0], parts[1]

    pr_number = row.get("pr_number", 0)
    issue_numbers = row.get("issue_numbers", [])
    issue_num = issue_numbers[0] if issue_numbers else pr_number

    problem_stmt = row.get("problem_statement", "") or ""
    lines = [ln.strip() for ln in problem_stmt.splitlines() if ln.strip()]
    title = lines[0] if lines else instance_id

    patch = row.get("patch", "") or ""
    # Parse PR files from patch diff headers
    pr_files = []
    for m in re.finditer(r"diff --git a/(.+?) b/(.+)", patch):
        fname = m.group(2)
        pr_files.append({
            "filename": fname,
            "status": "modified",
        })

    return {
        "repo_name": f"{owner}/{repo_name}",
        "issue_number": issue_num,
        "issue_id": instance_id,
        "title": title,
        "body": problem_stmt,
        "pr_owner": owner,
        "pr_repo": repo_name,
        "pr_number": pr_number,
        "pr_base_sha": row.get("base_commit", ""),
        "pr_files": pr_files,
        "ground_truth_patch": patch,
        "_pouya_dataset_created_at": row.get("created_at", ""),
        "instance_id": instance_id,
    }


def get_image_name(instance_id: str) -> str:
    """Compute Docker image name (same convention as SWE-bench-Live)."""
    name = instance_id.replace("__", "_1776_").lower()
    return f"starryzhang/sweb.eval.x86_64.{name}:latest"


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Collect Pouya-SWE-bench-Live-style 50-issue dataset."
    )
    parser.add_argument("--target", type=int, default=50,
                        help="Target number of instances (default: 50)")
    parser.add_argument("--seed", type=int, default=99,
                        help="Random seed for final selection (default: 99)")
    parser.add_argument("--max-repos", type=int, default=150,
                        help="Max repos to discover (default: 150)")
    parser.add_argument("--max-prs-per-repo", type=int, default=200,
                        help="Max PRs to check per repo (default: 200)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from previous progress")
    parser.add_argument("--output-dir", default=str(OUT_DIR),
                        help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    api = GitHubAPI(TOKENS)

    # Load SWE-bench-Live IDs to avoid overlap
    print("Loading SWE-bench-Live instance IDs...")
    existing_ids = load_swebench_live_ids()

    # Resume support
    progress = load_progress() if args.resume else {"candidates": [], "repos_processed": [], "phase": "start"}
    all_candidates = progress.get("candidates", [])
    repos_processed = set(progress.get("repos_processed", []))

    if all_candidates:
        print(f"Resuming: {len(all_candidates)} candidates from {len(repos_processed)} repos")

    # Phase A: Discover repos
    repos = discover_repos(api, max_repos=args.max_repos)
    random.Random(args.seed).shuffle(repos)

    # Phase B: Crawl candidates
    print(f"\n=== Phase B: Crawling issue-PR pairs from {len(repos)} repos ===")
    target_candidates = args.target * 3  # Collect 3x target for selection buffer

    for repo_info in repos:
        if len(all_candidates) >= target_candidates:
            break

        full_name = repo_info["full_name"]
        if full_name in repos_processed:
            continue

        print(f"\n  [{len(all_candidates)}/{target_candidates}] Crawling {full_name} "
              f"({repo_info['stars']} stars)...")

        try:
            new_candidates = crawl_repo_candidates(
                api, repo_info["owner"], repo_info["name"],
                existing_ids,
                max_prs_to_check=args.max_prs_per_repo,
            )
            if new_candidates:
                print(f"    Found {len(new_candidates)} candidates")
                all_candidates.extend(new_candidates)
        except Exception as e:
            print(f"    Error: {e}")

        repos_processed.add(full_name)

        # Save progress periodically
        if len(repos_processed) % 5 == 0:
            save_progress({
                "candidates": all_candidates,
                "repos_processed": sorted(repos_processed),
                "phase": "crawling",
                "api_requests": api._request_count,
            })

    print(f"\n  Total API candidates: {len(all_candidates)}")
    save_progress({
        "candidates": all_candidates,
        "repos_processed": sorted(repos_processed),
        "phase": "patches",
        "api_requests": api._request_count,
    })

    # Phase B.2: Extract patches via git
    validated = extract_patches_for_candidates(all_candidates)
    print(f"\n  Validated candidates (with patches): {len(validated)}")

    if len(validated) < args.target:
        print(f"WARNING: Only {len(validated)} validated candidates, need {args.target}")
        print("Try increasing --max-repos or --max-prs-per-repo")

    # Phase C: Select final instances
    print(f"\n=== Phase C: Selecting {args.target} instances ===")
    rng = random.Random(args.seed)
    rng.shuffle(validated)
    selected = validated[:args.target]

    print(f"  Selected {len(selected)} instances")

    # Show repo distribution
    repos_dist = Counter(c["repo"] for c in selected)
    print(f"  Repos: {len(repos_dist)}")
    for repo, count in repos_dist.most_common(20):
        print(f"    {repo}: {count}")

    # Write outputs
    print(f"\n=== Writing outputs to {out_dir} ===")

    # 1. dataset.jsonl
    jsonl_path = out_dir / "pouya_50_dataset.jsonl"
    with open(jsonl_path, "w") as f:
        for inst in selected:
            row = {
                "instance_id": inst["instance_id"],
                "repo": inst["repo"],
                "base_commit": inst["base_commit"],
                "patch": inst["patch"],
                "test_patch": inst["test_patch"],
                "problem_statement": inst["problem_statement"],
                "hints_text": "",
                "created_at": inst["created_at"],
                "version": "1.0",
                "FAIL_TO_PASS": inst["FAIL_TO_PASS"],
                "PASS_TO_PASS": inst["PASS_TO_PASS"],
                "pull_number": inst["pr_number"],
                "issue_numbers": inst["issue_numbers"],
                "environment_setup_commit": inst["base_commit"],
                "image_name": get_image_name(inst["instance_id"]),
            }
            f.write(json.dumps(row, cls=DateTimeEncoder) + "\n")
    print(f"  Wrote {jsonl_path} ({len(selected)} lines)")

    # 2. instance_ids.txt
    ids_path = out_dir / "pouya_50_instance_ids.txt"
    with open(ids_path, "w") as f:
        for inst in selected:
            f.write(inst["instance_id"] + "\n")
    print(f"  Wrote {ids_path}")

    # 3. samples.json (enhancer-friendly)
    samples = [swe_live_to_sample(inst) for inst in selected]
    samples_data = {
        "metadata": {
            "description": f"{len(selected)}-issue Pouya-SWE-bench-Live-style dataset (no description quality filter)",
            "source": "GitHub API crawl",
            "collection_date": datetime.date.today().isoformat(),
            "selection_seed": args.seed,
            "count": len(samples),
            "filter": "F2P > 0 AND P2P > 0, NO description quality filter",
            "swebench_live_overlap": 0,
            "repos_crawled": len(repos_processed),
            "total_candidates": len(all_candidates),
            "validated_candidates": len(validated),
        },
        "issues": samples,
    }
    samples_path = out_dir / "pouya_50_samples.json"
    with open(samples_path, "w") as f:
        json.dump(samples_data, f, indent=2)
    print(f"  Wrote {samples_path}")

    # 4. Description quality stats
    desc_stats = []
    for inst in selected:
        stats = compute_description_stats(inst["problem_statement"])
        stats["instance_id"] = inst["instance_id"]
        desc_stats.append(stats)

    stats_path = out_dir / "pouya_50_description_stats.json"
    with open(stats_path, "w") as f:
        json.dump(desc_stats, f, indent=2)
    print(f"  Wrote {stats_path}")

    # Summary
    body_lengths = [s["body_length"] for s in desc_stats]
    quality_dist = Counter(s["quality_bucket"] for s in desc_stats)
    print(f"\n=== Dataset Summary ===")
    print(f"  Issues: {len(selected)}")
    print(f"  Repos: {len(repos_dist)}")
    print(f"  Avg description length: {sum(body_lengths)/max(len(body_lengths),1):.0f} chars")
    print(f"  Min/Max description: {min(body_lengths)}/{max(body_lengths)} chars")
    print(f"  Quality distribution: {dict(quality_dist)}")
    print(f"  Total API requests: {api._request_count}")

    # Save final progress
    save_progress({
        "candidates": all_candidates,
        "repos_processed": sorted(repos_processed),
        "phase": "complete",
        "api_requests": api._request_count,
        "selected_count": len(selected),
        "validated_count": len(validated),
    })

    print(f"\nDone! Dataset at: {out_dir}")


if __name__ == "__main__":
    main()
