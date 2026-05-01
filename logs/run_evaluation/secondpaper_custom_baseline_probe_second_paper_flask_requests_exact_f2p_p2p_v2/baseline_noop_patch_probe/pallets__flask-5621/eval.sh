#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 7522c4bcdb10449dc919e0ffbdebb92fe66822b5
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git checkout 7522c4bcdb10449dc919e0ffbdebb92fe66822b5 tests/test_basic.py tests/typing/typing_app_decorators.py tests/typing/typing_error_handler.py tests/typing/typing_route.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_basic.py b/tests/test_basic.py
index 1fc0d67aa4..842321ceeb 100644
--- a/tests/test_basic.py
+++ b/tests/test_basic.py
@@ -1,5 +1,6 @@
 import gc
 import re
+import typing as t
 import uuid
 import warnings
 import weakref
@@ -369,6 +370,27 @@ def expect_exception(f, *args, **kwargs):
         expect_exception(flask.session.pop, "foo")
 
 
+def test_session_secret_key_fallbacks(app, client) -> None:
+    @app.post("/")
+    def set_session() -> str:
+        flask.session["a"] = 1
+        return ""
+
+    @app.get("/")
+    def get_session() -> dict[str, t.Any]:
+        return dict(flask.session)
+
+    # Set session with initial secret key
+    client.post()
+    assert client.get().json == {"a": 1}
+    # Change secret key, session can't be loaded and appears empty
+    app.secret_key = "new test key"
+    assert client.get().json == {}
+    # Add initial secret key as fallback, session can be loaded
+    app.config["SECRET_KEY_FALLBACKS"] = ["test key"]
+    assert client.get().json == {"a": 1}
+
+
 def test_session_expiration(app, client):
     permanent = True
 
diff --git a/tests/typing/typing_app_decorators.py b/tests/type_check/typing_app_decorators.py
similarity index 100%
rename from tests/typing/typing_app_decorators.py
rename to tests/type_check/typing_app_decorators.py
diff --git a/tests/typing/typing_error_handler.py b/tests/type_check/typing_error_handler.py
similarity index 100%
rename from tests/typing/typing_error_handler.py
rename to tests/type_check/typing_error_handler.py
diff --git a/tests/typing/typing_route.py b/tests/type_check/typing_route.py
similarity index 100%
rename from tests/typing/typing_route.py
rename to tests/type_check/typing_route.py

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_basic.py tests/type_check/typing_app_decorators.py tests/type_check/typing_error_handler.py tests/type_check/typing_route.py
: '>>>>> End Test Output'
git checkout 7522c4bcdb10449dc919e0ffbdebb92fe66822b5 tests/test_basic.py tests/typing/typing_app_decorators.py tests/typing/typing_error_handler.py tests/typing/typing_route.py
