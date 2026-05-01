#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff a5e7169e759817ca309f8271c3c4fa79393a22f5
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout a5e7169e759817ca309f8271c3c4fa79393a22f5 tests/test_utils.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_utils.py b/tests/test_utils.py
index a714b4700e..112bbd1eaf 100644
--- a/tests/test_utils.py
+++ b/tests/test_utils.py
@@ -864,6 +864,39 @@ def QueryValueEx(key, value_name):
     assert should_bypass_proxies(url, None) == expected
 
 
+@pytest.mark.skipif(os.name != "nt", reason="Test only on Windows")
+def test_should_bypass_proxies_win_registry_bad_values(monkeypatch):
+    """Tests for function should_bypass_proxies to check if proxy
+    can be bypassed or not with Windows invalid registry settings.
+    """
+    import winreg
+
+    class RegHandle:
+        def Close(self):
+            pass
+
+    ie_settings = RegHandle()
+
+    def OpenKey(key, subkey):
+        return ie_settings
+
+    def QueryValueEx(key, value_name):
+        if key is ie_settings:
+            if value_name == "ProxyEnable":
+                # Invalid response; Should be an int or int-y value
+                return [""]
+            elif value_name == "ProxyOverride":
+                return ["192.168.*;127.0.0.1;localhost.localdomain;172.16.1.1"]
+
+    monkeypatch.setenv("http_proxy", "")
+    monkeypatch.setenv("https_proxy", "")
+    monkeypatch.setenv("no_proxy", "")
+    monkeypatch.setenv("NO_PROXY", "")
+    monkeypatch.setattr(winreg, "OpenKey", OpenKey)
+    monkeypatch.setattr(winreg, "QueryValueEx", QueryValueEx)
+    assert should_bypass_proxies("http://172.16.1.1/", None) is False
+
+
 @pytest.mark.parametrize(
     "env_name, value",
     (

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_utils.py
: '>>>>> End Test Output'
git checkout a5e7169e759817ca309f8271c3c4fa79393a22f5 tests/test_utils.py
