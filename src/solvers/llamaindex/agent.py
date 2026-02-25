"""
LlamaIndex-based Issue-Solving Agent.

Implements the BaseAgent interface using LlamaIndex's workflow engine
with RAG-native capabilities.
"""

import logging
from typing import Optional

from src.solvers.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class LlamaIndexAgent(BaseAgent):
    """Issue solver using LlamaIndex's Workflow and AgentRunner."""

    FRAMEWORK_NAME = "llamaindex"

    def _setup(self, issue: dict) -> None:
        """Initialize LlamaIndex components."""
        # TODO: Import and configure LlamaIndex
        # from llama_index.core.agent import ReActAgent
        # from llama_index.core.tools import FunctionTool
        # from llama_index.llms.openai import OpenAI
        #
        # self.llm = OpenAI(model=self.model_config["name"], temperature=self.model_config["temperature"])
        # self.tools = self._create_tools()
        # self.agent = ReActAgent.from_tools(self.tools, llm=self.llm, verbose=True)
        pass

    def _solve(self, task_prompt: str) -> tuple[str, str]:
        """Execute the LlamaIndex agent to solve the issue."""
        # TODO: Implement LlamaIndex execution
        # response = self.agent.chat(task_prompt)
        # return self._extract_patch(response), str(response)
        raise NotImplementedError("LlamaIndex agent implementation pending")
