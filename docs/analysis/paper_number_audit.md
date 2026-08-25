# Reproducibility audit — paper numbers vs. data (in progress, 2026-08-25)

Verifying every quantitative claim in the draft against the underlying artifacts, ahead of the
rewrite. Status: partial — several checks are blocked behind a data recovery (see bottom).

## Verified ✔

| Claim (paper) | Source | Result |
|---|---|---|
| RQ2 reward model: **218/382** reports improve | `runs/cl_enhanced_scores/rq2_rewardmodel.json` (`improved: 218`, `n: 382`) | ✔ exact |
| RQ2 intrinsic **AUC = 0.49** (chance) | same file (`auc_threshold: 0.4943`) | ✔ exact |
| RQ2 **122 (32%)** cross low→high | 32% of 382 = 122 | ✔ consistent |
| Table 1 denominators (279 evaluable) | `.secrets/evaluable_279.txt` = 279 ids | ✔ |
| Solver tool access / 30-step loop | run logs + image inspection | ✔ (see `agent_tool_access_audit.md`) |

## Discrepancies found and resolved ✔

- **My own reconstruction, not the paper, was wrong.** A merged outcome set included
  `runs/stage6_100_scores`, whose matrix is all-zero (a failed scoring pass), adding 74 phantom
  always-unresolved rows. 205 + 74 = 279 exactly; the paper's Table 1 correctly credits those 74
  with 15 OpenHands and 30 Aider resolves. Corrected in
  `why_enhancement_fails_and_what_could_work.md`.
- **Two subsets coexist for the reward-model analysis.** `runs/analysis_quality.json` is computed
  on **279** (enh mean 0.576); the paper's counts come from the **382** run (`rq2_rewardmodel.py`
  loads `matrix_sample382_node01.jsonl`). The paper's 218/382 and AUC 0.49 verify exactly against
  the 382 file.

## Open — worth one check during the rewrite

- The paper pairs **"0.473 → 0.578"**. The 279-based file gives 0.473 → **0.576**. The counts
  (218/382) clearly come from the 382 analysis, so 0.578 is presumably the 382-based mean — but the
  two means should be confirmed to come from the *same* subset rather than mixed.

## Blocked behind data recovery

Table 1's per-cell counts, per-cell Δ, and the McNemar p-values cannot be recomputed until the 74
instances are re-scored. Their solver outputs survive in
`runs/stage6_100_consol/qwen3_32b/stage5/` (12 conditions × 74 instances, 343 non-empty patches);
only the scoring artifacts were lost. Recovery is Docker-only, no API cost, and is queued behind
the currently-running experiments.
