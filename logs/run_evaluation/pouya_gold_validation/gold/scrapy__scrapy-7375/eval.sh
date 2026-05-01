#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff b2b2d0b015948f8ca89fae9984ad67c4e7b33ea8
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install hatchling editables && python -m pip install -e '.[test]' --no-build-isolation || python -m pip install hatchling editables && python -m pip install -e . --no-build-isolation
git checkout b2b2d0b015948f8ca89fae9984ad67c4e7b33ea8 tests/test_utils_trackref.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_utils_trackref.py b/tests/test_utils_trackref.py
index 3967c336..7a7a264d 100644
--- a/tests/test_utils_trackref.py
+++ b/tests/test_utils_trackref.py
@@ -1,10 +1,11 @@
+import sys
 from io import StringIO
-from time import sleep, time
 from unittest import mock
 
 import pytest
 
 from scrapy.utils import trackref
+from scrapy.utils.python import garbage_collect
 
 
 class Foo(trackref.object_ref):
@@ -63,24 +64,57 @@ Foo                                 1   oldest: 0s ago\n\n"""
     )
 
 
+_IS_PYPY = "PyPy" in sys.version
+
+
 def test_get_oldest():
-    o1 = Foo()
+    """
+    Verify that `get_oldest` returns the oldest live instance of a class.
 
-    o1_time = time()
+    The test runs in two passes to expose differences between:
+    - CPython (reference counting, immediate destruction)
+    - PyPy (tracing GC, delayed destruction)
 
-    o2 = Bar()
+    Since `trackref` relies on weak references, delayed GC on PyPy can leave
+    stale entries in `live_refs`, affecting results unless explicitly cleared.
+    """
 
-    o3_time = time()
-    if o3_time <= o1_time:
-        sleep(0.01)
-        o3_time = time()
-    if o3_time <= o1_time:
-        pytest.skip("time.time is not precise enough")
+    def _delete_o1():
+        """Delete `o1` and ensure it is actually collected on PyPy."""
+        nonlocal o1
+        del o1
 
-    o3 = Foo()  # noqa: F841
-    assert trackref.get_oldest("Foo") is o1
-    assert trackref.get_oldest("Bar") is o2
-    assert trackref.get_oldest("XXX") is None
+        if _IS_PYPY:
+            # On PyPy, `del` only removes the local reference. The object may
+            # still exist until the GC runs, so we force a collection cycle.
+            garbage_collect()
+
+    def _do_asserts():
+        assert trackref.get_oldest("Foo") is o1
+        assert trackref.get_oldest("Bar") is o2
+        # Ensure the newer Foo is not incorrectly considered the oldest
+        assert trackref.get_oldest("Foo") is not o3
+        assert trackref.get_oldest("XXX") is None
+
+    o1, o2, o3 = Foo(), Bar(), Foo()
+
+    _do_asserts()
+
+    # Remove the oldest Foo instance; o3 should now become the oldest
+    _delete_o1()
+    assert trackref.get_oldest("Foo") is o3
+
+    # PyPy-specific behavior where stale references may persist
+    # unless the registry is explicitly cleared.
+    if _IS_PYPY:
+        trackref.live_refs.clear()
+
+    o1, o2, o3 = Foo(), Bar(), Foo()
+
+    _do_asserts()
+
+    _delete_o1()
+    assert trackref.get_oldest("Foo") is o3
 
 
 def test_iter_all():

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_utils_trackref.py
: '>>>>> End Test Output'
git checkout b2b2d0b015948f8ca89fae9984ad67c4e7b33ea8 tests/test_utils_trackref.py
