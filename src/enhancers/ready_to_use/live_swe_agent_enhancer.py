"""
Live-SWE-Agent enhancer — Category A (LLM proxy simulation).

Live-SWE-Agent (OpenAutoCoder/live-swe-agent) is a research-grade self-evolving
agent for full SWE-bench solving. It has no standalone CLI for issue enhancement.

This module simulates its approach via LLM proxy: enriching issues with a
runtime-aware, execution-context perspective (stack traces, dynamic analysis,
live reproduction steps), which characterises Live-SWE-Agent's distinctive style.
"""

from pathlib import Path
from typing import Any, Dict
import sys

_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_root))

from src.enhancers.ready_to_use.llm_proxy_enhancer import enhance_issue as _llm_proxy

_LIVE_STRATEGY = """\
You simulate Live-SWE-Agent — a real-time, execution-aware, self-evolving software \
engineering agent from OpenAutoCoder.

When enhancing this GitHub issue, emphasise:
1. **Runtime context**: infer probable stack traces, error propagation paths, \
dynamic state at the point of failure.
2. **Live reproduction steps**: detailed, step-by-step commands a developer can \
run RIGHT NOW to reproduce the bug, referencing exact versions / configs.
3. **Execution-aware analysis**: explain HOW the code fails at runtime, not just WHAT \
is wrong. Reference the relevant code paths / call chains.
4. **Component mapping**: identify the specific functions, classes, or modules that \
own the failing behaviour, using the changed-files hints.
5. **Proposed investigation**: suggest concrete debugging commands or test assertions.

Produce a well-structured, markdown-formatted enhancement that a developer can act on immediately."""


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    """Enhance using LLM proxy with Live-SWE-Agent's execution-aware style."""
    result = _llm_proxy(issue, changed_files, agent_id="live_swe_agent",
                        strategy_override=_LIVE_STRATEGY)
    result.setdefault("enhancement_metadata", {})["agent_label"] = "Live-SWE-Agent (LLM proxy)"
    return result
