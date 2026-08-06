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
    
    types = {"real": 0, "proxy": 0, "error": 0, "other": 0}
    with open(ds_file) as f:
        for line in f:
            row = json.loads(line)
            etype = row.get("enhancer_type", "unknown")
            if etype in types:
                types[etype] += 1
            else:
                types["other"] += 1
    print(f"{name}: {dict(types)}")
