import os
import re
import json
import time
import subprocess
import urllib.request
from urllib.error import HTTPError

REPO_URL = "https://github.com/pydantic/pydantic-ai.git"
REPO_NAME = "pydantic/pydantic-ai"
CLONE_DIR = "pydantic-ai"
OUTPUT_FILE = "pydantic_ai_swe_bench_50.json"
TARGET_COUNT = 50

def run_cmd(cmd, cwd=CLONE_DIR):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)
    return result.stdout.strip()

def fetch_pr_body(pr_number):
    url = f"https://api.github.com/repos/{REPO_NAME}/pulls/{pr_number}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            return data.get("body") or data.get("title") or ""
    except HTTPError as e:
        print(f"Failed to fetch PR {pr_number}: {e}")
        return ""

def main():
    if not os.path.exists(CLONE_DIR):
        print("Cloning repository...")
        subprocess.run(["git", "clone", REPO_URL, CLONE_DIR])

    print("Fetching git history...")
    log_output = run_cmd(["git", "log", "--pretty=format:%H %s", "-n", "1000"])
    
    tasks = []
    
    # regex for pull request squashes: e.g. "feat: add something (#123)"
    pr_format = re.compile(r"^(.*?)\s+\(#(\d+)\)$")
    
    for line in log_output.split("\n"):
        parts = line.split(" ", 1)
        if len(parts) != 2: continue
        commit_hash, message = parts
        
        m = pr_format.search(message)
        if not m:
            continue
            
        pr_number = m.group(2)
        
        # Base commit is parent 1
        base_commit = run_cmd(["git", "rev-parse", f"{commit_hash}^1"])
        
        # Test if it touches python files and tests
        changed_files = run_cmd(["git", "diff", "--name-only", base_commit, commit_hash]).split("\n")
        
        has_tests = any("tests/" in f or f.startswith("tests") for f in changed_files)
        has_src = any((f.endswith(".py") and "tests/" not in f) for f in changed_files)
        
        if not (has_tests and has_src):
            continue
            
        print(f"Found candidate PR {pr_number} (commit {commit_hash})")
        
        patch = run_cmd(["git", "diff", base_commit, commit_hash, "--", ".", ":!tests", ":!docs"])
        test_patch = run_cmd(["git", "diff", base_commit, commit_hash, "--", "tests"])
        
        if not patch.strip() or not test_patch.strip():
            continue
            
        print(f"Fetching PR body for {pr_number} (currently have {len(tasks)})...")
        time.sleep(1.0) # avoid rate limit
        
        problem_statement = fetch_pr_body(pr_number)
        
        # F2P and P2P approximation:
        # Just use the files changed in tests as P2P, SWE-bench evaluators often extract tests from these.
        test_files = [f for f in changed_files if f.startswith("tests/") and f.endswith(".py")]
        
        task = {
            "instance_id": f"pydantic__pydantic-ai-{pr_number}",
            "repo": REPO_NAME,
            "base_commit": base_commit,
            "patch": patch,
            "test_patch": test_patch,
            "problem_statement": problem_statement,
            "hints_text": "",
            "created_at": run_cmd(["git", "show", "-s", "--format=%cI", commit_hash]),
            "version": "1.0",
            "FAIL_TO_PASS": json.dumps(test_files),
            "PASS_TO_PASS": json.dumps(test_files),
            "environment_setup_commit": "Instructions: Run `pip install -e .[all]` to set up pydantic-ai, then `pytest <test_file>` to run tests."
        }
        
        tasks.append(task)
        
        if len(tasks) >= TARGET_COUNT:
            break

    print(f"Collected {len(tasks)} tasks.")
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(tasks, f, indent=4)
        
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
