# Paper 3: Benchmarking LLM-Based Agents for GitHub Issue Enhancement

## Research Trilogy Overview

| # | Paper | Venue | Focus | Status |
|---|-------|-------|-------|--------|
| 1 | SENIR: LLM-Based NER for Developer Chatroom Conversations | TSE | **Understanding** developer questions — what entities, intents, and features make chatroom questions resolvable | Published |
| 2 | LLM-Based Agents for GitHub Issue Enhancement | ASE 2026 | **Enhancing** GitHub issue descriptions — automatically improving issue quality to accelerate resolution | Draft/Submitted |
| 3 | Benchmarking LLM-Based Agents for GitHub Issue Enhancement | TSE (target) | **Benchmarking** — comparing ready-to-use agents and framework-built agents on issue enhancement, and measuring downstream impact on automated issue solving | **This work** |

### Research Trajectory

```
Paper 1: Understanding       Paper 2: Enhancing          Paper 3: Benchmarking Enhancement
(Chatroom NER/Intent)  --->  (Issue Enhancement)   --->  (How well do different agents
   Descriptive                  Prescriptive                enhance issues? And does
   "What makes Qs              "Improve issue text          enhancement actually help
    resolvable?"                to speed resolution"         automated solving?)
```

---

## 1. Motivation

### 1.1 Why Benchmark Issue Enhancement?

In Paper 2, we built a custom Issue Enhancer using a specific LLM and framework. But since then, the landscape has exploded: dozens of general-purpose AI coding agents (OpenHands, SWE-Agent, Copilot, Sweep, Cline, etc.) and multiple agent-building frameworks (LangGraph, AutoGen, CrewAI, OpenAI Agents SDK, etc.) now exist. A natural question arises:

> **If we asked all of these agents to enhance a GitHub issue, how would they compare? And does enhancement actually improve downstream automated resolution?**

### 1.2 The Current Gap

- Paper 2 demonstrated that issue enhancement is valuable, but tested only one approach
- No benchmark exists for comparing **issue enhancement** capabilities across agents
- The rapidly growing agent ecosystem makes comparative evaluation essential for practitioners
- No study has measured the **downstream impact** of enhancement on automated solving

### 1.3 Two Types of Enhancement Agents

We identify two fundamentally different categories of agents that can perform issue enhancement:

| Category | Description | Examples |
|----------|-------------|---------|
| **Category A: Ready-to-Use Agents** | Pre-built, commercially or open-source available agents that can be directed to enhance issues out-of-the-box | OpenHands, SWE-Agent, GitHub Copilot, Sweep, Cline, etc. |
| **Category B: Framework-Built Agents** | Custom agents built using agent-building frameworks, specifically designed for issue enhancement | Agents built with LangGraph, AutoGen, CrewAI, OpenAI Agents SDK, LlamaIndex, Semantic Kernel |

This dual-category design provides two complementary research angles:
- **Category A** answers: *"Which existing tool does the best job at issue enhancement?"*
- **Category B** answers: *"Which framework is best for building your own enhancement agent?"*

### 1.4 The Solving-as-Evaluation Loop

A unique contribution of this work is using **automated issue solving as an evaluation mechanism** for enhancement quality:

```
                    ┌──────────────────────┐
                    │   Original Issue     │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
         ┌─────────│   Enhancement Agent   │─────────┐
         │         │   (A or B)            │         │
         │         └───────────────────────┘         │
         │                                           │
┌────────▼────────┐                      ┌───────────▼──────────┐
│  Original Issue │                      │   Enhanced Issue      │
│  (unchanged)    │                      │   (improved by agent) │
└────────┬────────┘                      └───────────┬──────────┘
         │                                           │
┌────────▼────────┐                      ┌───────────▼──────────┐
│  Solver Agent   │                      │   Solver Agent        │
│  tries to fix   │                      │   tries to fix        │
└────────┬────────┘                      └───────────┬──────────┘
         │                                           │
┌────────▼────────┐                      ┌───────────▼──────────┐
│  Patch_before   │                      │   Patch_after         │
└────────┬────────┘                      └───────────┬──────────┘
         │                                           │
         └──────────────┬────────────────────────────┘
                        │
              ┌─────────▼─────────┐
              │  Compare patches  │
              │  against GT       │
              │  (ground truth)   │
              └───────────────────┘

  Enhancement Value = Patch_after quality − Patch_before quality
```

This design lets us measure not just "how good is the enhanced text?" but "does enhancement actually help an automated solver produce better patches?"

---

## 2. Research Questions

| RQ | Question | Scope |
|----|----------|-------|
| **RQ1** | How do ready-to-use agents (Category A) compare in their ability to enhance GitHub issue descriptions? | Enhancement quality across existing agents |
| **RQ2** | How do framework-built agents (Category B) compare when specifically designed for issue enhancement under controlled conditions? | Framework comparison (same LLM, tools, prompt) |
| **RQ3** | Does issue enhancement improve the performance of automated issue-solving agents? | Downstream impact measurement |
| **RQ4** | How do enhancement quality and downstream solving improvement vary across issue types, complexity levels, and repository characteristics? | Stratified analysis |

---

## 3. Approach

### 3.1 Benchmark Dataset

#### Data Source
Reuse the GitHub issue dataset from Paper 2 (43,708 issues from 1,000 repositories), with the golden dataset of 400 curated issues as the primary source.

#### Selection Criteria for Benchmark Issues
| Filter | Description | Rationale |
|--------|-------------|-----------|
| Resolution status | Closed + resolved via merged PR | Need ground truth for solving evaluation |
| Issue quality range | Mix of well-written and poorly-written issues | Test enhancement on varying quality levels |
| Linked merged PR | Issue linked to ≥1 merged PR with code changes | Ground truth for solver evaluation |
| Language diversity | Multiple programming languages | Generalizability |
| Complexity range | Simple, Moderate, Complex (via Paper 2's LightGBM classifier) | Stratified analysis |

#### Dataset Size Target (Iterative)

- **Iteration 1 (pilot)**: 10 issues — validate full workflow end-to-end, fix bugs, tune configs. Uses existing `data/samples/pilot_10_samples.json` and `data/ground_truth/`.
- **Iteration 2 (primary)**: 200 issues — full benchmark for paper results. Select from Paper 2 golden dataset with Phase 1 criteria.
- **Extended set**: 400+ issues for future large-scale evaluation.

### 3.2 Enhancement Task Definition

Given an original GitHub issue (title + body), the enhancement agent must produce an improved version that is:

| Dimension | What Enhancement Means |
|-----------|----------------------|
| **Completeness** | Adding missing information: reproduction steps, expected/actual behavior, environment info |
| **Clarity** | Restructuring unclear descriptions, removing ambiguity |
| **Actionability** | Making the issue more specific so a developer (or solver agent) knows exactly what to fix |
| **Structure** | Proper formatting, sections, code blocks, error messages |
| **Context** | Adding relevant code references, related issues, affected components |

#### Enhancement Output Schema
```json
{
  "original_title": "...",
  "enhanced_title": "...",
  "original_body": "...",
  "enhanced_body": "...",
  "enhancement_metadata": {
    "sections_added": ["reproduction_steps", "expected_behavior", ...],
    "labels_suggested": ["bug", "priority:high"],
    "components_identified": ["auth module", "user service"],
    "related_files_suggested": ["src/auth/login.py"],
    "enhancement_rationale": "..."
  }
}
```

### 3.3 Category A: Ready-to-Use Agents

We select 10 existing agents/tools that can be directed to perform issue enhancement. These are **used as-is** (their own models, prompts, tools) — we evaluate their real-world, out-of-the-box capability.

#### Top 10 Ready-to-Use Agents for Issue Enhancement

| # | Agent | Type | Why Suitable for Enhancement | Access |
|---|-------|------|------------------------------|--------|
| 1 | **OpenHands** | Open-source coding agent | Full repo access, can read codebase to enrich issue context; 72% SWE-bench; self-improving capabilities | Free, open-source |
| 2 | **SWE-Agent** | Open-source coding agent | Agent-Computer Interface for repo exploration; can analyze code to understand issues; Princeton/Stanford research | Free, open-source |
| 3 | **GitHub Copilot Coding Agent** | Commercial agent | Native GitHub integration; can be assigned issues; understands repo context; auto-triage capabilities | Copilot Pro+/Enterprise |
| 4 | **Sweep** | Open-source issue resolver | Purpose-built for GitHub issues; reads codebase, plans solutions; can be redirected to enhance rather than solve | Free, open-source |
| 5 | **Aider** | Open-source coding assistant | Git-native; BYO model; strong codebase understanding; can analyze and describe issues in context | Free, open-source |
| 6 | **Cline** | Open-source IDE agent | Local-first; editor-native; multi-model support; can explore repos and improve issue descriptions | Free, open-source |
| 7 | **MAGIS** | Research multi-agent framework | Multi-agent (Manager, Repo Custodian, Developer, QA); designed for GitHub issue understanding | Open-source, research |
| 8 | **Copilot Workspace** | Commercial platform | Issue-to-plan-to-spec pipeline; explicitly designed to understand and decompose issues | Preview access |
| 9 | **ChatBR** | Research chatbot | Specifically designed for bug report quality assessment and improvement using ChatGPT | Research prototype |
| 10 | **CodeRabbit** | Commercial code review agent | Deep repository understanding; PR analysis capabilities; can analyze issue context against codebase | Free tier available |

#### How These Agents Will Be Used

Each agent receives the same prompt directive:

> *"You are given a GitHub issue. Your task is to enhance this issue by improving its title and body. Make it more complete, clear, actionable, and well-structured. Add missing information such as reproduction steps, expected/actual behavior, relevant code references, and environment details where possible. Use the repository context to enrich the issue. Output the enhanced title and enhanced body."*

Each agent uses its **own** model, tools, and internal prompts — we evaluate their real-world capability as a user would experience it.

### 3.4 Category B: Framework-Built Agents

Using the same 6 frameworks from our pilot study, we build **controlled enhancement agents** where the only variable is the framework:

| Framework | Organization | Status from Pilot |
|-----------|-------------|-------------------|
| **OpenAI Agents SDK** | OpenAI | Working (ranked #1 in pilot) |
| **CrewAI** | CrewAI | Working (ranked #2 in pilot) |
| **AutoGen** | Microsoft | Working (ranked #3 in pilot) |
| **LangGraph** | LangChain | Working (ranked #4 in pilot) |
| **LlamaIndex** | LlamaIndex | To be fixed (connector issue) |
| **Semantic Kernel** | Microsoft | To be fixed (SDK version issue) |

#### Fairness Controls (Same for All Framework Agents)

| Control Variable | Specification |
|-----------------|---------------|
| **LLM Model** | Same model for all (e.g., Llama 3.3 70B, GPT-4o) |
| **System Prompt** | Identical enhancement prompt |
| **Tools** | Same tool access (repo read, file search, issue context) |
| **Token/Time Budget** | Same limits |
| **Output Schema** | Same structured output format |
| **Repository Context** | Same source code provided |

### 3.5 Solver Agents for Downstream Evaluation

We reuse the solver agents from our pilot study to measure enhancement impact:

```
For each issue I in benchmark:
  For each solver S in {OpenAI_SDK, CrewAI, AutoGen, LangGraph}:
    1. Patch_original = S.solve(I.original)
    2. For each enhancer E in {Category_A_agents ∪ Category_B_agents}:
       a. I_enhanced = E.enhance(I.original)
       b. Patch_enhanced = S.solve(I_enhanced)
       c. Compare Patch_original vs Patch_enhanced against ground truth
```

This creates a matrix: **enhancer × solver × issue**, allowing us to measure enhancement impact across different solver capabilities.

---

## 4. Evaluation Metrics

### A. Enhancement Quality Metrics (Direct)

| Metric | Definition | Measurement |
|--------|-----------|-------------|
| **Completeness Score** | Does the enhanced issue have all expected sections? | Checklist: title, description, steps-to-reproduce, expected/actual behavior, environment |
| **Information Gain** | How much new information was added? | Token/section count delta, new sections added |
| **Clarity Improvement** | Is the enhanced text clearer? | Readability score delta (Flesch-Kincaid, etc.) |
| **Actionability Score** | Does the enhancement make the issue more specific? | Presence of file references, function names, error messages, code snippets |
| **Factual Accuracy** | Does the enhancement introduce false information? | Manual validation on stratified sample |
| **Structure Quality** | Is the enhanced issue well-formatted? | Markdown structure, proper sections, code blocks |

### B. Downstream Solving Metrics (Indirect — Key Innovation)

| Metric | Definition | Measurement |
|--------|-----------|-------------|
| **Patch Quality Delta** | Improvement in solver patch quality after enhancement | Content similarity (enhanced) − Content similarity (original) |
| **File Localization Delta** | Improvement in targeting correct files | File overlap (enhanced) − File overlap (original) |
| **Solve Rate Delta** | Change in successful patch generation rate | Patch rate (enhanced) − Patch rate (original) |
| **Solver Time Delta** | Change in solver speed | Time (enhanced) − Time (original) |

### C. Efficiency Metrics

| Metric | Definition |
|--------|-----------|
| **Enhancement Time** | Wall-clock time for enhancement |
| **Enhancement Tokens** | Total tokens consumed |
| **Enhancement Cost** | API cost (for commercial agents) |

### D. Cross-Analysis

- Category A vs Category B overall comparison
- Best ready-to-use agent vs best framework-built agent
- Enhancement quality vs downstream solving improvement (correlation)
- Issue type × enhancement quality interaction
- Complexity × enhancement value interaction

---

## 5. Experimental Design

### 5.1 Independent Variables

| Variable | Levels |
|----------|--------|
| **Enhancement Agent** | 10 ready-to-use (Cat A) + 6 framework-built (Cat B) = 16 agents |
| **Solver Agent** | 4 working solvers from pilot (OpenAI SDK, CrewAI, AutoGen, LangGraph) |
| **Issue Quality** | Low / Medium / High (original quality) |
| **Issue Complexity** | Simple / Moderate / Complex |
| **LLM Model** (Cat B only) | 2–3 models |

### 5.2 Experimental Matrix

**Iteration 1 (10 issues):**
- Enhancement runs: N agents × 10 issues
- Solving runs: 4 solvers × (1 original + N enhanced) × 10 issues
- Purpose: validate pipeline, fix bugs, tune configs

**Iteration 2 (200 issues):**
- Enhancement runs: 16 agents × 200 issues = 3,200
- Solving runs: 4 solvers × (1 original + 16 enhanced) × 200 issues = 13,600
- Total: ~16,800 individual runs for full benchmark

### 5.3 Execution Plan (Iterative)

**Iteration 1 — Full workflow on 10 issues:**
| Step | Task |
|------|------|
| 1 | Implement 1–3 Category A + 1–2 Category B enhancement agents |
| 2 | Run enhancement benchmark on 10 issues |
| 3 | Run solver benchmark (before + after enhancement) |
| 4 | Generate reports, fix bugs, validate end-to-end |

**Iteration 2 — Scale to 200 issues:**
| Step | Task |
|------|------|
| 1 | Select 200 issues from golden dataset, prepare ground truth |
| 2 | Run full enhancement benchmark |
| 3 | Run full solving benchmark |
| 4 | Statistical analysis, stratified evaluation |
| 5 | Paper writing |

See `ROADMAP.md` for detailed handoff instructions.

---

## 6. Expected Contributions

1. **First benchmark for issue enhancement agents** — comparing both ready-to-use and framework-built agents on issue enhancement quality
2. **Novel evaluation methodology** — using automated solving as a downstream measure of enhancement value ("Does better issue text lead to better patches?")
3. **Dual-category comparison** — ready-to-use agents vs custom framework-built agents, providing guidance for both practitioners and researchers
4. **Reusable benchmark dataset** — curated GitHub issues with quality annotations and ground-truth solutions
5. **Practical guidance** — which existing agent to use for issue enhancement, and which framework to build on

---

## 7. Positioning Relative to Related Work

| Work | Focus | Our Differentiation |
|------|-------|---------------------|
| Yin et al. (2025) — [Agent Framework Evaluation](https://arxiv.org/pdf/2511.00872) | Evaluates 7 agent systems on code-centric SE tasks (dev, vuln detection, repair) | We focus on **issue enhancement** (not solving), compare both ready-to-use agents AND frameworks, and measure downstream solving impact |
| SWE-bench (Jimenez et al., 2024) | Benchmark for issue solving | We benchmark **issue enhancement**, not solving; solving is our evaluation mechanism |
| ChatBR (2024) | ChatGPT-based bug report quality improvement | Single tool, no framework comparison; no downstream solving evaluation |
| Burt (2023) | Interactive chatbot for bug reporting | Interactive approach only; no benchmark comparison |
| SWE-Agent (Yang et al., 2024) | Single agent for issue resolution | We include it as one of 10 Category A agents; we evaluate enhancement, not solving |
| OpenHands (Wang et al., 2024) | Platform for coding agents | We include it as one of 10 Category A agents |
| Our Paper 1 — SENIR (TSE) | Understanding developer questions | Foundation: what makes issues actionable |
| Our Paper 2 — Issue Enhancement (ASE) | Single-approach issue enhancement | We benchmark 16 agents; add downstream solving evaluation; extend from single to comparative |

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Some Category A agents may not support enhancement natively | Frame as "analyze and improve this issue" — all coding agents can do text analysis |
| Enhancement may not measurably improve solving | This is itself a finding worth reporting; we can analyze which types of issues benefit most |
| High computational cost (16,800 runs) | Prioritize: start with 50 issues × top agents; scale up for promising comparisons |
| Category A agents use different models, making comparison unfair | Explicitly position as "real-world comparison" — users also choose based on the full package |
| Framework API changes during study | Pin all versions; Docker environments |
| Enhancement introduces hallucinated information | Include factual accuracy metric; manual validation on sample |

---

## 9. Target Venue

**Primary**: IEEE Transactions on Software Engineering (TSE)
- Completes the trilogy: Paper 1 (TSE) → Paper 2 (ASE) → Paper 3 (TSE)
- TSE values comprehensive empirical studies with controlled comparisons
- The dual-category design + downstream evaluation provides the depth TSE expects

**Alternative**: ICSE 2027, FSE 2027

---

## Appendix: Top 10 Ready-to-Use Agents — Detailed Profiles

### 1. OpenHands (formerly OpenDevin)
- **Repository**: https://github.com/All-Hands-AI/OpenHands
- **Stars**: 68,000+ | **License**: MIT
- **Architecture**: Single-agent with multi-agent delegation; event-stream interaction
- **LLM**: Configurable (GPT-4o, Claude, Llama, etc.)
- **Why for Enhancement**: Full repo access via sandboxed Docker; can read source code to understand what an issue is really about; can identify relevant files/functions and add them to the issue description; self-improving agent that has contributed 37% of its own recent commits
- **Enhancement Strategy**: Give it the issue + repo access → ask it to produce an enhanced version with code context, affected files, and structured sections

### 2. SWE-Agent
- **Repository**: https://github.com/princeton-nlp/SWE-agent
- **Stars**: 18,500+ | **License**: MIT
- **Architecture**: Single-agent with Agent-Computer Interface (ACI)
- **LLM**: Configurable (GPT-4o, Claude Sonnet, etc.)
- **Why for Enhancement**: Custom bash tools for repo navigation (search_dir, open, edit); designed to understand GitHub issues deeply before fixing them; its issue analysis phase is essentially enhancement
- **Enhancement Strategy**: Use its issue analysis + code search to produce a context-enriched issue description

### 3. GitHub Copilot Coding Agent
- **Access**: GitHub Copilot Pro+ or Enterprise
- **Architecture**: GitHub-hosted runner, autonomous agent
- **LLM**: GitHub's internal models
- **Why for Enhancement**: Native GitHub integration; understands repository structure; designed for issue-to-PR workflow where issue understanding is step 1
- **Enhancement Strategy**: Assign the issue to Copilot with enhancement instructions; leverage its built-in repo understanding

### 4. Sweep
- **Repository**: https://github.com/sweepai/sweep
- **Stars**: 7,000+ | **License**: AGPL-3.0
- **Architecture**: Autonomous issue-to-PR agent with codebase search
- **LLM**: GPT-4, configurable
- **Why for Enhancement**: Purpose-built to read GitHub issues and map them to code; its issue analysis step already involves understanding affected files, components, and solution paths
- **Enhancement Strategy**: Redirect its analysis output to produce enhanced issue text instead of code changes

### 5. Aider
- **Repository**: https://github.com/paul-gauthier/aider
- **Stars**: 30,000+ | **License**: Apache-2.0
- **Architecture**: CLI-based pair programming; git-native
- **LLM**: Configurable (any model via API)
- **Why for Enhancement**: Deep codebase understanding via repo mapping; can identify relevant files, analyze code, and describe what needs to change; strong git integration for understanding history
- **Enhancement Strategy**: Point it at a repo + issue → ask it to describe what the issue means in code terms, adding file references and technical context

### 6. Cline
- **Repository**: https://github.com/cline/cline
- **Stars**: 40,000+ | **License**: Apache-2.0
- **Architecture**: IDE-native agent (VS Code); local-first with approval gates
- **LLM**: Configurable (local via Ollama, or cloud)
- **Why for Enhancement**: Editor-native access to full project; can explore code, read files, and understand structure; multi-model support allows testing with different LLMs
- **Enhancement Strategy**: Load the repo in VS Code → ask Cline to analyze the issue and produce an enriched version with code references

### 7. MAGIS
- **Repository**: Research prototype (from MAGIS paper)
- **Architecture**: Multi-agent (Manager, Repository Custodian, Developer, QA Engineer)
- **LLM**: GPT-4
- **Why for Enhancement**: Its Repository Custodian agent specifically understands code structure; the Manager agent decomposes tasks; the multi-agent discussion can produce rich issue analysis
- **Enhancement Strategy**: Use the Manager + Repository Custodian phase (before Developer acts) to produce enhanced issue understanding

### 8. Copilot Workspace
- **Access**: GitHub preview program
- **Architecture**: Issue → Specification → Plan → Implementation pipeline
- **LLM**: GitHub's internal models
- **Why for Enhancement**: Its core workflow starts with issue understanding and produces a "specification" — a structured analysis of what the issue means and what needs to change. This specification IS issue enhancement
- **Enhancement Strategy**: Use the specification/plan output as the enhanced issue description

### 9. ChatBR
- **Paper**: "Automated Assessment and Improvement of Bug Report Quality Using ChatGPT" (IEEE 2024)
- **Architecture**: ChatGPT-based quality assessment + improvement pipeline
- **LLM**: ChatGPT (GPT-3.5/4)
- **Why for Enhancement**: The only tool specifically designed for bug report quality improvement; assesses completeness, clarity, and reproducibility, then generates enhanced versions
- **Enhancement Strategy**: Direct application — it was built for exactly this task

### 10. CodeRabbit
- **Website**: https://coderabbit.ai
- **Architecture**: AI code review agent with deep repo understanding
- **LLM**: Multiple models
- **Why for Enhancement**: Deep understanding of codebases through PR review; can analyze an issue against the codebase to identify affected files, similar past issues, and relevant test cases
- **Enhancement Strategy**: Feed it an issue + repo context → ask it to produce an enriched analysis including affected components, related code, and suggested test scenarios
