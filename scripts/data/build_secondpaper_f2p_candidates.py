#!/usr/bin/env python3
"""
Build a deterministic candidate pool from the second-work hard dataset for exact
FAIL_TO_PASS / PASS_TO_PASS derivation.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
import sys

sys.path.insert(0, str(ROOT))

from src.utils.github_client import GitHubMultiTokenClient
from swebench.harness.constants import MAP_REPO_TO_EXT

DEFAULT_DATASET = Path("/home/22pf2/LLMforGithubIssuesRefactor/data/rq3/all_hard_issues_dataset.json")
DEFAULT_OUTPUT = ROOT / "data" / "samples" / "second_paper_hard_candidates_for_f2p_p2p.json"

TEST_PATH_HINTS = ("test", "tests", "testing", "e2e", "spec", "specs")


def _parse_tokens(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def _read_tokens_from_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    raw = path.read_text().strip()
    if not raw:
        return []
    if "," in raw:
        return _parse_tokens(raw)
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _extract_tokens_constant(py_file: Path, var_name: str = "GITHUB_TOKENS") -> list[str]:
    if not py_file.exists():
        return []
    try:
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
    except SyntaxError:
        return []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == var_name:
                value = node.value
                if not isinstance(value, (ast.List, ast.Tuple)):
                    return []
                out: list[str] = []
                for elt in value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        if elt.value.strip():
                            out.append(elt.value.strip())
                return out
    return []


def _load_legacy_script_tokens() -> list[str]:
    legacy_sources = [
        ROOT / "scripts" / "solvers" / "run_pilot_benchmark.py",
        ROOT / "scripts" / "solvers" / "run_simple_solver.py",
        ROOT / "scripts" / "enhancers" / "run_solving_after_enhancement.py",
    ]
    merged: list[str] = []
    for src in legacy_sources:
        merged.extend(_extract_tokens_constant(src))
    seen: set[str] = set()
    uniq: list[str] = []
    for tok in merged:
        if tok not in seen:
            seen.add(tok)
            uniq.append(tok)
    return uniq


def _build_gh_client(
    tokens_csv: str,
    tokens_file: Path | None,
    allow_legacy_fallback: bool,
) -> tuple[GitHubMultiTokenClient | None, str]:
    cli_tokens = _parse_tokens(tokens_csv)
    if cli_tokens:
        return GitHubMultiTokenClient(cli_tokens), "cli --gh-tokens"
    if tokens_file is not None:
        file_tokens = _read_tokens_from_file(tokens_file)
        if file_tokens:
            return GitHubMultiTokenClient(file_tokens), f"file {tokens_file}"
    env_tokens = _parse_tokens(os.environ.get("GITHUB_TOKENS", ""))
    if env_tokens:
        return GitHubMultiTokenClient(env_tokens), "env GITHUB_TOKENS"
    single = os.environ.get("GITHUB_TOKEN", "").strip()
    if single:
        return GitHubMultiTokenClient([single]), "env GITHUB_TOKEN"
    if allow_legacy_fallback:
        legacy_tokens = _load_legacy_script_tokens()
        if legacy_tokens:
            return GitHubMultiTokenClient(legacy_tokens), "legacy script constants"
    return None, "none"


def _parse_pr_number(closure_url: str) -> int | None:
    m = re.match(r"^https://github\.com/[^/]+/[^/]+/pull/(\d+)$", closure_url.strip())
    if not m:
        return None
    return int(m.group(1))


def _same_repo_pr(repo_name: str, closure_url: str) -> bool:
    m = re.match(r"^https://github\.com/([^/]+)/([^/]+)/pull/\d+$", closure_url.strip())
    if not m:
        return False
    return f"{m.group(1)}/{m.group(2)}".lower() == repo_name.lower()


def _is_test_path(path: str) -> bool:
    p = path.lower()
    return any(tok in p for tok in TEST_PATH_HINTS)


def _fetch_pr_files(client: GitHubMultiTokenClient | None, repo_name: str, pr_number: int) -> list[dict[str, Any]]:
    if client is None:
        raise RuntimeError("GitHub auth client required for candidate collection.")
    owner, repo = repo_name.split("/", 1)
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files?per_page=100&page={page}"
        payload = client.get_json(url)
        if payload is None:
            raise RuntimeError(f"Failed GitHub PR files API: {repo_name}#{pr_number} page={page}")
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected GitHub response type for {repo_name}#{pr_number}: {type(payload)}")
        if not payload:
            break
        out.extend(payload)
        if len(payload) < 100:
            break
        page += 1
    return out


def _load_hard_rows(path: Path) -> list[dict[str, Any]]:
    obj = json.loads(path.read_text())
    if isinstance(obj, dict) and "issues" in obj:
        return obj["issues"]
    if isinstance(obj, list):
        return obj
    raise ValueError(f"Unsupported dataset shape in {path}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--max-files", type=int, default=80)
    p.add_argument("--gh-tokens", type=str, default="")
    p.add_argument("--gh-tokens-file", type=Path, default=None)
    p.add_argument("--allow-legacy-token-fallback", action="store_true")
    p.add_argument("--require-github-auth", action="store_true")
    p.add_argument(
        "--repo-allowlist",
        type=str,
        default="",
        help="Comma-separated repo names to include. Empty means all harness-supported python repos.",
    )
    args = p.parse_args()

    rows = _load_hard_rows(args.dataset)
    allow = {x.strip() for x in args.repo_allowlist.split(",") if x.strip()}

    gh_client, gh_source = _build_gh_client(
        tokens_csv=args.gh_tokens,
        tokens_file=args.gh_tokens_file,
        allow_legacy_fallback=args.allow_legacy_token_fallback,
    )
    if args.require_github_auth and gh_client is None:
        raise RuntimeError("GitHub auth required but no token source found.")
    print(f"GitHub token source: {gh_source}")

    # Deterministic order.
    rows_sorted = sorted(
        rows,
        key=lambda r: (
            str(r.get("repo_name", "")),
            int(r.get("issue_number", 0)),
            int(r.get("issue_id", 0)),
        ),
    )

    out: list[dict[str, Any]] = []
    skipped = {
        "not_py_repo": 0,
        "not_allowlisted": 0,
        "not_pull_closure": 0,
        "cross_repo_or_bad_url": 0,
        "too_many_files": 0,
        "no_test_files": 0,
        "no_non_test_files": 0,
        "api_errors": 0,
    }

    for row in rows_sorted:
        repo_name = str(row.get("repo_name", ""))
        if MAP_REPO_TO_EXT.get(repo_name) != "py":
            skipped["not_py_repo"] += 1
            continue
        if allow and repo_name not in allow:
            skipped["not_allowlisted"] += 1
            continue

        src = row.get("source_repo_entry", {}) or {}
        closure_type = str(src.get("closure_type", ""))
        closure_url = str(src.get("closure_url", ""))
        if closure_type != "pull_request":
            skipped["not_pull_closure"] += 1
            continue
        if not _same_repo_pr(repo_name, closure_url):
            skipped["cross_repo_or_bad_url"] += 1
            continue

        pr_number = _parse_pr_number(closure_url)
        if pr_number is None:
            skipped["cross_repo_or_bad_url"] += 1
            continue

        try:
            pr_files = _fetch_pr_files(gh_client, repo_name, pr_number)
        except Exception:
            skipped["api_errors"] += 1
            continue

        if len(pr_files) > args.max_files:
            skipped["too_many_files"] += 1
            continue

        test_files = [f for f in pr_files if _is_test_path(str(f.get("filename", "")))]
        non_test_files = [f for f in pr_files if not _is_test_path(str(f.get("filename", "")))]
        if not test_files:
            skipped["no_test_files"] += 1
            continue
        if not non_test_files:
            skipped["no_non_test_files"] += 1
            continue

        out.append(
            {
                "repo_name": repo_name,
                "issue_number": int(row["issue_number"]),
                "closure_url": closure_url,
                "pull_number": int(pr_number),
                "num_files": len(pr_files),
                "num_test_files": len(test_files),
                "num_non_test_files": len(non_test_files),
            }
        )

    payload = {
        "dataset": str(args.dataset),
        "selection_method": "deterministic sorted scan over second-work hard dataset; same-repo merged PR; harness-supported python repo; has both test and non-test changed files",
        "repo_allowlist": sorted(allow) if allow else [],
        "max_files": args.max_files,
        "available_rows": len(out),
        "skipped": skipped,
        "candidates": out,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {len(out)} candidates to {args.output}")


if __name__ == "__main__":
    main()
