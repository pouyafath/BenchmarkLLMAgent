#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 537374809630a4cbdc82f25a1cd86d4c4f399879
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]' && python -m pip install requests pandas polars pyarrow || python -m pip install -e . && python -m pip install requests pandas polars pyarrow
git checkout 537374809630a4cbdc82f25a1cd86d4c4f399879 tests/test_core/test_graph_objs/test_figure_properties.py tests/test_optional/test_px/test_colors.py tests/test_optional/test_px/test_imshow.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_core/test_graph_objs/test_figure_properties.py b/tests/test_core/test_graph_objs/test_figure_properties.py
index d7847a587..967613739 100644
--- a/tests/test_core/test_graph_objs/test_figure_properties.py
+++ b/tests/test_core/test_graph_objs/test_figure_properties.py
@@ -1,4 +1,5 @@
 from unittest import TestCase
+from unittest.mock import MagicMock
 import pytest
 
 import plotly.graph_objs as go
@@ -42,6 +43,15 @@ class TestFigureProperties(TestCase):
     def test_iter(self):
         self.assertEqual(set(self.figure), {"data", "layout", "frames"})
 
+    def test_unsupported_eq_returns_not_implemented(self):
+        other = MagicMock()
+        self.assertFalse(self.figure == other)
+        other.__eq__.assert_called_once_with(self.figure)
+
+        other.reset_mock()
+        self.assertFalse(self.figure.layout == other)
+        other.__eq__.assert_called_once_with(self.figure.layout)
+
     def test_attr_item(self):
         # test that equal objects can be retrieved using attr or item
         # syntax
diff --git a/tests/test_optional/test_px/test_colors.py b/tests/test_optional/test_px/test_colors.py
index 8f6e599d8..d41dc7aa6 100644
--- a/tests/test_optional/test_px/test_colors.py
+++ b/tests/test_optional/test_px/test_colors.py
@@ -60,3 +60,24 @@ def test_color_categorical_dtype():
     px.scatter(
         df[df.day != df.day.cat.categories[0]], x="total_bill", y="tip", color="day"
     )
+
+
+def test_color_continuous_scale_autocolorscale():
+    # User-provided colorscale should override template autocolorscale=True
+    fig = px.scatter(
+        x=[1, 2],
+        y=[1, 2],
+        color=[1, 2],
+        color_continuous_scale="Viridis",
+        template=dict(layout_coloraxis_autocolorscale=True),
+    )
+    assert fig.layout.coloraxis1.autocolorscale is False
+
+    # Without user-provided colorscale, template autocolorscale should be respected
+    fig2 = px.scatter(
+        x=[1, 2],
+        y=[1, 2],
+        color=[1, 2],
+        template=dict(layout_coloraxis_autocolorscale=True),
+    )
+    assert fig2.layout.coloraxis1.autocolorscale is None
diff --git a/tests/test_optional/test_px/test_imshow.py b/tests/test_optional/test_px/test_imshow.py
index c4ecea944..3a0e230eb 100644
--- a/tests/test_optional/test_px/test_imshow.py
+++ b/tests/test_optional/test_px/test_imshow.py
@@ -98,6 +98,23 @@ def test_colorscale():
     assert fig.layout.coloraxis1.colorscale[0] == (0.0, "#440154")
 
 
+def test_imshow_color_continuous_scale_autocolorscale():
+    # User-provided colorscale should override template autocolorscale=True
+    fig = px.imshow(
+        img_gray,
+        color_continuous_scale="Viridis",
+        template=dict(layout_coloraxis_autocolorscale=True),
+    )
+    assert fig.layout.coloraxis1.autocolorscale is False
+
+    # Without user-provided colorscale, template autocolorscale should be respected
+    fig2 = px.imshow(
+        img_gray,
+        template=dict(layout_coloraxis_autocolorscale=True),
+    )
+    assert fig2.layout.coloraxis1.autocolorscale is None
+
+
 def test_wrong_dimensions():
     imgs = [1, np.ones((5,) * 3), np.ones((5,) * 4)]
     msg = "px.imshow only accepts 2D single-channel, RGB or RGBA images."

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_core/test_graph_objs/test_figure_properties.py tests/test_optional/test_px/test_colors.py tests/test_optional/test_px/test_imshow.py
: '>>>>> End Test Output'
git checkout 537374809630a4cbdc82f25a1cd86d4c4f399879 tests/test_core/test_graph_objs/test_figure_properties.py tests/test_optional/test_px/test_colors.py tests/test_optional/test_px/test_imshow.py
