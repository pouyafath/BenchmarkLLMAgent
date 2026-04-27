"""
Patch extraction and evaluation utilities.

Shared across solver and evaluator scripts for consistent
patch parsing, comparison, and metric computation.
"""

import re
from difflib import SequenceMatcher
from typing import List, Dict, Any


def extract_patch_from_response(response_text: str) -> str:
    """Extract a unified diff patch from an LLM response that may include markdown."""
    lines = response_text.split("\n")
    patch_lines = []
    in_patch = False
    in_code_block = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code_block:
                in_code_block = False
                if in_patch:
                    continue
                continue
            in_code_block = True
            continue

        if line.startswith("---") or line.startswith("diff --git"):
            in_patch = True
        if in_patch:
            patch_lines.append(line)

    if patch_lines:
        return "\n".join(patch_lines)

    diff_block = re.search(
        r"((?:diff --git|---)[^\n]*\n(?:.*\n)*?(?=\n(?:diff --git|$)))",
        response_text,
        re.MULTILINE,
    )
    if diff_block:
        return diff_block.group(0)

    return response_text.strip()


def evaluate_patch(
    agent_patch: str, gt_patch: str, gt_files: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute evaluation metrics comparing an agent patch against ground truth."""
    metrics = {
        "has_patch": bool(agent_patch.strip()),
        "patch_length": len(agent_patch),
        "file_overlap": 0.0,
        "content_similarity": 0.0,
        "gt_files_count": len(gt_files),
        "agent_files_count": 0,
    }
    if not agent_patch.strip() or not gt_patch.strip():
        return metrics

    agent_files = set()
    for line in agent_patch.split("\n"):
        if line.startswith("+++ ") or line.startswith("--- "):
            f = line.split(" ", 1)[1].strip() if " " in line else ""
            for prefix in ("a/", "b/"):
                if f.startswith(prefix):
                    f = f[2:]
            if f and f != "/dev/null":
                agent_files.add(f)

    gt_file_set = {f["filename"] for f in gt_files}
    metrics["agent_files_count"] = len(agent_files)

    if agent_files or gt_file_set:
        metrics["file_overlap"] = len(agent_files & gt_file_set) / len(
            agent_files | gt_file_set
        )

    metrics["content_similarity"] = SequenceMatcher(None, agent_patch, gt_patch).ratio()
    return metrics


def strip_git_metadata(patch: str) -> str:
    """Extract only diff content starting from 'diff --git' lines,
    removing commit metadata (From, Author, Date, Subject)."""
    lines = patch.split("\n")
    diff_lines = []
    in_diff = False
    for line in lines:
        if line.startswith("diff --git"):
            in_diff = True
        if in_diff:
            diff_lines.append(line)
    return "\n".join(diff_lines)
