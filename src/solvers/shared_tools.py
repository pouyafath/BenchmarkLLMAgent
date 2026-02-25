"""
Shared Tool Interface for solver and enhancer agents.

All framework agents use these identical tool implementations to ensure
fair comparison. The tools are framework-agnostic Python functions that
each framework wraps in its own tool-calling mechanism.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RepoTools:
    """Tools for interacting with the target repository."""

    def __init__(self, workspace_dir: str = "/tmp/agent_workspace"):
        self.workspace_dir = Path(workspace_dir)
        self.repo_dir: Optional[Path] = None

    def clone_repo(self, url: str, commit_sha: str) -> dict:
        """Clone a repository and checkout a specific commit."""
        repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
        self.repo_dir = self.workspace_dir / repo_name

        if self.repo_dir.exists():
            return {"status": "already_cloned", "path": str(self.repo_dir)}

        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth", "50", url, str(self.repo_dir)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            return {"status": "error", "message": result.stderr[:500]}

        subprocess.run(
            ["git", "checkout", commit_sha],
            cwd=str(self.repo_dir), capture_output=True, text=True, timeout=30,
        )
        return {"status": "success", "path": str(self.repo_dir)}

    def list_files(self, path: str = ".", pattern: str = "*") -> dict:
        """List files in a directory with optional glob pattern."""
        if self.repo_dir is None:
            return {"status": "error", "message": "No repository cloned"}

        target = self.repo_dir / path
        if not target.exists():
            return {"status": "error", "message": f"Path not found: {path}"}

        files = sorted(str(f.relative_to(self.repo_dir)) for f in target.rglob(pattern) if f.is_file())
        return {"status": "success", "files": files[:200]}

    def read_file(self, path: str, start_line: int = 1, end_line: int = -1) -> dict:
        """Read file contents, optionally within a line range."""
        if self.repo_dir is None:
            return {"status": "error", "message": "No repository cloned"}

        filepath = self.repo_dir / path
        if not filepath.exists():
            return {"status": "error", "message": f"File not found: {path}"}
        if not filepath.is_file():
            return {"status": "error", "message": f"Not a file: {path}"}

        try:
            lines = filepath.read_text(errors="replace").splitlines()
            if end_line == -1:
                end_line = len(lines)
            selected = lines[max(0, start_line - 1):end_line]
            content = "\n".join(f"{i + start_line}: {line}" for i, line in enumerate(selected))
            return {"status": "success", "content": content, "total_lines": len(lines)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def write_file(self, path: str, content: str) -> dict:
        """Write content to a file in the repository."""
        if self.repo_dir is None:
            return {"status": "error", "message": "No repository cloned"}

        filepath = self.repo_dir / path
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            return {"status": "success", "path": str(filepath)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def search_code(self, query: str, file_pattern: str = "*.py") -> dict:
        """Search for a pattern in the repository using ripgrep."""
        if self.repo_dir is None:
            return {"status": "error", "message": "No repository cloned"}

        try:
            result = subprocess.run(
                ["rg", "--json", "-l", "--glob", file_pattern, query, str(self.repo_dir)],
                capture_output=True, text=True, timeout=30,
            )
            matches = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    data = __import__("json").loads(line)
                    if data.get("type") == "match":
                        fpath = data["data"]["path"]["text"]
                        rel = str(Path(fpath).relative_to(self.repo_dir))
                        matches.append(rel)
                except (KeyError, ValueError):
                    pass
            return {"status": "success", "matches": matches[:50]}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Search timed out"}
        except FileNotFoundError:
            result = subprocess.run(
                ["grep", "-rl", "--include", file_pattern, query, str(self.repo_dir)],
                capture_output=True, text=True, timeout=30,
            )
            matches = [str(Path(f).relative_to(self.repo_dir)) for f in result.stdout.strip().split("\n") if f]
            return {"status": "success", "matches": matches[:50]}

    def get_repo_structure(self, depth: int = 3) -> dict:
        """Get the repository directory structure up to a given depth."""
        if self.repo_dir is None:
            return {"status": "error", "message": "No repository cloned"}

        try:
            result = subprocess.run(
                ["find", str(self.repo_dir), "-maxdepth", str(depth),
                 "-not", "-path", "*/.git/*", "-not", "-path", "*/__pycache__/*",
                 "-not", "-path", "*/node_modules/*"],
                capture_output=True, text=True, timeout=15,
            )
            paths = sorted(result.stdout.strip().split("\n"))
            rel_paths = []
            for p in paths:
                try:
                    rel_paths.append(str(Path(p).relative_to(self.repo_dir)))
                except ValueError:
                    pass
            return {"status": "success", "structure": rel_paths[:300]}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class GitTools:
    """Tools for git operations in the target repository."""

    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = repo_dir

    def set_repo(self, repo_dir: Path) -> None:
        self.repo_dir = repo_dir

    def _run_git(self, args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + args,
            cwd=str(self.repo_dir), capture_output=True, text=True, timeout=timeout,
        )

    def git_diff(self) -> dict:
        """Get the current diff of uncommitted changes."""
        if self.repo_dir is None:
            return {"status": "error", "message": "No repository set"}

        result = self._run_git(["diff"])
        return {"status": "success", "diff": result.stdout[:10000]}

    def git_log(self, n: int = 10) -> dict:
        """Get recent commit log."""
        if self.repo_dir is None:
            return {"status": "error", "message": "No repository set"}

        result = self._run_git(["log", f"-{n}", "--oneline", "--no-decorate"])
        return {"status": "success", "log": result.stdout}

    def create_patch(self) -> dict:
        """Create a unified diff patch from current changes."""
        if self.repo_dir is None:
            return {"status": "error", "message": "No repository set"}

        result = self._run_git(["diff", "--unified=5"])
        if not result.stdout.strip():
            return {"status": "error", "message": "No changes to create patch from"}
        return {"status": "success", "patch": result.stdout}


class TestTools:
    """Tools for running tests in the target repository."""

    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = repo_dir

    def set_repo(self, repo_dir: Path) -> None:
        self.repo_dir = repo_dir

    def run_tests(self, test_path: str = "", timeout: int = 300) -> dict:
        """Run the test suite (or a specific test path)."""
        if self.repo_dir is None:
            return {"status": "error", "message": "No repository set"}

        cmd = self._detect_test_command(test_path)
        if cmd is None:
            return {"status": "error", "message": "Could not detect test framework"}

        try:
            result = subprocess.run(
                cmd, shell=True, cwd=str(self.repo_dir),
                capture_output=True, text=True, timeout=timeout,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            return {
                "status": "success",
                "passed": result.returncode == 0,
                "stdout": result.stdout[-3000:],
                "stderr": result.stderr[-1000:],
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": f"Tests timed out after {timeout}s"}

    def run_specific_test(self, test_file: str, test_name: str = "") -> dict:
        """Run a specific test file or test case."""
        target = f"{test_file}::{test_name}" if test_name else test_file
        return self.run_tests(target)

    def get_test_results(self) -> dict:
        """Parse the latest test results."""
        return self.run_tests()

    def _detect_test_command(self, test_path: str) -> Optional[str]:
        if self.repo_dir is None:
            return None

        if (self.repo_dir / "pytest.ini").exists() or (self.repo_dir / "pyproject.toml").exists():
            return f"python -m pytest {test_path} -x -q --tb=short" if test_path else "python -m pytest -x -q --tb=short"
        if (self.repo_dir / "setup.py").exists():
            return f"python -m pytest {test_path} -x -q --tb=short" if test_path else "python -m pytest -x -q --tb=short"
        if (self.repo_dir / "package.json").exists():
            return "npm test"
        if (self.repo_dir / "Makefile").exists():
            return "make test"
        return f"python -m pytest {test_path} -x -q --tb=short" if test_path else "python -m pytest -x -q --tb=short"


class AnalysisTools:
    """Tools for analyzing issues and PRs."""

    def __init__(self, github_token: str = ""):
        self.github_token = github_token
        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        } if github_token else {}

    def get_issue_context(self, owner: str, repo: str, issue_number: int) -> dict:
        """Fetch full issue context including comments."""
        import requests
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
        resp = requests.get(url, headers=self.headers, timeout=30)
        if resp.status_code != 200:
            return {"status": "error", "message": f"HTTP {resp.status_code}"}

        issue = resp.json()

        comments_resp = requests.get(
            f"{url}/comments", headers=self.headers, timeout=30
        )
        comments = comments_resp.json() if comments_resp.status_code == 200 else []

        return {
            "status": "success",
            "title": issue.get("title", ""),
            "body": issue.get("body", ""),
            "labels": [l["name"] for l in issue.get("labels", [])],
            "comments": [
                {"author": c.get("user", {}).get("login", ""), "body": c.get("body", "")}
                for c in comments[:20]
            ],
        }

    def search_similar_issues(self, owner: str, repo: str, query: str, k: int = 5) -> dict:
        """Search for similar issues in the same repository."""
        import requests
        url = f"https://api.github.com/search/issues"
        params = {
            "q": f"{query} repo:{owner}/{repo} is:issue",
            "per_page": k,
            "sort": "relevance",
        }
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        if resp.status_code != 200:
            return {"status": "error", "message": f"HTTP {resp.status_code}"}

        items = resp.json().get("items", [])
        return {
            "status": "success",
            "issues": [
                {"number": i["number"], "title": i["title"], "state": i["state"]}
                for i in items
            ],
        }

    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> dict:
        """Get the list of files changed in a PR."""
        import requests
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        resp = requests.get(url, headers=self.headers, timeout=30)
        if resp.status_code != 200:
            return {"status": "error", "message": f"HTTP {resp.status_code}"}

        files = resp.json()
        return {
            "status": "success",
            "files": [
                {"filename": f["filename"], "status": f["status"], "changes": f.get("changes", 0)}
                for f in files
            ],
        }
