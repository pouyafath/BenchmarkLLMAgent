#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 938fa18abab38e78ed5c0fd975133595a8f19d1f
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -v --no-build-isolation -e .
git checkout 938fa18abab38e78ed5c0fd975133595a8f19d1f sklearn/tests/test_docstring_parameters.py sklearn/utils/_testing.py sklearn/utils/tests/test_testing.py
git apply -v - <<'EOF_114329324912'
diff --git a/sklearn/tests/test_docstring_parameters.py b/sklearn/tests/test_docstring_parameters.py
index 34b698e3f2073..6d44a3546f1ea 100644
--- a/sklearn/tests/test_docstring_parameters.py
+++ b/sklearn/tests/test_docstring_parameters.py
@@ -14,6 +14,7 @@
 import sklearn
 from sklearn import metrics
 from sklearn.datasets import make_classification
+from sklearn.ensemble import StackingClassifier, StackingRegressor
 
 # make it possible to discover experimental estimators when calling `all_estimators`
 from sklearn.experimental import (
@@ -29,6 +30,7 @@
     assert_docstring_consistency,
     check_docstring_parameters,
     ignore_warnings,
+    skip_if_no_numpydoc,
 )
 from sklearn.utils.deprecation import _is_deprecated
 from sklearn.utils.estimator_checks import (
@@ -326,12 +328,9 @@ def _get_all_fitted_attributes(estimator):
     return [k for k in fit_attr if k.endswith("_") and not k.startswith("_")]
 
 
+@skip_if_no_numpydoc
 def test_precision_recall_f_score_docstring_consistency():
     """Check docstrings parameters of related metrics are consistent."""
-    pytest.importorskip(
-        "numpydoc",
-        reason="numpydoc is required to test the docstrings",
-    )
     assert_docstring_consistency(
         [
             metrics.precision_recall_fscore_support,
@@ -347,3 +346,14 @@ def test_precision_recall_f_score_docstring_consistency():
         # precison and recall.
         exclude_params=["average", "zero_division"],
     )
+
+
+@skip_if_no_numpydoc
+def test_stacking_classifier_regressor_docstring_consistency():
+    """Check docstrings parameters stacking estimators are consistent."""
+    assert_docstring_consistency(
+        [StackingClassifier, StackingRegressor],
+        include_params=["cv", "n_jobs", "passthrough", "verbose"],
+        include_attrs=True,
+        exclude_attrs=["final_estimator_"],
+    )
diff --git a/sklearn/utils/_testing.py b/sklearn/utils/_testing.py
index d2a784494e5cd..ef683089eb64d 100644
--- a/sklearn/utils/_testing.py
+++ b/sklearn/utils/_testing.py
@@ -298,6 +298,15 @@ def set_random_state(estimator, random_state=0):
         estimator.set_params(random_state=random_state)
 
 
+def _is_numpydoc():
+    try:
+        import numpydoc  # noqa
+    except (ImportError, AssertionError):
+        return False
+    else:
+        return True
+
+
 try:
     _check_array_api_dispatch(True)
     ARRAY_API_COMPAT_FUNCTIONAL = True
@@ -342,6 +351,10 @@ def set_random_state(estimator, random_state=0):
     if_safe_multiprocessing_with_blas = pytest.mark.skipif(
         sys.platform == "darwin", reason="Possible multi-process bug with some BLAS"
     )
+    skip_if_no_numpydoc = pytest.mark.skipif(
+        not _is_numpydoc(),
+        reason="numpydoc is required to test the docstrings",
+    )
 except ImportError:
     pass
 
diff --git a/sklearn/utils/tests/test_testing.py b/sklearn/utils/tests/test_testing.py
index 08ded6e404924..bc13019dab550 100644
--- a/sklearn/utils/tests/test_testing.py
+++ b/sklearn/utils/tests/test_testing.py
@@ -22,6 +22,7 @@
     ignore_warnings,
     raises,
     set_random_state,
+    skip_if_no_numpydoc,
     turn_warnings_into_errors,
 )
 from sklearn.utils.deprecation import deprecated
@@ -399,12 +400,8 @@ def fit(self, X, y):
         """Incorrect docstring but should not be tested"""
 
 
+@skip_if_no_numpydoc
 def test_check_docstring_parameters():
-    pytest.importorskip(
-        "numpydoc",
-        reason="numpydoc is required to test the docstrings",
-        minversion="1.2.0",
-    )
     incorrect = check_docstring_parameters(f_ok)
     assert incorrect == []
     incorrect = check_docstring_parameters(f_ok, ignore=["b"])
@@ -608,16 +605,14 @@ def f_three(a, b):  # pragma: no cover
     pass
 
 
+@skip_if_no_numpydoc
 def test_assert_docstring_consistency_object_type():
     """Check error raised when `objects` incorrect type."""
-    pytest.importorskip(
-        "numpydoc",
-        reason="numpydoc is required to test the docstrings",
-    )
     with pytest.raises(TypeError, match="All 'objects' must be one of"):
         assert_docstring_consistency(["string", f_one])
 
 
+@skip_if_no_numpydoc
 @pytest.mark.parametrize(
     "objects, kwargs, error",
     [
@@ -635,14 +630,11 @@ def test_assert_docstring_consistency_object_type():
 )
 def test_assert_docstring_consistency_arg_checks(objects, kwargs, error):
     """Check `assert_docstring_consistency` argument checking correct."""
-    pytest.importorskip(
-        "numpydoc",
-        reason="numpydoc is required to test the docstrings",
-    )
     with pytest.raises(TypeError, match=error):
         assert_docstring_consistency(objects, **kwargs)
 
 
+@skip_if_no_numpydoc
 @pytest.mark.parametrize(
     "objects, kwargs, error, warn",
     [
@@ -691,10 +683,6 @@ def test_assert_docstring_consistency_arg_checks(objects, kwargs, error):
 )
 def test_assert_docstring_consistency(objects, kwargs, error, warn):
     """Check `assert_docstring_consistency` gives correct results."""
-    pytest.importorskip(
-        "numpydoc",
-        reason="numpydoc is required to test the docstrings",
-    )
     if error:
         with pytest.raises(AssertionError, match=error):
             assert_docstring_consistency(objects, **kwargs)
@@ -745,12 +733,9 @@ def f_six(labels):  # pragma: no cover
     pass
 
 
+@skip_if_no_numpydoc
 def test_assert_docstring_consistency_error_msg():
     """Check `assert_docstring_consistency` difference message."""
-    pytest.importorskip(
-        "numpydoc.docscrape",
-        reason="numpydoc is required to test the docstrings",
-    )
     msg = r"""The description of Parameter 'labels' is inconsistent between
 \['f_four'\] and \['f_five'\] and \['f_six'\]:
 

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA sklearn/tests/test_docstring_parameters.py sklearn/utils/_testing.py sklearn/utils/tests/test_testing.py
: '>>>>> End Test Output'
git checkout 938fa18abab38e78ed5c0fd975133595a8f19d1f sklearn/tests/test_docstring_parameters.py sklearn/utils/_testing.py sklearn/utils/tests/test_testing.py
