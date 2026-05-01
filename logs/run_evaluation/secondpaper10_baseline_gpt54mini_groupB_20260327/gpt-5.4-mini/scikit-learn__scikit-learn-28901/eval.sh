#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff ca7b42b4b7532ec4551dd5e35d699a143b939f19
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -v --no-build-isolation -e .
git checkout ca7b42b4b7532ec4551dd5e35d699a143b939f19 sklearn/semi_supervised/tests/test_self_training.py sklearn/tests/metadata_routing_common.py sklearn/tests/test_metaestimators_metadata_routing.py sklearn/tests/test_pipeline.py
git apply -v - <<'EOF_114329324912'
diff --git a/sklearn/semi_supervised/tests/test_self_training.py b/sklearn/semi_supervised/tests/test_self_training.py
index 29b8f1ac6e87c..02244063994d5 100644
--- a/sklearn/semi_supervised/tests/test_self_training.py
+++ b/sklearn/semi_supervised/tests/test_self_training.py
@@ -12,6 +12,7 @@
 from sklearn.neighbors import KNeighborsClassifier
 from sklearn.semi_supervised import SelfTrainingClassifier
 from sklearn.svm import SVC
+from sklearn.tests.test_pipeline import SimpleEstimator
 from sklearn.tree import DecisionTreeClassifier
 
 # Authors: The scikit-learn developers
@@ -43,25 +44,25 @@ def test_warns_k_best():
 
 
 @pytest.mark.parametrize(
-    "base_estimator",
+    "estimator",
     [KNeighborsClassifier(), SVC(gamma="scale", probability=True, random_state=0)],
 )
 @pytest.mark.parametrize("selection_crit", ["threshold", "k_best"])
-def test_classification(base_estimator, selection_crit):
+def test_classification(estimator, selection_crit):
     # Check classification for various parameter settings.
     # Also assert that predictions for strings and numerical labels are equal.
     # Also test for multioutput classification
     threshold = 0.75
     max_iter = 10
     st = SelfTrainingClassifier(
-        base_estimator, max_iter=max_iter, threshold=threshold, criterion=selection_crit
+        estimator, max_iter=max_iter, threshold=threshold, criterion=selection_crit
     )
     st.fit(X_train, y_train_missing_labels)
     pred = st.predict(X_test)
     proba = st.predict_proba(X_test)
 
     st_string = SelfTrainingClassifier(
-        base_estimator, max_iter=max_iter, criterion=selection_crit, threshold=threshold
+        estimator, max_iter=max_iter, criterion=selection_crit, threshold=threshold
     )
     st_string.fit(X_train, y_train_missing_strings)
     pred_string = st_string.predict(X_test)
@@ -112,15 +113,15 @@ def test_k_best():
 
 
 def test_sanity_classification():
-    base_estimator = SVC(gamma="scale", probability=True)
-    base_estimator.fit(X_train[n_labeled_samples:], y_train[n_labeled_samples:])
+    estimator = SVC(gamma="scale", probability=True)
+    estimator.fit(X_train[n_labeled_samples:], y_train[n_labeled_samples:])
 
-    st = SelfTrainingClassifier(base_estimator)
+    st = SelfTrainingClassifier(estimator)
     st.fit(X_train, y_train_missing_labels)
 
-    pred1, pred2 = base_estimator.predict(X_test), st.predict(X_test)
+    pred1, pred2 = estimator.predict(X_test), st.predict(X_test)
     assert not np.array_equal(pred1, pred2)
-    score_supervised = accuracy_score(base_estimator.predict(X_test), y_test)
+    score_supervised = accuracy_score(estimator.predict(X_test), y_test)
     score_self_training = accuracy_score(st.predict(X_test), y_test)
 
     assert score_self_training > score_supervised
@@ -137,21 +138,21 @@ def test_none_iter():
 
 
 @pytest.mark.parametrize(
-    "base_estimator",
+    "estimator",
     [KNeighborsClassifier(), SVC(gamma="scale", probability=True, random_state=0)],
 )
 @pytest.mark.parametrize("y", [y_train_missing_labels, y_train_missing_strings])
-def test_zero_iterations(base_estimator, y):
+def test_zero_iterations(estimator, y):
     # Check classification for zero iterations.
     # Fitting a SelfTrainingClassifier with zero iterations should give the
     # same results as fitting a supervised classifier.
     # This also asserts that string arrays work as expected.
 
-    clf1 = SelfTrainingClassifier(base_estimator, max_iter=0)
+    clf1 = SelfTrainingClassifier(estimator, max_iter=0)
 
     clf1.fit(X_train, y)
 
-    clf2 = base_estimator.fit(X_train[:n_labeled_samples], y[:n_labeled_samples])
+    clf2 = estimator.fit(X_train[:n_labeled_samples], y[:n_labeled_samples])
 
     assert_array_equal(clf1.predict(X_test), clf2.predict(X_test))
     assert clf1.termination_condition_ == "max_iter"
@@ -280,14 +281,14 @@ def test_k_best_selects_best():
         assert row in added_by_st
 
 
-def test_base_estimator_meta_estimator():
+def test_estimator_meta_estimator():
     # Check that a meta-estimator relying on an estimator implementing
     # `predict_proba` will work even if it does not expose this method before being
     # fitted.
     # Non-regression test for:
     # https://github.com/scikit-learn/scikit-learn/issues/19119
 
-    base_estimator = StackingClassifier(
+    estimator = StackingClassifier(
         estimators=[
             ("svc_1", SVC(probability=True)),
             ("svc_2", SVC(probability=True)),
@@ -296,12 +297,12 @@ def test_base_estimator_meta_estimator():
         cv=2,
     )
 
-    assert hasattr(base_estimator, "predict_proba")
-    clf = SelfTrainingClassifier(base_estimator=base_estimator)
+    assert hasattr(estimator, "predict_proba")
+    clf = SelfTrainingClassifier(estimator=estimator)
     clf.fit(X_train, y_train_missing_labels)
     clf.predict_proba(X_test)
 
-    base_estimator = StackingClassifier(
+    estimator = StackingClassifier(
         estimators=[
             ("svc_1", SVC(probability=False)),
             ("svc_2", SVC(probability=False)),
@@ -310,14 +311,14 @@ def test_base_estimator_meta_estimator():
         cv=2,
     )
 
-    assert not hasattr(base_estimator, "predict_proba")
-    clf = SelfTrainingClassifier(base_estimator=base_estimator)
+    assert not hasattr(estimator, "predict_proba")
+    clf = SelfTrainingClassifier(estimator=estimator)
     with pytest.raises(AttributeError):
         clf.fit(X_train, y_train_missing_labels)
 
 
 def test_self_training_estimator_attribute_error():
-    """Check that we raise the proper AttributeErrors when the `base_estimator`
+    """Check that we raise the proper AttributeErrors when the `estimator`
     does not implement the `predict_proba` method, which is called from within
     `fit`, or `decision_function`, which is decorated with `available_if`.
 
@@ -327,15 +328,15 @@ def test_self_training_estimator_attribute_error():
     # `SVC` with `probability=False` does not implement 'predict_proba' that
     # is required internally in `fit` of `SelfTrainingClassifier`. We expect
     # an AttributeError to be raised.
-    base_estimator = SVC(probability=False, gamma="scale")
-    self_training = SelfTrainingClassifier(base_estimator)
+    estimator = SVC(probability=False, gamma="scale")
+    self_training = SelfTrainingClassifier(estimator)
 
     with pytest.raises(AttributeError, match="has no attribute 'predict_proba'"):
         self_training.fit(X_train, y_train_missing_labels)
 
     # `DecisionTreeClassifier` does not implement 'decision_function' and
     # should raise an AttributeError
-    self_training = SelfTrainingClassifier(base_estimator=DecisionTreeClassifier())
+    self_training = SelfTrainingClassifier(estimator=DecisionTreeClassifier())
 
     outer_msg = "This 'SelfTrainingClassifier' has no attribute 'decision_function'"
     inner_msg = "'DecisionTreeClassifier' object has no attribute 'decision_function'"
@@ -343,3 +344,52 @@ def test_self_training_estimator_attribute_error():
         self_training.fit(X_train, y_train_missing_labels).decision_function(X_train)
     assert isinstance(exec_info.value.__cause__, AttributeError)
     assert inner_msg in str(exec_info.value.__cause__)
+
+
+# TODO(1.8): remove in 1.8
+def test_deprecation_warning_base_estimator():
+    warn_msg = "`base_estimator` has been deprecated in 1.6 and will be removed"
+    with pytest.warns(FutureWarning, match=warn_msg):
+        SelfTrainingClassifier(base_estimator=DecisionTreeClassifier()).fit(
+            X_train, y_train_missing_labels
+        )
+
+    error_msg = "You must pass an estimator to SelfTrainingClassifier"
+    with pytest.raises(ValueError, match=error_msg):
+        SelfTrainingClassifier().fit(X_train, y_train_missing_labels)
+
+    error_msg = "You must pass only one estimator to SelfTrainingClassifier."
+    with pytest.raises(ValueError, match=error_msg):
+        SelfTrainingClassifier(
+            base_estimator=DecisionTreeClassifier(), estimator=DecisionTreeClassifier()
+        ).fit(X_train, y_train_missing_labels)
+
+
+# Metadata routing tests
+# =================================================================
+
+
+@pytest.mark.filterwarnings("ignore:y contains no unlabeled samples:UserWarning")
+@pytest.mark.parametrize(
+    "method", ["decision_function", "predict_log_proba", "predict_proba", "predict"]
+)
+def test_routing_passed_metadata_not_supported(method):
+    """Test that the right error message is raised when metadata is passed while
+    not supported when `enable_metadata_routing=False`."""
+    est = SelfTrainingClassifier(estimator=SimpleEstimator())
+    with pytest.raises(
+        ValueError, match="is only supported if enable_metadata_routing=True"
+    ):
+        est.fit([[1], [1]], [1, 1], sample_weight=[1], prop="a")
+
+    est = SelfTrainingClassifier(estimator=SimpleEstimator())
+    with pytest.raises(
+        ValueError, match="is only supported if enable_metadata_routing=True"
+    ):
+        # make sure that the estimator thinks it is already fitted
+        est.fitted_params_ = True
+        getattr(est, method)([[1]], sample_weight=[1], prop="a")
+
+
+# End of routing tests
+# ====================
diff --git a/sklearn/tests/metadata_routing_common.py b/sklearn/tests/metadata_routing_common.py
index 0af522f9f9342..5fffec8fccecf 100644
--- a/sklearn/tests/metadata_routing_common.py
+++ b/sklearn/tests/metadata_routing_common.py
@@ -215,6 +215,17 @@ def predict(self, X):
         y_pred[len(X) // 2 :] = 1
         return y_pred
 
+    def predict_proba(self, X):
+        # dummy probabilities to support predict_proba
+        y_proba = np.empty(shape=(len(X), 2))
+        y_proba[: len(X) // 2, :] = np.asarray([1.0, 0.0])
+        y_proba[len(X) // 2 :, :] = np.asarray([0.0, 1.0])
+        return y_proba
+
+    def predict_log_proba(self, X):
+        # dummy probabilities to support predict_log_proba
+        return self.predict_proba(X)
+
 
 class NonConsumingRegressor(RegressorMixin, BaseEstimator):
     """A classifier which accepts no metadata on any method."""
@@ -291,13 +302,10 @@ def predict_proba(self, X, sample_weight="default", metadata="default"):
         return y_proba
 
     def predict_log_proba(self, X, sample_weight="default", metadata="default"):
-        pass  # pragma: no cover
-
-        # uncomment when needed
-        # record_metadata_not_default(
-        #     self, sample_weight=sample_weight, metadata=metadata
-        # )
-        # return np.zeros(shape=(len(X), 2))
+        record_metadata_not_default(
+            self, sample_weight=sample_weight, metadata=metadata
+        )
+        return np.zeros(shape=(len(X), 2))
 
     def decision_function(self, X, sample_weight="default", metadata="default"):
         record_metadata_not_default(
@@ -308,12 +316,11 @@ def decision_function(self, X, sample_weight="default", metadata="default"):
         y_score[: len(X) // 2] = 1
         return y_score
 
-    # uncomment when needed
-    # def score(self, X, y, sample_weight="default", metadata="default"):
-    # record_metadata_not_default(
-    #    self, sample_weight=sample_weight, metadata=metadata
-    # )
-    # return 1
+    def score(self, X, y, sample_weight="default", metadata="default"):
+        record_metadata_not_default(
+            self, sample_weight=sample_weight, metadata=metadata
+        )
+        return 1
 
 
 class ConsumingTransformer(TransformerMixin, BaseEstimator):
diff --git a/sklearn/tests/test_metaestimators_metadata_routing.py b/sklearn/tests/test_metaestimators_metadata_routing.py
index cf2bb130267a3..9aca241521ca0 100644
--- a/sklearn/tests/test_metaestimators_metadata_routing.py
+++ b/sklearn/tests/test_metaestimators_metadata_routing.py
@@ -390,6 +390,23 @@ def enable_slep006():
         "y": y,
         "estimator_routing_methods": ["fit", "predict"],
     },
+    {
+        "metaestimator": SelfTrainingClassifier,
+        "estimator_name": "estimator",
+        "estimator": "classifier",
+        "X": X,
+        "y": y,
+        "preserves_metadata": True,
+        "estimator_routing_methods": [
+            "fit",
+            "predict",
+            "predict_proba",
+            "predict_log_proba",
+            "decision_function",
+            "score",
+        ],
+        "method_mapping": {"fit": ["fit", "score"]},
+    },
 ]
 """List containing all metaestimators to be tested and their settings
 
@@ -433,7 +450,6 @@ def enable_slep006():
     AdaBoostRegressor(),
     RFE(ConsumingClassifier()),
     RFECV(ConsumingClassifier()),
-    SelfTrainingClassifier(ConsumingClassifier()),
     SequentialFeatureSelector(ConsumingClassifier()),
 ]
 
@@ -640,7 +656,7 @@ def test_error_on_missing_requests_for_sub_estimator(metaestimator):
                     value=None,
                 )
                 try:
-                    # `fit` and `partial_fit` accept y, others don't.
+                    # `fit`, `partial_fit`, 'score' accept y, others don't.
                     method(X, y, **method_kwargs)
                 except TypeError:
                     method(X, **method_kwargs)
diff --git a/sklearn/tests/test_pipeline.py b/sklearn/tests/test_pipeline.py
index 273aa4e9d36e4..b9fba86d01e9b 100644
--- a/sklearn/tests/test_pipeline.py
+++ b/sklearn/tests/test_pipeline.py
@@ -1822,8 +1822,8 @@ class SimpleEstimator(BaseEstimator):
     # This class is used in this section for testing routing in the pipeline.
     # This class should have every set_{method}_request
     def fit(self, X, y, sample_weight=None, prop=None):
-        assert sample_weight is not None
-        assert prop is not None
+        assert sample_weight is not None, sample_weight
+        assert prop is not None, prop
         return self
 
     def fit_transform(self, X, y, sample_weight=None, prop=None):

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA sklearn/semi_supervised/tests/test_self_training.py sklearn/tests/metadata_routing_common.py sklearn/tests/test_metaestimators_metadata_routing.py sklearn/tests/test_pipeline.py
: '>>>>> End Test Output'
git checkout ca7b42b4b7532ec4551dd5e35d699a143b939f19 sklearn/semi_supervised/tests/test_self_training.py sklearn/tests/metadata_routing_common.py sklearn/tests/test_metaestimators_metadata_routing.py sklearn/tests/test_pipeline.py
