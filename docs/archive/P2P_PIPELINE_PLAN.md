# P2P-Only Pipeline: Data Collection Plan

**Created:** 2026-05-15  
**Last Updated:** 2026-05-19  
**Status:** Stage 2 RUNNING (enhanced run with memory pool + error feedback)

## Core Design Decisions

| Decision | Old pipeline | New pipeline |
|---|---|---|
| F2P required? | Yes (F2P > 0) | **No — dropped** |
| P2P required? | Yes (P2P > 0) | Yes (P2P > 0) |
| Test derivation method | Static parse only | Approach 1 → 2 → 3 progressively |
| LLM for environment setup | OpenAI API | **`gpt-oss:120b` via Ollama, fallback to GPT-5.4-mini** |
| Issue types covered | Bug only (implicitly) | Bug + Feature + Refactoring |
| Enhancer+Solver workflow | Unchanged | **Unchanged — kept as-is** |

**Why drop F2P:** F2P = 0 is the defining signal for refactoring issues (behavior-preserving).
Requiring F2P > 0 excluded all pure refactoring candidates and some feature candidates.
With P2P > 0 as the only gate, all three issue types are included in one unified pipeline.
F2P is still stored per instance as an observed attribute for analysis.

---

## Folder Structure

```
data/samples/pouya_p2p_pipeline/
├── stage1_approach1/
│   ├── dataset.jsonl      ← 387 issues (P2P>0, static parse, no Docker)
│   └── summary.json
├── stage2_approach2/
│   ├── dataset.jsonl      ← ~160–230 issues (Paul/RepoLaunch validated, Docker images)
│   └── summary.json
└── stage3_approach3/
    ├── dataset.jsonl      ← ~120–180 issues (full test suite validated, ground-truth P2P)
    └── summary.json

paul-RepoLaunch/
├── configs/
│   ├── p2p_pipeline_enhanced.json          ← gpt-oss:120b enhanced run (active)
│   └── p2p_pipeline_fallback_gpt54mini.json ← GPT-5.4-mini fallback (auto-triggered)
├── data/
│   ├── p2p_pipeline_stage1.jsonl                 ← full 387 (original Paul input)
│   ├── p2p_pipeline_enhanced_retry.jsonl          ← 335 non-succeeded (enhanced run input)
│   └── p2p_pipeline_fallback_gpt54mini.jsonl      ← LLM-capacity failures (auto-built)
└── workspace/
    ├── p2p_pipeline_stage2_20260515/      ← original gpt-oss run (done, 47 success)
    ├── p2p_pipeline_retry_gpt54mini/      ← first GPT-5.4-mini retry (done, 5 success)
    ├── p2p_pipeline_enhanced/             ← ACTIVE: memory pool + error feedback
    └── p2p_pipeline_fallback_gpt54mini/   ← auto-triggered after enhanced run

scripts/data/p2p_pipeline/
├── stage1_static_parse.py
├── stage1_llm_classify.py
├── stage2_collect_results.py
├── run_experiment.py
├── run_enhanced_then_fallback.sh   ← auto-chain: waits → fallback analysis → GPT-5.4-mini
└── monitor.py
```

---

## Stage 1 — Approach 1: Static Diff Parse + LLM Classification ✅ DONE

**Filter:** P2P > 0 (from `test_patch` diff, heuristic)  
**Input:** `data/samples/pouya_dataset_2026/raw_candidates.jsonl` (941 issues)  
**Output:** `data/samples/pouya_p2p_pipeline/stage1_approach1/dataset.jsonl`  
**Classification:** `gpt-oss:120b` via Ollama (4 parallel workers, ~7 min for 387 issues)  
**Classification script:** `scripts/data/p2p_pipeline/stage1_llm_classify.py`

Issue type is determined entirely by LLM — **no keyword heuristics**.
The LLM reads issue title + labels + problem_statement body and responds with exactly
one word: `bug`, `feature`, or `refactoring`. Temperature=0, seed=42 for reproducibility.
Each row stores `issue_type_source: "llm_gpt_oss_120b"` and `issue_type_raw` (raw model output).

### Counts

| Metric | Count |
|---|---:|
| **Total** | **387** |
| Bug (LLM) | 255 (65.9%) |
| Feature (LLM) | 114 (29.5%) |
| Refactoring (LLM) | 18 (4.6%) |
| Unknown | **0** |

**Cross-tab: LLM issue type × test structure (F2P)**

| LLM type | F2P > 0 | F2P = 0 | Total |
|---|---:|---:|---:|
| bug | 183 | 72 | 255 |
| feature | 92 | 22 | 114 |
| refactoring | 7 | 11 | 18 |

---

## Stage 2 — Approach 2: Paul/RepoLaunch Docker Validation ⏳ RUNNING

**What it does:**
1. Clone repo at `base_commit` in Docker container
2. LLM agent installs dependencies and sets up test environment
3. Run P2P tests — verify they PASS at base_commit
4. Commit passing container as Docker image
5. Drop instances where tests don't match expected outcomes

### Stage 2 — Multi-Run Strategy (Updated 2026-05-18)

Due to failures in the original run caused by a bug in verify.py and LLM format compliance,
Stage 2 runs in multiple phases:

| Run | Workspace | Model | Instances | Result |
|---|---|---|---|---|
| Original | `p2p_pipeline_stage2_20260515` | gpt-oss:120b | 387 | 47 success (stopped — NoneType bug) |
| First retry | `p2p_pipeline_retry_gpt54mini` | GPT-5.4-mini | 117 failed | 5 additional success (stopped) |
| **Enhanced** | `p2p_pipeline_enhanced` | gpt-oss:120b | 335 remaining | **ACTIVE** |
| Fallback | `p2p_pipeline_fallback_gpt54mini` | GPT-5.4-mini | LLM-cap failures | auto-triggered |

**Total unique successes so far: ~54** (52 from original runs, 2 new from enhanced run)

### Key Bug Found and Fixed (2026-05-18)

The original run had **104/117 failures** caused by a single code bug:

```
File: launch/launch/agent/setup/verify.py, line 189
Bug: action = parse_verify_action(response.content)
     if action.action == "command":   ← CRASH when action is None
Fix: if action is not None and action.action == "command":
     if action is None:
         continue   ← retry instead of crash
```

**Root cause:** `gpt-oss:120b` sometimes produces responses that don't follow the
`Action: <command>...</command>` format. `parse_verify_action()` returns `None`,
and the code crashed instead of asking the LLM to retry with a format reminder.

This fix was applied to `SWE-bench-Live-Collection/launch/launch/agent/setup/verify.py`
before the enhanced run was launched.

### Enhancements in the Active Run (SWE-Factory + SWE-Universe Strategies)

Two strategies from recent academic papers were implemented as Paul patches
in `paul-RepoLaunch/paul/patches/patch_state.py`:

#### 1. Environment Memory Pool (SWE-Factory FSE'26)
- **What:** When a repo has a successful Docker build from a sibling instance, inject
  its `setup_commands` as hints for the new instance
- **Where:** `patch_memory_pool()` in `patch_state.py`
- **How:** Scans `workspace/playground/*/result.json` for same-repo successes,
  truncates to 40 commands, injects as "Environment Memory Pool" hint in setup prompt
- **Result:** Confirmed working — 4 injections logged, GeoNode-13352 succeeded using
  sibling data from GeoNode-13461

#### 2. Iterative Error Feedback (SWE-Universe arXiv 2602.02361)
- **What:** When verify() fails, capture structured diagnostics (error patterns,
  failing commands) and inject them into the setup prompt on the next retry cycle
- **Where:** `patch_error_feedback()` in `patch_state.py`
- **How:** Patches verify() to extract error lines, stores in `state["_error_diagnostic"]`,
  setup() reads this on retries and adds a "Diagnostic from previous failed attempt" hint
- **Result:** Confirmed working — 2 diagnostic injections logged

#### 3. Higher Limits
- `max_trials`: 2 → 3 (one more retry cycle)
- `max_steps_setup`: 40 → 50 (10 more LLM steps per setup)
- `max_steps_verify`: 20 → 25
- `cmd_timeout`: 60 → 90 seconds

### Fallback: GPT-5.4-mini for LLM-Capacity Failures

When the enhanced run finishes, `run_enhanced_then_fallback.sh` automatically:

1. Categorizes all failures:
   - **LLM-capacity:** `"'NoneType' object has no attribute 'action'"`, `JSONDecodeError`,
     or empty response — caused by the model not following the output format
   - **Infra failures:** everything else — Docker build errors, missing dependencies,
     platform issues (Windows-only repos, GPU requirements, etc.)
   - **Not attempted:** instances Paul never started (crash/timeout)
2. Builds fallback dataset: LLM-capacity + not-attempted
3. Seeds fallback workspace with all successful results (for memory pool)
4. Launches Paul with GPT-5.4-mini via OpenAI API
   - GPT-5.4-mini is significantly better at following structured output formats
   - Same config: memory pool enabled, error feedback enabled, max_trials=3

**Infra failures are NOT retried** — a smarter LLM cannot fix Docker build issues,
missing system libraries, or platform incompatibilities.

### Configs

```
paul-RepoLaunch/configs/p2p_pipeline_enhanced.json
paul-RepoLaunch/configs/p2p_pipeline_fallback_gpt54mini.json
```

### Expected counts after Stage 2 (estimated)

| Metric | Estimated |
|---|---:|
| **Total surviving** | **~160–230** (42–60% of 387) |
| Bug | ~105–150 |
| Feature | ~48–68 |
| Refactoring | ~7–12 |

**Output:** `data/samples/pouya_p2p_pipeline/stage2_approach2/dataset.jsonl`  
Each row gains: real `docker_image`, `test_cmds`, `validation_status`

---

## Stage 3 — Approach 3: Full Test Suite Before/After ⏳ PENDING

**What it does:**
For each Stage 2 survivor (has a real Docker image):
1. Start container from the Docker image (base_commit state)
2. Run the **full test suite** of the repo (`pytest tests/` or equivalent)
3. Record ALL test outcomes → `before_patch_results`
4. Apply gold patch (`patch` field)
5. Run full test suite again → `after_patch_results`
6. Derive ground-truth F2P and P2P from outcome diff
7. Keep instance only if ground-truth P2P > 0

**Why this improves on Stage 2:**
- P2P tests from Stage 2 are only the ones in files the developer touched
- Stage 3 P2P includes ALL passing tests in the entire repo — much stronger regression guard

**Expected counts after Stage 3 (estimated):**

| Metric | Estimated |
|---|---:|
| **Total surviving** | **~120–180** (75–80% of Stage 2) |
| Bug | ~80–120 |
| Feature | ~35–53 |
| Refactoring | ~5–8 |

---

## Issue Type Counts Across Stages

| Stage | Total | Bug | Feature | Refactoring |
|---|---:|---:|---:|---:|
| Raw candidates (941) | 941 | — | — | — |
| **Stage 1 ✅** | **387** | **255** | **114** | **18** |
| Stage 2 ⏳ (target) | ~160–230 | ~105–150 | ~48–68 | ~7–12 |
| Stage 3 ⏳ (target) | ~120–180 | ~80–120 | ~35–53 | ~5–8 |

---

## Steps 6–9: Enhancer+Solver Experiment

After Stage 2 produces Docker-validated instances, the experiment runs automatically.

### Step 6 — Baseline Solver

Solver (mini-SWE-agent) reads the **original** `problem_statement` and generates a patch.
**Evaluation:** Apply patch → run P2P tests → count how many pass = "resolved".

### Step 7 — Enhancer

The `llm_append_analysis` enhancer rewrites `problem_statement` with structured analysis.
LLM backend: `gpt-oss:120b` via Ollama.

### Step 8 — Enhanced Solver

Same solver runs again with the **enhanced** `problem_statement`.

### Step 9 — Analysis

Compare baseline vs enhanced resolution rates. If P2P pass rate increases after
enhancement, the enhancer has a positive effect.

### Experiment flow

```
Stage 2 validated dataset (Docker images)
         │
    ┌────┴────┐
    ▼         ▼
 Step 6     Step 7
 Baseline   Enhancer
 Solver        │
    │      Step 8
    │      Enhanced Solver
    │          │
    └────┬─────┘
         ▼
      Step 9: Analysis
```

---

## Script Reference

| Script | Purpose |
|---|---|
| `scripts/data/p2p_pipeline/stage1_llm_classify.py` | LLM issue type classifier |
| `scripts/data/p2p_pipeline/stage2_collect_results.py` | Merge Paul results into stage2 dataset |
| `scripts/data/p2p_pipeline/run_experiment.py` | Steps 6–9 orchestrator |
| `scripts/data/p2p_pipeline/run_enhanced_then_fallback.sh` | Auto-chain: waits → analyze → GPT-5.4-mini fallback |
| `scripts/data/p2p_pipeline/monitor.py` | Live pipeline status (all workspaces) |
| `paul-RepoLaunch/paul/patches/patch_state.py` | All Paul patches incl. memory pool + error feedback |

---

## LLM Configuration

| Task | Model | How |
|---|---|---|
| Issue classification (Stage 1) | gpt-oss:120b | Direct Ollama HTTP API |
| Docker env setup (Stage 2, primary) | gpt-oss:120b | Paul patches → local LLM provider |
| Docker env setup (Stage 2, fallback) | GPT-5.4-mini | OpenAI API (auto-triggered) |
| Enhancement (Step 7) | gpt-oss:120b | `src/utils/llm_client.py` → Ollama |
| Solver (Steps 6, 8) | gpt-oss:120b | mini-SWE-agent → litellm → Ollama |

---

## Monitoring & Status

```bash
# Full pipeline status:
watch -n 30 python3 scripts/data/p2p_pipeline/monitor.py

# Enhanced run log (active):
tail -f ~/paul-RepoLaunch/workspace/p2p_pipeline_enhanced_run.log

# Auto-chain log:
tail -f runs/p2p_enhanced_fallback_auto.log

# After stage 2 completes — collect results:
python scripts/data/p2p_pipeline/stage2_collect_results.py

# Test experiment on 10 instances:
python scripts/data/p2p_pipeline/run_experiment.py \
    --stage2-dataset data/samples/pouya_p2p_pipeline/stage2_approach2/dataset.jsonl \
    --run-dir runs/p2p_experiment_test_$(date +%Y%m%d) \
    --limit 10
```

---

## Related Docs

- `docs/F2P_P2P_APPROACHES_NOTE.md` — F2P/P2P definitions, why F2P was dropped
- `docs/DATA_COLLECTION.md` — issue type taxonomy, label vs test structure dimensions
- `docs/NEW_TYPED_DATASETS_ROADMAP.md` — roadmap for typed sub-datasets
