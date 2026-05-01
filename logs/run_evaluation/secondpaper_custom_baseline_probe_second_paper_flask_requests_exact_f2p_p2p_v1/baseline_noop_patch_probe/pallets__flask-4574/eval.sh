#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 5e40aa22afb7d3809f9d9559edd9d152b7f7d025
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git checkout 5e40aa22afb7d3809f9d9559edd9d152b7f7d025 
git apply -v - <<'EOF_114329324912'
diff --git a/tests/typing/typing_error_handler.py b/tests/typing/typing_error_handler.py
new file mode 100644
index 0000000000..ec9c886f22
--- /dev/null
+++ b/tests/typing/typing_error_handler.py
@@ -0,0 +1,33 @@
+from __future__ import annotations
+
+from http import HTTPStatus
+
+from werkzeug.exceptions import BadRequest
+from werkzeug.exceptions import NotFound
+
+from flask import Flask
+
+app = Flask(__name__)
+
+
+@app.errorhandler(400)
+@app.errorhandler(HTTPStatus.BAD_REQUEST)
+@app.errorhandler(BadRequest)
+def handle_400(e: BadRequest) -> str:
+    return ""
+
+
+@app.errorhandler(ValueError)
+def handle_custom(e: ValueError) -> str:
+    return ""
+
+
+@app.errorhandler(ValueError)
+def handle_accept_base(e: Exception) -> str:
+    return ""
+
+
+@app.errorhandler(BadRequest)
+@app.errorhandler(404)
+def handle_multiple(e: BadRequest | NotFound) -> str:
+    return ""
diff --git a/tests/typing/typing_route.py b/tests/typing/typing_route.py
new file mode 100644
index 0000000000..ba49d1328e
--- /dev/null
+++ b/tests/typing/typing_route.py
@@ -0,0 +1,62 @@
+from __future__ import annotations
+
+from http import HTTPStatus
+
+from flask import Flask
+from flask import jsonify
+from flask.templating import render_template
+from flask.views import View
+from flask.wrappers import Response
+
+app = Flask(__name__)
+
+
+@app.route("/str")
+def hello_str() -> str:
+    return "<p>Hello, World!</p>"
+
+
+@app.route("/bytes")
+def hello_bytes() -> bytes:
+    return b"<p>Hello, World!</p>"
+
+
+@app.route("/json")
+def hello_json() -> Response:
+    return jsonify({"response": "Hello, World!"})
+
+
+@app.route("/status")
+@app.route("/status/<int:code>")
+def tuple_status(code: int = 200) -> tuple[str, int]:
+    return "hello", code
+
+
+@app.route("/status-enum")
+def tuple_status_enum() -> tuple[str, int]:
+    return "hello", HTTPStatus.OK
+
+
+@app.route("/headers")
+def tuple_headers() -> tuple[str, dict[str, str]]:
+    return "Hello, World!", {"Content-Type": "text/plain"}
+
+
+@app.route("/template")
+@app.route("/template/<name>")
+def return_template(name: str | None = None) -> str:
+    return render_template("index.html", name=name)
+
+
+class RenderTemplateView(View):
+    def __init__(self: RenderTemplateView, template_name: str) -> None:
+        self.template_name = template_name
+
+    def dispatch_request(self: RenderTemplateView) -> str:
+        return render_template(self.template_name)
+
+
+app.add_url_rule(
+    "/about",
+    view_func=RenderTemplateView.as_view("about_page", template_name="about.html"),
+)

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/typing/typing_error_handler.py tests/typing/typing_route.py
: '>>>>> End Test Output'
git checkout 5e40aa22afb7d3809f9d9559edd9d152b7f7d025 
