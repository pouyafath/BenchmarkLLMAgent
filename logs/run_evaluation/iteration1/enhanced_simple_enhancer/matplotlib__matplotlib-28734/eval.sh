#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 1c892c20334185294fa06ee5bf7a91ec843bbaa7
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 1c892c20334185294fa06ee5bf7a91ec843bbaa7 lib/matplotlib/tests/test_constrainedlayout.py
git apply -v - <<'EOF_114329324912'
diff --git a/lib/matplotlib/tests/test_constrainedlayout.py b/lib/matplotlib/tests/test_constrainedlayout.py
index 4dc4d9501ec1..e42e2ee9bfd8 100644
--- a/lib/matplotlib/tests/test_constrainedlayout.py
+++ b/lib/matplotlib/tests/test_constrainedlayout.py
@@ -662,6 +662,30 @@ def test_compressed1():
     np.testing.assert_allclose(pos.y0, 0.1934, atol=1e-3)
 
 
+def test_compressed_suptitle():
+    fig, (ax0, ax1) = plt.subplots(
+        nrows=2, figsize=(4, 10), layout="compressed",
+        gridspec_kw={"height_ratios": (1 / 4, 3 / 4), "hspace": 0})
+
+    ax0.axis("equal")
+    ax0.set_box_aspect(1/3)
+
+    ax1.axis("equal")
+    ax1.set_box_aspect(1)
+
+    title = fig.suptitle("Title")
+    fig.draw_without_rendering()
+    assert title.get_position()[1] == pytest.approx(0.7457, abs=1e-3)
+
+    title = fig.suptitle("Title", y=0.98)
+    fig.draw_without_rendering()
+    assert title.get_position()[1] == 0.98
+
+    title = fig.suptitle("Title", in_layout=False)
+    fig.draw_without_rendering()
+    assert title.get_position()[1] == 0.98
+
+
 @pytest.mark.parametrize('arg, state', [
     (True, True),
     (False, False),

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA lib/matplotlib/tests/test_constrainedlayout.py
: '>>>>> End Test Output'
git checkout 1c892c20334185294fa06ee5bf7a91ec843bbaa7 lib/matplotlib/tests/test_constrainedlayout.py
