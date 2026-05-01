#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff be982f2f304487fe634e507f2d1341225fd5019d
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout be982f2f304487fe634e507f2d1341225fd5019d tests/plugins/test_bilibili.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/plugins/test_bilibili.py b/tests/plugins/test_bilibili.py
index 0ac77acfbbd..69b65c6f93f 100644
--- a/tests/plugins/test_bilibili.py
+++ b/tests/plugins/test_bilibili.py
@@ -6,5 +6,5 @@ class TestPluginCanHandleUrlBilibili(PluginCanHandleUrl):
     __plugin__ = Bilibili
 
     should_match_groups = [
-        ("https://live.bilibili.com/CHANNEL", {"channel": "CHANNEL"}),
+        ("https://live.bilibili.com/CHANNEL?live_from=78001", {"channel": "CHANNEL"}),
     ]

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/plugins/test_bilibili.py
: '>>>>> End Test Output'
git checkout be982f2f304487fe634e507f2d1341225fd5019d tests/plugins/test_bilibili.py
