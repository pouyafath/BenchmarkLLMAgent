# RQ3 Codebook — open-coding agent-generated issue enhancements

Two coders label each row **independently**, then reconcile. Report Cohen's kappa per
dimension and a pattern x outcome cross-tabulation.

## Dimension A — enhancement patterns (all that apply)
- `A1_restructure`   Reorganised into Problem / Reproduction / Expected / Actual sections
- `A2_root_cause`    Appended a root-cause hypothesis or diagnosis
- `A3_trace`         Extracted or surfaced a stack trace / error output
- `A4_code_context`  Added code context (file paths, symbols, snippets)
- `A5_repro_steps`   Added or reformatted reproduction steps
- `A6_env`           Added environment / version information
- `A7_none`          No substantive change

## Dimension B — failure modes (all that apply)
- `B1_hallucinated`  States specifics not derivable from the original or repo
- `B2_overspecified` Commits to one narrow reading, foreclosing others
- `B3_signal_loss`   Drops or buries information present in the original
- `B4_abstained`     Returned the original essentially unchanged
- `B5_none`          No failure mode observed

## Outcome (pre-filled, do not edit)
`helped` = unresolved at baseline, resolved after enhancement;
`hurt` = resolved at baseline, unresolved after; `unchanged` = same either way.
Solver held fixed at OpenHands; model held fixed at Qwen3-32B.

## Note on the auto_* columns
Regex-derived cues to speed reading. They are a prior, not ground truth — code what the
text actually shows and overrule them freely.
