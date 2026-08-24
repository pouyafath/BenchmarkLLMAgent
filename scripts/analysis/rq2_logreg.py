#!/usr/bin/env python3
"""
RQ2 — What SE features (from issue title+body) are related to a better enhancement?

Two-step (feature extractor lives in the issue_enhancer_py312 env; sklearn in bench_env):

  # 1. extract the 81-feature SE set for the 279 evaluable issues -> /tmp/rq2_se_features.json
  /home/22pf2/anaconda3/envs/issue_enhancer_py312/bin/python -c '
  import json,sys; sys.path.insert(0,"/home/22pf2/LLMforGithubIssuesRefactor/src")
  from issue_enhancer_agent_llm_based.feature_extraction_utils import extract_base_features
  d=json.load(open("/home/22pf2/BenchmarkLLMAgent/runs/stage6_new182_scores/FINAL_382_correctness.json"))["matrix"]
  rows={json.loads(l)["instance_id"]:json.loads(l) for l in open("/home/22pf2/BenchmarkLLMAgent/data/matrix_sample382_node01.jsonl") if l.strip()}
  out={}
  for iid in d["aider"]["enh:openhands"]:
      ps=rows[iid].get("problem_statement","") or ""; p=ps.split(chr(10),1)
      df=extract_base_features({"title":p[0],"body":p[1] if len(p)>1 else ""})
      out[iid]={k:float(df.iloc[0][k]) for k in df.columns}
  json.dump(out,open("/tmp/rq2_se_features.json","w"))'

  # 2. regress (this script)
  bench_env/bin/python scripts/analysis/rq2_logreg.py

Fits the downstream 'resolved' outcome on the best enhancer x solver cell (enh:openhands -> aider)
with L1 logistic regression (CV-tuned penalty); plus a helped-vs-hurt direction model on the
discordant issues. Reports L1-selected standardized odds ratios and 5-fold CV ROC-AUC.
"""
import json, numpy as np, warnings
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score

ROOT = "/home/22pf2/BenchmarkLLMAgent"
F = json.load(open("/tmp/rq2_se_features.json"))          # 81 SE features per issue
d = json.load(open(f"{ROOT}/runs/stage6_new182_scores/FINAL_382_correctness.json"))["matrix"]
res, base = d["aider"]["enh:openhands"], d["aider"]["baseline"]
ids = list(F); names = sorted(next(iter(F.values())).keys())
X = np.array([[F[i][n] for n in names] for i in ids])
y = np.array([1 if res[i] else 0 for i in ids])
keep = [j for j in range(X.shape[1]) if X[:, j].std() > 1e-9]
X, names = X[:, keep], [names[j] for j in keep]
Xs = StandardScaler().fit_transform(X)
print(f"n={len(y)} resolved={y.sum()} | non-constant SE features={len(names)}")

clf = LogisticRegressionCV(Cs=np.logspace(-2, 1, 12), penalty="l1", solver="liblinear",
                           cv=5, scoring="roc_auc", max_iter=5000, refit=True).fit(Xs, y)
auc = cross_val_score(clf, Xs, y, cv=5, scoring="roc_auc")
print(f"FULL 81-SE-feature model: 5-fold CV ROC-AUC = {auc.mean():.3f} ± {auc.std():.3f}")
sel = sorted([(names[j], clf.coef_[0][j]) for j in range(len(names)) if abs(clf.coef_[0][j]) > 1e-6],
             key=lambda z: -abs(z[1]))
print(f"L1-selected {len(sel)}/{len(names)} (standardized OR):")
for nm, c in sel:
    print(f"   {nm:<34} {np.exp(c):4.2f}")

disc = [i for i in ids if res[i] != base[i]]
Xd = StandardScaler().fit_transform(np.array([[F[i][n] for n in names] for i in disc]))
yd = np.array([1 if (res[i] and not base[i]) else 0 for i in disc])
ad = cross_val_score(LogisticRegression(penalty="l1", solver="liblinear", C=0.3, max_iter=5000),
                     Xd, yd, cv=5, scoring="roc_auc")
print(f"\ndirection helped-vs-hurt: n={len(yd)} helped={yd.sum()} | 5-fold CV AUC = {ad.mean():.3f}")
