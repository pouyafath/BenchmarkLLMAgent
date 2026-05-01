#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 61d209875422f5c40600d2d425bd92fac9cc1b02
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[default,developer,test]
git checkout 61d209875422f5c40600d2d425bd92fac9cc1b02 networkx/algorithms/connectivity/tests/test_kcutsets.py
git apply -v - <<'EOF_114329324912'
diff --git a/networkx/algorithms/connectivity/tests/test_kcutsets.py b/networkx/algorithms/connectivity/tests/test_kcutsets.py
index 644b378c..b47381dd 100644
--- a/networkx/algorithms/connectivity/tests/test_kcutsets.py
+++ b/networkx/algorithms/connectivity/tests/test_kcutsets.py
@@ -8,7 +8,7 @@ import networkx as nx
 from networkx.algorithms import flow
 from networkx.algorithms.connectivity.kcutsets import _is_separating_set
 
-MAX_CUTSETS_TO_TEST = 4  # originally 100. cut to decrease testing time
+MAX_CUTSETS_TO_TEST = 100
 
 flow_funcs = [
     flow.boykov_kolmogorov,
@@ -133,7 +133,6 @@ def _check_separating_sets(G):
             assert not nx.is_connected(nx.restricted_view(G, cut, []))
 
 
-@pytest.mark.slow
 def test_torrents_and_ferraro_graph():
     G = torrents_and_ferraro_graph()
     _check_separating_sets(G)
@@ -207,7 +206,6 @@ def test_disconnected_graph():
     pytest.raises(nx.NetworkXError, next, cuts)
 
 
-@pytest.mark.slow
 @pytest.mark.parametrize("G", [nx.grid_2d_graph(4, 4), nx.cycle_graph(5)])
 @pytest.mark.parametrize("flow_func", flow_funcs)
 def test_alternative_flow_functions(G, flow_func):

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA networkx/algorithms/connectivity/tests/test_kcutsets.py
: '>>>>> End Test Output'
git checkout 61d209875422f5c40600d2d425bd92fac9cc1b02 networkx/algorithms/connectivity/tests/test_kcutsets.py
