"""
Run enhancement benchmark on pilot issues.

Supports multiple agents:
  --agents all         : all Category A agents + simple_enhancer (default)
  --agents category_a  : only Category A (10 agents)
  --agents aider,openhands,sweep,... : comma-separated list

Usage:
    python scripts/enhancers/run_enhancement_benchmark.py [--max-issues 10] [--agents all]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))

from src.enhancers.dispatcher import get_enhancer, get_all_benchmark_agents, get_category_a_agent_ids

SAMPLES_PATH = _root / "data" / "samples" / "swe_bench_verified_10_samples.json"
RESULTS_DIR = _root / "results" / "enhancement_benchmark"


def parse_agents_arg(value: str) -> list[str]:
    if value == "all":
        return get_all_benchmark_agents()
    if value == "category_a":
        return get_category_a_agent_ids()
    return [a.strip() for a in value.split(",") if a.strip()]


def _build_cache_context(samples_path: Path, agents: list[str], parallel: int) -> dict:
    return {
        "samples_path": str(samples_path.resolve()),
        "agents": sorted(agents),
        "parallel": parallel,
        "openai_compat_base_url": os.environ.get("OPENAI_COMPAT_BASE_URL", ""),
        "openai_compat_model": os.environ.get("OPENAI_COMPAT_MODEL", ""),
        "use_ollama": os.environ.get("USE_OLLAMA", ""),
        "ollama_model": os.environ.get("OLLAMA_MODEL", ""),
        "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", ""),
    }


def _compute_cache_key(cache_context: dict) -> str:
    payload = json.dumps(cache_context, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-issues", type=int, default=10, help="Max issues to process")
    parser.add_argument("--samples", type=str, default=None, help="Path to samples JSON")
    parser.add_argument(
        "--agents",
        type=str,
        default="all",
        help="Agents to run: 'all', 'category_a', or comma-separated (e.g. aider,openhands,sweep)",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=4,
        help="Max concurrent enhancement calls (default: 4, matches Ollama concurrency limit)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: results/enhancement_benchmark)",
    )
    parser.add_argument(
        "--cache-key",
        type=str,
        default="",
        help="Optional explicit cache key. If omitted, a key is derived from runtime model/env config.",
    )
    parser.add_argument(
        "--disable-cache",
        action="store_true",
        help="Ignore existing cached enhancement files and recompute everything.",
    )
    args = parser.parse_args()

    agents = parse_agents_arg(args.agents)
    enhancers = {aid: get_enhancer(aid) for aid in agents}
    missing = [aid for aid, fn in enhancers.items() if fn is None]
    if missing:
        print(f"Error: unknown or unimplemented agents: {missing}")
        sys.exit(1)

    samples_path = Path(args.samples) if args.samples else SAMPLES_PATH
    if not samples_path.exists():
        print(f"Error: {samples_path} not found")
        sys.exit(1)

    with open(samples_path) as f:
        data = json.load(f)
    issues = data["issues"][: args.max_issues]

    results_dir = Path(args.output_dir) if args.output_dir else RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)

    cache_context = _build_cache_context(samples_path, agents, args.parallel)
    cache_key = args.cache_key.strip() or _compute_cache_key(cache_context)

    print(f"Enhancement Benchmark — {len(agents)} agents")
    print(f"  Agents: {', '.join(agents)}")
    print(f"  Issues: {len(issues)}")
    print(f"  Parallel workers: {args.parallel}")
    print(f"  Output: {results_dir}")
    print(f"  Cache key: {cache_key}")
    print(f"  Cache disabled: {args.disable_cache}")
    print()

    total = len(agents) * len(issues)
    done_count = 0
    lock = threading.Lock()

    def run_one(agent_id, enhance_fn, issue):
        iid = f"{issue['repo_name']}#{issue['issue_number']}"
        out_file = results_dir / f"{agent_id}__{issue['pr_owner']}__{issue['pr_repo']}__{issue['issue_number']}.json"
        if out_file.exists() and not args.disable_cache:
            try:
                existing = json.loads(out_file.read_text())
                if existing.get("cache_key") == cache_key:
                    return agent_id, iid, out_file, True  # cached
            except Exception:
                # Corrupt cache should be overwritten.
                pass
        changed_files = ", ".join(f["filename"] for f in issue.get("pr_files", [])[:10])
        try:
            result = enhance_fn(issue, changed_files)
        except Exception as e:
            result = {
                "enhanced_title": issue.get("title", ""),
                "enhanced_body": issue.get("body", ""),
                "enhancement_metadata": {"error": str(e)[:500]},
            }
        out_data = {
            "issue_id": iid,
            "agent": agent_id,
            "cache_key": cache_key,
            "cache_context": cache_context,
            "original_title": issue.get("title", ""),
            "original_body": issue.get("body", ""),
            "enhanced_title": result["enhanced_title"],
            "enhanced_body": result["enhanced_body"],
            "enhancement_metadata": result.get("enhancement_metadata", {}),
        }
        with open(out_file, "w") as f:
            json.dump(out_data, f, indent=2)
        return agent_id, iid, out_file, False  # fresh

    tasks = [(aid, enhancers[aid], issue) for aid in agents for issue in issues]

    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {executor.submit(run_one, aid, fn, iss): idx
                   for idx, (aid, fn, iss) in enumerate(tasks)}
        for future in as_completed(futures):
            agent_id, iid, out_file, cached = future.result()
            with lock:
                done_count += 1
                status = "(cached)" if cached else f"({len(out_file.read_bytes())} chars)"
                print(f"  [{done_count}/{total}] {agent_id} / {iid} {status}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
