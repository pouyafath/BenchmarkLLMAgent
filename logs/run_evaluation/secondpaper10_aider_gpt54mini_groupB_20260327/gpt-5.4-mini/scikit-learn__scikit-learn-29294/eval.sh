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
git checkout 2707099b23a0a8580731553629566c1182d26f48 sklearn/utils/tests/test_parallel.py
git apply -v - <<'EOF_114329324912'
diff --git a/sklearn/utils/tests/test_parallel.py b/sklearn/utils/tests/test_parallel.py
index 3a359ef8690e5..2f5025afe0662 100644
--- a/sklearn/utils/tests/test_parallel.py
+++ b/sklearn/utils/tests/test_parallel.py
@@ -1,4 +1,5 @@
 import time
+import warnings
 
 import joblib
 import numpy as np
@@ -9,6 +10,7 @@
 from sklearn.compose import make_column_transformer
 from sklearn.datasets import load_iris
 from sklearn.ensemble import RandomForestClassifier
+from sklearn.exceptions import ConvergenceWarning
 from sklearn.model_selection import GridSearchCV
 from sklearn.pipeline import make_pipeline
 from sklearn.preprocessing import StandardScaler
@@ -98,3 +100,54 @@ def transform(self, X, y=None):
         search_cv.fit(iris.data, iris.target)
 
     assert not np.isnan(search_cv.cv_results_["mean_test_score"]).any()
+
+
+def raise_warning():
+    warnings.warn("Convergence warning", ConvergenceWarning)
+
+
+@pytest.mark.parametrize("n_jobs", [1, 2])
+@pytest.mark.parametrize("backend", ["loky", "threading", "multiprocessing"])
+def test_filter_warning_propagates(n_jobs, backend):
+    """Check warning propagates to the job."""
+    with warnings.catch_warnings():
+        warnings.simplefilter("error", category=ConvergenceWarning)
+
+        with pytest.raises(ConvergenceWarning):
+            Parallel(n_jobs=n_jobs, backend=backend)(
+                delayed(raise_warning)() for _ in range(2)
+            )
+
+
+def get_warnings():
+    return warnings.filters
+
+
+def test_check_warnings_threading():
+    """Check that warnings filters are set correctly in the threading backend."""
+    with warnings.catch_warnings():
+        warnings.simplefilter("error", category=ConvergenceWarning)
+
+        filters = warnings.filters
+        assert ("error", None, ConvergenceWarning, None, 0) in filters
+
+        all_warnings = Parallel(n_jobs=2, backend="threading")(
+            delayed(get_warnings)() for _ in range(2)
+        )
+
+        assert all(w == filters for w in all_warnings)
+
+
+def test_filter_warning_propagates_no_side_effect_with_loky_backend():
+    with warnings.catch_warnings():
+        warnings.simplefilter("error", category=ConvergenceWarning)
+
+        Parallel(n_jobs=2, backend="loky")(delayed(time.sleep)(0) for _ in range(10))
+
+        # Since loky workers are reused, make sure that inside the loky workers,
+        # warnings filters have been reset to their original value. Using joblib
+        # directly should not turn ConvergenceWarning into an error.
+        joblib.Parallel(n_jobs=2, backend="loky")(
+            joblib.delayed(warnings.warn)("Convergence warning", ConvergenceWarning)
+            for _ in range(10)
+        )

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA sklearn/utils/tests/test_parallel.py
: '>>>>> End Test Output'
git checkout 2707099b23a0a8580731553629566c1182d26f48 sklearn/utils/tests/test_parallel.py
