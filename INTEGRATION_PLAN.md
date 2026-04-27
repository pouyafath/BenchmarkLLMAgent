# CL-Enhanced Agent (Gemma 3-12B) Integration Plan

**Goal**: Integrate the CL-Enhanced Agent from `/home/22pf2/LLMforGithubIssuesRefactor/` as the 4th enhancer in the BenchmarkLLMAgent 50-issue experiment to compare against TRAE, SWE-agent, and Aider.

---

## 1. Architecture Overview

### Source Agent (LLMforGithubIssuesRefactor)
- **Location**: `/home/22pf2/LLMforGithubIssuesRefactor/`
- **Agent**: V2_29 (CL-Enhanced Agent with continuous learning)
- **Model**: Gemma 3-12B (`gemma3:12b-it-fp16` via Ollama)
- **Entry Point**: `RefactoredIssueEnhancerDeepAgent.Managed_IssueEnhancerDeepAgent_V2_29.runtime.build_issue_enhancer_runtime()`
- **Tools**:
  - `retrieve_enhanced` (continuous learning RAG)
  - `retrieve_similar_fast` (baseline RAG)
  - `enhance_issue` (direct enhancement)
  - `evaluate_quality` (LightGBM)
- **Workflow**: Iterative enhancement with LightGBM quality gate (≥0.5 threshold, max 5 iterations)
- **Dependencies**:
  - Qdrant local storage at `./qdrant_data_v2_29_offline_gemma`
  - RAG collection: `seed_309` (pre-populated with 307 successful enhancements)
  - LightGBM model for quality evaluation

### Target Integration (BenchmarkLLMAgent)
- **Location**: `/home/22pf2/BenchmarkLLMAgent/`
- **Target Agent ID**: `cl_enhanced_gemma3`
- **Category**: Ready-to-use (Category A)
- **Registration Path**: `/home/22pf2/BenchmarkLLMAgent/src/enhancers/ready_to_use/cl_enhanced_gemma3.py`
- **Dispatcher**: `/home/22pf2/BenchmarkLLMAgent/src/enhancers/dispatcher.py`

---

## 2. Key Differences to Bridge

| Aspect | LLMforGithubIssuesRefactor | BenchmarkLLMAgent | Solution |
|--------|---------------------------|-------------------|----------|
| **Input Format** | `IssueEnhancementTask(issue_id, title, body, metadata)` | `dict{title, body, repo_name, issue_number, ...}` | Adapter wrapper |
| **Output Format** | `EnhancementResult` object | `{enhanced_title, enhanced_body, enhancement_metadata}` | Extract fields |
| **Async/Sync** | `asyncio.run(runtime.enhance_issue_async(task))` | Synchronous `enhance_issue(issue, changed_files)` | Wrap async in sync |
| **Working Dir** | `/home/22pf2/LLMforGithubIssuesRefactor` | `/home/22pf2/BenchmarkLLMAgent` | Set PYTHONPATH, cwd |
| **Qdrant Path** | Relative `./qdrant_data_v2_29_offline_gemma` | Needs absolute path | Use absolute path |
| **Conda Env** | `issue_enhancer_py312` | BenchmarkLLMAgent env | Import sys.path |

---

## 3. Implementation Strategy

### Option A: In-Process Integration (Recommended)
Directly import the agent runtime into BenchmarkLLMAgent Python process.

**Pros**:
- Faster (no subprocess overhead)
- Better error handling
- Cleaner code

**Cons**:
- Requires compatible Python environments
- More complex dependency management

### Option B: Subprocess Wrapper
Spawn a separate Python process (like `run_v2_29_gemma3_offline.py` does).

**Pros**:
- Isolated environments
- Easier to debug
- No import conflicts

**Cons**:
- Slower (process spawn + serialization)
- More complex logging

**Decision**: Use **Option A** if both projects use Python 3.12, otherwise **Option B**.

---

## 4. File Structure

```
/home/22pf2/BenchmarkLLMAgent/
├── src/enhancers/ready_to_use/
│   ├── cl_enhanced_gemma3.py          # NEW: Wrapper for CL-Enhanced Agent
│   └── registry.py                     # UPDATE: Add cl_enhanced_gemma3
├── src/enhancers/
│   └── dispatcher.py                   # UPDATE: Register cl_enhanced_gemma3
├── data/samples/groupC_swebenchlive_50/
│   └── groupC_50_samples.json         # EXISTING: 50-issue dataset
├── results/groupC50_baseline_vs_enhanced/
│   └── cl_enhanced_gemma3__native_groupC50_20260403/  # NEW: Results dir
│       ├── enhancements/              # 50 enhancement JSON files
│       ├── enhanced_solver_run/       # Solver trajectories on enhanced issues
│       ├── comparison_summary.json    # Metrics vs baseline
│       └── comparison_summary.md      # Human-readable report
└── scripts/workflows/
    └── run_groupC50_cl_enhanced_vs_baseline.py  # NEW: Orchestrator script
```

---

## 5. Implementation Steps

### Step 1: Create Wrapper (`cl_enhanced_gemma3.py`)

```python
#!/usr/bin/env python3
"""
CL-Enhanced Agent (Gemma 3-12B) wrapper for BenchmarkLLMAgent.

Integrates the V2_29 agent from LLMforGithubIssuesRefactor with continuous learning.
"""

import sys
import asyncio
import logging
from typing import Dict, Any
from pathlib import Path

# Add source project to path
LLMFOR_ISSUES_DIR = Path("/home/22pf2/LLMforGithubIssuesRefactor")
sys.path.insert(0, str(LLMFOR_ISSUES_DIR / "src"))

# Suppress noisy logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("qdrant_client").setLevel(logging.WARNING)

# Import V2_29 runtime (lazy import to avoid slowdown when not used)
_runtime = None

def _get_runtime():
    """Lazy initialization of V2_29 runtime."""
    global _runtime
    if _runtime is None:
        from RefactoredIssueEnhancerDeepAgent.Managed_IssueEnhancerDeepAgent_V2_29.runtime import build_issue_enhancer_runtime
        from RefactoredIssueEnhancerDeepAgent.config import IssueEnhancerDeepAgentConfig

        config = IssueEnhancerDeepAgentConfig()
        config.llm.provider = "ollama"
        config.llm.model_name = "gemma3:12b-it-fp16"
        config.evaluation.fast_probability_threshold = 0.5
        config.planner.model_name = "gemma3:12b-it-fp16"

        _runtime = build_issue_enhancer_runtime(config)

    return _runtime

def enhance_issue(issue: dict, changed_files: str = "") -> Dict[str, Any]:
    """
    Enhance a GitHub issue using the CL-Enhanced Agent with continuous learning.

    Args:
        issue: Dict with keys: title, body, repo_name, issue_number, instance_id, etc.
        changed_files: Comma-separated list of changed files (unused by this agent)

    Returns:
        {
            "enhanced_title": str,
            "enhanced_body": str,
            "enhancement_metadata": dict
        }
    """
    from RefactoredIssueEnhancerDeepAgent.Managed_IssueEnhancerDeepAgent_V2_29.schemas import IssueEnhancementTask

    # Extract inputs
    title = issue.get("title", "")
    body = issue.get("body", "")
    issue_id = issue.get("instance_id") or issue.get("issue_id") or f"{issue.get('repo_name', 'unknown')}__{issue.get('issue_number', 'unknown')}"
    repo_name = issue.get("repo_name", "")
    issue_number = issue.get("issue_number", "")

    # Create task
    task = IssueEnhancementTask(
        issue_id=issue_id,
        title=title,
        body=body,
        metadata={"repo_name": repo_name, "issue_number": issue_number}
    )

    # Get runtime
    runtime = _get_runtime()

    # Run enhancement (wrap async in sync)
    try:
        result = asyncio.run(runtime.enhance_issue_async(task))
    except Exception as e:
        # Fallback on error: return original issue
        return {
            "enhanced_title": title,
            "enhanced_body": body,
            "enhancement_metadata": {
                "error": str(e),
                "success": False,
                "iterations": 0,
                "final_score": 0.0
            }
        }

    # Extract enhanced content
    enhanced_title = result.enhanced_issue.title if result.enhanced_issue else title
    enhanced_body = result.enhanced_issue.body if result.enhanced_issue else body

    # Extract metadata
    final_score = 0.0
    iterations = 0
    if result.artifacts and result.artifacts.evaluation:
        if isinstance(result.artifacts.evaluation, dict):
            final_score = result.artifacts.evaluation.get('final_score', 0.0)
            iterations = result.artifacts.evaluation.get('iterations', 0)

    return {
        "enhanced_title": enhanced_title,
        "enhanced_body": enhanced_body,
        "enhancement_metadata": {
            "agent_id": "cl_enhanced_gemma3",
            "agent_type": "managed_iterative",
            "model": "gemma3:12b-it-fp16",
            "provider": "ollama",
            "success": result.success,
            "iterations": iterations,
            "final_score": final_score,
            "above_threshold": final_score >= 0.5,
            "continuous_learning": True,
            "rag_collection": "seed_309"
        }
    }
```

### Step 2: Register in Dispatcher

Edit `/home/22pf2/BenchmarkLLMAgent/src/enhancers/dispatcher.py`:

```python
# Add import
from src.enhancers.ready_to_use.cl_enhanced_gemma3 import enhance_issue as cl_enhanced_gemma3_enhance

def get_enhancer(agent_id: str):
    """Return enhance_issue(issue, changed_files) callable for the given agent."""
    # ... existing code ...

    if agent_id == "cl_enhanced_gemma3":
        return cl_enhanced_gemma3_enhance

    # ... existing code ...
```

### Step 3: Run Enhancement Benchmark

```bash
cd /home/22pf2/BenchmarkLLMAgent

# Test on 3 issues first
python scripts/enhancers/run_enhancement_benchmark.py \
  --agents cl_enhanced_gemma3 \
  --max-issues 3 \
  --samples data/samples/groupC_swebenchlive_50/groupC_50_samples.json

# Full 50 issues (takes ~2-3 hours)
python scripts/enhancers/run_enhancement_benchmark.py \
  --agents cl_enhanced_gemma3 \
  --max-issues 50 \
  --samples data/samples/groupC_swebenchlive_50/groupC_50_samples.json
```

### Step 4: Create Workflow Orchestrator

Copy and adapt `/home/22pf2/BenchmarkLLMAgent/scripts/workflows/run_secondpaper10_enhancement_vs_baseline.py` → `run_groupC50_cl_enhanced_vs_baseline.py`:

```python
#!/usr/bin/env python3
"""
Group C 50-Issue: CL-Enhanced Agent vs Baseline

Compares CL-Enhanced Agent (Gemma 3-12B with continuous learning) against
baseline on 50 SWE-bench-Live issues.
"""

# ... (copy structure from existing workflow) ...

# Key changes:
ENHANCER_AGENT = "cl_enhanced_gemma3"
DATASET_PATH = "data/samples/groupC_swebenchlive_50/groupC_50_dataset.jsonl"
SAMPLES_PATH = "data/samples/groupC_swebenchlive_50/groupC_50_samples.json"
RESULTS_DIR = "results/groupC50_baseline_vs_enhanced/cl_enhanced_gemma3__native_groupC50_20260403"
```

### Step 5: Run Full Experiment

```bash
cd /home/22pf2/BenchmarkLLMAgent

python scripts/workflows/run_groupC50_cl_enhanced_vs_baseline.py
```

**Expected output**:
- `results/groupC50_baseline_vs_enhanced/cl_enhanced_gemma3__native_groupC50_20260403/`
  - `enhancements/` — 50 enhancement JSON files
  - `baseline_solver_run/` — Baseline solver trajectories (reused from TRAE run)
  - `enhanced_solver_run/` — Solver trajectories on CL-Enhanced issues
  - `comparison_summary.json` — Metrics
  - `comparison_summary.md` — Human-readable report

---

## 6. Expected Results Format

### comparison_summary.json

```json
{
  "enhancer_agent": "cl_enhanced_gemma3",
  "baseline": {
    "resolved_issue_count": 1,
    "resolved_issue_rate": 0.02,
    "fail_to_pass_issue_success_count": 7,
    "fail_to_pass_issue_success_rate": 0.14
  },
  "enhanced": {
    "resolved_issue_count": ???,
    "resolved_issue_rate": ???,
    "fail_to_pass_issue_success_count": ???,
    "fail_to_pass_issue_success_rate": ???
  },
  "delta": {
    "resolved_rate": "???%",
    "fail_to_pass_rate": "???%"
  }
}
```

### comparison_summary.md

```markdown
# Baseline vs Enhanced Comparison (CL-Enhanced Agent)

## Delta

| Metric | Baseline | Enhanced | Delta |
|--------|:--------:|:--------:|:-----:|
| Resolved | 1/50 (2.0%) | ???/50 (???%) | ???% |
| F2P success | 7/50 (14.0%) | ???/50 (???%) | ???% |
| P2P success | 2/50 (4.0%) | ???/50 (???%) | ???% |
```

---

## 7. Dependencies Check

### Python Environment
- Both projects should use Python 3.12
- Required packages in BenchmarkLLMAgent env:
  - `sentence-transformers` (for embeddings)
  - `qdrant-client` (for vector DB)
  - `lightgbm` (for evaluator)
  - `langchain` (for agent framework)

### Qdrant Data
- **Source**: `/home/22pf2/LLMforGithubIssuesRefactor/qdrant_data_v2_29_offline_gemma/`
- **Collection**: `seed_309` (307 pre-seeded successful enhancements)
- **Action**: Either:
  1. Copy to BenchmarkLLMAgent project, OR
  2. Use absolute path in wrapper

### LightGBM Model
- **Source**: `/home/22pf2/LLMforGithubIssuesRefactor/data/copy_data/lightgbm_nov25_model.pkl` (or similar)
- **Action**: Ensure path is accessible from wrapper

### Ollama Server
- **Model**: `gemma3:12b-it-fp16`
- **Check**: `ollama list | grep gemma3`
- **Start if needed**: `ollama serve`

---

## 8. Testing Plan

### Phase 1: Unit Test (1 issue)
```bash
cd /home/22pf2/BenchmarkLLMAgent
python -c "
from src.enhancers.dispatcher import get_enhancer
import json

# Load one issue
with open('data/samples/groupC_swebenchlive_50/groupC_50_samples.json') as f:
    issues = json.load(f)

issue = issues[0]
enhance_fn = get_enhancer('cl_enhanced_gemma3')
result = enhance_fn(issue, '')

print('Enhanced Title:', result['enhanced_title'])
print('Enhanced Body:', result['enhanced_body'][:200])
print('Metadata:', result['enhancement_metadata'])
"
```

### Phase 2: Small Batch (3 issues)
```bash
python scripts/enhancers/run_enhancement_benchmark.py \
  --agents cl_enhanced_gemma3 \
  --max-issues 3 \
  --samples data/samples/groupC_swebenchlive_50/groupC_50_samples.json
```

### Phase 3: Full Run (50 issues)
```bash
python scripts/enhancers/run_enhancement_benchmark.py \
  --agents cl_enhanced_gemma3 \
  --max-issues 50 \
  --samples data/samples/groupC_swebenchlive_50/groupC_50_samples.json
```

### Phase 4: Full Workflow (Solver + Eval)
```bash
python scripts/workflows/run_groupC50_cl_enhanced_vs_baseline.py
```

---

## 9. Comparison Against Existing Enhancers

After completion, you'll have 4 enhancers on 50 issues:

| Agent | Body Similarity (expected) | Resolved Delta (expected) | Notes |
|-------|:---:|:---:|-------|
| **TRAE** | ~1.000 | 0.0% | Near-identical (conservative) |
| **SWE-agent** | ~0.204 | -2.0% | Moderate rewriting (harmful) |
| **Aider** | ~0.037 | -2.0% | Aggressive rewriting (very harmful) |
| **CL-Enhanced (Gemma3)** | ??? | ??? | **Managed iterative + RAG + LightGBM quality gate** |

**Hypothesis**: CL-Enhanced should outperform all 3 existing enhancers because:
1. **Iterative refinement** (up to 5 iterations with quality feedback)
2. **RAG grounding** (retrieves similar resolved issues)
3. **Objective quality gate** (LightGBM ≥0.5 threshold)
4. **Continuous learning** (seed_309 collection with 307 successful enhancements)

**Counter-hypothesis**: May still harm if:
- SWE-bench-Live issues are already well-written (as TRAE results suggest)
- Iterative enhancement compounds errors rather than correcting them
- LightGBM quality gate is tuned for different issue distribution

---

## 10. Timeline Estimate

| Phase | Duration | Notes |
|-------|:--------:|-------|
| Setup + Unit Test | 30 min | Create wrapper, test 1 issue |
| Small Batch (3 issues) | 15 min | Verify enhancement quality |
| Full Enhancement (50 issues) | 2-3 hours | Parallel workers, ~3-5 min/issue |
| Solver Baseline Run | 0 min | Reuse from TRAE experiment |
| Solver Enhanced Run | 3-5 hours | Same as TRAE/SWE-agent/Aider |
| Evaluation | 30 min | Generate comparison_summary |
| **Total** | **6-9 hours** | End-to-end |

---

## 11. Troubleshooting

### Import Errors
- **Symptom**: `ModuleNotFoundError: No module named 'RefactoredIssueEnhancerDeepAgent'`
- **Fix**: Verify `sys.path.insert(0, "/home/22pf2/LLMforGithubIssuesRefactor/src")`

### Qdrant Errors
- **Symptom**: `Collection 'seed_309' not found`
- **Fix**: Copy Qdrant data or use absolute path:
  ```bash
  cp -r /home/22pf2/LLMforGithubIssuesRefactor/qdrant_data_v2_29_offline_gemma \
        /home/22pf2/BenchmarkLLMAgent/qdrant_data_cl_enhanced
  ```

### Ollama Errors
- **Symptom**: `Connection refused on http://localhost:11434`
- **Fix**: `ollama serve` in background, verify `ollama list | grep gemma3`

### Slow Performance
- **Symptom**: >10 min per issue
- **Fix**: Reduce `MAX_WORKERS` to 1-2 to avoid Ollama saturation

---

## 12. Next Steps

1. ✅ Read this integration plan
2. ⏳ Create `cl_enhanced_gemma3.py` wrapper
3. ⏳ Register in dispatcher
4. ⏳ Run unit test (1 issue)
5. ⏳ Run small batch (3 issues)
6. ⏳ Run full enhancement (50 issues)
7. ⏳ Run full workflow (solver + eval)
8. ⏳ Compare results against TRAE/SWE-agent/Aider
9. ⏳ Update experiment report

---

**Status**: Integration plan ready. Ready to proceed with implementation?
