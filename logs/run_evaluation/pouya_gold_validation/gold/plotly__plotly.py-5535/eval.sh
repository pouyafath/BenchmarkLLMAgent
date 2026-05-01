#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff c7bffb935e1fdc5cd2a852e47838d4f1dc4a7ff0
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]' && python -m pip install requests pandas polars pyarrow || python -m pip install -e . && python -m pip install requests pandas polars pyarrow
git checkout c7bffb935e1fdc5cd2a852e47838d4f1dc4a7ff0 tests/test_optional/test_px/test_px_functions.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_optional/test_px/test_px_functions.py b/tests/test_optional/test_px/test_px_functions.py
index 0814898f8..2822a931f 100644
--- a/tests/test_optional/test_px/test_px_functions.py
+++ b/tests/test_optional/test_px/test_px_functions.py
@@ -619,3 +619,13 @@ def test_timeline_cols_already_temporal(constructor, datetime_columns):
     assert len(fig.data) == 3
     assert fig.layout.xaxis.type == "date"
     assert fig.layout.xaxis.title.text is None
+
+
+def test_empty_histogram():
+    """Empty px.histogram() should not raise, matching scatter/bar/pie behavior.
+
+    Regression test for https://github.com/plotly/plotly.py/issues/5534
+    """
+    fig = px.histogram()
+    assert len(fig.data) == 1
+    assert fig.data[0].type == "histogram"

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_optional/test_px/test_px_functions.py
: '>>>>> End Test Output'
git checkout c7bffb935e1fdc5cd2a852e47838d4f1dc4a7ff0 tests/test_optional/test_px/test_px_functions.py
