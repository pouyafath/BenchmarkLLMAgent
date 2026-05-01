#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 96800fb673cb7b2d75476096798e701e3e6d26bc
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git checkout 96800fb673cb7b2d75476096798e701e3e6d26bc examples/javascript/tests/test_js_example.py
git apply -v - <<'EOF_114329324912'
diff --git a/examples/javascript/tests/test_js_example.py b/examples/javascript/tests/test_js_example.py
index d155ad5c34..856f5f7725 100644
--- a/examples/javascript/tests/test_js_example.py
+++ b/examples/javascript/tests/test_js_example.py
@@ -5,7 +5,7 @@
 @pytest.mark.parametrize(
     ("path", "template_name"),
     (
-        ("/", "xhr.html"),
+        ("/", "fetch.html"),
         ("/plain", "xhr.html"),
         ("/fetch", "fetch.html"),
         ("/jquery", "jquery.html"),

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA examples/javascript/tests/test_js_example.py
: '>>>>> End Test Output'
git checkout 96800fb673cb7b2d75476096798e701e3e6d26bc examples/javascript/tests/test_js_example.py
