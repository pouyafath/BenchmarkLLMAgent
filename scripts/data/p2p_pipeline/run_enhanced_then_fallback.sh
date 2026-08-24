#!/bin/bash
# Enhanced pipeline: runs gpt-oss:120b with memory pool + error feedback,
# then falls back to GPT-5.4-mini for LLM-capacity failures.
set -euo pipefail

PAUL_DIR="/home/22pf2/paul-RepoLaunch"
PAUL_PYTHON="/home/22pf2/anaconda3/envs/paul-repolaunch/bin/python"
ENHANCED_WORKSPACE="$PAUL_DIR/workspace/p2p_pipeline_enhanced"
ENHANCED_LOG="$ENHANCED_WORKSPACE/p2p_pipeline_enhanced_run.log"
FALLBACK_WORKSPACE="$PAUL_DIR/workspace/p2p_pipeline_fallback_gpt54mini"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OPENAI_KEY="${OPENAI_API_KEY:-$(cat "$REPO_ROOT/.secrets/openai_api_key.txt")}"

echo "[$(date)] Waiting for enhanced Paul run (gpt-oss:120b) to complete..."

# Wait for enhanced run to finish
while pgrep -f "p2p_pipeline_enhanced.json" > /dev/null 2>&1; do
    DONE=$(find "$ENHANCED_WORKSPACE/playground" -name "result.json" 2>/dev/null | wc -l)
    SUCCESS=$(find "$ENHANCED_WORKSPACE/playground" -name "result.json" -exec grep -l '"docker_image": "pouya' {} + 2>/dev/null | wc -l || true)
    echo "[$(date)] Enhanced run: $DONE/335 done, $SUCCESS succeeded"
    sleep 120
done

echo "[$(date)] Enhanced run finished. Analyzing failures..."

# Analyze failures and build fallback dataset
python3 << 'PYEOF'
import json, glob, os
from collections import Counter

enhanced_base = "/home/22pf2/paul-RepoLaunch/workspace/p2p_pipeline_enhanced/playground"

# Load the retry dataset to know which instances were supposed to be processed
retry_ids = set()
with open("/home/22pf2/paul-RepoLaunch/data/p2p_pipeline_enhanced_retry.jsonl") as f:
    for line in f:
        retry_ids.add(json.loads(line)["instance_id"])

# Categorize results (only for instances in the retry dataset)
llm_capacity_failures = []
infra_failures = []
succeeded = []
not_attempted = []

attempted_ids = set()
for rpath in glob.glob(f"{enhanced_base}/*/result.json"):
    with open(rpath) as f:
        d = json.load(f)
    iid = d["instance_id"]
    if iid not in retry_ids:
        continue  # skip seeded results from prior runs

    attempted_ids.add(iid)
    if d.get("docker_image"):
        succeeded.append(iid)
        continue

    exc = d.get("exception", "") or ""

    # LLM capacity: the LLM couldn't follow the action format or produced empty/malformed output
    # Be specific to avoid false positives (e.g. "action" appearing in Docker error messages)
    is_llm_issue = False
    if "'NoneType' object has no attribute 'action'" in exc:
        is_llm_issue = True
    elif "JSONDecodeError" in exc:
        is_llm_issue = True
    elif "empty" in exc.lower() and "response" in exc.lower():
        is_llm_issue = True

    if is_llm_issue:
        llm_capacity_failures.append(iid)
    else:
        infra_failures.append(iid)

# Instances that Paul never even attempted (not in workspace)
for iid in retry_ids:
    if iid not in attempted_ids:
        not_attempted.append(iid)

print(f"Results from enhanced run (out of {len(retry_ids)} in dataset):")
print(f"  Succeeded:       {len(succeeded)}")
print(f"  LLM-capacity:    {len(llm_capacity_failures)}")
print(f"  Infra failures:  {len(infra_failures)}")
print(f"  Not attempted:   {len(not_attempted)}")

# Build fallback dataset: LLM-capacity failures + not-attempted instances
# (If Paul didn't attempt them, it may have crashed or timed out — worth retrying with GPT-5.4-mini)
fallback_ids = llm_capacity_failures + not_attempted
stage1 = "/home/22pf2/BenchmarkLLMAgent/data/samples/pouya_p2p_pipeline/stage1_approach1/dataset.jsonl"
stage1_map = {}
with open(stage1) as f:
    for line in f:
        row = json.loads(line)
        stage1_map[row["instance_id"]] = row

fallback_path = "/home/22pf2/paul-RepoLaunch/data/p2p_pipeline_fallback_gpt54mini.jsonl"
with open(fallback_path, "w") as out:
    for iid in fallback_ids:
        if iid in stage1_map:
            out.write(json.dumps(stage1_map[iid]) + "\n")

if fallback_ids:
    print(f"\nWrote {len(fallback_ids)} instances to fallback dataset ({len(llm_capacity_failures)} LLM-capacity + {len(not_attempted)} not-attempted)")
else:
    print("\nNo fallback needed — all instances either succeeded or had infra failures")

# Report infra failures for documentation
if infra_failures:
    print(f"\nInfra failures ({len(infra_failures)} instances — not retryable with better LLM):")
    for iid in sorted(infra_failures):
        print(f"  - {iid}")

# Write analysis summary
import datetime
summary = {
    "timestamp": str(datetime.datetime.now()),
    "total_in_dataset": len(retry_ids),
    "succeeded": len(succeeded),
    "llm_capacity_failures": len(llm_capacity_failures),
    "infra_failures": len(infra_failures),
    "not_attempted": len(not_attempted),
    "fallback_target": len(fallback_ids),
    "succeeded_ids": sorted(succeeded),
    "infra_failure_ids": sorted(infra_failures),
    "llm_capacity_ids": sorted(llm_capacity_failures),
    "not_attempted_ids": sorted(not_attempted),
}
with open("/home/22pf2/paul-RepoLaunch/workspace/p2p_pipeline_enhanced/analysis_after_enhanced.json", "w") as f:
    json.dump(summary, f, indent=2)
print(f"\nAnalysis saved to workspace/p2p_pipeline_enhanced/analysis_after_enhanced.json")
PYEOF

# Check if fallback dataset has any instances
FALLBACK_COUNT=$(wc -l < "$PAUL_DIR/data/p2p_pipeline_fallback_gpt54mini.jsonl")
if [ "$FALLBACK_COUNT" -gt 0 ]; then
    echo "[$(date)] Launching GPT-5.4-mini fallback for $FALLBACK_COUNT LLM-capacity failures..."

    mkdir -p "$FALLBACK_WORKSPACE/playground"

    # Copy successful results from enhanced workspace for memory pool
    python3 -c "
import json, glob, os, shutil
src = '$ENHANCED_WORKSPACE/playground'
dst = '$FALLBACK_WORKSPACE/playground'
copied = 0
for rpath in glob.glob(f'{src}/*/result.json'):
    d = json.load(open(rpath))
    if d.get('docker_image'):
        iid = d['instance_id']
        dest_dir = os.path.join(dst, iid)
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(rpath, os.path.join(dest_dir, 'result.json'))
        copied += 1
print(f'Seeded {copied} successful results into fallback workspace')
"

    # Run fallback with GPT-5.4-mini
    cd "$PAUL_DIR"
    OPENAI_API_KEY="$OPENAI_KEY" "$PAUL_PYTHON" -m paul.run configs/p2p_pipeline_fallback_gpt54mini.json

    echo "[$(date)] GPT-5.4-mini fallback complete."
else
    echo "[$(date)] No LLM-capacity failures — no fallback needed."
fi

echo "[$(date)] Full pipeline complete. Collecting final results..."

# Final summary
python3 << 'PYEOF2'
import json, glob

total_success = set()
for base in [
    "/home/22pf2/paul-RepoLaunch/workspace/p2p_pipeline_stage2_20260515/playground",
    "/home/22pf2/paul-RepoLaunch/workspace/p2p_pipeline_retry_gpt54mini/playground",
    "/home/22pf2/paul-RepoLaunch/workspace/p2p_pipeline_enhanced/playground",
    "/home/22pf2/paul-RepoLaunch/workspace/p2p_pipeline_fallback_gpt54mini/playground",
]:
    for rpath in glob.glob(f"{base}/*/result.json"):
        d = json.load(open(rpath))
        if d.get("docker_image"):
            total_success.add(d["instance_id"])

print(f"\n{'='*60}")
print(f"FINAL RESULT: {len(total_success)}/387 instances with Docker images")
print(f"{'='*60}")
PYEOF2
