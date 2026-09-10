# Reproducing the paper's numbers

Every table, figure and inline statistic in the manuscript, mapped to the artifact that
holds it and the command that regenerates it. Nothing here needs a GPU or an API key; the
analyses run from stored results. Only the two rows marked **Docker** re-execute containers.

## Layout

| Path | Contents |
|---|---|
| `data/stage6_all279_v{1,2,3}.jsonl` | The 279 gold-evaluable instances under each of the three test-command methods. 42 MB total, so distributed in the archive rather than in git. |
| `data/stage6_all279_methods.json` | Which method's gold probe validated each instance. Selects the dataset per instance. |
| `data/stage6_all279_f2p_derived.json` | Executed FAIL_TO_PASS / PASS_TO_PASS labels for all 279. |
| `data/stage6_f2p_evaluable_85.json` | The 85 instances carrying a real fail-to-pass test. |
| `data/stage6_*_result*.json`, `data/stage6_*_cells.json` | Per-condition scored outcomes, one entry per instance. |
| `scripts/evaluate/` | Scoring. Talks to Docker. |
| `scripts/analysis/` | Statistics. Reads stored results only. |

`runs/` holds raw harness output and is gitignored: it is ~200 GB and regenerable.

## Claim to artifact

| Paper | Artifact | Regenerate with |
|---|---|---|
| Fig. 3, pipeline funnel | counts in `docs/analysis/f2p_rederivation_2026-09-01.md` | figure is TikZ, inline in the `.tex` |
| Table 1, correctness matrix | `runs/stage6_*_scores/` | `scripts/evaluate/score_sample.py` **Docker** |
| Table, scale-up replication | `data/stage6_rerun_cells_summary.json` | `scripts/evaluate/score_missing_cells.py` **Docker** |
| RQ2 feature deltas | `scripts/analysis/rq2_feature_deltas.py` | `bench_env/bin/python scripts/analysis/rq2_feature_deltas.py` |
| RQ2 logistic regression | `scripts/analysis/rq2_logreg.py` | `bench_env/bin/python scripts/analysis/rq2_logreg.py` |
| RQ2 reward model | `scripts/analysis/rq2_rewardmodel.py` | `bench_env/bin/python scripts/analysis/rq2_rewardmodel.py` |
| Append-only matrix | `data/stage6_run4_appendonly_cells.json` | `bench_env/bin/python scripts/analysis/analyse_run4.py` |
| Table, executed fix criterion | `data/stage6_strict_all_conditions.json` | `bench_env/bin/python scripts/analysis/strict_rescore_all.py` |
| Executed F2P labels | `data/stage6_all279_f2p_derived.json` | `scripts/evaluate/derive_f2p.py pre` **Docker**, then `combine` |
| Replication of the protective effect | `data/stage6_replication80_result.json`, ids in `..._ids.json` | pre-registration in `docs/analysis/replication_prereg_openhands_aider.md` |
| Resample null (0.199 / 0.408) | `docs/analysis/why_enhancement_fails_and_what_could_work.md` | `bench_env/bin/python scripts/analysis/verdict.py` |

## The two claims worth checking first

A reviewer with limited time should check these, because they are the ones that decide
whether the negative result stands.

**The enhancement effect is indistinguishable from re-running the solver.**

```bash
bench_env/bin/python scripts/analysis/analyse_run4.py
```

Prints each cell's rescue and breakage counts beside what a resample predicts. The six
responsive cells pool to 165 -> 164, with a rescue rate of 0.187 against a chance 0.199.

**Changing the metric to a real fix criterion does not change the finding.**

```bash
bench_env/bin/python scripts/analysis/strict_rescore_all.py
```

Prints all 16 comparisons under the executed labels: 75 -> 66 over 738 paired trials, none
significant. The same script shows the criterion falling unevenly on the solvers, which is
the finding in the table of Section "Executing the fix criterion".

## Re-running the Docker parts

The scoring harness needs the per-instance images (`pouya/stage2_2026:<instance_id>_linux`)
and roughly 200 GB of disk. Container evaluations dominate the runtime: scoring one
80-instance cell takes 30-90 minutes at four workers, and the full re-derivation of the
executed labels took 279 container runs.

```bash
# executed F2P labels: pre-gold half, then combine with the stored gold probe
bench_env/bin/python scripts/evaluate/derive_f2p.py pre
bench_env/bin/python scripts/evaluate/derive_f2p.py combine
```

Two things will otherwise cost you a day each. The harness silently drops any instance
whose predicted patch is empty, so a no-op run needs a non-empty sentinel that `git apply`
rejects rather than an empty string. And a single hung evaluation blocks everything
downstream, which is why `HARNESS_TIMEOUT` (default 5400s) exists.

## What is not reproducible from this package

The solver and enhancer runs themselves. They need a served Qwen3-32B, roughly 14 hours per
80-instance two-arm cell, and they are stochastic: we did not fix seeds inside the agent
loops, so a re-run reproduces the distribution rather than the exact patches. This is why
every comparison in the paper is paired and why run-to-run variance is quantified against a
measured resample rate rather than assumed away. The stored patches are in the archive, so
the scoring and all statistics are exactly reproducible from them.
