import json
import re

NON_TEST_EXTS = [".json", ".txt", ".md", ".csv", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh"]

def get_test_directives(instance) -> list:
    if instance["repo"] == "swe-bench/humaneval":
        return ["test.py"]
        
    diff_pat = r"diff --git a/.* b/(.*)"
    test_patch = instance["test_patch"]
    directives = re.findall(diff_pat, test_patch)
    directives = [
        d for d in directives if not any(d.endswith(ext) for ext in NON_TEST_EXTS)
    ]
    if instance["repo"] == "django/django":
        directives_transformed = []
        for d in directives:
            d = d[: -len(".py")] if d.endswith(".py") else d
            d = d[len("tests/") :] if d.startswith("tests/") else d
            d = d.replace("/", ".")
            directives_transformed.append(d)
        directives = directives_transformed
    return directives

file_path = "/home/22pf2/BenchmarkLLMAgent/data/samples/swe_bench_live_10_samples.json"
backup_path = "/home/22pf2/BenchmarkLLMAgent/data/samples/swe_bench_live_10_samples.json.bak"

with open(file_path) as f:
    d = json.load(f)

# backup
with open(backup_path, "w") as f:
    json.dump(d, f, indent=4)

for k, task in d["issues"].items():
    directives = get_test_directives(task)
    
    new_p2p = []
    
    # ensure it's loaded properly
    if isinstance(task["PASS_TO_PASS"], str):
        p2p_list = json.loads(task["PASS_TO_PASS"])
    else:
        p2p_list = task["PASS_TO_PASS"]
        
    for test in p2p_list:
        keep = False
        for directive in directives:
            if directive in test:
                keep = True
                break
                
        if keep:
            new_p2p.append(test)
            
    print(f"{task['instance_id']}: P2P {len(p2p_list)} -> {len(new_p2p)}")
    
    # Store it back in the original format (if it was a string, store as string)
    if isinstance(task["PASS_TO_PASS"], str):
        task["PASS_TO_PASS"] = json.dumps(new_p2p)
    else:
        task["PASS_TO_PASS"] = new_p2p
    
with open(file_path, "w") as f:
    json.dump(d, f, indent=4)
