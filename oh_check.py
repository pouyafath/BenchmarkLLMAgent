import json
with open("runs/pouya_enhanced_openhands_20260505_084500/summary.json") as f:
    r = json.load(f)
    print("Baseline resolved:", r.get("baseline_resolved_ids", []))
    print("Enhanced resolved:", r.get("enhanced_resolved_ids", []))
