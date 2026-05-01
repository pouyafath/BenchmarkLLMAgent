#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 33dbc472444086e0db670758b30ed4a426a75244
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install --no-build-isolation -e ".[dev]"
git checkout 33dbc472444086e0db670758b30ed4a426a75244 lib/matplotlib/tests/test_figure.py
git apply -v - <<'EOF_114329324912'
diff --git a/lib/matplotlib/tests/test_figure.py b/lib/matplotlib/tests/test_figure.py
index 0c873934ebcb..014eb2cf23d0 100644
--- a/lib/matplotlib/tests/test_figure.py
+++ b/lib/matplotlib/tests/test_figure.py
@@ -1819,3 +1819,19 @@ def test_subfigure_stale_propagation():
     sfig2.stale = True
     assert sfig1.stale
     assert fig.stale
+
+
+@pytest.mark.parametrize("figsize, figsize_inches", [
+    ((6, 4), (6, 4)),
+    ((6, 4, "in"), (6, 4)),
+    ((5.08, 2.54, "cm"), (2, 1)),
+    ((600, 400, "px"), (6, 4)),
+])
+def test_figsize(figsize, figsize_inches):
+    fig = plt.figure(figsize=figsize, dpi=100)
+    assert tuple(fig.get_size_inches()) == figsize_inches
+
+
+def test_figsize_invalid_unit():
+    with pytest.raises(ValueError, match="Invalid unit 'um'"):
+        plt.figure(figsize=(6, 4, "um"))

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA lib/matplotlib/tests/test_figure.py
: '>>>>> End Test Output'
git checkout 33dbc472444086e0db670758b30ed4a426a75244 lib/matplotlib/tests/test_figure.py
