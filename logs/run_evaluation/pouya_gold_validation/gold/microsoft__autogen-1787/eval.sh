#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff b93e2c5eb4d929a972754c5022c1eb5a1826c5c3
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout b93e2c5eb4d929a972754c5022c1eb5a1826c5c3 
git apply -v - <<'EOF_114329324912'
diff --git a/samples/tools/finetuning/tests/test_conversable_agent_update_model.py b/samples/tools/finetuning/tests/test_conversable_agent_update_model.py
new file mode 100644
index 00000000..56f9474a
--- /dev/null
+++ b/samples/tools/finetuning/tests/test_conversable_agent_update_model.py
@@ -0,0 +1,216 @@
+import pytest
+from autogen import AssistantAgent, UserProxyAgent
+import sys
+
+sys.path.append("samples/tools/finetuning")
+
+from finetuning import update_model  # noqa: E402
+from typing import Dict  # noqa: E402
+
+sys.path.append("test")
+
+TEST_CUSTOM_RESPONSE = "This is a custom response."
+TEST_LOCAL_MODEL_NAME = "local_model_name"
+
+
+def test_custom_model_client():
+    TEST_LOSS = 0.5
+
+    class UpdatableCustomModel:
+        def __init__(self, config: Dict):
+            self.model = config["model"]
+            self.model_name = config["model"]
+
+        def create(self, params):
+            from types import SimpleNamespace
+
+            response = SimpleNamespace()
+            # need to follow Client.ClientResponseProtocol
+            response.choices = []
+            choice = SimpleNamespace()
+            choice.message = SimpleNamespace()
+            choice.message.content = TEST_CUSTOM_RESPONSE
+            response.choices.append(choice)
+            response.model = self.model
+            return response
+
+        def message_retrieval(self, response):
+            return [response.choices[0].message.content]
+
+        def cost(self, response) -> float:
+            """Calculate the cost of the response."""
+            response.cost = 0
+            return 0
+
+        @staticmethod
+        def get_usage(response) -> Dict:
+            return {}
+
+        def update_model(self, preference_data, messages, **kwargs):
+            return {"loss": TEST_LOSS}
+
+    config_list = [{"model": TEST_LOCAL_MODEL_NAME, "model_client_cls": "UpdatableCustomModel"}]
+
+    assistant = AssistantAgent(
+        "assistant",
+        system_message="You are a helpful assistant.",
+        human_input_mode="NEVER",
+        llm_config={"config_list": config_list},
+    )
+    assistant.register_model_client(model_client_cls=UpdatableCustomModel)
+    user_proxy = UserProxyAgent(
+        "user_proxy",
+        human_input_mode="NEVER",
+        max_consecutive_auto_reply=1,
+        code_execution_config=False,
+        llm_config=False,
+    )
+
+    res = user_proxy.initiate_chat(assistant, message="2+2=", silent=True)
+    response_content = res.summary
+
+    assert response_content == TEST_CUSTOM_RESPONSE
+    preference_data = [("this is what the response should have been like", response_content)]
+    update_model_stats = update_model(assistant, preference_data, user_proxy)
+    assert update_model_stats["update_stats"]["loss"] == TEST_LOSS
+
+
+def test_update_model_without_client_raises_error():
+    assistant = AssistantAgent(
+        "assistant",
+        system_message="You are a helpful assistant.",
+        human_input_mode="NEVER",
+        max_consecutive_auto_reply=0,
+        llm_config=False,
+        code_execution_config=False,
+    )
+
+    user_proxy = UserProxyAgent(
+        "user_proxy",
+        human_input_mode="NEVER",
+        max_consecutive_auto_reply=1,
+        code_execution_config=False,
+        llm_config=False,
+    )
+
+    user_proxy.initiate_chat(assistant, message="2+2=", silent=True)
+    with pytest.raises(ValueError):
+        update_model(assistant, [], user_proxy)
+
+
+def test_custom_model_update_func_missing_raises_error():
+    class UpdatableCustomModel:
+        def __init__(self, config: Dict):
+            self.model = config["model"]
+            self.model_name = config["model"]
+
+        def create(self, params):
+            from types import SimpleNamespace
+
+            response = SimpleNamespace()
+            # need to follow Client.ClientResponseProtocol
+            response.choices = []
+            choice = SimpleNamespace()
+            choice.message = SimpleNamespace()
+            choice.message.content = TEST_CUSTOM_RESPONSE
+            response.choices.append(choice)
+            response.model = self.model
+            return response
+
+        def message_retrieval(self, response):
+            return [response.choices[0].message.content]
+
+        def cost(self, response) -> float:
+            """Calculate the cost of the response."""
+            response.cost = 0
+            return 0
+
+        @staticmethod
+        def get_usage(response) -> Dict:
+            return {}
+
+    config_list = [{"model": TEST_LOCAL_MODEL_NAME, "model_client_cls": "UpdatableCustomModel"}]
+
+    assistant = AssistantAgent(
+        "assistant",
+        system_message="You are a helpful assistant.",
+        human_input_mode="NEVER",
+        llm_config={"config_list": config_list},
+    )
+    assistant.register_model_client(model_client_cls=UpdatableCustomModel)
+    user_proxy = UserProxyAgent(
+        "user_proxy",
+        human_input_mode="NEVER",
+        max_consecutive_auto_reply=1,
+        code_execution_config=False,
+        llm_config=False,
+    )
+
+    res = user_proxy.initiate_chat(assistant, message="2+2=", silent=True)
+    response_content = res.summary
+
+    assert response_content == TEST_CUSTOM_RESPONSE
+
+    with pytest.raises(NotImplementedError):
+        update_model(assistant, [], user_proxy)
+
+
+def test_multiple_model_clients_raises_error():
+    class UpdatableCustomModel:
+        def __init__(self, config: Dict):
+            self.model = config["model"]
+            self.model_name = config["model"]
+
+        def create(self, params):
+            from types import SimpleNamespace
+
+            response = SimpleNamespace()
+            # need to follow Client.ClientResponseProtocol
+            response.choices = []
+            choice = SimpleNamespace()
+            choice.message = SimpleNamespace()
+            choice.message.content = TEST_CUSTOM_RESPONSE
+            response.choices.append(choice)
+            response.model = self.model
+            return response
+
+        def message_retrieval(self, response):
+            return [response.choices[0].message.content]
+
+        def cost(self, response) -> float:
+            """Calculate the cost of the response."""
+            response.cost = 0
+            return 0
+
+        @staticmethod
+        def get_usage(response) -> Dict:
+            return {}
+
+        def update_model(self, preference_data, messages, **kwargs):
+            return {}
+
+    config_list = [
+        {"model": TEST_LOCAL_MODEL_NAME, "model_client_cls": "UpdatableCustomModel"},
+        {"model": TEST_LOCAL_MODEL_NAME, "model_client_cls": "UpdatableCustomModel"},
+    ]
+
+    assistant = AssistantAgent(
+        "assistant",
+        system_message="You are a helpful assistant.",
+        human_input_mode="NEVER",
+        llm_config={"config_list": config_list},
+    )
+    assistant.register_model_client(model_client_cls=UpdatableCustomModel)
+    assistant.register_model_client(model_client_cls=UpdatableCustomModel)
+    user_proxy = UserProxyAgent(
+        "user_proxy",
+        human_input_mode="NEVER",
+        max_consecutive_auto_reply=1,
+        code_execution_config=False,
+        llm_config=False,
+    )
+
+    user_proxy.initiate_chat(assistant, message="2+2=", silent=True)
+
+    with pytest.raises(ValueError):
+        update_model(assistant, [], user_proxy)

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA samples/tools/finetuning/tests/test_conversable_agent_update_model.py
: '>>>>> End Test Output'
git checkout b93e2c5eb4d929a972754c5022c1eb5a1826c5c3 
