# Paul/RepoLaunch: Docker Image Build Guide

**Paul** (`/home/22pf2/paul-RepoLaunch/`) is a localized wrapper around Microsoft's [RepoLaunch](https://arxiv.org/abs/2603.05026) that builds Docker images for each SWE-bench instance automatically using an LLM agent.

---

## What Paul Does

You give it a JSONL dataset of repos → it automatically:
1. Spins up a Docker container from a base Python image
2. Runs an LLM agent that clones the repo at `base_commit`, installs dependencies, and verifies targeted tests pass (F2P/P2P from the dataset)
3. Commits the passing container as a named Docker image: `<image_prefix>:<instance_id>_linux`
4. Saves all logs and metadata to the local filesystem

---

## Does Paul Need Qdrant?

**No.** Paul has zero vector database dependency. All outputs are saved to the local filesystem:

```
paul-RepoLaunch/workspace/<run_name>/
├── playground/<instance_id>/
│   ├── result.json         # Docker image name, test commands, setup duration, completion status
│   ├── setup.log           # Full LLM agent setup conversation
│   ├── organize.log        # Organize agent conversation (if mode.organize=true)
│   ├── llm/                # Per-step LLM logs as numbered Markdown files (0.md, 1.md, ...)
│   └── instance.json       # Input dataset row
├── setup.jsonl             # One line per instance: summary after setup phase
└── organize.jsonl          # One line per instance: docker_image + test_cmds + log_parser
```

The `organize.jsonl` file is what downstream workflow scripts (like `run_pouya20_gpt54mini.py`) read to get the `docker_image` field needed to launch the solver.

---

## API Requirements

| Config | Provider | API Key |
|--------|----------|---------|
| Default (`local_config.json`) | **Ollama** (local) | None — model must be pulled locally |
| OpenAI mode | **OpenAI API** | `OPENAI_API_KEY` environment variable |

**To use OpenAI (recommended for complex repos):**

Set `"llm_provider_name": "OpenAI"` in the config. The LLM monkey-patch is then skipped, and upstream RepoLaunch uses OpenAI directly via its LiteLLM integration.

---

## Architecture (How Patches Work)

Paul applies 5 monkey-patches **before** importing `launch.run`:

| Patch | Replaces | Why |
|-------|----------|-----|
| `patch_tavily_import` | Tavily (paid search) → DuckDuckGo | No API key needed |
| `patch_llm_provider` | Cloud LLM → Ollama HTTP client | Skipped if `llm_provider_name != "local"` |
| `patch_search_tool` | `TavilySearchResults` → `LocalSearchTool` | Uses DuckDuckGo in `AgentState.create()` |
| `patch_targeted_test_command_guard` | Broad pytest → F2P/P2P targeted commands | Prevents full-suite runs (10× slower) |
| `patch_timemachine_bind` | `127.0.0.1` → `0.0.0.0` for PyPI proxy | Docker containers reach it via `host.docker.internal` |

The upstream RepoLaunch code is **never modified** — patches are applied at runtime only.

---

## Known Bugs and Pitfalls

### Bug 1: `organize: false` in `local_config.json` — No Docker image produced!

```json
// local_config.json (WRONG for image creation)
"mode": {"setup": true, "organize": false}
```

**Problem:** Setup alone installs dependencies and verifies tests, but the Docker image commit happens at the END of the **organize phase**, not setup. With `organize: false`, Paul runs but no Docker image is saved.

**Fix:** Always use `"mode": {"setup": true, "organize": true}` when you need a Docker image for the solver.

### Bug 2: `image_prefix` mismatch

The default `local_config.json` uses `"image_prefix": "paul/dev"`, but the Pouya-20 solver pipeline expects `"pouya20gpt-stage12/dev"` (the prefix used for all 18 working instances).

**Fix:** Always set `image_prefix` in your config to match what the solver expects. For Pouya-20 rebuilds, use `"pouya20gpt-stage12/dev"`.

### Bug 3: PyPI time-machine network hang (CLOSE-WAIT)

When `disable_timemachine: false` (default), Paul binds a PyPI proxy at `0.0.0.0`. Some Docker network setups can't reach `host.docker.internal`, causing pip installs inside containers to stall indefinitely (CLOSE-WAIT socket state). This caused the `aws-powertools-*` exclusions.

**Fix:** Use `"disable_timemachine": true` in configs. This is already set in `dlt_hub_rebuild_config.json` and the canonical `pouya_final20b` launch config.

---

## Correct Config for Pouya-20 Rebuilds

Use `paul-RepoLaunch/configs/dlt_hub_rebuild_config.json`:

```json
{
    "llm_provider_name": "OpenAI",
    "model_config": {"model_name": "gpt-5.4-mini", "temperature": 0.0},
    "mode": {"setup": true, "organize": true},
    "upstream_path": "/home/22pf2/BenchmarkLLMAgent/SWE-bench-Live-Collection/launch",
    "workspace_root": "workspace/dlt_hub_rebuild/",
    "dataset": "data/dlt_hub_rebuild.jsonl",
    "image_prefix": "pouya20gpt-stage12/dev",
    "disable_timemachine": true,
    "max_workers": 1,
    "max_trials": 1,
    "max_steps_setup": 12,
    "max_steps_verify": 4,
    "max_steps_organize": 15,
    "cmd_timeout": 30
}
```

**Run:**
```bash
cd /home/22pf2/paul-RepoLaunch
set -a && source /home/22pf2/BenchmarkLLMAgent/.env && set +a
conda run -n paul-repolaunch python -m paul.run configs/dlt_hub_rebuild_config.json
```

---

## Rebuilding Specific Instances

To rebuild specific instances, create a filtered JSONL dataset:

```python
import json

# Read from the validated dataset
with open('/home/22pf2/BenchmarkLLMAgent/runs/pouya_final20b_20260505_050130/validated_instances.jsonl') as f:
    rows = [json.loads(l) for l in f]

# Filter to target instances
targets = {'dlt-hub__dlt-2935', 'dlt-hub__dlt-3048'}
subset = [r for r in rows if r['instance_id'] in targets]

with open('/home/22pf2/paul-RepoLaunch/data/my_rebuild.jsonl', 'w') as f:
    for r in subset:
        f.write(json.dumps(r) + '\n')
```

Then update the dataset field in the config and run.

---

## After Rebuilding: Update `validated_instances.jsonl`

After new images are built, update the `docker_image` field in the validated dataset:

```python
import json

path = 'runs/pouya_final20b_20260505_050130/validated_instances.jsonl'
with open(path) as f:
    rows = [json.loads(l) for l in f if l.strip()]

image_updates = {
    'dlt-hub__dlt-2935': 'pouya20gpt-stage12/dev:dlt-hub__dlt-2935_linux',
    'dlt-hub__dlt-3048': 'pouya20gpt-stage12/dev:dlt-hub__dlt-3048_linux',
}

for row in rows:
    iid = row.get('instance_id', '')
    if iid in image_updates:
        row['docker_image'] = image_updates[iid]
        row['image_name'] = image_updates[iid]

with open(path, 'w') as f:
    for row in rows:
        f.write(json.dumps(row) + '\n')
```

---

## Docker Image Naming Convention

All Pouya-20 images follow the pattern:
```
pouya20gpt-stage12/dev:<instance_id>_linux
```

Example: `pouya20gpt-stage12/dev:dlt-hub__dlt-2935_linux`

To list all available images:
```bash
docker images --format "{{.Repository}}:{{.Tag}}" | grep "pouya20gpt-stage12"
```

---

## Efficiency

| Repo | Setup Duration | Notes |
|------|---------------|-------|
| dlt-hub__dlt-2935 | ~3 min | Python, many optional extras, smart extra pruning |
| dlt-hub__dlt-3048 | ~5 min | Same base image reused from prior step |
| Typical Python repo | 3–10 min | Depends on dependency count |

**Targeted test injection** (F2P/P2P → `pytest -v -rA <specific_tests>`) prevents the LLM from running full test suites during setup verification, which would be 10–100× slower for large repos.

With `max_workers: 8` on the GPU server, 20 repos can be processed in ~30 minutes total.
