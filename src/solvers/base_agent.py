"""
Base Agent Interface for solver and enhancer agents.

All framework-specific agents must inherit from this base class to ensure
a controlled, fair comparison across frameworks.
"""

import time
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    turn: int
    action: str        # "tool_call", "llm_response", "error"
    tool: str
    args: dict
    result_summary: str
    tokens_used: int
    time_ms: float
    success: bool = True


@dataclass
class AgentResult:
    issue_id: str
    framework: str
    model: str
    patch: str
    rationale: str
    trace: list[ToolCall]
    total_tokens: int = 0
    total_time_ms: float = 0
    total_turns: int = 0
    total_tool_calls: int = 0
    failed_tool_calls: int = 0
    termination_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "issue_id": self.issue_id,
            "framework": self.framework,
            "model": self.model,
            "patch": self.patch,
            "rationale": self.rationale,
            "trace": [asdict(t) for t in self.trace],
            "metadata": {
                "total_tokens": self.total_tokens,
                "total_time_ms": self.total_time_ms,
                "total_turns": self.total_turns,
                "total_tool_calls": self.total_tool_calls,
                "failed_tool_calls": self.failed_tool_calls,
                "termination_reason": self.termination_reason,
            },
        }

    def save(self, output_dir: str) -> Path:
        path = Path(output_dir) / f"{self.framework}_{self.model}_{self.issue_id.replace('/', '__').replace('#', '_')}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path


class BaseAgent(ABC):
    """
    Abstract base class for all framework-specific issue-solving agents.

    Subclasses implement `_setup()` and `_solve()` while this class
    handles budget enforcement, tracing, and output standardization.
    """

    FRAMEWORK_NAME: str = "base"

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(Path(__file__).resolve().parent.parent.parent / "configs" / "benchmark_config.yaml")
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.budgets = self.config["budgets"]
        self.model_config = self.config["models"]["primary"]
        self.prompts = self._load_prompts()
        self.trace: list[ToolCall] = []
        self._turn_counter = 0
        self._token_counter = 0
        self._tool_call_counter = 0
        self._failed_tool_calls = 0

    def _load_prompts(self) -> dict[str, str]:
        prompts = {}
        prompt_section = self.config.get("prompts", {})
        prompt_config = prompt_section.get("solver", prompt_section)
        for key in ("system_prompt_path", "task_template_path"):
            path = prompt_config.get(key, "")
            if path and Path(path).exists():
                prompts[key.replace("_path", "")] = Path(path).read_text()
        return prompts

    def solve(self, issue: dict, ground_truth: Optional[dict] = None) -> AgentResult:
        """
        Main entry point. Runs the agent on a single issue with budget enforcement.
        Ground truth is NOT passed to the agent — it's only used for post-hoc evaluation.
        """
        issue_id = f"{issue['owner']}/{issue['repo']}#{issue['number']}"
        logger.info("[%s] Solving %s with %s", self.FRAMEWORK_NAME, issue_id, self.model_config["name"])

        self.trace = []
        self._turn_counter = 0
        self._token_counter = 0
        self._tool_call_counter = 0
        self._failed_tool_calls = 0

        task_prompt = self._format_task(issue)
        self._setup(issue)

        start_time = time.time()
        try:
            patch, rationale = self._solve(task_prompt)
            termination = "patch_produced" if patch else "no_patch"
        except BudgetExhaustedError as e:
            patch, rationale = "", str(e)
            termination = "budget_exhausted"
        except Exception as e:
            logger.exception("[%s] Error solving %s", self.FRAMEWORK_NAME, issue_id)
            patch, rationale = "", str(e)
            termination = "unrecoverable_error"

        elapsed_ms = (time.time() - start_time) * 1000

        return AgentResult(
            issue_id=issue_id,
            framework=self.FRAMEWORK_NAME,
            model=self.model_config["name"],
            patch=patch,
            rationale=rationale,
            trace=self.trace,
            total_tokens=self._token_counter,
            total_time_ms=elapsed_ms,
            total_turns=self._turn_counter,
            total_tool_calls=self._tool_call_counter,
            failed_tool_calls=self._failed_tool_calls,
            termination_reason=termination,
        )

    def _format_task(self, issue: dict) -> str:
        template = self.prompts.get("task_template", "Resolve the following issue:\n{issue_title}\n{issue_body}")
        return template.format(
            repo_owner=issue.get("owner", ""),
            repo_name=issue.get("repo", ""),
            issue_number=issue.get("number", ""),
            issue_title=issue.get("title", ""),
            issue_body=issue.get("body", ""),
            issue_labels=", ".join(issue.get("labels", [])),
            primary_language=issue.get("primary_language", ""),
            default_branch=issue.get("default_branch", "main"),
            base_commit_sha=issue.get("base_commit", ""),
        )

    def _check_budget(self) -> None:
        if self._turn_counter >= self.budgets["max_turns"]:
            raise BudgetExhaustedError(f"Turn budget exhausted: {self._turn_counter}/{self.budgets['max_turns']}")
        if self._token_counter >= self.budgets["max_total_tokens"]:
            raise BudgetExhaustedError(f"Token budget exhausted: {self._token_counter}/{self.budgets['max_total_tokens']}")
        if self._tool_call_counter >= self.budgets["max_tool_calls"]:
            raise BudgetExhaustedError(f"Tool call budget exhausted: {self._tool_call_counter}/{self.budgets['max_tool_calls']}")

    def record_tool_call(self, tool: str, args: dict, result_summary: str,
                         tokens: int, time_ms: float, success: bool = True) -> None:
        self._tool_call_counter += 1
        self._token_counter += tokens
        if not success:
            self._failed_tool_calls += 1
        self.trace.append(ToolCall(
            turn=self._turn_counter,
            action="tool_call",
            tool=tool,
            args=args,
            result_summary=result_summary[:500],
            tokens_used=tokens,
            time_ms=time_ms,
            success=success,
        ))

    def increment_turn(self) -> None:
        self._turn_counter += 1
        self._check_budget()

    @abstractmethod
    def _setup(self, issue: dict) -> None:
        """Framework-specific initialization (model client, tools, graph, etc.)."""

    @abstractmethod
    def _solve(self, task_prompt: str) -> tuple[str, str]:
        """
        Framework-specific solving logic.

        Returns:
            (patch, rationale) where patch is a unified diff string
        """


class BudgetExhaustedError(Exception):
    pass
