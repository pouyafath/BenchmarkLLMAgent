#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff f7bf3f726e3f19bf68b5e7e460f116850896eb42
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install hatchling editables && python -m pip install -e '.[test]' --no-build-isolation && python -m pip install pexpect pyftpdlib testfixtures || python -m pip install hatchling editables && python -m pip install -e . --no-build-isolation && python -m pip install pexpect pyftpdlib testfixtures
git checkout f7bf3f726e3f19bf68b5e7e460f116850896eb42 tests/test_robotstxt_interface.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_robotstxt_interface.py b/tests/test_robotstxt_interface.py
index d7a92308..6ad30dee 100644
--- a/tests/test_robotstxt_interface.py
+++ b/tests/test_robotstxt_interface.py
@@ -1,5 +1,7 @@
 from twisted.trial import unittest
 
+from scrapy.robotstxt import decode_robotstxt
+
 
 def reppy_available():
     # check if reppy parser is installed
@@ -141,6 +143,25 @@ class BaseRobotParserTest:
         )
 
 
+class DecodeRobotsTxtTest(unittest.TestCase):
+    def test_native_string_conversion(self):
+        robotstxt_body = "User-agent: *\nDisallow: /\n".encode("utf-8")
+        decoded_content = decode_robotstxt(
+            robotstxt_body, spider=None, to_native_str_type=True
+        )
+        self.assertEqual(decoded_content, "User-agent: *\nDisallow: /\n")
+
+    def test_decode_utf8(self):
+        robotstxt_body = "User-agent: *\nDisallow: /\n".encode("utf-8")
+        decoded_content = decode_robotstxt(robotstxt_body, spider=None)
+        self.assertEqual(decoded_content, "User-agent: *\nDisallow: /\n")
+
+    def test_decode_non_utf8(self):
+        robotstxt_body = b"User-agent: *\n\xFFDisallow: /\n"
+        decoded_content = decode_robotstxt(robotstxt_body, spider=None)
+        self.assertEqual(decoded_content, "User-agent: *\nDisallow: /\n")
+
+
 class PythonRobotParserTest(BaseRobotParserTest, unittest.TestCase):
     def setUp(self):
         from scrapy.robotstxt import PythonRobotParser

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_robotstxt_interface.py
: '>>>>> End Test Output'
git checkout f7bf3f726e3f19bf68b5e7e460f116850896eb42 tests/test_robotstxt_interface.py
