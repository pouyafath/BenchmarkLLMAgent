#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff c2b219fdae8c419ac5ce6477be3d37c6d060e4c7
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[default,developer,test]
git checkout c2b219fdae8c419ac5ce6477be3d37c6d060e4c7 networkx/utils/tests/test_misc.py
git apply -v - <<'EOF_114329324912'
diff --git a/networkx/utils/tests/test_misc.py b/networkx/utils/tests/test_misc.py
index e1a87495..d229ba59 100644
--- a/networkx/utils/tests/test_misc.py
+++ b/networkx/utils/tests/test_misc.py
@@ -261,6 +261,28 @@ def test_PythonRandomInterface_Generator():
     assert pri.random() == rng.random()
 
 
+def test_python_random_interface_choices_error_message():
+    np = pytest.importorskip("numpy")
+
+    seed = 42
+    pri = PythonRandomInterface(np.random.RandomState(seed))
+
+    msg = "random.choices is not supported when using numpy.random.RandomState"
+    with pytest.raises(AttributeError, match=msg):
+        pri.choices([1, 2, 3], k=2)
+
+
+def test_python_random_interface_unknown_attribute():
+    np = pytest.importorskip("numpy")
+
+    seed = 42
+    pri = PythonRandomInterface(np.random.RandomState(seed))
+
+    msg = "'PythonRandomInterface' object has no attribute 'choises'"
+    with pytest.raises(AttributeError, match=msg):
+        pri.choises([1, 2, 3], k=2)
+
+
 @pytest.mark.parametrize(
     ("iterable_type", "expected"), ((list, 1), (tuple, 1), (str, "["), (set, 1))
 )
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA networkx/utils/tests/test_misc.py
: '>>>>> End Test Output'
git checkout c2b219fdae8c419ac5ce6477be3d37c6d060e4c7 networkx/utils/tests/test_misc.py
