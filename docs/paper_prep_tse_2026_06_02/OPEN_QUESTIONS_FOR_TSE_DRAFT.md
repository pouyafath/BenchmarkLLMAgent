# Open Questions For TSE Draft

Date: 2026-06-02

## High-priority Scope Decisions

1. Should the paper freeze on the current pilot40 slice, or wait for the next frozen Stage 3 export from Developer 03?
2. Is the paper primarily a benchmark-construction/methodology paper with pilot evidence, or a comparative enhancer-results paper?
3. Should historical tracks such as Pouya-20 be included in the main paper, moved to an appendix, or excluded from the main result narrative?
4. What exact stage naming will the paper use: "seven stages with Stage 0.5" or "eight labeled checkpoints"?
5. Is the central empirical claim simply "OpenHands gains one case on the accepted pilot40 slice," or does the team want a broader current-dataset comparison before drafting full prose?

## High-priority Method Questions

1. How will the paper justify the branch-specific P2P-gated resolved definition to reviewers who expect standard SWE-bench semantics?
2. Will the paper explicitly distinguish dataset-level `FAIL_TO_PASS_count` from validation-observed `stage3_fail_to_pass_observed_count`?
3. How will the under-documented `3,285 -> 3,229` operational export trim be described if no canonical producer script is recovered?
4. Should the organize-only source bug and workaround be discussed as an operational threat, or kept out of the main narrative?
5. Will live Node1/Node2 status appear only in a system-status paragraph, or also in a figure showing ongoing scale-out?

## High-priority Experiment Gaps

1. Is one accepted same-slice native enhancer enough for the paper, or does the team want at least one more real current-dataset native agent?
2. Is OpenClaw going to remain explicitly out of scope for this draft, or does the team want to defer drafting until a real OpenClaw integration attempt happens?
3. Does the team want additional solver paths on the same slice beyond the current mini-SWE-agent primary path and the single gpt-oss sensitivity run?
4. Should a larger validated slice be required before the main Results section is written in full prose?
5. Does the team want any human qualitative scoring of enhancement quality in addition to solving-as-evaluation?

## High-priority Analysis Gaps

1. What inferential statistics, if any, are appropriate for `40` paired baseline/enhanced instances?
2. Should the paper include confidence intervals around resolved-rate deltas?
3. Does the team want a more systematic error taxonomy beyond the one gained case and one OpenHands runtime outlier?
4. Should unchanged-enhancement coverage be elevated into a main result, given the large difference between `19/40` and `39/40`?
5. Is the gpt-oss `0/40` run a main-text result or an appendix-level sensitivity check?

## Medium-priority Presentation Questions

1. Should the paper explicitly include a figure showing the frozen-artifact boundary between RepoLaunch and downstream benchmarking?
2. Should the paper include both the full lineage funnel (`7,714 -> 3,285 -> 3,229 -> 2,950 -> 2,900`) and the pilot funnel (`48 -> 41 -> 40`)?
3. Should the real-versus-proxy agent inventory appear in the main paper or supplementary material?
4. How prominently should the `Diaoul__subliminal-1328` gained case be featured?
5. Should the paper frame `llm_append_analysis` as a baseline local enhancer, a framework-built enhancer, or both?

## Minimum Missing Items Before A Submission-quality Draft

1. A frozen decision on paper scope.
2. A resolved treatment of the next Stage 3 export question.
3. A statistics plan.
4. A figure/table plan.
5. Final wording boundaries for claims about scale, generality, and native-agent coverage.

