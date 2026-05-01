#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 380eefa041afdc18ca36d278174bef787c18d023
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]' && python -m pip install requests pandas || python -m pip install -e . && python -m pip install requests pandas
git checkout 380eefa041afdc18ca36d278174bef787c18d023 tests/test_io/test_renderers.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_io/test_renderers.py b/tests/test_io/test_renderers.py
index 4860c738a..43dd250d8 100644
--- a/tests/test_io/test_renderers.py
+++ b/tests/test_io/test_renderers.py
@@ -33,6 +33,13 @@ def fig1(request):
     )
 
 
+def test_default_renderer():
+    """
+    The default renderer should be 'browser'.
+    """
+    assert pio.renderers.default == "browser"
+
+
 # JSON
 # ----
 def test_json_renderer_mimetype(fig1):

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_io/test_renderers.py
: '>>>>> End Test Output'
git checkout 380eefa041afdc18ca36d278174bef787c18d023 tests/test_io/test_renderers.py
