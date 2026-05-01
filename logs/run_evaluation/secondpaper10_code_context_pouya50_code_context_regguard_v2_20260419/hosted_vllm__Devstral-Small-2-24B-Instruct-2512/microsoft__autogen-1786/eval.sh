#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff c6f6707f4da1ade4449a999b17d31e65ae2c66b5
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]' || python -m pip install -e .
git checkout c6f6707f4da1ade4449a999b17d31e65ae2c66b5 test/agentchat/test_conversable_agent.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/agentchat/test_conversable_agent.py b/test/agentchat/test_conversable_agent.py
index 2a5eaf5f..df6a06a7 100644
--- a/test/agentchat/test_conversable_agent.py
+++ b/test/agentchat/test_conversable_agent.py
@@ -559,6 +559,16 @@ def test_update_function_signature_and_register_functions() -> None:
         assert agent.function_map["python"] == exec_python
         assert agent.function_map["sh"] == exec_sh
 
+        # remove the functions
+        agent.register_function(
+            function_map={
+                "python": None,
+            }
+        )
+
+        assert set(agent.function_map.keys()) == {"sh"}
+        assert agent.function_map["sh"] == exec_sh
+
 
 def test__wrap_function_sync():
     CurrencySymbol = Literal["USD", "EUR"]

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/agentchat/test_conversable_agent.py
: '>>>>> End Test Output'
git checkout c6f6707f4da1ade4449a999b17d31e65ae2c66b5 test/agentchat/test_conversable_agent.py
