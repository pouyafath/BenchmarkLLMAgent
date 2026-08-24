#!/usr/bin/env python3
"""Analyze baseline results split by enhancement status."""
import json
from pathlib import Path

RUN = Path("/home/22pf2/BenchmarkLLMAgent/runs/test50_qwen3_20260611_222615")
OUT = RUN / "fallback_analysis.txt"

manifest = json.loads((RUN / "stage4_enhanced/fallback_manifest.json").read_text())
fallback_ids = set(manifest["fallback_ids"])
enhanced_ids = set(manifest["enhanced_ids"])

preds = json.load(open(RUN / "stage5_solver_eval/solver_baseline/preds.json"))

lines = []
def p(s=""): lines.append(s)

bl_enh_patched, bl_fb_patched = [], []
for iid, v in preds.items():
    has_patch = bool((v.get("model_patch","") or "").strip())
    if has_patch:
        if iid in enhanced_ids: bl_enh_patched.append(iid)
        else: bl_fb_patched.append(iid)

p("=" * 60)
p("BASELINE SOLVER — Split by Enhancement Status")
p("=" * 60)
p(f"Truly Enhanced group ({len(enhanced_ids)} instances):")
p(f"  Patches: {len(bl_enh_patched)}/{len(enhanced_ids)} ({100*len(bl_enh_patched)/len(enhanced_ids):.1f}%)")
for iid in sorted(bl_enh_patched):
    sz = len(preds[iid]["model_patch"].strip())
    p(f"    {iid}: {sz} chars")

p()
p(f"Fallback group ({len(fallback_ids)} instances):")
p(f"  Patches: {len(bl_fb_patched)}/{len(fallback_ids)} ({100*len(bl_fb_patched)/len(fallback_ids):.1f}%)")
for iid in sorted(bl_fb_patched):
    sz = len(preds[iid]["model_patch"].strip())
    p(f"    {iid}: {sz} chars")

p()
p("=" * 60)
p("KEY INSIGHT")
p("=" * 60)
p(f"Both groups see ORIGINAL issue text in baseline condition.")
p(f"In enhanced condition, fallback instances STILL see original text.")
p(f"So they add noise, not signal, to the enhanced vs baseline comparison.")
p()
p(f"Truly enhanced baseline patch rate: {100*len(bl_enh_patched)/len(enhanced_ids):.1f}%")
p(f"Fallback baseline patch rate:       {100*len(bl_fb_patched)/len(fallback_ids):.1f}%")
p()
p("Fallback instances that produced patches:")
for iid in sorted(bl_fb_patched):
    p(f"  {iid} — this instance's enhancement FAILED, so enhanced=baseline for it")

OUT.write_text("\n".join(lines))
print(f"Written to {OUT}")
