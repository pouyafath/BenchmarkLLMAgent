"""
Aider-based enhancement for Category A.

Uses aider CLI when available: writes issue to temp file, runs aider with
enhancement message, parses result. Returns error metadata if aider not found
(no fallback to LLM proxy).

Environment variables (all optional):
  AIDER_MODEL      - Model name for aider (default: openai/gpt-5.4-mini)
  AIDER_API_BASE   - Base URL for OpenAI-compat endpoint (default: https://api.openai.com/v1)
  AIDER_API_KEY    - API key (default: OPENAI_API_KEY env var)
  AIDER_TIMEOUT    - Seconds before giving up (default: 300)
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

import sys
_here = Path(__file__).resolve()
_root = _here.parent.parent.parent
sys.path.insert(0, str(_root))

_AIDER_CLI = "/home/22pf2/BenchmarkLLMAgent/bench_env/bin/aider"
_MODEL     = os.environ.get("AIDER_MODEL",    "openai/gpt-5.4-mini")
_API_BASE  = os.environ.get("AIDER_API_BASE", "https://api.openai.com/v1")
_API_KEY   = os.environ.get("AIDER_API_KEY",  os.environ.get("OPENAI_API_KEY", ""))
_TIMEOUT   = int(os.environ.get("AIDER_TIMEOUT", "300"))
_NOOP_MAX_RETRIES = int(os.environ.get("AIDER_NOOP_MAX_RETRIES", "2"))
_RETRY_TEMPERATURE = float(os.environ.get("AIDER_RETRY_TEMPERATURE", "0.2"))

ENHANCEMENT_PROMPT_REPO = """Enhance this GitHub issue using the ACTUAL SOURCE CODE in this repository.

The repository is checked out in your working directory. Investigate it first: find and read the
files implementing the behaviour the issue describes. Do NOT fix the bug and do NOT modify any
source file — only edit issue.md.

Rewrite issue.md to add: reproduction steps, expected vs actual behaviour, and a "## Code Context"
section citing the real file paths, functions and line numbers you verified in this repository.
Only cite paths you actually opened — never guess one. Preserve the original report's content and
add to it rather than replacing it.
"""

ENHANCEMENT_PROMPT = """Enhance this GitHub issue. Improve the title and body to be more complete, clear, and actionable.

Add: reproduction steps, expected vs actual behavior, environment details where inferable.
Keep the original content but restructure and enrich it. Add file references from the hints if relevant.

Output the enhanced issue in this exact format at the end of your response:
---
ENHANCED_TITLE: <improved title>
ENHANCED_BODY:
<improved body as markdown>
---"""

FORCE_REWRITE_SUFFIX = """\

Additional hard constraints for this attempt:
- Do not copy the original text verbatim.
- Keep the same facts, but rewrite and restructure the issue.
- The body must include these sections exactly as markdown headers:
  - `## Summary`
  - `## Steps to Reproduce`
  - `## Expected Behavior`
  - `## Actual Behavior`
  - `## Scope / Affected Areas`
- Include at least one bulleted list.
"""


def _aider_available() -> bool:
    return os.path.exists(_AIDER_CLI) or shutil.which("aider") is not None


def _get_aider_cmd() -> str:
    if os.path.exists(_AIDER_CLI):
        return _AIDER_CLI
    return shutil.which("aider") or "aider"


def _is_placeholder_title(title: str) -> bool:
    """Detect placeholder text that the LLM copied from the prompt template."""
    t = (title or "").strip().lower()
    if not t:
        return True
    if t in ("...", "…"):
        return True
    placeholder_tokens = (
        "<improved title>",
        "improved title",
        "<improved single-line title>",
        "improved single-line title",
        "<improved single line title>",
        "improved single line title",
        "<title>",
        "enhanced_title:",
    )
    return any(tok in t for tok in placeholder_tokens)


def _is_placeholder_body(body: str) -> bool:
    """Detect placeholder text that the LLM copied from the prompt template."""
    b = (body or "").strip().lower()
    if not b:
        return True
    placeholder_tokens = (
        "<improved body as markdown>",
        "improved body as markdown",
        "<improved body>",
        "enhanced_body:",
    )
    return any(tok in b for tok in placeholder_tokens)


def _body_quality_score(body: str, fallback_body: str) -> int:
    """Score whether a parsed body looks like a complete enhanced issue."""
    text = (body or "").strip()
    if _is_placeholder_body(text) or text == (fallback_body or "").strip():
        return -10

    lower = text.lower()
    score = 0
    if len(text) >= 180:
        score += 1
    if len(text) >= 350:
        score += 2
    if len(text) >= 700:
        score += 1

    section_signals = (
        "## summary",
        "steps to reproduce",
        "reproduction steps",
        "expected behavior",
        "## expected",
        "actual behavior",
        "## actual",
        "affected",
        "scope",
        "relevant files",
    )
    score += sum(1 for signal in section_signals if signal in lower)

    if re.search(r"(^|\n)\s*(?:[-*]\s+|\d+\.\s+)", text):
        score += 1
    if "```" in text:
        score += 1
    return score


def _is_quality_body(body: str, fallback_body: str) -> bool:
    return _body_quality_score(body, fallback_body) >= 4


_BOX_CHARS = str.maketrans("", "", "┏┓┗┛┃━╔╗╚╝║═╭╮╰╯│─")

def _strip_terminal_noise(text: str) -> str:
    """Remove leading terminal box-drawing/formatting lines from aider's rich UI output.

    Aider renders rich panels (e.g. '┏━━━┓\\n┃ GitHub Issue ┃\\n┗━━━┛') when it
    reads/displays the task file.  These characters leak into the enhanced body
    when the stdout parse path is taken.  Strip any leading lines that consist
    almost entirely of box-drawing characters.
    """
    lines = text.splitlines()
    start = 0
    for i, line in enumerate(lines):
        cleaned = line.translate(_BOX_CHARS).strip()
        # A "box" line is one where ≥50% of non-space chars are box-drawing chars
        original_nonspace = len(line.replace(" ", ""))
        if original_nonspace > 0 and len(cleaned.replace(" ", "")) / original_nonspace < 0.5:
            start = i + 1
        else:
            break
    return "\n".join(lines[start:]).strip()


def _parse_aider_output(content: str, fallback_title: str, fallback_body: str) -> tuple[str, str, str]:
    """Extract ENHANCED_TITLE and ENHANCED_BODY from aider's edited file content.

    Returns (title, body, parse_source). Tries three formats in order:
    1. Explicit markers: ENHANCED_TITLE: ... / ENHANCED_BODY: ...
    2. Known section pairs: ## Enhanced Title + ## Enhanced Body,
       ## Title + ## Description, ## Improved Title + ## Improved Body
    """
    candidates: list[tuple[str, str, str]] = []

    # Format 1: ENHANCED_TITLE: / ENHANCED_BODY: markers
    m = re.search(r"ENHANCED_TITLE:\s*(.+?)(?:\n|$)", content, re.DOTALL)
    body_m = re.search(r"ENHANCED_BODY:\s*\n([\s\S]*?)(?=---|\Z)", content, re.DOTALL)
    if m and body_m:
        candidate_title = m.group(1).strip()
        candidate_body = _strip_terminal_noise(body_m.group(1).strip())
        if (
            candidate_title
            and not _is_placeholder_title(candidate_title)
            and candidate_body
            and not _is_placeholder_body(candidate_body)
        ):
            candidates.append((candidate_title, candidate_body, "explicit_markers"))

    # Format 2: Only accept explicit known title+body section-name pairs.
    # Do NOT accept arbitrary short/long sections — that is too permissive and
    # would misparse normal issue markdown (## Steps to Reproduce, etc.).
    _KNOWN_PAIRS = [
        # (title_section_name, body_section_name)
        ("enhanced title",  "enhanced body"),
        ("improved title",  "improved body"),
        ("title",           "description"),
        ("issue title",     "issue body"),
        ("new title",       "new body"),
    ]
    section_re = re.compile(r"^##\s+(.+?)\s*\n([\s\S]*?)(?=^##\s|\Z)", re.MULTILINE)
    sections: dict[str, str] = {}
    section_body_starts: dict[str, int] = {}
    for sec_m in section_re.finditer(content):
        section_name = sec_m.group(1).strip().lower()
        sections[section_name] = sec_m.group(2).strip()
        section_body_starts[section_name] = sec_m.start(2)

    for title_key, body_key in _KNOWN_PAIRS:
        raw_title = sections.get(title_key, "")
        body_start = section_body_starts.get(body_key)
        raw_body = content[body_start:].strip() if body_start is not None else ""
        candidate_title = raw_title.split("\n")[0].strip()
        candidate_body  = _strip_terminal_noise(raw_body)
        if (
            candidate_title
            and not _is_placeholder_title(candidate_title)
            and candidate_title != fallback_title
            and candidate_body
            and not _is_placeholder_body(candidate_body)
            and candidate_body != fallback_body
        ):
            candidates.append((candidate_title, candidate_body, f"section_pair:{title_key}+{body_key}"))

    # Format 3: Complete file rewrite — aider replaced the entire task file.
    # Detected by: H1 header (`# `) that is NOT the original template header
    # ("# GitHub Issue"), followed by body content.
    _TEMPLATE_H1 = {"github issue", "github issue\n"}
    h1_match = re.match(r"^#\s+(.+?)[\r\n]+([\s\S]+)", content.strip())
    if h1_match:
        h1_title = h1_match.group(1).strip()
        h1_body  = _strip_terminal_noise(h1_match.group(2).strip())
        if (
            h1_title.lower() not in _TEMPLATE_H1
            and not _is_placeholder_title(h1_title)
            and h1_title != fallback_title
            and h1_body
            and not _is_placeholder_body(h1_body)
            and h1_body != fallback_body
        ):
            candidates.append((h1_title, h1_body, "h1_rewrite"))

    best = (fallback_title, fallback_body, "none")
    best_score = -10
    for cand_title, cand_body, source in candidates:
        score = _body_quality_score(cand_body, fallback_body)
        if score > best_score:
            best = (cand_title, cand_body, source)
            best_score = score

    if _is_quality_body(best[1], fallback_body):
        return best

    return fallback_title, fallback_body, "none"


def _build_task_text(
    *,
    repo: str,
    num: str | int,
    title: str,
    body: str,
    changed_files: str,
    force_rewrite: bool,
) -> str:
    suffix = FORCE_REWRITE_SUFFIX if force_rewrite else ""
    return f"""# GitHub Issue

Repository: {repo}
Issue #{num}

## Original Title
{title}

## Original Body
{body}

## Hints (files changed in fix)
{changed_files}

{ENHANCEMENT_PROMPT}
{suffix}"""


def _export_repo(docker_image: str, dest: Path) -> int:
    """Copy /testbed out of the instance image into `dest`. Returns files exported.

    Aider is a local CLI, so to give it genuine repository access we materialise the
    repository at the target commit from the RepoLaunch image. Aider then gets a real
    repo map and can read the source, instead of seeing only the issue file.
    """
    try:
        cid = subprocess.run(["docker", "create", docker_image, "true"],
                             capture_output=True, text=True, timeout=300).stdout.strip()
        if not cid:
            return 0
        try:
            subprocess.run(["docker", "cp", f"{cid}:/testbed/.", str(dest)],
                           capture_output=True, timeout=1200)
        finally:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=120)
        # Prune untracked bulk (venv, caches). Aider's repo map uses `git ls-files`,
        # so these were never indexed anyway; dropping them saves disk and time.
        import shutil as _sh
        for junk in (".venv", "venv", ".pytest_cache", ".cache", "node_modules", ".mypy_cache"):
            t = dest / junk
            if t.is_dir():
                _sh.rmtree(t, ignore_errors=True)
        return sum(1 for _ in dest.rglob("*") if _.is_file())
    except Exception:
        return 0


def _run_aider_once(
    *,
    task_text: str,
    title: str,
    body: str,
    docker_image: str = "",
) -> dict[str, Any]:
    aider_cmd = _get_aider_cmd()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Repository access: materialise the repo at the target commit so aider can
        # actually read the source (repo map + file reads), matching the paper.
        n_files = _export_repo(docker_image, Path(tmpdir)) if docker_image else 0
        # Create a git repo (aider requires it)
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

        issue_path = Path(tmpdir) / "issue.md"
        issue_path.write_text(task_text, encoding="utf-8")

        subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmpdir, capture_output=True)

        # Build a clean environment for aider: strip AIDER_* vars to prevent
        # them from being auto-interpreted as CLI flags by aider.
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("AIDER_")}
        clean_env["OPENAI_API_KEY"] = _API_KEY
        clean_env["OPENAI_API_BASE"] = _API_BASE
        clean_env["AIDER_YES"] = "1"

        try:
            result = subprocess.run(
                [
                    aider_cmd,
                    "--model", _MODEL,
                    "--no-auto-commits",
                    # With a materialised repo we keep git ENABLED so aider builds a
                    # repo map and can read the source. Without one, git adds nothing.
                    *([] if n_files else ["--no-git"]),
                    *(["--map-tokens", "2048"] if n_files else []),
                    "--yes",
                    "--no-check-update",
                    "--no-analytics",
                    "--no-show-model-warnings",
                    "--message", (ENHANCEMENT_PROMPT_REPO if n_files else ENHANCEMENT_PROMPT),
                    str(issue_path),
                ],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                cwd=tmpdir,
                env=clean_env,
            )
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(str(e)) from e

        # Try to parse from the edited file first
        content = issue_path.read_text(encoding="utf-8")
        file_title, file_body, file_parse_source = _parse_aider_output(content, title, body)

        # Also try stdout
        stdout_title, stdout_body, stdout_parse_source = _parse_aider_output(result.stdout or "", title, body)

        # Pick best (file takes priority over stdout)
        labeled = [
            ("file",   file_title,   file_body,   file_parse_source),
            ("stdout", stdout_title, stdout_body, stdout_parse_source),
        ]
        best_title, best_body, best_source, best_parse_source = title, body, "none", "none"
        for src, ct, cb, ps in labeled:
            if ct != title or cb != body:
                best_title, best_body, best_source, best_parse_source = ct, cb, src, ps
                break

        return {
            "enhanced_title": best_title,
            "enhanced_body": best_body,
            "returncode": result.returncode,
            "stderr_preview": (result.stderr or "")[:300],
            "stdout_preview": (result.stdout or "")[:500],
            "parse_source": best_parse_source,
            "source": best_source,
        }


def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    """Enhance using aider CLI (native only, no proxy fallback)."""
    title = issue.get("title") or issue.get("instance_id") or ""
    body = issue.get("body") or issue.get("problem_statement") or ""
    if not _aider_available():
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "aider",
                "error": f"aider CLI not found at {_AIDER_CLI} or in PATH",
            },
        }

    repo = issue.get("repo_name", "")
    num = issue.get("issue_number", "")
    if not changed_files and "pr_files" in issue:
        changed_files = ", ".join(f["filename"] for f in issue["pr_files"][:10])

    attempts: list[dict[str, Any]] = []
    run_errors: list[str] = []
    first_result: dict[str, Any] | None = None
    final_result: dict[str, Any] | None = None

    for attempt_idx in range(_NOOP_MAX_RETRIES + 1):
        force_rewrite = attempt_idx > 0
        task_text = _build_task_text(
            repo=repo,
            num=num,
            title=title,
            body=body,
            changed_files=changed_files,
            force_rewrite=force_rewrite,
        )
        try:
            run_result = _run_aider_once(
                task_text=task_text,
                title=title,
                body=body,
                docker_image=issue.get("docker_image") or issue.get("image_name", ""),
            )
        except TimeoutError:
            return {
                "enhanced_title": title,
                "enhanced_body": body,
                "enhancement_metadata": {
                    "enhancer_type": "error",
                    "agent_id": "aider",
                    "model": _MODEL,
                    "base_url": _API_BASE,
                    "error": f"aider timeout after {_TIMEOUT}s",
                    "attempts": attempts,
                },
            }
        except Exception as e:
            run_errors.append(str(e))
            continue

        attempts.append(
            {
                "attempt": attempt_idx + 1,
                "force_rewrite": force_rewrite,
                "returncode": run_result.get("returncode"),
                "enhancement_noop": (
                    run_result.get("enhanced_title") == title
                    and run_result.get("enhanced_body") == body
                ),
            }
        )

        if first_result is None:
            first_result = run_result
        final_result = run_result
        if run_result["enhanced_title"] != title or run_result["enhanced_body"] != body:
            break

    if final_result is None:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "aider",
                "model": _MODEL,
                "base_url": _API_BASE,
                "error": run_errors[-1] if run_errors else "aider execution failed",
                "attempts": attempts,
            },
        }

    enh_title = final_result["enhanced_title"]
    enh_body = final_result["enhanced_body"]
    returncode = int(final_result.get("returncode", 1))

    # Require returncode == 0: a non-zero exit means the CLI itself failed,
    # even if markers happen to appear in partial output.
    if returncode != 0:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "aider",
                "model": _MODEL,
                "base_url": _API_BASE,
                "error": f"aider exited with returncode {returncode}",
                "aider_returncode": returncode,
                "aider_stderr_preview": final_result.get("stderr_preview", ""),
                "attempts": attempts,
            },
        }

    if enh_title == title and enh_body == body:
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "enhancer_type": "error",
                "agent_id": "aider",
                "model": _MODEL,
                "base_url": _API_BASE,
                "error": "aider exited 0 but no ENHANCED_TITLE/ENHANCED_BODY markers found",
                "aider_returncode": returncode,
                "aider_stderr_preview": final_result.get("stderr_preview", ""),
                "attempts": attempts,
            },
        }

    return {
        "enhanced_title": enh_title,
        "enhanced_body": enh_body,
        "enhancement_metadata": {
            "enhancer_type": "real",
            "agent_id": "aider",
            "model": _MODEL,
            "base_url": _API_BASE,
            "aider_returncode": returncode,
            "aider_stderr_preview": final_result.get("stderr_preview", ""),
            "aider_stdout_preview": final_result.get("stdout_preview", ""),
            "parse_source": final_result.get("parse_source", "unknown"),
            "source": final_result.get("source", "unknown"),
            "enhancement_noop": enh_title == title and enh_body == body,
            "attempt_count": len(attempts),
            "noop_retry_used": len(attempts) > 1,
            "attempts": attempts,
            "initial_noop": (
                first_result is not None
                and first_result.get("enhanced_title") == title
                and first_result.get("enhanced_body") == body
            ),
        },
    }
