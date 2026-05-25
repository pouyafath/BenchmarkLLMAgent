# Slide 1 — Project Goal And Setup

**Goal**
Evaluate LLM-based coding agents on SWE-bench-Live with a reproducible pipeline that separates issue understanding from patch generation.

**Setup**
- 10 SWE-bench-Live issues (verified split, seed=42)
- 7 agents: 2 baselines + 5 enhanced
- Pipeline: Enhance issue → Solve → SWE-bench harness

---

# Slide 2 — Pipeline And What We Measure

**Pipeline**
1. Enhancement agent rewrites the issue
2. Solver generates a patch
3. Harness applies patch and runs tests

**Metrics (why they matter)**
- Patch Apply Rate (can we even evaluate?)
- F2P Progress (fix target failures)
- Regression Rate (avoid breaking existing tests)
- Content similarity + file overlap (alignment to ground truth)

---

# Slide 3 — Key Results (Iteration 2)

**Coverage**
- 66 submitted, 15 completed test reports
- Baselines: 0% patch apply, 0 completed tests
- Enhanced: 20–40% patch apply

**Core Outcomes**
- Fix Rate: 0% (blocked by regressions)
- F2P Progress: up to 50%
- Regression Rate: ~99% (dominant failure mode)

---

# Slide 4 — What The Results Mean

**What worked**
- Enhancement improves patch validity substantially
- Target failures can be fixed (F2P successes)

**What blocks success**
- Massive regressions in P2P tests
- Fix Rate stays 0 even when F2P passes

**Interpretation**
Quality of issue understanding is helping, but regression control is the core bottleneck.

---

# Slide 5 — Next Steps

**Engineering**
- Add regression-aware solving (test-aware patching)
- Improve patch formatting and context matching

**Research**
- Scale to more issues for statistical power
- Track cost/tokens/time for efficiency metrics

**Deliverables Ready**
- Comprehensive metrics pipeline (9 metrics)
- Final report with dual baselines and definitions
- Reproducible scripts and artifacts
