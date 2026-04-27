#!/usr/bin/env python3
"""
Derive exact FAIL_TO_PASS / PASS_TO_PASS sets for a custom second-paper sample.

Method:
1) Build SWE-bench-style instances from issue+PR metadata:
   - base_commit = PR base SHA
   - patch = non-test hunk diff
   - test_patch = test-only hunk diff
2) Run harness twice on the same instances:
   - baseline run: empty model patch
   - gold run: reference patch
3) Parse test outputs from both runs and derive exact sets:
   - FAIL_TO_PASS: failed in baseline and passed in gold
   - PASS_TO_PASS: passed in baseline and passed in gold

This script is intentionally scoped to Python harness-supported repos.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from unidiff import PatchSet

from swebench.harness.grading import get_logs_eval, test_failed, test_passed
from swebench.harness.test_spec.test_spec import make_test_spec
from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS, MAP_REPO_TO_EXT


ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from src.utils.github_client import GitHubMultiTokenClient

DEFAULT_SELECTION_JSON = (
    ROOT / "data" / "samples" / "second_paper_py10_for_exact_f2p_p2p.json"
)
DEFAULT_WORK_DIR = ROOT / "data" / "samples" / "second_paper_py10_exact_f2p_p2p"

TEST_PATH_HINTS = ("test", "tests", "testing", "e2e", "spec", "specs")


LIVE_SPECS_OVERRIDES: dict[str, dict[str, Any]] = {
    # Fixes editable-build failures for modern matplotlib/scikit-learn live tasks.
    "matplotlib/matplotlib": {
        "python": "3.11",
        "packages": "numpy scipy pandas pytest setuptools",
        "install": 'MPLLOCALFREETYPE=0 MPLLOCALQHULL=0 python -m pip install --no-build-isolation -e ".[dev]"',
        "pre_install": [
            "apt-get -y update && DEBIAN_FRONTEND=noninteractive apt-get -y --fix-missing -o Acquire::Retries=3 install libfreetype6-dev libpng-dev libqhull-dev",
        ],
        "pip_packages": [
            "pytest",
            "'meson-python>=0.18.0'",
            "'packaging>=24.2'",
            "'pyproject-metadata>=0.9.0'",
            "'setuptools>=75.8.1'",
            "'wheel>=0.46.0'",
            "'numpy>=1.26.0'",
        ],
        "test_cmd": "pytest -rA",
    },
    "scikit-learn/scikit-learn": {
        "python": "3.10",
        "packages": "'numpy==1.19.5' 'scipy==1.6.0' 'cython==3.0.10' pytest 'pandas<2.0.0' 'matplotlib<3.9.0' setuptools pytest joblib threadpoolctl",
        "install": "python -m pip install -v --no-build-isolation -e .",
        "pip_packages": [
            "cython",
            "'setuptools>=75.8.1'",
            "'meson-python>=0.18.0'",
            "'ninja>=1.11.1'",
            "'packaging>=24.2'",
            "'pyproject-metadata>=0.9.0'",
            "'wheel>=0.46.0'",
        ],
        "test_cmd": "pytest -rA",
    },
    # Flask tasks in the second-work sample can be older than the default live fallback assumptions.
    # Pin dependencies to avoid import-time failures (e.g., url_quote removal in newer Werkzeug).
    "pallets/flask": {
        "python": "3.10",
        "packages": "requirements.txt",
        "install": "python -m pip install -e .",
        "pip_packages": [
            "setuptools==70.0.0",
            "'Werkzeug<2.1'",
            "'Jinja2<3.1'",
            "'itsdangerous<2.1'",
            "'click<8.1'",
            "'MarkupSafe<2.1'",
        ],
        "test_cmd": "pytest -rA",
    },
}


@dataclass
class Candidate:
    repo_name: str
    issue_number: int
    pull_number: int
    closure_url: str


def _split_patch(diff_text: str) -> tuple[str, str]:
    patch_fix = ""
    patch_test = ""
    for hunk in PatchSet(diff_text):
        path = (hunk.path or "").lower()
        if any(tok in path for tok in TEST_PATH_HINTS):
            patch_test += str(hunk)
        else:
            patch_fix += str(hunk)
    return patch_fix, patch_test


def _load_candidates(selection_json: Path, max_issues: int) -> list[Candidate]:
    payload = json.loads(selection_json.read_text())
    if isinstance(payload, dict):
        rows = payload.get("selected") or payload.get("candidates") or []
    else:
        rows = payload
    out: list[Candidate] = []
    for row in rows[:max_issues]:
        out.append(
            Candidate(
                repo_name=str(row["repo_name"]),
                issue_number=int(row["issue_number"]),
                pull_number=int(row["pull_number"]),
                closure_url=str(row["closure_url"]),
            )
        )
    return out


def _gh_headers(token: str | None) -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "BenchmarkLLMAgent"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _parse_tokens(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def _read_tokens_from_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    raw = path.read_text().strip()
    if not raw:
        return []
    # Supports comma-separated or one-token-per-line files.
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
                tokens: list[str] = []
                for elt in value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        if elt.value.strip():
                            tokens.append(elt.value.strip())
                return tokens
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
    # Preserve order while deduping.
    seen: set[str] = set()
    unique: list[str] = []
    for tok in merged:
        if tok not in seen:
            seen.add(tok)
            unique.append(tok)
    return unique


def _build_gh_client(
    tokens_csv: str,
    tokens_file: Path | None = None,
    allow_legacy_fallback: bool = False,
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


def _http_json(session: requests.Session, client: GitHubMultiTokenClient | None, url: str) -> dict[str, Any]:
    if client:
        payload = client.get_json(url)
        if payload is not None:
            return payload
        raise RuntimeError(f"GitHub API JSON fetch failed: {url}")
    resp = session.get(url, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed API {url}: {resp.status_code}")
    return resp.json()


def _http_text(
    session: requests.Session,
    client: GitHubMultiTokenClient | None,
    url: str,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    if client:
        resp = client.get(url, extra_headers=extra_headers)
        if resp is None:
            return 599, ""
        return resp.status_code, resp.text
    resp = session.get(url, timeout=60, headers=extra_headers)
    return resp.status_code, resp.text


def _fetch_issue_and_pr(
    session: requests.Session,
    client: GitHubMultiTokenClient | None,
    c: Candidate,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    owner, repo = c.repo_name.split("/", 1)
    issue_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{c.issue_number}"
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{c.pull_number}"
    issue_obj = _http_json(session, client, issue_url)
    pr_obj = _http_json(session, client, pr_url)
    diff_url = pr_obj.get("diff_url") or f"https://github.com/{owner}/{repo}/pull/{c.pull_number}.diff"
    code, text = _http_text(session, client, diff_url, {"Accept": "application/vnd.github.v3.diff"})
    if code != 200:
        raise RuntimeError(f"Failed PR diff {diff_url}: {code}")
    return issue_obj, pr_obj, text


def _instance_id(repo_name: str, issue_number: int) -> str:
    return f"{repo_name.replace('/', '__')}-{issue_number}"


def _build_noop_baseline_patch(
    session: requests.Session,
    client: GitHubMultiTokenClient | None,
    repo_name: str,
    base_commit: str,
) -> str:
    owner, repo = repo_name.split("/", 1)
    candidate_paths = [
        "README.md",
        "README.rst",
        "README.txt",
        "README",
        "readme.md",
        ".gitignore",
    ]
    for path in candidate_paths:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{base_commit}/{path}"
        code, text = _http_text(session, client, raw_url)
        if code != 200:
            continue

        old_lines = text.splitlines()
        # Non-empty but behavior-neutral patch.
        path_l = path.lower()
        if path_l.endswith(".md"):
            add_line = "<!-- baseline-probe-noop -->"
        elif path_l.endswith(".rst"):
            add_line = ".. baseline-probe-noop"
        elif path_l == ".gitignore":
            add_line = "# baseline-probe-noop"
        else:
            add_line = "baseline-probe-noop"
        new_lines = old_lines + [add_line]
        diff_lines = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
        )
        diff_body = "\n".join(diff_lines)
        if diff_body:
            diff_body += "\n"
        if not diff_body.strip():
            continue
        return f"diff --git a/{path} b/{path}\n{diff_body}\n"

    raise RuntimeError(
        f"{repo_name}@{base_commit}: could not create a safe non-empty baseline patch"
    )


def _build_instances(
    candidates: list[Candidate],
    gh_token: str | None,
    gh_client: GitHubMultiTokenClient | None,
) -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update(_gh_headers(gh_token))
    instances: list[dict[str, Any]] = []

    for c in candidates:
        issue_obj, pr_obj, diff_text = _fetch_issue_and_pr(session, gh_client, c)
        patch_fix, patch_test = _split_patch(diff_text)
        if not patch_fix.strip():
            raise RuntimeError(
                f"{c.repo_name}#{c.issue_number}: empty fix patch after split (cannot build gold run)"
            )
        if not patch_test.strip():
            raise RuntimeError(
                f"{c.repo_name}#{c.issue_number}: empty test patch after split (cannot derive F2P/P2P)"
            )

        title = issue_obj.get("title") or ""
        body = issue_obj.get("body") or ""
        problem_statement = f"{title}\n{body}".strip()
        base_commit = pr_obj["base"]["sha"]
        created_at = issue_obj.get("created_at") or pr_obj.get("created_at") or ""
        baseline_patch = _build_noop_baseline_patch(
            session, gh_client, c.repo_name, base_commit
        )

        inst = {
            "repo": c.repo_name,
            "pull_number": c.pull_number,
            "issue_number": c.issue_number,
            "instance_id": _instance_id(c.repo_name, c.issue_number),
            "base_commit": base_commit,
            "patch": patch_fix,
            "test_patch": patch_test,
            "problem_statement": problem_statement,
            "hints_text": "",
            "created_at": created_at,
            # Force live fallback spec builder; test command remains deterministic.
            "version": "live",
            "test_cmds": ["pytest -rA"],
            # Filled later.
            "FAIL_TO_PASS": [],
            "PASS_TO_PASS": [],
            # Internal helper used for baseline run.
            "_baseline_patch": baseline_patch,
        }
        instances.append(inst)
    return instances


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _write_predictions(path: Path, instances: list[dict[str, Any]], model_name: str, gold: bool) -> None:
    preds = []
    for inst in instances:
        preds.append(
            {
                "instance_id": inst["instance_id"],
                "model_name_or_path": model_name,
                "model_patch": inst["patch"] if gold else inst.get("_baseline_patch", ""),
            }
        )
    _write_jsonl(path, preds)


def _apply_live_specs_overrides(enabled: bool) -> None:
    if not enabled:
        return
    for repo, specs in LIVE_SPECS_OVERRIDES.items():
        MAP_REPO_VERSION_TO_SPECS.setdefault(repo, {})["live"] = specs
        MAP_REPO_TO_EXT.setdefault(repo, "py")


def _run_harness_eval(
    *,
    python_exec: Path,
    dataset_jsonl: Path,
    predictions_jsonl: Path,
    instance_ids: list[str],
    run_id: str,
    report_dir: Path,
    max_workers: int,
    timeout: int,
) -> None:
    cmd = [
        str(python_exec),
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        str(dataset_jsonl),
        "--split",
        "test",
        "--predictions_path",
        str(predictions_jsonl),
        "--instance_ids",
        *instance_ids,
        "--max_workers",
        str(max_workers),
        "--timeout",
        str(timeout),
        "--run_id",
        run_id,
        "--report_dir",
        str(report_dir),
        "--namespace",
        "none",
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def _model_dir_name(model_name: str) -> str:
    return model_name.replace("/", "__")


def _derive_sets(
    instances: list[dict[str, Any]],
    baseline_run_id: str,
    baseline_model_name: str,
    gold_run_id: str,
    gold_model_name: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    out_instances: list[dict[str, Any]] = []
    per_instance_summary: list[dict[str, Any]] = []

    baseline_model_dir = ROOT / "logs" / "run_evaluation" / baseline_run_id / _model_dir_name(baseline_model_name)
    gold_model_dir = ROOT / "logs" / "run_evaluation" / gold_run_id / _model_dir_name(gold_model_name)

    def _clean_instance_fields(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        out.pop("_baseline_patch", None)
        return out

    for inst in instances:
        iid = inst["instance_id"]
        test_spec = make_test_spec(inst)
        b_log = baseline_model_dir / iid / "test_output.txt"
        g_log = gold_model_dir / iid / "test_output.txt"

        if not b_log.exists() or not g_log.exists():
            per_instance_summary.append(
                {
                    "instance_id": iid,
                    "repo": inst["repo"],
                    "issue_number": inst["issue_number"],
                    "baseline_log_exists": b_log.exists(),
                    "gold_log_exists": g_log.exists(),
                    "error": "missing_test_output",
                }
            )
            out_instances.append(_clean_instance_fields(inst))
            continue

        b_status, b_ok = get_logs_eval(test_spec, str(b_log))
        g_status, g_ok = get_logs_eval(test_spec, str(g_log))

        if not b_ok or not g_ok:
            summary = {
                "instance_id": iid,
                "repo": inst["repo"],
                "issue_number": inst["issue_number"],
                "baseline_log_ok": b_ok,
                "gold_log_ok": g_ok,
                "error": "missing_or_unparseable_test_output",
            }
            per_instance_summary.append(summary)
            out_instances.append(_clean_instance_fields(inst))
            continue

        all_tests = sorted(set(b_status.keys()) | set(g_status.keys()))
        fail_to_pass: list[str] = []
        pass_to_pass: list[str] = []
        fail_to_fail: list[str] = []
        pass_to_fail: list[str] = []

        for t in all_tests:
            b_pass = test_passed(t, b_status)
            g_pass = test_passed(t, g_status)
            b_fail = test_failed(t, b_status)
            g_fail = test_failed(t, g_status)

            if b_fail and g_pass:
                fail_to_pass.append(t)
            elif b_pass and g_pass:
                pass_to_pass.append(t)
            elif b_fail and g_fail:
                fail_to_fail.append(t)
            elif b_pass and g_fail:
                pass_to_fail.append(t)

        updated = _clean_instance_fields(inst)
        updated["FAIL_TO_PASS"] = fail_to_pass
        updated["PASS_TO_PASS"] = pass_to_pass
        out_instances.append(updated)

        per_instance_summary.append(
            {
                "instance_id": iid,
                "repo": inst["repo"],
                "issue_number": inst["issue_number"],
                "baseline_tests_seen": len(b_status),
                "gold_tests_seen": len(g_status),
                "all_tests_union": len(all_tests),
                "FAIL_TO_PASS_count": len(fail_to_pass),
                "PASS_TO_PASS_count": len(pass_to_pass),
                "FAIL_TO_FAIL_count": len(fail_to_fail),
                "PASS_TO_FAIL_count": len(pass_to_fail),
            }
        )

    return out_instances, per_instance_summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--selection-json", type=Path, default=DEFAULT_SELECTION_JSON)
    p.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    p.add_argument("--max-issues", type=int, default=10)
    p.add_argument("--smoke-instance-id", type=str, default="")
    p.add_argument("--python-exec", type=Path, default=Path(sys.executable))
    p.add_argument("--max-workers", type=int, default=1)
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--gh-token", type=str, default="")
    p.add_argument(
        "--gh-tokens",
        type=str,
        default="",
        help="Comma-separated GitHub tokens. If omitted, uses env GITHUB_TOKENS.",
    )
    p.add_argument(
        "--gh-tokens-file",
        type=Path,
        default=None,
        help="Optional file containing GitHub tokens (comma-separated or one token per line).",
    )
    p.add_argument(
        "--allow-legacy-token-fallback",
        action="store_true",
        help="Allow fallback to hardcoded legacy script token constants (disabled by default).",
    )
    p.add_argument(
        "--require-github-auth",
        action="store_true",
        help="Fail fast if neither GitHub token client nor single token auth is configured.",
    )
    p.add_argument(
        "--no-live-spec-overrides",
        action="store_true",
        help="Disable repo-specific live environment overrides for known problematic repos.",
    )
    args = p.parse_args()

    args.work_dir.mkdir(parents=True, exist_ok=True)
    _apply_live_specs_overrides(enabled=not args.no_live_spec_overrides)

    candidates = _load_candidates(args.selection_json, args.max_issues)
    if args.smoke_instance_id:
        candidates = [
            c for c in candidates if _instance_id(c.repo_name, c.issue_number) == args.smoke_instance_id
        ]
        if not candidates:
            raise ValueError(f"Smoke instance_id not found in selection: {args.smoke_instance_id}")
    gh_client, gh_client_source = _build_gh_client(
        args.gh_tokens,
        args.gh_tokens_file,
        allow_legacy_fallback=args.allow_legacy_token_fallback,
    )
    gh_token = args.gh_token.strip() or os.environ.get("GITHUB_TOKEN", "").strip() or None
    if args.require_github_auth and gh_client is None and not gh_token:
        raise RuntimeError(
            "GitHub auth required but no tokens configured. Provide --gh-tokens/--gh-tokens-file "
            "or set GITHUB_TOKENS/GITHUB_TOKEN."
        )
    if gh_client is not None:
        print(f"Using GitHub multi-token client source: {gh_client_source}")
    elif gh_token:
        print("Using single GitHub token from --gh-token/env GITHUB_TOKEN")
    else:
        print("Using unauthenticated GitHub API access")

    instances = _build_instances(candidates, gh_token, gh_client)

    instance_ids = [x["instance_id"] for x in instances]

    dataset_raw_jsonl = args.work_dir / "custom_instances_raw.jsonl"
    preds_baseline = args.work_dir / "predictions_baseline_empty_patch.jsonl"
    preds_gold = args.work_dir / "predictions_gold_patch.jsonl"
    report_dir = args.work_dir / "eval_reports"
    run_suffix = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.work_dir.name)
    baseline_run_id = f"secondpaper_custom_baseline_probe_{run_suffix}"
    gold_run_id = f"secondpaper_custom_gold_probe_{run_suffix}"
    baseline_model_name = "baseline_noop_patch_probe"
    gold_model_name = "gold_patch_probe"

    _write_jsonl(dataset_raw_jsonl, instances)
    _write_predictions(preds_baseline, instances, baseline_model_name, gold=False)
    _write_predictions(preds_gold, instances, gold_model_name, gold=True)

    _run_harness_eval(
        python_exec=args.python_exec,
        dataset_jsonl=dataset_raw_jsonl,
        predictions_jsonl=preds_baseline,
        instance_ids=instance_ids,
        run_id=baseline_run_id,
        report_dir=report_dir / "baseline",
        max_workers=args.max_workers,
        timeout=args.timeout,
    )
    _run_harness_eval(
        python_exec=args.python_exec,
        dataset_jsonl=dataset_raw_jsonl,
        predictions_jsonl=preds_gold,
        instance_ids=instance_ids,
        run_id=gold_run_id,
        report_dir=report_dir / "gold",
        max_workers=args.max_workers,
        timeout=args.timeout,
    )

    final_instances, summary = _derive_sets(
        instances=instances,
        baseline_run_id=baseline_run_id,
        baseline_model_name=baseline_model_name,
        gold_run_id=gold_run_id,
        gold_model_name=gold_model_name,
    )

    final_jsonl = args.work_dir / "custom_instances_with_f2p_p2p.jsonl"
    summary_json = args.work_dir / "f2p_p2p_derivation_summary.json"
    _write_jsonl(final_jsonl, final_instances)
    summary_json.write_text(
        json.dumps(
            {
                "selection_json": str(args.selection_json),
                "num_instances": len(final_instances),
                "instance_ids": [x["instance_id"] for x in final_instances],
                "per_instance": summary,
            },
            indent=2,
        )
    )

    print(f"Wrote raw instances: {dataset_raw_jsonl}")
    print(f"Wrote final instances: {final_jsonl}")
    print(f"Wrote summary: {summary_json}")


if __name__ == "__main__":
    main()
