#!/usr/bin/env python3
"""
Post-processing fix: derive test_commands from PASS_TO_PASS + FAIL_TO_PASS
for any Paul result.json that has empty test_commands.

Run after Stage 2 completes (or at any time — safe to re-run).
"""
import glob, json, shlex
from pathlib import Path

STAGE1   = Path("/home/22pf2/BenchmarkLLMAgent/data/samples/pouya_dataset_2026_stage1/dataset.jsonl")
WORKSPACES = [
    "/home/22pf2/paul-RepoLaunch/workspace/stage2_2026_full",
    "/home/22pf2/paul-RepoLaunch/workspace/p2p_pipeline_enhanced",
    "/home/22pf2/paul-RepoLaunch/workspace/p2p_pipeline_stage2_20260515",
]

def make_test_cmd(f2p, p2p):
    targets = [t for t in (f2p or []) + (p2p or []) if t]
    if not targets:
        return None
    return "pytest -v -rA " + " ".join(shlex.quote(t) for t in targets)

# Load stage1 lookup by instance_id
stage1_lookup = {}
if STAGE1.exists():
    for line in open(STAGE1):
        r = json.loads(line)
        stage1_lookup[r["instance_id"]] = r

fixed = skipped = already_ok = missing = 0
for ws in WORKSPACES:
    for rf in glob.glob(f"{ws}/playground/*/result.json"):
        r = json.load(open(rf))
        if not (r.get("docker_image") and r.get("setup_commands")):
            skipped += 1
            continue
        if r.get("test_commands"):
            already_ok += 1
            continue
        iid = r["instance_id"]
        s1 = stage1_lookup.get(iid)
        if not s1:
            missing += 1
            continue
        cmd = make_test_cmd(s1.get("FAIL_TO_PASS"), s1.get("PASS_TO_PASS"))
        if not cmd:
            missing += 1
            continue
        r["test_commands"] = [cmd]
        r["_test_commands_source"] = "derived_from_f2p_p2p"
        with open(rf, "w") as f:
            json.dump(r, f, indent=2)
        fixed += 1

print(f"Fixed (filled test_commands):  {fixed}")
print(f"Already had test_commands:     {already_ok}")
print(f"Skipped (not successful):      {skipped}")
print(f"Missing stage1 data:           {missing}")
