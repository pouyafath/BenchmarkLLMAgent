#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 83aa3e41bf9d4de308e306521e0cb3f688952942
source /opt/miniconda3/bin/activate
conda activate testbed
MPLLOCALFREETYPE=0 MPLLOCALQHULL=0 python -m pip install --no-build-isolation -e ".[dev]"
git checkout 83aa3e41bf9d4de308e306521e0cb3f688952942 lib/matplotlib/tests/test_cycles.py
git apply -v - <<'EOF_114329324912'
diff --git a/lib/matplotlib/tests/test_cycles.py b/lib/matplotlib/tests/test_cycles.py
index 9bbb9bc9f19c..4fa261619490 100644
--- a/lib/matplotlib/tests/test_cycles.py
+++ b/lib/matplotlib/tests/test_cycles.py
@@ -27,6 +27,11 @@ def test_marker_cycle():
     assert [l.get_marker() for l in ax.lines] == ['.', '*', 'x', '.']
 
 
+def test_valid_marker_cycles():
+    fig, ax = plt.subplots()
+    ax.set_prop_cycle(cycler(marker=[1, "+", ".", 4]))
+
+
 def test_marker_cycle_kwargs_arrays_iterators():
     fig, ax = plt.subplots()
     ax.set_prop_cycle(c=np.array(['r', 'g', 'y']),

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA lib/matplotlib/tests/test_cycles.py
: '>>>>> End Test Output'
git checkout 83aa3e41bf9d4de308e306521e0cb3f688952942 lib/matplotlib/tests/test_cycles.py
