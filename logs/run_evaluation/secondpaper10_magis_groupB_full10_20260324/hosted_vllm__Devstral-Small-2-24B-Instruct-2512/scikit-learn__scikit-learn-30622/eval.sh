#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 2707099b23a0a8580731553629566c1182d26f48
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -v --no-build-isolation -e .
git checkout 2707099b23a0a8580731553629566c1182d26f48 sklearn/ensemble/tests/test_voting.py
git apply -v - <<'EOF_114329324912'
diff --git a/sklearn/ensemble/tests/test_voting.py b/sklearn/ensemble/tests/test_voting.py
index bb0d34bcd7d16..797dd9bdd5989 100644
--- a/sklearn/ensemble/tests/test_voting.py
+++ b/sklearn/ensemble/tests/test_voting.py
@@ -52,6 +52,14 @@
             {"estimators": []},
             "Invalid 'estimators' attribute, 'estimators' should be a non-empty list",
         ),
+        (
+            {"estimators": [LogisticRegression()]},
+            "Invalid 'estimators' attribute, 'estimators' should be a non-empty list",
+        ),
+        (
+            {"estimators": [(213, LogisticRegression())]},
+            "Invalid 'estimators' attribute, 'estimators' should be a non-empty list",
+        ),
         (
             {"estimators": [("lr", LogisticRegression())], "weights": [1, 2]},
             "Number of `estimators` and weights must be equal",

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA sklearn/ensemble/tests/test_voting.py
: '>>>>> End Test Output'
git checkout 2707099b23a0a8580731553629566c1182d26f48 sklearn/ensemble/tests/test_voting.py
