# Pipeline State — Live Status (per-node, per-process)

> Snapshot timestamp: **2026-06-29 (UTC)** · captured on **docjk-gpu-01**.
> How the pipeline works + every script → **[WORKFLOW.md](WORKFLOW.md)**. This file is the
> *current state*: what ran, when, where, and the results.

---

## 0-CL. CL-Enhanced (\ourmethod) 4th arm — IN PROGRESS (2026-07-30)

Testing the paper's own managed/reward-gated/RAG enhancer as a 4th arm vs the 3 generic enhancers,
on the same 382 / downstream-correctness harness. **Model = qwen3:32b** (NOT gemma3 — see below),
so the comparison isolates enhancement METHOD from model (generic enhancers all used qwen3:32b too).
Run: `runs/cl_enhanced_382_20260730_*`, driver `scripts/workflows/run_cl_enhanced_arm.py`
(Stage 4 cl_enhanced + Stage 5 3 solvers; baseline REUSED from the 382 run).

- **gemma3 blocked** (faithful RQ2/RQ3 model): Ollama 0.23.4 too old to load gemma3 arch; user-space
  0.30.8 gated by driver 535/CUDA 12.2 (same wall as qwen3-coder). NOT a VRAM/storage issue — model
  is pulled (24 GB) and fits; needs an admin driver upgrade. qwen3:32b is the correct control anyway.
- **Infra resurrected:** Qdrant server on `/home/22pf2/qdrant_storage` (fast_issues 1000, seed_309 2103,
  seed_361_mixtral 4940; patches empty, approved_enhanced_issues created on write-back). The
  `_offline_gemma` embedded store had only seed_* collections → RAG retrieval 404'd on `fast_issues`
  until the correct server store was mounted. Reward model + RAG retrieval validated working.
- **Selective enhancer:** reward gate scores originals; ~49% below threshold (enhanced w/ RAG), ~51%
  above (abstain → original = baseline-equivalent). So the arm's action concentrates on ~half the set.
- Result pending; will append the CL-Enhanced correctness column + McNemar vs baseline when done.

---

## 0a-FULL. 🔴🔴 FINAL n=382 CORRECTNESS VERDICT (2026-07-21) — NULL CONFIRMED AT FULL SCALE

Full dataset (382 issues, all node1-runnable images), **279 evaluable** (141 from n=200 + 138 from
new-182, 75.8% gold-probe coverage — the best yet). Metric = P2P resolved, fixed denominator,
McNemar exact. Artifact = `runs/stage6_new182_scores/FINAL_382_correctness.json`.
**NO comparison is significant (all p≥0.489). This is the terminal result — scale is exhausted.**

| solver (baseline resolved) | enh:openhands | enh:swe_agent | enh:aider |
|---|---|---|---|
| **openhands** 60/279 (22%) | 58 (−2) p=.910 | 66 (+6) p=.561 | 67 (+7) p=.489 |
| **swe_agent** 18/279 (6%) | 18 (0) p=1.0 | 19 (+1) p=1.0 | 19 (+1) p=1.0 |
| **aider** 124/279 (44%) | 125 (+1) p=1.0 | 119 (−5) p=.649 | 124 (0) p=1.0 |

- **Every single effect is within noise** (|Δ| ≤ 7 out of 279, all p > 0.48). No trend, no near-miss.
- **swe_agent baseline dropped from 12%→6%** as n grew — its earlier apparent success rate was itself
  partly small-n noise; discordant pairs are still ~0-1 per comparison (still essentially inert to enhancement).
- **Solver strength is the only thing that stayed rock-stable across every n** (100→200→382):
  aider ~44-45% ≫ openhands ~20-24% ≫ swe_agent 6-12%.
- **This is n=279 evaluable — more than enough power** to detect even a modest true effect (the n=100
  "trend toward significance" argument that justified scaling is now closed: doubling n moved effects
  toward zero, not toward significance).
- **CONCLUSION: LLM issue-enhancement (as implemented: openhands/swe_agent/aider enhancers,
  qwen3:32b) does not improve solver correctness at any tested scale.** The honest finding is
  (1) solver choice dominates outcome, (2) enhancement perturbs ~25-30% of outcomes with no net
  direction, (3) swe_agent is unusable with qwen3:32b regardless of enhancement.

---

## 0a. 🔴 FINAL n=200 CORRECTNESS VERDICT (2026-07-05) — enhancement effect is NULL [SUPERSEDED by n=382 above]

Combined 200-issue run (first-100 ⊕ new-100), **141 evaluable** (74+67). Metric = P2P resolved,
fixed denominator, paired **McNemar exact**. Artifact = `runs/stage6_new100_scores/FINAL_200_correctness.json`.
**NO enhancer×solver comparison is significant (all p>0.39); scaling 100→200 moved every effect TOWARD
null** — the opposite of a real effect. The n≤100 "signals" were sample noise.

| solver (baseline resolved) | enh:openhands | enh:swe_agent | enh:aider |
|---|---|---|---|
| **openhands** 31/141 (22%) | 34 (+3) p=.749 | 31 (0) p=1.0 | 37 (+6) p=.430 |
| **swe_agent** 17/141 (12%) | 17 (0) p=1.0 | 17 (0) p=1.0 | 17 (0) p=1.0 |
| **aider** 64/141 (45%) | 66 (+2) **p=.856** | 70 (+6) p=.405 | 70 (+6) p=.392 |

- **Headline (openhands-enh → aider) is dead:** +4 at n=100 (p=.388) → **+2 at n=200 (p=.856)**.
- **openhands-enh → openhands REVERSED across halves** (first +6, new −3 → pooled +3, p=.749).
- **swe_agent totally inert to enhancement** (0 discordant pairs in every comparison — it `exit_error`s
  before the problem text matters).
- **What IS robust:** solver strength (aider 45% > openhands 22% > swe_agent 12%), stable across both halves.
- **Enhancement perturbs without helping:** 14–23 discordant pairs per comparison, ~symmetric → real
  behavioral change, no net correctness gain. Ceiling effect where baseline is already high (aider).
- **Recommendation: DO NOT run the 382** — null already, effects trending wrong way; scale is not the
  missing ingredient. Pivot = better solver model (qwen3:32b handicaps openhands/swe_agent) or stronger enhancement.

---

## 0b. ⭐⭐ STAGE 6 CORRECTNESS — 100 issues (2026-06-30, qwen3:32b) [SUPERSEDED by §0a at n=200]

Gold-probe gate: **74/100 evaluable** (59 v2-targeted + 15 v3-label-agnostic) — coverage up from
55% on sample20. Metric = **P2P resolved** (solver patch + test_patch applied; P2P tests pass;
empty/failed patch = unresolved). **FIXED denominator = evaluable set** (74 / val-33 / new-41).
Directional, not definitive (P2P-only, not full F2P). Artifact = `runs/stage6_100_scores/correctness_recovered.json`.

| state \ solver | openhands | swe_agent | aider |
|---|---|---|---|
| baseline      | 15/74 (20%) | 9/74 (12%) | 30/74 (41%) |
| enh:openhands | **21/74 (28%)** | 9/74 (12%) | **34/74 (46%)** |
| enh:swe_agent | 16/74 (22%) | 9/74 (12%) | 33/74 (45%) |
| enh:aider     | 15/74 (20%) | 9/74 (12%) | 31/74 (42%) |
| **total**     | 67/296 | 36/296 | 128/296 |

- **Solver strength holds under correctness:** aider 43% > openhands 23% > swe_agent 12%.
- **enh:openhands is the best enhancer for BOTH solvers** — aider 30→34 (+4, 41→46%) AND openhands
  15→21 (+6, 20→28%). enh:swe_agent/enh:aider help little or not at all.
- **Headline (openhands-enh → aider) under correctness:** val 8→10, new 22→24, combined 30→34 (+4).
  Real & positive, modest. (Earlier n=11 pass showed 2→4 "doubling" — that was tiny-n noise; +4/74 here is the reliable read.)
- **swe_agent flat 9/74** — same few issues regardless of enhancement (the exit_error mismatch).
- **Method note:** scorer relative-output-dir bug wrote reports under `evaluation/` (fixed in
  `run_stage6_combined_100.py`; results recovered from there). Empty patches produce no report → counted unresolved.

**⚠️ Significance (McNemar exact, paired, n=74 — `stage6_100_stats.json`): NO comparison reaches
p<0.05.** Headline aider 30→34 p=0.388 (discordant b=4,c=8); openhands 15→21 p=0.286 (b=8,c=14);
best trend = openhands solver on the new-41 subset 7→14, p=0.118. **The effect is directional &
consistent but UNDERPOWERED at n=74** — discordant pairs are too few. A significant claim needs more
data (≈300 issues if the effect size holds) — this is the case FOR scaling.

**F2P NOT viable** with current labels: only **4/74** instances have usable FAIL_TO_PASS labels in the
gold reports (rest are stale/empty), and v3's 15 are label-agnostic. Full F2P needs the heavy
label-repair pass (re-derive F2P/P2P from execution), not a quick rescore. P2P (directional) stays the metric.

---

## 0. ⭐ FINAL 100-issue matrix (2026-06-29, qwen3:32b, non-empty patches)

Built from the **corrected validated-50** (`rerun_slow50_20260625` slow solvers @ workers=4 +
original valid aider) **⊕ clean new-50** (`matrix100_new50_20260626`, full matrix, with both
artifact recoveries applied). Artifact = `runs/matrix100_new50_20260626_200219/FINAL_100_matrix.json`.

| state \ solver | openhands | swe_agent | aider |
|---|---|---|---|
| baseline      | 33/100 | 13/100 | 56/100 |
| enh:openhands | 42/100 | 13/100 | **70/100** |
| enh:swe_agent | **43/100** | 13/100 | 67/100 |
| enh:aider     | 34/100 | 13/100 | 65/100 |
| **total**     | 152/400 | 52/400 | **258/400** |

- **Solver strength:** aider 64.5% > openhands 38% > swe_agent 13%.
- **Headline (openhands-enh → aider):** validated-50 **18→29 (+61%)**, new-50 **38→41 (+8%)**,
  combined **56→70 (+25%)**. Effect tracks **baseline headroom** (new-50 aider baseline already
  76% → little room). All enhancements help aider.
- **Two artifacts found & fixed in new-50 (do NOT trust raw new-50 numbers):**
  1. **openhands `0600`** — runtime container flushed `oh_solution.patch` 0600/own-UID, unreadable
     to host (~2%). Recovered 3/3 via root-Docker read. **Fix:** `openhands_solver.py` now has a
     root-read fallback.
  2. **aider workers=8 timeouts** — on heavier new-50 repos aider starved on Ollama contention →
     27 cells hit the 3600s wall (artifact, not failure). Re-solved @ workers=4 → 20/27 recovered
     (median 881s, 1 genuine timeout). **Fix:** `SOLVER_WORKERS` aider 8→4.
- **swe_agent stuck ~13%:** ~86% of runs end in **`exit_error`** (qwen3:32b can't reliably drive
  SWE-agent's strict ACI command format) — model↔harness mismatch, NOT issue difficulty. Flat
  across enhancement because the failure is in the agent protocol, not the problem text.
- **Caveat:** non-empty-patch rate, not correctness. Stage-6 on the 100 is the next step.

---

## 1. At-a-glance

| Node | Right now | Detail |
|---|---|---|
| **docjk-gpu-01** | ⚪ IDLE (50-run done; disk cleaned) | **50-issue matrix done** (06-20 15:38, 20.7 h, workers=8). aider **97/200**, openhands **6/200**, swe_agent **0/200** — slow solvers collapsed under workers=8 timeouts (see §3b). **Stage-6 evaluability lifted 30%→55%** via multi-method (§3a). ⚠️ disk hit 100% near the end (50 distinct runtime images > guard) — cleaned to 170 GB; the Docker→/home move is now required for ≥50-issue runs. |
| **docjk-gpu-02** | 🟢 **Part-1 1450 Stage-1-3 pass RUNNING** | ~chunk 14/677; ~5–7 days; rebuilding node2 images. 127-image build for Node 01 **PAUSED at 3/127** (resumable) |
| Private Ollama (both) | qwen3:32b, `:11435` | Node 01 GPUs 3,4,5,7; Node 02 GPUs 1–7. `UNTIL=Forever`, stable. qwen3-coder blocked (driver). |
| Disk / swap (Node 01) | 319 GB free / swap 1.0 GB | healthy; no leak |

---

## 2. Process inventory (with dates/times)

### docjk-gpu-01 (Node 01)
| Process | Script | Period (UTC) | Status |
|---|---|---|---|
| 3-issue matrix health-check | `run_matrix_test.py` (`matrix_health`) | 06-17 00:31 → 05:36 (5.09 h) | ✅ done |
| 10-issue matrix **batch 1** | `run_matrix_test.py` (`matrix20_node01`) | 06-17 08:25 → 15:42 (7.29 h) | ✅ done |
| 10-issue matrix **batch 2** | `run_matrix_test.py` (`matrix20_node01_batch2`) | 06-17 17:52 → 06-18 03:18 (9.44 h) | ✅ done, 12/12 |
| 127 missing-image build | `build_node1_missing127.py` | 06-17 02:46 (started) | ⏹ stopped — moved to Node 02, now paused there at 3/127 |

### docjk-gpu-02 (Node 02)
| Process | Period (UTC) | Status |
|---|---|---|
| 3-issue matrix health-check (mirror) | 06-17 01:45 → 05:11 (3.44 h) | ✅ done |
| Node 01 127-image build (offloaded) | started, then stopped | ⏸ paused at **3/127** (resumable; 3 on NFS) |
| Node 02 own 1450 Stage-1-3 pass | running | 🟢 ~chunk 14/677, ~5–7 days |

---

## 3b. 50-issue matrix (non-empty patches, workers=8) — methodology caveat
aider **97/200 (48%)**; openhands **6/200**; swe_agent **0/200**. The slow iterative solvers
**collapsed under workers=8** (sequential LLM calls starved → 1800 s timeouts → empty), so their
50-issue numbers are NOT comparable to the n≤20 (workers=2) runs. aider (fast) is unaffected and
**reconfirms the signal: openhands-enhancement helps aider** — aider baseline 18/50 → enh:openhands
**29/50** (+61%). Robust across n=10 (6→9), n=20 (14→16), n=50 (18→29).

## 3a. ⭐ STAGE 6 — real correctness scoring + **evaluability lifted 30%→55%**
**Multi-method evaluability gate (2026-06-20):** the dataset's offline F2P/P2P node-IDs are often
wrong, so coverage was lifted from **6/20 (30%) to 11/20 (55%)** by combining three test methods
(per-instance, whichever passes gold): v2 (real validated commands), v3 (label-agnostic file-level),
v1 (generic). Fixed django/pgcli/atlassian via v3. Remaining ~45% are fundamental (skip-only tests:
bleak/fsspec; uv/heavy envs: mjlab/torchgeo; unresolved fails). Method map: `stage6/evaluable_methods.json`.

**Correctness matrix on the 11-instance evaluable subset (per-instance gold-validated method):**

| state \ solver | openhands | swe_agent | aider |
|---|---|---|---|
| baseline | 0/11 | 1/11 | 2/11 |
| enh:openhands | 0/11 | 1/11 | **4/11** |
| enh:swe_agent | 0/11 | 1/11 | 1/11 |
| enh:aider | 0/11 | 1/11 | 1/11 |
| **solver total** | 0/44 | 4/44 | **8/44** |

**openhands-enhancement DOUBLES aider correctness (2→4/11)** — the strongest, most consistent
result of the study. aider best overall (8/44); openhands solver 0/44 (its patches don't pass);
swe_agent flat. Tooling: `scripts/evaluate/run_stage6_combined.py`.

**(earlier) First correctness scoring on the original 6 evaluable:**

| state \ solver | openhands | swe_agent | aider |
|---|---|---|---|
| baseline | 0/6 | 1/6 | 2/6 |
| enh:openhands | 0/6 | 1/6 | **3/6** |
| enh:swe_agent | 1/6 | 1/6 | 2/6 |
| enh:aider | 0/6 | 1/6 | 1/6 |
| **solver total** | **1/24** | **4/24** | **8/24** |

**Findings (real correctness, not just "patch exists"):**
- **aider solver strongest** (8/24) — consistent with the non-empty matrix.
- **Best combo = openhands-enhancement → aider solver (3/6)** vs baseline aider 2/6 — same
  directional signal as n=20 non-empty (openhands-enhancement helps aider).
- **openhands solver collapses** under real scoring (1/24): it writes patches that mostly
  don't pass tests — "non-empty patch" badly overstated it (was 5/40 non-empty).
- Absolute resolved rates are **low** (best 50%, most 0–33%); real fixing ≪ patch generation.
- **n is tiny (6)** and metric is P2P-only (no-regression + de-facto correctness via test_patch),
  so treat as directional, not definitive. Tooling: `scripts/evaluate/run_stage6_p2p.py`.

## 3. Results so far (Part 2 — non-empty patches per condition, qwen3:32b)

### ⭐ Node 01 — **20-sample set** (batch 1 + batch 2) — headline result, /20
| state \ solver | openhands | swe_agent | **aider** | row /60 |
|---|---|---|---|---|
| baseline | 5/20 | 2/20 | 14/20 | 21 |
| enh:openhands | 5/20 | 2/20 | **16/20** | 23 |
| enh:swe_agent | 5/20 | 2/20 | 14/20 | 21 |
| enh:aider | 4/20 | 2/20 | 15/20 | 21 |
| **solver total** | **19/80 (24%)** | **8/80 (10%)** | **59/80 (74%)** | 86/240 |

**n=20 findings:** (1) **Solver choice dominates** — aider 74% ≫ openhands 24% ≫ swe_agent 10%.
(2) **Enhancement effect is small** at n=20 (baseline 21/60 vs best enhanced 23/60); the only
consistent gain is **openhands-enhancement → aider solver (14→16/20)**. (3) openhands solver flat
under enhancement; swe_agent solver uniformly weak. **Caveat:** metric = *non-empty patch*, not
*correct fix* — enhancement may matter more for correctness, which needs **Stage 6 F2P/P2P scoring**.

### Node 01 — **10 issues** (batch 1) · component of the 20-set
| state \ solver | openhands | swe_agent | **aider** |
|---|---|---|---|
| baseline | 2/10 | 1/10 | 6/10 |
| enh:openhands | 1/10 | 1/10 | **9/10** |
| enh:swe_agent | 1/10 | 1/10 | 7/10 |
| enh:aider | 1/10 | 1/10 | 6/10 |
| **solver total** | 5/40 (12.5%) | 4/40 (10%) | **28/40 (70%)** |

### Node 01 — 3 issues (earlier health-check)
| state \ solver | openhands | swe_agent | aider |
|---|---|---|---|
| baseline | 2/3 | 0/3 | 1/3 |
| enh:openhands | 1/3 | 0/3 | 1/3 |
| enh:swe_agent | 0/3 | 0/3 | 1/3 |
| enh:aider | 1/3 | 0/3 | 1/3 |

### Node 02 — 3 issues (different issues; mirror health-check)
| state \ solver | openhands | swe_agent | aider |
|---|---|---|---|
| baseline | 0/3 | 1/3 | 2/3 |
| enh:openhands | 2/3 | 1/3 | 2/3 |
| enh:swe_agent | 1/3 | 1/3 | 3/3 |
| enh:aider | 1/3 | 1/3 | 3/3 |

**Consistent findings (both nodes):** all 3 enhancers work (≈9–10/10 truly-enhanced);
all 3 solvers run with **0 crashes**; **aider solver is strongest**; **openhands
enhancement boosts the aider solver** (Node 01: 6/10 → 9/10); **swe_agent solver is
functional but low-yield** (~1 in 10). Resources flat, no process leaks.

> **Caveat:** n is small and the two nodes used *different* issue sets, so cross-node
> yield differences reflect issue difficulty, not node quality. The 20-sample set
> (batch 1 + batch 2) will give the first n=20 read.

---

## 4. The 20-sample set ✅ COMPLETE (results in §3)

20 issues = **batch 1 (done)** ∪ **batch 2 (running)**, and it contains all 6 merged
samples (3 Node 01 + 3 Node 02) + 14 node1 issues.

- **batch 1 (10):** huggingface/datasets-7743, codingjoe/django-health-check-562,
  flet-6298, titiler-1282, chardet-365, chonkie-496, bleak-1924, dask-11988, pgcli-1513,
  outlines-1674.
- **batch 2 (10):** modelscope/evalscope-1160, mujocolab/mjlab-435, torchgeo-3185 (the 3
  restored Node-02 samples) + outlines-1726, sentry-python-4644, sqlmesh-4847,
  filesystem_spec-1991, atlassian-python-api-1638, chardet-347, datasets-7823.

Both batches done → merged **20-sample analysis is in §3** (per-solver totals + n=20 enhancement
effect). Node 01 idle since 06-18 03:18 UTC.

---

## 5. Stage 1-3 image inventory

- **Node 01:** 417 `pouya/stage2_2026` images local (383 node1-runnable + the 3 restored
  Node 02 samples + others). **127 node1 issues still lack images** (being rebuilt on Node 02).
- **NFS `stage2_image_backups/`:** **132 tarballs** persisted (shared, restorable on either node).
- **Node 02:** rebuilding its node2 images via the 1450 pass (1450 candidates → 964 S1 →
  963 S2/S3 validated; ~128 currently have a usable image, rest being rebuilt).

---

## 6. Open decisions / action items

1. **127 missing node1 images — re-sequence Node 02? → NO (agreed).** Not on the critical
   path; let Node 02 finish its 1450 pass (~5–7 days), then resume the 127-build (skips the
   3 already on NFS). Restore on Node 01 when needed via `backup_stage2_images.py restore`.
2. **qwen3-coder:30b comparison — BLOCKED** on both nodes (driver 535 / CUDA 12.2). Needs an
   **admin NVIDIA-driver upgrade** to run the MoE arch; until then use a dense code model.
3. **Docker data-root on `/home`** (permanent disk fix) — still pending admin; needs root.

---

## 7. Next steps (proposed)
- Finish batch 2 → deliver the **20-sample merged analysis**.
- Then either (a) scale to ~50 issues for statistical power on the aider+enhancement effect,
  or (b) wire **Stage 6 full SWE-bench F2P/P2P scoring** (currently health = non-empty patch).
- Decision pending from PI on (a) vs (b).
