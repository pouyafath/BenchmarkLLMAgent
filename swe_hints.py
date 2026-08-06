import json

with open("runs/pouya_enhanced_swe_agent_20260505_084500/solver_enhanced_dataset.jsonl") as f:
    for line in f:
        row = json.loads(line)
        enh_text = row.get("hints_text", "")
        print(f"{row['instance_id']}: len={len(enh_text)}")
