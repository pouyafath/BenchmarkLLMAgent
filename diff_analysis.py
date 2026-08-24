import json
from pathlib import Path

run_dir = Path("runs/pouya_enhanced_openhands_20260505_084500")

def get_eval(report_path):
    if not Path(report_path).exists(): return False, False
    with open(report_path) as f: r = json.load(f)
    s = r.get("tests_status", {})
    return len(s.get("PASS_TO_PASS", {}).get("failure", [])) == 0, len(s.get("FAIL_TO_PASS", {}).get("failure", [])) == 0

b_eval = run_dir / "solver_baseline_eval"
e_eval = run_dir / "solver_enhanced_eval"

for d in b_eval.glob("*/"):
    if not d.is_dir(): continue
    inst = d.name
    bp, bf = get_eval(b_eval / inst / "report.json")
    ep, ef = get_eval(e_eval / inst / "report.json")
    
    if bp != ep or bf != ef:
        print(f"{inst}:")
        print(f"  Baseline: P2P={'PASS' if bp else 'FAIL'}, F2P={'PASS' if bf else 'FAIL'}")
        print(f"  Enhanced: P2P={'PASS' if ep else 'FAIL'}, F2P={'PASS' if ef else 'FAIL'}")
