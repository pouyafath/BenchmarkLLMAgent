#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 4089d82159eed4027fbcde1530c9f959854d10a8
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 4089d82159eed4027fbcde1530c9f959854d10a8 tests/unit/mcpgateway/test_main.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/unit/mcpgateway/test_main.py b/tests/unit/mcpgateway/test_main.py
index f16e3526..ccf37911 100644
--- a/tests/unit/mcpgateway/test_main.py
+++ b/tests/unit/mcpgateway/test_main.py
@@ -909,6 +909,7 @@ async def dummy_post(*_args, **_kwargs):
             response = json.loads(data)
             assert response == {"jsonrpc": "2.0", "id": 1, "result": {}}
 
+    @patch("mcpgateway.main.update_url_protocol", new=lambda url: url)
     @patch("mcpgateway.main.session_registry.add_session")
     @patch("mcpgateway.main.session_registry.respond")
     @patch("mcpgateway.main.SSETransport")

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/unit/mcpgateway/test_main.py
: '>>>>> End Test Output'
git checkout 4089d82159eed4027fbcde1530c9f959854d10a8 tests/unit/mcpgateway/test_main.py
