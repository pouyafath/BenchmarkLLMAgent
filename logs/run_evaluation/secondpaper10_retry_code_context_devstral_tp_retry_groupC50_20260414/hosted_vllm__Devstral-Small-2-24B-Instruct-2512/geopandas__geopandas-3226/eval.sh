#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 514f975298b940fca1a39917ff35aa12b149a1e7
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 514f975298b940fca1a39917ff35aa12b149a1e7 geopandas/tests/test_geoseries.py
git apply -v - <<'EOF_114329324912'
diff --git a/geopandas/tests/test_geoseries.py b/geopandas/tests/test_geoseries.py
index 99b8336bcd..9ee5615025 100644
--- a/geopandas/tests/test_geoseries.py
+++ b/geopandas/tests/test_geoseries.py
@@ -55,6 +55,9 @@ def setup_method(self):
         self.l1 = LineString([(0, 0), (0, 1), (1, 1)])
         self.l2 = LineString([(0, 0), (1, 0), (1, 1), (0, 1)])
         self.g5 = GeoSeries([self.l1, self.l2])
+        self.esb3857 = Point(-8235939.130493107, 4975301.253789809)
+        self.sol3857 = Point(-8242607.167991625, 4966620.938285081)
+        self.landmarks3857 = GeoSeries([self.esb3857, self.sol3857], crs="epsg:3857")
 
     def teardown_method(self):
         shutil.rmtree(self.tempdir)
@@ -201,9 +204,62 @@ def test_to_json(self):
         Test whether GeoSeries.to_json works and returns an actual json file.
         """
         json_str = self.g3.to_json()
-        json.loads(json_str)
+        data = json.loads(json_str)
+        assert "id" in data["features"][0].keys()
+        assert "bbox" in data["features"][0].keys()
         # TODO : verify the output is a valid GeoJSON.
 
+    def test_to_json_drop_id(self):
+        """
+        Test whether GeoSeries.to_json works when drop_id is True.
+        """
+        json_str = self.g3.to_json(drop_id=True)
+        data = json.loads(json_str)
+        assert "id" not in data["features"][0].keys()
+
+    def test_to_json_no_bbox(self):
+        """
+        Test whether GeoSeries.to_json works when show_bbox is False.
+        """
+        json_str = self.g3.to_json(show_bbox=False)
+        data = json.loads(json_str)
+        assert "bbox" not in data["features"][0].keys()
+
+    def test_to_json_no_bbox_drop_id(self):
+        """
+        Test whether GeoSeries.to_json works when show_bbox is False
+        and drop_id is True.
+        """
+        json_str = self.g3.to_json(show_bbox=False, drop_id=True)
+        data = json.loads(json_str)
+        assert "id" not in data["features"][0].keys()
+        assert "bbox" not in data["features"][0].keys()
+
+    @pytest.mark.skipif(not compat.HAS_PYPROJ, reason="Requires pyproj")
+    def test_to_json_wgs84(self):
+        """
+        Test whether the wgs84 conversion works as intended.
+        """
+        text = self.landmarks3857.to_json(to_wgs84=True)
+        data = json.loads(text)
+        assert data["type"] == "FeatureCollection"
+        assert "id" in data["features"][0].keys()
+        coord1 = data["features"][0]["geometry"]["coordinates"]
+        coord2 = data["features"][1]["geometry"]["coordinates"]
+        np.testing.assert_allclose(coord1, self.esb.coords[0])
+        np.testing.assert_allclose(coord2, self.sol.coords[0])
+
+    def test_to_json_wgs84_false(self):
+        """
+        Ensure no conversion to wgs84
+        """
+        text = self.landmarks3857.to_json()
+        data = json.loads(text)
+        coord1 = data["features"][0]["geometry"]["coordinates"]
+        coord2 = data["features"][1]["geometry"]["coordinates"]
+        assert coord1 == [-8235939.130493107, 4975301.253789809]
+        assert coord2 == [-8242607.167991625, 4966620.938285081]
+
     def test_representative_point(self):
         assert np.all(self.g1.contains(self.g1.representative_point()))
         assert np.all(self.g2.contains(self.g2.representative_point()))

EOF_114329324912
: '>>>>> Start Test Output'
pytest -v -rA geopandas/ geopandas/tests/test_geoseries.py
: '>>>>> End Test Output'
git checkout 514f975298b940fca1a39917ff35aa12b149a1e7 geopandas/tests/test_geoseries.py
