#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff e577796707472e66dfdf8d8e6e633d347e856da7
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[default,developer,test]
git checkout e577796707472e66dfdf8d8e6e633d347e856da7 networkx/algorithms/tests/test_distance_measures.py
git apply -v - <<'EOF_114329324912'
diff --git a/networkx/algorithms/tests/test_distance_measures.py b/networkx/algorithms/tests/test_distance_measures.py
index 1668fefd..f3fe7e66 100644
--- a/networkx/algorithms/tests/test_distance_measures.py
+++ b/networkx/algorithms/tests/test_distance_measures.py
@@ -74,10 +74,9 @@ class TestDistance:
         assert e == 0
         pytest.raises(nx.NetworkXError, nx.eccentricity, G, 1)
 
-        # test against empty graph
-        G = nx.empty_graph()
-        e = nx.eccentricity(G)
-        assert e == {}
+        # test against null graph
+        G = nx.Graph()
+        pytest.raises(nx.NetworkXPointlessConcept, nx.eccentricity, G)
 
     def test_diameter(self):
         assert nx.diameter(self.G) == 6
@@ -171,6 +170,13 @@ class TestDistance:
             DG = nx.DiGraph([(1, 2), (1, 3)])
             nx.eccentricity(DG)
 
+    def test_diameter_radius_empty_graph(self):
+        G = nx.Graph()
+        with pytest.raises(nx.NetworkXPointlessConcept, match="null graph"):
+            nx.diameter(G)
+        with pytest.raises(nx.NetworkXPointlessConcept, match="null graph"):
+            nx.radius(G)
+
 
 class TestWeightedDistance:
     def setup_method(self):

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA networkx/algorithms/tests/test_distance_measures.py
: '>>>>> End Test Output'
git checkout e577796707472e66dfdf8d8e6e633d347e856da7 networkx/algorithms/tests/test_distance_measures.py
