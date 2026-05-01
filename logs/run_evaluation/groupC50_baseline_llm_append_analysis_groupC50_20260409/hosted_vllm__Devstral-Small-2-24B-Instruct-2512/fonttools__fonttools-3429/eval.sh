#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 7cdac78423b259e77641fe3a1cf3a0b1cc5ec049
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 7cdac78423b259e77641fe3a1cf3a0b1cc5ec049 Tests/otlLib/builder_test.py
git apply -v - <<'EOF_114329324912'
diff --git a/Tests/otlLib/builder_test.py b/Tests/otlLib/builder_test.py
index b7a6caa2f5..e2743808bf 100644
--- a/Tests/otlLib/builder_test.py
+++ b/Tests/otlLib/builder_test.py
@@ -1051,11 +1051,11 @@ def test_buildValue(self):
         func = lambda writer, font: value.toXML(writer, font, valueName="Val")
         assert getXML(func) == ['<Val XPlacement="7" YPlacement="23"/>']
 
-    def test_getLigatureKey(self):
+    def test_getLigatureSortKey(self):
         components = lambda s: [tuple(word) for word in s.split()]
         c = components("fi fl ff ffi fff")
-        c.sort(key=builder._getLigatureKey)
-        assert c == components("fff ffi ff fi fl")
+        c.sort(key=otTables.LigatureSubst._getLigatureSortKey)
+        assert c == components("ffi fff fi fl ff")
 
     def test_getSinglePosValueKey(self):
         device = builder.buildDevice({10: 1, 11: 3})

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA Tests/otlLib/builder_test.py
: '>>>>> End Test Output'
git checkout 7cdac78423b259e77641fe3a1cf3a0b1cc5ec049 Tests/otlLib/builder_test.py
