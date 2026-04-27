"""
Pilot Solver Benchmark Runner.

Runs 6 framework-based solver agents on pilot sample issues using
Llama 3.3 70B via Ollama (4 parallel workers), then compares
results against ground truth.

Usage:
    python -m scripts.solvers.run_pilot_benchmark
"""

import json
import time
import os
import re
import asyncio
import base64
from pathlib import Path
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.utils.github_client import GitHubMultiTokenClient
from src.utils.patch_utils import extract_patch_from_response, evaluate_patch

OLLAMA_MODEL = "llama3.3:70b-instruct-fp16"
OLLAMA_BASE_URL = "http://localhost:11434"
SAMPLES_PATH = "data/samples/pilot_10_samples.json"
GT_DIR = "data/ground_truth"
RESULTS_DIR = "results/pilot_solver_benchmark"
MAX_WORKERS = 4

try:
    from secrets import GITHUB_TOKENS
except ImportError:
    raise ImportError("secrets.py not found. Copy secrets_example.py to secrets.py and add your GitHub PATs.")

gh_client = GitHubMultiTokenClient(GITHUB_TOKENS)

# ─── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a software engineering agent that solves GitHub issues by producing code patches.

Given a GitHub issue (title + body) and relevant source code files, you must:
1. Analyze the issue to understand the bug or feature request
2. Determine which files and lines need to change
3. Produce a unified diff patch that resolves the issue

Output ONLY a valid unified diff patch (starting with --- and +++) that can be applied with `git apply`.
Do NOT include explanations outside the diff. If you need to explain, put it in a comment within the code."""

TASK_TEMPLATE = """## GitHub Issue to Solve

**Repository**: {repo_name}
**Issue #{issue_number}**: {title}

### Issue Description
{body}

### Changed Files in the Fix (hints)
The fix involves these files: {changed_files}

### Source Code of Relevant Files
{source_code}

### Instructions
Produce a unified diff patch that fixes this issue. Output ONLY the patch."""

# ─── Helpers ──────────────────────────────────────────────────────────────────

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
        fn = f["filename"]
        content = fetch_file_content(owner, repo, fn, issue.get("pr_base_sha", "HEAD"))
        if content:
            lines = content.split("\n")
            if len(lines) > 200:
                content = "\n".join(lines[:200]) + f"\n... ({len(lines) - 200} more lines)"
            source_code_parts.append(f"### File: {fn}\n```\n{content}\n```")
        else:
            source_code_parts.append(f"### File: {fn}\n(Could not fetch content)")
        time.sleep(0.3)

    body = issue.get("body", "") or ""
    if len(body) > 3000:
        body = body[:3000] + "... (truncated)"

    return TASK_TEMPLATE.format(
        repo_name=f"{owner}/{repo}",
        issue_number=issue["issue_number"],
        title=issue["title"],
        body=body,
        changed_files=", ".join(changed_files),
        source_code="\n\n".join(source_code_parts) if source_code_parts else "(Could not fetch source files)",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Framework implementations
# ═══════════════════════════════════════════════════════════════════════════════

def run_langgraph(issue_context):
    from langgraph.graph import StateGraph, END
    from langchain_ollama import ChatOllama
    from langchain_core.messages import SystemMessage, HumanMessage
    from typing import TypedDict, Optional as Opt

    class SolverState(TypedDict):
        task: str
        response: Opt[str]
        elapsed_s: Opt[float]

    llm = ChatOllama(model=OLLAMA_MODEL, temperature=0, base_url=OLLAMA_BASE_URL, num_predict=4096)

    def solve_node(state: SolverState) -> dict:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=state["task"]),
        ]
        start = time.time()
        response = llm.invoke(messages)
        return {"response": response.content, "elapsed_s": time.time() - start}

    graph = StateGraph(SolverState)
    graph.add_node("solve", solve_node)
    graph.set_entry_point("solve")
    graph.add_edge("solve", END)
    app = graph.compile()

    result = app.invoke({"task": issue_context, "response": None, "elapsed_s": None})
    return {"response": result["response"] or "", "elapsed_s": result.get("elapsed_s", 0), "tokens": {}}


def run_llamaindex(issue_context):
    from llama_index.llms.ollama import Ollama
    from llama_index.core.llms import ChatMessage, MessageRole

    llm = Ollama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0, request_timeout=600.0,
                 additional_kwargs={"num_predict": 4096})
    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
        ChatMessage(role=MessageRole.USER, content=issue_context),
    ]
    start = time.time()
    response = llm.chat(messages)
    return {"response": response.message.content, "elapsed_s": time.time() - start, "tokens": {}}


def run_semantic_kernel(issue_context):
    from semantic_kernel import Kernel
    from semantic_kernel.connectors.ai.ollama import OllamaChatCompletion, OllamaPromptExecutionSettings
    from semantic_kernel.contents import ChatHistory

    kernel = Kernel()
    chat_service = OllamaChatCompletion(
        ai_model_id=OLLAMA_MODEL,
        host=OLLAMA_BASE_URL,
    )
    kernel.add_service(chat_service)

    settings = OllamaPromptExecutionSettings(service_id=chat_service.service_id)

    chat_history = ChatHistory()
    chat_history.add_system_message(SYSTEM_PROMPT)
    chat_history.add_user_message(issue_context)

    loop = asyncio.new_event_loop()
    start = time.time()
    try:
        result = loop.run_until_complete(
            chat_service.get_chat_message_contents(chat_history=chat_history, settings=settings)
        )
    finally:
        loop.close()

    response_text = result[0].content if result else ""
    return {"response": response_text, "elapsed_s": time.time() - start, "tokens": {}}


def run_autogen(issue_context):
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    from autogen_agentchat.messages import TextMessage
    from autogen_core import CancellationToken

    model_client = OpenAIChatCompletionClient(
        model=OLLAMA_MODEL,
        api_key="ollama",
        base_url=f"{OLLAMA_BASE_URL}/v1",
        model_info={
            "vision": False, "function_calling": False, "json_output": False,
            "family": "unknown", "structured_output": False,
        },
    )
    agent = AssistantAgent(name="issue_solver", model_client=model_client, system_message=SYSTEM_PROMPT)

    loop = asyncio.new_event_loop()
    start = time.time()
    try:
        result = loop.run_until_complete(
            agent.on_messages([TextMessage(content=issue_context, source="user")], CancellationToken())
        )
    finally:
        loop.close()

    response_text = result.chat_message.content if result.chat_message else ""
    return {"response": response_text, "elapsed_s": time.time() - start, "tokens": {}}


def run_crewai(issue_context):
    os.environ["OPENAI_API_KEY"] = "ollama"
    os.environ["OPENAI_API_BASE"] = f"{OLLAMA_BASE_URL}/v1"
    from crewai import Agent, Task, Crew, Process, LLM

    llm = LLM(model=f"ollama/{OLLAMA_MODEL}", base_url=OLLAMA_BASE_URL, temperature=0)
    solver = Agent(
        role="Issue Solver",
        goal="Produce a unified diff patch that fixes the GitHub issue",
        backstory=SYSTEM_PROMPT, llm=llm, verbose=False, allow_delegation=False,
    )
    task = Task(description=issue_context, expected_output="A unified diff patch that fixes the issue", agent=solver)
    crew = Crew(agents=[solver], tasks=[task], process=Process.sequential, verbose=False)

    start = time.time()
    result = crew.kickoff()
    usage = getattr(result, "token_usage", None)
    tokens = {}
    if usage:
        try:
            tokens = json.loads(json.dumps(usage, default=str))
        except Exception:
            tokens = {"raw": str(usage)}
    return {"response": str(result), "elapsed_s": time.time() - start, "tokens": tokens}


def run_openai_agents_sdk(issue_context):
    os.environ["OPENAI_API_KEY"] = "ollama"
    os.environ["OPENAI_BASE_URL"] = f"{OLLAMA_BASE_URL}/v1"
    from agents import Agent, Runner, ModelSettings

    agent = Agent(
        name="issue_solver", instructions=SYSTEM_PROMPT,
        model=OLLAMA_MODEL, model_settings=ModelSettings(temperature=0),
    )
    start = time.time()
    result = Runner.run_sync(agent, issue_context)
    return {"response": result.final_output, "elapsed_s": time.time() - start, "tokens": {}}


# ═══════════════════════════════════════════════════════════════════════════════

FRAMEWORKS = {
    "langgraph": run_langgraph,
    "llamaindex": run_llamaindex,
    "semantic_kernel": run_semantic_kernel,
    "autogen": run_autogen,
    "crewai": run_crewai,
    "openai_agents_sdk": run_openai_agents_sdk,
}


def run_one_task(fw_name, fw_func, issue_context, issue, gt_data):
    """Run a single (framework x issue) pair. Designed for thread pool."""
    issue_id = f"{issue['repo_name']}#{issue['issue_number']}"
    result_key = f"{fw_name}__{issue['repo_name'].replace('/','__')}__{issue['issue_number']}"
    result_file = Path(RESULTS_DIR) / f"{result_key}.json"

    if result_file.exists():
        with open(result_file) as f:
            return json.load(f)

    try:
        start_total = time.time()
        fw_result = fw_func(issue_context)
        total_elapsed = time.time() - start_total

        raw_response = fw_result.get("response", "")
        patch = extract_patch_from_response(raw_response)
        eval_metrics = evaluate_patch(patch, gt_data.get("patch", ""), gt_data.get("pr_files", []))

        result_data = {
            "issue_id": issue_id, "framework": fw_name, "model": OLLAMA_MODEL,
            "patch": patch, "raw_response_length": len(raw_response),
            "elapsed_s": total_elapsed, "fw_elapsed_s": fw_result.get("elapsed_s", 0),
            "tokens": fw_result.get("tokens", {}), "evaluation": eval_metrics, "error": None,
        }
        print(f"  [{fw_name:^22}] {issue_id:<40} "
              f"Time={total_elapsed:>6.1f}s  Patch={len(patch):>5}ch  "
              f"FileOvlp={eval_metrics['file_overlap']:.2f}  Sim={eval_metrics['content_similarity']:.3f}")

    except Exception as e:
        result_data = {
            "issue_id": issue_id, "framework": fw_name, "model": OLLAMA_MODEL,
            "patch": "", "raw_response_length": 0,
            "elapsed_s": 0, "fw_elapsed_s": 0, "tokens": {},
            "evaluation": {"has_patch": False, "error": True},
            "error": f"{type(e).__name__}: {str(e)[:500]}",
        }
        print(f"  [{fw_name:^22}] {issue_id:<40} ERROR: {type(e).__name__}: {str(e)[:120]}")

    with open(result_file, "w") as f:
        json.dump(result_data, f, indent=2)

    return result_data


def main():
    os.chdir(Path(__file__).parent.parent)
    with open(SAMPLES_PATH) as f:
        issues = json.load(f)["issues"]
    print(f"Loaded {len(issues)} sample issues")
    print(f"Model: {OLLAMA_MODEL}")
    print(f"Workers: {MAX_WORKERS}")
    print(f"Frameworks: {', '.join(FRAMEWORKS.keys())}")

    Path(RESULTS_DIR).mkdir(parents=True, exist_ok=True)

    # Phase 1: pre-fetch all issue contexts sequentially (GitHub API calls)
    print(f"\n{'='*80}")
    print("Phase 1: Fetching source code context for all issues...")
    print(f"{'='*80}")
    contexts = {}
    gt_cache = {}
    for i, issue in enumerate(issues):
        iid = f"{issue['repo_name']}#{issue['issue_number']}"
        print(f"  [{i+1}/{len(issues)}] {iid}...", end="", flush=True)
        contexts[iid] = prepare_issue_context(issue)
        gt_file = Path(GT_DIR) / f"{issue['pr_owner']}__{issue['pr_repo']}__{issue['issue_number']}.json"
        gt_cache[iid] = json.load(open(gt_file)) if gt_file.exists() else {}
        print(f" OK ({len(contexts[iid])} chars)")

    # Phase 2: run all (framework x issue) pairs with 4 parallel workers
    print(f"\n{'='*80}")
    print(f"Phase 2: Running 6 frameworks x {len(issues)} issues = {6*len(issues)} tasks ({MAX_WORKERS} workers)")
    print(f"{'='*80}")

    all_results = {fw: [] for fw in FRAMEWORKS}
    tasks = []
    for issue in issues:
        iid = f"{issue['repo_name']}#{issue['issue_number']}"
        for fw_name, fw_func in FRAMEWORKS.items():
            tasks.append((fw_name, fw_func, contexts[iid], issue, gt_cache[iid]))

    total = len(tasks)
    completed = 0
    start_all = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(run_one_task, *t): t for t in tasks}
        for future in as_completed(futures):
            completed += 1
            fw_name = futures[future][0]
            result = future.result()
            all_results[fw_name].append(result)
            elapsed_total = time.time() - start_all
            rate = completed / elapsed_total * 60 if elapsed_total > 0 else 0
            remaining = (total - completed) / rate if rate > 0 else 0
            print(f"  Progress: {completed}/{total} ({completed/total*100:.0f}%) "
                  f"| Elapsed: {elapsed_total/60:.1f}min | ETA: {remaining:.1f}min")

    print_benchmark_summary(all_results)


def print_benchmark_summary(all_results):
    print(f"\n\n{'='*90}")
    print(f"{'INITIAL BENCHMARK RESULTS':^90}")
    print(f"{'='*90}")
    print(f"\nModel: {OLLAMA_MODEL}  |  Workers: {MAX_WORKERS}  |  Issues: 10")
    print(f"\n{'Framework':<22} {'Patches':>8} {'Avg Time':>10} {'File Ovlp':>10} {'Similarity':>11} {'Errors':>8}")
    print("-" * 75)

    summary = {}
    for fw_name, results in sorted(all_results.items()):
        n = len(results)
        n_patches = sum(1 for r in results if r.get("evaluation", {}).get("has_patch", False))
        avg_time = sum(r.get("elapsed_s", 0) for r in results) / max(n, 1)
        avg_file_ovlp = sum(r.get("evaluation", {}).get("file_overlap", 0) for r in results) / max(n, 1)
        avg_sim = sum(r.get("evaluation", {}).get("content_similarity", 0) for r in results) / max(n, 1)
        n_errors = sum(1 for r in results if r.get("error"))

        summary[fw_name] = {
            "n_issues": n, "n_patches": n_patches,
            "patch_rate": n_patches / max(n, 1),
            "avg_time_s": round(avg_time, 2),
            "avg_file_overlap": round(avg_file_ovlp, 4),
            "avg_similarity": round(avg_sim, 4),
            "n_errors": n_errors,
        }
        print(f"{fw_name:<22} {n_patches:>5}/{n:<2} {avg_time:>9.1f}s {avg_file_ovlp:>9.3f} {avg_sim:>10.4f} {n_errors:>8}")

    print(f"\n{'='*90}")
    print("Metrics:")
    print("  Patches:    Issues where the agent produced a non-empty patch")
    print("  Avg Time:   Average wall-clock time per issue (seconds)")
    print("  File Ovlp:  Jaccard similarity of changed files vs ground truth PR")
    print("  Similarity: SequenceMatcher ratio of agent patch vs ground truth patch")
    print("  Errors:     Framework errors/exceptions")

    # Per-issue breakdown
    print(f"\n{'='*90}")
    print(f"{'PER-ISSUE BREAKDOWN':^90}")
    print(f"{'='*90}")
    print(f"\n{'Issue':<45} {'Framework':<22} {'Time':>7} {'FilOv':>6} {'Sim':>7} {'Err':>4}")
    print("-" * 90)
    for fw_name, results in sorted(all_results.items()):
        for r in sorted(results, key=lambda x: x.get("issue_id", "")):
            ev = r.get("evaluation", {})
            err = "Y" if r.get("error") else ""
            print(f"{r.get('issue_id','?'):<45} {fw_name:<22} "
                  f"{r.get('elapsed_s',0):>6.1f}s {ev.get('file_overlap',0):>5.2f} "
                  f"{ev.get('content_similarity',0):>6.3f} {err:>4}")

    print(f"{'='*90}")

    summary_path = Path(RESULTS_DIR) / "benchmark_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary: {summary_path}")


if __name__ == "__main__":
    main()
