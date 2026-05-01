import json
from datasets import load_dataset
from datetime import datetime

def default_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

print("Loading dataset...")
ds = load_dataset("SWE-bench-Live/SWE-bench-Live", split="test")

target_id = "conan-io__conan-15377"
for row in ds:
    if row["instance_id"] == target_id:
        print(f"Found {target_id}")
        with open(f"{target_id}.json", "w") as f:
            json.dump(row, f, indent=2, default=default_serializer)
        break
else:
    print(f"Not found: {target_id}")
