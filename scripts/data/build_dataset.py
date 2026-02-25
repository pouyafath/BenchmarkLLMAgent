"""
Dataset Builder for BenchmarkLLMAgent.

Constructs the benchmark dataset by filtering GitHub issues from the Paper 2
pipeline and preparing ground truth from linked merged PRs.

Usage:
    python -m scripts.data.build_dataset
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import requests
import yaml

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


@dataclass
class GitHubIssue:
    owner: str
    repo: str
    number: int
    title: str
    body: str
    labels: list[str]
    state: str
    created_at: str
    closed_at: Optional[str]
    issue_type: Optional[str] = None  # "bug" or "feature"
    linked_prs: list[dict] = field(default_factory=list)
    complexity: Optional[str] = None  # "simple", "moderate", "complex"


@dataclass
class GroundTruth:
    issue_id: str  # "owner/repo#number"
    pr_number: int
    pr_merge_commit: str
    base_commit: str  # repo state before the fix
    changed_files: list[str]
    changed_functions: list[str]
    patch_content: str
    test_files: list[str]


@dataclass
class BenchmarkInstance:
    issue: GitHubIssue
    ground_truth: GroundTruth
    has_tests: bool
    metadata: dict = field(default_factory=dict)


class DatasetBuilder:
    """Builds the benchmark dataset from GitHub issues with linked merged PRs."""

    def __init__(self, config_path: str = "configs/benchmark_config.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.dataset_config = self.config["dataset"]
        self.github_token = self._load_token()
        self.headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def _load_token(self) -> str:
        token_path = Path.home() / ".github_token"
        if token_path.exists():
            return token_path.read_text().strip()
        import os
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            logger.warning("No GitHub token found. API rate limits will apply.")
        return token

    def build(self, source_path: Optional[str] = None) -> list[BenchmarkInstance]:
        source = source_path or self.dataset_config["source_path"]
        logger.info("Loading raw issues from %s", source)
        raw_issues = self._load_raw_issues(source)
        logger.info("Loaded %d raw issues", len(raw_issues))

        filtered = self._apply_filters(raw_issues)
        logger.info("After filtering: %d issues", len(filtered))

        instances = []
        for issue in filtered:
            gt = self._build_ground_truth(issue)
            if gt is None:
                continue
            has_tests = len(gt.test_files) > 0
            instances.append(BenchmarkInstance(
                issue=issue, ground_truth=gt, has_tests=has_tests
            ))

        logger.info("Built %d benchmark instances", len(instances))
        self._assign_complexity(instances)
        self._save(instances)
        return instances

    def _load_raw_issues(self, path: str) -> list[GitHubIssue]:
        issues = []
        with open(path) as f:
            for line in f:
                data = json.loads(line)
                issues.append(GitHubIssue(**{
                    k: v for k, v in data.items()
                    if k in GitHubIssue.__dataclass_fields__
                }))
        return issues

    def _apply_filters(self, issues: list[GitHubIssue]) -> list[GitHubIssue]:
        filters = self.dataset_config["filters"]
        allowed_types = set(filters["issue_types"])

        result = []
        for issue in issues:
            issue_type = self._classify_issue_type(issue)
            if issue_type not in allowed_types:
                continue
            if issue.state != "closed":
                continue
            if filters["require_merged_pr"] and not issue.linked_prs:
                continue
            issue.issue_type = issue_type
            result.append(issue)
        return result

    def _classify_issue_type(self, issue: GitHubIssue) -> Optional[str]:
        bug_labels = {"bug", "defect", "fix", "error", "crash", "regression"}
        feature_labels = {"feature", "enhancement", "improvement", "feature-request"}

        lower_labels = {l.lower() for l in issue.labels}

        if lower_labels & bug_labels:
            return "bug"
        if lower_labels & feature_labels:
            return "feature"
        return None

    def _build_ground_truth(self, issue: GitHubIssue) -> Optional[GroundTruth]:
        for pr_info in issue.linked_prs:
            pr_number = pr_info.get("number")
            if not pr_number:
                continue

            pr_data = self._fetch_pr(issue.owner, issue.repo, pr_number)
            if pr_data is None or not pr_data.get("merged"):
                continue

            merge_commit = pr_data.get("merge_commit_sha", "")
            base_commit = pr_data.get("base", {}).get("sha", "")

            files_data = self._fetch_pr_files(issue.owner, issue.repo, pr_number)
            changed_files = [f["filename"] for f in files_data]
            test_files = [f for f in changed_files if self._is_test_file(f)]
            changed_functions = self._extract_changed_functions(files_data)

            patch = self._fetch_pr_patch(issue.owner, issue.repo, pr_number)

            return GroundTruth(
                issue_id=f"{issue.owner}/{issue.repo}#{issue.number}",
                pr_number=pr_number,
                pr_merge_commit=merge_commit,
                base_commit=base_commit,
                changed_files=changed_files,
                changed_functions=changed_functions,
                patch_content=patch,
                test_files=test_files,
            )
        return None

    def _fetch_pr(self, owner: str, repo: str, pr_number: int) -> Optional[dict]:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
        resp = requests.get(url, headers=self.headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        logger.warning("Failed to fetch PR %s/%s#%d: %d", owner, repo, pr_number, resp.status_code)
        return None

    def _fetch_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        resp = requests.get(url, headers=self.headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return []

    def _fetch_pr_patch(self, owner: str, repo: str, pr_number: int) -> str:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = {**self.headers, "Accept": "application/vnd.github.v3.patch"}
        resp = requests.get(url, headers=headers, timeout=60)
        if resp.status_code == 200:
            return resp.text
        return ""

    @staticmethod
    def _is_test_file(filepath: str) -> bool:
        parts = filepath.lower().split("/")
        name = parts[-1]
        return (
            "test" in parts
            or "tests" in parts
            or name.startswith("test_")
            or name.endswith("_test.py")
            or name.endswith(".test.js")
            or name.endswith(".test.ts")
            or name.endswith("_spec.rb")
        )

    @staticmethod
    def _extract_changed_functions(files_data: list[dict]) -> list[str]:
        functions = []
        for f in files_data:
            patch = f.get("patch", "")
            for line in patch.split("\n"):
                if line.startswith("@@") and "@@" in line[2:]:
                    context = line.split("@@")[-1].strip()
                    if context:
                        functions.append(context)
        return functions

    def _assign_complexity(self, instances: list[BenchmarkInstance]) -> None:
        # Placeholder: uses heuristics based on patch size and files changed
        for inst in instances:
            n_files = len(inst.ground_truth.changed_files)
            patch_lines = inst.ground_truth.patch_content.count("\n")
            if n_files <= 1 and patch_lines <= 20:
                inst.issue.complexity = "simple"
            elif n_files <= 3 and patch_lines <= 100:
                inst.issue.complexity = "moderate"
            else:
                inst.issue.complexity = "complex"

    def _save(self, instances: list[BenchmarkInstance]) -> None:
        out_path = Path(self.dataset_config["processed_path"])
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with open(out_path, "w") as f:
            for inst in instances:
                record = {
                    "issue": asdict(inst.issue),
                    "ground_truth": asdict(inst.ground_truth),
                    "has_tests": inst.has_tests,
                    "metadata": inst.metadata,
                }
                f.write(json.dumps(record) + "\n")

        gt_dir = Path(self.dataset_config["ground_truth_path"])
        gt_dir.mkdir(parents=True, exist_ok=True)
        for inst in instances:
            gt_file = gt_dir / f"{inst.issue.owner}__{inst.issue.repo}__{inst.issue.number}.json"
            with open(gt_file, "w") as f:
                json.dump(asdict(inst.ground_truth), f, indent=2)

        logger.info("Saved %d instances to %s", len(instances), out_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    builder = DatasetBuilder()
    builder.build()
