# BenchmarkLLMAgent — Canonical Workflow & Script Reference

> **Purpose:** one authoritative description of the end-to-end pipeline, every script,
> **which node each runs on**, and the operational rules. For *live status* (what is
> running right now, with timestamps and results) see **[PIPELINE_STATE.md](PIPELINE_STATE.md)**.
> Last reviewed: **2026-06-17**.

---

## 0. Two-server topology

| | **docjk-gpu-01 (Node 01)** | **docjk-gpu-02 (Node 02)** |
|---|---|---|
| GPUs | 8× A100 80 GB | 8× A100 80 GB |
| Shared Ollama (other users) | **yes, on `:11434`** — never use | none |
| Our private Ollama | `:11435` (gets the free GPUs) | `:11435` (gets all 8) |
| Primary dataset | node1 (`node1_all494_stage3_merged_20260610.jsonl`, 510 issues) | node2 (`node2_gpu02_ready_stage45_20260614.jsonl` + `node2_stage3_p2p878_20260610.jsonl`) |
| `/home` | per-node (NOT shared) | per-node (NOT shared) |
| `/data` | **shared NFS (42 TB)** — the cross-node channel | same `/data` |

**Golden rules**
1. **Never use the shared Ollama `:11434`.** Always our private `:11435`.
2. **One LLM-heavy job per node at a time.** `:11435` holds one model (`MAX_LOADED_MODELS=1`);
   two jobs with different context sizes thrash it. So on any single node you run *either* a
   matrix run *or* an image-build pass — never both at once.
3. **Never delete `pouya/stage2_2026:*` images** (Stage 1-3 output, irreplaceable). Only the
   ephemeral `ghcr.io/openhands/runtime:*` layer is safe to prune.
4. Cross-node hand-off is always via `/data` (NFS). `/home` is per-node.

---

## 1. The pipeline — 6 stages, split into 2 parts

```
   ┌──────────────── PART 1 (Stages 1-3): build the environment ────────────────┐
   │  Stage 1  LLM classification / setup planning   (paul-RepoLaunch `collect`) │
   │  Stage 2  Docker image build  ─────────────►  pouya/stage2_2026:<id>_linux  │
   │  Stage 3  Validation (P2P>0 test executes; recorded in dataset row)         │
   └────────────────────────────────────────────────────────────────────────────┘
                                      │  (image is the hand-off artifact)
                                      ▼
   ┌──────────────── PART 2 (Stages 4-6): run the agents ───────────────────────┐
   │  Stage 4  Enhancer agent rewrites the issue text                            │
   │  Stage 5  Solver agent writes a patch INSIDE the Stage-2 image              │
   │  Stage 6  Evaluation (non-empty patch now; full SWE-bench F2P/P2P later)    │
   └────────────────────────────────────────────────────────────────────────────┘
```

- **Part 1 output** = one tagged Docker image per issue, `pouya/stage2_2026:<instance_id>_linux`.
  Irreplaceable without a rebuild (minutes-to-an-hour each). Persisted to NFS (see §6).
- **Part 2** = the experiment. Enhancers ∈ {openhands, swe_agent, aider, …}; Solvers (with
  `run_batch`) ∈ {openhands, swe_agent, aider}. Both use the private Ollama.

---

## 2. Private Ollama — identical setup on both nodes

**Script:** `scripts/ops/setup_private_ollama.sh` — **runs on: BOTH nodes.**
```bash
bash scripts/ops/setup_private_ollama.sh            # start + ensure models
bash scripts/ops/setup_private_ollama.sh status     # health
bash scripts/ops/setup_private_ollama.sh restart    # force restart
```
Fixed reproducible config it applies:
- `OLLAMA_HOST=127.0.0.1:11435` (private port, never `:11434`).
- **Adaptive GPU selection:** auto-detects GPUs with ≥40 GB free and spreads across exactly
  those (`OLLAMA_SCHED_SPREAD=1`). Node 02 → all 8; Node 01 → the 4 the shared Ollama left
  free (3,4,5,7). *Forcing SCHED_SPREAD onto the shared Ollama's full GPUs crashes the runner
  with CUDA OOM — hence adaptive.* Override: `FORCE_GPUS=...`, `FREE_VRAM_MIN_MB=...`.
- `OLLAMA_NUM_PARALLEL=8` (raised from 4 on 2026-06-18 — GPUs were ~22% idle; supports
  `--workers 8`), `OLLAMA_KEEP_ALIVE=-1`, `OLLAMA_MAX_LOADED_MODELS=1`. Override via
  `OLLAMA_NUM_PARALLEL=…`; takes effect on the next `setup_private_ollama.sh restart`.
- `OLLAMA_MODELS=/data/22pf2_data/ollama_models` — **writable, NFS-shared, persistent**
  (pulled once, reused on both nodes). NOT `/home/ollama_shared_models` (owned by `ollama`,
  read-only for us — `pull` fails there with "permission denied").

**Models**
- `qwen3:32b` (dense) — **works. Default model for the whole pipeline.**
- `qwen3-coder:30b` (`qwen3moe` MoE) — **BLOCKED on both nodes.** System Ollama v0.23.4 can't
  load the MoE arch; the user-space v0.30.8 binary can, but its CUDA kernels need a newer
  driver than installed (**driver 535 / CUDA 12.2** → "device kernel image is invalid").
  Running MoE models requires an **admin NVIDIA-driver upgrade**. Until then, use a dense
  code model (`deepseek-coder:33b`, `qwen2.5-coder:32b`) for comparisons. User-space binary
  is opt-in: `USE_USERSPACE_OLLAMA=1`.

---

## 3. PART 1 scripts (Stages 1-3 — build & persist images)

| Script | Runs on | What it does |
|---|---|---|
| `scripts/workflows/run_part1_build_images.py` | **either node** | Driver for a dataset: `--mode verify` (which images present/backed-up), `--mode backup` (persist present images to NFS), `--mode build` (build missing via paul-RepoLaunch, then persist). |
| `/home/22pf2/paul-RepoLaunch/scripts/build_node1_missing127.py` | **either node** (designed to offload to Node 02) | Rebuilds the 127 node1 images missing on Node 01, using the proven `collect.main(setup)` + `paul/run.py` path, pinned to **qwen3:32b** (won't evict a matrix's model). **Build → `docker save` to NFS → free local copy → prune cache**, so disk stays flat and it can grind all 127 without ENOSPC. Disk floor 150 GB. **Auto-aborts if a Part-2 run is active** (single-Ollama rule). Reads recipes/IDs from NFS via `RECIPE_SRC`, `BUILD_INSTANCE_LIST`, `BUILD_DATASET` so it runs on Node 02 against Node 01's targets. |

The underlying builder is **paul-RepoLaunch** (`/home/22pf2/paul-RepoLaunch`), `collect` in
setup-only / `overwrite=true` mode → `pouya/stage2_2026:<id>_linux`.

```bash
# verify / persist images for a dataset (either node):
python scripts/workflows/run_part1_build_images.py --dataset data/<set>.jsonl --mode verify
python scripts/workflows/run_part1_build_images.py --dataset data/<set>.jsonl --mode backup
# build missing node1 images on Node 02 (recipes staged on NFS):
RECIPE_SRC=/data/22pf2_data/node02_pipeline_sync/node1_missing_build/recipes \
BUILD_INSTANCE_LIST=/data/22pf2_data/node02_pipeline_sync/node1_missing_build/missing_127_ids.txt \
BUILD_DATASET=/data/22pf2_data/node02_pipeline_sync/node1_missing_build/node1_all494_stage3_merged_20260610.jsonl \
nohup nice -n 15 ~/anaconda3/envs/paul-repolaunch/bin/python \
    ~/paul-RepoLaunch/scripts/build_node1_missing127.py > ~/build_missing127.log 2>&1 &
```

---

## 4. PART 2 scripts (Stages 4-6 — enhance, solve, evaluate)

| Script | Runs on | What it does |
|---|---|---|
| `scripts/workflows/run_matrix_test.py` | **either node** | The enhancer×solver **matrix** runner. For each LLM, runs `(1 baseline + N enhancers) × M solvers` conditions over a dataset. Flags: `--dataset`, `--llms`, `--workers` (default 4; use 8 with `NUM_PARALLEL=8`), `--tag`, `--disk-floor` (mid-run prune of ephemeral runtime images so long runs can't ENOSPC). Isolates every condition (a failing agent never aborts the matrix). Writes `matrix_result.json` and copies it to NFS. |
| `scripts/workflows/run_node1_full383_qwen3.py` | **Node 01 only** | Production single-condition run (openhands enhancer + openhands solver) over the full node1 runnable set (383). |
| `scripts/workflows/run_node2_qwen3.py` | **Node 02 only** | Same, for node2. Use `--dataset … --base-url http://localhost:11435/v1`; set `MINI_TIMEOUT=600`. |
| `scripts/evaluate/run_stage6_p2p.py` | **either node (CPU, no LLM/GPU)** | **Stage 6** — scores solver patches for real via the SWE-bench-Live harness in the `pouya/stage2_2026` image. **Gate first with a gold probe** (`--patch_dir gold`): only score instances where the gold patch passes. Can run concurrently with a GPU matrix run. **Multi-method evaluability (2026-06-20):** the dataset's offline F2P/P2P node-IDs are often wrong, so no single test command works for all repos. Combine three methods, taking per-instance whichever passes gold — (v2) the playground's real validated `test_commands`/`rebuild_commands` (env: pytest-django, etc.); (v3) **label-agnostic** = run the test *files* with the real env and require "≥1 passed, 0 failed" (robust to bad labels; fixes django/pgcli/atlassian); (v1) generic file-based. **This lifted clean coverage 30%→55%** (6→11 of 20). The rest are fundamental (skip-only tests like bleak/fsspec, `uv`/heavy envs like mjlab/torchgeo, or unresolved failures). Method map: `/home/22pf2/stage6/evaluable_methods.json`. |

Per-agent model env (the matrix runner sets these automatically): enhancers read
`OPENHANDS_*` / `SWEAGENT_*` / `AIDER_*`; solvers read `OH_SOLVER_*` / `SWEA_SOLVER_*` /
`AIDER_SOLVER_*`. openhands & swe_agent take the bare model (`qwen3:32b`); aider/litellm
needs the `openai/` prefix (`openai/qwen3:32b`).

```bash
# matrix health-check (either node):
MINI_TIMEOUT=600 nohup bench_env/bin/python scripts/workflows/run_matrix_test.py \
    --dataset data/<set>.jsonl --llms qwen3:32b --workers 4 --tag <tag> > ~/<tag>.log 2>&1 &
```

---

## 5. Operations scripts (`scripts/ops/`) — run on BOTH nodes

| Script | Purpose | When |
|---|---|---|
| `setup_private_ollama.sh` | Start/verify the private `:11435` Ollama (see §2). | before any run |
| `cleanup_between_runs.py` | **Reap leaked solver subprocesses** (OpenHands orphans `python`+`ipykernel`+`action_execution_server` on timeout — held 88 GB on Node 02), **remove ephemeral `ghcr.io/openhands/runtime` images**, prune stopped containers + build cache. **Refuses if a run is active; never touches `pouya/stage2_2026`** (asserts the count is unchanged). | before & after every run |
| `backup_stage2_images.py` | `backup` / `verify` / `restore` the `pouya/stage2_2026` images to/from NFS. | persist after Part 1; restore before Part 2 if images were pruned |

```bash
python scripts/ops/cleanup_between_runs.py --dry-run   # preview
python scripts/ops/cleanup_between_runs.py             # reap + prune (safe)
python scripts/ops/backup_stage2_images.py restore --dataset data/<set>.jsonl
```

---

## 6. Image persistence — "saved on disk, not cache, lives forever"

Three layers guarantee Stage 1-3 images survive:
1. **Real tagged images** (overlay2 on disk), not build cache. Build *cache* (the 366 GB kind
   that filled root on 2026-06-15) is throwaway and gets pruned; the tagged images don't.
2. **NFS backup** at `/data/22pf2_data/stage2_image_backups/<id>_linux.tar.gz`. An accidental
   `docker image prune -a` is then recoverable in minutes, on either node.
3. **Cleanup never touches them** — `cleanup_between_runs.py` asserts the base-image count is
   unchanged and only removes the ephemeral runtime layer.

---

## 7. Shared NFS layout (`/data/22pf2_data/`)

| Path | Contents |
|---|---|
| `ollama_models/` | Private-Ollama model store (qwen3:32b, qwen3-coder:30b). Shared by both nodes. |
| `stage2_image_backups/*.tar.gz` | Persisted `pouya/stage2_2026` images (restore source). |
| `gpu_matrix_results/<run>/matrix_result.json` | Part-2 matrix results from both nodes. |
| `gpu_matrix_results/NODE02_*_FOR_NODE01.md` | Cross-node reports from the Node 02 agent. |
| `node02_pipeline_sync/` | Scripts + the 127-build recipes staged for Node 02. |

---

## 8. Resource guardrails (learned the hard way)

- **Root `/` is only 1.8 TB and holds Docker.** Run `cleanup_between_runs.py` before/after
  every run. The permanent fix is moving Docker's data-root to `/home` (32 TB free) — needs admin.
- **Leaked solver subprocesses** fill RAM/swap; the cleanup reaps them (88 GB recovered on Node 02).
- **`/tmp` ENOSPC** crashed runs on 2026-06-15 (build cache ballooned); the runners guard `/tmp`.
- **Concurrency / speed tuning (measured 2026-06-18):** at `--workers 2` + `NUM_PARALLEL=4`,
  the 4 GPUs sat at only **~22% util** (16/80 GB VRAM), RAM 96 GB/1.5 TB, CPU load 10/96 — i.e.
  the box was ~80% idle and runs were **under-parallelized, not resource-bound**. Safe speed-ups:
  - **`--workers 4`** uses the `NUM_PARALLEL=4` already configured → ~2× faster, free (GPUs still <50%).
  - **`--workers 8` + restart Ollama with `OLLAMA_NUM_PARALLEL=8`** (only when no run is active) →
    ~3–4× (GPUs ~50–70%); RAM/CPU/VRAM all have ample headroom (full383 ran 8 on `:11435`).
  - **⚠️ CORRECTION (measured on the 50-issue run, 2026-06-20):** high concurrency is NOT a
    "marginal" wobble for **slow, iterative solvers**. At `--workers 8` the openhands and
    swe_agent solvers collapsed (openhands 24%→3% non-empty, swe_agent →0%) because they make
    many sequential LLM calls and got starved under 8-way contention → hit the 1800 s timeout →
    empty patches. The **fast aider solver was unaffected** (≈48%). **Guidance:** use `--workers 8`
    only when the solver is fast (aider) or you're not comparing slow solvers; keep `--workers 2-4`
    for fair openhands/swe_agent comparisons, or raise `OH_SOLVER_TIMEOUT`. The runner has no
    resume — pick `--workers` at launch.
  - **⚠️ CORRECTION 2 (100-issue run, 2026-06-28): aider is NOT always safe at workers=8.** On the
    new-50 (heavier repos: Azure-search-demo 37 MB diff, AutoRAG, hypothesis…) aider at `--workers 8`
    *also* starved on Ollama contention → **27 cells hit the 3600 s wall** (artifact, not failure).
    Re-solving those at `--workers 4` recovered **20/27** with a **median 881 s** solve (1 genuine
    timeout). **`SOLVER_WORKERS` is now `{openhands:4, swe_agent:4, aider:4}`** in `run_matrix_test.py`.
    aider=8 is only safe when the repos are light; use 4 for unknown/large sets.
  - **⚠️ openhands `0600` patch artifact (~2%):** the runtime container occasionally flushes
    `oh_solution.patch` as its own UID with `0600` perms → unreadable to the host → counted empty.
    `openhands_solver.py` now has a **root-Docker read fallback**. To recover historic runs:
    `docker run --rm -v <workspace>:/mnt:ro python:3.12-slim cat /mnt/oh_solution.patch`.

---

## 9. Standard run order (either node)

```bash
cd ~/BenchmarkLLMAgent
python scripts/ops/cleanup_between_runs.py                      # 1. clean leftovers
bash   scripts/ops/setup_private_ollama.sh                      # 2. private Ollama up
python scripts/workflows/run_part1_build_images.py --dataset data/<set>.jsonl --mode build   # 3. Part 1 (images)
MINI_TIMEOUT=600 nohup bench_env/bin/python scripts/workflows/run_matrix_test.py \
    --dataset data/<set>.jsonl --llms qwen3:32b --workers 4 --tag <tag> > ~/<tag>.log 2>&1 &  # 4. Part 2
python scripts/ops/cleanup_between_runs.py                      # 5. clean again afterward
```

Live dashboard: `watch -n 15 bash /home/22pf2/pipeline_dashboard.sh`.

---

## 10. Cross-node coordination protocol

- Node 01 and Node 02 each have a manager agent; they coordinate **only through `/data` (NFS)**.
- Reports are written as `NODE0X_*_FOR_NODE0Y.md` in `gpu_matrix_results/`.
- To run Node 01 work on Node 02 (e.g., image builds), stage inputs under
  `node02_pipeline_sync/` and the built images return via `stage2_image_backups/`.

---

## 11. Stage 6 — correctness scoring on a new issue set (CPU/Docker only, no GPU)

Three phases (see `scripts/evaluate/`):
1. **`build_stage6_100.py`** — builds, for the target set: (a) consolidated per-condition preds
   spanning the source runs, (b) `stage6_<set>_v{1,2,3}.jsonl` eval datasets, (c) `gold_preds_*.json`.
2. **`gold_probe_100.py`** — gold-probe gate: runs the harness with the GOLD patch under each method
   (v2 real commands → v3 label-agnostic → v1 generic), assigns each instance the most precise
   passing method → `evaluable_methods_*.json`. **100-issue coverage: 74/100** (59 v2 + 15 v3),
   up from 55% on sample20.
3. **`run_stage6_combined_100.py`** — scores each condition's patches on the evaluable subset using
   the per-instance method. Metric = **P2P resolved** (solver patch + test_patch applied; P2P passes).

**Gotchas (cost real debugging):**
- **Absolute `--output_dir`/`--patch_dir` are mandatory.** The harness runs with `cwd=evaluation/`,
  so a *relative* path writes reports under `evaluation/<relpath>` while the checker reads the repo
  root → **silent `0/74`**. Fixed in `run_stage6_combined_100.py` (resolves paths); same trap bit the
  output dir of `gold_probe` (use absolute `OUTDIR`).
- **Fixed denominator = the evaluable set.** Empty/failed patches produce no report → count as
  *unresolved*. Do NOT divide by "instances that produced a report" (inflates the rate, and makes
  conditions incomparable).
- **Metric is P2P-only** (no-regression + de-facto fix via applied test_patch), not full F2P —
  **directional, not definitive.** Re-deriving F2P/P2P from real execution is the lever to make it definitive.
