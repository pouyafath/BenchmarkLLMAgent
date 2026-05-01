#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff c5887932a552c859376a53fb4dbe39f2ab17ba20
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout c5887932a552c859376a53fb4dbe39f2ab17ba20 tests/test_utils.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_utils.py b/tests/test_utils.py
index 6ec178b9..714c0621 100644
--- a/tests/test_utils.py
+++ b/tests/test_utils.py
@@ -150,15 +150,38 @@ def test_get_repository_config_missing(config_file):
     assert utils.get_repository_from_config(config_file, "pypi") == exp
 
 
-def test_get_repository_config_url_with_auth(config_file):
-    repository_url = "https://user:pass@notexisting.python.org/pypi"
-    exp = {
-        "repository": "https://notexisting.python.org/pypi",
-        "username": "user",
-        "password": "pass",
-    }
-    assert utils.get_repository_from_config(config_file, "foo", repository_url) == exp
-    assert utils.get_repository_from_config(config_file, "pypi", repository_url) == exp
+@pytest.mark.parametrize(
+    "repository_url, expected_config",
+    [
+        (
+            "https://user:pass@notexisting.python.org/pypi",
+            {
+                "repository": "https://notexisting.python.org/pypi",
+                "username": "user",
+                "password": "pass",
+            },
+        ),
+        (
+            "https://auser:pass@pypi.proxy.local.repo.net:8443",
+            {
+                "repository": "https://pypi.proxy.local.repo.net:8443",
+                "username": "auser",
+                "password": "pass",
+            },
+        ),
+    ],
+)
+def test_get_repository_config_url_with_auth(
+    config_file, repository_url, expected_config
+):
+    assert (
+        utils.get_repository_from_config(config_file, "foo", repository_url)
+        == expected_config
+    )
+    assert (
+        utils.get_repository_from_config(config_file, "pypi", repository_url)
+        == expected_config
+    )
 
 
 @pytest.mark.parametrize(

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_utils.py
: '>>>>> End Test Output'
git checkout c5887932a552c859376a53fb4dbe39f2ab17ba20 tests/test_utils.py
