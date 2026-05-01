#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 82a14627fddbd0b2d802fbc574fa3b1ef010a801
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 82a14627fddbd0b2d802fbc574fa3b1ef010a801 tests/test_slots.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_slots.py b/tests/test_slots.py
index c1332f2d3..78215ea18 100644
--- a/tests/test_slots.py
+++ b/tests/test_slots.py
@@ -806,6 +806,45 @@ def f(self):
         a.z
 
 
+@pytest.mark.skipif(not PY_3_8_PLUS, reason="cached_property is 3.8+")
+def test_slots_cached_property_raising_attributeerror():
+    """
+    Ensures AttributeError raised by a property is preserved by __getattr__()
+    implementation.
+
+    Regression test for issue https://github.com/python-attrs/attrs/issues/1230
+    """
+
+    @attr.s(slots=True)
+    class A:
+        x = attr.ib()
+
+        @functools.cached_property
+        def f(self):
+            return self.p
+
+        @property
+        def p(self):
+            raise AttributeError("I am a property")
+
+        @functools.cached_property
+        def g(self):
+            return self.q
+
+        @property
+        def q(self):
+            return 2
+
+    a = A(1)
+    with pytest.raises(AttributeError, match=r"^I am a property$"):
+        a.p
+    with pytest.raises(AttributeError, match=r"^I am a property$"):
+        a.f
+
+    assert a.g == 2
+    assert a.q == 2
+
+
 @pytest.mark.skipif(not PY_3_8_PLUS, reason="cached_property is 3.8+")
 def test_slots_cached_property_with_getattr_calls_getattr_for_missing_attributes():
     """

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_slots.py
: '>>>>> End Test Output'
git checkout 82a14627fddbd0b2d802fbc574fa3b1ef010a801 tests/test_slots.py
