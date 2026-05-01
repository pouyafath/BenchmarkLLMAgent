"""
Category A: Ready-to-use enhancement agents.

Registry of the 10 agents from the research plan. Each has:
- id: short identifier for results and scripts
- name: display name
- enhancer_type: "real" (actual integration) or "llm_proxy" (LLM with agent-specific prompt)
- enhancement_strategy: prompt hints for proxy mode
"""

from __future__ import annotations

CATEGORY_A_AGENTS = [
    {
        "id": "openhands",
        "name": "OpenHands",
        "enhancer_type": "llm_proxy",
        "enhancement_strategy": (
            "You simulate OpenHands: a full-repo-access coding agent. "
            "Enrich the issue with inferred code context, affected files, and structured sections "
            "as if you had explored the repository."
        ),
    },
    {
        "id": "swe_agent",
        "name": "SWE-Agent",
        "enhancer_type": "llm_proxy",
        "enhancement_strategy": (
            "You simulate SWE-Agent (Agent-Computer Interface). "
            "Use its issue-analysis style: identify relevant code, map issue to files/functions, "
            "add context-enriched sections from a codebase exploration perspective."
        ),
    },
    {
        "id": "github_copilot",
        "name": "GitHub Copilot Coding Agent",
        "enhancer_type": "llm_proxy",
        "enhancement_strategy": (
            "You simulate GitHub Copilot's issue understanding. "
            "Native GitHub integration style: structured, actionable, with inferred repo context "
            "and clear issue-to-implementation mapping."
        ),
    },
    {
        "id": "sweep",
        "name": "Sweep",
        "enhancer_type": "llm_proxy",
        "enhancement_strategy": (
            "You simulate Sweep: purpose-built for GitHub issues. "
            "Map the issue to affected files/components, add solution-path hints, "
            "and structure as Sweep would analyze before creating a PR."
        ),
    },
    {
        "id": "aider",
        "name": "Aider",
        "enhancer_type": "real",  # real CLI integration when available
        "enhancement_strategy": (
            "You simulate Aider: git-native pair programming. "
            "Add file references, code context, and technical precision. "
            "Describe what needs to change in code terms."
        ),
    },
    {
        "id": "cline",
        "name": "Cline",
        "enhancer_type": "llm_proxy",
        "enhancement_strategy": (
            "You simulate Cline: IDE-native agent. "
            "Add editor-visible structure, code references, and clear reproduction steps. "
            "Prioritize clarity for a developer reading in an IDE."
        ),
    },
    {
        "id": "magis",
        "name": "MAGIS",
        "enhancer_type": "llm_proxy",
        "enhancement_strategy": (
            "You simulate MAGIS: multi-agent (Manager, Repo Custodian, Developer, QA). "
            "Produce a rich analysis with decomposed tasks, repo structure insights, "
            "and QA-oriented sections (steps to reproduce, expected/actual)."
        ),
    },
    {
        "id": "copilot_workspace",
        "name": "Copilot Workspace",
        "enhancer_type": "llm_proxy",
        "enhancement_strategy": (
            "You simulate Copilot Workspace: issue-to-spec pipeline. "
            "Produce a specification-style enhanced issue: what it means, what needs to change, "
            "and a clear plan structure."
        ),
    },
    {
        "id": "chatbr",
        "name": "ChatBR",
        "enhancer_type": "llm_proxy",
        "enhancement_strategy": (
            "You simulate ChatBR: bug report quality assessment and improvement. "
            "Assess completeness, clarity, reproducibility. Add missing sections "
            "(steps, expected/actual, environment) and improve structure."
        ),
    },
    {
        "id": "coderabbit",
        "name": "CodeRabbit",
        "enhancer_type": "llm_proxy",
        "enhancement_strategy": (
            "You simulate CodeRabbit: code review agent with deep repo understanding. "
            "Add affected components, related code references, suggested test scenarios, "
            "and review-style structured analysis."
        ),
    },
    {
        "id": "mini_swe_agent",
        "name": "Mini-SWE-Agent",
        "enhancer_type": "llm_proxy",
        "enhancement_strategy": (
            "You simulate Mini-SWE-Agent: a lightweight, fast SWE-agent variant. "
            "Focus on conciseness and correctness — identify the minimal set of files and "
            "changes needed, map the issue to the core code location, and produce a "
            "tight, actionable enhancement without unnecessary verbosity."
        ),
    },
    {
        "id": "live_swe_agent",
        "name": "Live-SWE-Agent",
        "enhancer_type": "llm_proxy",
        "enhancement_strategy": (
            "You simulate Live-SWE-Agent: a real-time, execution-aware SWE-agent variant. "
            "Enrich the issue with live execution context: stack traces if inferable, "
            "runtime behavior, dynamic analysis hints, and precise reproduction steps "
            "grounded in how the code actually runs."
        ),
    },
    {
        "id": "trae",
        "name": "TRAE Agent",
        "enhancer_type": "real",
        "enhancement_strategy": (
            "You simulate TRAE Agent (ByteDance): an autonomous coding agent. "
            "Analyze the issue from a software engineering perspective, map it to "
            "affected code areas, and produce a well-structured, complete, actionable "
            "issue description with reproduction steps, expected vs actual, and code context."
        ),
    },
    {
        "id": "cl_enhanced_gemma3",
        "name": "CL-Enhanced Agent (Gemma3-12B)",
        "enhancer_type": "real",
        "enhancement_strategy": (
            "Managed iterative enhancement with retrieve-enhanced RAG and LightGBM quality gate. "
            "Uses the V2_29 continuous-learning agent with Gemma3-12B (Ollama) and seed_309 collection."
        ),
    },
]


def get_agent_by_id(agent_id: str):
    """Return agent config by id."""
    for a in CATEGORY_A_AGENTS:
        if a["id"] == agent_id:
            return a
    return None


def get_all_agent_ids() -> list[str]:
    """Return all Category A agent ids."""
    return [a["id"] for a in CATEGORY_A_AGENTS]
