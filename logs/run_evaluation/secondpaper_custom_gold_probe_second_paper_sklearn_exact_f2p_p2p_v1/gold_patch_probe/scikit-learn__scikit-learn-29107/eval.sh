#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 06fb3dee57a8f3a872de52ea7092a9e6b6709e5a
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -v --no-build-isolation -e .
git checkout 06fb3dee57a8f3a872de52ea7092a9e6b6709e5a sklearn/utils/tests/test_array_api.py
git apply -v - <<'EOF_114329324912'
diff --git a/sklearn/utils/tests/test_array_api.py b/sklearn/utils/tests/test_array_api.py
index 30fc88c539fc8..25913e7f54846 100644
--- a/sklearn/utils/tests/test_array_api.py
+++ b/sklearn/utils/tests/test_array_api.py
@@ -22,6 +22,7 @@
     _ravel,
     device,
     get_namespace,
+    get_namespace_and_device,
     indexing_dtype,
     supported_float_dtypes,
     yield_namespace_device_dtype_combinations,
@@ -540,3 +541,28 @@ def test_isin(
         )
 
     assert_array_equal(_convert_to_numpy(result, xp=xp), expected)
+
+
+def test_get_namespace_and_device():
+    # Use torch as a library with custom Device objects:
+    torch = pytest.importorskip("torch")
+    xp_torch = pytest.importorskip("array_api_compat.torch")
+    some_torch_tensor = torch.arange(3, device="cpu")
+    some_numpy_array = numpy.arange(3)
+
+    # When dispatch is disabled, get_namespace_and_device should return the
+    # default NumPy wrapper namespace and no device. Our code will handle such
+    # inputs via the usual __array__ interface without attempting to dispatch
+    # via the array API.
+    namespace, is_array_api, device = get_namespace_and_device(some_torch_tensor)
+    assert namespace is get_namespace(some_numpy_array)[0]
+    assert not is_array_api
+    assert device is None
+
+    # Otherwise, expose the torch namespace and device via array API compat
+    # wrapper.
+    with config_context(array_api_dispatch=True):
+        namespace, is_array_api, device = get_namespace_and_device(some_torch_tensor)
+        assert namespace is xp_torch
+        assert is_array_api
+        assert device == some_torch_tensor.device

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA sklearn/utils/tests/test_array_api.py
: '>>>>> End Test Output'
git checkout 06fb3dee57a8f3a872de52ea7092a9e6b6709e5a sklearn/utils/tests/test_array_api.py
