import argparse
import json
import os
import subprocess
import tempfile
import time
import re
from pathlib import Path

def parse_pytest_output(output):
    """Parses pytest output to extract passed/failed tests."""
    passed = []
    failed = []
    skipped = []
    
    # Match pytest short test summary info
    # e.g., FAILED conans/test/functional/tools/scm/test_git.py::TestGitBasicSCMFlow::test_full_scm[True] - assert False
    # e.g., PASSED conans/test/functional/tools/scm/test_git.py::test_branch_flow[True]
    
    for line in output.splitlines():
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            parts = line.split(" ", 2)
            if len(parts) >= 2:
                failed.append(parts[1])
        elif line.startswith("PASSED "):
            parts = line.split(" ", 2)
            if len(parts) >= 2:
                passed.append(parts[1])
        elif line.startswith("SKIPPED ") or line.startswith("XFAIL "):
            parts = line.split(" ", 2)
            if len(parts) >= 2:
                skipped.append(parts[1])
                
    return list(set(passed)), list(set(failed)), list(set(skipped))


def run_docker_evaluation(instance_id, repo, base_commit, test_cmds, patch_path=None, test_patch=None):
    """
    Builds and runs a minimal Docker container to execute the tests.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        
        # 1. Provide the main solver patch if requested
        if patch_path:
            patch_content = Path(patch_path).read_text()
            with open(temp_dir_path / "solver_patch.diff", "w") as f:
                f.write(patch_content)
        
        # 2. Provide the dataset test_patch if requested
        if test_patch:
            with open(temp_dir_path / "test_patch.diff", "w") as f:
                f.write(test_patch)

        # 3. Create a bash script that runs inside the container
        run_script = f"""#!/bin/bash
set -e
git clone https://github.com/{repo} /workspace
cd /workspace
git checkout {base_commit}

# Apply dataset test patch if it exists
if [ -f /mnt/test_patch.diff ]; then
    git apply /mnt/test_patch.diff || true
fi

# Apply solver patch if it exists
if [ -f /mnt/solver_patch.diff ]; then
    git apply /mnt/solver_patch.diff || echo "PATCH_APPLY_FAILED"
fi

# Setup Environment
echo "Installing base requirements..."
timeout 180 pip install -e ".[test]" || timeout 180 pip install -e . || timeout 180 pip install -r requirements.txt || true

echo "Installing pytest capabilities..."
pip install pytest pytest-cov mock parameterized webtest pyjwt pytest-timeout

# Run tests
echo "=== RUNNING TESTS ==="
"""
        for cmd in test_cmds:
            # If it is a pytest command, inject --timeout to prevent hanging
            if cmd.strip().startswith("pytest "):
                cmd = cmd.replace("pytest ", "pytest --timeout=60 ")
            run_script += f"{cmd}\n"
            
        with open(temp_dir_path / "run.sh", "w") as f:
            f.write(run_script)
            
        # 4. Construct Dockerfile
        dockerfile = """FROM python:3.11-slim
RUN apt-get update && apt-get install -y git build-essential
WORKDIR /workspace
"""
        with open(temp_dir_path / "Dockerfile", "w") as f:
            f.write(dockerfile)
            
        # 5. Build Image
        image_name = f"swe_eval_{instance_id.lower()}"
        print(f"Building Docker image {image_name}...")
        subprocess.run(["docker", "build", "-t", image_name, temp_dir], check=True, capture_output=True)
        
        # 6. Run Container
        print(f"Running evaluation inside {image_name}...")
        start_time = time.time()
        
        # Mount the temp directory into /mnt inside the container so the scripts/patches are available
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{temp_dir_path}:/mnt",
            image_name,
            "bash", "/mnt/run.sh"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = time.time() - start_time
        
        output = result.stdout + "\n" + result.stderr
        
        patch_applied = True
        if "PATCH_APPLY_FAILED" in output:
            patch_applied = False
            
        return {
            "exit_code": result.returncode,
            "output": output,
            "duration": duration,
            "patch_applied": patch_applied
        }

def evaluate_instance(args):
    # Load Instance JSON
    with open(args.dataset_json) as f:
        instance_data = json.load(f)
        if isinstance(instance_data, list):
            # Try to find the specific instance if it's a list
            instance = next((x for x in instance_data if x["instance_id"] == args.instance_id), None)
        else:
            instance = instance_data
            
    if not instance:
        print(f"Error: Could not find instance {args.instance_id} inside {args.dataset_json}")
        return
        
    repo = instance["repo"]
    base_commit = instance["base_commit"]
    test_patch = instance.get("test_patch", "")
    fail_to_pass_expected = instance.get("FAIL_TO_PASS", [])
    pass_to_pass_expected = instance.get("PASS_TO_PASS", [])

    # Optimization: Instead of blindly running test_cmds which might hang or take 10 minutes on full suite,
    # just test the actual files we care about tracking.
    test_files_to_run = set()
    for t in fail_to_pass_expected + pass_to_pass_expected:
        file_path = t.split("::")[0]
        test_files_to_run.add(file_path)

    test_cmds = [f"pytest -rA {' '.join(test_files_to_run)}"]
    
    out_dir = Path(args.out_dir) / args.instance_id
    out_dir.mkdir(parents=True, exist_ok=True)
    
    def run_mode(mode_name, patch_path=None):
        print(f"\\n--- Running {mode_name.upper()} ---")
        mode_dir = out_dir / mode_name
        mode_dir.mkdir(exist_ok=True)
        
        result = run_docker_evaluation(
            instance["instance_id"],
            repo,
            base_commit,
            test_cmds,
            patch_path=patch_path,
            test_patch=test_patch
        )
        
        with open(mode_dir / "docker.log", "w") as f:
            f.write(result["output"])
            
        passed, failed, skipped = parse_pytest_output(result["output"])
        
        total_collected = len(passed) + len(failed) + len(skipped)
        
        # Determine actual metrics based on Pytest parsing
        obs_fail_to_pass = [t for t in passed if any(expected in t for expected in fail_to_pass_expected)]
        obs_pass_to_pass_reg = [t for t in failed if any(expected in t for expected in pass_to_pass_expected)]
        
        # Look for a fatal error in stderr
        error_sig = ""
        lines = result["output"].splitlines()
        for i, line in enumerate(lines):
            if "Error:" in line or "Exception:" in line or "Traceback" in line:
                error_sig = line.strip()
                break
                
        summary = {
            "instance_id": args.instance_id,
            "mode": mode_name,
            "repo": repo,
            "base_commit": base_commit,
            "patch_applies": result["patch_applied"],
            "ran": total_collected > 0,
            "exit_code": result["exit_code"],
            "duration_s": result["duration"],
            "tests": {
                "total_collected": total_collected,
                "total_passed": len(passed),
                "total_failed": len(failed),
                "total_skipped": len(skipped),
                "pass_rate": len(passed) / max(total_collected, 1),
                "fail_to_pass_expected": fail_to_pass_expected,
                "pass_to_pass_expected": pass_to_pass_expected,
                "fail_to_pass_observed": obs_fail_to_pass,
                "pass_to_pass_regressions": obs_pass_to_pass_reg,
                "passed_list": passed,
                "failed_list": failed
            },
            "error_signature": error_sig
        }
        
        with open(mode_dir / "summary.json", "w") as f:
            json.dump(summary, f, indent=2)
            
        return summary

    # RUN BASELINE
    baseline_summary = run_mode("baseline")
    
    # RUN PATCHED
    patched_summary = run_mode("patched", patch_path=args.patch_file)
    
    # COMPARE
    print("\n--- GENERATING COMPARISON ---")
    
    # A true regression is a test that was passing in baseline but failed in patched
    true_regressions = []
    baseline_passed = set(baseline_summary["tests"]["passed_list"])
    patched_failed = set(patched_summary["tests"]["failed_list"])
    for t in pass_to_pass_expected:
        passed_in_base = any(t in bp for bp in baseline_passed)
        failed_in_patch = any(t in pf for pf in patched_failed)
        if passed_in_base and failed_in_patch:
            true_regressions.append(t)
            
    # true ftp solved checks if it failed in baseline and passed in patched
    ftp_solved_list = []
    baseline_failed = set(baseline_summary["tests"]["failed_list"])
    patched_passed = set(patched_summary["tests"]["passed_list"])
    for t in fail_to_pass_expected:
        failed_in_base = any(t in bf for bf in baseline_failed)
        passed_in_patch = any(t in pp for pp in patched_passed)
        if failed_in_base and passed_in_patch:
            ftp_solved_list.append(t)

    ftp_solved_count = len(ftp_solved_list)
    regression_count = len(true_regressions)
    
    ftp_solved = ftp_solved_count > 0 and regression_count == 0
    
    # Update patched_summary to reflect true regressions
    patched_summary["tests"]["pass_to_pass_regressions"] = true_regressions
    with open(out_dir / "patched" / "summary.json", "w") as f:
        json.dump(patched_summary, f, indent=2)

    
    comparison = {
        "instance_id": args.instance_id,
        "issue_context": args.issue_context or "unknown",
        "patch_applies": patched_summary["patch_applies"],
        "tests_ran": patched_summary["ran"],
        "ftp_solved": ftp_solved,
        "ftp_solved_count": ftp_solved_count,
        "ftp_total_expected": len(fail_to_pass_expected),
        "regression_count": regression_count,
        "baseline_pass_rate": baseline_summary["tests"]["pass_rate"],
        "patched_pass_rate": patched_summary["tests"]["pass_rate"],
        "pass_rate_delta": patched_summary["tests"]["pass_rate"] - baseline_summary["tests"]["pass_rate"]
    }
    
    with open(out_dir / "comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)
        
    print(json.dumps(comparison, indent=2))
    print(f"\\nEvaluation complete. Artifacts saved to {out_dir}")
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_json", required=True)
    parser.add_argument("--instance_id", required=True)
    parser.add_argument("--patch_file", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--issue_context", default="")
    args = parser.parse_args()
    evaluate_instance(args)
