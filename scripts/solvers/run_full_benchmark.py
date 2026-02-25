"""
Full Solver Benchmark Runner.

Orchestrates the full benchmark: loads dataset, runs each framework agent
on each issue, collects results, and triggers evaluation.

Usage:
    python -m scripts.solvers.run_full_benchmark [--config configs/benchmark_config.yaml]
"""

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.solvers.base_agent import AgentResult
from src.evaluation.evaluator import Evaluator, EvaluationResult

logger = logging.getLogger(__name__)

FRAMEWORK_REGISTRY = {
    "langgraph": "src.solvers.langgraph.agent.LangGraphAgent",
    "llamaindex": "src.solvers.llamaindex.agent.LlamaIndexAgent",
    "semantic_kernel": "src.solvers.semantic_kernel.agent.SemanticKernelAgent",
    "autogen": "src.solvers.autogen.agent.AutoGenAgent",
    "crewai": "src.solvers.crewai.agent.CrewAIAgent",
    "openai_agents_sdk": "src.solvers.openai_agents_sdk.agent.OpenAIAgentsSDKAgent",
}


def load_agent_class(framework_name: str):
    module_path, class_name = FRAMEWORK_REGISTRY[framework_name].rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def load_dataset(path: str) -> list[dict]:
    instances = []
    with open(path) as f:
        for line in f:
            instances.append(json.loads(line))
    return instances


def run_single(framework_name: str, issue: dict, ground_truth: dict,
               config_path: str) -> dict:
    """Run a single framework on a single issue. Designed for parallel execution."""
    agent_cls = load_agent_class(framework_name)
    agent = agent_cls(config_path)
    result = agent.solve(issue, ground_truth)
    return result.to_dict()


def main():
    parser = argparse.ArgumentParser(description="Run BenchmarkLLMAgent benchmark")
    parser.add_argument("--config", default="configs/benchmark_config.yaml")
    parser.add_argument("--frameworks", nargs="+", default=None,
                        help="Frameworks to benchmark (default: all enabled)")
    parser.add_argument("--max-issues", type=int, default=None,
                        help="Limit number of issues (for pilot runs)")
    parser.add_argument("--parallel", type=int, default=1,
                        help="Number of parallel workers")
    parser.add_argument("--output-dir", default="results/")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    with open(args.config) as f:
        config = yaml.safe_load(f)

    frameworks_config = config["frameworks"]
    if args.frameworks:
        active_frameworks = [f["name"] for f in frameworks_config
                             if f["name"] in args.frameworks and f["enabled"]]
    else:
        active_frameworks = [f["name"] for f in frameworks_config if f["enabled"]]

    logger.info("Active frameworks: %s", active_frameworks)

    dataset = load_dataset(config["dataset"]["processed_path"])
    if args.max_issues:
        dataset = dataset[:args.max_issues]
    logger.info("Loaded %d benchmark instances", len(dataset))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    evaluator = Evaluator()

    for framework in active_frameworks:
        logger.info("=== Running %s ===", framework)
        fw_results = []

        for i, instance in enumerate(dataset):
            issue = instance["issue"]
            gt = instance["ground_truth"]
            issue_id = f"{issue['owner']}/{issue['repo']}#{issue['number']}"

            logger.info("[%d/%d] %s on %s", i + 1, len(dataset), framework, issue_id)

            try:
                agent_result = run_single(framework, issue, gt, args.config)
                eval_result = evaluator.evaluate(agent_result, gt)
                agent_result["evaluation"] = eval_result.to_dict()
                fw_results.append(agent_result)
            except Exception:
                logger.exception("Failed: %s on %s", framework, issue_id)
                continue

        fw_output = output_dir / f"{framework}_results.jsonl"
        with open(fw_output, "w") as f:
            for r in fw_results:
                f.write(json.dumps(r) + "\n")

        all_results.extend(fw_results)
        logger.info("Completed %s: %d/%d issues", framework, len(fw_results), len(dataset))

    summary_path = output_dir / "benchmark_summary.json"
    summary = _compute_summary(all_results, active_frameworks)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("Benchmark complete. Summary saved to %s", summary_path)


def _compute_summary(results: list[dict], frameworks: list[str]) -> dict:
    summary = {"frameworks": {}}
    for fw in frameworks:
        fw_results = [r for r in results if r["framework"] == fw]
        if not fw_results:
            continue

        evals = [r.get("evaluation", {}) for r in fw_results]
        correctness = [e.get("correctness", {}) for e in evals]
        efficiency = [e.get("efficiency", {}) for e in evals]
        trajectory = [e.get("trajectory", {}) for e in evals]

        n = len(fw_results)
        summary["frameworks"][fw] = {
            "n_issues": n,
            "resolve_rate": sum(1 for c in correctness if c.get("resolved")) / n if n else 0,
            "patch_apply_rate": sum(1 for c in correctness if c.get("patch_applies")) / n if n else 0,
            "regression_rate": sum(1 for c in correctness if c.get("has_regression")) / n if n else 0,
            "avg_tokens": sum(e.get("total_tokens", 0) for e in efficiency) / n if n else 0,
            "avg_time_ms": sum(e.get("wall_clock_ms", 0) for e in efficiency) / n if n else 0,
            "avg_cost_usd": sum(e.get("cost_usd", 0) for e in efficiency) / n if n else 0,
            "avg_turns": sum(t.get("num_turns", 0) for t in trajectory) / n if n else 0,
            "avg_tool_calls": sum(t.get("num_tool_calls", 0) for t in trajectory) / n if n else 0,
            "avg_failed_tool_calls": sum(t.get("failed_tool_calls", 0) for t in trajectory) / n if n else 0,
        }

    return summary


if __name__ == "__main__":
    main()
