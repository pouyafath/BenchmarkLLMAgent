#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 5d81ed43f30976f93e7fd79cb725fdd9b2da5228
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 5d81ed43f30976f93e7fd79cb725fdd9b2da5228 test/agentchat/contrib/test_lmm.py test/agentchat/contrib/test_web_surfer.py test/agentchat/test_groupchat.py test/agentchat/test_tool_calls.py test/test_graph_utils.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/agentchat/contrib/test_lmm.py b/test/agentchat/contrib/test_lmm.py
index 41513397..866f8a74 100644
--- a/test/agentchat/contrib/test_lmm.py
+++ b/test/agentchat/contrib/test_lmm.py
@@ -4,7 +4,7 @@ from unittest.mock import MagicMock
 import pytest
 
 import autogen
-from autogen.agentchat.agent import Agent
+from autogen.agentchat.conversable_agent import ConversableAgent
 
 try:
     from autogen.agentchat.contrib.multimodal_conversable_agent import MultimodalConversableAgent
@@ -72,7 +72,7 @@ class TestMultimodalConversableAgent(unittest.TestCase):
         self.assertDictEqual(self.agent._message_to_dict(message_dict), message_dict)
 
     def test_print_received_message(self):
-        sender = Agent(name="SenderAgent")
+        sender = ConversableAgent(name="SenderAgent", llm_config=False, code_execution_config=False)
         message_str = "Hello"
         self.agent._print_received_message = MagicMock()  # Mocking print method to avoid actual print
         self.agent._print_received_message(message_str, sender)
diff --git a/test/agentchat/contrib/test_web_surfer.py b/test/agentchat/contrib/test_web_surfer.py
index 307abefe..abf7903d 100644
--- a/test/agentchat/contrib/test_web_surfer.py
+++ b/test/agentchat/contrib/test_web_surfer.py
@@ -2,8 +2,9 @@ import os
 import sys
 import re
 import pytest
-from autogen import ConversableAgent, UserProxyAgent, config_list_from_json
+from autogen import UserProxyAgent, config_list_from_json
 from autogen.oai.openai_utils import filter_config
+from autogen.cache import Cache
 
 sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))
 from conftest import skip_openai  # noqa: E402
@@ -44,70 +45,76 @@ if not skip_oai:
     skip_all,
     reason="do not run if dependency is not installed",
 )
-def test_web_surfer():
-    page_size = 4096
-    web_surfer = WebSurferAgent("web_surfer", llm_config=False, browser_config={"viewport_size": page_size})
-
-    # Sneak a peak at the function map, allowing us to call the functions for testing here
-    function_map = web_surfer._user_proxy._function_map
-
-    # Test some basic navigations
-    response = function_map["visit_page"](BLOG_POST_URL)
-    assert f"Address: {BLOG_POST_URL}".strip() in response
-    assert f"Title: {BLOG_POST_TITLE}".strip() in response
+def test_web_surfer() -> None:
+    with pytest.MonkeyPatch.context() as mp:
+        # we mock the API key so we can register functions (llm_config must be present for this to work)
+        mp.setenv("OPENAI_API_KEY", "mock")
+        page_size = 4096
+        web_surfer = WebSurferAgent(
+            "web_surfer", llm_config={"config_list": []}, browser_config={"viewport_size": page_size}
+        )
+
+        # Sneak a peak at the function map, allowing us to call the functions for testing here
+        function_map = web_surfer._user_proxy._function_map
+
+        # Test some basic navigations
+        response = function_map["visit_page"](BLOG_POST_URL)
+        assert f"Address: {BLOG_POST_URL}".strip() in response
+        assert f"Title: {BLOG_POST_TITLE}".strip() in response
+
+        # Test scrolling
+        m = re.search(r"\bViewport position: Showing page 1 of (\d+).", response)
+        total_pages = int(m.group(1))  # type: ignore[union-attr]
 
-    # Test scrolling
-    m = re.search(r"\bViewport position: Showing page 1 of (\d+).", response)
-    total_pages = int(m.group(1))
-
-    response = function_map["page_down"]()
-    assert (
-        f"Viewport position: Showing page 2 of {total_pages}." in response
-    )  # Assumes the content is longer than one screen
+        response = function_map["page_down"]()
+        assert (
+            f"Viewport position: Showing page 2 of {total_pages}." in response
+        )  # Assumes the content is longer than one screen
 
-    response = function_map["page_up"]()
-    assert f"Viewport position: Showing page 1 of {total_pages}." in response
+        response = function_map["page_up"]()
+        assert f"Viewport position: Showing page 1 of {total_pages}." in response
 
-    # Try to scroll too far back up
-    response = function_map["page_up"]()
-    assert f"Viewport position: Showing page 1 of {total_pages}." in response
+        # Try to scroll too far back up
+        response = function_map["page_up"]()
+        assert f"Viewport position: Showing page 1 of {total_pages}." in response
 
-    # Try to scroll too far down
-    for i in range(0, total_pages + 1):
-        response = function_map["page_down"]()
-    assert f"Viewport position: Showing page {total_pages} of {total_pages}." in response
+        # Try to scroll too far down
+        for i in range(0, total_pages + 1):
+            response = function_map["page_down"]()
+        assert f"Viewport position: Showing page {total_pages} of {total_pages}." in response
 
-    # Test web search -- we don't have a key in this case, so we expect it to raise an error (but it means the code path is correct)
-    with pytest.raises(ValueError, match="Missing Bing API key."):
-        response = function_map["informational_web_search"](BING_QUERY)
+        # Test web search -- we don't have a key in this case, so we expect it to raise an error (but it means the code path is correct)
+        with pytest.raises(ValueError, match="Missing Bing API key."):
+            response = function_map["informational_web_search"](BING_QUERY)
 
-    with pytest.raises(ValueError, match="Missing Bing API key."):
-        response = function_map["navigational_web_search"](BING_QUERY)
+        with pytest.raises(ValueError, match="Missing Bing API key."):
+            response = function_map["navigational_web_search"](BING_QUERY)
 
-    # Test Q&A and summarization -- we don't have a key so we expect it to fail (but it means the code path is correct)
-    with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'create'"):
-        response = function_map["answer_from_page"]("When was it founded?")
+        # Test Q&A and summarization -- we don't have a key so we expect it to fail (but it means the code path is correct)
+        with pytest.raises(IndexError):
+            response = function_map["answer_from_page"]("When was it founded?")
 
-    with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'create'"):
-        response = function_map["summarize_page"]()
+        with pytest.raises(IndexError):
+            response = function_map["summarize_page"]()
 
 
 @pytest.mark.skipif(
     skip_oai,
     reason="do not run if oai is not installed",
 )
-def test_web_surfer_oai():
-    llm_config = {"config_list": config_list, "timeout": 180, "cache_seed": None}
+def test_web_surfer_oai() -> None:
+    llm_config = {"config_list": config_list, "timeout": 180, "cache_seed": 42}
+
+    # adding Azure name variations to the model list
+    model = ["gpt-3.5-turbo-1106", "gpt-3.5-turbo-16k-0613", "gpt-3.5-turbo-16k"]
+    model += [m.replace(".", "") for m in model]
 
     summarizer_llm_config = {
-        "config_list": filter_config(
-            config_list, {"model": ["gpt-3.5-turbo-1106", "gpt-3.5-turbo-16k-0613", "gpt-3.5-turbo-16k"]}
-        ),
+        "config_list": filter_config(config_list, dict(model=model)),  # type: ignore[no-untyped-call]
         "timeout": 180,
-        "cache_seed": None,
     }
 
-    assert len(llm_config["config_list"]) > 0
+    assert len(llm_config["config_list"]) > 0  # type: ignore[arg-type]
     assert len(summarizer_llm_config["config_list"]) > 0
 
     page_size = 4096
@@ -126,27 +133,35 @@ def test_web_surfer_oai():
         is_termination_msg=lambda x: True,
     )
 
-    # Make some requests that should test function calling
-    user_proxy.initiate_chat(web_surfer, message="Please visit the page 'https://en.wikipedia.org/wiki/Microsoft'")
+    with Cache.disk():
+        # Make some requests that should test function calling
+        user_proxy.initiate_chat(web_surfer, message="Please visit the page 'https://en.wikipedia.org/wiki/Microsoft'")
 
-    user_proxy.initiate_chat(web_surfer, message="Please scroll down.")
+        user_proxy.initiate_chat(web_surfer, message="Please scroll down.")
 
-    user_proxy.initiate_chat(web_surfer, message="Please scroll up.")
+        user_proxy.initiate_chat(web_surfer, message="Please scroll up.")
 
-    user_proxy.initiate_chat(web_surfer, message="When was it founded?")
+        user_proxy.initiate_chat(web_surfer, message="When was it founded?")
 
-    user_proxy.initiate_chat(web_surfer, message="What's this page about?")
+        user_proxy.initiate_chat(web_surfer, message="What's this page about?")
 
 
 @pytest.mark.skipif(
     skip_bing,
     reason="do not run if bing api key is not available",
 )
-def test_web_surfer_bing():
+def test_web_surfer_bing() -> None:
     page_size = 4096
     web_surfer = WebSurferAgent(
         "web_surfer",
-        llm_config=False,
+        llm_config={
+            "config_list": [
+                {
+                    "model": "gpt-3.5-turbo-16k",
+                    "api_key": "sk-PLACEHOLDER_KEY",
+                }
+            ]
+        },
         browser_config={"viewport_size": page_size, "bing_api_key": BING_API_KEY},
     )
 
@@ -168,5 +183,5 @@ def test_web_surfer_bing():
 if __name__ == "__main__":
     """Runs this file's tests from the command line."""
     test_web_surfer()
-    # test_web_surfer_oai()
-    # test_web_surfer_bing()
+    test_web_surfer_oai()
+    test_web_surfer_bing()
diff --git a/test/agentchat/test_groupchat.py b/test/agentchat/test_groupchat.py
index b11c371b..1d340127 100644
--- a/test/agentchat/test_groupchat.py
+++ b/test/agentchat/test_groupchat.py
@@ -489,7 +489,7 @@ def test_selection_helpers():
 
 
 def test_init_default_parameters():
-    agents = [Agent(name=f"Agent{i}") for i in range(3)]
+    agents = [autogen.ConversableAgent(name=f"Agent{i}", llm_config=False) for i in range(3)]
     group_chat = GroupChat(agents=agents, messages=[], max_round=3)
     for agent in agents:
         assert set([a.name for a in group_chat.allowed_speaker_transitions_dict[agent]]) == set(
@@ -498,7 +498,7 @@ def test_init_default_parameters():
 
 
 def test_graph_parameters():
-    agents = [Agent(name=f"Agent{i}") for i in range(3)]
+    agents = [autogen.ConversableAgent(name=f"Agent{i}", llm_config=False) for i in range(3)]
     with pytest.raises(ValueError):
         GroupChat(
             agents=agents,
diff --git a/test/agentchat/test_tool_calls.py b/test/agentchat/test_tool_calls.py
index 55e891fc..21596ced 100644
--- a/test/agentchat/test_tool_calls.py
+++ b/test/agentchat/test_tool_calls.py
@@ -194,9 +194,17 @@ def test_update_tool():
 def test_multi_tool_call():
     class FakeAgent(autogen.Agent):
         def __init__(self, name):
-            super().__init__(name)
+            self._name = name
             self.received = []
 
+        @property
+        def name(self):
+            return self._name
+
+        @property
+        def description(self):
+            return self._name
+
         def receive(
             self,
             message,
@@ -281,9 +289,17 @@ def test_multi_tool_call():
 async def test_async_multi_tool_call():
     class FakeAgent(autogen.Agent):
         def __init__(self, name):
-            super().__init__(name)
+            self._name = name
             self.received = []
 
+        @property
+        def name(self):
+            return self._name
+
+        @property
+        def description(self):
+            return self._name
+
         async def a_receive(
             self,
             message,
diff --git a/test/coding/test_commandline_code_executor.py b/test/coding/test_commandline_code_executor.py
new file mode 100644
index 00000000..1ee5e6be
--- /dev/null
+++ b/test/coding/test_commandline_code_executor.py
@@ -0,0 +1,179 @@
+import sys
+import tempfile
+import pytest
+from autogen.agentchat.conversable_agent import ConversableAgent
+from autogen.coding.base import CodeBlock, CodeExecutor
+from autogen.coding.factory import CodeExecutorFactory
+from autogen.coding.local_commandline_code_executor import LocalCommandlineCodeExecutor
+from autogen.oai.openai_utils import config_list_from_json
+
+from conftest import skip_openai
+
+
+def test_create() -> None:
+    config = {"executor": "commandline-local"}
+    executor = CodeExecutorFactory.create(config)
+    assert isinstance(executor, LocalCommandlineCodeExecutor)
+
+    config = {"executor": LocalCommandlineCodeExecutor()}
+    executor = CodeExecutorFactory.create(config)
+    assert executor is config["executor"]
+
+
+def test_local_commandline_executor_init() -> None:
+    executor = LocalCommandlineCodeExecutor(timeout=10, work_dir=".")
+    assert executor.timeout == 10 and executor.work_dir == "."
+
+    # Try invalid working directory.
+    with pytest.raises(ValueError, match="Working directory .* does not exist."):
+        executor = LocalCommandlineCodeExecutor(timeout=111, work_dir="/invalid/directory")
+
+
+def test_local_commandline_executor_execute_code() -> None:
+    with tempfile.TemporaryDirectory() as temp_dir:
+        executor = LocalCommandlineCodeExecutor(work_dir=temp_dir)
+        _test_execute_code(executor=executor)
+
+
+def _test_execute_code(executor: CodeExecutor) -> None:
+    # Test single code block.
+    code_blocks = [CodeBlock(code="import sys; print('hello world!')", language="python")]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code == 0 and "hello world!" in code_result.output and code_result.code_file is not None
+
+    # Test multiple code blocks.
+    code_blocks = [
+        CodeBlock(code="import sys; print('hello world!')", language="python"),
+        CodeBlock(code="a = 100 + 100; print(a)", language="python"),
+    ]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert (
+        code_result.exit_code == 0
+        and "hello world!" in code_result.output
+        and "200" in code_result.output
+        and code_result.code_file is not None
+    )
+
+    # Test bash script.
+    if sys.platform not in ["win32"]:
+        code_blocks = [CodeBlock(code="echo 'hello world!'", language="bash")]
+        code_result = executor.execute_code_blocks(code_blocks)
+        assert code_result.exit_code == 0 and "hello world!" in code_result.output and code_result.code_file is not None
+
+    # Test running code.
+    file_lines = ["import sys", "print('hello world!')", "a = 100 + 100", "print(a)"]
+    code_blocks = [CodeBlock(code="\n".join(file_lines), language="python")]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert (
+        code_result.exit_code == 0
+        and "hello world!" in code_result.output
+        and "200" in code_result.output
+        and code_result.code_file is not None
+    )
+
+    # Check saved code file.
+    with open(code_result.code_file) as f:
+        code_lines = f.readlines()
+        for file_line, code_line in zip(file_lines, code_lines):
+            assert file_line.strip() == code_line.strip()
+
+
+@pytest.mark.skipif(sys.platform in ["win32"], reason="do not run on windows")
+def test_local_commandline_code_executor_timeout() -> None:
+    with tempfile.TemporaryDirectory() as temp_dir:
+        executor = LocalCommandlineCodeExecutor(timeout=1, work_dir=temp_dir)
+        _test_timeout(executor)
+
+
+def _test_timeout(executor: CodeExecutor) -> None:
+    code_blocks = [CodeBlock(code="import time; time.sleep(10); print('hello world!')", language="python")]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code and "Timeout" in code_result.output
+
+
+def test_local_commandline_code_executor_restart() -> None:
+    executor = LocalCommandlineCodeExecutor()
+    _test_restart(executor)
+
+
+def _test_restart(executor: CodeExecutor) -> None:
+    # Check warning.
+    with pytest.warns(UserWarning, match=r".*No action is taken."):
+        executor.restart()
+
+
+@pytest.mark.skipif(skip_openai, reason="requested to skip openai tests")
+def test_local_commandline_executor_conversable_agent_capability() -> None:
+    with tempfile.TemporaryDirectory() as temp_dir:
+        executor = LocalCommandlineCodeExecutor(work_dir=temp_dir)
+        _test_conversable_agent_capability(executor=executor)
+
+
+def _test_conversable_agent_capability(executor: CodeExecutor) -> None:
+    KEY_LOC = "notebook"
+    OAI_CONFIG_LIST = "OAI_CONFIG_LIST"
+    config_list = config_list_from_json(
+        OAI_CONFIG_LIST,
+        file_location=KEY_LOC,
+        filter_dict={
+            "model": {
+                "gpt-3.5-turbo",
+                "gpt-35-turbo",
+            },
+        },
+    )
+    llm_config = {"config_list": config_list}
+    agent = ConversableAgent(
+        "coding_agent",
+        llm_config=llm_config,
+        code_execution_config=False,
+    )
+    executor.user_capability.add_to_agent(agent)
+
+    # Test updated system prompt.
+    assert executor.DEFAULT_SYSTEM_MESSAGE_UPDATE in agent.system_message
+
+    # Test code generation.
+    reply = agent.generate_reply(
+        [{"role": "user", "content": "write a python script to print 'hello world' to the console"}],
+        sender=ConversableAgent(name="user", llm_config=False, code_execution_config=False),
+    )
+
+    # Test code extraction.
+    code_blocks = executor.code_extractor.extract_code_blocks(reply)  # type: ignore[arg-type]
+    assert len(code_blocks) == 1 and code_blocks[0].language == "python"
+
+    # Test code execution.
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code == 0 and "hello world" in code_result.output.lower().replace(",", "")
+
+
+def test_local_commandline_executor_conversable_agent_code_execution() -> None:
+    with tempfile.TemporaryDirectory() as temp_dir:
+        executor = LocalCommandlineCodeExecutor(work_dir=temp_dir)
+        with pytest.MonkeyPatch.context() as mp:
+            mp.setenv("OPENAI_API_KEY", "mock")
+            _test_conversable_agent_code_execution(executor)
+
+
+def _test_conversable_agent_code_execution(executor: CodeExecutor) -> None:
+    agent = ConversableAgent(
+        "user_proxy",
+        code_execution_config={"executor": executor},
+        llm_config=False,
+    )
+
+    assert agent.code_executor is executor
+
+    message = """
+    Example:
+    ```python
+    print("hello extract code")
+    ```
+    """
+
+    reply = agent.generate_reply(
+        [{"role": "user", "content": message}],
+        sender=ConversableAgent("user", llm_config=False, code_execution_config=False),
+    )
+    assert "hello extract code" in reply  # type: ignore[operator]
diff --git a/test/coding/test_embedded_ipython_code_executor.py b/test/coding/test_embedded_ipython_code_executor.py
new file mode 100644
index 00000000..d1669096
--- /dev/null
+++ b/test/coding/test_embedded_ipython_code_executor.py
@@ -0,0 +1,219 @@
+import os
+import tempfile
+from typing import Dict, Union
+import uuid
+import pytest
+from autogen.agentchat.conversable_agent import ConversableAgent
+from autogen.coding.base import CodeBlock, CodeExecutor
+from autogen.coding.factory import CodeExecutorFactory
+from autogen.oai.openai_utils import config_list_from_json
+from conftest import skip_openai  # noqa: E402
+
+try:
+    from autogen.coding.embedded_ipython_code_executor import EmbeddedIPythonCodeExecutor
+
+    skip = False
+    skip_reason = ""
+except ImportError:
+    skip = True
+    skip_reason = "Dependencies for EmbeddedIPythonCodeExecutor not installed."
+
+
+@pytest.mark.skipif(skip, reason=skip_reason)
+def test_create() -> None:
+    config: Dict[str, Union[str, CodeExecutor]] = {"executor": "ipython-embedded"}
+    executor = CodeExecutorFactory.create(config)
+    assert isinstance(executor, EmbeddedIPythonCodeExecutor)
+
+    config = {"executor": EmbeddedIPythonCodeExecutor()}
+    executor = CodeExecutorFactory.create(config)
+    assert executor is config["executor"]
+
+
+@pytest.mark.skipif(skip, reason=skip_reason)
+def test_init() -> None:
+    executor = EmbeddedIPythonCodeExecutor(timeout=10, kernel_name="python3", output_dir=".")
+    assert executor.timeout == 10 and executor.kernel_name == "python3" and executor.output_dir == "."
+
+    # Try invalid output directory.
+    with pytest.raises(ValueError, match="Output directory .* does not exist."):
+        executor = EmbeddedIPythonCodeExecutor(timeout=111, kernel_name="python3", output_dir="/invalid/directory")
+
+    # Try invalid kernel name.
+    with pytest.raises(ValueError, match="Kernel .* is not installed."):
+        executor = EmbeddedIPythonCodeExecutor(timeout=111, kernel_name="invalid_kernel_name", output_dir=".")
+
+
+@pytest.mark.skipif(skip, reason=skip_reason)
+def test_execute_code_single_code_block() -> None:
+    executor = EmbeddedIPythonCodeExecutor()
+    code_blocks = [CodeBlock(code="import sys\nprint('hello world!')", language="python")]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code == 0 and "hello world!" in code_result.output
+
+
+@pytest.mark.skipif(skip, reason=skip_reason)
+def test_execute_code_multiple_code_blocks() -> None:
+    executor = EmbeddedIPythonCodeExecutor()
+    code_blocks = [
+        CodeBlock(code="import sys\na = 123 + 123\n", language="python"),
+        CodeBlock(code="print(a)", language="python"),
+    ]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code == 0 and "246" in code_result.output
+
+    msg = """
+def test_function(a, b):
+    return a + b
+"""
+    code_blocks = [
+        CodeBlock(code=msg, language="python"),
+        CodeBlock(code="test_function(431, 423)", language="python"),
+    ]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code == 0 and "854" in code_result.output
+
+
+@pytest.mark.skipif(skip, reason=skip_reason)
+def test_execute_code_bash_script() -> None:
+    executor = EmbeddedIPythonCodeExecutor()
+    # Test bash script.
+    code_blocks = [CodeBlock(code='!echo "hello world!"', language="bash")]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code == 0 and "hello world!" in code_result.output
+
+
+@pytest.mark.skipif(skip, reason=skip_reason)
+def test_timeout() -> None:
+    executor = EmbeddedIPythonCodeExecutor(timeout=1)
+    code_blocks = [CodeBlock(code="import time; time.sleep(10); print('hello world!')", language="python")]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code and "Timeout" in code_result.output
+
+
+@pytest.mark.skipif(skip, reason=skip_reason)
+def test_silent_pip_install() -> None:
+    executor = EmbeddedIPythonCodeExecutor()
+    code_blocks = [CodeBlock(code="!pip install matplotlib numpy", language="python")]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code == 0 and code_result.output.strip() == ""
+
+    none_existing_package = uuid.uuid4().hex
+    code_blocks = [CodeBlock(code=f"!pip install matplotlib_{none_existing_package}", language="python")]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code == 0 and "ERROR: " in code_result.output
+
+
+@pytest.mark.skipif(skip, reason=skip_reason)
+def test_restart() -> None:
+    executor = EmbeddedIPythonCodeExecutor()
+    code_blocks = [CodeBlock(code="x = 123", language="python")]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code == 0 and code_result.output.strip() == ""
+
+    executor.restart()
+    code_blocks = [CodeBlock(code="print(x)", language="python")]
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code and "NameError" in code_result.output
+
+
+@pytest.mark.skipif(skip, reason=skip_reason)
+def test_save_image() -> None:
+    with tempfile.TemporaryDirectory() as temp_dir:
+        executor = EmbeddedIPythonCodeExecutor(output_dir=temp_dir)
+        # Install matplotlib.
+        code_blocks = [CodeBlock(code="!pip install matplotlib", language="python")]
+        code_result = executor.execute_code_blocks(code_blocks)
+        assert code_result.exit_code == 0 and code_result.output.strip() == ""
+
+        # Test saving image.
+        code_blocks = [
+            CodeBlock(code="import matplotlib.pyplot as plt\nplt.plot([1, 2, 3, 4])\nplt.show()", language="python")
+        ]
+        code_result = executor.execute_code_blocks(code_blocks)
+        assert code_result.exit_code == 0
+        assert os.path.exists(code_result.output_files[0])
+        assert f"Image data saved to {code_result.output_files[0]}" in code_result.output
+
+
+@pytest.mark.skipif(skip, reason=skip_reason)
+def test_save_html() -> None:
+    with tempfile.TemporaryDirectory() as temp_dir:
+        executor = EmbeddedIPythonCodeExecutor(output_dir=temp_dir)
+        # Test saving html.
+        code_blocks = [
+            CodeBlock(code="from IPython.display import HTML\nHTML('<h1>Hello, world!</h1>')", language="python")
+        ]
+        code_result = executor.execute_code_blocks(code_blocks)
+        assert code_result.exit_code == 0
+        assert os.path.exists(code_result.output_files[0])
+        assert f"HTML data saved to {code_result.output_files[0]}" in code_result.output
+
+
+@pytest.mark.skipif(skip, reason=skip_reason)
+@pytest.mark.skipif(skip_openai, reason="openai not installed OR requested to skip")
+def test_conversable_agent_capability() -> None:
+    KEY_LOC = "notebook"
+    OAI_CONFIG_LIST = "OAI_CONFIG_LIST"
+    config_list = config_list_from_json(
+        OAI_CONFIG_LIST,
+        file_location=KEY_LOC,
+        filter_dict={
+            "model": {
+                "gpt-3.5-turbo",
+                "gpt-35-turbo",
+            },
+        },
+    )
+    llm_config = {"config_list": config_list}
+    agent = ConversableAgent(
+        "coding_agent",
+        llm_config=llm_config,
+        code_execution_config=False,
+    )
+    executor = EmbeddedIPythonCodeExecutor()
+    executor.user_capability.add_to_agent(agent)
+
+    # Test updated system prompt.
+    assert executor.DEFAULT_SYSTEM_MESSAGE_UPDATE in agent.system_message
+
+    # Test code generation.
+    reply = agent.generate_reply(
+        [{"role": "user", "content": "print 'hello world' to the console in a single python code block"}],
+        sender=ConversableAgent("user", llm_config=False, code_execution_config=False),
+    )
+
+    # Test code extraction.
+    code_blocks = executor.code_extractor.extract_code_blocks(reply)  # type: ignore[arg-type]
+    assert len(code_blocks) == 1 and code_blocks[0].language == "python"
+
+    # Test code execution.
+    code_result = executor.execute_code_blocks(code_blocks)
+    assert code_result.exit_code == 0 and "hello world" in code_result.output.lower()
+
+
+@pytest.mark.skipif(skip, reason=skip_reason)
+def test_conversable_agent_code_execution() -> None:
+    agent = ConversableAgent(
+        "user_proxy",
+        llm_config=False,
+        code_execution_config={"executor": "ipython-embedded"},
+    )
+    msg = """
+Run this code:
+```python
+def test_function(a, b):
+    return a * b
+```
+And then this:
+```python
+print(test_function(123, 4))
+```
+"""
+    with pytest.MonkeyPatch.context() as mp:
+        mp.setenv("OPENAI_API_KEY", "mock")
+        reply = agent.generate_reply(
+            [{"role": "user", "content": msg}],
+            sender=ConversableAgent("user", llm_config=False, code_execution_config=False),
+        )
+        assert "492" in reply  # type: ignore[operator]
diff --git a/test/coding/test_factory.py b/test/coding/test_factory.py
new file mode 100644
index 00000000..a4f40ec9
--- /dev/null
+++ b/test/coding/test_factory.py
@@ -0,0 +1,12 @@
+import pytest
+from autogen.coding.factory import CodeExecutorFactory
+
+
+def test_create_unknown() -> None:
+    config = {"executor": "unknown"}
+    with pytest.raises(ValueError, match="Unknown code executor unknown"):
+        CodeExecutorFactory.create(config)
+
+    config = {}
+    with pytest.raises(ValueError, match="Unknown code executor None"):
+        CodeExecutorFactory.create(config)
diff --git a/test/coding/test_markdown_code_extractor.py b/test/coding/test_markdown_code_extractor.py
new file mode 100644
index 00000000..4185d675
--- /dev/null
+++ b/test/coding/test_markdown_code_extractor.py
@@ -0,0 +1,115 @@
+from autogen.coding import MarkdownCodeExtractor
+
+_message_1 = """
+Example:
+```
+print("hello extract code")
+```
+"""
+
+_message_2 = """Example:
+```python
+def scrape(url):
+    import requests
+    from bs4 import BeautifulSoup
+    response = requests.get(url)
+    soup = BeautifulSoup(response.text, "html.parser")
+    title = soup.find("title").text
+    text = soup.find("div", {"id": "bodyContent"}).text
+    return title, text
+```
+Test:
+```python
+url = "https://en.wikipedia.org/wiki/Web_scraping"
+title, text = scrape(url)
+print(f"Title: {title}")
+print(f"Text: {text}")
+```
+"""
+
+_message_3 = """
+Example:
+   ```python
+   def scrape(url):
+       import requests
+       from bs4 import BeautifulSoup
+       response = requests.get(url)
+       soup = BeautifulSoup(response.text, "html.parser")
+       title = soup.find("title").text
+       text = soup.find("div", {"id": "bodyContent"}).text
+       return title, text
+   ```
+"""
+
+_message_4 = """
+Example:
+``` python
+def scrape(url):
+   import requests
+   from bs4 import BeautifulSoup
+   response = requests.get(url)
+   soup = BeautifulSoup(response.text, "html.parser")
+   title = soup.find("title").text
+   text = soup.find("div", {"id": "bodyContent"}).text
+   return title, text
+```
+""".replace(
+    "\n", "\r\n"
+)
+
+_message_5 = """
+Test bash script:
+```bash
+echo 'hello world!'
+```
+"""
+
+_message_6 = """
+Test some C# code, expecting ""
+```
+using System;
+using System.Collections.Generic;
+using System.Linq;
+using System.Text;
+
+namespace ConsoleApplication1
+{
+    class Program
+    {
+        static void Main(string[] args)
+        {
+            Console.WriteLine("Hello World");
+        }
+    }
+}
+```
+"""
+
+_message_7 = """
+Test some message that has no code block.
+"""
+
+
+def test_extract_code() -> None:
+    extractor = MarkdownCodeExtractor()
+
+    code_blocks = extractor.extract_code_blocks(_message_1)
+    assert len(code_blocks) == 1 and code_blocks[0].language == "python"
+
+    code_blocks = extractor.extract_code_blocks(_message_2)
+    assert len(code_blocks) == 2 and code_blocks[0].language == "python" and code_blocks[1].language == "python"
+
+    code_blocks = extractor.extract_code_blocks(_message_3)
+    assert len(code_blocks) == 1 and code_blocks[0].language == "python"
+
+    code_blocks = extractor.extract_code_blocks(_message_4)
+    assert len(code_blocks) == 1 and code_blocks[0].language == "python"
+
+    code_blocks = extractor.extract_code_blocks(_message_5)
+    assert len(code_blocks) == 1 and code_blocks[0].language == "bash"
+
+    code_blocks = extractor.extract_code_blocks(_message_6)
+    assert len(code_blocks) == 1 and code_blocks[0].language == ""
+
+    code_blocks = extractor.extract_code_blocks(_message_7)
+    assert len(code_blocks) == 0
diff --git a/test/test_graph_utils.py b/test/test_graph_utils.py
index 8518d0da..5bdcab3c 100644
--- a/test/test_graph_utils.py
+++ b/test/test_graph_utils.py
@@ -1,13 +1,23 @@
+from typing import Any
 import pytest
 import logging
 from autogen.agentchat import Agent
 import autogen.graph_utils as gru
 
 
+class FakeAgent(Agent):
+    def __init__(self, name) -> None:
+        self._name = name
+
+    @property
+    def name(self) -> str:
+        return self._name
+
+
 class TestHelpers:
     def test_has_self_loops(self):
         # Setup test data
-        agents = [Agent(name=f"Agent{i}") for i in range(3)]
+        agents = [FakeAgent(name=f"Agent{i}") for i in range(3)]
         allowed_speaker_transitions = {
             agents[0]: [agents[1], agents[2]],
             agents[1]: [agents[2]],
@@ -26,19 +36,19 @@ class TestHelpers:
 
 class TestGraphUtilCheckGraphValidity:
     def test_valid_structure(self):
-        agents = [Agent("agent1"), Agent("agent2"), Agent("agent3")]
+        agents = [FakeAgent("agent1"), FakeAgent("agent2"), FakeAgent("agent3")]
         valid_speaker_transitions_dict = {agent: [other_agent for other_agent in agents] for agent in agents}
         gru.check_graph_validity(allowed_speaker_transitions_dict=valid_speaker_transitions_dict, agents=agents)
 
     def test_graph_with_invalid_structure(self):
-        agents = [Agent("agent1"), Agent("agent2"), Agent("agent3")]
-        unseen_agent = Agent("unseen_agent")
+        agents = [FakeAgent("agent1"), FakeAgent("agent2"), FakeAgent("agent3")]
+        unseen_agent = FakeAgent("unseen_agent")
         invalid_speaker_transitions_dict = {unseen_agent: ["stranger"]}
         with pytest.raises(ValueError):
             gru.check_graph_validity(invalid_speaker_transitions_dict, agents)
 
     def test_graph_with_invalid_string(self):
-        agents = [Agent("agent1"), Agent("agent2"), Agent("agent3")]
+        agents = [FakeAgent("agent1"), FakeAgent("agent2"), FakeAgent("agent3")]
         invalid_speaker_transitions_dict = {
             agent: ["agent1"] for agent in agents
         }  # 'agent1' is a string, not an Agent. Therefore raises an error.
@@ -46,13 +56,13 @@ class TestGraphUtilCheckGraphValidity:
             gru.check_graph_validity(invalid_speaker_transitions_dict, agents)
 
     def test_graph_with_invalid_key(self):
-        agents = [Agent("agent1"), Agent("agent2"), Agent("agent3")]
+        agents = [FakeAgent("agent1"), FakeAgent("agent2"), FakeAgent("agent3")]
         with pytest.raises(ValueError):
             gru.check_graph_validity({1: 1}, agents)
 
     # Test for Warning 1: Isolated agent nodes
     def test_isolated_agent_nodes_warning(self, caplog):
-        agents = [Agent("agent1"), Agent("agent2"), Agent("agent3")]
+        agents = [FakeAgent("agent1"), FakeAgent("agent2"), FakeAgent("agent3")]
         # Create a speaker_transitions_dict where at least one agent is isolated
         speaker_transitions_dict_with_isolation = {agents[0]: [agents[0], agents[1]], agents[1]: [agents[0]]}
         # Add an isolated agent
@@ -66,14 +76,14 @@ class TestGraphUtilCheckGraphValidity:
 
     # Test for Warning 2: Warning if the set of agents in allowed_speaker_transitions do not match agents
     def test_warning_for_mismatch_in_agents(self, caplog):
-        agents = [Agent("agent1"), Agent("agent2"), Agent("agent3")]
+        agents = [FakeAgent("agent1"), FakeAgent("agent2"), FakeAgent("agent3")]
 
         # Test with missing agents in allowed_speaker_transitions_dict
 
         unknown_agent_dict = {
             agents[0]: [agents[0], agents[1], agents[2]],
             agents[1]: [agents[0], agents[1], agents[2]],
-            agents[2]: [agents[0], agents[1], agents[2], Agent("unknown_agent")],
+            agents[2]: [agents[0], agents[1], agents[2], FakeAgent("unknown_agent")],
         }
 
         with caplog.at_level(logging.WARNING):
@@ -83,7 +93,7 @@ class TestGraphUtilCheckGraphValidity:
 
     # Test for Warning 3: Warning if there is duplicated agents in allowed_speaker_transitions_dict
     def test_warning_for_duplicate_agents(self, caplog):
-        agents = [Agent("agent1"), Agent("agent2"), Agent("agent3")]
+        agents = [FakeAgent("agent1"), FakeAgent("agent2"), FakeAgent("agent3")]
 
         # Construct an `allowed_speaker_transitions_dict` with duplicated agents
         duplicate_agents_dict = {
@@ -100,7 +110,7 @@ class TestGraphUtilCheckGraphValidity:
 
 class TestGraphUtilInvertDisallowedToAllowed:
     def test_basic_functionality(self):
-        agents = [Agent("agent1"), Agent("agent2"), Agent("agent3")]
+        agents = [FakeAgent("agent1"), FakeAgent("agent2"), FakeAgent("agent3")]
         disallowed_graph = {agents[0]: [agents[1]], agents[1]: [agents[0], agents[2]], agents[2]: []}
         expected_allowed_graph = {
             agents[0]: [agents[0], agents[2]],
@@ -113,7 +123,7 @@ class TestGraphUtilInvertDisallowedToAllowed:
         assert inverted == expected_allowed_graph
 
     def test_empty_disallowed_graph(self):
-        agents = [Agent("agent1"), Agent("agent2"), Agent("agent3")]
+        agents = [FakeAgent("agent1"), FakeAgent("agent2"), FakeAgent("agent3")]
         disallowed_graph = {}
         expected_allowed_graph = {
             agents[0]: [agents[0], agents[1], agents[2]],
@@ -126,7 +136,7 @@ class TestGraphUtilInvertDisallowedToAllowed:
         assert inverted == expected_allowed_graph
 
     def test_fully_disallowed_graph(self):
-        agents = [Agent("agent1"), Agent("agent2"), Agent("agent3")]
+        agents = [FakeAgent("agent1"), FakeAgent("agent2"), FakeAgent("agent3")]
 
         disallowed_graph = {
             agents[0]: [agents[0], agents[1], agents[2]],
@@ -140,9 +150,9 @@ class TestGraphUtilInvertDisallowedToAllowed:
         assert inverted == expected_allowed_graph
 
     def test_disallowed_graph_with_nonexistent_agent(self):
-        agents = [Agent("agent1"), Agent("agent2"), Agent("agent3")]
+        agents = [FakeAgent("agent1"), FakeAgent("agent2"), FakeAgent("agent3")]
 
-        disallowed_graph = {agents[0]: [Agent("nonexistent_agent")]}
+        disallowed_graph = {agents[0]: [FakeAgent("nonexistent_agent")]}
         # In this case, the function should ignore the nonexistent agent and proceed with the inversion
         expected_allowed_graph = {
             agents[0]: [agents[0], agents[1], agents[2]],

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/agentchat/contrib/test_lmm.py test/agentchat/contrib/test_web_surfer.py test/agentchat/test_groupchat.py test/agentchat/test_tool_calls.py test/coding/test_commandline_code_executor.py test/coding/test_embedded_ipython_code_executor.py test/coding/test_factory.py test/coding/test_markdown_code_extractor.py test/test_graph_utils.py
: '>>>>> End Test Output'
git checkout 5d81ed43f30976f93e7fd79cb725fdd9b2da5228 test/agentchat/contrib/test_lmm.py test/agentchat/contrib/test_web_surfer.py test/agentchat/test_groupchat.py test/agentchat/test_tool_calls.py test/test_graph_utils.py
