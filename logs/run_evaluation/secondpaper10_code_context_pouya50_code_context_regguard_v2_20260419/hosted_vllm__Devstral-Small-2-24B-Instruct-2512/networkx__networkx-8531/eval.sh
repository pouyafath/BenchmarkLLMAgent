#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 991fbe966a7af0ebd74d5929966b468a602c9c59
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[default,developer,test]
git checkout 991fbe966a7af0ebd74d5929966b468a602c9c59 networkx/algorithms/approximation/tests/test_dominating_set.py
git apply -v - <<'EOF_114329324912'
diff --git a/networkx/algorithms/approximation/tests/test_dominating_set.py b/networkx/algorithms/approximation/tests/test_dominating_set.py
index 6b90d85e..d0ae6f01 100644
--- a/networkx/algorithms/approximation/tests/test_dominating_set.py
+++ b/networkx/algorithms/approximation/tests/test_dominating_set.py
@@ -44,6 +44,22 @@ class TestMinWeightDominatingSet:
         G = nx.Graph()
         assert min_weighted_dominating_set(G) == set()
 
+    def test_cost_accounts_for_already_dominated(self):
+        """Tests that the greedy cost function considers nodes dominated by
+        neighbors of the dominating set, not just nodes in the set itself.
+
+        Regression test for #8523.
+        """
+        # K5 + path 4-5-6: nodes 0-4 form a clique, 5 and 6 hang off node 4.
+        # Any minimum dominating set has 2 nodes: one from the clique (0-4)
+        # and one from the tail (5 or 6). E.g. {0, 5}, {4, 6}, {2, 5}, etc.
+        graph = nx.complete_graph(5)
+        graph.add_edge(4, 5)
+        graph.add_edge(5, 6)
+        dom_set = min_weighted_dominating_set(graph)
+        assert nx.is_dominating_set(graph, dom_set)
+        assert len(dom_set) == 2
+
     def test_min_edge_dominating_set(self):
         graph = nx.path_graph(5)
         dom_set = min_edge_dominating_set(graph)
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA networkx/algorithms/approximation/tests/test_dominating_set.py
: '>>>>> End Test Output'
git checkout 991fbe966a7af0ebd74d5929966b468a602c9c59 networkx/algorithms/approximation/tests/test_dominating_set.py
