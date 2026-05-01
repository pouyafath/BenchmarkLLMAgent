#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 6f2014d353d514e404c1f40e8f0a24e2bf62b941
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git checkout 6f2014d353d514e404c1f40e8f0a24e2bf62b941 tests/test_basic.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_basic.py b/tests/test_basic.py
index 64337ab38c..1fc0d67aa4 100644
--- a/tests/test_basic.py
+++ b/tests/test_basic.py
@@ -293,6 +293,7 @@ def test_session_using_session_settings(app, client):
         SESSION_COOKIE_DOMAIN=".example.com",
         SESSION_COOKIE_HTTPONLY=False,
         SESSION_COOKIE_SECURE=True,
+        SESSION_COOKIE_PARTITIONED=True,
         SESSION_COOKIE_SAMESITE="Lax",
         SESSION_COOKIE_PATH="/",
     )
@@ -315,6 +316,7 @@ def clear():
     assert "secure" in cookie
     assert "httponly" not in cookie
     assert "samesite" in cookie
+    assert "partitioned" in cookie
 
     rv = client.get("/clear", "http://www.example.com:8080/test/")
     cookie = rv.headers["set-cookie"].lower()
@@ -324,6 +326,7 @@ def clear():
     assert "path=/" in cookie
     assert "secure" in cookie
     assert "samesite" in cookie
+    assert "partitioned" in cookie
 
 
 def test_session_using_samesite_attribute(app, client):

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_basic.py
: '>>>>> End Test Output'
git checkout 6f2014d353d514e404c1f40e8f0a24e2bf62b941 tests/test_basic.py
