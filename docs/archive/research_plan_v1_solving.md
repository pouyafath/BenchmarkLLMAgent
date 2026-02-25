# Paper 3: Benchmarking LLM Agent Frameworks for GitHub Issue Solving

## Research Trilogy Overview

| # | Paper | Venue | Focus | Status |
|---|-------|-------|-------|--------|
| 1 | SENIR: LLM-Based NER for Developer Chatroom Conversations | TSE | **Understanding** developer questions — what entities, intents, and features make chatroom questions resolvable | Published |
| 2 | LLM-Based Agents for GitHub Issue Enhancement | ASE 2026 | **Enhancing** GitHub issue descriptions — automatically improving issue quality to accelerate resolution | Draft/Submitted |
| 3 | Benchmarking LLM Agent Frameworks for GitHub Issue Solving | TSE (target) | **Solving** GitHub issues — comparing agent-building frameworks on automated issue resolution | **This work** |

### Research Trajectory

```
Paper 1: Understanding       Paper 2: Enhancing          Paper 3: Solving
(Chatroom NER/Intent)  --->  (Issue Enhancement)   --->  (Issue Resolution)
   Descriptive                  Prescriptive                Autonomous
   "What makes Qs              "Improve issue text         "Fix the code
    resolvable?"                to speed resolution"        directly"
```

---

## 1. Motivation

### 1.1 From Issue Enhancement to Issue Solving

In Paper 2, we built an **Issue Enhancer**: LLM-based agents that improve issue title/body text to increase the chance of faster resolution. The natural next step is to move from *improving issue reports* to **solving issues directly** using LLM-based agents.

### 1.2 The Current Landscape Problem

Recent progress in agentic coding systems (SWE-bench, SWE-Agent, AutoCodeRover, Agentless, etc.) shows promise, but existing comparisons are:

- **Model-centric**: LLM A vs LLM B (same framework, different models)
- **Prompt-centric**: prompt strategy A vs B (same framework, different prompts)
- **Benchmark-specific**: performance on SWE-bench only (selection bias toward Python, mature repos)

These comparisons miss a critical dimension: **framework-centric** evaluation.

### 1.3 Research Gap

> We lack a controlled benchmark that compares **agent-building frameworks** (e.g., LangGraph, LlamaIndex, Semantic Kernel, AutoGen, CrewAI, OpenAI Agents SDK) on the same GitHub issue-solving task under identical conditions.

### 1.4 Why This Matters

- Framework choice is one of the first architectural decisions practitioners make
- Frameworks differ in orchestration, tool-calling patterns, memory management, error recovery, and state management
- No existing study isolates framework effects from model/prompt/tool effects
- Software teams need evidence-based guidance for framework selection

---

## 2. Research Questions

| RQ | Question | Scope |
|----|----------|-------|
| **RQ1** | How do different agent-building frameworks compare in their ability to resolve GitHub issues? | Effectiveness (resolve rate, test pass rate, patch quality) |
| **RQ2** | What are the efficiency and cost trade-offs across frameworks? | Efficiency (tokens, time, cost, tool calls) |
| **RQ3** | How do framework characteristics (orchestration, memory, error handling) influence agent behavior and trajectory quality? | Process/Trajectory analysis |
| **RQ4** | How do framework performance differences vary across issue types (bug vs. feature), complexity levels, and repository characteristics? | Stratified analysis |

---

## 3. Approach

### 3.1 Benchmark Dataset Construction

#### Data Source
Reuse and extend the GitHub issue dataset pipeline from Paper 2 (43,708 issues from 1,000 repositories), then apply stricter filtering:

#### Filtering Criteria

| Filter | Description | Rationale |
|--------|-------------|-----------|
| Issue type | `bug` or `feature` label | Focus on actionable issues |
| Resolution status | Closed + resolved | Need known-solvable issues |
| Linked merged PR | Issue linked to ≥1 merged PR | Ground truth for evaluation |
| Solid PR quality | PR clearly reflects the issue solution (not refactoring noise) | Clean ground truth |
| Repository state | Repo accessible + specific commit available | Reproducibility |
| Test environment | (Optional) Repository has test suite | Enables functional validation |

#### Dataset Size Target
- **Primary benchmark**: 300-500 issues (balanced across bug/feature, complexity levels)
- **Extended set**: 1,000+ issues for large-scale evaluation

#### Complexity Stratification
Leverage the LightGBM difficulty classifier from Paper 2:
- **Simple**: Resolution time < 25th percentile for repo
- **Moderate**: 25th-75th percentile
- **Complex**: > 75th percentile

### 3.2 Ground Truth Design

#### Primary: Functional Ground Truth
> Does the agent's patch **solve the issue**?

Evaluation pipeline:
1. Apply agent's patch to the pre-fix repository state
2. Run issue-relevant test cases (if available)
3. Run full test suite for regression detection
4. Manual inspection for a stratified sample

#### Secondary: PR Alignment
> Does the agent's patch **align with the human-authored merged PR**?

Alignment metrics (diagnostic, not primary):
- File overlap with merged PR
- Function/method overlap
- Edit localization similarity (AST-level)
- Patch size comparison

### 3.3 Framework Benchmarking

#### Candidate Frameworks

| Framework | Org | Key Differentiator | Priority |
|-----------|-----|-------------------|----------|
| **LangGraph** | LangChain | Graph-based orchestration, state machines, checkpointing | High (used in Paper 2) |
| **LlamaIndex** | LlamaIndex | RAG-native, workflow engine, data-aware agents | High |
| **Semantic Kernel** | Microsoft | Enterprise-grade, planner abstraction, .NET/Python SDK | High |
| **AutoGen** | Microsoft | Multi-agent conversations, code execution | High |
| **CrewAI** | CrewAI | Role-based multi-agent, process types (sequential/hierarchical) | Medium |
| **OpenAI Agents SDK** | OpenAI | Handoffs, guardrails, tracing, minimal abstraction | Medium |

#### Per-Framework Implementation
Each framework implementation must:
1. Accept a standardized issue specification (title, body, repo URL, commit SHA)
2. Use the shared tool interface (see 3.4)
3. Produce a standardized output (patch + rationale + execution trace)
4. Respect the shared budget constraints

### 3.4 Fairness Controls (Unified Across All Frameworks)

**Critical**: All frameworks must share the following to isolate framework effects.

| Control Variable | Specification |
|-----------------|---------------|
| **LLM Model** | Same model for all (e.g., GPT-4o, Llama 3.3-70B); test with 2-3 models |
| **Decoding settings** | temperature=0, top_p=1, same max_tokens |
| **Toolset** | Identical tool implementations (repo clone, file read/write, search, test run, git operations) |
| **Prompts / Task instructions** | Same system prompt, same task description template |
| **Token budget** | Same max total tokens per issue (e.g., 100K input + 50K output) |
| **Time budget** | Same wall-clock timeout per issue (e.g., 30 min) |
| **Turn budget** | Same max interaction turns (e.g., 30 turns) |
| **Stopping criteria** | Same conditions: patch produced, budget exhausted, or explicit stop |
| **Output schema** | Unified: `{patch, rationale, trace, metadata}` |
| **Execution environment** | Same Docker container spec per repository |

### 3.5 Shared Tool Interface

All frameworks call the same underlying tool implementations:

```
Tools:
├── repo_tools/
│   ├── clone_repo(url, commit_sha)
│   ├── list_files(path, pattern)
│   ├── read_file(path, start_line, end_line)
│   ├── write_file(path, content)
│   ├── search_code(query, file_pattern)
│   └── get_repo_structure(depth)
├── git_tools/
│   ├── git_diff()
│   ├── git_log(n)
│   └── create_patch()
├── test_tools/
│   ├── run_tests(test_path)
│   ├── run_specific_test(test_file, test_name)
│   └── get_test_results()
└── analysis_tools/
    ├── get_issue_context(issue_url)
    ├── search_similar_issues(query, k)
    └── get_pr_files(pr_url)
```

### 3.6 Output Specification

Every framework agent produces:

```json
{
  "issue_id": "owner/repo#123",
  "framework": "langgraph",
  "model": "gpt-4o",
  "patch": "unified diff string",
  "rationale": "explanation of the fix",
  "trace": [
    {"turn": 1, "action": "tool_call", "tool": "read_file", "args": {...}, "result_summary": "...", "tokens_used": 1234, "time_ms": 500},
    ...
  ],
  "metadata": {
    "total_tokens": 45000,
    "total_time_ms": 120000,
    "total_turns": 12,
    "total_tool_calls": 25,
    "failed_tool_calls": 2,
    "termination_reason": "patch_produced"
  }
}
```

---

## 4. Evaluation Metrics

### A. Correctness / Outcome Metrics (Primary)

| Metric | Definition | Measurement |
|--------|-----------|-------------|
| **Resolve Rate (%)** | Fraction of issues successfully solved | Automated test pass + manual validation |
| **Patch Apply Rate (%)** | Patch cleanly applies to target repo state | `git apply --check` |
| **Task Test Pass Rate (%)** | Issue-relevant tests pass after patch | Run targeted tests |
| **Regression Rate (%)** | Previously passing tests now fail | Full test suite before/after comparison |

### B. Efficiency / Cost Metrics

| Metric | Definition | Lower is Better |
|--------|-----------|-----------------|
| **Total Tokens Used** | Sum of input + output tokens across all turns | Yes |
| **Wall-Clock Time** | End-to-end time from issue ingestion to patch | Yes |
| **Time to First Valid Patch** | Time until first `git apply`-able patch | Yes |
| **Cost per Resolved Issue** | API cost / number of resolved issues | Yes |

### C. Agent Process / Trajectory Metrics

| Metric | Definition | Insight |
|--------|-----------|---------|
| **# Turns** | Total interaction turns | Framework verbosity |
| **# Tool Calls** | Total tool invocations | Framework exploration style |
| **Failed Tool Calls** | Invalid or errored tool calls | Framework robustness |
| **Looping Score** | Repeated similar actions (cosine similarity of consecutive turns) | Framework stuck detection |
| **Termination Type Distribution** | {success, timeout, premature_stop, invalid_patch, error} | Framework reliability |

### D. Ground Truth Alignment (Secondary Diagnostic)

| Metric | Definition | Purpose |
|--------|-----------|---------|
| **File Overlap** | Jaccard similarity of changed files vs merged PR | Localization accuracy |
| **Function Overlap** | Overlap of modified functions/methods | Granularity accuracy |
| **Edit Localization** | AST-level similarity of edit locations | Precision of changes |
| **Patch Size Ratio** | Agent patch size / PR patch size | Over/under-patching |

### E. Analysis Plan

#### Cross-cutting Comparisons
- **Overall framework ranking** (all metrics)
- **Bug vs Feature** stratification
- **Complexity tier** stratification (Simple / Moderate / Complex)
- **Repository characteristics** (size, language, test coverage, stars)

#### Statistical Rigor
- Paired comparisons across frameworks (same issues)
- Wilcoxon signed-rank tests for non-normal distributions
- Cliff's delta for effect sizes
- Bootstrap confidence intervals for resolve rates
- Bonferroni correction for multiple comparisons

---

## 5. Experimental Design

### 5.1 Independent Variables

| Variable | Levels |
|----------|--------|
| **Framework** | LangGraph, LlamaIndex, Semantic Kernel, AutoGen, CrewAI, OpenAI Agents SDK |
| **Model** (secondary) | 2-3 models (e.g., GPT-4o, Llama 3.3-70B, Claude 3.5 Sonnet) |
| **Issue type** | Bug, Feature |
| **Complexity** | Simple, Moderate, Complex |

### 5.2 Dependent Variables
All metrics from Section 4 (A through D).

### 5.3 Experimental Matrix

Primary experiment: **6 frameworks x 2-3 models x 300-500 issues**
= ~3,600 to 9,000 individual runs

### 5.4 Execution Plan

| Phase | Task | Duration (est.) |
|-------|------|-----------------|
| **Phase 1** | Dataset construction + filtering + ground truth preparation | 3-4 weeks |
| **Phase 2** | Shared tool interface implementation + Docker environments | 2-3 weeks |
| **Phase 3** | Framework agent implementations (6 frameworks) | 4-6 weeks |
| **Phase 4** | Pilot runs (50 issues x 6 frameworks x 1 model) | 1-2 weeks |
| **Phase 5** | Full benchmark execution | 3-4 weeks |
| **Phase 6** | Evaluation, analysis, statistical tests | 2-3 weeks |
| **Phase 7** | Paper writing | 4-6 weeks |
| **Total** | | **~20-28 weeks** |

---

## 6. Expected Contributions

1. **First controlled framework benchmark** for LLM-based issue solving that isolates framework effects from model/prompt/tool effects
2. **Reusable benchmark dataset** of GitHub issues with ground-truth solutions (linked merged PRs)
3. **Comprehensive evaluation framework** spanning correctness, efficiency, trajectory quality, and ground truth alignment
4. **Evidence-based framework comparison** with statistical rigor, providing actionable guidance for practitioners
5. **Open-source benchmark toolkit** for reproducible evaluation of future agent frameworks

---

## 7. Positioning Relative to Related Work

| Work | Focus | Our Differentiation |
|------|-------|---------------------|
| SWE-bench (Jimenez et al., 2024) | Benchmark dataset for issue solving | We use it as inspiration but add framework comparison dimension |
| SWE-Agent (Yang et al., 2024) | Single agent architecture | We compare multiple frameworks, not just one |
| AutoCodeRover (Zhang et al., 2024) | Specific agent approach | We provide controlled comparison across approaches |
| Agentless (Xia et al., 2024) | Non-agent baseline | Included as baseline comparison point |
| OpenHands (Wang et al., 2024) | Platform for agents | Platform, not framework benchmark |
| Our Paper 1 (TSE) | Understanding developer questions | Foundation for what makes issues actionable |
| Our Paper 2 (ASE 2026) | Enhancing issue descriptions | Predecessor — from enhancement to resolution |

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Framework APIs change during study | Pin framework versions; use Docker for reproducibility |
| Some frameworks can't support the shared tool interface cleanly | Allow thin adapter layers; document deviations |
| Insufficient test coverage in target repos | Use repos with known test suites; supplement with manual evaluation |
| API cost for commercial models | Budget planning; use open-source models as primary; commercial as secondary |
| Inconsistent framework maturity levels | Document maturity; separate analysis for mature vs emerging frameworks |
| Reviewer concern: "just an empirical comparison" | Emphasize insights into *why* frameworks differ (orchestration, memory, error handling analysis) |

---

## 9. Target Venue

**Primary**: IEEE Transactions on Software Engineering (TSE)
- Fits the trilogy: Paper 1 (TSE) → Paper 2 (ASE) → Paper 3 (TSE)
- TSE values comprehensive empirical studies with statistical rigor
- Framework benchmarking aligns with TSE's interest in tools and methods evaluation

**Alternative**: ICSE 2027, FSE 2027, ISSTA 2027
