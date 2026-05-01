#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 802c0a2d8ea282d8c7c1407a2a22717d7575355e
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[default,developer,test]
git checkout 802c0a2d8ea282d8c7c1407a2a22717d7575355e networkx/algorithms/tests/test_mis.py
git apply -v - <<'EOF_114329324912'
diff --git a/networkx/algorithms/tests/test_mis.py b/networkx/algorithms/tests/test_mis.py
index 02be02d4..5a7b67ac 100644
--- a/networkx/algorithms/tests/test_mis.py
+++ b/networkx/algorithms/tests/test_mis.py
@@ -12,13 +12,13 @@ import networkx as nx
 
 def test_random_seed():
     G = nx.empty_graph(5)
-    assert nx.maximal_independent_set(G, seed=1) == [1, 0, 3, 2, 4]
+    assert nx.maximal_independent_set(G, seed=1) == {1, 0, 3, 2, 4}
 
 
 @pytest.mark.parametrize("graph", [nx.complete_graph(5), nx.complete_graph(55)])
 def test_K5(graph):
     """Maximal independent set for complete graphs"""
-    assert all(nx.maximal_independent_set(graph, [n]) == [n] for n in graph)
+    assert all(nx.maximal_independent_set(graph, [n]) == {n} for n in graph)
 
 
 def test_exceptions():

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA networkx/algorithms/tests/test_mis.py
: '>>>>> End Test Output'
git checkout 802c0a2d8ea282d8c7c1407a2a22717d7575355e networkx/algorithms/tests/test_mis.py
