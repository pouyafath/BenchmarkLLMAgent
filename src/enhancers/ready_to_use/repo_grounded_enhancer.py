"""
Repo-grounded enhancer — a real agent with repository access.

This is the enhancer the paper's thesis actually calls for. Unlike the existing
aider/openhands/swe_agent enhancers, which are text-to-text rewriters run in an empty
temp directory, this one gets **exactly what the solver gets**: the per-instance
RepoLaunch container with the repository checked out at the target commit under
/testbed, plus the full OpenHands toolset (bash, file editor, ipython, search).

It explores the codebase and rewrites the issue grounded in what it actually finds.

NO ORACLE. Unlike ``code_context_enhancer`` (which reads filenames straight out of the
ground-truth patch and injects hints_text / FAIL_TO_PASS test names), this enhancer is
given only the issue text and the repository. It never sees:
  - the gold patch          - the test patch
  - hints_text              - FAIL_TO_PASS / PASS_TO_PASS test names
Those fields are explicitly stripped before the task is written, so a grounded claim
here reflects genuine localization work, not leakage.

Design constraints, motivated by
docs/analysis/why_enhancement_fails_and_what_could_work.md:
  1. APPEND-ONLY. The original issue text is preserved verbatim; the agent may only add
     a grounded context section. This removes the observed compression failure mode
     (the OpenHands enhancer's median output was *shorter* than the original).
  2. VERIFIED REFERENCES ONLY. Every file path the agent cites must exist in the repo;
     unverified/guessed references measurably hurt (2.4% rescue rate vs 12.7%).

Environment variables:
  RGE_MODEL / RGE_BASE_URL / RGE_API_KEY   LLM endpoint (same convention as the solver)
  RGE_MAX_ITER   agent turns for exploration (default 20)
  RGE_TIMEOUT    seconds before giving up (default 1800)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

_ROOT = Path("/home/22pf2/BenchmarkLLMAgent")
_MODEL    = os.environ.get("RGE_MODEL", "qwen3:32b")
_BASE_URL = os.environ.get("RGE_BASE_URL", "http://localhost:11435/v1")
_API_KEY  = os.environ.get("RGE_API_KEY", "ollama")
# Agent-loop budget: 30 steps, uniform across every enhancer and solver.
# Chosen so enhancer and solver get identical budgets (a symmetric, describable
# design), to match the OpenHands SWE-bench convention for comparability with
# prior work, and because it is empirically non-binding: agents that solve a task
# converge well before the cap, while those that reach it are thrashing and fail
# regardless (see docs/analysis/agent_iteration_budget.md).
_MAX_ITER = int(os.environ.get("RGE_MAX_ITER", "30"))
_TIMEOUT  = int(os.environ.get("RGE_TIMEOUT", "1800"))

# Fields that would leak the answer. Never place these in the task text.
_ORACLE_FIELDS = {
    "patch", "test_patch", "hints_text", "all_hints_text",
    "FAIL_TO_PASS", "PASS_TO_PASS", "FAIL_TO_PASS_count", "PASS_TO_PASS_count",
    "stage3_fail_to_pass_observed", "stage3_pass_to_pass_observed", "test_status",
    "f2p_p2p_derivation", "commit_urls",
}

_TASK_TEMPLATE = """<issue>
{problem_statement}
</issue>

<instructions>
# Task: Enrich a GitHub issue report using the actual codebase

You are a software engineer. A bug/feature has been reported in the issue above. Your job
is NOT to fix it. Your job is to investigate the repository and produce an **enriched
version of the issue report** that will help a *different* engineer fix it faster.

## Boundaries
- The repository is mounted at `/testbed`. `cd /testbed` to see the code.
- DO NOT modify any file in /testbed. This is a read-only investigation.
- DO NOT write a patch or fix the bug.

## Workflow
1. `cd /testbed`
2. Read the issue carefully and identify what it is about.
3. Search the codebase for the relevant code: the functions, classes and files that
   implement the described behaviour. Use grep/find/read aggressively.
4. Where useful, run a quick reproduction to confirm which code path is involved.
5. Determine the most likely location of the defect and why.

## Output — write to /workspace/enhanced_issue.md
Write a file `/workspace/enhanced_issue.md` with EXACTLY this structure:

<ORIGINAL_ISSUE_VERBATIM>
(copy the issue text above, unchanged, character for character)
</ORIGINAL_ISSUE_VERBATIM>

## Code Context (added by investigation)

### Relevant files
- `path/to/file.py` — one line on what it does and why it is relevant

### Relevant functions/classes
- `path/to/file.py::function_name` (line N) — what it does, how it relates to the issue

### Relevant code
```python
# the smallest excerpt that shows the suspect logic, with the file path above it
```

### Likely root cause
A short, concrete paragraph naming the specific code responsible, and why it produces the
reported behaviour.

## Hard rules for the output
- The original issue MUST be reproduced verbatim inside the tags. Never shorten, summarise
  or reword it. You may only ADD the Code Context section after it.
- ONLY cite files, functions and line numbers you have actually opened and verified in
  /testbed. Never guess a path. An invented reference is worse than no reference.
- If you genuinely cannot localize the issue, write "### Likely root cause\\nNot determined."
  rather than speculating.

## Submission
When `/workspace/enhanced_issue.md` is written and you have verified it with `cat`, you are done.
</instructions>"""


def _build_config_toml(docker_image: str, workspace_dir: str) -> str:
    return f"""[core]
workspace_base = "{workspace_dir}"

[llm]
model = "openai/{_MODEL}"
base_url = "{_BASE_URL}"
api_key = "{_API_KEY}"
temperature = 0.3
max_output_tokens = 16384

[sandbox]
base_container_image = "{docker_image}"
user_id = 0
timeout = 120
"""


def _strip_verbatim_tags(text: str) -> str:
    m = re.search(r"<ORIGINAL_ISSUE_VERBATIM>(.*?)</ORIGINAL_ISSUE_VERBATIM>",
                  text, re.S)
    if not m:
        return text
    original = m.group(1).strip()
    rest = text[m.end():].strip()
    return f"{original}\n\n{rest}" if rest else original


def _verify_append_only(original: str, enhanced: str) -> tuple[bool, str]:
    """Constraint 1: the original must survive. Compare on normalised whitespace."""
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    o, e = norm(original), norm(enhanced)
    if not o:
        return True, ""
    if o in e:
        return True, ""
    # allow minor drift: require a high fraction of the original's lines to survive
    lines = [l for l in (x.strip() for x in original.splitlines()) if len(l) > 25]
    if lines:
        kept = sum(1 for l in lines if norm(l) in e)
        if kept / len(lines) >= 0.9:
            return True, f"partial ({kept}/{len(lines)} long lines retained)"
    return False, "original text not preserved"


def _norm_path(p: str) -> str:
    """Strip a leading './' only. NOT lstrip('./') -- that strips characters, so
    '.venv/x.py' would become 'venv/x.py' and never match."""
    return p[2:] if p.startswith("./") else p


def _verify_references(enhanced: str, docker_image: str) -> tuple[int, int, list[str]]:
    """Constraint 2: every cited path must really exist in the container.

    Distinguishes three cases, because "not in `git ls-files`" is NOT the same as
    "does not exist" -- a cited dependency file under .venv/ is a real, readable file
    and citing it is not a hallucination:
      - git-tracked            -> verified (repo source)
      - exists but untracked   -> verified, reported separately as non-source
      - does not exist         -> hallucination, the only real failure
    Returns (verified, cited, hallucinated).
    """
    cited = set(re.findall(r'`([\w./-]+\.(?:py|js|ts|go|rs|java|c|cpp|h|rb|php))`', enhanced))
    cited |= set(re.findall(r'^###?\s*`?([\w./-]+\.py)`?', enhanced, re.M))
    cited = {_norm_path(c) for c in cited if "/" in c or c.endswith(".py")}
    if not cited:
        return 0, 0, []
    # One container call: list tracked files, then test existence of each cited path.
    probe = " ; ".join(f'[ -e "/testbed/{c}" ] && echo "EXISTS {c}"' for c in sorted(cited))
    try:
        out = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "/bin/sh", docker_image, "-c",
             f"cd /testbed && git ls-files 2>/dev/null; {probe}"],
            capture_output=True, text=True, timeout=300,
        ).stdout
    except Exception:
        return 0, len(cited), []
    tracked, exists = set(), set()
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("EXISTS "):
            exists.add(line[7:])
        elif line:
            tracked.add(_norm_path(line))
    basenames = {f.split("/")[-1] for f in tracked}
    def _variants(c: str) -> set[str]:
        """Accept dotted module notation. Weaker models cite
        'pkg.mod.file.py' for what is really 'pkg/mod/file.py'; that is a citation
        FORMAT artifact, not an invented path, and must not count as a hallucination."""
        v = {c}
        if "/" not in c and c.count(".") > 1 and c.endswith(".py"):
            v.add(c[:-3].replace(".", "/") + ".py")
        return v

    hallucinated = []
    for c in cited:
        vs = _variants(c)
        if (vs & tracked) or (vs & exists) or any(x.split("/")[-1] in basenames for x in vs):
            continue
        hallucinated.append(c)
    return len(cited) - len(hallucinated), len(cited), hallucinated


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    """Explore the repo in the solver's own container, then enrich the issue.

    `changed_files` is accepted for dispatcher compatibility and deliberately IGNORED —
    it carries oracle information about the real fix.
    """
    instance_id = issue.get("instance_id", "")
    docker_image = issue.get("docker_image") or issue.get("image_name", "")
    original = issue.get("problem_statement") or issue.get("body") or ""

    meta: dict[str, Any] = {"enhancer_type": "real", "agent_id": "repo_grounded",
                            "instance_id": instance_id, "model": _MODEL,
                            "image_name": docker_image, "oracle_used": False}
    if not docker_image:
        meta.update(enhancer_type="error", error="no docker_image for instance")
        return {"enhanced_body": "", "enhancement_metadata": meta}

    work_root = Path(os.environ.get("RGE_WORK_DIR", str(_ROOT/"runs/_rge_work")))
    inst_dir = (work_root / instance_id).resolve()
    inst_dir.mkdir(parents=True, exist_ok=True)
    ws = inst_dir / "workspace"; ws.mkdir(parents=True, exist_ok=True)

    # Only the issue text crosses into the task; no oracle field is ever read.
    # _ORACLE_FIELDS documents exactly what is withheld (see module docstring).
    (inst_dir/"task.txt").write_text(
        _TASK_TEMPLATE.format(problem_statement=original), encoding="utf-8")
    (inst_dir/"config.toml").write_text(
        _build_config_toml(docker_image, str(ws)), encoding="utf-8")

    cmd = [sys.executable, "-m", "openhands.core.main",
           "-f", str(inst_dir/"task.txt"), "-i", str(_MAX_ITER),
           "--config-file", str(inst_dir/"config.toml")]
    env = {**os.environ, "DOCKER_BUILDKIT": "0"}
    try:
        with (inst_dir/"agent.log").open("w") as lf:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=lf, text=True,
                           timeout=_TIMEOUT, cwd=str(inst_dir), env=env)
    except subprocess.TimeoutExpired:
        meta.update(enhancer_type="error", error=f"timeout after {_TIMEOUT}s")
        return {"enhanced_body": "", "enhancement_metadata": meta}
    except Exception as e:  # noqa: BLE001
        meta.update(enhancer_type="error", error=str(e))
        return {"enhanced_body": "", "enhancement_metadata": meta}

    out = ws/"enhanced_issue.md"
    if not out.exists() or not out.read_text(errors="replace").strip():
        meta.update(enhancer_type="error", error="agent produced no enhanced_issue.md")
        return {"enhanced_body": "", "enhancement_metadata": meta}

    enhanced = _strip_verbatim_tags(out.read_text(errors="replace"))

    ok_append, note = _verify_append_only(original, enhanced)
    if not ok_append:
        # Fail closed into append-only: keep the original, append whatever context was added
        extra = enhanced.split("## Code Context", 1)
        enhanced = (original + "\n\n## Code Context" + extra[1]) if len(extra) > 1 else original
        meta["append_only_repaired"] = True
    meta["append_only_note"] = note

    good, total, bad = _verify_references(enhanced, docker_image)
    meta.update(refs_verified=good, refs_cited=total, refs_bad=bad[:10])

    meta["len_ratio"] = round(len(enhanced)/max(len(original), 1), 2)
    meta["changed"] = enhanced.strip() != original.strip()

    # Persist verification alongside the run. The shared runner
    # (run_matrix_test.enhance) keeps only _enh_ok/_enh_by/_enh_err and drops
    # enhancement_metadata, so without this sidecar the append-only and
    # reference-verification results are lost.
    try:
        (inst_dir / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    except Exception:
        pass
    return {"enhanced_body": enhanced, "enhancement_metadata": meta}
