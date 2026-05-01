#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 664b45729aa6ac2d6ef9459d8c0ad04f50af847c
source /opt/miniconda3/bin/activate
conda activate testbed
MPLLOCALFREETYPE=0 MPLLOCALQHULL=0 python -m pip install --no-build-isolation -e ".[dev]"
git checkout 664b45729aa6ac2d6ef9459d8c0ad04f50af847c lib/matplotlib/tests/test_backend_registry.py lib/matplotlib/tests/test_backend_template.py
git apply -v - <<'EOF_114329324912'
diff --git a/lib/matplotlib/tests/test_backend_registry.py b/lib/matplotlib/tests/test_backend_registry.py
index 141ffd69c266..80c2ce4fc51a 100644
--- a/lib/matplotlib/tests/test_backend_registry.py
+++ b/lib/matplotlib/tests/test_backend_registry.py
@@ -86,6 +86,15 @@ def test_is_valid_backend(backend, is_valid):
     assert backend_registry.is_valid_backend(backend) == is_valid
 
 
+@pytest.mark.parametrize("backend, normalized", [
+    ("agg", "matplotlib.backends.backend_agg"),
+    ("QtAgg", "matplotlib.backends.backend_qtagg"),
+    ("module://Anything", "Anything"),
+])
+def test_backend_normalization(backend, normalized):
+    assert backend_registry._backend_module_name(backend) == normalized
+
+
 def test_deprecated_rcsetup_attributes():
     match = "was deprecated in Matplotlib 3.9"
     with pytest.warns(mpl.MatplotlibDeprecationWarning, match=match):
diff --git a/lib/matplotlib/tests/test_backend_template.py b/lib/matplotlib/tests/test_backend_template.py
index d7e2a5cd1266..964d15c1559a 100644
--- a/lib/matplotlib/tests/test_backend_template.py
+++ b/lib/matplotlib/tests/test_backend_template.py
@@ -49,3 +49,14 @@ def test_show_old_global_api(monkeypatch):
     mpl.use("module://mpl_test_backend")
     plt.show()
     mock_show.assert_called_with()
+
+
+def test_load_case_sensitive(monkeypatch):
+    mpl_test_backend = SimpleNamespace(**vars(backend_template))
+    mock_show = MagicMock()
+    monkeypatch.setattr(
+        mpl_test_backend.FigureManagerTemplate, "pyplot_show", mock_show)
+    monkeypatch.setitem(sys.modules, "mpl_Test_Backend", mpl_test_backend)
+    mpl.use("module://mpl_Test_Backend")
+    plt.show()
+    mock_show.assert_called_with()

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA lib/matplotlib/tests/test_backend_registry.py lib/matplotlib/tests/test_backend_template.py
: '>>>>> End Test Output'
git checkout 664b45729aa6ac2d6ef9459d8c0ad04f50af847c lib/matplotlib/tests/test_backend_registry.py lib/matplotlib/tests/test_backend_template.py
