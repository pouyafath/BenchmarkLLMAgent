# Executed FAIL_TO_PASS labels, and what they do to the results (2026-09-01)

## The problem

Every instance in the 279-issue evaluable set carried
`f2p_p2p_derivation.method == "offline_test_patch_diff_parse"`. The FAIL_TO_PASS and
PASS_TO_PASS labels were read off the test patch's diff and never executed. The rows say
so: *"P2P>0 required; F2P not required. F2P stored for reference only."*

The damage was measurable before re-running anything:

| check | result |
|---|---|
| F2P-labelled tests appearing in the recorded `test_status` | 17 of 1210 |
| instances where the labelled F2P set matched observed failures | 49 of 279 |

Because F2P could not be trusted, the paper reported **P2P-resolved** (no regression).
That criterion credits a patch that never applied: the repository is untouched, the P2P
suite stays green, and the instance scores as solved.

## What was done

A test's class is a behaviour, not a diff:

    F2P = fails at base+test_patch, passes at base+test_patch+gold
    P2P = passes at base+test_patch, passes at base+test_patch+gold

The second half was already on disk. The gold probe had run base+test_patch+gold for all
279 instances under each one's assigned method and left a parsed per-test `status.json`
(verified: 279/279 present for the assigned method). Only the PRE half was missing, so the
job cost 279 container runs rather than 558.

`scripts/evaluate/derive_f2p.py` runs PRE through the same harness with a sentinel patch
that `git apply` rejects, leaving the tree at base+test_patch. An *empty* patch does not
work: `run_instances()` filters those out and starts no container, which produced 0/279 on
the first attempt while exiting 0.

## Result: the labels were largely fictional

| | offline (diff-parsed) | executed |
|---|---:|---:|
| instances with >=1 F2P test | 225 | **85** |
| agreement between the two sets | | **45 / 279** |

## Effect on the headline numbers

Rescoring reuses the per-test `status.json` the harness already wrote, so it costs no
containers. Strictly resolved = every executed F2P test passes and every executed P2P test
passes.

**Main matrix** (`scripts/analysis/strict_matrix_279.py`), on instances that are both
gradeable and still have artifacts:

| solver | published (P2P dispatch) | executed F2P |
|---|---:|---:|
| OpenHands, 4 arms | 15 | **0** |
| Aider, 4 arms | 27 | 25 |
| total | 42 | **25** (1.7x) |

Aider's solves are genuine fixes; the criterion barely flatters it. **Every one of
OpenHands' 15 credited solves is an artifact of the no-regression criterion.** The
solver-capability gap the paper reports is therefore understated, not overstated.

**Run-4** (append-only), 30 gradeable of 80: 35 published solves become 14 (2.5x).

## Enhancement stays null under the stricter criterion

| | baseline | enhanced | delta | McNemar |
|---|---:|---:|---:|---|
| main matrix, 6 cells | 21 | 18 | -3 | p=0.453 |
| run-4, 9 cells | 12 | 10 | -2 | p=0.688 |

No cell reaches significance under either criterion. The metric change does not rescue
the hypothesis.

## Caveats

* **85 of 279 instances are strictly gradeable.** The rest have no executed fail->pass
  test, so they cannot be scored on fixing at all.
* **The first 100-issue tranche cannot be rescored.** Its scoring artifacts were lost and
  recovered only as booleans, not per-test status. Cells report their own n.
* **The old labels fail in both directions.** Besides over-crediting unapplied patches,
  4 instances have an *empty* P2P label list while 18-33 tests actually ran and passed, so
  `len(success)>0` marks them unresolved. Comparisons must use the published dispatch
  (v3 -> label-agnostic log, else report.json), not a naive report.json read.
* Two run-4 instances had no F2P test in their solver status. Both were checked by hand:
  one collected zero tests, one broke collection. Both are genuine failures.

## Artifacts

| path | contents |
|---|---|
| `data/stage6_all279_f2p_derived.json` | executed F2P/P2P labels, 279 instances |
| `data/stage6_f2p_evaluable_85.json` | the 85 strictly gradeable instance ids |
| `runs/f2p_rederive/pre/` | PRE per-test status, 279 instances |
| `data/stage6_strict_matrix_279.json` | strict matrix cells |
| `data/stage6_run4_appendonly_cells.json` | run-4 per-cell results (both criteria) |
| `runs/f2p_rederive/`, `runs/stage6_run4_appendonly/` | raw harness output (gitignored) |
