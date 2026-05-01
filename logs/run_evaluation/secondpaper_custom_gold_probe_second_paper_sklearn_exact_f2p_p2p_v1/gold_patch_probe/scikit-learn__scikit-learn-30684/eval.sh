#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff b9be6d385c985464d26d7d11c582e836b486691d
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -v --no-build-isolation -e .
git checkout b9be6d385c985464d26d7d11c582e836b486691d sklearn/linear_model/tests/test_base.py
git apply -v - <<'EOF_114329324912'
diff --git a/sklearn/linear_model/tests/test_base.py b/sklearn/linear_model/tests/test_base.py
index be8e85b9703fa..cf8dfdf4e4712 100644
--- a/sklearn/linear_model/tests/test_base.py
+++ b/sklearn/linear_model/tests/test_base.py
@@ -72,7 +72,7 @@ def test_linear_regression_sample_weights(
     sample_weight = 1.0 + rng.uniform(size=n_samples)
 
     # LinearRegression with explicit sample_weight
-    reg = LinearRegression(fit_intercept=fit_intercept)
+    reg = LinearRegression(fit_intercept=fit_intercept, tol=1e-16)
     reg.fit(X, y, sample_weight=sample_weight)
     coefs1 = reg.coef_
     inter1 = reg.intercept_

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA sklearn/linear_model/tests/test_base.py
: '>>>>> End Test Output'
git checkout b9be6d385c985464d26d7d11c582e836b486691d sklearn/linear_model/tests/test_base.py
