#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 72b35a46684c0ecf4182500d3320836607d1f17c
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -v --no-build-isolation -e .
git checkout 72b35a46684c0ecf4182500d3320836607d1f17c sklearn/covariance/tests/test_robust_covariance.py
git apply -v - <<'EOF_114329324912'
diff --git a/sklearn/covariance/tests/test_robust_covariance.py b/sklearn/covariance/tests/test_robust_covariance.py
index ebeb2c6e5aa6b..a7bd3996b9e4b 100644
--- a/sklearn/covariance/tests/test_robust_covariance.py
+++ b/sklearn/covariance/tests/test_robust_covariance.py
@@ -34,6 +34,9 @@ def test_mcd(global_random_seed):
     # 1D data set
     launch_mcd_on_dataset(500, 1, 100, 0.02, 0.02, 350, global_random_seed)
 
+    # n_samples == n_features
+    launch_mcd_on_dataset(20, 20, 0, 0.1, 0.1, 15, global_random_seed)
+
 
 def test_fast_mcd_on_invalid_input():
     X = np.arange(100)

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA sklearn/covariance/tests/test_robust_covariance.py
: '>>>>> End Test Output'
git checkout 72b35a46684c0ecf4182500d3320836607d1f17c sklearn/covariance/tests/test_robust_covariance.py
