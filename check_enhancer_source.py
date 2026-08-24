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
    # Check progress.json or enhancement logs
    prog = Path(path) / "progress.json"
    if prog.exists():
        with open(prog) as f:
            p = json.load(f)
        stage = p.get("current_stage", "?")
        print(f"{name}: stage={stage}")
    
    # Check the enhancement output files
    enh_dir = Path(path) / "enhancement_outputs"
    if enh_dir.exists():
        files = list(enh_dir.glob("*.json"))
        if files:
            with open(files[0]) as f:
                d = json.load(f)
            print(f"  Enhancement output keys: {list(d.keys())}")
            if "enhancer_type" in d:
                print(f"  enhancer_type: {d['enhancer_type']}")
    
    # Check run.log for proxy/fallback mentions
    log = Path(path) / "run.log"
    if log.exists():
        text = log.read_text()
        proxy_count = text.lower().count("proxy")
        fallback_count = text.lower().count("fallback")
        native_count = text.lower().count("native")
        real_count = text.lower().count("enhancer_type")
        print(f"  run.log mentions: proxy={proxy_count}, fallback={fallback_count}, native={native_count}, enhancer_type={real_count}")
    print()
