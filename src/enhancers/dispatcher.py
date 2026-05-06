"""
Dispatcher: map agent ids to enhance_issue callables.

Used by run_enhancement_benchmark to run multiple agents.
"""

from __future__ import annotations

from src.enhancers.ready_to_use.registry import CATEGORY_A_AGENTS
from src.enhancers.ready_to_use.aider_enhancer import enhance_issue as aider_enhance
from src.enhancers.ready_to_use.trae_enhancer import enhance_issue as trae_enhance
from src.enhancers.ready_to_use.openhands_enhancer import enhance_issue as openhands_enhance
from src.enhancers.ready_to_use.mini_swe_agent_enhancer import enhance_issue as mini_swe_enhance
from src.enhancers.ready_to_use.live_swe_agent_enhancer import enhance_issue as live_swe_enhance
from src.enhancers.ready_to_use.sweagent_enhancer import enhance_issue as sweagent_enhance
from src.enhancers.ready_to_use.cl_enhanced_gemma3 import enhance_issue as cl_enhanced_enhance
from src.enhancers.ready_to_use.code_context_enhancer import enhance_issue as code_context_enhance
from src.enhancers.ready_to_use.llm_append_enhancer import enhance_issue as llm_append_enhance
from src.enhancers.framework_built.simple_enhancer import enhance_issue as simple_enhance


def get_enhancer(agent_id: str):
    """Return enhance_issue(issue, changed_files) for the given agent, or None."""
    if agent_id == "simple_enhancer":
        return simple_enhance
    if agent_id == "aider":
        return aider_enhance
    if agent_id == "trae":
        return trae_enhance
    if agent_id == "openhands":
        return openhands_enhance
    if agent_id == "mini_swe_agent":
        return mini_swe_enhance
    if agent_id == "live_swe_agent":
        return live_swe_enhance
    if agent_id == "swe_agent":
        return sweagent_enhance
    if agent_id == "cl_enhanced_gemma3":
        return cl_enhanced_enhance
    if agent_id == "code_context":
        return code_context_enhance
    if agent_id == "llm_append_analysis":
        return lambda issue, cf="": llm_append_enhance(issue, cf, strategy="append_analysis")
    if agent_id == "llm_extract_highlight":
        return lambda issue, cf="": llm_append_enhance(issue, cf, strategy="extract_highlight")
    if agent_id == "llm_hybrid":
        return lambda issue, cf="": llm_append_enhance(issue, cf, strategy="hybrid")
    # Proxy fallback is intentionally disabled for benchmark runs.  Agents must
    # have an explicit native integration or a named LLM enhancer implementation.
    return None



def get_category_a_agent_ids() -> list[str]:
    """Return all Category A agent ids."""
    return [a["id"] for a in CATEGORY_A_AGENTS]


def get_all_benchmark_agents() -> list[str]:
    """Return agent ids for the full benchmark: Category A + simple_enhancer."""
    return get_category_a_agent_ids() + ["simple_enhancer"]
