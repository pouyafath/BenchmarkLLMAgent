#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 2276f624cf0ab85a43df17fb3f21058ca08d1123
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 2276f624cf0ab85a43df17fb3f21058ca08d1123 geopandas/tests/test_plotting.py
git apply -v - <<'EOF_114329324912'
diff --git a/geopandas/tests/test_plotting.py b/geopandas/tests/test_plotting.py
index e74f7a1ca0..83395ac82c 100644
--- a/geopandas/tests/test_plotting.py
+++ b/geopandas/tests/test_plotting.py
@@ -451,6 +451,17 @@ def test_no_missing_and_missing_kwds(self):
         df["category"] = df["values"].astype("str")
         df.plot("category", missing_kwds={"facecolor": "none"}, legend=True)
 
+    def test_missing_aspect(self):
+        self.df.loc[0, "values"] = np.nan
+        ax = self.df.plot(
+            "values",
+            missing_kwds={"color": "r"},
+            categorical=True,
+            legend=True,
+            aspect=2,
+        )
+        assert ax.get_aspect() == 2
+
 
 class TestPointZPlotting:
     def setup_method(self):

EOF_114329324912
: '>>>>> Start Test Output'
pytest -v -rA geopandas/tests geopandas/tests/test_plotting.py
: '>>>>> End Test Output'
git checkout 2276f624cf0ab85a43df17fb3f21058ca08d1123 geopandas/tests/test_plotting.py
