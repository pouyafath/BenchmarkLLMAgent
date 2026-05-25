# P2P Failure Analysis — Approach B (Regression Guard v1)

**Date**: 2026-04-14  
**Dataset**: 50 SWE-bench-Live issues, Devstral-24B + code-context + test_patch  
**Approach B**: 27/50 F2P (54%), 4/50 P2P (8%), 1/50 resolved (2%)  
**Scope**: 26 instances that fix the bug (F2P ✓) but break regression tests (P2P ✗)

---

## Severity Distribution

| Category | Count | Description |
|----------|:-----:|-------------|
| **CATASTROPHIC** (>70% fails) | 23 | Patch breaks vast majority of existing tests |
| **PARTIAL** (30-70% fails) | 1 | `geopandas-3513`: 635/2353 tests fail |
| **MAJORITY** (5-30% fails) | 1 | `instructlab-615`: 6/12 tests fail |
| **NEAR_MISS** (<5% fails) | 1 | `litellm-10198`: 8/425 tests fail (98.1% pass) |

## Root Cause Categories

### Category 1: Core Function Modification (15/26, ~58%)
The solver modifies a shared/core function that thousands of tests invoke. The fix is correct for the target bug but changes behavior broadly.

**Examples**:
- `keras-19937`: Modified `standardize_dtype()` in `variables.py` — used by every Keras test (7106 failures)
- `conan-17292`: Changed 1 line in `cmake.py` (`njobs` → `maxcpucount`) — breaks 4075 tests
- `pdm-3191`: Wrapped `resolve_from_lockfile()` in `list()` — breaks 903 tests
- `sphinx-11888`: Added `sorted()` to dictionary iteration — breaks 1985 tests

**Pattern**: These changes ARE correct but introduce subtle behavioral changes (different ordering, type coercion, timing) that cascade.

### Category 2: Broad API/Output Changes (6/26, ~23%)
The solver's fix changes output format, error messages, or API signatures that tests assert on.

**Examples**:
- `pypa__twine-1112`: Changed URL parsing to include port — 162 tests check URL format
- `aws-cloudformation__cfn-lint-*` (3 instances): Rule modifications break ~1000 tests each
- `matplotlib-*` (2 instances): Rendering/output changes break 7000+ tests

### Category 3: Infrastructure Side Effects (3/26, ~12%)
The fix adds code that has unintended side effects on test infrastructure.

**Examples**:
- `home-assistant-5701`: Added `.git` directory check — breaks mock-based tests
- `deepset-ai__haystack-7362`: Modified pipeline component — breaks 1156 tests
- `instructlab-615`: Added duplicate error message — 6/12 tests check output

### Category 4: Near-Miss (1/26, ~4%)
- `BerriAI__litellm-10198`: 413-line patch, only 8 test failures in `test_url_with_format_param` — a specific edge case in URL formatting.

## Key Insight

> **The solver fixes bugs correctly but doesn't verify its patches against existing tests.**

Despite Approach B's regression guard prompt instructing the solver to "run the project's test suite," the solver appears to **skip this step** — likely hitting the step limit or finding test execution too complex. The 250-step limit and 60-second timeout per command mean:

1. Most test suites take >60s to run, causing timeouts
2. The solver uses many steps for exploration/fixing, leaving few for test verification
3. When the solver does run tests, it may not know which tests are relevant

## Actionable Improvements for v2

### High-Impact (prompt engineering)
1. **Explicit test command discovery**: Instruct solver to find and run tests BEFORE making changes (pre-patch baseline)
2. **Focused test scope**: Run only tests in modified module, not entire suite
3. **Mandatory verify step**: Require solver to test BEFORE generating patch
4. **Minimality enforcement**: "Change the fewest lines possible"

### Medium-Impact (configuration)
5. **Increase timeout**: 60s → 300s for test execution commands specifically
6. **Increase step limit**: 250 → 300+ to allow test verification phase

### Low-Impact (already tried)
7. ~~List P2P test names~~ (Approach A: no effect)
8. ~~Retry with failure info~~ (Approach C: counterproductive)

## Patch Size vs P2P Failure Correlation

| Patch Size | Count | Avg P2P Failures |
|-----------|:-----:|:----------------:|
| Small (≤30L) | 12 | 2,534 |
| Medium (31-80L) | 11 | 2,940 |
| Large (>80L) | 3 | 422 |

Counterintuitively, **smaller patches cause more P2P failures** — because small changes to core functions have the largest blast radius. Larger patches tend to be more targeted (e.g., litellm's 413L patch only breaks 8 tests).
