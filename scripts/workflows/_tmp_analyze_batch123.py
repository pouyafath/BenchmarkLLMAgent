#!/usr/bin/env python3
"""Temporary script: analyze new batch123 Stage 3 export vs old pilot40."""
import json
from pathlib import Path
from collections import Counter

NEW = Path("/home/22pf2/paul-RepoLaunch/runs/stage2_2026_node1_batch123_stage3_exports_20260602_1230_utc/stage3_validation_completed122.jsonl")
OLD = Path("/home/22pf2/paul-RepoLaunch/runs/stage2_2026_full_pilot48_stage_exports_20260526_1552_utc/stage3_validation_completed40.jsonl")

def load(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]

new_rows = load(NEW)
old_rows = load(OLD)

print(f"New export: {len(new_rows)} rows")
print(f"Old export: {len(old_rows)} rows")

# P2P observed > 0 subset
p2p_obs = [r for r in new_rows if r.get("stage3_pass_to_pass_observed_count", 0) > 0]
p2p_zero = [r for r in new_rows if r.get("stage3_pass_to_pass_observed_count", 0) == 0]
print(f"\nP2P observed > 0: {len(p2p_obs)}")
print(f"P2P observed == 0: {len(p2p_zero)}")

# Issue type for P2P>0 subset
types = Counter(r.get("issue_type", "unknown") for r in p2p_obs)
print(f"P2P>0 issue types: {dict(types)}")

# Old IDs
old_ids = {r["instance_id"] for r in old_rows}

# Overlap + net-new within P2P>0 subset
p2p_ids = {r["instance_id"] for r in p2p_obs}
overlap = p2p_ids & old_ids
net_new = p2p_ids - old_ids

print(f"\nOverlap (P2P>0 ∩ old40): {len(overlap)}")
print(f"Net-new (P2P>0 - old40): {len(net_new)}")

# Net-new issue type breakdown
net_new_rows = [r for r in p2p_obs if r["instance_id"] in net_new]
net_new_types = Counter(r.get("issue_type", "unknown") for r in net_new_rows)
print(f"Net-new issue types: {dict(net_new_types)}")

# Key fields check for P2P>0 subset
has_repo = sum(1 for r in p2p_obs if r.get("repo"))
has_ps = sum(1 for r in p2p_obs if r.get("problem_statement"))
has_docker = sum(1 for r in p2p_obs if r.get("docker_image"))
print(f"\nP2P>0 key fields: repo={has_repo}/{len(p2p_obs)}, problem_statement={has_ps}/{len(p2p_obs)}, docker_image={has_docker}/{len(p2p_obs)}")

# List overlap IDs
print(f"\n=== OVERLAP IDs ({len(overlap)}) ===")
for iid in sorted(overlap):
    t = next((r.get("issue_type", "?") for r in p2p_obs if r["instance_id"] == iid), "?")
    print(f"  {iid} ({t})")

# List net-new IDs
print(f"\n=== NET-NEW IDs ({len(net_new)}) ===")
for iid in sorted(net_new):
    t = next((r.get("issue_type", "?") for r in p2p_obs if r["instance_id"] == iid), "?")
    obs = next((r.get("stage3_pass_to_pass_observed_count", 0) for r in p2p_obs if r["instance_id"] == iid), 0)
    print(f"  {iid} ({t}, p2p_observed={obs})")

# Also: which old40 IDs are NOT in the new P2P>0 set?
missing_from_new = old_ids - p2p_ids
print(f"\n=== OLD40 IDs NOT in new P2P>0 ({len(missing_from_new)}) ===")
for iid in sorted(missing_from_new):
    t = next((r.get("issue_type", "?") for r in old_rows if r["instance_id"] == iid), "?")
    # Check if it's in the full 122 at all
    in_122 = iid in {r["instance_id"] for r in new_rows}
    if in_122:
        obs = next((r.get("stage3_pass_to_pass_observed_count", 0) for r in new_rows if r["instance_id"] == iid), "?")
        print(f"  {iid} ({t}) — in 122 but p2p_observed={obs}")
    else:
        print(f"  {iid} ({t}) — NOT in 122 at all")
