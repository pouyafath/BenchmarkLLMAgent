#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff bf0ebb8d09289a398f891964c53903f6a471d49d
source /opt/miniconda3/bin/activate
conda activate testbed
poetry install --with dev || poetry install
git checkout bf0ebb8d09289a398f891964c53903f6a471d49d tests/test_app.py tests/test_prerequisites.py tests/test_var.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_app.py b/tests/test_app.py
index 9cd0cfb5028..1e1df01bff2 100644
--- a/tests/test_app.py
+++ b/tests/test_app.py
@@ -1,7 +1,9 @@
 from __future__ import annotations
 
 import io
+import json
 import os.path
+import re
 import unittest.mock
 import uuid
 from pathlib import Path
@@ -1444,3 +1446,55 @@ def page2():
     )
     assert isinstance((third_text := page2_fragment_wrapper.children[0]), Text)
     assert str(third_text.children[0].contents) == "{`third`}"  # type: ignore
+
+
+@pytest.mark.parametrize("export", (True, False))
+def test_app_with_transpile_packages(compilable_app, export):
+    class C1(rx.Component):
+        library = "foo@1.2.3"
+        tag = "Foo"
+        transpile_packages: List[str] = ["foo"]
+
+    class C2(rx.Component):
+        library = "bar@4.5.6"
+        tag = "Bar"
+        transpile_packages: List[str] = ["bar@4.5.6"]
+
+    class C3(rx.NoSSRComponent):
+        library = "baz@7.8.10"
+        tag = "Baz"
+        transpile_packages: List[str] = ["baz@7.8.9"]
+
+    class C4(rx.NoSSRComponent):
+        library = "quuc@2.3.4"
+        tag = "Quuc"
+        transpile_packages: List[str] = ["quuc"]
+
+    class C5(rx.Component):
+        library = "quuc"
+        tag = "Quuc"
+
+    app, web_dir = compilable_app
+    page = Fragment.create(
+        C1.create(), C2.create(), C3.create(), C4.create(), C5.create()
+    )
+    app.add_page(page, route="/")
+    app.compile_(export=export)
+
+    next_config = (web_dir / "next.config.js").read_text()
+    transpile_packages_match = re.search(r"transpilePackages: (\[.*?\])", next_config)
+    transpile_packages_json = transpile_packages_match.group(1)  # type: ignore
+    transpile_packages = sorted(json.loads(transpile_packages_json))
+
+    assert transpile_packages == [
+        "bar",
+        "foo",
+        "quuc",
+    ]
+
+    if export:
+        assert 'output: "export"' in next_config
+        assert f'distDir: "{constants.Dirs.STATIC}"' in next_config
+    else:
+        assert 'output: "export"' not in next_config
+        assert f'distDir: "{constants.Dirs.STATIC}"' not in next_config
diff --git a/tests/test_prerequisites.py b/tests/test_prerequisites.py
index 711826cbcfe..28608c48c14 100644
--- a/tests/test_prerequisites.py
+++ b/tests/test_prerequisites.py
@@ -1,3 +1,5 @@
+import json
+import re
 import tempfile
 from unittest.mock import Mock, mock_open
 
@@ -61,6 +63,30 @@ def test_update_next_config(config, export, expected_output):
     assert output == expected_output
 
 
+@pytest.mark.parametrize(
+    ("transpile_packages", "expected_transpile_packages"),
+    (
+        (
+            ["foo", "@bar/baz"],
+            ["@bar/baz", "foo"],
+        ),
+        (
+            ["foo", "@bar/baz", "foo", "@bar/baz@3.2.1"],
+            ["@bar/baz", "foo"],
+        ),
+    ),
+)
+def test_transpile_packages(transpile_packages, expected_transpile_packages):
+    output = _update_next_config(
+        Config(app_name="test"),
+        transpile_packages=transpile_packages,
+    )
+    transpile_packages_match = re.search(r"transpilePackages: (\[.*?\])", output)
+    transpile_packages_json = transpile_packages_match.group(1)  # type: ignore
+    actual_transpile_packages = sorted(json.loads(transpile_packages_json))
+    assert actual_transpile_packages == expected_transpile_packages
+
+
 def test_initialize_requirements_txt_no_op(mocker):
     # File exists, reflex is included, do nothing
     mocker.patch("pathlib.Path.exists", return_value=True)
diff --git a/tests/test_var.py b/tests/test_var.py
index 61286dc8362..68271d2bad1 100644
--- a/tests/test_var.py
+++ b/tests/test_var.py
@@ -836,7 +836,7 @@ def test_state_with_initial_computed_var(
         (f"{BaseVar(_var_name='var', _var_type=str)}", "${var}"),
         (
             f"testing f-string with {BaseVar(_var_name='myvar', _var_type=int)._var_set_state('state')}",
-            'testing f-string with $<reflex.Var>{"state": "state", "interpolations": [], "imports": {"/utils/context": [{"tag": "StateContexts", "is_default": false, "alias": null, "install": true, "render": true}], "react": [{"tag": "useContext", "is_default": false, "alias": null, "install": true, "render": true}]}, "hooks": {"const state = useContext(StateContexts.state)": null}, "string_length": 13}</reflex.Var>{state.myvar}',
+            'testing f-string with $<reflex.Var>{"state": "state", "interpolations": [], "imports": {"/utils/context": [{"tag": "StateContexts", "is_default": false, "alias": null, "install": true, "render": true, "transpile": false}], "react": [{"tag": "useContext", "is_default": false, "alias": null, "install": true, "render": true, "transpile": false}]}, "hooks": {"const state = useContext(StateContexts.state)": null}, "string_length": 13}</reflex.Var>{state.myvar}',
         ),
         (
             f"testing local f-string {BaseVar(_var_name='x', _var_is_local=True, _var_type=str)}",

EOF_114329324912
: '>>>>> Start Test Output'
poetry run pytest -rA tests tests/test_app.py tests/test_prerequisites.py tests/test_var.py
: '>>>>> End Test Output'
git checkout bf0ebb8d09289a398f891964c53903f6a471d49d tests/test_app.py tests/test_prerequisites.py tests/test_var.py
