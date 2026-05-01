#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 5d160909eeb42e9844496dd2bbd19b826d2242d7
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[default,developer,test]
git checkout 5d160909eeb42e9844496dd2bbd19b826d2242d7 networkx/algorithms/tree/tests/test_mst.py
git apply -v - <<'EOF_114329324912'
diff --git a/networkx/algorithms/tree/tests/test_mst.py b/networkx/algorithms/tree/tests/test_mst.py
index 66ed8652..aab79172 100644
--- a/networkx/algorithms/tree/tests/test_mst.py
+++ b/networkx/algorithms/tree/tests/test_mst.py
@@ -470,6 +470,14 @@ class TestSpanningTreeIterator:
             assert edges_equal(actual, self.spanning_trees[tree_index])
             tree_index -= 1
 
+    def test_next_without_iter(self):
+        """Iteration error. See gh-8563"""
+        G = nx.cycle_graph(3)
+        spanning_trees = nx.SpanningTreeIterator(G)
+        tree = next(spanning_trees)  # must not raise AttributeError
+        assert isinstance(tree, nx.Graph)
+        assert nx.is_tree(tree)
+
 
 class TestSpanningTreeMultiGraphIterator:
     """

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA networkx/algorithms/tree/tests/test_mst.py
: '>>>>> End Test Output'
git checkout 5d160909eeb42e9844496dd2bbd19b826d2242d7 networkx/algorithms/tree/tests/test_mst.py
