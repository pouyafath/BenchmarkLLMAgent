#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 11d50b056752033df792fc56efccae5d3835cf5d
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]' && python -m pip install requests pandas polars pyarrow || python -m pip install -e . && python -m pip install requests pandas polars pyarrow
git checkout 11d50b056752033df792fc56efccae5d3835cf5d 
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_optional/test_graph_objs/test_numpy.py b/tests/test_optional/test_graph_objs/test_numpy.py
new file mode 100644
index 000000000..a234dc478
--- /dev/null
+++ b/tests/test_optional/test_graph_objs/test_numpy.py
@@ -0,0 +1,16 @@
+from datetime import datetime
+
+import numpy as np
+
+import plotly.graph_objs as go
+
+
+def test_np_ns_datetime():
+    x = [np.datetime64("2025-09-26").astype("datetime64[ns]")]
+    y = [1.23]
+    scatter = go.Scatter(x=x, y=y, mode="markers")
+
+    # x value should be converted to native datetime
+    assert isinstance(scatter.x[0], datetime)
+    # x value should match original numpy value at microsecond precision
+    assert x[0].astype("datetime64[us]").item() == scatter.x[0]
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_optional/test_graph_objs/test_numpy.py
: '>>>>> End Test Output'
git checkout 11d50b056752033df792fc56efccae5d3835cf5d 
