#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 9fffcc1b8288eabfdb42f0f89ff7e95df85f65c6
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install hatchling editables && python -m pip install -e '.[test]' --no-build-isolation && python -m pip install pexpect pyftpdlib testfixtures || python -m pip install hatchling editables && python -m pip install -e . --no-build-isolation && python -m pip install pexpect pyftpdlib testfixtures
git checkout 9fffcc1b8288eabfdb42f0f89ff7e95df85f65c6 tests/test_command_shell.py tests/test_commands.py tests/test_http_request.py tests/test_http_response.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_command_shell.py b/tests/test_command_shell.py
index 6a12f28b..b407211d 100644
--- a/tests/test_command_shell.py
+++ b/tests/test_command_shell.py
@@ -22,6 +22,12 @@ class TestShellCommand:
         _, out, _ = proc("shell", "-c", "item")
         assert "{}" in out
 
+    def test_empty_no_reactor(self) -> None:
+        _, out, _ = proc(
+            "shell", "-c", "item", "--set", "TWISTED_REACTOR_ENABLED=False"
+        )
+        assert "{}" in out
+
     def test_response_body(self, mockserver: MockServer) -> None:
         _, out, _ = proc("shell", mockserver.url("/text"), "-c", "response.body")
         assert "Works" in out
@@ -125,7 +131,6 @@ class TestShellCommand:
         assert ret == 0, err
         assert "RuntimeError: There is no current event loop in thread" not in err
 
-    @pytest.mark.xfail(reason="Not implemented yet", strict=True)
     def test_shell_fetch_no_reactor(self, mockserver: MockServer) -> None:
         url = mockserver.url("/html")
         code = f"fetch('{url}')"
@@ -134,17 +139,6 @@ class TestShellCommand:
         )
         assert ret == 0, err
 
-    def test_no_reactor_unsupported(self) -> None:
-        # to be removed when it's supported
-        ret, out, err = proc(
-            "shell", "-c", "item", "--set", "TWISTED_REACTOR_ENABLED=False"
-        )
-        assert ret == 1, out or err
-        assert (
-            "RuntimeError: scrapy shell currently doesn't support TWISTED_REACTOR_ENABLED=False"
-            in err
-        )
-
 
 class TestInteractiveShell:
     def test_fetch(self, mockserver: MockServer) -> None:
diff --git a/tests/test_commands.py b/tests/test_commands.py
index 1e91aa0b..edb03da1 100644
--- a/tests/test_commands.py
+++ b/tests/test_commands.py
@@ -378,27 +378,28 @@ class TestViewCommand:
 
 
 class TestHelpMessage(TestProjectBase):
-    COMMANDS = [
-        "parse",
-        "startproject",
-        "view",
-        "crawl",
-        "edit",
-        "list",
-        "fetch",
-        "settings",
-        "shell",
-        "runspider",
-        "version",
-        "genspider",
-        "check",
-        "bench",
-    ]
-
-    def test_help_messages(self, proj_path: Path) -> None:
-        for command in self.COMMANDS:
-            _, out, _ = proc(command, "-h", cwd=proj_path)
-            assert "Usage" in out
+    @pytest.mark.parametrize(
+        "command",
+        [
+            "parse",
+            "startproject",
+            "view",
+            "crawl",
+            "edit",
+            "list",
+            "fetch",
+            "settings",
+            "shell",
+            "runspider",
+            "version",
+            "genspider",
+            "check",
+            "bench",
+        ],
+    )
+    def test_help_messages(self, proj_path: Path, command: str) -> None:
+        _, out, _ = proc(command, "-h", cwd=proj_path)
+        assert "Usage" in out
 
 
 class TestPopCommandName:
diff --git a/tests/test_http_request.py b/tests/test_http_request.py
index 81f8fa3c..4c77bb1e 100644
--- a/tests/test_http_request.py
+++ b/tests/test_http_request.py
@@ -349,6 +349,7 @@ class TestRequest:
         assert request._flags == []
         original_flags = request.flags
         request.flags = None
+        assert request._flags is None
         assert request.flags == []
         assert request.flags is not original_flags
 
@@ -358,6 +359,7 @@ class TestRequest:
         assert request._cookies == {}
         original_cookies = request.cookies
         request.cookies = None
+        assert request._cookies is None
         assert request.cookies == {}
         assert request.cookies is not original_cookies
 
@@ -373,7 +375,9 @@ class TestRequest:
         assert isinstance(request._headers, Headers)
         original_headers = request.headers
         request.headers = None
+        assert request._headers is None
         assert request.headers == {}
+        assert request._headers == {}
         assert request.headers is not original_headers
 
     def test_no_callback(self):
diff --git a/tests/test_http_response.py b/tests/test_http_response.py
index 1becf154..09c95dc2 100644
--- a/tests/test_http_response.py
+++ b/tests/test_http_response.py
@@ -160,6 +160,53 @@ class TestResponse:
         with pytest.raises(AttributeError):
             r.body = "xxx"
 
+    def test_setter_mutable_lazy_loading(self):
+        """Mutable attributes are set internally to None only until they are
+        read, then they always return the same falsy instance of the
+        corresponding mutable structure.
+
+        Setting them to None causes the next read to return a different object.
+        """
+
+        response = self.response_class("http://example.com")
+
+        response.request = Request("http://example.com")
+
+        assert response._flags is None
+        assert response.flags == []
+        assert response.flags is response.flags
+        assert response._flags == []
+        original_flags = response.flags
+        response.flags = None
+        assert response._flags is None
+        assert response.flags == []
+        assert response.flags is not original_flags
+
+        assert response._headers is None
+        assert response.headers == {}
+        assert response.headers is response.headers
+        assert isinstance(response.headers, Headers)
+        assert isinstance(response._headers, Headers)
+        original_headers = response.headers
+        response.headers = None
+        assert response._headers is None
+        assert response.headers == {}
+        assert response._headers == {}
+        assert response.headers is not original_headers
+
+    def test_setters(self):
+        response = self.response_class("http://example.com")
+
+        response.flags = ["f1"]
+        assert response.flags == ["f1"]
+
+        headers = Headers({b"X-Test": b"1"})
+        response.headers = headers
+        assert response._headers is headers
+        response.headers = {b"A": b"b"}
+        assert isinstance(response.headers, Headers)
+        assert response._headers[b"A"] == b"b"
+
     def test_urljoin(self):
         """Test urljoin shortcut (only for existence, since behavior equals urljoin)"""
         joined = self.response_class("http://www.example.com").urljoin("/test")

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_command_shell.py tests/test_commands.py tests/test_http_request.py tests/test_http_response.py
: '>>>>> End Test Output'
git checkout 9fffcc1b8288eabfdb42f0f89ff7e95df85f65c6 tests/test_command_shell.py tests/test_commands.py tests/test_http_request.py tests/test_http_response.py
