#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff e25e8e2119ab6c5aa5072b05c0eb60b10aee4b05
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -v --no-build-isolation -e .
git checkout e25e8e2119ab6c5aa5072b05c0eb60b10aee4b05 sklearn/ensemble/_hist_gradient_boosting/tests/test_gradient_boosting.py sklearn/inspection/tests/test_permutation_importance.py sklearn/preprocessing/tests/test_discretization.py sklearn/preprocessing/tests/test_polynomial.py sklearn/preprocessing/tests/test_target_encoder.py sklearn/tests/test_docstring_parameters.py sklearn/utils/_test_common/instance_generator.py sklearn/utils/tests/test_indexing.py sklearn/utils/tests/test_stats.py
git apply -v - <<'EOF_114329324912'
diff --git a/sklearn/ensemble/_hist_gradient_boosting/tests/test_gradient_boosting.py b/sklearn/ensemble/_hist_gradient_boosting/tests/test_gradient_boosting.py
index 190251da92615..9a625ba7af76a 100644
--- a/sklearn/ensemble/_hist_gradient_boosting/tests/test_gradient_boosting.py
+++ b/sklearn/ensemble/_hist_gradient_boosting/tests/test_gradient_boosting.py
@@ -568,7 +568,9 @@ def make_missing_value_data(n_samples=int(1e4), seed=0):
         # Pre-bin the data to ensure a deterministic handling by the 2
         # strategies and also make it easier to insert np.nan in a structured
         # way:
-        X = KBinsDiscretizer(n_bins=42, encode="ordinal").fit_transform(X)
+        X = KBinsDiscretizer(
+            n_bins=42, encode="ordinal", quantile_method="averaged_inverted_cdf"
+        ).fit_transform(X)
 
         # First feature has missing values completely at random:
         rnd_mask = rng.rand(X.shape[0]) > 0.9
diff --git a/sklearn/inspection/tests/test_permutation_importance.py b/sklearn/inspection/tests/test_permutation_importance.py
index a0a9b21e5fc1f..b51ad7b71f66d 100644
--- a/sklearn/inspection/tests/test_permutation_importance.py
+++ b/sklearn/inspection/tests/test_permutation_importance.py
@@ -311,7 +311,11 @@ def test_permutation_importance_equivalence_array_dataframe(n_jobs, max_samples)
     X_df = pd.DataFrame(X)
 
     # Add a categorical feature that is statistically linked to y:
-    binner = KBinsDiscretizer(n_bins=3, encode="ordinal")
+    binner = KBinsDiscretizer(
+        n_bins=3,
+        encode="ordinal",
+        quantile_method="averaged_inverted_cdf",
+    )
     cat_column = binner.fit_transform(y.reshape(-1, 1))
 
     # Concatenate the extra column to the numpy array: integers will be
diff --git a/sklearn/preprocessing/tests/test_discretization.py b/sklearn/preprocessing/tests/test_discretization.py
index fd16a3db3efac..140e95e3e6f46 100644
--- a/sklearn/preprocessing/tests/test_discretization.py
+++ b/sklearn/preprocessing/tests/test_discretization.py
@@ -11,86 +11,116 @@
     assert_allclose_dense_sparse,
     assert_array_almost_equal,
     assert_array_equal,
+    ignore_warnings,
 )
+from sklearn.utils.fixes import np_version, parse_version
 
 X = [[-2, 1.5, -4, -1], [-1, 2.5, -3, -0.5], [0, 3.5, -2, 0.5], [1, 4.5, -1, 2]]
 
 
 @pytest.mark.parametrize(
-    "strategy, expected, sample_weight",
+    "strategy, quantile_method, expected, sample_weight",
     [
-        ("uniform", [[0, 0, 0, 0], [1, 1, 1, 0], [2, 2, 2, 1], [2, 2, 2, 2]], None),
-        ("kmeans", [[0, 0, 0, 0], [0, 0, 0, 0], [1, 1, 1, 1], [2, 2, 2, 2]], None),
-        ("quantile", [[0, 0, 0, 0], [1, 1, 1, 1], [2, 2, 2, 2], [2, 2, 2, 2]], None),
+        (
+            "uniform",
+            "warn",  # default, will not warn when strategy != "quantile"
+            [[0, 0, 0, 0], [1, 1, 1, 0], [2, 2, 2, 1], [2, 2, 2, 2]],
+            None,
+        ),
+        (
+            "kmeans",
+            "warn",  # default, will not warn when strategy != "quantile"
+            [[0, 0, 0, 0], [0, 0, 0, 0], [1, 1, 1, 1], [2, 2, 2, 2]],
+            None,
+        ),
         (
             "quantile",
+            "averaged_inverted_cdf",
             [[0, 0, 0, 0], [1, 1, 1, 1], [2, 2, 2, 2], [2, 2, 2, 2]],
+            None,
+        ),
+        (
+            "uniform",
+            "warn",  # default, will not warn when strategy != "quantile"
+            [[0, 0, 0, 0], [1, 1, 1, 0], [2, 2, 2, 1], [2, 2, 2, 2]],
             [1, 1, 2, 1],
         ),
+        (
+            "uniform",
+            "warn",  # default, will not warn when strategy != "quantile"
+            [[0, 0, 0, 0], [1, 1, 1, 0], [2, 2, 2, 1], [2, 2, 2, 2]],
+            [1, 1, 1, 1],
+        ),
         (
             "quantile",
+            "averaged_inverted_cdf",
+            [[0, 0, 0, 0], [1, 1, 1, 1], [2, 2, 2, 2], [2, 2, 2, 2]],
+            [1, 1, 2, 1],
+        ),
+        (
+            "quantile",
+            "averaged_inverted_cdf",
             [[0, 0, 0, 0], [1, 1, 1, 1], [2, 2, 2, 2], [2, 2, 2, 2]],
             [1, 1, 1, 1],
         ),
         (
             "quantile",
-            [[0, 0, 0, 0], [0, 0, 0, 0], [1, 1, 1, 1], [1, 1, 1, 1]],
+            "averaged_inverted_cdf",
+            [[0, 0, 0, 0], [0, 0, 0, 0], [1, 1, 1, 1], [2, 2, 2, 2]],
             [0, 1, 1, 1],
         ),
         (
             "kmeans",
+            "warn",  # default, will not warn when strategy != "quantile"
             [[0, 0, 0, 0], [1, 1, 1, 0], [1, 1, 1, 1], [2, 2, 2, 2]],
             [1, 0, 3, 1],
         ),
         (
             "kmeans",
+            "warn",  # default, will not warn when strategy != "quantile"
             [[0, 0, 0, 0], [0, 0, 0, 0], [1, 1, 1, 1], [2, 2, 2, 2]],
             [1, 1, 1, 1],
         ),
     ],
 )
-def test_fit_transform(strategy, expected, sample_weight):
-    est = KBinsDiscretizer(n_bins=3, encode="ordinal", strategy=strategy)
-    est.fit(X, sample_weight=sample_weight)
-    assert_array_equal(expected, est.transform(X))
+def test_fit_transform(strategy, quantile_method, expected, sample_weight):
+    est = KBinsDiscretizer(
+        n_bins=3, encode="ordinal", strategy=strategy, quantile_method=quantile_method
+    )
+    with ignore_warnings(category=UserWarning):
+        # Ignore the warning on removed small bins.
+        est.fit(X, sample_weight=sample_weight)
+    assert_array_equal(est.transform(X), expected)
 
 
 def test_valid_n_bins():
-    KBinsDiscretizer(n_bins=2).fit_transform(X)
-    KBinsDiscretizer(n_bins=np.array([2])[0]).fit_transform(X)
-    assert KBinsDiscretizer(n_bins=2).fit(X).n_bins_.dtype == np.dtype(int)
-
-
-@pytest.mark.parametrize("strategy", ["uniform"])
-def test_kbinsdiscretizer_wrong_strategy_with_weights(strategy):
-    """Check that we raise an error when the wrong strategy is used."""
-    sample_weight = np.ones(shape=(len(X)))
-    est = KBinsDiscretizer(n_bins=3, strategy=strategy)
-    err_msg = (
-        "`sample_weight` was provided but it cannot be used with strategy='uniform'."
-    )
-    with pytest.raises(ValueError, match=err_msg):
-        est.fit(X, sample_weight=sample_weight)
+    KBinsDiscretizer(n_bins=2, quantile_method="averaged_inverted_cdf").fit_transform(X)
+    KBinsDiscretizer(
+        n_bins=np.array([2])[0], quantile_method="averaged_inverted_cdf"
+    ).fit_transform(X)
+    assert KBinsDiscretizer(n_bins=2, quantile_method="averaged_inverted_cdf").fit(
+        X
+    ).n_bins_.dtype == np.dtype(int)
 
 
 def test_invalid_n_bins_array():
     # Bad shape
     n_bins = np.full((2, 4), 2.0)
-    est = KBinsDiscretizer(n_bins=n_bins)
+    est = KBinsDiscretizer(n_bins=n_bins, quantile_method="averaged_inverted_cdf")
     err_msg = r"n_bins must be a scalar or array of shape \(n_features,\)."
     with pytest.raises(ValueError, match=err_msg):
         est.fit_transform(X)
 
     # Incorrect number of features
     n_bins = [1, 2, 2]
-    est = KBinsDiscretizer(n_bins=n_bins)
+    est = KBinsDiscretizer(n_bins=n_bins, quantile_method="averaged_inverted_cdf")
     err_msg = r"n_bins must be a scalar or array of shape \(n_features,\)."
     with pytest.raises(ValueError, match=err_msg):
         est.fit_transform(X)
 
     # Bad bin values
     n_bins = [1, 2, 2, 1]
-    est = KBinsDiscretizer(n_bins=n_bins)
+    est = KBinsDiscretizer(n_bins=n_bins, quantile_method="averaged_inverted_cdf")
     err_msg = (
         "KBinsDiscretizer received an invalid number of bins "
         "at indices 0, 3. Number of bins must be at least 2, "
@@ -101,7 +131,7 @@ def test_invalid_n_bins_array():
 
     # Float bin values
     n_bins = [2.1, 2, 2.1, 2]
-    est = KBinsDiscretizer(n_bins=n_bins)
+    est = KBinsDiscretizer(n_bins=n_bins, quantile_method="averaged_inverted_cdf")
     err_msg = (
         "KBinsDiscretizer received an invalid number of bins "
         "at indices 0, 2. Number of bins must be at least 2, "
@@ -112,46 +142,66 @@ def test_invalid_n_bins_array():
 
 
 @pytest.mark.parametrize(
-    "strategy, expected, sample_weight",
+    "strategy, quantile_method, expected, sample_weight",
     [
-        ("uniform", [[0, 0, 0, 0], [0, 1, 1, 0], [1, 2, 2, 1], [1, 2, 2, 2]], None),
-        ("kmeans", [[0, 0, 0, 0], [0, 0, 0, 0], [1, 1, 1, 1], [1, 2, 2, 2]], None),
-        ("quantile", [[0, 0, 0, 0], [0, 1, 1, 1], [1, 2, 2, 2], [1, 2, 2, 2]], None),
+        (
+            "uniform",
+            "warn",  # default, will not warn when strategy != "quantile"
+            [[0, 0, 0, 0], [0, 1, 1, 0], [1, 2, 2, 1], [1, 2, 2, 2]],
+            None,
+        ),
+        (
+            "kmeans",
+            "warn",  # default, will not warn when strategy != "quantile"
+            [[0, 0, 0, 0], [0, 0, 0, 0], [1, 1, 1, 1], [1, 2, 2, 2]],
+            None,
+        ),
         (
             "quantile",
+            "linear",
             [[0, 0, 0, 0], [0, 1, 1, 1], [1, 2, 2, 2], [1, 2, 2, 2]],
-            [1, 1, 3, 1],
+            None,
+        ),
+        (
+            "quantile",
+            "averaged_inverted_cdf",
+            [[0, 0, 0, 0], [0, 1, 1, 1], [1, 2, 2, 2], [1, 2, 2, 2]],
+            None,
+        ),
+        (
+            "quantile",
+            "averaged_inverted_cdf",
+            [[0, 0, 0, 0], [0, 1, 1, 1], [1, 2, 2, 2], [1, 2, 2, 2]],
+            [1, 1, 1, 1],
         ),
         (
             "quantile",
+            "averaged_inverted_cdf",
             [[0, 0, 0, 0], [0, 0, 0, 0], [1, 1, 1, 1], [1, 1, 1, 1]],
             [0, 1, 3, 1],
         ),
-        # (
-        #     "quantile",
-        #     [[0, 0, 0, 0], [0, 1, 1, 1], [1, 2, 2, 2], [1, 2, 2, 2]],
-        #     [1, 1, 1, 1],
-        # ),
-        #
-        # TODO: This test case above aims to test if the case where an array of
-        #       ones passed in sample_weight parameter is equal to the case when
-        #       sample_weight is None.
-        #       Unfortunately, the behavior of `_weighted_percentile` when
-        #       `sample_weight = [1, 1, 1, 1]` are currently not equivalent.
-        #       This problem has been addressed in issue :
-        #       https://github.com/scikit-learn/scikit-learn/issues/17370
+        (
+            "quantile",
+            "averaged_inverted_cdf",
+            [[0, 0, 0, 0], [0, 0, 0, 0], [1, 2, 2, 2], [1, 2, 2, 2]],
+            [1, 1, 3, 1],
+        ),
         (
             "kmeans",
+            "warn",  # default, will not warn when strategy != "quantile"
             [[0, 0, 0, 0], [0, 1, 1, 0], [1, 1, 1, 1], [1, 2, 2, 2]],
             [1, 0, 3, 1],
         ),
     ],
 )
-def test_fit_transform_n_bins_array(strategy, expected, sample_weight):
+def test_fit_transform_n_bins_array(strategy, quantile_method, expected, sample_weight):
     est = KBinsDiscretizer(
-        n_bins=[2, 3, 3, 3], encode="ordinal", strategy=strategy
+        n_bins=[2, 3, 3, 3],
+        encode="ordinal",
+        strategy=strategy,
+        quantile_method=quantile_method,
     ).fit(X, sample_weight=sample_weight)
-    assert_array_equal(expected, est.transform(X))
+    assert_array_equal(est.transform(X), expected)
 
     # test the shape of bin_edges_
     n_features = np.array(X).shape[1]
@@ -166,16 +216,30 @@ def test_kbinsdiscretizer_effect_sample_weight():
     X = np.array([[-2], [-1], [1], [3], [500], [1000]])
     # add a large number of bins such that each sample with a non-null weight
     # will be used as bin edge
-    est = KBinsDiscretizer(n_bins=10, encode="ordinal", strategy="quantile")
+    est = KBinsDiscretizer(
+        n_bins=10,
+        encode="ordinal",
+        strategy="quantile",
+        quantile_method="averaged_inverted_cdf",
+    )
     est.fit(X, sample_weight=[1, 1, 1, 1, 0, 0])
-    assert_allclose(est.bin_edges_[0], [-2, -1, 1, 3])
-    assert_allclose(est.transform(X), [[0.0], [1.0], [2.0], [2.0], [2.0], [2.0]])
+    assert_allclose(est.bin_edges_[0], [-2, -1, 0, 1, 3])
+    assert_allclose(est.transform(X), [[0.0], [1.0], [3.0], [3.0], [3.0], [3.0]])
 
 
 @pytest.mark.parametrize("strategy", ["kmeans", "quantile"])
 def test_kbinsdiscretizer_no_mutating_sample_weight(strategy):
     """Make sure that `sample_weight` is not changed in place."""
-    est = KBinsDiscretizer(n_bins=3, encode="ordinal", strategy=strategy)
+
+    if strategy == "quantile":
+        est = KBinsDiscretizer(
+            n_bins=3,
+            encode="ordinal",
+            strategy=strategy,
+            quantile_method="averaged_inverted_cdf",
+        )
+    else:
+        est = KBinsDiscretizer(n_bins=3, encode="ordinal", strategy=strategy)
     sample_weight = np.array([1, 3, 1, 2], dtype=np.float64)
     sample_weight_copy = np.copy(sample_weight)
     est.fit(X, sample_weight=sample_weight)
@@ -186,7 +250,15 @@ def test_kbinsdiscretizer_no_mutating_sample_weight(strategy):
 def test_same_min_max(strategy):
     warnings.simplefilter("always")
     X = np.array([[1, -2], [1, -1], [1, 0], [1, 1]])
-    est = KBinsDiscretizer(strategy=strategy, n_bins=3, encode="ordinal")
+    if strategy == "quantile":
+        est = KBinsDiscretizer(
+            strategy=strategy,
+            n_bins=3,
+            encode="ordinal",
+            quantile_method="averaged_inverted_cdf",
+        )
+    else:
+        est = KBinsDiscretizer(strategy=strategy, n_bins=3, encode="ordinal")
     warning_message = "Feature 0 is constant and will be replaced with 0."
     with pytest.warns(UserWarning, match=warning_message):
         est.fit(X)
@@ -198,11 +270,11 @@ def test_same_min_max(strategy):
 
 def test_transform_1d_behavior():
     X = np.arange(4)
-    est = KBinsDiscretizer(n_bins=2)
+    est = KBinsDiscretizer(n_bins=2, quantile_method="averaged_inverted_cdf")
     with pytest.raises(ValueError):
         est.fit(X)
 
-    est = KBinsDiscretizer(n_bins=2)
+    est = KBinsDiscretizer(n_bins=2, quantile_method="averaged_inverted_cdf")
     est.fit(X.reshape(-1, 1))
     with pytest.raises(ValueError):
         est.transform(X)
@@ -215,14 +287,22 @@ def test_numeric_stability(i):
 
     # Test up to discretizing nano units
     X = X_init / 10**i
-    Xt = KBinsDiscretizer(n_bins=2, encode="ordinal").fit_transform(X)
+    Xt = KBinsDiscretizer(
+        n_bins=2, encode="ordinal", quantile_method="averaged_inverted_cdf"
+    ).fit_transform(X)
     assert_array_equal(Xt_expected, Xt)
 
 
 def test_encode_options():
-    est = KBinsDiscretizer(n_bins=[2, 3, 3, 3], encode="ordinal").fit(X)
+    est = KBinsDiscretizer(
+        n_bins=[2, 3, 3, 3], encode="ordinal", quantile_method="averaged_inverted_cdf"
+    ).fit(X)
     Xt_1 = est.transform(X)
-    est = KBinsDiscretizer(n_bins=[2, 3, 3, 3], encode="onehot-dense").fit(X)
+    est = KBinsDiscretizer(
+        n_bins=[2, 3, 3, 3],
+        encode="onehot-dense",
+        quantile_method="averaged_inverted_cdf",
+    ).fit(X)
     Xt_2 = est.transform(X)
     assert not sp.issparse(Xt_2)
     assert_array_equal(
@@ -231,7 +311,9 @@ def test_encode_options():
         ).fit_transform(Xt_1),
         Xt_2,
     )
-    est = KBinsDiscretizer(n_bins=[2, 3, 3, 3], encode="onehot").fit(X)
+    est = KBinsDiscretizer(
+        n_bins=[2, 3, 3, 3], encode="onehot", quantile_method="averaged_inverted_cdf"
+    ).fit(X)
     Xt_3 = est.transform(X)
     assert sp.issparse(Xt_3)
     assert_array_equal(
@@ -245,36 +327,48 @@ def test_encode_options():
 
 
 @pytest.mark.parametrize(
-    "strategy, expected_2bins, expected_3bins, expected_5bins",
+    "strategy, quantile_method, expected_2bins, expected_3bins, expected_5bins",
     [
-        ("uniform", [0, 0, 0, 0, 1, 1], [0, 0, 0, 0, 2, 2], [0, 0, 1, 1, 4, 4]),
-        ("kmeans", [0, 0, 0, 0, 1, 1], [0, 0, 1, 1, 2, 2], [0, 0, 1, 2, 3, 4]),
-        ("quantile", [0, 0, 0, 1, 1, 1], [0, 0, 1, 1, 2, 2], [0, 1, 2, 3, 4, 4]),
+        ("uniform", "warn", [0, 0, 0, 0, 1, 1], [0, 0, 0, 0, 2, 2], [0, 0, 1, 1, 4, 4]),
+        ("kmeans", "warn", [0, 0, 0, 0, 1, 1], [0, 0, 1, 1, 2, 2], [0, 0, 1, 2, 3, 4]),
+        (
+            "quantile",
+            "averaged_inverted_cdf",
+            [0, 0, 0, 1, 1, 1],
+            [0, 0, 1, 1, 2, 2],
+            [0, 1, 2, 3, 4, 4],
+        ),
     ],
 )
 def test_nonuniform_strategies(
-    strategy, expected_2bins, expected_3bins, expected_5bins
+    strategy, quantile_method, expected_2bins, expected_3bins, expected_5bins
 ):
     X = np.array([0, 0.5, 2, 3, 9, 10]).reshape(-1, 1)
 
     # with 2 bins
-    est = KBinsDiscretizer(n_bins=2, strategy=strategy, encode="ordinal")
+    est = KBinsDiscretizer(
+        n_bins=2, strategy=strategy, quantile_method=quantile_method, encode="ordinal"
+    )
     Xt = est.fit_transform(X)
     assert_array_equal(expected_2bins, Xt.ravel())
 
     # with 3 bins
-    est = KBinsDiscretizer(n_bins=3, strategy=strategy, encode="ordinal")
+    est = KBinsDiscretizer(
+        n_bins=3, strategy=strategy, quantile_method=quantile_method, encode="ordinal"
+    )
     Xt = est.fit_transform(X)
     assert_array_equal(expected_3bins, Xt.ravel())
 
     # with 5 bins
-    est = KBinsDiscretizer(n_bins=5, strategy=strategy, encode="ordinal")
+    est = KBinsDiscretizer(
+        n_bins=5, strategy=strategy, quantile_method=quantile_method, encode="ordinal"
+    )
     Xt = est.fit_transform(X)
     assert_array_equal(expected_5bins, Xt.ravel())
 
 
 @pytest.mark.parametrize(
-    "strategy, expected_inv",
+    "strategy, expected_inv,quantile_method",
     [
         (
             "uniform",
@@ -284,6 +378,7 @@ def test_nonuniform_strategies(
                 [0.5, 4.0, -1.5, 0.5],
                 [0.5, 4.0, -1.5, 1.5],
             ],
+            "warn",  # default, will not warn when strategy != "quantile"
         ),
         (
             "kmeans",
@@ -293,6 +388,7 @@ def test_nonuniform_strategies(
                 [-0.125, 3.375, -2.125, 0.5625],
                 [0.75, 4.25, -1.25, 1.625],
             ],
+            "warn",  # default, will not warn when strategy != "quantile"
         ),
         (
             "quantile",
@@ -302,12 +398,15 @@ def test_nonuniform_strategies(
                 [0.5, 4.0, -1.5, 1.25],
                 [0.5, 4.0, -1.5, 1.25],
             ],
+            "averaged_inverted_cdf",
         ),
     ],
 )
 @pytest.mark.parametrize("encode", ["ordinal", "onehot", "onehot-dense"])
-def test_inverse_transform(strategy, encode, expected_inv):
-    kbd = KBinsDiscretizer(n_bins=3, strategy=strategy, encode=encode)
+def test_inverse_transform(strategy, encode, expected_inv, quantile_method):
+    kbd = KBinsDiscretizer(
+        n_bins=3, strategy=strategy, quantile_method=quantile_method, encode=encode
+    )
     Xt = kbd.fit_transform(X)
     Xinv = kbd.inverse_transform(Xt)
     assert_array_almost_equal(expected_inv, Xinv)
@@ -316,7 +415,16 @@ def test_inverse_transform(strategy, encode, expected_inv):
 @pytest.mark.parametrize("strategy", ["uniform", "kmeans", "quantile"])
 def test_transform_outside_fit_range(strategy):
     X = np.array([0, 1, 2, 3])[:, None]
-    kbd = KBinsDiscretizer(n_bins=4, strategy=strategy, encode="ordinal")
+
+    if strategy == "quantile":
+        kbd = KBinsDiscretizer(
+            n_bins=4,
+            strategy=strategy,
+            encode="ordinal",
+            quantile_method="averaged_inverted_cdf",
+        )
+    else:
+        kbd = KBinsDiscretizer(n_bins=4, strategy=strategy, encode="ordinal")
     kbd.fit(X)
 
     X2 = np.array([-2, 5])[:, None]
@@ -329,7 +437,9 @@ def test_overwrite():
     X = np.array([0, 1, 2, 3])[:, None]
     X_before = X.copy()
 
-    est = KBinsDiscretizer(n_bins=3, encode="ordinal")
+    est = KBinsDiscretizer(
+        n_bins=3, quantile_method="averaged_inverted_cdf", encode="ordinal"
+    )
     Xt = est.fit_transform(X)
     assert_array_equal(X, X_before)
 
@@ -340,14 +450,21 @@ def test_overwrite():
 
 
 @pytest.mark.parametrize(
-    "strategy, expected_bin_edges", [("quantile", [0, 1, 3]), ("kmeans", [0, 1.5, 3])]
+    "strategy, expected_bin_edges, quantile_method",
+    [
+        ("quantile", [0, 1.5, 3], "averaged_inverted_cdf"),
+        ("kmeans", [0, 1.5, 3], "warn"),
+    ],
 )
-def test_redundant_bins(strategy, expected_bin_edges):
+def test_redundant_bins(strategy, expected_bin_edges, quantile_method):
     X = [[0], [0], [0], [0], [3], [3]]
-    kbd = KBinsDiscretizer(n_bins=3, strategy=strategy, subsample=None)
+    kbd = KBinsDiscretizer(
+        n_bins=3, strategy=strategy, quantile_method=quantile_method, subsample=None
+    )
     warning_message = "Consider decreasing the number of bins."
     with pytest.warns(UserWarning, match=warning_message):
         kbd.fit(X)
+
     assert_array_almost_equal(kbd.bin_edges_[0], expected_bin_edges)
 
 
@@ -355,7 +472,15 @@ def test_percentile_numeric_stability():
     X = np.array([0.05, 0.05, 0.95]).reshape(-1, 1)
     bin_edges = np.array([0.05, 0.23, 0.41, 0.59, 0.77, 0.95])
     Xt = np.array([0, 0, 4]).reshape(-1, 1)
-    kbd = KBinsDiscretizer(n_bins=10, encode="ordinal", strategy="quantile")
+    kbd = KBinsDiscretizer(
+        n_bins=10,
+        encode="ordinal",
+        strategy="quantile",
+        quantile_method="linear",
+    )
+    ## TODO: change to averaged inverted cdf, but that means we only get bin
+    ## edges of 0.05 and 0.95 and nothing in between
+
     warning_message = "Consider decreasing the number of bins."
     with pytest.warns(UserWarning, match=warning_message):
         kbd.fit(X)
@@ -369,7 +494,12 @@ def test_percentile_numeric_stability():
 @pytest.mark.parametrize("encode", ["ordinal", "onehot", "onehot-dense"])
 def test_consistent_dtype(in_dtype, out_dtype, encode):
     X_input = np.array(X, dtype=in_dtype)
-    kbd = KBinsDiscretizer(n_bins=3, encode=encode, dtype=out_dtype)
+    kbd = KBinsDiscretizer(
+        n_bins=3,
+        encode=encode,
+        quantile_method="averaged_inverted_cdf",
+        dtype=out_dtype,
+    )
     kbd.fit(X_input)
 
     # test output dtype
@@ -392,12 +522,22 @@ def test_32_equal_64(input_dtype, encode):
     X_input = np.array(X, dtype=input_dtype)
 
     # 32 bit output
-    kbd_32 = KBinsDiscretizer(n_bins=3, encode=encode, dtype=np.float32)
+    kbd_32 = KBinsDiscretizer(
+        n_bins=3,
+        encode=encode,
+        quantile_method="averaged_inverted_cdf",
+        dtype=np.float32,
+    )
     kbd_32.fit(X_input)
     Xt_32 = kbd_32.transform(X_input)
 
     # 64 bit output
-    kbd_64 = KBinsDiscretizer(n_bins=3, encode=encode, dtype=np.float64)
+    kbd_64 = KBinsDiscretizer(
+        n_bins=3,
+        encode=encode,
+        quantile_method="averaged_inverted_cdf",
+        dtype=np.float64,
+    )
     kbd_64.fit(X_input)
     Xt_64 = kbd_64.transform(X_input)
 
@@ -407,7 +547,12 @@ def test_32_equal_64(input_dtype, encode):
 def test_kbinsdiscretizer_subsample_default():
     # Since the size of X is small (< 2e5), subsampling will not take place.
     X = np.array([-2, 1.5, -4, -1]).reshape(-1, 1)
-    kbd_default = KBinsDiscretizer(n_bins=10, encode="ordinal", strategy="quantile")
+    kbd_default = KBinsDiscretizer(
+        n_bins=10,
+        encode="ordinal",
+        strategy="quantile",
+        quantile_method="averaged_inverted_cdf",
+    )
     kbd_default.fit(X)
 
     kbd_without_subsampling = clone(kbd_default)
@@ -449,7 +594,9 @@ def test_kbinsdiscrtizer_get_feature_names_out(encode, expected_names):
     """
     X = [[-2, 1, -4], [-1, 2, -3], [0, 3, -2], [1, 4, -1]]
 
-    kbd = KBinsDiscretizer(n_bins=4, encode=encode).fit(X)
+    kbd = KBinsDiscretizer(
+        n_bins=4, encode=encode, quantile_method="averaged_inverted_cdf"
+    ).fit(X)
     Xt = kbd.transform(X)
 
     input_features = [f"feat{i}" for i in range(3)]
@@ -464,9 +611,17 @@ def test_kbinsdiscretizer_subsample(strategy, global_random_seed):
     # Check that the bin edges are almost the same when subsampling is used.
     X = np.random.RandomState(global_random_seed).random_sample((100000, 1)) + 1
 
-    kbd_subsampling = KBinsDiscretizer(
-        strategy=strategy, subsample=50000, random_state=global_random_seed
-    )
+    if strategy == "quantile":
+        kbd_subsampling = KBinsDiscretizer(
+            strategy=strategy,
+            subsample=50000,
+            random_state=global_random_seed,
+            quantile_method="averaged_inverted_cdf",
+        )
+    else:
+        kbd_subsampling = KBinsDiscretizer(
+            strategy=strategy, subsample=50000, random_state=global_random_seed
+        )
     kbd_subsampling.fit(X)
 
     kbd_no_subsampling = clone(kbd_subsampling)
@@ -480,10 +635,45 @@ def test_kbinsdiscretizer_subsample(strategy, global_random_seed):
     )
 
 
+def test_quantile_method_future_warnings():
+    X = [[-2, 1, -4], [-1, 2, -3], [0, 3, -2], [1, 4, -1]]
+    with pytest.warns(
+        FutureWarning,
+        match="The current default behavior, quantile_method='linear', will be "
+        "changed to quantile_method='averaged_inverted_cdf' in "
+        "scikit-learn version 1.9 to naturally support sample weight "
+        "equivalence properties by default. Pass "
+        "quantile_method='averaged_inverted_cdf' explicitly to silence this "
+        "warning.",
+    ):
+        KBinsDiscretizer(strategy="quantile").fit(X)
+
+
+def test_invalid_quantile_method_with_sample_weight():
+    X = [[-2, 1, -4], [-1, 2, -3], [0, 3, -2], [1, 4, -1]]
+    expected_msg = (
+        "When fitting with strategy='quantile' and sample weights, "
+        "quantile_method should either be set to 'averaged_inverted_cdf' or "
+        "'inverted_cdf', got quantile_method='linear' instead."
+    )
+    with pytest.raises(
+        ValueError,
+        match=expected_msg,
+    ):
+        KBinsDiscretizer(strategy="quantile", quantile_method="linear").fit(
+            X,
+            sample_weight=[1, 1, 2, 2],
+        )
+
+
 # TODO(1.7): remove this test
-def test_KBD_inverse_transform_Xt_deprecation():
+@pytest.mark.parametrize(
+    "strategy, quantile_method",
+    [("uniform", "warn"), ("quantile", "averaged_inverted_cdf"), ("kmeans", "warn")],
+)
+def test_KBD_inverse_transform_Xt_deprecation(strategy, quantile_method):
     X = np.arange(10)[:, None]
-    kbd = KBinsDiscretizer()
+    kbd = KBinsDiscretizer(strategy=strategy, quantile_method=quantile_method)
     X = kbd.fit_transform(X)
 
     with pytest.raises(TypeError, match="Missing required positional argument"):
@@ -498,3 +688,18 @@ def test_KBD_inverse_transform_Xt_deprecation():
 
     with pytest.warns(FutureWarning, match="Xt was renamed X in version 1.5"):
         kbd.inverse_transform(Xt=X)
+
+
+# TODO: remove this test when numpy min version >= 1.22
+@pytest.mark.skipif(
+    condition=np_version >= parse_version("1.22"),
+    reason="newer numpy versions do support the 'method' parameter",
+)
+def test_invalid_quantile_method_on_old_numpy():
+    expected_msg = (
+        "quantile_method='closest_observation' is not supported with numpy < 1.22"
+    )
+    with pytest.raises(ValueError, match=expected_msg):
+        KBinsDiscretizer(
+            quantile_method="closest_observation", strategy="quantile"
+        ).fit(X)
diff --git a/sklearn/preprocessing/tests/test_polynomial.py b/sklearn/preprocessing/tests/test_polynomial.py
index a339d2793c02c..6e55824e4a2c8 100644
--- a/sklearn/preprocessing/tests/test_polynomial.py
+++ b/sklearn/preprocessing/tests/test_polynomial.py
@@ -386,7 +386,12 @@ def test_spline_transformer_kbindiscretizer(global_random_seed):
     )
     splines = splt.fit_transform(X)
 
-    kbd = KBinsDiscretizer(n_bins=n_bins, encode="onehot-dense", strategy="quantile")
+    kbd = KBinsDiscretizer(
+        n_bins=n_bins,
+        encode="onehot-dense",
+        strategy="quantile",
+        quantile_method="averaged_inverted_cdf",
+    )
     kbins = kbd.fit_transform(X)
 
     # Though they should be exactly equal, we test approximately with high
diff --git a/sklearn/preprocessing/tests/test_target_encoder.py b/sklearn/preprocessing/tests/test_target_encoder.py
index c1e707b9bff98..536f2e031bf77 100644
--- a/sklearn/preprocessing/tests/test_target_encoder.py
+++ b/sklearn/preprocessing/tests/test_target_encoder.py
@@ -561,9 +561,9 @@ def test_invariance_of_encoding_under_label_permutation(smooth, global_random_se
     # using smoothing.
     y = rng.normal(size=1000)
     n_categories = 30
-    X = KBinsDiscretizer(n_bins=n_categories, encode="ordinal").fit_transform(
-        y.reshape(-1, 1)
-    )
+    X = KBinsDiscretizer(
+        n_bins=n_categories, quantile_method="averaged_inverted_cdf", encode="ordinal"
+    ).fit_transform(y.reshape(-1, 1))
 
     X_train, X_test, y_train, y_test = train_test_split(
         X, y, random_state=global_random_seed
diff --git a/sklearn/tests/test_docstring_parameters.py b/sklearn/tests/test_docstring_parameters.py
index 56ed0a33f656d..4490c59758650 100644
--- a/sklearn/tests/test_docstring_parameters.py
+++ b/sklearn/tests/test_docstring_parameters.py
@@ -224,6 +224,10 @@ def test_fit_docstring_attributes(name, Estimator):
     elif Estimator.__name__ == "TSNE":
         # default raises an error, perplexity must be less than n_samples
         est.set_params(perplexity=2)
+    # TODO(1.9) remove
+    elif Estimator.__name__ == "KBinsDiscretizer":
+        # default raises an FutureWarning if quantile method is at default "warn"
+        est.set_params(quantile_method="averaged_inverted_cdf")
 
     # Low max iter to speed up tests: we are only interested in checking the existence
     # of fitted attributes. This should be invariant to whether it has converged or not.
diff --git a/sklearn/utils/_test_common/instance_generator.py b/sklearn/utils/_test_common/instance_generator.py
index efcf06140f3f8..d26c79d0eaef3 100644
--- a/sklearn/utils/_test_common/instance_generator.py
+++ b/sklearn/utils/_test_common/instance_generator.py
@@ -563,6 +563,37 @@
     IncrementalPCA: {"check_dict_unchanged": dict(batch_size=10, n_components=1)},
     Isomap: {"check_dict_unchanged": dict(n_components=1)},
     KMeans: {"check_dict_unchanged": dict(max_iter=5, n_clusters=1, n_init=2)},
+    # TODO(1.9) simplify when averaged_inverted_cdf is the default
+    KBinsDiscretizer: {
+        "check_sample_weight_equivalence_on_dense_data": [
+            # Using subsample != None leads to a stochastic fit that is not
+            # handled by the check_sample_weight_equivalence_on_dense_data test.
+            dict(strategy="quantile", subsample=None, quantile_method="inverted_cdf"),
+            dict(
+                strategy="quantile",
+                subsample=None,
+                quantile_method="averaged_inverted_cdf",
+            ),
+            dict(strategy="uniform", subsample=None),
+            # The "kmeans" strategy leads to a stochastic fit that is not
+            # handled by the check_sample_weight_equivalence test.
+        ],
+        "check_sample_weights_list": dict(
+            strategy="quantile", quantile_method="averaged_inverted_cdf"
+        ),
+        "check_sample_weights_pandas_series": dict(
+            strategy="quantile", quantile_method="averaged_inverted_cdf"
+        ),
+        "check_sample_weights_shape": dict(
+            strategy="quantile", quantile_method="averaged_inverted_cdf"
+        ),
+        "check_sample_weights_not_an_array": dict(
+            strategy="quantile", quantile_method="averaged_inverted_cdf"
+        ),
+        "check_sample_weights_not_overwritten": dict(
+            strategy="quantile", quantile_method="averaged_inverted_cdf"
+        ),
+    },
     KernelPCA: {"check_dict_unchanged": dict(n_components=1)},
     LassoLars: {"check_non_transformer_estimators_n_iter": dict(alpha=0.0)},
     LatentDirichletAllocation: {
@@ -959,15 +990,6 @@ def _yield_instances_for_check(check, estimator_orig):
             "sample_weight is not equivalent to removing/repeating samples."
         ),
     },
-    KBinsDiscretizer: {
-        # TODO: fix sample_weight handling of this estimator, see meta-issue #16298
-        "check_sample_weight_equivalence_on_dense_data": (
-            "sample_weight is not equivalent to removing/repeating samples."
-        ),
-        "check_sample_weight_equivalence_on_sparse_data": (
-            "sample_weight is not equivalent to removing/repeating samples."
-        ),
-    },
     KernelDensity: {
         "check_sample_weight_equivalence_on_dense_data": (
             "sample_weight must have positive values"
diff --git a/sklearn/utils/tests/test_indexing.py b/sklearn/utils/tests/test_indexing.py
index c2cdf24817cac..fa54c58413a3f 100644
--- a/sklearn/utils/tests/test_indexing.py
+++ b/sklearn/utils/tests/test_indexing.py
@@ -4,6 +4,7 @@
 
 import numpy as np
 import pytest
+from scipy.stats import kstest
 
 import sklearn
 from sklearn.externals._packaging.version import parse as parse_version
@@ -495,6 +496,46 @@ def test_resample():
     assert len(resample([1, 2], n_samples=5)) == 5
 
 
+def test_resample_weighted():
+    # Check that sampling with replacement with integer weights yields the
+    # samples from the same distribution as sampling uniformly with
+    # repeated data points.
+    data = np.array([-1, 0, 1])
+    sample_weight = np.asarray([0, 100, 1])
+
+    mean_repeated = []
+    mean_reweighted = []
+
+    for seed in range(100):
+        mean_repeated.append(
+            resample(
+                data.repeat(sample_weight),
+                replace=True,
+                random_state=seed,
+                n_samples=data.shape[0],
+            ).mean()
+        )
+        mean_reweighted.append(
+            resample(
+                data,
+                sample_weight=sample_weight,
+                replace=True,
+                random_state=seed,
+                n_samples=data.shape[0],
+            ).mean()
+        )
+
+    mean_repeated = np.asarray(mean_repeated)
+    mean_reweighted = np.asarray(mean_reweighted)
+
+    test_result = kstest(mean_repeated, mean_reweighted)
+    # Should never be negative because -1 has a 0 weight.
+    assert np.all(mean_reweighted >= 0)
+    # The null-hypothesis (the computed means are identically distributed)
+    # cannot be rejected.
+    assert test_result.pvalue > 0.05
+
+
 def test_resample_stratified():
     # Make sure resample can stratify
     rng = np.random.RandomState(0)
@@ -546,6 +587,21 @@ def test_resample_stratify_2dy():
     assert y.ndim == 2
 
 
+def test_notimplementederror():
+
+    with pytest.raises(
+        NotImplementedError,
+        match="Resampling with sample_weight is only implemented for replace=True.",
+    ):
+        resample([0, 1], [0, 1], sample_weight=[1, 1], replace=False)
+
+    with pytest.raises(
+        NotImplementedError,
+        match="Resampling with sample_weight is only implemented for stratify=None",
+    ):
+        resample([0, 1], [0, 1], sample_weight=[1, 1], stratify=[0, 1])
+
+
 @pytest.mark.parametrize("csr_container", CSR_CONTAINERS)
 def test_resample_stratify_sparse_error(csr_container):
     # resample must be ndarray
diff --git a/sklearn/utils/tests/test_stats.py b/sklearn/utils/tests/test_stats.py
index fdf679b99b7f2..5ed1934da1c5a 100644
--- a/sklearn/utils/tests/test_stats.py
+++ b/sklearn/utils/tests/test_stats.py
@@ -1,8 +1,46 @@
 import numpy as np
+import pytest
 from numpy.testing import assert_allclose
 from pytest import approx
 
-from sklearn.utils.stats import _weighted_percentile
+from sklearn.utils.fixes import np_version, parse_version
+from sklearn.utils.stats import _averaged_weighted_percentile, _weighted_percentile
+
+
+def test_averaged_weighted_median():
+    y = np.array([0, 1, 2, 3, 4, 5])
+    sw = np.array([1, 1, 1, 1, 1, 1])
+
+    score = _averaged_weighted_percentile(y, sw, 50)
+
+    assert score == np.median(y)
+
+
+# TODO: remove @pytest.mark.skipif when numpy min version >= 1.22.
+@pytest.mark.skipif(
+    condition=np_version < parse_version("1.22"),
+    reason="older numpy do not support the 'method' parameter",
+)
+def test_averaged_weighted_percentile():
+    rng = np.random.RandomState(0)
+    y = rng.randint(20, size=10)
+
+    sw = np.ones(10)
+
+    score = _averaged_weighted_percentile(y, sw, 20)
+
+    assert score == np.percentile(y, 20, method="averaged_inverted_cdf")
+
+
+def test_averaged_and_weighted_percentile():
+    y = np.array([0, 1, 2])
+    sw = np.array([5, 1, 5])
+    q = 50
+
+    score_averaged = _averaged_weighted_percentile(y, sw, q)
+    score = _weighted_percentile(y, sw, q)
+
+    assert score_averaged == score
 
 
 def test_weighted_percentile():

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA sklearn/ensemble/_hist_gradient_boosting/tests/test_gradient_boosting.py sklearn/inspection/tests/test_permutation_importance.py sklearn/preprocessing/tests/test_discretization.py sklearn/preprocessing/tests/test_polynomial.py sklearn/preprocessing/tests/test_target_encoder.py sklearn/tests/test_docstring_parameters.py sklearn/utils/_test_common/instance_generator.py sklearn/utils/tests/test_indexing.py sklearn/utils/tests/test_stats.py
: '>>>>> End Test Output'
git checkout e25e8e2119ab6c5aa5072b05c0eb60b10aee4b05 sklearn/ensemble/_hist_gradient_boosting/tests/test_gradient_boosting.py sklearn/inspection/tests/test_permutation_importance.py sklearn/preprocessing/tests/test_discretization.py sklearn/preprocessing/tests/test_polynomial.py sklearn/preprocessing/tests/test_target_encoder.py sklearn/tests/test_docstring_parameters.py sklearn/utils/_test_common/instance_generator.py sklearn/utils/tests/test_indexing.py sklearn/utils/tests/test_stats.py
