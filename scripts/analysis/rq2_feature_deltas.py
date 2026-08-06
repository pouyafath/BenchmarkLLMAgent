#!/usr/bin/env python3
"""
RQ2 (descriptive) — which SE features does enhancement ADD?
For each truly-enhanced issue, extract the 81 SE features of the ORIGINAL and the ENHANCED
title+body; a feature is 'gained' when it is absent in the original (0/False) and present in the
enhanced (True or >0). Ranks the presence-type features by how many enhancements add them.

Run with the issue_enhancer_py312 env (needs feature_extraction_utils). Enhancer default = OpenHands.
"""
import json, glob, sys
sys.path.insert(0, "/home/22pf2/LLMforGithubIssuesRefactor/src")
from issue_enhancer_agent_llm_based.feature_extraction_utils import extract_base_features

B = "/home/22pf2/BenchmarkLLMAgent"
ENHANCER_GLOB = f"{B}/runs/matrix*_*/qwen3_32b/stage4/openhands/enhanced_openhands.jsonl"
rows = {json.loads(l)["instance_id"]: json.loads(l) for l in open(f"{B}/data/matrix_sample382_node01.jsonl") if l.strip()}
enh, ok = {}, {}
for f in glob.glob(ENHANCER_GLOB):
    for l in open(f):
        if l.strip():
            r = json.loads(l); enh[r["instance_id"]] = r.get("problem_statement", "") or ""; ok[r["instance_id"]] = bool(r.get("_enh_ok"))

PRESENCE = ["body_has_reproduction_steps", "body_has_expected_behavior", "body_has_actual_behavior",
            "body_has_logs", "body_has_error_message", "body_has_environment_info", "body_has_stack_trace",
            "has_code_blocks", "has_sections", "body_num_headers", "has_list_items", "body_num_lists",
            "has_checkboxes", "has_todo_list", "has_urls", "has_images", "has_questions_in_body",
            "body_num_tables", "body_num_bold_text", "body_num_inline_code", "body_num_links",
            "num_file_references", "title_contains_error", "title_contains_version_number"]
def split(ps): p = ps.split("\n", 1); return p[0], (p[1] if len(p) > 1 else "")
def present(v): return 1 if (v is True or (isinstance(v, (int, float)) and v > 0)) else 0

ids = [i for i in rows if i in enh and ok.get(i)]
gained = {f: 0 for f in PRESENCE}
for iid in ids:
    ot, ob = split(rows[iid].get("problem_statement", "") or ""); et, eb = split(enh[iid])
    of = extract_base_features({"title": ot, "body": ob}).iloc[0]
    ef = extract_base_features({"title": et, "body": eb}).iloc[0]
    for f in PRESENCE:
        if f in of and f in ef and present(of[f]) == 0 and present(ef[f]) == 1:
            gained[f] += 1
N = len(ids)
print(f"enhancer=OpenHands | truly-enhanced issues N={N}\n{'feature':<30}{'gained':>8}{'%N':>7}")
out = []
for f, c in sorted(gained.items(), key=lambda z: -z[1]):
    print(f"{f:<30}{c:>8}{round(100*c/N):>6}%"); out.append({"feature": f, "gained": c, "pct": round(100*c/N)})
json.dump({"enhancer": "openhands", "N": N, "features_added": out},
          open(f"{B}/runs/cl_enhanced_scores/rq2_feature_deltas.json", "w"), indent=2)
