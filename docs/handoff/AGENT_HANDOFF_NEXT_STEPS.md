# Agent Handoff: Next-Generation Enhancer Experiments & Scaling

## 1. Current Situation & Historical Context
Welcome! We are evaluating how modifying GitHub issue descriptions (i.e., "Enhancing") affects the performance of an underlying autonomous coding agent (the "Solver"). Our solver uses the `mini-SWE-agent` framework evaluating on `swebench_backticks` with `Devstral-Small-2-24B`.

**What worked:**
We achieved highly successful results using a deterministic python script known as the **Code-Context Enhancer** (adding raw file paths and reproduction scripts directly to the issue). This jumped bug-fixing (F2P) success from 28% to 54% when paired with a "V1 Regression Guard" (a simple sentence telling the solver to run the test suite before submitting to avoid P2P regressions).

**What failed terribly:**
We attempted to use autonomous LLM agents (specifically **Aider**, SWE-agent, and TRAE) to read the repository and "re-write" the issue description into a neat summary. **Aider caused an absolute catastrophic performance drop (F2P baseline dropped from 28% down to 14%).** 
We identified this as the **"Lossy Compressor"** problem: by trying to write clean summaries, Aider strips out the deep technical nuances, raw stack traces, memory addresses, and messy jargon that the downstream solver actually relies on to locate the bug.

---

## 2. Your Tasks

### Task 1: Rescue LLM Enhancers (The Aider Rehabilitation)
Your first objective is to fix the LLM Enhancer methodology framework so it actually *improves* performance rather than degrades it. You must figure out how an LLM can parse an issue/repo without being a "lossy compressor."

**Requirements:**
1. Pick a small experimental subset of **5 sample issues**.
2. Hypothesize and implement new prompting approaches for Aider (or an equivalent LLM enhancement agent). For example:
   * **Approach X:** Ask the enhancer to extract exact code snippets and stack traces, appending them verbatim rather than summarizing them.
   * **Approach Y:** Implement a Chain-of-Thought where the enhancer identifies the root cause and writes a step-by-step hypothesis without altering the original user prompt text.
   * **Approach Z:** Combine the deterministic code-context gathering script with Aider's logical reasoning.
3. Run these approaches using the pipeline on your 5 samples.
4. Analyze and document the results. Determine which strategy actually benefits the solver compared to the raw baseline.

### Task 2: The 90-Issue Scale-Up Experiment
Once you have formulated a potentially successful LLM enhancement strategy, we need to test everything at a larger scale to ensure statistical significance.

**Requirements:**
1. Automatically pull an additional **40 issues** from the `SWE-bench-Live/SWE-bench-Live` HuggingFace dataset (specifically the `test` split).
2. **Crucial Filtering Criteria:** You MUST ensure these selected issues have `FAIL_TO_PASS > 0 AND PASS_TO_PASS > 0`. You must use a deterministic random seed to select these.
3. Merge these 40 new issues with our existing 50-issue group (Group C) to create a **90-issue dataset**.
4. Run comprehensive benchmarks across this 90-issue dataset for all our strategies to see how the numbers shift:
   * Baseline (No enhancement)
   * The new, improved Aider/LLM Enhancer (from Task 1)
   * Code-Context + V1 Regression Guard (our current champion)
5. Generate a final report detailing the comparative performance statistics (Resolved rate, F2P rates, P2P passing) across the 90 issues.
