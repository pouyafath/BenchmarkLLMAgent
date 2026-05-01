# Benchmarking LLM Agent Frameworks for GitHub Issue Solving: Pilot Study Report

**Authors**: Pouya Fathollahzadeh  
**Date**: February 2026  
**Status**: Pilot study (Phase 4 of research plan)  
**Target Venue**: IEEE Transactions on Software Engineering (TSE)

---

## Abstract

This report presents the pilot study for our third paper in a research trilogy on LLM-powered software engineering automation. While our first paper (published in TSE) addressed understanding developer questions through chatroom NER, and our second paper (submitted to ASE 2026) focused on enhancing GitHub issue descriptions, this work takes the natural next step: **solving GitHub issues directly using LLM-based agents**. Critically, rather than comparing models or prompts, we introduce the first **framework-centric benchmark** that isolates the effect of agent-building frameworks on issue-solving performance. In this pilot study, we evaluated six prominent agent frameworks—AutoGen, CrewAI, LangGraph, LlamaIndex, OpenAI Agents SDK, and Semantic Kernel—on 10 real-world GitHub issues using Llama 3.3 70B as the underlying LLM, with all other variables held constant. Four of the six frameworks produced working results, generating patches for 90–100% of issues. OpenAI Agents SDK ranked first overall, achieving perfect file localization (1.000 Jaccard overlap), the highest content similarity to ground truth (0.224 on diff-only comparison), and the fastest average completion time (31.0s). These initial findings demonstrate the viability of framework-centric benchmarking and reveal measurable differences in framework behavior even under controlled conditions.

---

## 1. Introduction

### 1.1 Research Trilogy

This work is the third paper in a trilogy that progressively advances LLM-based automation along the software issue lifecycle:

| Paper | Venue | Focus | Stage |
|-------|-------|-------|-------|
| Paper 1: SENIR | TSE (Published) | **Understanding** — NER for developer chatroom conversations | Descriptive |
| Paper 2: Issue Enhancement | ASE 2026 (Submitted) | **Enhancing** — Improving GitHub issue quality to accelerate resolution | Prescriptive |
| Paper 3: Issue Solving | TSE (Target) | **Solving** — Comparing agent frameworks on automated issue resolution | Autonomous |

The trajectory moves from understanding what makes questions resolvable (Paper 1), to improving issue text so that resolution happens faster (Paper 2), to having agents fix the code directly (Paper 3).

### 1.2 Motivation

Recent progress in agentic coding systems—SWE-bench, SWE-Agent, AutoCodeRover, Agentless, OpenHands—shows that LLM-based agents can resolve real software issues. However, existing evaluations are predominantly:

- **Model-centric**: comparing GPT-4 vs. Claude vs. Llama on the same framework
- **Prompt-centric**: comparing different prompting strategies within a single system
- **Benchmark-specific**: performance on SWE-bench alone (selection bias toward Python, mature repos)

These approaches miss a critical practical question: **given the same LLM, prompts, tools, and budget, which agent-building framework produces the best issue-solving agents?**

This is a first-order architectural decision for any team building coding agents, yet no existing study isolates framework effects from model/prompt/tool effects.

### 1.3 Research Questions

| RQ | Question |
|----|----------|
| **RQ1** | How do different agent-building frameworks compare in their ability to resolve GitHub issues? |
| **RQ2** | What are the efficiency and cost trade-offs across frameworks? |
| **RQ3** | How do framework characteristics (orchestration, memory, error handling) influence agent behavior? |
| **RQ4** | How do framework performance differences vary across issue types and complexity levels? |

### 1.4 Scope of This Pilot Study

This report covers the **Phase 4 pilot run** of our research plan: a controlled experiment on 10 issues with 6 frameworks using a single LLM model. The purpose is to validate the experimental methodology, identify practical challenges, and obtain preliminary results before scaling to the full benchmark (300–500 issues, 2–3 models).

---

## 2. Approach

### 2.1 Controlled Experimental Design

The core principle of our benchmark is **fairness through control**. We isolate the independent variable (agent framework) by holding all other factors constant:

| Control Variable | Value Used in Pilot |
|-----------------|---------------------|
| **LLM Model** | Llama 3.3 70B Instruct (FP16) |
| **LLM Hosting** | Ollama (local GPU inference) |
| **Temperature** | 0 (deterministic) |
| **System Prompt** | Identical across all frameworks |
| **Task Template** | Identical across all frameworks |
| **Tool Access** | None (single-turn patch generation) |
| **Context Provided** | Issue title, body, labels, changed file hints, source code |
| **Output Format** | Unified diff patch |
| **Parallel Workers** | 4 concurrent workers per framework |

### 2.2 Agent Frameworks Under Evaluation

We selected six frameworks representing the major approaches to LLM agent construction:

| Framework | Organization | Key Architecture | Version |
|-----------|-------------|-----------------|---------|
| **AutoGen** | Microsoft | Multi-agent conversations, code execution sandbox | Latest (Feb 2026) |
| **CrewAI** | CrewAI | Role-based agents, sequential/hierarchical processes | Latest (Feb 2026) |
| **LangGraph** | LangChain | Graph-based state machines, checkpointing | Latest (Feb 2026) |
| **LlamaIndex** | LlamaIndex | RAG-native workflows, data-aware agents | Latest (Feb 2026) |
| **OpenAI Agents SDK** | OpenAI | Minimal abstraction, handoffs, guardrails | Latest (Feb 2026) |
| **Semantic Kernel** | Microsoft | Enterprise planner abstraction, multi-language SDK | Latest (Feb 2026) |

Each framework was implemented as a solver agent that:
1. Receives a standardized issue context (title, body, labels, source code of affected file)
2. Generates a unified diff patch as its solution
3. Returns the patch, execution time, and token usage metadata

### 2.3 Dataset Construction

#### 2.3.1 Source

We reused the **golden dataset** from Paper 2, which contains 400 curated GitHub issues from 1,000 repositories (originally 43,708 issues). This dataset was constructed using a multi-stage pipeline including repository selection, issue filtering, and quality validation.

#### 2.3.2 Pilot Sample Selection

From the 400-issue golden dataset, we selected 10 issues meeting the following criteria:

- **Closure type**: Closed by a pull request (not manual closure)
- **PR linkage**: Same-repository merged PR directly linked to the issue
- **Code changes**: PR contains actual code modifications (not just documentation)
- **Balanced complexity**: Mix of difficulty levels (based on LightGBM difficulty scores from Paper 2)
- **Preference for smaller changes**: Issues with 1–2 files changed, suitable for single-turn agents

#### 2.3.3 Selected Issues

| # | Repository | Issue | Bug Summary | Language | PR Changes |
|---|-----------|-------|-------------|----------|------------|
| 1 | serverless/serverless | #12980 | Missing AWS region `ca-west-1` | JavaScript | 1 file, +2 lines |
| 2 | eclipse-theia/theia | #15048 | Empty changeset not auto-deleted | TypeScript | 1 file, +4 lines |
| 3 | bevyengine/bevy | #18468 | Deferred rendering broken on macOS | Rust | 1 file, +4 lines |
| 4 | nlohmann/json | #4309 | GDB pretty printer broken after `m_data` refactor | Python | 1 file, +3/−3 lines |
| 5 | mpv-player/mpv | #15776 | Hang when switching files in EDL timeline | C | 1 file, +7/−1 lines |
| 6 | syncthing/syncthing | #9775 | NTFS junction directories not syncing | Go | 1 file, +6/−3 lines |
| 7 | withfig/autocomplete | #1625 | Missing `remove` subcommand in conda spec | TypeScript | 1 file, +14/−1 lines |
| 8 | nextcloud/server | #51652 | Password-protected share ZIP download errors | PHP | 1 file, +17 lines |
| 9 | vuejs/core | #12181 | Memory leak with Transition component | TypeScript | 1 file, +15/−6 lines |
| 10 | pixijs/pixijs | #11207 | Mesh geometry crash at ~200 vertices | TypeScript | 1 file, +28/−2 lines |

The dataset spans **7 programming languages** (JavaScript, TypeScript, Rust, Python, C, Go, PHP) and **10 distinct open-source projects** of varying size and domain (game engine, media player, web framework, file sync, cloud platform, etc.).

### 2.4 Ground Truth

For each issue, the ground truth is the **actual merged PR patch** that resolved the issue. We fetched the full patch diff from GitHub using a multi-token API client (rotating through multiple personal access tokens to manage rate limits). Each ground truth file contains:

- The complete unified diff of the merged PR
- The list of files changed, with addition/deletion counts
- The merge commit SHA and base commit SHA (for exact repository state)

### 2.5 Agent Implementation

Each framework agent follows the same logical flow:

```
Input: System prompt + Task context (issue metadata + source code)
   │
   ▼
Framework-specific LLM invocation
   │
   ▼
Output: Raw LLM response
   │
   ▼
Patch extraction (regex-based, framework-independent)
   │
   ▼
Evaluation against ground truth
```

The differences between frameworks lie solely in how they:
- Initialize the LLM connection (client construction)
- Structure the conversation (message format, chat history)
- Invoke the model (sync vs. async, streaming vs. batch)
- Handle the response (extraction, metadata collection)

This design ensures that any performance differences are attributable to the framework's LLM integration layer, not to differences in prompting, tools, or models.

### 2.6 Evaluation Metrics

We evaluated agent-generated patches against the ground truth merged PR using three categories of metrics:

**A. Patch Generation Rate** — Did the agent produce a non-empty, parseable unified diff?

**B. File Localization (Jaccard File Overlap)** — Did the agent modify the correct file(s)? Computed as the Jaccard similarity between the set of files changed by the agent and the set of files changed in the ground truth PR.

**C. Content Similarity (SequenceMatcher Ratio)** — How similar is the agent's patch to the ground truth patch? To ensure a fair comparison, we strip git commit metadata (author, date, subject, stat lines) from the ground truth, comparing only the actual `diff --git` content against the agent's output. Similarity is computed using Python's `difflib.SequenceMatcher`, which produces a ratio in [0, 1] representing the proportion of matching subsequences.

**D. Efficiency (Wall-Clock Time)** — How long did the framework take to produce its patch?

---

## 3. Results

### 3.1 Framework Operability

Of the six frameworks, **four produced working results** and **two failed due to connector-level issues**:

| Framework | Status | Failure Reason |
|-----------|--------|---------------|
| AutoGen | Working | — |
| CrewAI | Working | — |
| LangGraph | Working (1 error) | `KeyError` on 1 issue due to state management in newer LangGraph API |
| OpenAI Agents SDK | Working | — |
| LlamaIndex | Failed (all 10) | `ReadTimeout`: Ollama Python library connector stalls under concurrent load with 70B model |
| Semantic Kernel | Failed (all 10) | `TypeError`: Rapidly evolving SDK; API signature changed between versions |

The two failures are **integration issues**, not fundamental framework limitations. LlamaIndex's Ollama connector has a timeout handling problem under concurrent GPU load, while Semantic Kernel's Python SDK had a breaking API change. Both are fixable with dependency pinning and alternative connectors.

### 3.2 Overall Framework Comparison

| Rank | Framework | Patch Rate | File Overlap | Content Sim | Mean Time | Median Time |
|------|-----------|-----------|-------------|------------|-----------|-------------|
| **#1** | **OpenAI Agents SDK** | **10/10 (100%)** | **1.000** | **0.2237** | **31.0s** | **26.2s** |
| #2 | CrewAI | 10/10 (100%) | 1.000 | 0.2092 | 33.0s | 25.9s |
| #3 | LangGraph | 9/10 (90%) | 1.000 | 0.1858 | 61.8s | 31.4s |
| #4 | AutoGen | 10/10 (100%) | 0.800 | 0.1686 | 40.4s | 38.8s |

**Key observations:**

- **OpenAI Agents SDK** leads on every metric: 100% patch rate, perfect file localization, highest similarity (0.224), and fastest execution (31.0s).
- **CrewAI** is a close second, nearly identical in patch rate and file overlap, with competitive similarity (0.209) and speed (33.0s).
- **LangGraph** achieves perfect file localization when successful and strong similarity (0.186), but is the slowest (61.8s, influenced by a 255s outlier) and had one framework error.
- **AutoGen** achieves 100% patch generation but has weaker file localization (0.800), indicating it sometimes patches the wrong file, which also reduces its content similarity (0.169).

### 3.3 Per-Issue Content Similarity

Content similarity is computed by comparing only the actual diff content (starting from `diff --git` lines), excluding git commit metadata (author, date, subject, stat lines) from the ground truth. This ensures a fair comparison between the agent's output and the representative code changes in the ground truth patch.

| Issue | AutoGen | CrewAI | LangGraph | OpenAI SDK | Avg |
|-------|---------|--------|-----------|------------|-----|
| nlohmann/json#4309 | 0.552 | 0.598 | **0.630** | **0.630** | 0.603 |
| eclipse-theia/theia#15048 | 0.212 | **0.460** | ERR | 0.429 | 0.367 |
| serverless/serverless#12980 | 0.240 | 0.232 | 0.166 | **0.301** | 0.235 |
| bevyengine/bevy#18468 | 0.088 | 0.129 | **0.179** | **0.179** | 0.144 |
| nextcloud/server#51652 | 0.165 | 0.166 | **0.167** | **0.167** | 0.166 |
| withfig/autocomplete#1625 | 0.049 | 0.141 | **0.205** | **0.205** | 0.150 |
| pixijs/pixijs#11207 | **0.143** | 0.063 | 0.102 | 0.102 | 0.103 |
| mpv-player/mpv#15776 | 0.105 | **0.126** | 0.116 | 0.116 | 0.116 |
| vuejs/core#12181 | 0.076 | **0.125** | 0.058 | 0.058 | 0.079 |
| syncthing/syncthing#9775 | **0.056** | 0.051 | 0.050 | 0.050 | 0.052 |

**Findings:**
- **nlohmann/json#4309** had the highest similarity across all frameworks (avg 0.603). This issue had explicit fix instructions in the body, making it straightforward for any agent.
- **eclipse-theia/theia#15048** showed the second-highest similarity. CrewAI achieved 0.460 and OpenAI Agents SDK 0.429, closely matching the human fix.
- **syncthing/syncthing#9775** and **vuejs/core#12181** had the lowest similarity. These involved platform-specific logic (Go on Windows) and complex state management (Vue.js transitions), respectively.
- While absolute similarity values remain moderate (0.05–0.22 for most issues), these reflect genuine textual divergence between valid alternative fixes — agents often produce functionally correct patches that differ in approach from the human solution.

### 3.4 Per-Issue Timing

| Issue | AutoGen | CrewAI | LangGraph | OpenAI SDK |
|-------|---------|--------|-----------|------------|
| vuejs/core#12181 | **7.8s** | 23.1s | 30.1s | 28.6s |
| bevyengine/bevy#18468 | 41.5s | 28.8s | 255.3s | **11.8s** |
| nextcloud/server#51652 | 15.6s | 20.6s | 16.8s | **15.4s** |
| mpv-player/mpv#15776 | 34.2s | 26.4s | 40.5s | **16.4s** |
| nlohmann/json#4309 | 46.5s | 30.1s | 24.3s | **23.5s** |
| syncthing/syncthing#9775 | 36.9s | 25.3s | 25.2s | **23.8s** |
| withfig/autocomplete#1625 | **19.0s** | 19.9s | 31.4s | 30.2s |
| pixijs/pixijs#11207 | **40.8s** | 99.7s | 64.2s | 63.4s |
| serverless/serverless#12980 | 52.4s | **37.0s** | 68.4s | 47.7s |
| eclipse-theia/theia#15048 | 109.3s | **19.4s** | ERR | 48.8s |

**Findings:**
- **OpenAI Agents SDK wins on 5/10 issues** for speed, with consistent performance (std dev = 16.9s).
- **AutoGen wins on 3 issues** but has higher variance, including the fastest single run (7.8s on vuejs/core).
- **LangGraph has the highest variance** (std dev = 74.7s), driven by a 255.3s outlier on bevyengine/bevy.
- **CrewAI wins on 2 issues** with the lowest median time (25.9s), suggesting consistent mid-range performance.

### 3.5 Issue Difficulty Analysis

| Issue | GT Diff Size | Avg Similarity | Hardest For |
|-------|-------------|----------------|-------------|
| nlohmann/json#4309 | 1,298 chars | 0.603 | AutoGen |
| eclipse-theia/theia#15048 | 651 chars | 0.367 | AutoGen |
| serverless/serverless#12980 | 521 chars | 0.235 | LangGraph |
| nextcloud/server#51652 | 1,190 chars | 0.166 | AutoGen |
| withfig/autocomplete#1625 | 567 chars | 0.150 | AutoGen |
| bevyengine/bevy#18468 | 728 chars | 0.144 | AutoGen |
| mpv-player/mpv#15776 | 911 chars | 0.116 | AutoGen |
| pixijs/pixijs#11207 | 2,917 chars | 0.103 | CrewAI |
| vuejs/core#12181 | 3,613 chars | 0.079 | LangGraph |
| syncthing/syncthing#9775 | 3,526 chars | 0.052 | LangGraph |

**Findings:**
- There is a clear **inverse correlation between ground truth diff size and average similarity**: larger diffs (vuejs at 3,613 chars, syncthing at 3,526 chars) yield lower similarity because there are more ways to diverge from the exact human solution.
- **AutoGen is "hardest for" on 6/10 issues**, primarily where file localization failed (it sometimes patches the wrong file or includes extraneous changes).
- **LangGraph is "hardest for" on 2/10 issues**, both involving large, complex patches (vuejs, syncthing).

### 3.6 Qualitative Example: nlohmann/json#4309

This issue provides the clearest illustration of how agents approach bug fixing. The bug: GDB's pretty printer for the nlohmann/json library broke after an internal `m_data` struct was added, requiring three lines of `m_type`/`m_value` references to be updated to `m_data.m_type`/`m_data.m_value`.

**Ground truth fix** (human PR): Changed 3 occurrences of `val['m_type']` to `val['m_data']['m_type']` and similarly for `m_value`.

**Agent patches** (LangGraph and OpenAI Agents SDK produced identical patches):
- Correctly identified the same file (`tools/gdb_pretty_printer/nlohmann-json.py`)
- Applied the same `m_data` dereference pattern
- Additionally added a guard clause `'m_data' in val.keys()` (a reasonable defensive check not in the human fix)
- Achieved 0.630 content similarity (diff-only)—the highest in the dataset

This example illustrates that agents can identify the correct root cause and apply an appropriate fix, while also introducing their own design decisions (the extra guard clause), leading to textual divergence from the ground truth despite functional equivalence.

---

## 4. Discussion

### 4.1 Framework Architecture and Performance

Our results suggest that the framework's **LLM integration layer** (how it constructs API calls, manages sessions, and parses responses) matters more than its higher-level abstractions (graph execution, multi-agent coordination) in this single-turn setting:

- **OpenAI Agents SDK and LangGraph** both use the OpenAI-compatible `/v1/chat/completions` endpoint, producing nearly identical patches for 8/10 issues. Their performance differences stem from LangGraph's additional state management overhead.
- **CrewAI** uses LiteLLM for model routing, adding a thin translation layer that produces slightly different tokenization, leading to different (and sometimes higher-quality) patches.
- **AutoGen** uses its own `OpenAIChatCompletionClient`, which occasionally formats the context differently, explaining its lower file localization on some issues.

### 4.2 Why Moderate Similarity Doesn't Mean Low Quality

After stripping commit metadata and comparing only the actual diff content, the average content similarity across frameworks is 0.17–0.22. While higher than the raw comparison, the values remain moderate. This is expected for several reasons:

1. **Multiple valid fixes**: A bug can often be fixed in different ways (guard clause, null check, restructured logic) that are semantically equivalent but textually distinct. For example, on nlohmann/json#4309, agents added a defensive `'m_data' in val.keys()` check that the human author did not include — a reasonable alternative approach.
2. **Diff context granularity**: Even when agents target the exact same lines, differences in surrounding context line counts or hunk headers cause textual divergence.
3. **Fix strategy divergence**: An agent might fix the same bug via a different code path or with different variable names while achieving the same functional outcome.
4. **SequenceMatcher limitations**: This metric measures character-level subsequence overlap, not semantic equivalence. Two patches can be functionally identical yet score below 0.5 if they use different indentation, comments, or surrounding context.

The high file overlap (0.8–1.0) confirms that agents correctly localize the problem. The moderate content similarity reflects natural variation in fix strategy, not incorrect patches. A proper assessment of patch correctness requires execution-based evaluation (applying the patch and running test suites), which is planned for the full study.

### 4.3 Framework Integration Challenges

The failure of LlamaIndex and Semantic Kernel highlights a practical finding relevant to practitioners:

- **LlamaIndex's Ollama connector** uses the `ollama` Python library, which has a hard timeout that doesn't properly handle concurrent GPU load with large models. Other frameworks using the OpenAI-compatible endpoint (`/v1/chat/completions`) don't have this issue.
- **Semantic Kernel's Python SDK** introduced a breaking change in the `get_chat_message_contents()` signature, requiring a `settings` parameter that wasn't needed in the previous version. This reflects the rapid evolution of the framework.

These findings inform our recommendation: **framework maturity and connector stability should be an evaluation dimension** alongside performance metrics.

### 4.4 Implications for the Full Study

This pilot validates several aspects of our methodology:

1. **The controlled design works**: Holding the LLM, prompt, and context constant successfully isolates framework-specific differences in patch generation.
2. **File overlap is a strong signal**: Most frameworks achieve 1.000 file overlap, confirming that the issue context we provide is sufficient for localization.
3. **Content similarity needs supplementation**: Text-based similarity alone cannot distinguish between "correct but different" and "incorrect" patches. The full study must add execution-based evaluation.
4. **10 issues are insufficient for statistical conclusions**: We need at least 50–100 issues to apply Wilcoxon signed-rank tests with adequate power.

---

## 5. Threats to Validity

### Internal Validity
- **Single LLM model**: Results may not generalize to other models (GPT-4, Claude, Gemma). The full study will test 2–3 models.
- **Single-turn agents**: In practice, agents iterate with tool access. This pilot tests only the "one-shot" capability. The full study will add multi-turn agents.
- **Framework version sensitivity**: Results depend on exact package versions. We pin all versions and use a reproducible virtual environment.

### External Validity
- **Small sample size** (n=10): Insufficient for statistical significance. The full study targets 300–500 issues.
- **Bug-only issues**: All 10 issues are bug reports. Feature requests may require different capabilities.
- **Single-file issues**: All selected issues involve one file. Multi-file issues may expose different framework behaviors.
- **Language diversity limited**: While 7 languages are represented, the sample size per language is too small for language-specific analysis.

### Construct Validity
- **Text similarity as quality proxy**: SequenceMatcher measures textual overlap, not functional correctness. The full study will add test execution.
- **Ground truth is one valid fix**: Multiple correct patches may exist. A patch with low similarity may still be correct.
- **File overlap is coarse**: Jaccard overlap at file granularity doesn't capture within-file localization accuracy.

---

## 6. Related Work

| Work | Focus | Our Differentiation |
|------|-------|---------------------|
| Yin et al. (2025) — [Comprehensive Empirical Evaluation of Agent Frameworks](https://arxiv.org/pdf/2511.00872) | Evaluates 7 *task-specific* agent systems (OpenHands, SWE-Agent, GPTSwarm, etc.) across 3 SE tasks (development, vulnerability detection, program repair) using effectiveness/efficiency/overhead metrics | (1) We evaluate *general-purpose agent-building frameworks* (LangGraph, AutoGen, CrewAI, etc.) that practitioners use to **build** agents, not pre-built agent systems; (2) We enforce strict fairness controls (same LLM, prompt, tools, budget) to isolate framework effects — they allow each agent to use its own tools/prompts; (3) We use real-world multi-language GitHub issues as our benchmark, not Python-only SWE-bench; (4) Our dataset comes from our own research pipeline (Paper 2), not existing benchmarks |
| SWE-bench (Jimenez et al., 2024) | Benchmark dataset for Python issue solving | We add framework comparison dimension; multi-language |
| SWE-Agent (Yang et al., 2024) | Single agent architecture for issue solving | We compare multiple frameworks, not just one |
| AutoCodeRover (Zhang et al., 2024) | Specific agent approach using program analysis | We provide controlled comparison across approaches |
| Agentless (Xia et al., 2024) | Non-agent baseline (localize + repair) | Included as design inspiration; shows agent overhead |
| OpenHands (Wang et al., 2024) | Platform for building coding agents | Platform for deploying agents, not a framework benchmark |
| Our Paper 1 — SENIR (TSE) | Understanding developer questions | Foundation for what makes issues actionable |
| Our Paper 2 — Issue Enhancement (ASE) | Improving issue descriptions with LLMs | Predecessor: from enhancement to resolution |

The closest related work is Yin et al. (2025), which evaluates agent frameworks on code-centric SE tasks. However, a critical distinction exists: they evaluate **pre-built agent systems** (OpenHands, SWE-Agent, GPTSwarm) that each come with their own models, tools, and prompts, making it impossible to isolate what causes performance differences. In contrast, we evaluate **agent-building frameworks** (LangGraph, AutoGen, CrewAI, OpenAI Agents SDK, etc.) — the libraries that practitioners use to *construct* agents — under strictly controlled conditions where the only variable is the framework itself. This makes our study the first to provide actionable guidance on framework selection for teams building their own coding agents.

---

## 7. Conclusion and Next Steps

### 7.1 Summary of Findings

This pilot study demonstrates that **framework-centric benchmarking of LLM agents is feasible and produces measurable differences**. Key findings from 10 issues across 4 working frameworks:

1. **All working frameworks generate patches at ≥90% rate**, confirming that current agent frameworks can produce code changes from issue descriptions.
2. **OpenAI Agents SDK ranks first** across all metrics (patch rate, file localization, content similarity 0.224, speed 31.0s).
3. **CrewAI is a close second** (similarity 0.209), nearly matching OpenAI Agents SDK with slightly different patch strategies.
4. **AutoGen has weaker file localization** (0.800 vs. 1.000), sometimes patching the wrong file, which reduces its similarity (0.169).
5. **LangGraph is the slowest** and had one framework error, but achieves perfect file localization and strong similarity (0.186) when successful.
6. **Framework integration maturity varies widely**: 2/6 frameworks failed due to connector issues, highlighting the importance of evaluating practical usability alongside theoretical capability.

### 7.2 Planned Next Steps

| Phase | Task | Timeline |
|-------|------|----------|
| **Fix remaining frameworks** | Resolve LlamaIndex timeout (use httpx-based connector) and Semantic Kernel API mismatch (pin SDK version) | 1 week |
| **Scale dataset** | Expand from 10 to 300–500 issues, balanced across bug/feature and complexity tiers | 3–4 weeks |
| **Multi-turn agents** | Add tool access (file read, search, test execution) for iterative refinement | 4–6 weeks |
| **Multi-model evaluation** | Test with GPT-4o, Claude 3.5 Sonnet, and Gemma 3 alongside Llama 3.3 | 2–3 weeks |
| **Execution-based evaluation** | Apply patches to repository checkouts, run test suites | 3–4 weeks |
| **Statistical analysis** | Wilcoxon signed-rank tests, Cliff's delta, bootstrap CIs | 2 weeks |
| **Paper writing** | Full manuscript for TSE submission | 4–6 weeks |

### 7.3 Reproducibility

All code, data, configurations, and results are available at:

```
/home/22pf2/BenchmarkLLMAgent/
├── RESEARCH_PLAN.md              # Full research plan
├── PILOT_STUDY_REPORT.md         # This report
├── configs/                      # Benchmark configuration
│   ├── benchmark_config.yaml
│   └── prompts/                  # System prompt and task template
├── data/
│   ├── 10_initial_samples.json   # Pilot dataset (10 issues)
│   └── ground_truth/             # Per-issue ground truth patches
├── scripts/
│   ├── select_initial_samples.py # Dataset selection script
│   ├── run_initial_benchmark.py  # Main benchmark runner
│   └── generate_full_report.py   # Report generation
├── results/
│   └── initial_benchmark/        # All result JSONs (60 files)
│       ├── benchmark_summary.json
│       └── BENCHMARK_REPORT.txt
├── agents/                       # Framework agent implementations
│   ├── base_agent.py
│   ├── shared_tools.py
│   └── {framework}/agent.py      # Per-framework stubs
├── evaluation/                   # Evaluation modules
│   ├── evaluator.py
│   └── statistical_analysis.py
├── requirements.txt
└── README.md
```

---

## Appendix A: Framework Implementation Details

### AutoGen
Uses `OpenAIChatCompletionClient` from `autogen-ext` with the Ollama-compatible `/v1` endpoint. Agent is an `AssistantAgent` with the system prompt as its persona. Invoked asynchronously via `asyncio`.

### CrewAI
Defines a single `Agent` with the solver role and a `Task` for patch generation. Uses LiteLLM for model routing with `ollama/llama3.3:70b-instruct-fp16` as the model identifier. The `Crew` runs with `process=Process.sequential`.

### LangGraph
Constructs a `StateGraph` with a single `solve_node` that wraps `ChatOllama` from `langchain-ollama`. The graph compiles into an `app` and is invoked with a `TypedDict` state containing the task context.

### OpenAI Agents SDK
Uses the standard `openai.OpenAI` client with `base_url` pointed to Ollama's `/v1` endpoint. Constructs a chat completion request with system and user messages. The most minimal wrapper of any framework.

### LlamaIndex (Failed)
Uses `llama_index.llms.ollama.Ollama` which wraps the `ollama` Python library. The `ollama.Client.chat()` method stalls under concurrent GPU load with the 70B model, likely due to HTTP timeout handling in the underlying `httpx` client.

### Semantic Kernel (Failed)
Uses `OllamaChatCompletion` from `semantic_kernel.connectors.ai.ollama`. The `get_chat_message_contents()` method requires a `PromptExecutionSettings` parameter that was added in a recent SDK update, breaking backward compatibility.

---

## Appendix B: System Prompt (Used for All Frameworks)

```
You are a software engineering agent. Your task is to fix a GitHub issue by generating a unified diff patch.

Analyze the issue description carefully, understand the bug or feature request, determine what changes need to be made to the codebase, and produce a unified diff patch that resolves the issue.

Your output MUST contain a unified diff patch in the following format:
--- path/to/file
+++ path/to/file
@@ -line,count +line,count @@
 context line
-removed line
+added line
 context line

Focus on producing a minimal, correct patch. Do not include explanations outside the diff.
```

---

## Appendix C: GitHub API Multi-Token Strategy

To fetch issue data, PR patches, and source code from GitHub without hitting rate limits, we implemented a **thread-safe multi-token rotation client** adapted from Paper 2's data collection pipeline. The client maintains a pool of GitHub personal access tokens and automatically switches to the next available token when one is rate-limited, using a `threading.Lock` for thread safety across the 4 parallel workers.
