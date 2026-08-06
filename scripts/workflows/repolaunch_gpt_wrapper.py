#!/usr/bin/env python3
"""
Wrapper: run one RepoLaunch instance with GPT as the LLM.

Applies:
  1. Tavily-bypass patches (DuckDuckGo no-op) so pydantic never loads the real Tavily
  2. Timemachine disable patch — unset host.docker.internal pip proxy in container
     (reads disable_timemachine from the config JSON; default True for GPT runs)

LLM is NOT patched: upstream LLMProvider("OpenAI", ...) uses OPENAI_API_KEY normally.

Usage (called by run_pouya20_gpt54mini.py per instance):
    python repolaunch_gpt_wrapper.py <config_json_path>

Environment:
    OPENAI_API_KEY   — required, never written to disk
    TAVILY_API_KEY   — set to "dummy" in env to satisfy pydantic; never actually used
"""

from __future__ import annotations

import json
import os
import sys
import types

PAUL_DIR = "/home/22pf2/paul-RepoLaunch"
LAUNCH_DIR = "/home/22pf2/BenchmarkLLMAgent/SWE-bench-Live-Collection/launch"

if PAUL_DIR not in sys.path:
    sys.path.insert(0, PAUL_DIR)
if LAUNCH_DIR not in sys.path:
    sys.path.insert(0, LAUNCH_DIR)


def patch_tavily():
    """Replace Tavily with DuckDuckGo before any upstream imports use it."""
    try:
        from paul.search_local import LocalSearchTool
    except ImportError:
        class LocalSearchTool:
            def __init__(self, max_results=3):
                self.max_results = max_results

            def invoke(self, query):
                return []

    fake_tavily = types.ModuleType("langchain_community.tools.tavily_search")
    fake_tavily.TavilySearchResults = LocalSearchTool
    sys.modules["langchain_community.tools.tavily_search"] = fake_tavily

    class _FakeWrapper:
        tavily_api_key: str = "dummy"

        def __init__(self, **kwargs):
            pass

        def results(self, *args, **kwargs):
            return []

    fake_wrapper_mod = types.ModuleType("langchain_community.utilities.tavily_search")
    fake_wrapper_mod.TavilySearchAPIWrapper = _FakeWrapper
    sys.modules["langchain_community.utilities.tavily_search"] = fake_wrapper_mod

    print("✓ Tavily patched → DuckDuckGo/no-op", flush=True)


def patch_agent_state_search():
    """Patch AgentState.create to replace Tavily search with DuckDuckGo after init."""
    try:
        from paul.search_local import LocalSearchTool

        import launch.agent.state as state_module

        original_create = state_module.AgentState.create

        @classmethod
        def patched_create(cls, *args, max_search_results: int = 3, **kwargs):
            instance = original_create.__func__(cls, *args, max_search_results=max_search_results, **kwargs)
            instance["search_tool"] = LocalSearchTool(max_results=max_search_results)
            return instance

        state_module.AgentState.create = patched_create
        print("✓ AgentState.create patched → LocalSearchTool", flush=True)
    except Exception as exc:
        print(f"WARN: AgentState patch failed ({exc}), continuing anyway", flush=True)


def patch_timemachine(disable: bool):
    """
    When disable=True, replace start_timemachine with a no-op so containers never
    try to connect to host.docker.internal for the pip time-machine proxy.
    This avoids repeated pip install timeouts on machines where the proxy isn't running.
    """
    if not disable:
        print("✓ Timemachine: enabled (using live PyPI)", flush=True)
        return

    try:
        import launch.utilities.timemachine as timemachine_mod
        import launch.utilities.language_handlers as language_handlers_mod

        def _noop_start_timemachine(session, date):
            return None

        timemachine_mod.start_timemachine = _noop_start_timemachine
        language_handlers_mod.start_timemachine = _noop_start_timemachine
        print("✓ Timemachine disabled → pip uses live PyPI directly", flush=True)
    except Exception as exc:
        print(f"WARN: timemachine patch failed ({exc}), continuing anyway", flush=True)


def main():
    if len(sys.argv) < 2:
        print("Usage: repolaunch_gpt_wrapper.py <config_json_path>")
        sys.exit(1)

    config_path = sys.argv[1]

    with open(config_path) as f:
        config_data = json.load(f)

    disable_timemachine = config_data.get("disable_timemachine", True)

    if not os.environ.get("TAVILY_API_KEY"):
        os.environ["TAVILY_API_KEY"] = "tvly-dummy-no-tavily-calls"

    # Apply all patches BEFORE importing upstream launch.*
    patch_tavily()

    # Import after Tavily patch
    from launch.run import run_launch
    from launch.agent import state  # noqa: F401 — triggers import for search patch

    patch_agent_state_search()
    patch_timemachine(disable_timemachine)

    print(f"Starting RepoLaunch: {config_path}", flush=True)
    run_launch(config_path)


if __name__ == "__main__":
    main()
