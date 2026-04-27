"""
Run solver on enhanced issues or baseline (non-enhanced) issues.

Enhanced mode (default):
1. Load enhancement results from results/enhancement_benchmark/
2. Run solver on each enhanced issue
3. Save to results/solving_after_enhancement/

Baseline mode (--baseline-mode):
1. Load original issues from samples JSON
2. Run solver on original (non-enhanced) issue text
3. Save to results/solving_baseline/
"""

import argparse
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))

from src.utils.llm_client import get_client
from src.utils.github_client import GitHubMultiTokenClient
from src.utils.patch_utils import extract_patch_from_response, evaluate_patch
from src.solvers.openhands.agent import run_openhands_solver_with_retry

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

_DEFAULT_SAMPLES = _root / "data" / "samples" / "swe_bench_live_10_samples.json"
_DEFAULT_ENHANCEMENT_DIR = _root / "results" / "enhancement_benchmark"
_DEFAULT_ENHANCED_RESULTS_DIR = _root / "results" / "solving_after_enhancement"
_DEFAULT_BASELINE_RESULTS_DIR = _root / "results" / "solving_baseline"
_DEFAULT_GT_DIR = _root / "data" / "ground_truth_swe_bench_live"

try:
    from secrets import GITHUB_TOKENS
except ImportError:
    raise ImportError("secrets.py not found. Copy secrets_example.py to secrets.py and add your GitHub PATs.")
gh_client = GitHubMultiTokenClient(GITHUB_TOKENS)

SYSTEM_PROMPT = """You are a code diff generator. Your ONLY task:
1. Look at the BEFORE code (current state)
2. Look at the AFTER code (desired state)
3. Generate a unified diff patch showing the transformation from BEFORE to AFTER

Output format requirements:
- Start with: diff --git a/path b/path
- Then: --- a/path and +++ b/path
- Then hunks with @@ -start,count +start,count @@
- Context lines (unchanged): start with single space
- Removed lines: start with -
- Added lines: start with +
- Include 3+ context lines before and after each change
- End with newline

Output ONLY the patch. No explanations."""

TASK_TEMPLATE = """## Issue: {title}
{body}

## BEFORE (current code) and AFTER (desired code):
{source_code}

## GENERATE DIFF PATCH
Find the exact differences between BEFORE and AFTER code.
Output a complete unified diff patch that transforms BEFORE into AFTER exactly.
Use standard diff format with context lines, no truncation."""


def fetch_file_content(owner: str, repo: str, filepath: str, ref: str = "HEAD") -> str | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filepath}"
    if ref != "HEAD":
        url += f"?ref={ref}"
    data = gh_client.get_json(url)
    if data and "content" in data:
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return None


def prepare_context(issue: dict, title: str, body: str) -> str:
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

    return TASK_TEMPLATE.format(
        repo_name=f"{owner}/{repo}",
        issue_number=issue["issue_number"],
        title=title,
        body=body[:3000],
        changed_files="\n".join(f"- {f}" for f in changed_files),
        source_code="\n\n".join(source_code_parts) if source_code_parts else "(No source)",
    )


def run_openai_agents_sdk(issue_context: str) -> dict:
    """OpenAI Agents SDK solver. Uses vLLM Gemma 3 when USE_VLLM=1 (Ollama out)."""
    import httpx
    from openai import AsyncOpenAI
    from agents import Agent, ModelSettings, Runner, set_default_openai_client

    use_vllm = os.environ.get("USE_VLLM", "0").lower() in ("1", "true", "yes")
    if use_vllm:
        base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:8001/v1")
        model = os.environ.get("OPENAI_MODEL", "gemma-3-12b-it")
        api_key = "vllm"
    else:
        base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")
        model = os.environ.get("OPENAI_MODEL", "gpt-oss:120b")
        api_key = "ollama"

    os.environ.setdefault("OPENAI_API_KEY", api_key)
    os.environ.setdefault("OPENAI_BASE_URL", base_url)

    custom_client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(1800.0),
    )
    set_default_openai_client(custom_client)

    agent = Agent(
        name="issue_solver",
        instructions=SYSTEM_PROMPT,
        model=model,
        model_settings=ModelSettings(temperature=0),
    )
    start = time.time()
    result = Runner.run_sync(agent, issue_context)
    return {"response": result.final_output, "elapsed_s": time.time() - start, "model": model}


def load_sample_issues(samples_path: Path, max_issues: int) -> list[dict]:
    with open(samples_path) as f:
        data = json.load(f)

    if isinstance(data, dict) and "issues" in data:
        issues = data["issues"]
    elif isinstance(data, list):
        issues = data
    else:
        raise ValueError(f"Unsupported samples format in {samples_path}")

    return issues[:max_issues]


def build_enhanced_tasks(
    issues: list[dict],
    enhancement_dir: Path,
    output_dir: Path,
    solver: str,
) -> list[dict]:
    # Build lookup: (owner_lower, repo_lower, issue_num) -> sample issue
    sample_lookup = {}
    for issue in issues:
        key = (issue["pr_owner"].lower(), issue["pr_repo"].lower(), int(issue["issue_number"]))
        sample_lookup[key] = issue

    tasks = []
    for ef in sorted(enhancement_dir.glob("*__*__*__*.json")):
        parts = ef.stem.split("__")
        if len(parts) != 4:
            continue

        agent_id, owner, repo, issue_num_raw = parts
        try:
            issue_num = int(issue_num_raw)
        except ValueError:
            continue

        key = (owner.lower(), repo.lower(), issue_num)
        if key not in sample_lookup:
            continue

        sample = sample_lookup[key]

        with open(ef) as f:
            enh = json.load(f)

        issue_id = enh.get("issue_id", f"{owner}/{repo}#{issue_num}")
        out_file = output_dir / f"{solver}_after_enhancement__{agent_id}__{owner}__{repo}__{issue_num}.json"

        tasks.append(
            {
                "issue_id": issue_id,
                "agent_id": agent_id,
                "owner": owner,
                "repo": repo,
                "issue_num": issue_num,
                "title": enh.get("enhanced_title", ""),
                "body": enh.get("enhanced_body", ""),
                "input_type": "enhanced",
                "out_file": out_file,
                "pr_files": sample.get("pr_files", []),
                "pr_base_sha": sample.get("pr_base_sha", "HEAD"),
            }
        )

    return tasks


def build_baseline_tasks(issues: list[dict], output_dir: Path, solver: str) -> list[dict]:
    tasks = []
    for issue in issues:
        # Handle both JSON formats (samples vs harness)
        if "repo" in issue and "/" in issue["repo"]:
            # Harness format: repo = "owner/repo"
            owner, repo = issue["repo"].split("/", 1)
        else:
            # Samples format: separate pr_owner and pr_repo
            owner = issue["pr_owner"]
            repo = issue["pr_repo"]

        # Handle different field names for issue number
        if "pull_number" in issue:
            issue_num = int(issue["pull_number"])
        else:
            issue_num = int(issue["issue_number"])

        # Get instance_id or construct it
        issue_id = issue.get("instance_id") or issue.get("issue_id") or issue.get("_swe_live_instance_id") or f"{owner}/{repo}#{issue_num}"

        # Get title and body (handle different field names)
        title = issue.get("title", "")
        body = issue.get("body", "") or issue.get("problem_statement", "")

        out_file = output_dir / f"{solver}__{owner}__{repo}__{issue_num}.json"

        tasks.append(
            {
                "issue_id": issue_id,
                "agent_id": "baseline_no_enhancement",
                "owner": owner,
                "repo": repo,
                "issue_num": issue_num,
                "title": title,
                "body": body,
                "input_type": "baseline",
                "out_file": out_file,
                "pr_files": issue.get("pr_files", []),
                "pr_base_sha": issue.get("pr_base_sha", issue.get("base_commit", "HEAD")),
                "issue": issue,  # Pass full issue dict for source code extraction
            }
        )

    return tasks


def solve_one_task(task: dict, solver: str, gt_dir: Path, use_openai_sdk: bool, use_vllm: bool, client) -> tuple[dict, bool]:
    out_file: Path = task["out_file"]
    if out_file.exists():
        return {}, True

    owner = task["owner"]
    repo = task["repo"]
    issue_num = task["issue_num"]

    gt_file = gt_dir / f"{owner}__{repo}__{issue_num}.json"
    gt = json.load(open(gt_file)) if gt_file.exists() else {}

    # pr_files come from samples (task dict), not ground truth
    pr_files = task.get("pr_files", [])

    # Use the original issue dict if available (for source code extraction)
    # Otherwise construct one with the old format
    if "issue" in task:
        issue = task["issue"]
        # Ensure backward compatibility fields exist
        if "pr_owner" not in issue:
            issue["pr_owner"] = owner
        if "pr_repo" not in issue:
            issue["pr_repo"] = repo
        if "issue_number" not in issue:
            issue["issue_number"] = issue_num
        if "pr_files" not in issue:
            issue["pr_files"] = pr_files
        if "pr_base_sha" not in issue and "base_commit" not in issue:
            issue["pr_base_sha"] = task.get("pr_base_sha", "HEAD")
    else:
        issue = {
            "pr_owner": owner,
            "pr_repo": repo,
            "issue_number": issue_num,
            "title": task["title"],
            "body": task["body"],
            "pr_files": pr_files,
            "pr_base_sha": task.get("pr_base_sha", "HEAD"),
        }

    context = prepare_context(issue, task["title"], task["body"])

    try:
        if solver == "openhands":
            # --- OpenHands solver ---
            changed_files = ", ".join(f["filename"] for f in pr_files)
            # Extract ACTUAL source code from repository at base_commit
            # This provides the LLM with EXACT context to generate patches that will apply
            try:
                from src.utils.source_code_extractor import SourceCodeExtractor
                extractor = SourceCodeExtractor()
                # Use Option 4: Hybrid approach - show before/after code
                source_code = extractor.extract_before_after_code_for_instance(issue)
                logger.info(f"Extracted {len(source_code)} chars of source code from {issue.get('repo', '?')} @ {issue.get('base_commit', '?')[:8]}")
            except Exception as e:
                logger.warning(f"Failed to extract source code: {e}. Falling back to GitHub API.")
                # Fallback to old method
                source_parts = []
                for f in pr_files[:5]:
                    content = fetch_file_content(owner, repo, f["filename"], issue.get("pr_base_sha", "HEAD"))
                    if content:
                        lines = content.split("\n")
                        if len(lines) > 200:
                            # Use non-diff notation to avoid teaching LLM truncation patterns
                            content = "\n".join(lines[:200]) + f"\n\n[SOURCE TRUNCATED - {len(lines)-200} additional lines omitted for brevity]"
                        source_parts.append(f"### File: {f['filename']}\n```\n{content}\n```")
                    time.sleep(0.3)
                source_code = "\n\n".join(source_parts) if source_parts else ""
            fw_result = run_openhands_solver_with_retry(
                issue=issue,
                title=task["title"],
                body=task["body"],
                changed_files=changed_files,
                source_code=source_code,
                max_retries=2,  # Total of 3 attempts
            )
            patch = fw_result.get("patch", "")
            if not patch:
                patch = extract_patch_from_response(fw_result.get("response", ""))
            elapsed = fw_result["elapsed_s"]
            model_name = fw_result.get("model", "gpt-oss:120b")
            error = fw_result.get("error")
        elif use_openai_sdk:
            # --- OpenAI Agents SDK solver ---
            fw_result = run_openai_agents_sdk(context)
            response = fw_result["response"]
            patch = extract_patch_from_response(response)
            elapsed = fw_result["elapsed_s"]
            model_name = fw_result.get("model", "llama3.3:70b-instruct-fp16")
            error = None
        # NOTE: simple_solver is commented out for now — see ITERATION3_SETUP.md
        # else:
        #     start = time.time()
        #     response, _meta = client.generate(SYSTEM_PROMPT, context)
        #     elapsed = time.time() - start
        #     patch = extract_patch_from_response(response)
        #     model_name = "gemma3:12b"
        #     error = None
        else:
            raise ValueError(f"Unknown solver: {solver}")

        eval_m = evaluate_patch(patch, gt.get("patch", ""), pr_files)
        result = {
            "issue_id": task["issue_id"],
            "solver": solver,
            "input": task["input_type"],
            "agent": task["agent_id"],
            "model": model_name,
            "patch": patch,
            "elapsed_s": elapsed,
            "evaluation": eval_m,
            "error": error,
        }

        # Include validation metrics if available (from enhanced solvers)
        if "validation" in fw_result:
            result["validation"] = fw_result["validation"]
        if "sanitization" in fw_result:
            result["sanitization"] = fw_result["sanitization"]
        if "attempts" in fw_result:
            result["attempts"] = fw_result["attempts"]
        print(
            f"    Time={elapsed:.1f}s  Sim={eval_m.get('content_similarity', 0):.3f}  "
            f"Patch={len(patch)}ch  FileOvlp={eval_m.get('file_overlap', 0):.2f}"
        )
    except Exception as e:  # noqa: BLE001
        result = {
            "issue_id": task["issue_id"],
            "solver": solver,
            "input": task["input_type"],
            "agent": task["agent_id"],
            "model": "unknown",
            "patch": "",
            "elapsed_s": 0,
            "evaluation": {"has_patch": False},
            "error": str(e)[:500],
        }
        print(f"    ERROR: {e}")

    with open(out_file, "w") as f:
        json.dump(result, f, indent=2)

    return result, False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-issues", type=int, default=10)
    parser.add_argument(
        "--solver",
        type=str,
        default="openhands",
        choices=["openhands", "openai_agents_sdk"],
        # NOTE: simple_solver is commented out — see docs/ITERATION3_SETUP.md
        help="Solver agent: openhands (default) or openai_agents_sdk",
    )
    parser.add_argument(
        "--samples",
        type=str,
        default=str(_DEFAULT_SAMPLES),
        help=f"Samples JSON path (default: {_DEFAULT_SAMPLES})",
    )
    parser.add_argument(
        "--gt-dir",
        type=str,
        default=None,
        help="Directory of ground-truth JSON files (default: data/ground_truth_swe_bench_live/)",
    )
    parser.add_argument(
        "--enhancement-dir",
        type=str,
        default=str(_DEFAULT_ENHANCEMENT_DIR),
        help=f"Enhancement results directory (default: {_DEFAULT_ENHANCEMENT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: results/solving_after_enhancement or results/solving_baseline in baseline mode)",
    )
    parser.add_argument(
        "--baseline-mode",
        action="store_true",
        help="Run solver on original sample issues instead of enhancement files",
    )
    args = parser.parse_args()

    samples_path = Path(args.samples)
    gt_dir = Path(args.gt_dir) if args.gt_dir else _DEFAULT_GT_DIR
    enhancement_dir = Path(args.enhancement_dir)
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = _DEFAULT_BASELINE_RESULTS_DIR if args.baseline_mode else _DEFAULT_ENHANCED_RESULTS_DIR

    issues = load_sample_issues(samples_path, args.max_issues)

    if args.baseline_mode:
        tasks = build_baseline_tasks(issues, output_dir, args.solver)
        mode_name = "Baseline Solving"
    else:
        tasks = build_enhanced_tasks(issues, enhancement_dir, output_dir, args.solver)
        mode_name = "Solving After Enhancement"

    if not tasks:
        if args.baseline_mode:
            print(f"No baseline tasks found from samples: {samples_path}")
        else:
            print(f"No enhancement results found in: {enhancement_dir}")
            print("Run scripts/enhancers/run_enhancement_benchmark.py first.")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    use_openai_sdk = args.solver == "openai_agents_sdk"
    use_vllm = os.environ.get("USE_VLLM", "0").lower() in ("1", "true", "yes")

    print(f"{mode_name} — {args.solver}")
    if args.solver == "openhands":
        from src.solvers.openhands.agent import _MODEL, _BASE_URL
        print(f"  (OpenHands LLM, model={_MODEL}, base_url={_BASE_URL})")
    elif use_openai_sdk:
        if use_vllm:
            print("  (OpenAI Agents SDK, Gemma 3 12B via vLLM localhost:8001)")
        else:
            print("  (OpenAI Agents SDK, gpt-oss via Ollama localhost:11434)")
    print(f"  Tasks: {len(tasks)}")
    print(f"  Output: {output_dir}")
    print()

    client = None

    for idx, task in enumerate(tasks, start=1):
        print(f"  [{idx}/{len(tasks)}] {task['agent_id']} / {task['issue_id']}...", flush=True)

        _result, cached = solve_one_task(
            task=task,
            solver=args.solver,
            gt_dir=gt_dir,
            use_openai_sdk=use_openai_sdk,
            use_vllm=use_vllm,
            client=client,
        )
        if cached:
            print("    (cached)")

    print("\nDone.")


if __name__ == "__main__":
    main()
