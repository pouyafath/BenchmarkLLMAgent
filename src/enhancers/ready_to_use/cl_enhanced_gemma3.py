"""
CL-Enhanced Agent (Gemma3-12B) wrapper for BenchmarkLLMAgent.

Integrates the V2_29 agent from LLMforGithubIssuesRefactor via subprocess.
The V2_29 agent runs in a separate conda environment (issue_enhancer_py312) with
its own Qdrant storage and LightGBM evaluator.

Key features:
  - Managed iterative enhancement (up to 5 iterations)
  - LightGBM quality gate (threshold >= 0.5)
  - retrieve_enhanced RAG (seed_309 collection, 307 pre-seeded enhancements)
  - Continuous learning (successful enhancements stored back to Qdrant)

Environment variables (all optional):
  CL_ENHANCED_TIMEOUT       - Per-issue timeout in seconds (default: 600)
  CL_ENHANCED_MAX_WORKERS   - Not used directly, but respected by caller
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ── paths ────────────────────────────────────────────────────────────────────
_LLMFOR_ROOT = Path("/home/22pf2/LLMforGithubIssuesRefactor")
_CONDA_PYTHON = "/home/22pf2/anaconda3/envs/issue_enhancer_py312/bin/python"
_RAG_COLLECTION = "seed_309"
_QDRANT_LOCAL_PATH = str(_LLMFOR_ROOT / "qdrant_data_v2_29_offline_gemma")
_MODEL = "gemma3:12b-it-fp16"
_TIMEOUT = int(os.environ.get("CL_ENHANCED_TIMEOUT", "600"))

# ── per-issue subprocess script template ─────────────────────────────────────
_ISSUE_SCRIPT_TEMPLATE = """\
#!/usr/bin/env python3
import json, sys, asyncio, logging, os

sys.path.insert(0, '/home/22pf2/LLMforGithubIssuesRefactor/src')

logging.basicConfig(level=logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("qdrant_client").setLevel(logging.WARNING)

try:
    from RefactoredIssueEnhancerDeepAgent.Managed_IssueEnhancerDeepAgent_V2_29.runtime import (
        build_issue_enhancer_runtime,
    )
    from RefactoredIssueEnhancerDeepAgent.Managed_IssueEnhancerDeepAgent_V2_29.schemas import (
        IssueEnhancementTask,
    )
    from RefactoredIssueEnhancerDeepAgent.config import IssueEnhancerDeepAgentConfig
except ImportError as e:
    print(f"JSON_RESULT:{json.dumps({'error': str(e), 'success': False})}")
    sys.exit(1)

task_json = TASK_JSON_PLACEHOLDER
task_data = json.loads(task_json)

config = IssueEnhancerDeepAgentConfig()
config.llm.provider = "ollama"
config.llm.model_name = "MODEL_PLACEHOLDER"
config.evaluation.fast_probability_threshold = 0.5
config.planner.model_name = "MODEL_PLACEHOLDER"

try:
    runtime = build_issue_enhancer_runtime(config)
except Exception as e:
    print(f"JSON_RESULT:{json.dumps({'error': f'runtime build failed: {e}', 'success': False})}")
    sys.exit(1)

task = IssueEnhancementTask(
    issue_id=task_data['issue_id'],
    title=task_data['title'],
    body=task_data.get('body', ''),
    metadata={
        'repo_name': task_data.get('repo_name', ''),
        'issue_number': task_data.get('issue_number', ''),
    },
)

try:
    result = asyncio.run(runtime.enhance_issue_async(task))

    final_score = 0.0
    iterations = 0
    if result.artifacts and result.artifacts.evaluation:
        ev = result.artifacts.evaluation
        if isinstance(ev, dict):
            final_score = ev.get('final_score', 0.0)
            iterations = ev.get('iterations', 0)

    enhanced_title = task_data['title']
    enhanced_body = task_data.get('body', '')
    if result.enhanced_issue:
        if isinstance(result.enhanced_issue, dict):
            enhanced_title = result.enhanced_issue.get('title') or enhanced_title
            enhanced_body = result.enhanced_issue.get('body') or enhanced_body
        else:
            enhanced_title = result.enhanced_issue.title or enhanced_title
            enhanced_body = result.enhanced_issue.body or enhanced_body

    output = {
        'success': result.success,
        'enhanced_title': enhanced_title,
        'enhanced_body': enhanced_body,
        'final_score': final_score,
        'iterations': iterations,
        'above_threshold': final_score >= 0.5,
    }
    print(f"JSON_RESULT:{json.dumps(output)}")
except Exception as e:
    print(f"JSON_RESULT:{json.dumps({'error': str(e), 'success': False})}")
    sys.exit(1)
"""


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    """
    Enhance a GitHub issue using the CL-Enhanced Agent (V2_29, Gemma3-12B).

    Runs the agent in a subprocess under the issue_enhancer_py312 conda env.
    Falls back to returning the original issue on timeout or error.

    Args:
        issue: BenchmarkLLMAgent issue dict (instance_id, title, body, repo_name, etc.)
        changed_files: Not used by this agent.

    Returns:
        {enhanced_title, enhanced_body, enhancement_metadata}
    """
    title = issue.get("title") or issue.get("instance_id") or ""
    body = issue.get("body") or issue.get("problem_statement") or ""
    issue_id = (
        issue.get("instance_id")
        or issue.get("issue_id")
        or f"{issue.get('repo_name', 'unknown')}__{issue.get('issue_number', 'unknown')}"
    )
    repo_name = issue.get("repo_name", "")
    issue_number = issue.get("issue_number", "")

    task_data = {
        "issue_id": str(issue_id),
        "title": title,
        "body": body,
        "repo_name": repo_name,
        "issue_number": str(issue_number),
    }

    # Build per-issue script
    script = _ISSUE_SCRIPT_TEMPLATE.replace(
        "TASK_JSON_PLACEHOLDER", repr(json.dumps(task_data))
    ).replace("MODEL_PLACEHOLDER", _MODEL)

    env = {
        **os.environ,
        "PYTHONPATH": "src",
        "RAG_COLLECTION_NAME": _RAG_COLLECTION,
        "QDRANT_LOCAL_PATH": _QDRANT_LOCAL_PATH,
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="cl_enhanced_"
    ) as tf:
        tf.write(script)
        script_path = tf.name

    try:
        result = subprocess.run(
            [_CONDA_PYTHON, script_path],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            cwd=str(_LLMFOR_ROOT),
            env=env,
        )
        output_text = result.stdout or ""
    except subprocess.TimeoutExpired:
        return _error_result(
            title,
            body,
            f"cl_enhanced_gemma3 timed out after {_TIMEOUT}s",
        )
    except Exception as e:
        return _error_result(title, body, str(e))
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass

    # Parse JSON_RESULT from stdout
    for line in reversed(output_text.splitlines()):
        line = line.strip()
        if line.startswith("JSON_RESULT:"):
            json_str = line[len("JSON_RESULT:"):]
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                break

            if "error" in data and not data.get("success"):
                return _error_result(title, body, data["error"])

            return {
                "enhanced_title": data.get("enhanced_title", title),
                "enhanced_body": data.get("enhanced_body", body),
                "enhancement_metadata": {
                    "enhancer_type": "real",
                    "agent_id": "cl_enhanced_gemma3",
                    "agent_type": "managed_iterative",
                    "model": _MODEL,
                    "provider": "ollama",
                    "success": data.get("success", False),
                    "iterations": data.get("iterations", 0),
                    "final_score": data.get("final_score", 0.0),
                    "above_threshold": data.get("above_threshold", False),
                    "continuous_learning": True,
                    "rag_collection": _RAG_COLLECTION,
                    "returncode": result.returncode,
                },
            }

    # No JSON_RESULT found — treat as error
    stderr_preview = (result.stderr or "")[:500]
    stdout_preview = output_text[:500]
    return _error_result(
        title,
        body,
        f"No JSON_RESULT in output. returncode={result.returncode}. stderr={stderr_preview[:200]}",
        extra={
            "stdout_preview": stdout_preview,
            "stderr_preview": stderr_preview,
            "returncode": result.returncode,
        },
    )


def _error_result(
    title: str,
    body: str,
    error: str,
    extra: dict | None = None,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "enhancer_type": "error",
        "agent_id": "cl_enhanced_gemma3",
        "model": _MODEL,
        "provider": "ollama",
        "success": False,
        "error": error,
        "continuous_learning": True,
        "rag_collection": _RAG_COLLECTION,
    }
    if extra:
        meta.update(extra)
    return {
        "enhanced_title": title,
        "enhanced_body": body,
        "enhancement_metadata": meta,
    }
