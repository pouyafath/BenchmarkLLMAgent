#!/usr/bin/env python3
"""
Pouya 20-issue GPT-5.4-mini pilot pipeline — v2.

Stages:
  1. Select 20 deterministic rows from dataset
  2. Paul/RepoLaunch setup+organize (OpenAI gpt-5.4-mini)
     - disable_timemachine=true: no host.docker.internal pip proxy timeouts
     - hints and Paul target fields injected from PASS_TO_PASS: forces targeted pytest, not broad suites
     - success requires organize.jsonl with docker_image field
     - per-instance result classified: setup_failed | organize_missing |
       organize_passed | timeout | infra_complex
  3. SWE-bench-Live gold evaluation → validated_instances.jsonl
  4. mini-SWE-agent baseline solver (gpt-5.4-mini)
  5. mini-SWE-agent enhanced solver (gpt-5.4-mini + llm_append_analysis enhancer)
  6. Evaluate both solver conditions
  7. Write summary report

Usage:
    export OPENAI_API_KEY=...
    # or: export OPENAI_API_KEY_FILE=/path/to/plain-text-or-json-keyfile
    cd /home/22pf2/BenchmarkLLMAgent
    python scripts/workflows/run_pouya20_gpt54mini.py --run-dir runs/pouya_20_gpt54mini_v3

Monitoring:
    tail -f ~/BenchmarkLLMAgent/runs/pouya_20_gpt54mini_v3/progress.log
    python -m json.tool ~/BenchmarkLLMAgent/runs/pouya_20_gpt54mini_v3/progress.json
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import threading
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EVAL_SCRIPT = ROOT / "SWE-bench-Live-Collection/evaluation/evaluation.py"
SOLVER_SCRIPT = ROOT / "scripts/solvers/run_mini_sweagent_jsonl.py"
REPLICATION_DIR = Path("/home/22pf2/SWE-Bench_Replication")
BENCH_ENV_PYTHON = ROOT / "bench_env/bin/python"
PAUL_ENV_PYTHON = Path("/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python")
SWEBENCH_CONFIG = REPLICATION_DIR / "mini-SWE-agent/src/minisweagent/config/benchmarks/swebench_backticks.yaml"
GPT_OVERRIDE = REPLICATION_DIR / "config/openai_gpt54mini_override.yaml"
DATASET_PATH = ROOT / "data/samples/pouya_dataset_2026_swebench_style_f2p_p2p/dataset.jsonl"
TEST_FILE_RE = re.compile(r"(?:^|/)tests?[/_]|test_[^/]*\.py$|_test\.py$", re.IGNORECASE)
TEST_DEF_RE = re.compile(r"(?:async\s+)?def\s+(test_\w+)")
CLASS_RE = re.compile(r"class\s+(\w+)")
PYTEST_FLEXIBLE_LOG_PARSER = r'''def parser(log: str) -> dict[str, str]:
    import re

    result: dict[str, str] = {}
    status_re = re.compile(
        r"^(?P<test>\S+::\S+)\s+"
        r"(?P<status>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b"
    )
    summary_re = re.compile(
        r"^(?P<status>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\s+"
        r"(?P<test>\S+::\S+)"
    )

    for raw_line in log.splitlines():
        line = raw_line.strip()
        match = status_re.search(line) or summary_re.search(line)
        if not match:
            continue
        status = match.group("status").upper()
        test = match.group("test")
        if status == "PASSED":
            result[test] = "pass"
        elif status == "SKIPPED":
            result[test] = "skip"
        else:
            result[test] = "fail"
    return result
'''

# Result classifications written to per-instance result.
# setup_failed    — RepoLaunch setup agent failed to install/verify
# organize_missing— setup passed but organize step didn't produce docker_image
# organize_passed — both setup and organize succeeded; docker_image available
# timeout         — subprocess exceeded per-instance timeout
# infra_complex   — timeout on known service-dependency repos (redis/rabbitmq/etc.)
RESULT_SETUP_FAILED    = "setup_failed"
RESULT_ORGANIZE_MISSING = "organize_missing"
RESULT_ORGANIZE_PASSED  = "organize_passed"
RESULT_TIMEOUT          = "timeout"
RESULT_INFRA_COMPLEX    = "infra_complex"

# Repos known to require external services (redis, rabbitmq, etc.) — classify
# timeouts from these as infra_complex rather than setup_failed.
INFRA_COMPLEX_REPOS = {
    "Bogdanp/dramatiq",       # rabbitmq + redis + memcached
}

# Repos proven by the pilot to need service stacks that RepoLaunch does not
# provision in this lightweight GPT-only batch. This is a run selection policy,
# not a dataset collection policy.
SERVICE_HEAVY_REPOS = {
    "Bogdanp/dramatiq",       # rabbitmq + redis + memcached
    "GeoNode/geonode",        # PostgreSQL/PostGIS + Django DB setup
}

# Rows observed in the 20-issue pilot to be unsuitable for the lightweight
# Stage 1+2 batch without repo-specific environment work. They are excluded
# only from deterministic pilot selection so replacements can fill the 20 rows.
DEFAULT_EXCLUDED_INSTANCE_IDS = {
    "NVIDIA-NeMo__RL-1334",                         # huge GPU/uv stack; failed verify
    "apple__coremltools-2532",                      # Rust/toolchain dependency failure
    "aws-powertools__powertools-lambda-python-7028",# Pydantic/FastAPI dep mismatch
    "aws-powertools__powertools-lambda-python-7253",# Poetry install/verify hung in pilot
    "aws-powertools__powertools-lambda-python-7901",# Poetry install hung with no log progress
    "aws-powertools__powertools-lambda-python-7940",# Poetry install hung with no log progress
    "aws-powertools__powertools-lambda-python-7980",# Poetry install hung (CLOSE-WAIT on API socket)
    "aws-powertools__powertools-lambda-python-7083",# Poetry install hung — same repo pattern
    "aws-powertools__powertools-lambda-python-8089",# Poetry install hung — same repo pattern
    "aws-powertools__powertools-lambda-python-8092",# Poetry install hung — same repo pattern
    "beeware__toga-3471",                           # gold F2P fails under warnings=error
    "beeware__toga-4191",                           # unsatisfiable dev/docs deps
    "biolab__orange3-7219",                         # GUI/system deps not provisioned
    "biopython__biopython-5005",                    # targeted tests need missing PDB fixtures
    "dgtlmoon__changedetection.io-3442",            # targeted suite fails app assertions in setup
    "dgtlmoon__changedetection.io-3465",            # gold eval failed: both F2P and P2P tests failed
    "django-import-export__django-import-export-2108",  # RepoLaunch NoneType crash in verify.py
    "GeoNode__geonode-13769",                          # 2116-line patch + 11 F2P + GIS infra (GDAL/PostgreSQL)
    "dlt-hub__dlt-2951",                               # P2P tests need live Databricks catalog credentials
    "dlt-hub__dlt-3048",                               # gold eval failed: F2P tests not collected (test ID mismatch)
    "dlt-hub__dlt-3096",                               # preemptively excluded — same dlt-hub gold eval risk pattern
    # All remaining dlt-hub instances excluded: library mixes local & cloud tests; gold patches change test IDs
    "dlt-hub__dlt-2917", "dlt-hub__dlt-2936", "dlt-hub__dlt-2965",
    "dlt-hub__dlt-3056", "dlt-hub__dlt-3091", "dlt-hub__dlt-3233",
    "dlt-hub__dlt-3322", "dlt-hub__dlt-3431", "dlt-hub__dlt-3601",
    "dlt-hub__dlt-3606", "dlt-hub__dlt-3638", "dlt-hub__dlt-3676",
    "dlt-hub__dlt-3700", "dlt-hub__dlt-3743",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pouya20")


# ── Progress tracking ────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_progress(run_dir: Path, total: int, instance_ids: list[str]) -> dict:
    p = {
        "total": total,
        "done": 0,
        "remaining": total,
        "stage": "init",
        "last_instance_id": None,
        # top-level outcome lists (final, cross-stage)
        "completed_ids": [],
        "failed_ids": [],
        # repolaunch stage
        "repolaunch_passed": [],
        "repolaunch_failed": [],
        "repolaunch_results": {},   # iid → classification string
        # downstream stages
        "validated_ids": [],
        "gold_passed": [],
        "baseline_resolved": [],
        "enhanced_resolved": [],
        "started_at": _now(),
        "updated_at": _now(),
        "all_instance_ids": instance_ids,
    }
    write_progress(run_dir, p)
    return p


def write_progress(run_dir: Path, p: dict, log_msg: str = "") -> None:
    p["updated_at"] = _now()
    (run_dir / "progress.json").write_text(json.dumps(p, indent=2))
    if log_msg:
        with (run_dir / "progress.log").open("a") as f:
            f.write(f"{_now()} {log_msg}\n")
        logger.info(log_msg)


# ── Dataset selection ────────────────────────────────────────────────────────

def select_instances(src: Path, limit: int = 20,
                     excluded_ids: set[str] | None = None) -> list[dict]:
    rows = [json.loads(l) for l in src.open()]
    excluded_ids = excluded_ids or set()
    rows = [r for r in rows if "azure" not in r["repo"].lower()]
    rows = [r for r in rows if r["repo"] not in SERVICE_HEAVY_REPOS]
    rows = [r for r in rows if r["instance_id"] not in excluded_ids]
    detailed = sorted([r for r in rows if r.get("quality_bucket") == "detailed"],
                      key=lambda r: r["instance_id"])
    moderate = sorted([r for r in rows if r.get("quality_bucket") == "moderate"],
                      key=lambda r: r["instance_id"])
    selected: list[dict] = []
    repo_count: dict[str, int] = defaultdict(int)
    for r in detailed + moderate:
        if repo_count[r["repo"]] < 2 and len(selected) < limit:
            selected.append(r)
            repo_count[r["repo"]] += 1
    if len(selected) < limit:
        raise ValueError(
            f"select_instances: only {len(selected)} eligible instances in dataset "
            f"(wanted {limit}). Add fewer exclusions or reduce --limit."
        )
    return selected


def _as_str_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value).strip()] if str(value).strip() else []


def _nodeid_to_file(nodeid: str) -> str:
    return nodeid.split("::", 1)[0].strip()


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _is_test_file(path: str) -> bool:
    return bool(TEST_FILE_RE.search(path))


def _test_node(file_path: str, func_name: str, class_name: str | None) -> str:
    return f"{file_path}::{class_name}::{func_name}" if class_name else f"{file_path}::{func_name}"


def _fetch_base_test_file(instance: dict, file_path: str, cache_dir: Path) -> str:
    """Fetch one base-commit test file for class-qualified pytest node repair."""
    repo = str(instance.get("repo", "")).strip()
    base_commit = str(instance.get("base_commit", "")).strip()
    if not repo or not base_commit or not file_path:
        return ""

    cache_path = cache_dir / repo.replace("/", "__") / base_commit / file_path
    if cache_path.exists():
        return cache_path.read_text(errors="replace")

    url = f"https://raw.githubusercontent.com/{repo}/{base_commit}/{file_path}"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            text = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        logger.warning("Could not fetch %s for %s: %s", file_path, instance.get("instance_id"), exc)
        return ""

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text)
    return text


def _test_class_map(source: str) -> dict[str, str | None]:
    """Map test function names to their pytest class, if any, from Python source."""
    class_stack: list[tuple[int, str]] = []
    result: dict[str, str | None] = {}
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        while class_stack and indent <= class_stack[-1][0]:
            class_stack.pop()
        class_match = CLASS_RE.match(stripped)
        if class_match:
            class_stack.append((indent, class_match.group(1)))
            continue
        test_match = TEST_DEF_RE.match(stripped)
        if test_match:
            result[test_match.group(1)] = class_stack[-1][1] if class_stack else None
    return result


def _derive_test_nodes_from_patch(instance: dict, cache_dir: Path) -> tuple[list[str], list[str]]:
    """Derive class-qualified F2P/P2P pytest nodes from the test patch."""
    test_patch = str(instance.get("test_patch", "") or "")
    if not test_patch:
        return [], []

    fail_to_pass: list[str] = []
    pass_to_pass: list[str] = []
    current_file: str | None = None
    current_class: str | None = None
    class_maps: dict[str, dict[str, str | None]] = {}

    def class_map_for(file_path: str) -> dict[str, str | None]:
        if file_path not in class_maps:
            source = _fetch_base_test_file(instance, file_path, cache_dir)
            class_maps[file_path] = _test_class_map(source)
        return class_maps[file_path]

    for raw_line in test_patch.splitlines():
        if raw_line.startswith("diff --git"):
            current_file = None
            current_class = None
            match = re.search(r" b/(.+)$", raw_line)
            if match and _is_test_file(match.group(1)):
                current_file = match.group(1)
            continue

        if raw_line.startswith("+++ b/"):
            path = raw_line[len("+++ b/") :]
            current_file = path if _is_test_file(path) else None
            current_class = None
            continue

        if not current_file:
            continue

        if raw_line.startswith("@@"):
            tail = raw_line.split("@@", 2)[-1].strip() if raw_line.count("@@") >= 2 else ""
            class_match = CLASS_RE.search(tail)
            test_match = TEST_DEF_RE.search(tail)
            if class_match:
                current_class = class_match.group(1)
            elif test_match:
                current_class = class_map_for(current_file).get(test_match.group(1))
            continue

        if not raw_line or raw_line[0] not in " +":
            continue

        prefix = raw_line[0]
        content = raw_line[1:]
        stripped = content.strip()
        if not stripped:
            continue

        indent = len(content) - len(content.lstrip(" \t"))
        class_match = CLASS_RE.match(stripped)
        if class_match:
            current_class = class_match.group(1)
            continue

        test_match = TEST_DEF_RE.match(stripped)
        if not test_match:
            continue

        func_name = test_match.group(1)
        class_name = current_class if indent > 0 else None
        if prefix == " ":
            class_name = class_map_for(current_file).get(func_name, class_name)
            add_to = pass_to_pass
        else:
            add_to = fail_to_pass
        node = _test_node(current_file, func_name, class_name)
        if node not in add_to:
            add_to.append(node)

    f2p_set = set(fail_to_pass)
    pass_to_pass = [node for node in pass_to_pass if node not in f2p_set]
    return fail_to_pass, pass_to_pass


def repair_test_labels(instance: dict, cache_dir: Path) -> dict:
    """Return instance with exact class-qualified F2P/P2P labels when derivable."""
    old_f2p = _as_str_list(instance.get("FAIL_TO_PASS"))
    old_p2p = _as_str_list(instance.get("PASS_TO_PASS"))
    if any("[" in label for label in old_f2p + old_p2p):
        return instance

    f2p, p2p = _derive_test_nodes_from_patch(instance, cache_dir)
    if not f2p or not p2p:
        return instance
    if f2p == old_f2p and p2p == old_p2p:
        return instance
    repaired = dict(instance)
    repaired["FAIL_TO_PASS"] = f2p
    repaired["PASS_TO_PASS"] = p2p
    repaired["FAIL_TO_PASS_count"] = len(f2p)
    repaired["PASS_TO_PASS_count"] = len(p2p)
    repaired["test_cmds"] = [_runner_aware_pytest_command(f2p + p2p, verbose=False)]
    repaired["log_parser"] = PYTEST_FLEXIBLE_LOG_PARSER
    repaired["pouya_label_repair"] = {
        "method": "test_patch_plus_base_file_class_qualification",
        "old_FAIL_TO_PASS": old_f2p,
        "old_PASS_TO_PASS": old_p2p,
    }
    logger.info(
        "Repaired F2P/P2P labels for %s: F2P %s -> %s; P2P %s -> %s",
        repaired.get("instance_id"), old_f2p, f2p, old_p2p, p2p,
    )
    return repaired


def repair_instances_test_labels(instances: list[dict], run_dir: Path) -> list[dict]:
    cache_dir = run_dir / "base_test_file_cache"
    repaired: list[dict] = []
    for inst in instances:
        row = dict(repair_test_labels(inst, cache_dir))
        eval_cmds = _evaluation_test_cmds(row)
        if eval_cmds:
            row["test_cmds"] = eval_cmds
            row["print_cmds"] = []
            row["log_parser"] = PYTEST_FLEXIBLE_LOG_PARSER
        repaired.append(row)
    return repaired


def _parse_pytest_nodes_from_log(log: str) -> list[str]:
    status_re = re.compile(
        r"^(?P<test>\S+::\S+)\s+"
        r"(?P<status>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b"
    )
    summary_re = re.compile(
        r"^(?P<status>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\s+"
        r"(?P<test>\S+::\S+)"
    )
    result: list[str] = []
    for raw_line in log.splitlines():
        line = raw_line.strip()
        match = status_re.search(line) or summary_re.search(line)
        if not match:
            continue
        node = match.group("test")
        if node not in result:
            result.append(node)
    return result


def _expand_label_from_observed(label: str, observed_nodes: list[str]) -> list[str]:
    matches = [
        node for node in observed_nodes
        if node == label or node.startswith(f"{label}[")
    ]
    return matches or [label]


def repair_parametrized_labels_from_gold_log(instance: dict, log_path: Path) -> dict:
    """Expand unparameterized labels to exact pytest-collected node IDs."""
    if not log_path.exists():
        return instance
    observed_nodes = _parse_pytest_nodes_from_log(log_path.read_text(errors="replace"))
    if not observed_nodes:
        return instance

    old_f2p = _as_str_list(instance.get("FAIL_TO_PASS"))
    old_p2p = _as_str_list(instance.get("PASS_TO_PASS"))
    new_f2p = _unique_preserve_order([
        expanded
        for label in old_f2p
        for expanded in _expand_label_from_observed(label, observed_nodes)
    ])
    new_p2p = _unique_preserve_order([
        expanded
        for label in old_p2p
        for expanded in _expand_label_from_observed(label, observed_nodes)
    ])

    if new_f2p == old_f2p and new_p2p == old_p2p:
        return instance

    repaired = dict(instance)
    repaired["FAIL_TO_PASS"] = new_f2p
    repaired["PASS_TO_PASS"] = new_p2p
    repaired["FAIL_TO_PASS_count"] = len(new_f2p)
    repaired["PASS_TO_PASS_count"] = len(new_p2p)
    repaired["test_cmds"] = [_runner_aware_pytest_command(new_f2p + new_p2p, verbose=False)]
    repaired["log_parser"] = PYTEST_FLEXIBLE_LOG_PARSER
    repaired["pouya_param_label_repair"] = {
        "method": "expand_unparametrized_labels_from_gold_pytest_log",
        "old_FAIL_TO_PASS": old_f2p,
        "old_PASS_TO_PASS": old_p2p,
    }
    logger.info(
        "Expanded parametrized F2P/P2P labels for %s: F2P %s -> %s; P2P %s -> %s",
        repaired.get("instance_id"), old_f2p, new_f2p, old_p2p, new_p2p,
    )
    return repaired


def _runner_aware_pytest_command(targets: list[str], *, verbose: bool,
                                 marker_expr: str | None = None) -> str:
    """Build a pytest command that works in uv and non-uv containers."""
    clean_targets = _unique_preserve_order([t for t in targets if t])
    flags = "-v -rA" if verbose else "-rA"
    if marker_expr is not None:
        flags = f"{flags} -m {shlex.quote(marker_expr)}"
    args = " ".join(shlex.quote(t) for t in clean_targets)
    pytest_args = f"{flags} {args}".strip()
    script = (
        "if command -v uv >/dev/null 2>&1 && [ -f pyproject.toml ]; then "
        f"uv run python -m pytest {pytest_args}; "
        "elif command -v pytest >/dev/null 2>&1; then "
        f"pytest {pytest_args}; "
        "else "
        f"python -m pytest {pytest_args}; "
        "fi"
    )
    return f"bash -lc {shlex.quote(script)}"


def _evaluation_test_cmds(instance: dict) -> list[str]:
    """Exact benchmark F2P/P2P command used after the test patch is applied."""
    targets = (
        _as_str_list(instance.get("FAIL_TO_PASS"))
        + _as_str_list(instance.get("PASS_TO_PASS"))
    )
    if targets:
        # Explicit benchmark node IDs should not be filtered out by repository
        # addopts such as "-m 'not slow'"; an empty marker expression overrides
        # those filters while preserving the exact F2P/P2P targets.
        return [_runner_aware_pytest_command(targets, verbose=False, marker_expr="")]
    return _as_str_list(instance.get("test_cmds"))


def _inject_hints(instance: dict) -> dict:
    """
    Return a copy of the instance with Paul setup-smoke fields from PASS_TO_PASS.
    This mirrors the paul_exp_pouya2 dataset pattern where `hints` told the LLM
    exactly which pytest command to run instead of discovering a broad test suite.
    If hints already exist, preserve and append.

    RepoLaunch runs on the base checkout, before the benchmark test patch is
    applied. FAIL_TO_PASS tests may be introduced by that test patch and can be
    absent at setup time. Some derived PASS_TO_PASS node IDs can also be renamed
    by the benchmark test patch, so the setup smoke uses their test files. The
    exact original F2P/P2P command is restored before validation/evaluation.
    """
    inst = dict(instance)
    pass_to_pass = _as_str_list(inst.get("PASS_TO_PASS"))
    if not pass_to_pass:
        return inst

    smoke_targets = _unique_preserve_order(
        [_nodeid_to_file(target) for target in pass_to_pass]
    )
    if not smoke_targets:
        return inst

    cmd_str = _runner_aware_pytest_command(smoke_targets, verbose=True)

    if inst.get("test_cmds"):
        inst["pouya_original_test_cmds"] = inst["test_cmds"]
    inst["pouya_eval_test_cmds"] = _evaluation_test_cmds(instance)
    inst["test_cmds"] = [cmd_str]
    inst["paul_validation_test_cmds"] = [cmd_str]
    inst["paul_organize_test_cmds"] = [cmd_str]

    strict_hint = (
        "STRICT LAUNCH SMOKE VALIDATION: run exactly this P2P file-level command "
        "after installing test dependencies, and do not replace it with a "
        f"package-wide or repo-wide pytest command: {cmd_str}. "
        "Use only PASS_TO_PASS-derived files for RepoLaunch setup/organize because "
        "FAIL_TO_PASS tests may require the benchmark test patch, and some exact "
        "PASS_TO_PASS node IDs may be renamed by that patch. The exact original "
        "F2P/P2P command is preserved for validation/evaluation after the benchmark "
        "test patch is applied."
    )

    existing = inst.get("hints", "")
    inst["hints"] = (existing + "\n" + strict_hint).strip() if existing else strict_hint
    return inst


# ── subprocess helper ────────────────────────────────────────────────────────

def run_subprocess(cmd: list, *, env: dict, log_path: Path | None = None,
                   timeout: int | None = None) -> int:
    logger.info("CMD: %s", " ".join(str(c) for c in cmd))
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a") as lf:
            result = subprocess.run(cmd, env=env, stdout=lf,
                                    stderr=subprocess.STDOUT, timeout=timeout)
    else:
        result = subprocess.run(cmd, env=env, timeout=timeout)
    if result.returncode != 0:
        logger.warning("Subprocess exited rc=%d: %s", result.returncode,
                       " ".join(str(c) for c in cmd[:3]))
    return result.returncode


def _make_env(api_key: str) -> dict:
    e = os.environ.copy()
    e["OPENAI_API_KEY"] = api_key
    e["USE_OLLAMA"] = "0"
    e["OPENAI_COMPAT_BASE_URL"] = "https://api.openai.com/v1"
    e["OPENAI_COMPAT_API_KEY"] = api_key
    e["OPENAI_COMPAT_MODEL"] = "gpt-5.4-mini"
    e["TAVILY_API_KEY"] = "tvly-dummy-no-tavily-calls"
    return e


def _load_openai_api_key() -> str:
    """Load the OpenAI key without requiring callers to put it in argv."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if api_key:
        return api_key

    key_file = os.environ.get("OPENAI_API_KEY_FILE", "").strip()
    if key_file:
        path = Path(key_file).expanduser()
        if path.exists():
            raw = path.read_text().strip()
            if raw.startswith("{"):
                try:
                    found = _find_openai_key(json.loads(raw))
                    if found:
                        return found
                    return ""
                except json.JSONDecodeError:
                    pass
            return raw

    return ""


def _find_openai_key(value) -> str:
    """Return the first key-like string found in a nested JSON value."""
    if isinstance(value, str):
        match = re.search(r"sk-[A-Za-z0-9_-]+", value)
        if match:
            return match.group(0)
    if isinstance(value, dict):
        for item in value.values():
            found = _find_openai_key(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_openai_key(item)
            if found:
                return found
    return ""


# ── Stage 1: RepoLaunch ──────────────────────────────────────────────────────

def _classify_repolaunch_result(iid: str, inst_workspace: Path,
                                 timed_out: bool) -> str:
    """
    Determine per-instance outcome after RepoLaunch completes or times out.
    Priority: timeout (infra_complex) > organize_passed > organize_missing > setup_failed
    """
    if timed_out:
        repo = iid.rsplit("__", 1)[0].replace("__", "/")
        if repo in INFRA_COMPLEX_REPOS:
            return RESULT_INFRA_COMPLEX
        return RESULT_TIMEOUT

    organize_jsonl = inst_workspace / "organize.jsonl"
    if organize_jsonl.exists():
        entries = [json.loads(l) for l in organize_jsonl.open() if l.strip()]
        if any(_organize_entry_is_complete(iid, e) for e in entries):
            return RESULT_ORGANIZE_PASSED

    setup_jsonl = inst_workspace / "setup.jsonl"
    if setup_jsonl.exists():
        entries = [json.loads(l) for l in setup_jsonl.open() if l.strip()]
        if any(e.get("instance_id") == iid for e in entries):
            return RESULT_ORGANIZE_MISSING   # setup OK but organize incomplete

    return RESULT_SETUP_FAILED


def _organize_entry_is_complete(iid: str, entry: dict) -> bool:
    """Return True if organize output has the fields needed downstream."""
    return (
        entry.get("instance_id") == iid
        and bool(entry.get("docker_image"))
        and bool(entry.get("test_cmds"))
        and bool(entry.get("log_parser"))
    )


def _read_organize_instance(iid: str, inst_workspace: Path) -> dict | None:
    """Return the complete organize.jsonl entry for iid, else None."""
    organize_jsonl = inst_workspace / "organize.jsonl"
    if not organize_jsonl.exists():
        return None
    for line in organize_jsonl.open():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
            if _organize_entry_is_complete(iid, e):
                return e
        except json.JSONDecodeError:
            continue
    return None


def run_repolaunch(run_dir: Path, instances: list[dict], launch_config: Path,
                   api_key: str, progress: dict, max_issue_workers: int = 1,
                   instance_timeout: int = 2400) -> list[dict]:
    """
    Run Paul/RepoLaunch setup+organize per instance.

    Key behaviours vs v1:
    - Injects strict hints and Paul fields from PASS_TO_PASS → targeted verify/organize tests
    - Sets disable_timemachine=true → no pip proxy timeouts on host.docker.internal
    - Batch-level per-instance timeout guards against wrapper stalls
    - Success requires organize.jsonl with docker_image (not just setup.jsonl)
    - Per-instance result classified and written to progress
    """
    progress["stage"] = "repolaunch"
    write_progress(run_dir, progress, "=== STAGE 1: Paul/RepoLaunch (GPT-5.4-mini) ===")

    workspace = run_dir / "repolaunch_workspace"
    workspace.mkdir(exist_ok=True)

    # Write dataset with hints and Paul target fields from base-checkout PASS_TO_PASS tests
    rl_dataset = workspace / "rl_selected_20.jsonl"
    with rl_dataset.open("w") as f:
        for r in instances:
            f.write(json.dumps(_inject_hints(r)) + "\n")
    logger.info("Wrote dataset with hints → %s", rl_dataset)

    env = _make_env(api_key)

    base_config = json.loads(launch_config.read_text())
    # Always disable timemachine for GPT runs (no host.docker.internal proxy)
    base_config["disable_timemachine"] = True
    base_config["upstream_path"] = str(ROOT / "SWE-bench-Live-Collection/launch")

    passed: list[dict] = []
    cached_passed_path = run_dir / "repolaunch_passed.jsonl"
    if cached_passed_path.exists():
        selected_ids = {r["instance_id"] for r in instances}
        for line in cached_passed_path.open():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("instance_id") in selected_ids:
                passed.append(row)

    total = len(instances)
    already_done = set(progress.get("repolaunch_passed", []) +
                       progress.get("repolaunch_failed", []))
    progress_lock = threading.Lock()

    def run_one(i: int, inst: dict) -> dict:
        iid = inst["instance_id"]
        inst_workspace = workspace / iid
        inst_log = workspace / f"{iid}.repolaunch.log"
        write_progress(run_dir, progress, f"[{i}/{total}] RepoLaunch start: {iid}")

        inst_config = dict(base_config)
        inst_config["dataset"] = str(rl_dataset)
        inst_config["workspace_root"] = str(inst_workspace)
        inst_config["instance_id"] = iid

        inst_cfg_path = workspace / f"{iid}_launch_config.json"
        inst_cfg_path.write_text(json.dumps(inst_config, indent=2))

        cmd = [str(PAUL_ENV_PYTHON), "-m", "paul.run", str(inst_cfg_path)]

        timed_out = False
        error = ""
        try:
            # RepoLaunch's cmd_timeout controls in-container commands, but some
            # wrappers can still stall. Keep a batch-level guard per instance.
            rc = run_subprocess(cmd, env=env, log_path=inst_log, timeout=instance_timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            rc = -1
        except Exception as exc:
            error = str(exc)
            rc = -1

        classification = _classify_repolaunch_result(iid, inst_workspace, timed_out)

        merged = None
        if classification == RESULT_ORGANIZE_PASSED:
            organize_entry = _read_organize_instance(iid, inst_workspace)
            # Use the organize entry (has docker_image, test_cmds, log_parser)
            # but merge back the original dataset fields (patch, FAIL_TO_PASS, etc.)
            merged = dict(inst)
            if organize_entry:
                merged.update(organize_entry)
            # Paul setup/organize uses a base-checkout smoke command. Evaluation
            # must run the original exact F2P/P2P target command after applying
            # the benchmark test patch, so do not leak the smoke command into
            # validation/gold evaluation.
            eval_cmds = _evaluation_test_cmds(inst)
            if eval_cmds:
                merged["test_cmds"] = eval_cmds
                merged["print_cmds"] = []
        return {
            "index": i,
            "instance": inst,
            "instance_id": iid,
            "classification": classification,
            "merged": merged,
            "timed_out": timed_out,
            "error": error,
            "log": inst_log,
        }

    pending: list[tuple[int, dict]] = []
    skipped = 0
    for i, inst in enumerate(instances, 1):
        iid = inst["instance_id"]
        if iid in already_done:
            skipped += 1
            write_progress(run_dir, progress, f"[{i}/{total}] SKIP (already done): {iid}")
        else:
            pending.append((i, inst))

    workers = max(1, min(max_issue_workers, len(pending) or 1))
    if pending:
        write_progress(
            run_dir,
            progress,
            f"RepoLaunch issue workers: {workers} for {len(pending)} pending instances",
        )

    completed_count = skipped
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_index: dict[concurrent.futures.Future, int] = {}
        for i, inst in pending:
            write_progress(run_dir, progress, f"[{i}/{total}] RepoLaunch queued: {inst['instance_id']}")
            future_to_index[executor.submit(run_one, i, inst)] = i

        for future in concurrent.futures.as_completed(future_to_index):
            result = future.result()
            iid = result["instance_id"]
            classification = result["classification"]
            completed_count += 1

            with progress_lock:
                progress["repolaunch_results"][iid] = classification

                if result.get("timed_out"):
                    write_progress(run_dir, progress, f"  TIMEOUT (>2h): {iid}")
                if result.get("error"):
                    write_progress(run_dir, progress, f"  ERROR: {iid}: {result['error']}")

                if classification == RESULT_ORGANIZE_PASSED:
                    merged = result["merged"]
                    passed.append(merged)
                    progress["repolaunch_passed"].append(iid)
                    write_progress(
                        run_dir,
                        progress,
                        f"  PASS [{classification}]: {iid}  "
                        f"docker_image={merged.get('docker_image','?')}",
                    )
                else:
                    progress["repolaunch_failed"].append(iid)
                    failed_ids = progress.setdefault("failed_ids", [])
                    if iid not in failed_ids:
                        failed_ids.append(iid)
                    inst_log = result["log"]
                    write_progress(
                        run_dir,
                        progress,
                        f"  FAIL [{classification}]: {iid} (see {inst_log.name})",
                    )

                progress["last_instance_id"] = iid
                progress["done"] = completed_count
                progress["remaining"] = total - completed_count
                write_progress(run_dir, progress)

    instance_order = {inst["instance_id"]: i for i, inst in enumerate(instances)}
    passed.sort(key=lambda row: instance_order.get(row["instance_id"], 10**9))

    n_passed = len(passed)
    n_failed = len(progress["repolaunch_failed"])
    write_progress(run_dir, progress,
                   f"RepoLaunch complete: {n_passed}/{total} passed, {n_failed} failed")
    # Summary of classifications
    for cls in [RESULT_ORGANIZE_PASSED, RESULT_ORGANIZE_MISSING,
                RESULT_SETUP_FAILED, RESULT_TIMEOUT, RESULT_INFRA_COMPLEX]:
        ids = [k for k, v in progress["repolaunch_results"].items() if v == cls]
        if ids:
            write_progress(run_dir, progress,
                           f"  {cls}: {len(ids)} — {', '.join(ids)}")
    return passed


# ── Stage 2: Gold evaluation → validated_instances.jsonl ────────────────────

def run_gold_eval(run_dir: Path, instances: list[dict], api_key: str,
                  progress: dict, workers: int = 2) -> list[dict]:
    """Apply gold patch; keep instances where F2P tests flip."""
    if not instances:
        write_progress(run_dir, progress, "SKIP gold_eval: no RepoLaunch survivors")
        return []

    progress["stage"] = "gold_eval"
    write_progress(run_dir, progress, "=== STAGE 2: Gold evaluation ===")

    gold_dir = run_dir / "gold_eval"
    gold_dir.mkdir(exist_ok=True)

    subset_path = run_dir / "repolaunch_passed.jsonl"
    with subset_path.open("w") as f:
        for r in instances:
            f.write(json.dumps(r) + "\n")

    instance_ids = [r["instance_id"] for r in instances]
    env = _make_env(api_key)

    cmd = [
        str(PAUL_ENV_PYTHON), str(EVAL_SCRIPT),
        "--dataset", str(subset_path),
        "--patch_dir", "gold",
        "--platform", "linux",
        "--workers", str(workers),
        "--output_dir", str(gold_dir),
        "--overwrite", "1",
        "--instance_ids", *instance_ids,
    ]

    write_progress(run_dir, progress,
                   f"Running gold eval on {len(instances)} instances…")
    try:
        rc = run_subprocess(cmd, env=env, log_path=gold_dir / "gold_eval.log",
                            timeout=3600)
    except subprocess.TimeoutExpired:
        write_progress(run_dir, progress, "Gold eval TIMEOUT")

    results_file = gold_dir / "gold_patch_evaluated_instances.jsonl"
    validated: list[dict] = []
    if results_file.exists():
        validated = [json.loads(l) for l in results_file.open() if l.strip()]

    validated_ids = {r["instance_id"] for r in validated}
    failed_after_first_eval = [
        r for r in instances if r["instance_id"] not in validated_ids
    ]
    repaired_failed: list[dict] = []
    for inst in failed_after_first_eval:
        iid = inst["instance_id"]
        repaired = repair_parametrized_labels_from_gold_log(
            inst, gold_dir / iid / "post_patch_log.txt"
        )
        if repaired != inst:
            repaired_failed.append(repaired)

    if repaired_failed:
        repair_dir = run_dir / "gold_eval_param_repair"
        repair_dir.mkdir(exist_ok=True)
        repair_subset = run_dir / "repolaunch_passed_param_repaired.jsonl"
        repaired_by_id = {r["instance_id"]: r for r in repaired_failed}
        repaired_instances = [
            repaired_by_id.get(r["instance_id"], r)
            for r in instances
        ]
        with repair_subset.open("w") as f:
            for r in repaired_instances:
                f.write(json.dumps(r) + "\n")

        repaired_ids = [r["instance_id"] for r in repaired_failed]
        write_progress(
            run_dir, progress,
            f"Rerunning gold eval for parametrized label repairs: {', '.join(repaired_ids)}",
        )
        repair_cmd = [
            str(PAUL_ENV_PYTHON), str(EVAL_SCRIPT),
            "--dataset", str(repair_subset),
            "--patch_dir", "gold",
            "--platform", "linux",
            "--workers", str(workers),
            "--output_dir", str(repair_dir),
            "--overwrite", "1",
            "--instance_ids", *repaired_ids,
        ]
        try:
            run_subprocess(
                repair_cmd,
                env=env,
                log_path=repair_dir / "gold_eval.log",
                timeout=3600,
            )
        except subprocess.TimeoutExpired:
            write_progress(run_dir, progress, "Gold eval parametrized repair TIMEOUT")

        repair_results = repair_dir / "gold_patch_evaluated_instances.jsonl"
        if repair_results.exists():
            repaired_validated = [
                json.loads(l) for l in repair_results.open() if l.strip()
            ]
            validated_by_id = {r["instance_id"]: r for r in validated}
            for repaired in repaired_validated:
                validated_by_id[repaired["instance_id"]] = repaired
            validated = list(validated_by_id.values())
            instances = repaired_instances

    results_summary = {
        "submitted": len(instances),
        "gold_passed": len(validated),
        "gold_failed": len(instances) - len(validated),
        "passed_ids": [r["instance_id"] for r in validated],
        "failed_ids": [r["instance_id"] for r in instances
                       if r["instance_id"] not in {v["instance_id"] for v in validated}],
    }
    (gold_dir / "results.json").write_text(json.dumps(results_summary, indent=2))

    validated_path = run_dir / "validated_instances.jsonl"
    with validated_path.open("w") as f:
        for r in validated:
            f.write(json.dumps(r) + "\n")

    progress["validated_ids"] = [r["instance_id"] for r in validated]
    progress["gold_passed"] = [r["instance_id"] for r in validated]
    write_progress(run_dir, progress,
                   f"Gold eval: {len(validated)}/{len(instances)} validated")
    return validated


# ── Stage 3: mini-SWE-agent solver ──────────────────────────────────────────

def _solver_ready_instance(inst: dict) -> dict:
    """Return instance with image_name forced to our RepoLaunch docker_image.

    The source dataset has image_name=starryzhang/sweb.eval.x86_64.* (original
    SWE-bench images).  mini-SWE-agent checks image_name before docker_image, so
    without this override it ignores our custom RepoLaunch-built image entirely.
    """
    row = dict(inst)
    if row.get("docker_image"):
        row["image_name"] = row["docker_image"]
    return row


def _issue_text(row: dict) -> str:
    return (row.get("problem_statement") or row.get("body") or "").strip()


def _metadata_error(metadata: dict) -> str:
    if not isinstance(metadata, dict):
        return ""
    if metadata.get("enhancer_type") == "error":
        return str(metadata.get("error") or "enhancer returned error metadata")
    if metadata.get("error"):
        return str(metadata["error"])
    return ""


def _write_solver_instances(solver_dir: Path, instances: list[dict]) -> None:
    with (solver_dir / "solver_instances.jsonl").open("w") as f:
        for row in instances:
            f.write(json.dumps(row) + "\n")


def _filter_valid_enhancements(
    run_dir: Path,
    candidate_rows: list[dict],
    original_instances: list[dict],
    progress: dict,
    enhancer_id: str,
    source: str,
) -> list[dict]:
    """Drop rows that did not receive a real changed enhancement."""
    original_by_id = {r["instance_id"]: r for r in original_instances}
    valid: list[dict] = []
    failures: list[dict] = []

    for row in candidate_rows:
        iid = row.get("instance_id", "<missing-instance-id>")
        original = original_by_id.get(iid, {})
        original_text = _issue_text(original)
        enhanced_text = _issue_text(row)
        metadata = row.get("enhancement_metadata") or {}
        error = _metadata_error(metadata)

        reason = ""
        if not enhanced_text:
            reason = error or "empty enhanced problem_statement"
        elif enhanced_text == original_text:
            reason = error or "enhanced problem_statement is unchanged from baseline"
        elif error:
            reason = error

        if reason:
            failures.append(
                {
                    "instance_id": iid,
                    "reason": reason,
                    "source": source,
                    "metadata": metadata,
                }
            )
        else:
            valid.append(row)

    failure_path = run_dir / f"{enhancer_id}_enhancement_failures.json"
    failure_path.write_text(json.dumps(failures, indent=2))
    progress.setdefault("enhancement_failures", {})[enhancer_id] = [
        f["instance_id"] for f in failures
    ]
    write_progress(
        run_dir,
        progress,
        f"Enhancement validation for {enhancer_id}: "
        f"{len(valid)}/{len(candidate_rows)} valid, {len(failures)} failed",
    )
    if failures:
        write_progress(
            run_dir,
            progress,
            f"  Enhancement failures written to {failure_path}",
        )
    return valid


def run_solver(run_dir: Path, instances: list[dict], output_subdir: str,
               api_key: str, progress: dict, enhanced: bool = False,
               enhancer_id: str = "llm_append_analysis",
               solver_id: str = "mini_swe_agent",
               prebuilt_dataset: Path | None = None) -> Path:
    """Run solver (mini_swe_agent or openhands) for baseline or enhanced condition.

    Args:
        prebuilt_dataset: If set, load this JSONL as the solver input instead of
            running the enhancer.  Useful when reusing enhanced datasets from a
            previous run (saves re-running expensive enhancement).
    """
    label = "enhanced" if enhanced else "baseline"
    progress["stage"] = f"solver_{label}"

    solver_dir = run_dir / output_subdir
    solver_dir.mkdir(exist_ok=True)

    write_progress(run_dir, progress, f"=== STAGE: {solver_id} {label} ===")

    if not instances:
        write_progress(run_dir, progress,
                       f"SKIP {output_subdir}: no validated instances")
        (solver_dir / "preds.json").write_text("{}")
        return solver_dir

    # ----- Build the dataset to pass to the solver -----
    if prebuilt_dataset is not None:
        # Reuse an existing enhanced_dataset.jsonl (no enhancer invocation needed)
        write_progress(run_dir, progress,
                       f"Loading prebuilt dataset from {prebuilt_dataset.name}…")
        solver_instances = [json.loads(l) for l in prebuilt_dataset.open() if l.strip()]
        if enhanced:
            solver_instances = _filter_valid_enhancements(
                run_dir,
                solver_instances,
                instances,
                progress,
                enhancer_id,
                source=str(prebuilt_dataset),
            )
        solver_dataset = run_dir / f"solver_{label}_dataset.jsonl"
        with solver_dataset.open("w") as f:
            for r in solver_instances:
                f.write(json.dumps(_solver_ready_instance(r)) + "\n")
    elif enhanced:
        enhanced_instances = _build_enhanced_dataset(run_dir, instances, api_key, progress,
                                                     enhancer_id=enhancer_id)
        solver_instances = enhanced_instances
        solver_dataset = run_dir / "solver_enhanced_dataset.jsonl"
        with solver_dataset.open("w") as f:
            for r in enhanced_instances:
                f.write(json.dumps(_solver_ready_instance(r)) + "\n")
    else:
        solver_instances = instances
        solver_dataset = run_dir / "solver_baseline_dataset.jsonl"
        with solver_dataset.open("w") as f:
            for r in instances:
                f.write(json.dumps(_solver_ready_instance(r)) + "\n")

    _write_solver_instances(solver_dir, solver_instances)
    if not solver_instances:
        write_progress(
            run_dir,
            progress,
            f"SKIP {output_subdir}: no valid {label} instances after enhancement validation",
        )
        (solver_dir / "preds.json").write_text("{}")
        return solver_dir

    # ----- Dispatch to chosen solver -----
    if solver_id == "openhands":
        _run_openhands_solver(
            run_dir, solver_instances, solver_dir, api_key, progress, label
        )
    elif solver_id == "swe_agent":
        _run_sweagent_solver(
            run_dir, solver_instances, solver_dir, api_key, progress, label
        )
    else:
        _run_miniswe_solver(
            run_dir, solver_dataset, solver_dir, api_key, progress, label
        )

    write_progress(run_dir, progress,
                   f"{label} solver done (preds → {solver_dir}/preds.json)")
    return solver_dir


def _run_miniswe_solver(run_dir: Path, solver_dataset: Path, solver_dir: Path,
                        api_key: str, progress: dict, label: str) -> None:
    env = _make_env(api_key)
    cmd = [
        str(BENCH_ENV_PYTHON), str(SOLVER_SCRIPT),
        "--dataset-jsonl", str(solver_dataset),
        "-c", str(SWEBENCH_CONFIG),
        "-c", str(GPT_OVERRIDE),
        "--output", str(solver_dir),
        "--workers", "2",
    ]
    write_progress(run_dir, progress,
                   f"Running mini-SWE-agent {label}…")
    try:
        run_subprocess(cmd, env=env,
                       log_path=solver_dir / "minisweagent.log",
                       timeout=7200)
    except subprocess.TimeoutExpired:
        write_progress(run_dir, progress,
                       f"{label} solver TIMEOUT (partial results may exist)")


def _run_openhands_solver(run_dir: Path, instances: list[dict], solver_dir: Path,
                          api_key: str, progress: dict, label: str) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from solvers.openhands_solver import run_batch as oh_run_batch

    write_progress(run_dir, progress,
                   f"Running OpenHands solver {label} on {len(instances)} instances…")
    oh_run_batch(
        instances=instances,
        api_key=api_key,
        work_dir=solver_dir / "oh_workdirs",
        preds_out=solver_dir / "preds.json",
        model=os.environ.get("OH_SOLVER_MODEL", "gpt-5.4-mini"),
        base_url=os.environ.get("OH_SOLVER_BASE_URL", "https://api.openai.com/v1"),
        max_iter=int(os.environ.get("OH_SOLVER_MAX_ITER", "30")),
        timeout=int(os.environ.get("OH_SOLVER_TIMEOUT", "1800")),
        workers=2,
    )


def _run_sweagent_solver(run_dir: Path, instances: list[dict], solver_dir: Path,
                         api_key: str, progress: dict, label: str) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from solvers.swe_agent_solver import run_batch as swea_run_batch

    write_progress(run_dir, progress,
                   f"Running SWE-agent solver {label} on {len(instances)} instances…")
    swea_run_batch(
        instances=instances,
        api_key=api_key,
        work_dir=solver_dir / "sweagent_workdirs",
        preds_out=solver_dir / "preds.json",
        model=os.environ.get("SWEA_SOLVER_MODEL", "gpt-5.4-mini"),
        base_url=os.environ.get("SWEA_SOLVER_BASE_URL", "https://api.openai.com/v1"),
        max_steps=int(os.environ.get("SWEA_SOLVER_MAX_STEPS", "30")),
        workers=2,
        timeout=int(os.environ.get("SWEA_SOLVER_TIMEOUT", "7200")),
    )


_ENHANCER_ENV: dict[str, dict[str, str]] = {
    "llm_append_analysis": {
        "USE_OLLAMA": "0",
        "OPENAI_COMPAT_BASE_URL": "https://api.openai.com/v1",
        "OPENAI_COMPAT_MODEL": "gpt-5.4-mini",
        "LLM_APPEND_MAX_BODY_CHARS": "80000",
        "__key__": "OPENAI_COMPAT_API_KEY",
    },
    "aider": {
        "AIDER_MODEL": "openai/gpt-5.4-mini",
        "AIDER_API_BASE": "https://api.openai.com/v1",
        "__key__": "AIDER_API_KEY",
    },
    "trae": {
        "TRAE_BASE_URL": "https://api.openai.com/v1",
        "TRAE_MODEL": "gpt-5.4-mini",
        "__key__": "TRAE_API_KEY",
    },
    "openhands": {
        "OPENHANDS_BASE_URL": "https://api.openai.com/v1",
        "OPENHANDS_MODEL": "gpt-5.4-mini",
        "__key__": "OPENHANDS_API_KEY",
    },
    "mini_swe_agent": {
        "MINI_BASE_URL": "https://api.openai.com/v1",
        "MINI_MODEL": "gpt-5.4-mini",
        "__key__": "MINI_API_KEY",
    },
    "swe_agent": {
        "SWEAGENT_BASE_URL": "https://api.openai.com/v1",
        "SWEAGENT_MODEL": "gpt-5.4-mini",
        "__key__": "SWEAGENT_API_KEY",
    },
}


def _build_enhanced_dataset(run_dir: Path, instances: list[dict],
                             api_key: str, progress: dict,
                             enhancer_id: str = "llm_append_analysis") -> list[dict]:
    write_progress(run_dir, progress, f"Running {enhancer_id} enhancer…")

    env_spec = _ENHANCER_ENV.get(enhancer_id, _ENHANCER_ENV["llm_append_analysis"])
    key_var = env_spec.get("__key__", "OPENAI_COMPAT_API_KEY")
    env_patch = {k: v for k, v in env_spec.items() if k != "__key__"}
    env_patch[key_var] = api_key

    for k, v in env_patch.items():
        os.environ[k] = v

    sys.path.insert(0, str(ROOT))
    try:
        from src.enhancers.dispatcher import get_enhancer
        enhancer = get_enhancer(enhancer_id)
        if enhancer is None:
            raise RuntimeError(f"{enhancer_id} enhancer is not registered")
    except Exception as exc:
        write_progress(run_dir, progress,
                       f"  WARN: enhancer import failed ({exc}); no enhanced rows will be run")
        failed_rows = []
        for inst in instances:
            row = dict(inst)
            row["enhancement_metadata"] = {
                "enhancer_type": "error",
                "agent_id": enhancer_id,
                "error": f"enhancer import failed: {exc}",
            }
            failed_rows.append(row)
        return _filter_valid_enhancements(
            run_dir,
            failed_rows,
            instances,
            progress,
            enhancer_id,
            source="enhancer_import",
        )

    candidates: list[dict] = []
    for inst in instances:
        try:
            result = enhancer(inst)
            enhanced_inst = dict(inst)
            enhanced_body = result.get("enhanced_body") if isinstance(result, dict) else None
            if enhanced_body:
                enhanced_inst["problem_statement"] = enhanced_body
                enhanced_inst["enhanced_title"] = result.get("enhanced_title")
                enhanced_inst["enhancement_metadata"] = result.get("enhancement_metadata", {})
            else:
                enhanced_inst.setdefault("enhancement_metadata", {})
                enhanced_inst["enhancement_metadata"]["enhancer_type"] = "error"
                enhanced_inst["enhancement_metadata"]["agent_id"] = enhancer_id
                enhanced_inst["enhancement_metadata"]["error"] = "enhancer returned no enhanced_body"
            candidates.append(enhanced_inst)
        except Exception as exc:
            write_progress(run_dir, progress,
                           f"  WARN: enhance failed {inst['instance_id']}: {exc}")
            row = dict(inst)
            row["enhancement_metadata"] = {
                "enhancer_type": "error",
                "agent_id": enhancer_id,
                "error": f"per-instance enhancement exception: {exc}",
            }
            candidates.append(row)

    enhanced = _filter_valid_enhancements(
        run_dir,
        candidates,
        instances,
        progress,
        enhancer_id,
        source="enhancer_run",
    )
    write_progress(
        run_dir,
        progress,
        f"Enhancement done: {len(enhanced)}/{len(instances)} valid instances",
    )
    return enhanced


# ── Stage 4: Evaluate solver predictions ────────────────────────────────────

def run_solver_eval(run_dir: Path, instances: list[dict], solver_dir: Path,
                    eval_subdir: str, api_key: str, progress: dict) -> dict:
    progress["stage"] = f"eval_{eval_subdir}"
    write_progress(run_dir, progress, f"=== STAGE: Evaluation ({eval_subdir}) ===")

    eval_dir = run_dir / eval_subdir
    eval_dir.mkdir(exist_ok=True)

    preds_file = solver_dir / "preds.json"
    solver_instances_file = solver_dir / "solver_instances.jsonl"
    if solver_instances_file.exists():
        instances = [json.loads(l) for l in solver_instances_file.open() if l.strip()]

    if not preds_file.exists() or not instances:
        write_progress(run_dir, progress,
                       f"SKIP eval_{eval_subdir}: no preds or instances")
        result = {"resolved": 0, "total": 0, "resolved_ids": [], "failed_ids": []}
        (eval_dir / "results.json").write_text(json.dumps(result, indent=2))
        return result

    subset_path = run_dir / "validated_instances.jsonl"
    instance_ids = [r["instance_id"] for r in instances]

    # Skip re-evaluation if all per-instance report.json files already exist
    existing_reports = {p.parent.name for p in eval_dir.glob("*/report.json")}
    skip_eval = existing_reports >= set(instance_ids)
    if skip_eval:
        write_progress(run_dir, progress,
                       f"Reusing cached {eval_subdir} results ({len(instance_ids)} reports found)")

    env = _make_env(api_key)

    cmd = [
        str(PAUL_ENV_PYTHON), str(EVAL_SCRIPT),
        "--dataset", str(subset_path),
        "--patch_dir", str(preds_file),
        "--platform", "linux",
        "--workers", "2",
        "--output_dir", str(eval_dir),
        "--overwrite", "1",
        "--instance_ids", *instance_ids,
    ]

    if not skip_eval:
        write_progress(run_dir, progress, f"Evaluating {len(instance_ids)} instances…")
        try:
            rc = run_subprocess(cmd, env=env, log_path=eval_dir / "eval.log",
                                timeout=3600)
        except subprocess.TimeoutExpired:
            write_progress(run_dir, progress, f"eval_{eval_subdir} TIMEOUT")

    resolved_ids: list[str] = []
    failed_ids: list[str] = []
    for iid in instance_ids:
        result_file = eval_dir / iid / "report.json"
        if result_file.exists():
            try:
                r = json.loads(result_file.read_text())
                if r.get("resolved"):
                    resolved_ids.append(iid)
                else:
                    failed_ids.append(iid)
            except Exception:
                failed_ids.append(iid)
        else:
            failed_ids.append(iid)

    result = {
        "resolved": len(resolved_ids),
        "total": len(instance_ids),
        "resolved_ids": resolved_ids,
        "failed_ids": failed_ids,
    }
    (eval_dir / "results.json").write_text(json.dumps(result, indent=2))
    write_progress(run_dir, progress,
                   f"{eval_subdir}: {len(resolved_ids)}/{len(instance_ids)} resolved")
    return result


# ── Final summary ────────────────────────────────────────────────────────────

def write_summary(run_dir: Path, instances_20: list[dict],
                  rl_passed: list[dict], validated: list[dict],
                  baseline_result: dict, enhanced_result: dict,
                  progress: dict) -> None:
    progress["stage"] = "done"
    write_progress(run_dir, progress, "=== Writing final summary ===")

    rl_results = progress.get("repolaunch_results", {})
    summary = {
        "run_dir": str(run_dir),
        "started_at": progress.get("started_at", _now()),
        "finished_at": _now(),
        "total_selected": len(instances_20),
        "repolaunch_passed": len(rl_passed),
        "repolaunch_failed": len(instances_20) - len(rl_passed),
        "repolaunch_classifications": {
            cls: [k for k, v in rl_results.items() if v == cls]
            for cls in [RESULT_ORGANIZE_PASSED, RESULT_ORGANIZE_MISSING,
                        RESULT_SETUP_FAILED, RESULT_TIMEOUT, RESULT_INFRA_COMPLEX]
        },
        "validated": len(validated),
        "gold_passed": len(validated),
        "baseline_resolved": baseline_result.get("resolved", 0),
        "baseline_total": baseline_result.get("total", 0),
        "baseline_resolved_ids": baseline_result.get("resolved_ids", []),
        "enhanced_resolved": enhanced_result.get("resolved", 0),
        "enhanced_total": enhanced_result.get("total", 0),
        "enhanced_resolved_ids": enhanced_result.get("resolved_ids", []),
        "monitoring": {
            "progress_log": f"tail -f {run_dir}/progress.log",
            "progress_json": f"python -m json.tool {run_dir}/progress.json",
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    write_progress(
        run_dir, progress,
        f"DONE. RL_passed={len(rl_passed)}/{len(instances_20)} | "
        f"Validated={len(validated)}/{len(rl_passed)} | "
        f"Baseline={baseline_result.get('resolved',0)}/{baseline_result.get('total',0)} | "
        f"Enhanced={enhanced_result.get('resolved',0)}/{enhanced_result.get('total',0)}"
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if sys.version_info < (3, 10):
        logger.error(
            "This workflow must be launched with Python >=3.10 so enhancer "
            "modules can be imported. Use bench_env/bin/python or a Python 3.12 env."
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Pouya 20-issue GPT-5.4-mini pilot v2")
    parser.add_argument("--run-dir", type=Path, required=True,
                        help="Run directory (must contain launch_config.json)")
    parser.add_argument("--skip-repolaunch", action="store_true")
    parser.add_argument("--skip-gold-eval", action="store_true")
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--skip-enhanced", action="store_true")
    parser.add_argument("--limit", type=int, default=20,
                        help="Number of deterministic selected instances to run")
    parser.add_argument("--repolaunch-workers", type=int,
                        default=int(os.environ.get("POUYA_REPOLAUNCH_WORKERS", "4")),
                        help="Number of issue-level Paul/RepoLaunch processes to run concurrently")
    parser.add_argument("--repolaunch-timeout", type=int,
                        default=int(os.environ.get("POUYA_REPOLAUNCH_TIMEOUT", "2400")),
                        help="Max seconds per issue-level Paul/RepoLaunch process")
    parser.add_argument("--gold-workers", type=int,
                        default=int(os.environ.get("POUYA_GOLD_WORKERS", "4")),
                        help="Number of SWE-bench-Live gold-eval workers")
    parser.add_argument("--stop-after-gold-eval", action="store_true",
                        help="Run only RepoLaunch plus gold evaluation, then write summary and exit")
    parser.add_argument("--include-known-bad", action="store_true",
                        help="Do not exclude pilot rows already proven unsuitable for the lightweight Stage 1+2 batch")
    parser.add_argument("--enhancer", default="llm_append_analysis",
                        choices=["llm_append_analysis", "aider", "trae", "openhands",
                                 "mini_swe_agent", "swe_agent"],
                        help="Which enhancer to use for the enhanced solver condition")
    parser.add_argument("--solver", default="mini_swe_agent",
                        choices=["mini_swe_agent", "openhands", "swe_agent"],
                        help="Solver agent to use for baseline and enhanced conditions")
    parser.add_argument("--load-enhanced-from", type=Path, default=None,
                        help="Load a pre-built solver_enhanced_dataset.jsonl instead of "
                             "running the enhancer (skips enhancement phase, jumps to solver)")
    args = parser.parse_args()

    api_key = _load_openai_api_key()
    if not api_key:
        logger.error("OPENAI_API_KEY or OPENAI_API_KEY_FILE must be set before running.")
        sys.exit(1)

    run_dir: Path = args.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    launch_config = run_dir / "launch_config.json"
    if not launch_config.exists():
        logger.error("launch_config.json missing from %s", run_dir)
        sys.exit(1)

    # Stage 0: Select instances (deterministic, cached)
    selected_path = run_dir / f"selected_{args.limit}.jsonl"
    if selected_path.exists():
        instances_20 = [json.loads(l) for l in selected_path.open() if l.strip()]
        logger.info("Loaded existing %s (%d instances)", selected_path.name, len(instances_20))
    else:
        excluded_ids = set() if args.include_known_bad else DEFAULT_EXCLUDED_INSTANCE_IDS
        instances_20 = select_instances(DATASET_PATH, limit=args.limit, excluded_ids=excluded_ids)

    instances_20 = repair_instances_test_labels(instances_20, run_dir)
    with selected_path.open("w") as f:
        for r in instances_20:
            f.write(json.dumps(r) + "\n")
    (run_dir / f"selected_{args.limit}_instance_ids.txt").write_text(
        "\n".join(r["instance_id"] for r in instances_20) + "\n"
    )
    logger.info("Selected %d instances → %s", len(instances_20), selected_path)

    all_ids = [r["instance_id"] for r in instances_20]

    # Load or init progress
    progress_file = run_dir / "progress.json"
    if progress_file.exists():
        progress = json.loads(progress_file.read_text())
        # Ensure new keys exist for old progress files
        progress.setdefault("repolaunch_results", {})
        logger.info("Resuming from existing progress (stage=%s)", progress.get("stage"))
    else:
        progress = init_progress(run_dir, len(instances_20), all_ids)

    # Stage 1: RepoLaunch
    rl_passed_path = run_dir / "repolaunch_passed.jsonl"
    if args.skip_repolaunch and rl_passed_path.exists():
        rl_passed = [json.loads(l) for l in rl_passed_path.open() if l.strip()]
        rl_passed = repair_instances_test_labels(rl_passed, run_dir)
        write_progress(run_dir, progress,
                       f"Skipping RepoLaunch (using {len(rl_passed)} cached results)")
    else:
        rl_passed = run_repolaunch(
            run_dir,
            instances_20,
            launch_config,
            api_key,
            progress,
            max_issue_workers=args.repolaunch_workers,
            instance_timeout=args.repolaunch_timeout,
        )
        rl_passed = repair_instances_test_labels(rl_passed, run_dir)
        with rl_passed_path.open("w") as f:
            for r in rl_passed:
                f.write(json.dumps(r) + "\n")

    # Stage 2: Gold eval → validated_instances.jsonl
    validated_path = run_dir / "validated_instances.jsonl"
    if args.skip_gold_eval and validated_path.exists():
        validated = [json.loads(l) for l in validated_path.open() if l.strip()]
        write_progress(run_dir, progress,
                       f"Skipping gold_eval (using {len(validated)} cached)")
    else:
        validated = run_gold_eval(
            run_dir,
            rl_passed,
            api_key,
            progress,
            workers=args.gold_workers,
        )

    if args.stop_after_gold_eval:
        empty_result = {"resolved": 0, "total": 0, "resolved_ids": [], "failed_ids": []}
        write_progress(run_dir, progress, "Stopping after gold evaluation (--stop-after-gold-eval)")
        write_summary(run_dir, instances_20, rl_passed, validated, empty_result, empty_result, progress)
        logger.info("Pipeline stopped after gold eval. Results → %s", run_dir)
        return

    # Stage 3: Solver baseline
    solver_baseline_dir = run_dir / "solver_baseline"
    if not args.skip_baseline:
        solver_baseline_dir = run_solver(run_dir, validated, "solver_baseline",
                                         api_key, progress, enhanced=False,
                                         solver_id=args.solver)
    else:
        write_progress(run_dir, progress, "Skipping baseline solver (--skip-baseline)")

    baseline_result = run_solver_eval(run_dir, validated, solver_baseline_dir,
                                      "solver_baseline_eval", api_key, progress)
    progress["baseline_resolved"] = baseline_result.get("resolved_ids", [])

    # Stage 4: Solver enhanced
    solver_enhanced_dir = run_dir / "solver_enhanced"
    if not args.skip_enhanced:
        solver_enhanced_dir = run_solver(
            run_dir, validated, "solver_enhanced",
            api_key, progress, enhanced=True,
            enhancer_id=args.enhancer,
            solver_id=args.solver,
            prebuilt_dataset=args.load_enhanced_from,
        )
    else:
        write_progress(run_dir, progress, "Skipping enhanced solver (--skip-enhanced)")

    enhanced_result = run_solver_eval(run_dir, validated, solver_enhanced_dir,
                                      "solver_enhanced_eval", api_key, progress)
    progress["enhanced_resolved"] = enhanced_result.get("resolved_ids", [])

    write_summary(run_dir, instances_20, rl_passed, validated,
                  baseline_result, enhanced_result, progress)
    logger.info("Pipeline complete! Results → %s", run_dir)


if __name__ == "__main__":
    main()
