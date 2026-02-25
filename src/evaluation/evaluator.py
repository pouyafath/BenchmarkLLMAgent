"""
Evaluation Module for BenchmarkLLMAgent.

Implements all four metric categories:
  A. Correctness / Outcome
  B. Efficiency / Cost
  C. Agent Process / Trajectory
  D. Ground Truth Alignment
"""

import json
import logging
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CorrectnessMetrics:
    resolved: bool = False
    patch_applies: bool = False
    task_tests_pass: bool = False
    has_regression: bool = False


@dataclass
class EfficiencyMetrics:
    total_tokens: int = 0
    wall_clock_ms: float = 0
    time_to_first_patch_ms: Optional[float] = None
    cost_usd: float = 0.0


@dataclass
class TrajectoryMetrics:
    num_turns: int = 0
    num_tool_calls: int = 0
    failed_tool_calls: int = 0
    looping_score: float = 0.0
    termination_type: str = ""


@dataclass
class AlignmentMetrics:
    file_overlap: float = 0.0    # Jaccard similarity
    function_overlap: float = 0.0
    edit_localization: float = 0.0
    patch_size_ratio: float = 0.0


@dataclass
class EvaluationResult:
    issue_id: str
    framework: str
    model: str
    correctness: CorrectnessMetrics = field(default_factory=CorrectnessMetrics)
    efficiency: EfficiencyMetrics = field(default_factory=EfficiencyMetrics)
    trajectory: TrajectoryMetrics = field(default_factory=TrajectoryMetrics)
    alignment: AlignmentMetrics = field(default_factory=AlignmentMetrics)

    def to_dict(self) -> dict:
        return {
            "issue_id": self.issue_id,
            "framework": self.framework,
            "model": self.model,
            "correctness": self.correctness.__dict__,
            "efficiency": self.efficiency.__dict__,
            "trajectory": self.trajectory.__dict__,
            "alignment": self.alignment.__dict__,
        }


class Evaluator:
    """Evaluates agent results against ground truth."""

    COST_PER_1K_INPUT = {
        "gpt-4o": 0.0025,
        "gpt-4o-mini": 0.00015,
        "claude-3-5-sonnet": 0.003,
    }
    COST_PER_1K_OUTPUT = {
        "gpt-4o": 0.01,
        "gpt-4o-mini": 0.0006,
        "claude-3-5-sonnet": 0.015,
    }

    def evaluate(self, agent_result: dict, ground_truth: dict,
                 repo_dir: Optional[str] = None) -> EvaluationResult:
        result = EvaluationResult(
            issue_id=agent_result["issue_id"],
            framework=agent_result["framework"],
            model=agent_result["model"],
        )

        result.correctness = self._evaluate_correctness(agent_result, repo_dir)
        result.efficiency = self._evaluate_efficiency(agent_result)
        result.trajectory = self._evaluate_trajectory(agent_result)
        result.alignment = self._evaluate_alignment(agent_result, ground_truth)

        return result

    def _evaluate_correctness(self, agent_result: dict,
                              repo_dir: Optional[str]) -> CorrectnessMetrics:
        metrics = CorrectnessMetrics()
        patch = agent_result.get("patch", "")

        if not patch.strip():
            return metrics

        metrics.patch_applies = self._check_patch_applies(patch, repo_dir)

        if metrics.patch_applies and repo_dir:
            pre_tests = self._run_tests(repo_dir)
            self._apply_patch(patch, repo_dir)
            post_tests = self._run_tests(repo_dir)
            self._revert_patch(patch, repo_dir)

            metrics.task_tests_pass = post_tests.get("passed", False)
            metrics.has_regression = (
                pre_tests.get("passed", False) and not post_tests.get("passed", False)
            )
            metrics.resolved = metrics.task_tests_pass and not metrics.has_regression

        return metrics

    def _evaluate_efficiency(self, agent_result: dict) -> EfficiencyMetrics:
        meta = agent_result.get("metadata", {})
        model = agent_result.get("model", "")

        total_tokens = meta.get("total_tokens", 0)
        input_cost = self.COST_PER_1K_INPUT.get(model, 0.005) * total_tokens / 1000 * 0.6
        output_cost = self.COST_PER_1K_OUTPUT.get(model, 0.015) * total_tokens / 1000 * 0.4
        cost = input_cost + output_cost

        first_patch_time = None
        trace = agent_result.get("trace", [])
        cumulative_time = 0
        for step in trace:
            cumulative_time += step.get("time_ms", 0)
            if step.get("tool") == "create_patch" and step.get("success"):
                first_patch_time = cumulative_time
                break

        return EfficiencyMetrics(
            total_tokens=total_tokens,
            wall_clock_ms=meta.get("total_time_ms", 0),
            time_to_first_patch_ms=first_patch_time,
            cost_usd=cost,
        )

    def _evaluate_trajectory(self, agent_result: dict) -> TrajectoryMetrics:
        meta = agent_result.get("metadata", {})
        trace = agent_result.get("trace", [])

        looping_score = self._compute_looping_score(trace)

        return TrajectoryMetrics(
            num_turns=meta.get("total_turns", 0),
            num_tool_calls=meta.get("total_tool_calls", 0),
            failed_tool_calls=meta.get("failed_tool_calls", 0),
            looping_score=looping_score,
            termination_type=meta.get("termination_reason", ""),
        )

    def _evaluate_alignment(self, agent_result: dict,
                            ground_truth: dict) -> AlignmentMetrics:
        metrics = AlignmentMetrics()

        agent_files = self._extract_files_from_patch(agent_result.get("patch", ""))
        gt_files = set(ground_truth.get("changed_files", []))

        if agent_files or gt_files:
            intersection = agent_files & gt_files
            union = agent_files | gt_files
            metrics.file_overlap = len(intersection) / len(union) if union else 0.0

        agent_funcs = self._extract_functions_from_patch(agent_result.get("patch", ""))
        gt_funcs = set(ground_truth.get("changed_functions", []))

        if agent_funcs or gt_funcs:
            intersection = agent_funcs & gt_funcs
            union = agent_funcs | gt_funcs
            metrics.function_overlap = len(intersection) / len(union) if union else 0.0

        agent_patch_size = len(agent_result.get("patch", "").splitlines())
        gt_patch_size = len(ground_truth.get("patch_content", "").splitlines())
        if gt_patch_size > 0:
            metrics.patch_size_ratio = agent_patch_size / gt_patch_size

        return metrics

    @staticmethod
    def _check_patch_applies(patch: str, repo_dir: Optional[str]) -> bool:
        if not repo_dir:
            return bool(patch.strip())
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            f.write(patch)
            f.flush()
            result = subprocess.run(
                ["git", "apply", "--check", f.name],
                cwd=repo_dir, capture_output=True, text=True, timeout=10,
            )
        return result.returncode == 0

    @staticmethod
    def _apply_patch(patch: str, repo_dir: str) -> bool:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            f.write(patch)
            f.flush()
            result = subprocess.run(
                ["git", "apply", f.name],
                cwd=repo_dir, capture_output=True, text=True, timeout=10,
            )
        return result.returncode == 0

    @staticmethod
    def _revert_patch(patch: str, repo_dir: str) -> bool:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            f.write(patch)
            f.flush()
            result = subprocess.run(
                ["git", "apply", "--reverse", f.name],
                cwd=repo_dir, capture_output=True, text=True, timeout=10,
            )
        return result.returncode == 0

    @staticmethod
    def _run_tests(repo_dir: str) -> dict:
        result = subprocess.run(
            ["python", "-m", "pytest", "-x", "-q", "--tb=no"],
            cwd=repo_dir, capture_output=True, text=True, timeout=300,
        )
        return {"passed": result.returncode == 0, "output": result.stdout[-2000:]}

    @staticmethod
    def _compute_looping_score(trace: list[dict]) -> float:
        if len(trace) < 2:
            return 0.0
        actions = [(step.get("tool", ""), json.dumps(step.get("args", {}), sort_keys=True)) for step in trace]
        consecutive_repeats = sum(1 for i in range(1, len(actions)) if actions[i] == actions[i - 1])
        return consecutive_repeats / (len(actions) - 1)

    @staticmethod
    def _extract_files_from_patch(patch: str) -> set[str]:
        files = set()
        for line in patch.splitlines():
            if line.startswith("+++ b/") or line.startswith("--- a/"):
                filepath = line.split(" ", 1)[1]
                if filepath.startswith("a/") or filepath.startswith("b/"):
                    filepath = filepath[2:]
                if filepath != "/dev/null":
                    files.add(filepath)
        return files

    @staticmethod
    def _extract_functions_from_patch(patch: str) -> set[str]:
        functions = set()
        for line in patch.splitlines():
            if line.startswith("@@") and "@@" in line[2:]:
                context = line.split("@@")[-1].strip()
                if context:
                    functions.add(context)
        return functions
