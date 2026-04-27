"""
Simple solver using Gemma 3 12B (HuggingFace or Ollama).

Use when Ollama is unavailable. Same interface as run_pilot_benchmark
but with a single LLM-based solver instead of 6 frameworks.

Usage:
    USE_OLLAMA=0 python scripts/solvers/run_simple_solver.py [--max-issues 10]
"""

import json
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))

from src.utils.llm_client import get_client
from src.utils.github_client import GitHubMultiTokenClient
from src.utils.patch_utils import extract_patch_from_response, evaluate_patch

import base64

# Default to the SWE-bench-Live 10-issue sample (Iteration 1).
# Override via --samples and --gt-dir CLI args.
_DEFAULT_SAMPLES = _root / "data" / "samples" / "swe_bench_live_10_samples.json"
_DEFAULT_GT_DIR  = _root / "data" / "ground_truth_swe_bench_live"
RESULTS_DIR = _root / "results" / "pilot_solver_benchmark"
MAX_WORKERS = 2  # LLM inference is sequential per process; limit parallelism

try:
    from secrets import GITHUB_TOKENS
except ImportError:
    raise ImportError("secrets.py not found. Copy secrets_example.py to secrets.py and add your GitHub PATs.")
gh_client = GitHubMultiTokenClient(GITHUB_TOKENS)

SYSTEM_PROMPT = """You are a software engineering agent that solves GitHub issues by producing code patches.
Given a GitHub issue (title + body) and relevant source code files, produce a unified diff patch that resolves the issue.
Output ONLY a valid unified diff patch (starting with --- and +++) that can be applied with `git apply`.
Do NOT include explanations outside the diff."""

TASK_TEMPLATE = """## GitHub Issue to Solve
**Repository**: {repo_name}
**Issue #{issue_number}**: {title}

### Issue Description
{body}

### Changed Files in the Fix (hints)
{changed_files}

### Source Code of Relevant Files
{source_code}

Produce a unified diff patch. Output ONLY the patch."""


def fetch_file_content(owner, repo, filepath, ref="HEAD"):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filepath}"
    if ref != "HEAD":
        url += f"?ref={ref}"
    data = gh_client.get_json(url)
    if data and "content" in data:
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return None


def prepare_issue_context(issue):
    owner, repo = issue["pr_owner"], issue["pr_repo"]
    pr_files = issue.get("pr_files", [])
    changed_files = [f["filename"] for f in pr_files]
    source_code_parts = []
    for f in pr_files[:5]:
        content = fetch_file_content(owner, repo, f["filename"], issue.get("pr_base_sha", "HEAD"))
        if content:
            lines = content.split("\n")
            if len(lines) > 200:
                content = "\n".join(lines[:200]) + f"\n... ({len(lines)-200} more lines)"
            source_code_parts.append(f"### File: {f['filename']}\n```\n{content}\n```")
        else:
            source_code_parts.append(f"### File: {f['filename']}\n(Could not fetch)")
        time.sleep(0.3)
    body = (issue.get("body") or "")[:3000]
    return TASK_TEMPLATE.format(
        repo_name=f"{owner}/{repo}",
        issue_number=issue["issue_number"],
        title=issue["title"],
        body=body,
        changed_files=", ".join(changed_files),
        source_code="\n\n".join(source_code_parts) if source_code_parts else "(No source)",
    )


def run_simple_solver(issue_context):
    client = get_client(max_new_tokens=4096, temperature=0)
    response, meta = client.generate(SYSTEM_PROMPT, issue_context)
    return {"response": response, "elapsed_s": meta.get("elapsed_s", 0), "tokens": {}}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-issues", type=int, default=10)
    parser.add_argument("--samples", type=str, default=None,
                        help="Path to samples JSON (default: data/samples/swe_bench_live_10_samples.json)")
    parser.add_argument("--gt-dir", type=str, default=None,
                        help="Directory of ground-truth JSONs (default: data/ground_truth_swe_bench_live/)")
    args = parser.parse_args()

    SAMPLES_PATH = Path(args.samples) if args.samples else _DEFAULT_SAMPLES
    GT_DIR = Path(args.gt_dir) if args.gt_dir else _DEFAULT_GT_DIR

    with open(SAMPLES_PATH) as f:
        issues = json.load(f)["issues"][: args.max_issues]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Simple Solver (Gemma 3 12B)")
    print(f"  Issues: {len(issues)}")
    print()

    contexts = {}
    gt_cache = {}
    for issue in issues:
        iid = f"{issue['repo_name']}#{issue['issue_number']}"
        contexts[iid] = prepare_issue_context(issue)
        gt_file = GT_DIR / f"{issue['pr_owner']}__{issue['pr_repo']}__{issue['issue_number']}.json"
        gt_cache[iid] = json.load(open(gt_file)) if gt_file.exists() else {}

    fw_name = "simple_solver"
    for i, issue in enumerate(issues):
        iid = f"{issue['repo_name']}#{issue['issue_number']}"
        result_key = f"{fw_name}__{issue['pr_owner']}__{issue['pr_repo']}__{issue['issue_number']}"
        result_file = RESULTS_DIR / f"{result_key}.json"

        if result_file.exists():
            print(f"  [{i+1}/{len(issues)}] {iid} (cached)")
            continue

        print(f"  [{i+1}/{len(issues)}] {iid}...", flush=True)
        try:
            start = time.time()
            fw_result = run_simple_solver(contexts[iid])
            total_elapsed = time.time() - start
            patch = extract_patch_from_response(fw_result["response"])
            gt = gt_cache[iid]
            eval_metrics = evaluate_patch(patch, gt.get("patch", ""), gt.get("pr_files", []))
            result_data = {
                "issue_id": iid,
                "framework": fw_name,
                "model": "gemma3:12b",
                "patch": patch,
                "elapsed_s": total_elapsed,
                "evaluation": eval_metrics,
                "error": None,
            }
            print(f"    Time={total_elapsed:.1f}s  Patch={len(patch)}ch  FileOvlp={eval_metrics['file_overlap']:.2f}")
        except Exception as e:
            result_data = {
                "issue_id": iid,
                "framework": fw_name,
                "model": "gemma3:12b",
                "patch": "",
                "elapsed_s": 0,
                "evaluation": {"has_patch": False},
                "error": str(e)[:500],
            }
            print(f"    ERROR: {e}")
        with open(result_file, "w") as f:
            json.dump(result_data, f, indent=2)

    print("\nDone.")


if __name__ == "__main__":
    main()
