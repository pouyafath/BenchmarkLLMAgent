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
        print(f"{name}: no dataset")
        continue
    
    types = {}
    with open(ds_file) as f:
        for line in f:
            row = json.loads(line)
            meta = row.get("enhancement_metadata", {})
            etype = meta.get("enhancer_type", meta.get("agent_label", "none"))
            error = meta.get("error", "")
            key = f"{etype}" + (f" ({error[:60]})" if error else "")
            types[key] = types.get(key, 0) + 1
    print(f"{name}: {types}")
