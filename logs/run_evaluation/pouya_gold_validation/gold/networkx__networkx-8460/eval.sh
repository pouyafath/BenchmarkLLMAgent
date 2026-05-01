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
git checkout e577796707472e66dfdf8d8e6e633d347e856da7 benchmarks/benchmarks/benchmark_shortest_path.py
git apply -v - <<'EOF_114329324912'
diff --git a/benchmarks/benchmarks/benchmark_shortest_path.py b/benchmarks/benchmarks/benchmark_shortest_path.py
index 0e2a8356..6a97c2d0 100644
--- a/benchmarks/benchmarks/benchmark_shortest_path.py
+++ b/benchmarks/benchmarks/benchmark_shortest_path.py
@@ -47,3 +47,23 @@ class UndirectedGraphAtlasSevenNodesConnected:
     def time_multi_source_dijkstra_over_atlas_with_target(self, edge_weights):
         for G in self.graphs:
             _ = nx.multi_source_dijkstra(G, sources=[0, 1], target=6)
+
+
+class AllShortestPathsGrid:
+    """
+    This tests the performance of _build_paths_from_predecessors
+    on graphs with a large number of paths (high recursion depth).
+    """
+
+    params = [8, 10, 12]
+    param_names = ["N"]
+    timeout = 300
+
+    def setup(self, N):
+        self.G = nx.grid_2d_graph(N, N)
+        self.source = (0, 0)
+        self.target = (N - 1, N - 1)
+
+    def time_all_shortest_paths(self, N):
+        for _ in nx.all_shortest_paths(self.G, self.source, self.target):
+            pass

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA benchmarks/benchmarks/benchmark_shortest_path.py
: '>>>>> End Test Output'
git checkout e577796707472e66dfdf8d8e6e633d347e856da7 benchmarks/benchmarks/benchmark_shortest_path.py
