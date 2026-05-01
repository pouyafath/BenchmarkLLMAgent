#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 3435d2ff1589eb0c1a85cc294a20985910a1a606
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git checkout 3435d2ff1589eb0c1a85cc294a20985910a1a606 tests/test_cli.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_cli.py b/tests/test_cli.py
index 79de1fc8d1..09995488cc 100644
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -679,3 +679,8 @@ def test_cli_empty(app):
 
     result = app.test_cli_runner().invoke(args=["blue", "--help"])
     assert result.exit_code == 2, f"Unexpected success:\n\n{result.output}"
+
+
+def test_run_exclude_patterns():
+    ctx = run_command.make_context("run", ["--exclude-patterns", __file__])
+    assert ctx.params["exclude_patterns"] == [__file__]

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_cli.py
: '>>>>> End Test Output'
git checkout 3435d2ff1589eb0c1a85cc294a20985910a1a606 tests/test_cli.py
