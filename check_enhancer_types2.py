import json
from pathlib import Path

enhancers = {
    "aider": "runs/pouya_enhanced_aider_20260505_084500",
    "trae": "runs/pouya_enhanced_trae_20260505_084500",
    "openhands": "runs/pouya_enhanced_openhands_20260505_084500",
    "mini_swe_agent": "runs/pouya_enhanced_mini_swe_agent_20260505_084500",
    "swe_agent": "runs/pouya_enhanced_swe_agent_20260505_084500",
}

for name, path in enhancers.items():
    ds_file = Path(path) / "solver_enhanced_dataset.jsonl"
    if not ds_file.exists():
        print(f"{name}: dataset file not found")
        continue
    
    with open(ds_file) as f:
        first = json.loads(f.readline())
        # Check all keys that might indicate enhancer type
        for k in sorted(first.keys()):
            if "enhancer" in k.lower() or "type" in k.lower() or "source" in k.lower():
                print(f"  {name}: {k} = {first[k]}")
        # Also check hints_text source
        hints = first.get("hints_text", "")
        print(f"  {name}: first instance={first['instance_id']}, hints_len={len(hints)}")
        print(f"  {name}: first 200 chars of hints: {repr(hints[:200])}")
        print()
