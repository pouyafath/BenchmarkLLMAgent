# Pouya-5 Native Enhancer Solver Comparison - 2026-05-09

This run passes the first five canonical Pouya-20 issues through the mini-SWE-agent solver after native CLI issue enhancement. It uses the corrected native enhancer artifact from `runs/native_cli_pouya5_20260509/`.

The goal is a pre-flight check before rerunning the full 20-issue native enhancer pipeline. This is not a full-performance result.

## Artifacts

| Artifact | Path |
|---|---|
| Summary JSON | `runs/pouya5_native_solver_comparison_20260509/summary.json` |
| Run report | `runs/pouya5_native_solver_comparison_20260509/ANALYSIS.md` |
| Enhanced solver datasets | `runs/pouya5_native_solver_comparison_20260509/datasets/*.jsonl` |
| Solver predictions | `runs/pouya5_native_solver_comparison_20260509/solver_runs/*/preds.json` |
| Evaluator outputs | `runs/pouya5_native_solver_comparison_20260509/eval_runs/*/` |

## Results

| Condition | Solver Inputs | Predictions | Enhancement Failures | Solver Missing | Empty Patches | Resolved / Evaluated | Effective Resolved / 5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 5 | 5 | 0 | 0 | 0 | 0/5 | 0/5 |
| `aider` | 5 | 5 | 0 | 0 | 0 | 0/5 | 0/5 |
| `trae` | 5 | 5 | 0 | 0 | 0 | 0/5 | 0/5 |
| `openhands` | 5 | 5 | 0 | 0 | 0 | 0/5 | 0/5 |
| `mini_swe_agent` | 5 | 5 | 0 | 0 | 0 | 0/5 | 0/5 |
| `swe_agent` | 5 | 5 | 0 | 0 | 1 | 0/5 | 0/5 |

All five native enhancers now produce valid enhanced issues and all five solver datasets produce predictions. The remaining technical caveat is `swe_agent` producing an empty solver patch for `PennyLaneAI__pennylane-7474`.

No enhancer improved the final `resolved` score on this five-issue subset.

## Why The Five Issues Failed

| Instance | Main Failure Pattern |
|---|---|
| `Flexget__Flexget-4986` | Every patch passes the 2 F2P tests but fails both P2P tests, so the solver fixes the reported behavior while breaking existing `exists_series` behavior. |
| `MDAnalysis__mdanalysis-5071` | All conditions still fail `test_dcd_writer_angle_cosines`; OpenHands additionally regresses `test_write_random_unitcell`. The generated DCD fixes are incomplete or wrong. |
| `MDAnalysis__mdanalysis-5113` | All conditions fail both F2P tests and both P2P tests for `sort_backbone`; patches add narrow error handling but do not implement the expected branch/circular handling. |
| `PennyLaneAI__pennylane-7474` | Aider, TRAE, and Mini-SWE-Agent eliminate all 5 F2P failures, but still fail 20 P2P tests for two-qubit decomposition. They overfit by changing decomposition behavior in a way that breaks existing 2-CNOT cases. OpenHands keeps the F2P failures. SWE-agent submits an empty patch. |
| `PennyLaneAI__pennylane-7668` | All solver patches still fail all 3 F2P tests and 5 P2P tests around drawer wire mapping. The patches touch plausible files but do not correctly preserve `default_wire_map` / `convert_wire_order` semantics. |

## Issue-Level Counts

| Instance | Baseline | Best Enhanced Signal |
|---|---|---|
| `Flexget__Flexget-4986` | F2P 2 pass / 0 fail, P2P 0 pass / 2 fail | No change across enhancers. |
| `MDAnalysis__mdanalysis-5071` | F2P 0 pass / 1 fail, P2P 1 pass / 0 fail | No F2P improvement; OpenHands worsens P2P. |
| `MDAnalysis__mdanalysis-5113` | F2P 0 pass / 2 fail, P2P 0 pass / 2 fail | No improvement. |
| `PennyLaneAI__pennylane-7474` | F2P 0 pass / 5 fail, P2P 1 pass / 20 fail | Aider, TRAE, and Mini-SWE-Agent reach F2P 5 pass / 0 fail, but still P2P 1 pass / 20 fail. |
| `PennyLaneAI__pennylane-7668` | F2P 0 pass / 3 fail, P2P 2 pass / 5 fail | No improvement. |

## Fixes Applied During This Pass

- SWE-agent enhancer now scans `history`, `trajectory`, `messages`, and `info.submission` trajectory schemas instead of only one schema.
- SWE-agent timeout handling now preserves a valid trajectory-produced enhancement when the CLI writes the enhancement but fails to call `submit` before timeout.
- TRAE and SWE-agent title cleanup no longer strips a leading backtick from titles like `` `draw_mpl` crashes...``.
- The solver comparison runner now retries missing predictions even when `preds.json` already exists.
- The comparison runner now distinguishes enhancement failures, solver-missing predictions, empty patches, and missing evaluator reports.

## Recommendation

The pipeline is technically ready for a full 20-issue data-collection run if empty patches are counted explicitly. Do not claim that native issue enhancement improves solving based on this pre-flight: the observed result is 0/5 for baseline and 0/5 for every enhanced condition.
