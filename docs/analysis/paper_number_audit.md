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

## Table 1 fully verified (2026-08-28) ✔

The 74 instances were recovered (`scripts/evaluate/recover_74.py`, Docker only) and the complete
279-instance outcome set rebuilt. **Every cell of Table 1 reproduces exactly**, and so does every
McNemar p-value:

| Solver | baseline | enh:openhands | enh:swe_agent | enh:aider |
|---|---:|---:|---:|---:|
| OpenHands | 60 ✔ | 58 ✔ | 66 ✔ | 67 ✔ |
| SWE-agent | 18 ✔ | 18 ✔ | 19 ✔ | 19 ✔ |
| Aider | 124 ✔ | 125 ✔ | 119 ✔ | 124 ✔ |

McNemar exact p, recomputed from the discordant pairs: .910 / .561 / .489 (OpenHands),
1.000 / 1.000 / 1.000 (SWE-agent), 1.000 / .649 / 1.000 (Aider) — **identical to the published
values in all nine comparisons.**

The recovery is also self-validating: it independently produced 15 OpenHands and 30 Aider resolves
on the 74, exactly the counts implied by subtracting the 205-instance subset from Table 1.

**Conclusion: the paper's headline table is sound.** The discrepancy chased earlier in this audit
was entirely an artifact of my own partial reconstruction, never of the paper.
