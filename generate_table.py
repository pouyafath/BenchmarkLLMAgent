import json
import glob
from pathlib import Path

runs = [
    ("llm_append_analysis", "runs/pouya_solver20_20260505_063614"),
    ("aider", "runs/pouya_enhanced_aider_20260505_084500"),
    ("trae", "runs/pouya_enhanced_trae_20260505_084500"),
    ("openhands", "runs/pouya_enhanced_openhands_20260505_084500"),
    ("mini_swe_agent", "runs/pouya_enhanced_mini_swe_agent_20260505_084500"),
    ("swe_agent", "runs/pouya_enhanced_swe_agent_20260505_084500"),
]

def check_status(report_path):
    if not Path(report_path).exists():
        return False, False, False
    with open(report_path) as f:
        r = json.load(f)
    
    resolved = r.get("resolved", False)
    
    p2p_pass = False
    f2p_pass = False
    
    if "PASS_TO_PASS" in r:
        failures = r["PASS_TO_PASS"].get("failure", [])
        p2p_pass = len(failures) == 0
        
    if "FAIL_TO_PASS" in r:
        failures = r["FAIL_TO_PASS"].get("failure", [])
        f2p_pass = len(failures) == 0
        
    return p2p_pass, f2p_pass, resolved

print("| Enhancer | Baseline P2P | Enhanced P2P | Baseline F2P | Enhanced F2P | Baseline Resolved | Enhanced Resolved |")
print("|----------|--------------|--------------|--------------|--------------|-------------------|-------------------|")

for name, path in runs:
    base_p2p, base_f2p, base_res = 0, 0, 0
    enh_p2p, enh_f2p, enh_res = 0, 0, 0
    total = 0
    
    base_dir = Path(path) / "solver_baseline_eval"
    enh_dir = Path(path) / "solver_enhanced_eval"
    
    instances = set()
    if base_dir.exists():
        instances.update([d.name for d in base_dir.glob("*/") if d.is_dir()])
    if enh_dir.exists():
        instances.update([d.name for d in enh_dir.glob("*/") if d.is_dir()])
        
    for inst in instances:
        total += 1
        bp2p, bf2p, bres = check_status(base_dir / inst / "report.json")
        ep2p, ef2p, eres = check_status(enh_dir / inst / "report.json")
        
        base_p2p += int(bp2p)
        base_f2p += int(bf2p)
        base_res += int(bres)
        
        enh_p2p += int(ep2p)
        enh_f2p += int(ef2p)
        enh_res += int(eres)
        
    print(f"| {name} | {base_p2p}/{total} | {enh_p2p}/{total} | {base_f2p}/{total} | {enh_f2p}/{total} | {base_res}/{total} | {enh_res}/{total} |")

