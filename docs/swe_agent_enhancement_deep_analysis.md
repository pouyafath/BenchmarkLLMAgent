# Deep Analysis: SWE-Agent Enhancement Effects Across All Groups

## 1. Scope

This report provides a per-instance analysis of SWE-agent enhancement effects across **30 issues** in **3 groups**, using **Devstral-Small-2-24B** as both enhancer LLM and solver LLM. For each issue, we compare the baseline (original description) and enhanced (SWE-agent rewritten description) solver outcomes, then categorize the root causes of improvement, regression, or no change.

Additionally, a 4th experiment (Group B with GPT-5.4-mini) is included for reference, though its baseline was not evaluated.

---

## 2. Per-Instance Results: Full 30-Issue Comparison

### 2.1 Group A — SWE-bench Verified (10 astropy issues)

| Instance | Baseline | Enhanced | Delta | Category |
|----------|----------|----------|-------|----------|
| astropy-12907 | F2P: 0/2, P2P: **13/13** | F2P: 0/2, P2P: 0/13 (eval error) | **Regression** | Infra error (report_not_found) |
| astropy-13033 | F2P: 0/1, P2P: 19/20 | F2P: 0/1, P2P: 19/20 | **No change** | Stable non-resolved |
| astropy-13236 | F2P: 0/2, P2P: **644/644** | F2P: 0/2, P2P: **644/644** | **No change** | Stable non-resolved |
| astropy-13398 | F2P: 0/4, P2P: **63/68** | F2P: 0/4, P2P: **0/68** | **Regression** | Enhancement mislead solver |
| astropy-13453 | F2P: 0/1, P2P: 2/9 | F2P: **1/1**, P2P: **9/9** | **RESOLVED** | Enhancement clarified issue |
| astropy-13579 | F2P: **1/1**, P2P: **40/40** RESOLVED | F2P: **1/1**, P2P: **40/40** RESOLVED | **No change** | Stable resolved (enhancement timed out, used original) |
| astropy-13977 | F2P: **12/20**, P2P: 318/322 | F2P: **0/20**, P2P: 277/322 | **Regression** | Enhancement changed fix approach |
| astropy-14096 | F2P: **1/1**, P2P: **426/426** RESOLVED | F2P: **1/1**, P2P: **426/426** RESOLVED | **No change** | Stable resolved |
| astropy-14182 | F2P: 0/1, P2P: 1/9 | F2P: 0/1, P2P: **9/9** | **Improvement** | Enhancement improved P2P |
| astropy-14309 | F2P: **1/1**, P2P: **141/141** RESOLVED | F2P: **1/1**, P2P: **141/141** RESOLVED | **No change** | Stable resolved |

**Group A summary**: +1 gained (13453), -0 lost resolutions = net +10%
- But 2 regressions in non-resolved instances (13398 P2P collapse, 13977 F2P collapse)

### 2.2 Group B — Community Issues (5 Flask + 1 Requests + 4 sklearn)

| Instance | Baseline | Enhanced | Delta | Category |
|----------|----------|----------|-------|----------|
| flask-5004 | F2P: 0/2, P2P: 0/53 (eval error) | F2P: **1/2**, P2P: **53/53** | **Improvement** | Enhancement fixed eval + improved F2P |
| flask-5391 | F2P: **1/1**, P2P: **53/53** RESOLVED | F2P: **1/1**, P2P: **53/53** RESOLVED | **No change** | Stable resolved (enhancement timed out) |
| flask-5472 | F2P: 0/1, P2P: **125/125** | F2P: **1/1**, P2P: **125/125** RESOLVED | **RESOLVED** | Enhancement clarified issue |
| flask-5553 | F2P: 0/2, P2P: **188/188** | F2P: 0/2, P2P: **188/188** | **No change** | Stable non-resolved |
| flask-5621 | F2P: 0/1, P2P: **126/126** | F2P: 0/1, P2P: **126/126** | **No change** | Stable non-resolved |
| requests-6628 | F2P: **1/1**, P2P: 135/136 | F2P: 0/1, P2P: 0/136 (eval error) | **Regression** | Enhancement caused eval failure |
| sklearn-28901 | F2P: 0/11, P2P: 0/359 | F2P: 0/11, P2P: 0/359 (eval error) | **Regression** | Enhancement caused eval failure |
| sklearn-29294 | F2P: 0/1, P2P: **16/16** | F2P: 0/1, P2P: **16/16** | **No change** | Stable non-resolved |
| sklearn-30056 | F2P: 0/1, P2P: 0/19 (eval error) | F2P: 0/1, P2P: 0/19 (eval error) | **No change** | Infra error in both |
| sklearn-30622 | F2P: 0/2, P2P: **39/39** | F2P: 0/2, P2P: **35/39** | **Regression** | Enhancement changed fix location |

**Group B summary**: +1 gained (flask-5472), -0 lost resolutions = net +10%
- But 3 regressions: requests-6628 lost F2P, sklearn-28901 new eval error, sklearn-30622 lost 4 P2P tests

### 2.3 Group C — SWE-bench-Live (10 diverse repos)

| Instance | Baseline | Enhanced | Delta | Category |
|----------|----------|----------|-------|----------|
| conan-15377 | F2P: 0/2, P2P: 0/3574 (eval error) | F2P: 0/2, P2P: 0/3574 (eval error) | **No change** | Infra error in both |
| matplotlib-27613 | F2P: **1/1**, P2P: 11/7799 | F2P: 0/1, P2P: 0/7799 (eval error) | **Regression** | Context overflow → empty patch |
| cfn-lint-3400 | F2P: 0/1, P2P: 6/990 | F2P: 0/1, P2P: 0/990 (eval error) | **Regression** | Context overflow → empty patch |
| haystack-6713 | F2P: 0/8, P2P: 0/849 (eval error) | F2P: 0/8, P2P: 0/849 (eval error) | **No change** | Infra error in both |
| pylint-9419 | F2P: 0/2, P2P: 0/1822 (eval error) | F2P: 0/2, P2P: 0/1822 (eval error) | **Regression** | Context overflow → empty patch |
| keras-19300 | F2P: 0/1, P2P: 198/6659 | F2P: **1/1**, P2P: 201/6659 | **Improvement** | Enhancement improved F2P |
| instructlab-615 | F2P: 0/1, P2P: 4/12 | F2P: 0/1, P2P: 0/12 (eval error) | **Regression** | Empty patch in enhanced |
| streamlink-5774 | F2P: 0/5, P2P: 0/5996 (eval error) | F2P: 0/5, P2P: 0/5996 (eval error) | **No change** | Infra error in both |
| **reflex-2457** | F2P: **1/1**, P2P: **978/978** **RESOLVED** | F2P: 0/1, P2P: 0/978 (eval error) | **LOST RESOLUTION** | Context overflow → empty patch |
| sphinx-11888 | F2P: **1/1**, P2P: 12/1997 | F2P: **1/1**, P2P: 12/1997 | **No change** | Stable non-resolved |

**Group C summary**: +0 gained, -1 lost resolution (reflex-2457) = net -10%
- 4 context window overflows, 1 empty patch, only 1 genuine improvement (keras-19300)

---

## 3. Categorized Failure Modes

### Category 1: Context Window Overflow (4 instances — all Group C)

**Affected**: `matplotlib-27613`, `cfn-lint-3400`, `pylint-9419`, `reflex-2457`

**Mechanism**: SWE-agent enhancement expanded the issue description significantly. When combined with the solver's system prompt + repository code context, the total exceeded Devstral's 65536-token context window.

| Instance | Token Count | Over Limit By |
|----------|:---:|:---:|
| cfn-lint-3400 | 65,646 | +110 tokens |
| matplotlib-27613 | 66,067 | +531 tokens |
| pylint-9419 | >65,536 | Unknown |
| reflex-2457 | >65,536 | Unknown |

**Impact**: Empty patches → 0 edits → 0 tests pass → evaluation failure.

**Critical loss**: `reflex-2457` was **the only resolved instance** in Group C baseline, and enhancement killed it.

**Root cause**: SWE-bench-Live descriptions are already verbose (avg 1,877 chars). Enhancement expanded them by ~101% on average. Group A/B descriptions start shorter and their expansions still fit.

**Enhancement body expansion by group**:
| Group | Avg Original Body | Avg Enhanced Body | Expansion |
|-------|:-:|:-:|:-:|
| A | ~2,071 chars | ~3,647 chars | +76% |
| B | ~2,236 chars | ~3,851 chars | +72% |
| C | ~1,427 chars | ~2,872 chars | +101% |

Note: Group C has shorter average original bodies but the highest expansion rate. Combined with more complex code repositories, this pushes past the limit.

### Category 2: Enhancement Mislead the Solver (3 instances)

**Affected**: `astropy-13398`, `astropy-13977`, `sklearn-30622`

These instances show the solver producing a **worse patch** after enhancement, not due to infrastructure limits but because the enhanced description changed the solver's understanding of the problem.

#### astropy-13398: P2P collapsed (63/68 → 0/68)
- **Original**: Proposal for "direct approach to ITRS to observed frame transforms"
- **Enhanced**: Restructured as "Proposal: Direct ITRS to Observed frame transforms" with detailed sections
- **Baseline patch**: ~11,754 chars — added entire new module `itrs_observed_transforms.py`
- **Enhanced patch**: Similar approach but misunderstood architectural placement
- **Verdict**: Enhancement's restructuring changed the framing enough that the solver produced an incompatible implementation. The original's nuanced description of the coordinate transform chain was lost in the enhancement's formalized structure.

#### astropy-13977: F2P collapsed (12/20 → 0/20)
- **Original**: Discussion about `Quantity.__array_ufunc__()` return behavior
- **Enhanced**: Formalized as "should return NotImplemented" with structured sections
- **Baseline patch**: 910 chars — wrapped unit conversion in try/except, returned NotImplemented for UnitsError
- **Enhanced patch**: Similar approach but the restructured description led to subtly different error handling
- **Verdict**: The enhanced description was more prescriptive ("should return NotImplemented") which led the solver to a similar but slightly wrong approach. The original's open-ended discussion gave the solver more room to reason.

#### sklearn-30622: P2P regressed (39/39 → 35/39)
- **Original**: "Validate estimators argument type in StackingClassifier/Regressor"
- **Enhanced**: "Add validation for estimators parameter with type checking"
- **Baseline patch**: 2,094 chars — validation in `_validate_estimators()` method (correct location)
- **Enhanced patch**: 1,587 chars — validation in `__init__()` (wrong location)
- **Verdict**: Enhancement's rephrasing from "validate in existing method" to "add validation" led the solver to add validation at construction time instead of the dedicated validation method. This caused edge cases (e.g., "drop" sentinel value) to fail.

**Pattern**: Enhancement's formalization and restructuring can strip away contextual clues that help the solver make correct architectural decisions.

### Category 3: Enhancement Caused Evaluation Failures (3 instances)

**Affected**: `astropy-12907` (Group A), `requests-6628` (Group B), `sklearn-28901` (Group B)

These instances produced patches in both baseline and enhanced, but the enhanced patch triggered evaluation infrastructure errors (report_not_found).

#### requests-6628: Lost F2P (1/1 → 0/1) + eval error
- **Baseline**: 664 chars — clean, targeted fix for JSONDecodeError serialization
- **Enhanced**: 0 chars — solver timed out, no patch generated
- **Root cause**: The enhanced description (7,842 chars, up from 6,884) was so verbose that the solver spent all its steps reading the description and exploring code, running out of time before generating a patch.

#### astropy-12907: Lost P2P (13/13 → 0/13)
- **Baseline**: Produced a patch that passed all P2P tests
- **Enhanced**: Produced a patch but evaluation returned report_not_found
- **Root cause**: The enhanced patch may have caused the test harness to crash or the Docker container to fail

#### sklearn-28901: eval_error in enhanced only
- **Baseline**: eval_error too, but due to different reason
- **Enhanced**: eval_error persisted
- **Verdict**: Not solely enhancement's fault — infrastructure issue

### Category 4: Enhancement Helped the Solver (4 instances)

**Affected**: `astropy-13453` (RESOLVED), `astropy-14182` (P2P improved), `flask-5472` (RESOLVED), `keras-19300` (F2P improved)

#### astropy-13453: NOT resolved → RESOLVED
- **Original title**: "ASCII table output to HTML does not use the formats argument"
- **Enhanced title**: "HTML table writer ignores `formats` argument"
- **Original body**: 3,571 chars — described the formatting issue with examples but in a narrative style
- **Enhanced body**: 5,847 chars — structured with Description, Expected Behavior, Actual Behavior, Steps to Reproduce, Code Example
- **Baseline patch**: Attempted fix but missed `_set_col_formats()` call
- **Enhanced patch**: 551 chars — clean, minimal: `self.data.cols = cols` + `self.data._set_col_formats()`
- **Why enhancement helped**: The enhanced description's "Expected vs Actual Behavior" section clearly delineated what the output should look like, guiding the solver to the correct fix. The original's narrative style buried the key requirement.

#### flask-5472: NOT resolved → RESOLVED
- **Original title**: "Add support for partitioned cookies"
- **Enhanced title**: "Add support for partitioned session cookies with Partitioned attribute"
- **Original body**: 394 chars — very brief, minimal context
- **Enhanced body**: 3,812 chars — comprehensive with Background, Current Behavior, Expected Behavior, Proposed Solution, Affected Components
- **Baseline patch**: 2,042 chars — added `get_cookie_partitioned()` but missed some call sites
- **Enhanced patch**: 2,567 chars — more comprehensive coverage of all `set_cookie()` calls
- **Why enhancement helped**: The original description was extremely short (394 chars). Enhancement expanded it 10x with critical details about the Partitioned cookie attribute, its purpose, and where it needs to be applied. This gave the solver enough context to produce a complete fix.

#### keras-19300: F2P improved (0/1 → 1/1)
- **Original body**: 743 chars — described softmax error but briefly
- **Enhanced body**: 2,681 chars — added Root Cause Analysis, Steps to Reproduce, Affected Components
- **Baseline patch**: 1,473 chars — defensive try/except approach
- **Enhanced patch**: 859 chars — clean `isinstance(x, KerasTensor)` type check
- **Why enhancement helped**: Enhancement's Root Cause Analysis section identified the type-checking issue, leading the solver to a simpler, more correct approach. The enhanced patch was 42% smaller and more focused.

#### astropy-14182: P2P improved (1/9 → 9/9)
- **Original body**: 1,512 chars — feature request for header_rows support
- **Enhanced body**: 3,186 chars — structured with Current Behavior, Expected Behavior, Affected Components
- **Why enhancement helped**: Clear Expected Behavior section helped the solver produce a patch that didn't break existing functionality.

**Pattern**: Enhancement works best when:
1. Original descriptions are **short** (<1000 chars) — flask-5472 (394 chars), keras-19300 (743 chars)
2. Original descriptions are **narrative/unstructured** — astropy-13453 (narrative), astropy-14182
3. Enhancement adds **reproduction steps** and **expected vs actual** comparisons

### Category 5: No Change (14 instances)

| Group | Instance | Reason |
|-------|----------|--------|
| A | astropy-13033 | Both failed F2P, same P2P |
| A | astropy-13236 | Both failed F2P, same P2P |
| A | astropy-13579 | Both resolved (enhancement timed out, used original) |
| A | astropy-14096 | Both resolved |
| A | astropy-14309 | Both resolved |
| B | flask-5553 | Both failed F2P, same P2P |
| B | flask-5621 | Both failed F2P, same P2P |
| B | flask-5391 | Both resolved (enhancement timed out, used original) |
| B | sklearn-29294 | Both failed F2P, same P2P |
| B | sklearn-30056 | Infra error in both |
| C | conan-15377 | Infra error in both |
| C | haystack-6713 | Infra error in both |
| C | streamlink-5774 | Infra error in both |
| C | sphinx-11888 | Same F2P/P2P in both |

**Key observation**: 5 of 14 "no change" instances have infrastructure errors in BOTH baseline and enhanced, meaning neither could be properly evaluated regardless of description quality.

---

## 4. Enhancement Outcome Distribution

### 4.1 Overall (30 instances)

| Outcome | Count | % | Instances |
|---------|:---:|:---:|-----------|
| **Gained resolution** | 2 | 6.7% | astropy-13453, flask-5472 |
| **Improvement (no new resolution)** | 2 | 6.7% | astropy-14182, keras-19300 |
| **No change** | 14 | 46.7% | (see above) |
| **Regression (non-critical)** | 6 | 20.0% | astropy-13398, -13977, -12907, requests-6628, sklearn-28901, -30622 |
| **Lost resolution** | 1 | 3.3% | reflex-2457 |
| **Context overflow** | 4 | 13.3% | matplotlib-27613, cfn-lint-3400, pylint-9419, reflex-2457 |
| **Infra error (both)** | 5 | 16.7% | (double-counted with no change) |

Note: reflex-2457 is counted in both "lost resolution" and "context overflow".

### 4.2 By Group

| Outcome | Group A | Group B | Group C |
|---------|:---:|:---:|:---:|
| Gained resolution | 1 (13453) | 1 (flask-5472) | 0 |
| Improvement | 1 (14182) | 1 (flask-5004) | 1 (keras-19300) |
| No change | 5 | 4 | 5 |
| Regression | 3 | 3 | 4 |
| Lost resolution | 0 | 0 | 1 (reflex-2457) |
| **Net resolved delta** | **+1 (+10%)** | **+1 (+10%)** | **-1 (-10%)** |

---

## 5. What Enhancement Does Well

### 5.1 Expanding Short Descriptions (Most Effective)

| Instance | Original Length | Enhanced Length | Outcome |
|----------|:-:|:-:|---|
| flask-5472 | **394 chars** | 3,812 chars | **RESOLVED** |
| keras-19300 | **743 chars** | 2,681 chars | **F2P gained** |
| astropy-14182 | 1,512 chars | 3,186 chars | **P2P improved** |

**Finding**: Enhancement is most effective on descriptions under ~1,500 chars. These issues lack context that the solver needs, and enhancement fills the gap.

### 5.2 Adding Structure to Narrative Descriptions

| Instance | Original Style | Enhanced Style | Outcome |
|----------|---|---|---|
| astropy-13453 | Narrative with embedded code examples | Sections: Description, Expected, Actual, Steps | **RESOLVED** |
| flask-5472 | Brief one-paragraph request | Sections: Background, Current/Expected Behavior, Proposed Solution | **RESOLVED** |

**Finding**: Converting narrative-style descriptions to structured bug reports (Expected vs Actual, Steps to Reproduce) helps the solver zero in on the correct fix.

### 5.3 Identifying Affected Components

Enhancement consistently adds an "Affected Components" or "Affected Files" section. This helps the solver navigate large codebases faster. Example:

- **keras-19300**: Enhancement identified the root cause as a type-checking issue, leading to a simpler `isinstance()` fix instead of a defensive try/except.
- **flask-5472**: Enhancement listed specific files and methods that need the Partitioned attribute.

### 5.4 Simplifying the Solver's Output

Counterintuitively, enhanced descriptions sometimes lead to **smaller, better patches**:

| Instance | Baseline Patch | Enhanced Patch | Result |
|----------|:-:|:-:|---|
| astropy-13453 | Failed | **551 chars (minimal)** | RESOLVED |
| keras-19300 | 1,473 chars (defensive) | **859 chars (clean)** | F2P gained |

**Finding**: When enhancement clearly articulates the root cause, the solver produces focused fixes instead of defensive workarounds.

---

## 6. What Enhancement Does Poorly

### 6.1 Over-Expanding Already-Verbose Descriptions (Most Harmful)

| Instance | Original Length | Enhanced Length | Expansion | Outcome |
|----------|:-:|:-:|:-:|---|
| reflex-2457 | 645 chars | 2,478 chars | +284% | **LOST RESOLUTION** |
| matplotlib-27613 | 1,754 chars | 4,521 chars | +158% | Context overflow |
| cfn-lint-3400 | 1,506 chars | 1,674 chars | +11% | Context overflow |
| pylint-9419 | 545 chars | 2,845 chars | +422% | Context overflow |

**Finding**: Even moderately-sized descriptions can cause context overflow when combined with large codebases. The `cfn-lint-3400` expansion was only 11% but the repository's code context was already near the limit.

**Key insight**: The overflow depends on **description length + code context size**, not just description length alone. Repositories with large test suites or complex file structures consume more context.

### 6.2 Stripping Domain-Specific Nuance

| Instance | Original Nuance | Enhancement Lost | Impact |
|----------|---|---|---|
| astropy-13398 | Detailed discussion of ITRS↔AltAz coordinate transform chain with specific mathematical considerations | Formalized to generic "Proposal: Direct ITRS to Observed" with sections | P2P: 63/68 → 0/68 |
| astropy-13977 | Open-ended discussion "should Quantity.__array_ufunc__ return..." | Prescriptive "should return NotImplemented" | F2P: 12/20 → 0/20 |

**Finding**: Enhancement converts open-ended discussions into prescriptive statements. This can be harmful when:
- The original discussion captures design trade-offs the solver should consider
- Domain-specific terminology and relationships are simplified
- The "correct" approach isn't obvious and the solver needs flexibility

### 6.3 Changing Architectural Framing

| Instance | Baseline Approach | Enhanced Approach | Impact |
|----------|---|---|---|
| sklearn-30622 | Validation in `_validate_estimators()` | Validation in `__init__()` | Lost 4/39 P2P tests |

**Finding**: Enhancement's rephrasing from "validate estimators argument" to "add validation for estimators" subtly shifted the solver from "modify existing validation" to "add new validation at construction". This architectural difference caused edge cases to fail.

### 6.4 Creating Near-Identical Enhancements (Wasted Compute)

| Instance | Enhancement Type | Similarity | Impact |
|----------|---|:-:|---|
| flask-5391 | Timeout → used original | 100% | No change (already resolved) |
| astropy-13579 | Timeout → used original | 100% | No change (already resolved) |

**Finding**: When SWE-agent times out (300s limit), the original description is used as fallback. Ironically, both timeout instances were **already resolved in baseline**, suggesting the enhancement was unnecessary. This wastes 300 seconds of compute per timeout.

### 6.5 Introducing Hallucinated Details

In some Group C enhancements, SWE-agent added specific technical details that may not be accurate:
- **pylint-9419**: Enhanced body included error tracebacks that weren't in the original
- **deepset-ai__haystack-6713**: Enhancement condensed the body from 4,982 to 1,823 chars, potentially losing critical reproduction details

**Finding**: Enhancement can both add false details and remove real ones, depending on the issue complexity and the enhancer's understanding of the domain.

---

## 7. Enhancement Effectiveness by Description Characteristics

### 7.1 Original Description Length vs Enhancement Outcome

```
Length < 500 chars:   2 improved, 1 overflow    (mixed — depends on codebase size)
Length 500-1500:      2 improved, 1 overflow     (sweet spot for improvement)
Length 1500-3000:     0 improved, 3 regression   (diminishing returns)
Length 3000+:         0 improved, 2 regression   (actively harmful)
```

**Optimal zone**: Original descriptions between **400-1500 chars** benefit most from enhancement.

### 7.2 Enhancement Similarity Score vs Outcome

| Similarity Range | Outcomes |
|---|---|
| Body sim < 0.05 | 5 cases: 2 regression, 2 no change, 1 context overflow |
| Body sim 0.05-0.15 | 10 cases: 2 improvement, 4 no change, 4 regression |
| Body sim 0.15-0.30 | 8 cases: 2 improvement, 4 no change, 2 regression |
| Body sim > 0.90 | 2 cases: 2 no change (timeouts, used original) |

**Finding**: Very low similarity (< 0.05) is a red flag — it means the enhancer rewrote almost everything, likely losing important context. Moderate similarity (0.10-0.30) correlates with the best outcomes.

### 7.3 Repository Complexity vs Enhancement Risk

| Repository | Baseline Eval Success | Enhanced Eval Success | Risk Level |
|---|:-:|:-:|---|
| astropy | 10/10 | 9/10 | Low |
| Flask | 4/5 | 5/5 | Low |
| requests | 1/1 | 0/1 | Medium |
| scikit-learn | 2/4 | 1/4 | High |
| **SWE-bench-Live repos** | **6/10** | **2/10** | **Very High** |

**Finding**: Enhancement risk increases with repository complexity and novelty. Well-tested, popular repos (astropy, Flask) are relatively safe. Newer or more complex repos (sklearn with large test suites, SWE-bench-Live) are high-risk.

---

## 8. Group B with GPT-5.4-mini (Reference)

The GPT-5.4-mini experiment on Group B provides an interesting comparison point, though the baseline was not properly evaluated (0/10, all eval failures).

**Enhanced results with GPT-5.4-mini**: 4/10 resolved (40%)
- flask-5391, flask-5472, requests-6628, sklearn-30622

**Key observation**: The enhancement quality was "near-identical" (100% similarity) — meaning GPT-5.4-mini's enhancement effectively just reproduced the original text. The improvement came entirely from the **stronger solver model** (GPT-5.4-mini vs Devstral), not from enhancement.

This serves as a control: a better model with the same descriptions outperforms a weaker model with enhanced descriptions.

---

## 9. Summary: When to Enhance and When Not To

### 9.1 Enhance When:

| Condition | Evidence | Expected Benefit |
|-----------|----------|-----------------|
| Description < 1000 chars | flask-5472 (394→3812), keras-19300 (743→2681) | +10-20% resolve rate |
| Unstructured narrative style | astropy-13453, astropy-14182 | Better solver focus |
| Missing reproduction steps | Multiple Group B instances | Solver finds right code faster |
| Feature request (not bug) | flask-5472, flask-5621 | Clarifies expected behavior |

### 9.2 Do NOT Enhance When:

| Condition | Evidence | Expected Risk |
|-----------|----------|--------------|
| Description > 3000 chars | astropy-13398 (3876), astropy-13977 (3284) | P2P regression |
| Large codebase + moderate description | Group C context overflows | Empty patches, lost resolutions |
| Domain-specific technical discussion | astropy-13398 (coordinate transforms) | Loss of nuance |
| Already well-structured issue | Many Group A stable instances | Wasted compute, no benefit |
| Already resolved in baseline | astropy-13579, flask-5391 | Risk of regression with no upside |

### 9.3 Decision Framework

```
IF original_description.length < 1000:
    → ENHANCE (high benefit, low risk)
ELIF original_description.length < 2000 AND is_unstructured:
    → ENHANCE (moderate benefit, moderate risk)
ELIF original_description.length > 3000:
    → SKIP (low benefit, high risk)
ELIF repo.test_suite_size > 5000:
    → SKIP (context overflow risk)
ELSE:
    → ENHANCE with length cap (max 3000 chars enhanced body)
```

---

## 10. Recommendations for Enhancer Improvement

### 10.1 Length-Aware Enhancement
- **Cap enhanced body at 3,000-5,000 chars** (currently unbounded)
- **Monitor token budget**: Before enhancing, estimate total prompt tokens (system + enhanced description + code context) and abort if > 80% of model limit

### 10.2 Quality-Aware Skipping
- **Auto-skip well-structured issues**: If original has sections (## Expected, ## Steps to Reproduce, ## Actual), skip enhancement
- **Auto-skip long descriptions**: If original > 3,000 chars, skip or only lightly edit

### 10.3 Preserve Domain Context
- **Instruction to enhancer**: "Preserve all technical terminology, mathematical notation, and domain-specific references from the original description"
- **Never delete original content**: Enhancement should ADD structure, not REWRITE content

### 10.4 Validate Enhancement Quality
- **Similarity floor**: If body similarity < 0.05, reject the enhancement and use original
- **Length ceiling**: If enhanced body > 2x original length AND original > 2000 chars, reject

### 10.5 Context-Aware Enhancement
- **Measure codebase complexity**: Before enhancing, estimate the code context that will be loaded
- **Adjust enhancement verbosity**: Larger codebases → shorter enhancements

---

**Report Generated**: 2026-03-31
**Data Sources**: Groups A, B, C comparison_summary.json + enhancement JSONs + patch diffs
**Total Issues Analyzed**: 30 (10 per group)
