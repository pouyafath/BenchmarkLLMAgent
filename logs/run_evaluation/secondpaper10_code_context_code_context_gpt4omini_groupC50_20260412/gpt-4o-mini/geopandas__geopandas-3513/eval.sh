#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff bdb4006f2ac24003b003e5975586c299bbf61b5d
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout bdb4006f2ac24003b003e5975586c299bbf61b5d geopandas/io/tests/test_geoarrow.py
git apply -v - <<'EOF_114329324912'
diff --git a/geopandas/io/tests/test_geoarrow.py b/geopandas/io/tests/test_geoarrow.py
index f01b1e91c1..3e3000cca6 100644
--- a/geopandas/io/tests/test_geoarrow.py
+++ b/geopandas/io/tests/test_geoarrow.py
@@ -210,11 +210,11 @@ def test_geoarrow_multiple_geometry_crs(encoding):
     meta1 = json.loads(
         result.schema.field("geometry").metadata[b"ARROW:extension:metadata"]
     )
-    assert json.loads(meta1["crs"])["id"]["code"] == 4326
+    assert meta1["crs"]["id"]["code"] == 4326
     meta2 = json.loads(
         result.schema.field("geom2").metadata[b"ARROW:extension:metadata"]
     )
-    assert json.loads(meta2["crs"])["id"]["code"] == 3857
+    assert meta2["crs"]["id"]["code"] == 3857
 
     roundtripped = GeoDataFrame.from_arrow(result)
     assert_geodataframe_equal(gdf, roundtripped)
@@ -237,7 +237,7 @@ def test_geoarrow_series_name_crs(encoding):
         else b"geoarrow.polygon"
     )
     meta = json.loads(field.metadata[b"ARROW:extension:metadata"])
-    assert json.loads(meta["crs"])["id"]["code"] == 4326
+    assert meta["crs"]["id"]["code"] == 4326
 
     # ensure it also works without a name
     gser = GeoSeries([box(0, 0, 10, 10)])

EOF_114329324912
: '>>>>> Start Test Output'
pytest -v -rA geopandas/io/tests/test_geoarrow.py
: '>>>>> End Test Output'
git checkout bdb4006f2ac24003b003e5975586c299bbf61b5d geopandas/io/tests/test_geoarrow.py
