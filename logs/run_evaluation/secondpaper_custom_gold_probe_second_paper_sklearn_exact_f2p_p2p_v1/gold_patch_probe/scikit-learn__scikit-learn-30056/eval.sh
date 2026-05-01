#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 5b0ca3939854a3823beee6840b415a32ef16deb2
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -v --no-build-isolation -e .
git checkout 5b0ca3939854a3823beee6840b415a32ef16deb2 sklearn/utils/_test_common/instance_generator.py sklearn/utils/tests/test_class_weight.py
git apply -v - <<'EOF_114329324912'
diff --git a/sklearn/utils/_test_common/instance_generator.py b/sklearn/utils/_test_common/instance_generator.py
index c46213b417090..f1978c130c108 100644
--- a/sklearn/utils/_test_common/instance_generator.py
+++ b/sklearn/utils/_test_common/instance_generator.py
@@ -569,6 +569,17 @@
         "check_dict_unchanged": dict(batch_size=10, max_iter=5, n_components=1)
     },
     LinearDiscriminantAnalysis: {"check_dict_unchanged": dict(n_components=1)},
+    LinearSVC: {
+        "check_sample_weight_equivalence": [
+            # TODO: dual=True is a stochastic solver: we cannot rely on
+            # check_sample_weight_equivalence to check the correct handling of
+            # sample_weight and we would need a statistical test instead, see
+            # meta-issue #162298.
+            # dict(max_iter=20, dual=True, tol=1e-12),
+            dict(dual=False, tol=1e-12),
+            dict(dual=False, tol=1e-12, class_weight="balanced"),
+        ]
+    },
     LinearRegression: {
         "check_estimator_sparse_tag": [dict(positive=False), dict(positive=True)],
         "check_sample_weight_equivalence_on_dense_data": [
@@ -584,6 +595,14 @@
             dict(solver="liblinear"),
             dict(solver="newton-cg"),
             dict(solver="newton-cholesky"),
+            dict(solver="newton-cholesky", class_weight="balanced"),
+        ]
+    },
+    LogisticRegressionCV: {
+        "check_sample_weight_equivalence": [
+            dict(solver="lbfgs"),
+            dict(solver="newton-cholesky"),
+            dict(solver="newton-cholesky", class_weight="balanced"),
         ],
         "check_sample_weight_equivalence_on_sparse_data": [
             dict(solver="liblinear"),
diff --git a/sklearn/utils/tests/test_class_weight.py b/sklearn/utils/tests/test_class_weight.py
index b98ce6be05658..3efee050c3b90 100644
--- a/sklearn/utils/tests/test_class_weight.py
+++ b/sklearn/utils/tests/test_class_weight.py
@@ -129,14 +129,32 @@ def test_compute_class_weight_balanced_negative():
     assert len(cw) == len(classes)
     assert_array_almost_equal(cw, np.array([1.0, 1.0, 1.0]))
 
-    # Test with unbalanced class labels.
-    y = np.asarray([-1, 0, 0, -2, -2, -2])
 
-    cw = compute_class_weight("balanced", classes=classes, y=y)
-    assert len(cw) == len(classes)
-    class_counts = np.bincount(y + 2)
-    assert_almost_equal(np.dot(cw, class_counts), y.shape[0])
-    assert_array_almost_equal(cw, [2.0 / 3, 2.0, 1.0])
+def test_compute_class_weight_balanced_sample_weight_equivalence():
+    # Test with unbalanced and negative class labels for
+    # equivalence between repeated and weighted samples
+
+    classes = np.array([-2, -1, 0])
+    y = np.asarray([-1, -1, 0, 0, -2, -2])
+    sw = np.asarray([1, 0, 1, 1, 1, 2])
+
+    y_rep = np.repeat(y, sw, axis=0)
+
+    class_weights_weighted = compute_class_weight(
+        "balanced", classes=classes, y=y, sample_weight=sw
+    )
+    class_weights_repeated = compute_class_weight("balanced", classes=classes, y=y_rep)
+    assert len(class_weights_weighted) == len(classes)
+    assert len(class_weights_repeated) == len(classes)
+
+    class_counts_weighted = np.bincount(y + 2, weights=sw)
+    class_counts_repeated = np.bincount(y_rep + 2)
+
+    assert np.dot(class_weights_weighted, class_counts_weighted) == pytest.approx(
+        np.dot(class_weights_repeated, class_counts_repeated)
+    )
+
+    assert_allclose(class_weights_weighted, class_weights_repeated)
 
 
 def test_compute_class_weight_balanced_unordered():

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA sklearn/utils/_test_common/instance_generator.py sklearn/utils/tests/test_class_weight.py
: '>>>>> End Test Output'
git checkout 5b0ca3939854a3823beee6840b415a32ef16deb2 sklearn/utils/_test_common/instance_generator.py sklearn/utils/tests/test_class_weight.py
