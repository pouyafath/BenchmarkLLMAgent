#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 98af964055bb1e719de0468ff1ddf58ec1e9d3d0
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -v --no-build-isolation -e .
git checkout 98af964055bb1e719de0468ff1ddf58ec1e9d3d0 sklearn/tests/test_calibration.py
git apply -v - <<'EOF_114329324912'
diff --git a/sklearn/tests/test_calibration.py b/sklearn/tests/test_calibration.py
index 6e5900e4fa4a6..774a6f83ad1b6 100644
--- a/sklearn/tests/test_calibration.py
+++ b/sklearn/tests/test_calibration.py
@@ -579,8 +579,12 @@ def test_calibration_attributes(clf, cv):
     X, y = make_classification(n_samples=10, n_features=5, n_classes=2, random_state=7)
     if cv == "prefit":
         clf = clf.fit(X, y)
-    calib_clf = CalibratedClassifierCV(clf, cv=cv)
-    calib_clf.fit(X, y)
+        calib_clf = CalibratedClassifierCV(clf, cv=cv)
+        with pytest.warns(FutureWarning):
+            calib_clf.fit(X, y)
+    else:
+        calib_clf = CalibratedClassifierCV(clf, cv=cv)
+        calib_clf.fit(X, y)
 
     if cv == "prefit":
         assert_array_equal(calib_clf.classes_, clf.classes_)
@@ -1077,20 +1081,48 @@ def test_sigmoid_calibration_max_abs_prediction_threshold(global_random_seed):
     assert_allclose(b2, b3, atol=atol)
 
 
-def test_float32_predict_proba(data):
+@pytest.mark.parametrize("use_sample_weight", [True, False])
+@pytest.mark.parametrize("method", ["sigmoid", "isotonic"])
+def test_float32_predict_proba(data, use_sample_weight, method):
     """Check that CalibratedClassifierCV works with float32 predict proba.
 
-    Non-regression test for gh-28245.
+    Non-regression test for gh-28245 and gh-28247.
     """
+    if use_sample_weight:
+        # Use dtype=np.float64 to check that this does not trigger an
+        # unintentional upcasting: the dtype of the base estimator should
+        # control the dtype of the final model. In particular, the
+        # sigmoid calibrator relies on inputs (predictions and sample weights)
+        # with consistent dtypes because it is partially written in Cython.
+        # As this test forces the predictions to be `float32`, we want to check
+        # that `CalibratedClassifierCV` internally converts `sample_weight` to
+        # the same dtype to avoid crashing the Cython call.
+        sample_weight = np.ones_like(data[1], dtype=np.float64)
+    else:
+        sample_weight = None
 
     class DummyClassifer32(DummyClassifier):
         def predict_proba(self, X):
             return super().predict_proba(X).astype(np.float32)
 
     model = DummyClassifer32()
-    calibrator = CalibratedClassifierCV(model)
-    # Does not raise an error
-    calibrator.fit(*data)
+    calibrator = CalibratedClassifierCV(model, method=method)
+    # Does not raise an error.
+    calibrator.fit(*data, sample_weight=sample_weight)
+
+    # Check with frozen prefit model
+    model = DummyClassifer32().fit(*data, sample_weight=sample_weight)
+    calibrator = CalibratedClassifierCV(FrozenEstimator(model), method=method)
+    # Does not raise an error.
+    calibrator.fit(*data, sample_weight=sample_weight)
+
+    # TODO(1.8): remove me once the deprecation period is over.
+    # Check with prefit model using the deprecated cv="prefit" argument:
+    model = DummyClassifer32().fit(*data, sample_weight=sample_weight)
+    calibrator = CalibratedClassifierCV(model, method=method, cv="prefit")
+    # Does not raise an error.
+    with pytest.warns(FutureWarning):
+        calibrator.fit(*data, sample_weight=sample_weight)
 
 
 def test_error_less_class_samples_than_folds():

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA sklearn/tests/test_calibration.py
: '>>>>> End Test Output'
git checkout 98af964055bb1e719de0468ff1ddf58ec1e9d3d0 sklearn/tests/test_calibration.py
