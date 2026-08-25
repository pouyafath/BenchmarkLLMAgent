"""
OpenHands enhancer — Category A.

Runs OpenHands as a Python module (`python -m openhands.core.main`) in headless
mode, pointing at gpt-5.4-mini via OpenAI API.

Returns an error dict if the process times out or exits non-zero.

Environment variables (all optional):
  OPENHANDS_MODEL    - model (default: gpt-5.4-mini)
  OPENHANDS_BASE_URL - OpenAI-compat base URL (default: https://api.openai.com/v1)
  OPENHANDS_API_KEY  - API key (default: OPENAI_API_KEY env var)
  OPENHANDS_TIMEOUT  - seconds before giving up (default: 300)
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

import sys
_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_root))

# Use the bench_env Python that has openhands installed
_BENCH_PYTHON = str(_root / "bench_env" / "bin" / "python")

from src.enhancers.ready_to_use.native_output_parser import parse_enhanced_output



_MODEL    = os.environ.get("OPENHANDS_MODEL",    "gpt-5.4-mini")
_BASE_URL = os.environ.get("OPENHANDS_BASE_URL", "https://api.openai.com/v1")
_API_KEY  = os.environ.get("OPENHANDS_API_KEY",  os.environ.get("OPENAI_API_KEY", ""))
_TIMEOUT  = int(os.environ.get("OPENHANDS_TIMEOUT", "300"))
# Iterations: ~30-step agent loop, matching the paper's stated configuration and the
# solver's OH_SOLVER_MAX_ITER=30. Was 8, which did not match the description.
_MAX_ITER = int(os.environ.get("OPENHANDS_MAX_ITER", "30"))
# Repo-backed runs need a real timeout (container pull + exploration), not 300s.
_REPO_TIMEOUT = int(os.environ.get("OPENHANDS_REPO_TIMEOUT", "1800"))

ENHANCEMENT_TASK = """\
Enhance the GitHub issue below and write the result to the file `enhanced_issue.md`.

Repository: {repo}
Issue #{num}

## Original Title
{title}

## Original Body
{body}

## Hints (files changed in the fix)
{changed_files}

Instructions:
1. Write the enhanced issue to `enhanced_issue.md` using bash (cat or echo), in EXACTLY this format:
---
ENHANCED_TITLE: <improved single-line title>
ENHANCED_BODY:
<improved body as markdown with: ## Summary, ## Steps to Reproduce, ## Expected, ## Actual>
---
2. Improve: add reproduction steps, clarify expected vs actual, reference affected files.
3. Call finish() when done."""


ENHANCEMENT_TASK_REPO = """\
Enhance the GitHub issue below, using the ACTUAL SOURCE CODE, and write the result to
`/workspace/enhanced_issue.md`.

Repository: {repo}
Issue #{num}

## Original Title
{title}

## Original Body
{body}

Instructions:
1. `cd /testbed` — the repository is checked out there. Investigate it: search for the
   code the issue describes, read the relevant files, and identify where the defect is.
   DO NOT modify anything in /testbed and DO NOT write a fix; this is investigation only.
2. Write the enhanced issue to `/workspace/enhanced_issue.md` in EXACTLY this format:
---
ENHANCED_TITLE: <improved single-line title>
ENHANCED_BODY:
<improved body as markdown with: ## Summary, ## Steps to Reproduce, ## Expected, ## Actual,
 ## Code Context (real file paths, functions and line numbers you verified in /testbed)>
---
3. Only cite files/symbols you actually opened in /testbed. Never guess a path.
4. Preserve the original report's information; add to it rather than replacing it.
5. Call finish() when done."""


def _parse_output(text: str, fallback_title: str, fallback_body: str) -> tuple[str, str]:
    title, body, _ = parse_enhanced_output(text, fallback_title, fallback_body)
    return title, body


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    title = issue.get("title") or issue.get("instance_id") or ""
    body  = issue.get("body") or issue.get("problem_statement") or ""
    repo  = issue.get("repo_name", "")
    num   = issue.get("issue_number", "")

    if not changed_files and "pr_files" in issue:
        changed_files = ", ".join(f["filename"] for f in issue["pr_files"][:10])

    # Repository access: use the instance's RepoLaunch image when present.
    _docker_image = issue.get("docker_image") or issue.get("image_name", "")
    if _docker_image:
        task_text = ENHANCEMENT_TASK_REPO.format(repo=repo, num=num, title=title, body=body)
    else:
        task_text = ENHANCEMENT_TASK.format(
            repo=repo, num=num, title=title, body=body, changed_files=changed_files
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        task_file = Path(tmpdir) / "task.txt"
        task_file.write_text(task_text, encoding="utf-8")

        # Repository access. When the instance carries a RepoLaunch image we run the
        # agent inside it, so the repo is present at /testbed exactly as the solver
        # sees it — this is what the paper describes. Without an image we fall back
        # to the old local runtime (no repo), and say so in the metadata.
        workspace = Path(tmpdir) / "workspace" / "local"
        workspace.mkdir(parents=True, exist_ok=True)
        if _docker_image:
            config_toml = f"""
[core]
workspace_base = "{workspace}"
enable_browser = false

[llm]
model = "{_MODEL if "/" in _MODEL else f"openai/{_MODEL}"}"
base_url = "{_BASE_URL}"
api_key = "{_API_KEY}"
temperature = 0.3
max_output_tokens = 16384

[sandbox]
base_container_image = "{_docker_image}"
user_id = 0
timeout = 120
"""
        else:
            config_toml = f"""
[core]
runtime = "local"
enable_browser = false

[llm]
model = "{_MODEL if "/" in _MODEL else f"openai/{_MODEL}"}"
base_url = "{_BASE_URL}"
api_key = "{_API_KEY}"
"""
        config_path = Path(tmpdir) / "config.toml"
        config_path.write_text(config_toml, encoding="utf-8")

        cmd = [
            _BENCH_PYTHON,
            "-m", "openhands.core.main",
            "-f", str(task_file),
            "-i", str(_MAX_ITER),
            "--config-file", str(config_path),
        ]

        env = {**os.environ}

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=(_REPO_TIMEOUT if _docker_image else _TIMEOUT),
                cwd=tmpdir,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return {
                "enhanced_title": title,
                "enhanced_body":  body,
                "enhancement_metadata": {
                    "enhancer_type": "error",
                    "agent_id": "openhands",
                    "model": _MODEL,
                    "base_url": _BASE_URL,
                    "error": f"openhands timeout after {_TIMEOUT}s",
                },
            }
        except Exception as e:
            return {
                "enhanced_title": title,
                "enhanced_body":  body,
                "enhancement_metadata": {
                    "enhancer_type": "error",
                    "agent_id": "openhands",
                    "error": str(e),
                },
            }

        # Require returncode == 0: a non-zero exit means the CLI itself failed,
        # even if a partial output file was written with valid markers.
        if result.returncode != 0:
            return {
                "enhanced_title": title,
                "enhanced_body":  body,
                "enhancement_metadata": {
                    "enhancer_type": "error",
                    "agent_id": "openhands",
                    "model": _MODEL,
                    "base_url": _BASE_URL,
                    "error": f"openhands exited with returncode {result.returncode}",
                    "returncode": result.returncode,
                    "stderr_preview": (result.stderr or "")[:300],
                },
            }

        # Read the output file written by the agent
        output_file = workspace / "enhanced_issue.md"
        file_content = ""
        if output_file.exists():
            file_content = output_file.read_text(encoding="utf-8", errors="replace")

        # Also try stdout/stderr as fallback
        stdout_content = (result.stdout or "").strip()

        # Parse both sources; pick best
        for content in (file_content, stdout_content):
            if not content:
                continue
            enh_title, enh_body, parse_source = parse_enhanced_output(content, title, body)
            if enh_title != title or enh_body != body:
                return {
                    "enhanced_title": enh_title,
                    "enhanced_body":  enh_body,
                    "enhancement_metadata": {
                        "enhancer_type": "real", "repo_access": bool(_docker_image), "max_iter": _MAX_ITER,
                        "agent_id": "openhands",
                        "model": _MODEL,
                        "base_url": _BASE_URL,
                        "returncode": result.returncode,
                        "parse_source": parse_source,
                        "source": "file" if content == file_content else "stdout",
                    },
                }

        return {
            "enhanced_title": title,
            "enhanced_body":  body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "openhands",
                "model": _MODEL,
                "base_url": _BASE_URL,
                "returncode": result.returncode,
                "error": "no ENHANCED_TITLE/ENHANCED_BODY markers in output file or stdout",
                "file_exists": output_file.exists(),
                "file_preview": file_content[:300],
                "stderr_preview": (result.stderr or "")[:300],
            },
        }
