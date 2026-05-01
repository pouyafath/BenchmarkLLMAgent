#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 509d1fceb024a7cf3354f55eac108e2ac199da2c
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]' && python -m pip install requests pandas polars pyarrow pdfrw xarray || python -m pip install -e . && python -m pip install requests pandas polars pyarrow pdfrw xarray
git checkout 509d1fceb024a7cf3354f55eac108e2ac199da2c tests/test_optional/test_px/test_px.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_optional/test_px/test_px.py b/tests/test_optional/test_px/test_px.py
index 3a8ddabcd..6c65925a7 100644
--- a/tests/test_optional/test_px/test_px.py
+++ b/tests/test_optional/test_px/test_px.py
@@ -1,6 +1,7 @@
 from itertools import permutations
 import warnings
 
+import pandas as pd
 import plotly.express as px
 import plotly.io as pio
 import narwhals.stable.v1 as nw
@@ -226,6 +227,54 @@ def test_px_templates(backend):
         pio.templates.default = "plotly"
 
 
+def test_px_templates_trace_specific_colors(backend):
+    tips = px.data.tips(return_type=backend)
+
+    # trace-specific colors: each trace type uses its own template colors
+    template = {
+        "data": {
+            "histogram": [
+                {"marker": {"color": "orange"}},
+                {"marker": {"color": "purple"}},
+            ],
+            "bar": [
+                {"marker": {"color": "red"}},
+                {"marker": {"color": "blue"}},
+            ],
+        },
+        "layout": {
+            "colorway": ["yellow", "green"],
+        },
+    }
+    # histogram uses histogram colors
+    fig = px.histogram(tips, x="total_bill", color="sex", template=template)
+    assert fig.data[0].marker.color == "orange"
+    assert fig.data[1].marker.color == "purple"
+    # fallback to layout.colorway when trace-specific colors don't exist
+    fig = px.box(tips, x="day", y="total_bill", color="sex", template=template)
+    assert fig.data[0].marker.color == "yellow"
+    assert fig.data[1].marker.color == "green"
+    # timeline special case (maps to bar)
+    df_timeline = pd.DataFrame(
+        {
+            "Task": ["Job A", "Job B"],
+            "Start": ["2009-01-01", "2009-03-05"],
+            "Finish": ["2009-02-28", "2009-04-15"],
+            "Resource": ["Alex", "Max"],
+        }
+    )
+    fig = px.timeline(
+        df_timeline,
+        x_start="Start",
+        x_end="Finish",
+        y="Task",
+        color="Resource",
+        template=template,
+    )
+    assert fig.data[0].marker.color == "red"
+    assert fig.data[1].marker.color == "blue"
+
+
 def test_px_defaults():
     px.defaults.labels = dict(x="hey x")
     px.defaults.category_orders = dict(color=["b", "a"])

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_optional/test_px/test_px.py
: '>>>>> End Test Output'
git checkout 509d1fceb024a7cf3354f55eac108e2ac199da2c tests/test_optional/test_px/test_px.py
