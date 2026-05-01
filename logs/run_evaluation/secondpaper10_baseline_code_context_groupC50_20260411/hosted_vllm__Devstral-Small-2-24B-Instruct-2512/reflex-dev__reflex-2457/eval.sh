#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 4219a78e7c404a223ad791f3a9a4130b416a8418
source /opt/miniconda3/bin/activate
conda activate testbed
poetry install --with dev || poetry install
git checkout 4219a78e7c404a223ad791f3a9a4130b416a8418 tests/test_config.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_config.py b/tests/test_config.py
index bc35314122c..1ba2f548dea 100644
--- a/tests/test_config.py
+++ b/tests/test_config.py
@@ -1,3 +1,4 @@
+import multiprocessing
 import os
 from typing import Any, Dict
 
@@ -200,3 +201,21 @@ def test_replace_defaults(
     c._set_persistent(**set_persistent_vars)
     for key, value in exp_config_values.items():
         assert getattr(c, key) == value
+
+
+def reflex_dir_constant():
+    return rx.constants.Reflex.DIR
+
+
+def test_reflex_dir_env_var(monkeypatch, tmp_path):
+    """Test that the REFLEX_DIR environment variable is used to set the Reflex.DIR constant.
+
+    Args:
+        monkeypatch: The pytest monkeypatch object.
+        tmp_path: The pytest tmp_path object.
+    """
+    monkeypatch.setenv("REFLEX_DIR", str(tmp_path))
+
+    mp_ctx = multiprocessing.get_context(method="spawn")
+    with mp_ctx.Pool(processes=1) as pool:
+        assert pool.apply(reflex_dir_constant) == str(tmp_path)

EOF_114329324912
: '>>>>> Start Test Output'
poetry run pytest -rA tests tests/test_config.py
: '>>>>> End Test Output'
git checkout 4219a78e7c404a223ad791f3a9a4130b416a8418 tests/test_config.py
