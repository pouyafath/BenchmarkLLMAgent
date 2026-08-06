#!/usr/bin/env python3
"""
RQ2 (reward-model version) — faithful to the prior paper: 581 features (81 base SE + 500 TF-IDF of
the ORIGINAL issue title+body) -> logistic regression on an INTRINSIC 'successful enhancement'
outcome defined by the learned reward model (LightGBM quality score of the ENHANCED report >= 0.5).
Enhancer = OpenHands (best cell). Run with the issue_enhancer_py312 env (reward model + sklearn).
"""
import os, sys, json, glob, numpy as np, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/home/22pf2/LLMforGithubIssuesRefactor/src")
os.environ["PYTHONPATH"] = "/home/22pf2/LLMforGithubIssuesRefactor/src"
os.environ["RAG_COLLECTION_NAME"] = "seed_309"
import logging; logging.disable(logging.CRITICAL)

from RefactoredIssueEnhancerDeepAgent.Managed_IssueEnhancerDeepAgent_V2_29.runtime import build_issue_enhancer_runtime
from RefactoredIssueEnhancerDeepAgent.config import IssueEnhancerDeepAgentConfig
from issue_enhancer_agent_llm_based.feature_extraction_utils import extract_base_features

cfg = IssueEnhancerDeepAgentConfig()
cfg.llm.provider = "ollama"; cfg.llm.model_name = "qwen3:32b"; cfg.llm.base_url = "http://localhost:11435"
cfg.planner.model_name = "qwen3:32b"; cfg.evaluation.fast_probability_threshold = 0.5
rt = build_issue_enhancer_runtime(cfg)
checker = next(getattr(rt, n) for n in dir(rt) if getattr(rt, n).__class__.__name__ == "EvaluationChecker")
tfv = checker.tf_vectorizer
print(f"reward model + TF vectorizer loaded (TF dims={len(tfv.get_feature_names_out())})", flush=True)

B = "/home/22pf2/BenchmarkLLMAgent"
rows = {json.loads(l)["instance_id"]: json.loads(l) for l in open(f"{B}/data/matrix_sample382_node01.jsonl") if l.strip()}
enh = {}
for f in glob.glob(f"{B}/runs/matrix*_*/qwen3_32b/stage4/openhands/enhanced_openhands.jsonl"):
    for l in open(f):
        if l.strip():
            r = json.loads(l); enh[r["instance_id"]] = r.get("problem_statement", "") or ""
ids = [i for i in rows if i in enh]

def split(ps): p = ps.split("\n", 1); return p[0], (p[1] if len(p) > 1 else "")
def score(title, body):
    return float(checker.evaluate_issue(title=title, body=body, issue_data={}).fast_probability)
def feat581(title, body):
    base = extract_base_features({"title": title, "body": body})
    b = base.iloc[0].to_numpy(dtype=float)
    tf = tfv.transform([f"{title} {body}"]).toarray()[0]
    return np.concatenate([b, tf]), list(base.columns)

X = []; y = []; os_all = []; es_all = []; names = None
for k, iid in enumerate(ids):
    ot, ob = split(rows[iid].get("problem_statement", "") or "")
    et, eb = split(enh[iid])
    osc, esc = score(ot, ob), score(et, eb)
    vec, base_names = feat581(ot, ob)          # features of the ORIGINAL issue
    if names is None: names = base_names + [f"tf::{w}" for w in tfv.get_feature_names_out()]
    X.append(vec); y.append(1 if esc >= 0.5 else 0); os_all.append(osc); es_all.append(esc)
    if (k + 1) % 80 == 0: print(f"  scored {k+1}/{len(ids)}", flush=True)

X = np.array(X); y = np.array(y); os_all = np.array(os_all); es_all = np.array(es_all)
print(f"\nn={len(y)} | 581 features | reward-model outcome (enhanced>=0.5): positives={y.sum()} ({100*y.mean():.0f}%)")
print(f"reward scores: original mean {os_all.mean():.3f} (>=.5: {int((os_all>=.5).sum())}) | "
      f"enhanced mean {es_all.mean():.3f} (>=.5: {int((es_all>=.5).sum())}) | "
      f"improved (enh>orig): {int((es_all>os_all).sum())}/{len(y)} | crossed .5: {int(((os_all<.5)&(es_all>=.5)).sum())}")

from sklearn.linear_model import LogisticRegressionCV, LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
keep = [j for j in range(X.shape[1]) if X[:, j].std() > 1e-9]
Xk, nk = X[:, keep], [names[j] for j in keep]
Xs = StandardScaler().fit_transform(Xk)
clf = LogisticRegressionCV(Cs=np.logspace(-2, 1, 10), penalty="l1", solver="liblinear", cv=5,
                           scoring="roc_auc", max_iter=6000).fit(Xs, y)
auc = cross_val_score(clf, Xs, y, cv=5, scoring="roc_auc")
print(f"\n*** 581-feature (81 SE + 500 TF-IDF), reward-model outcome: 5-fold CV ROC-AUC = {auc.mean():.3f} ± {auc.std():.3f} ***")
sel = sorted([(nk[j], clf.coef_[0][j]) for j in range(len(nk)) if abs(clf.coef_[0][j]) > 1e-6], key=lambda z: -abs(z[1]))
print(f"L1-selected {len(sel)} features; top 20 (standardized OR):")
for nm, c in sel[:20]:
    print(f"   {nm:<32} OR={np.exp(c):4.2f}")

# also: does the improvement outcome differ?
yimp = (es_all > os_all).astype(int)
if 0 < yimp.sum() < len(yimp):
    a2 = cross_val_score(clf.__class__(Cs=[clf.C_[0]], penalty="l1", solver="liblinear", cv=3, scoring="roc_auc", max_iter=6000),
                         Xs, yimp, cv=5, scoring="roc_auc")
    print(f"\n(alt outcome = reward improved, positives={yimp.sum()}): 5-fold CV AUC = {a2.mean():.3f}")
json.dump({"auc_threshold":float(auc.mean()),"n":int(len(y)),"pos":int(y.sum()),
           "orig_ge05":int((os_all>=.5).sum()),"enh_ge05":int((es_all>=.5).sum()),
           "improved":int((es_all>os_all).sum()),"top":[(n,float(np.exp(c))) for n,c in sel[:20]]},
          open(f"{B}/runs/cl_enhanced_scores/rq2_rewardmodel.json","w"), indent=2)
print("\nsaved rq2_rewardmodel.json")
