#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 7a13c041dbef42f9f3feb14110f02626f6892e9a
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 7a13c041dbef42f9f3feb14110f02626f6892e9a tests/test_requests.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_requests.py b/tests/test_requests.py
index a71fe7d6b8..b6fb84d1bd 100644
--- a/tests/test_requests.py
+++ b/tests/test_requests.py
@@ -1808,6 +1808,23 @@ def test_autoset_header_values_are_native(self, httpbin):
 
         assert p.headers["Content-Length"] == length
 
+    def test_content_length_for_bytes_data(self, httpbin):
+        data = "This is a string containing multi-byte UTF-8 ☃️"
+        encoded_data = data.encode("utf-8")
+        length = str(len(encoded_data))
+        req = requests.Request("POST", httpbin("post"), data=encoded_data)
+        p = req.prepare()
+
+        assert p.headers["Content-Length"] == length
+
+    def test_content_length_for_string_data_counts_bytes(self, httpbin):
+        data = "This is a string containing multi-byte UTF-8 ☃️"
+        length = str(len(data.encode("utf-8")))
+        req = requests.Request("POST", httpbin("post"), data=data)
+        p = req.prepare()
+
+        assert p.headers["Content-Length"] == length
+
     def test_nonhttp_schemes_dont_check_URLs(self):
         test_urls = (
             "data:image/gif;base64,R0lGODlhAQABAHAAACH5BAUAAAAALAAAAAABAAEAAAICRAEAOw==",

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_requests.py
: '>>>>> End Test Output'
git checkout 7a13c041dbef42f9f3feb14110f02626f6892e9a tests/test_requests.py
