#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 7ab1b647f57e0df5f33bdf14ae57a62b0bd861dd
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -v --no-build-isolation -e .
git checkout 7ab1b647f57e0df5f33bdf14ae57a62b0bd861dd sklearn/model_selection/tests/test_search.py
git apply -v - <<'EOF_114329324912'
diff --git a/sklearn/model_selection/tests/test_search.py b/sklearn/model_selection/tests/test_search.py
index e7637be8d654b..0efb934795be2 100644
--- a/sklearn/model_selection/tests/test_search.py
+++ b/sklearn/model_selection/tests/test_search.py
@@ -2864,3 +2864,11 @@ def test_yield_masked_array_for_each_param(candidate_params, expected):
         assert value.dtype == expected_value.dtype
         np.testing.assert_array_equal(value, expected_value)
         np.testing.assert_array_equal(value.mask, expected_value.mask)
+
+
+def test_yield_masked_array_no_runtime_warning():
+    # non-regression test for https://github.com/scikit-learn/scikit-learn/issues/29929
+    candidate_params = [{"param": i} for i in range(1000)]
+    with warnings.catch_warnings():
+        warnings.simplefilter("error", RuntimeWarning)
+        list(_yield_masked_array_for_each_param(candidate_params))

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA sklearn/model_selection/tests/test_search.py
: '>>>>> End Test Output'
git checkout 7ab1b647f57e0df5f33bdf14ae57a62b0bd861dd sklearn/model_selection/tests/test_search.py
