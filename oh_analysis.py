import json
from pathlib import Path

run_dir = Path("runs/pouya_enhanced_aider_20260505_084500")

def get_status(report_path):
    if not Path(report_path).exists():
        return False, False, False
    with open(report_path) as f:
        r = json.load(f)
    
    res = r.get("resolved", False)
    # Check if nested or flat
    if "PASS_TO_PASS" in r:
        p_fail = len(r["PASS_TO_PASS"].get("failure", []))
        f_fail = len(r["FAIL_TO_PASS"].get("failure", []))
    else:
        s = r.get("tests_status", {})
        p_fail = len(s.get("PASS_TO_PASS", {}).get("failure", []))
        f_fail = len(s.get("FAIL_TO_PASS", {}).get("failure", []))
        
    return p_fail == 0, f_fail == 0, res

def categorize(p2p_pass, f2p_pass, resolved):
    if resolved: return "Resolved"
    if not p2p_pass: return "Regression"
    if not f2p_pass: return "Failed Fix"
    return "Unknown"

b_eval = run_dir / "solver_baseline_eval"
e_eval = run_dir / "solver_enhanced_eval"

markdown = ["### OpenHands Enhancer Analysis (20 Issues)"]
markdown.append("| Instance ID | Baseline Outcome | Enhanced Outcome | Shift |")
markdown.append("|---|---|---|---|")

for d in b_eval.glob("*/"):
    if not d.is_dir(): continue
    inst = d.name
    bp, bf, br = get_status(b_eval / inst / "report.json")
    ep, ef, er = get_status(e_eval / inst / "report.json")
    
    b_cat = categorize(bp, bf, br)
    e_cat = categorize(ep, ef, er)
    
    if b_cat != e_cat:
        shift = "❌ Worsened" if (b_cat == "Failed Fix" and e_cat == "Regression") else "🔄 Changed"
    else:
        shift = "⏸️ Unchanged"
        
    markdown.append(f"| `{inst}` | {b_cat} | {e_cat} | {shift} |")

with open("analysis_results.md", "w") as f:
    f.write("\n".join(markdown))
