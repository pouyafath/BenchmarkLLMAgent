"""
Shared helper: materialise an instance's repository into a local directory.

Enhancers that run a *local* CLI (aider, trae, mini-swe-agent) cannot be pointed at a
container the way OpenHands and SWE-agent can, so to give them genuine repository access
the repo is exported out of the instance's RepoLaunch image at the target commit.

`git archive` is used rather than `docker cp` of the whole /testbed: it yields only
git-tracked files (~800 vs ~31,000 for a typical instance) with no .venv, caches or build
artifacts, at the same cost (measured 5.6s vs 6.6s). A smaller tree keeps the agent's
file search focused on real source.
"""

from __future__ import annotations

import subprocess
import tarfile
from io import BytesIO
from pathlib import Path


def export_repo(docker_image: str, dest: Path, timeout: int = 600) -> int:
    """Extract the git-tracked repo at HEAD from `docker_image` into `dest`.

    Returns the number of files written (0 if unavailable, so callers can degrade to
    their previous text-only behaviour rather than fail).
    """
    if not docker_image:
        return 0
    try:
        r = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "/bin/sh", docker_image,
             "-c", "cd /testbed && git archive --format=tar HEAD 2>/dev/null"],
            capture_output=True, timeout=timeout,
        )
        if r.returncode != 0 or not r.stdout:
            return 0
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=BytesIO(r.stdout)) as tf:
            tf.extractall(dest)          # archive is produced by us from a trusted image
        return sum(1 for p in dest.rglob("*") if p.is_file())
    except Exception:
        return 0


REPO_PREAMBLE = """
The repository for this issue is checked out in your working directory, at the exact
commit the issue refers to. Investigate it before writing anything: search for the code
the issue describes, open the relevant files, and identify where the defect actually is.

Do NOT modify any source file and do NOT write a fix — this is investigation only.

Cite only files, functions and line numbers you have actually opened and verified. Never
guess a path; an invented reference is worse than no reference. Preserve everything the
original report says and add to it rather than replacing it.
""".strip()


def enforce_append_only(original: str, enhanced: str) -> tuple[str, bool]:
    """Guarantee the original report survives; return (text, repaired).

    Agents given repository access tend to *replace* the report with their findings
    rather than add to them. Measured on one instance, trae returned 199 characters for
    a 6,619-character issue -- a 0.03x ratio, discarding 97% of what the reporter wrote,
    including the reproduction detail a solver needs. That is signal loss, not
    enhancement, and it confounds the experiment: a null could then mean either "added
    context does not help" or "we deleted the useful part".

    Applying this uniformly isolates the treatment to *added* context.
    """
    o, e = (original or "").strip(), (enhanced or "").strip()
    if not o or not e:
        return enhanced, False
    norm = lambda t: " ".join(t.split())
    if norm(o) in norm(e):
        return enhanced, False
    # keep whatever the agent added, but restore the original in front of it
    return f"{o}\n\n## Added by investigation\n\n{e}", True
