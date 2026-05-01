#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 0107b52d5a7dc0125f9a155338bff1c08511bc23
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 0107b52d5a7dc0125f9a155338bff1c08511bc23 test/agentchat/test_conversable_agent.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/agentchat/test_conversable_agent.py b/test/agentchat/test_conversable_agent.py
index 64b8473c..8ff8038d 100644
--- a/test/agentchat/test_conversable_agent.py
+++ b/test/agentchat/test_conversable_agent.py
@@ -13,6 +13,7 @@ from typing_extensions import Annotated
 import autogen
 
 from autogen.agentchat import ConversableAgent, UserProxyAgent
+from autogen.agentchat.conversable_agent import register_function
 from test_assistant_agent import KEY_LOC, OAI_CONFIG_LIST
 from conftest import skip_openai
 
@@ -823,6 +824,47 @@ def test_register_for_execution():
         assert get_origin(user_proxy_1.function_map) == expected_function_map
 
 
+def test_register_functions():
+    with pytest.MonkeyPatch.context() as mp:
+        mp.setenv("OPENAI_API_KEY", "mock")
+        agent = ConversableAgent(name="agent", llm_config={"config_list": []})
+        user_proxy = UserProxyAgent(name="user_proxy")
+
+        def exec_python(cell: Annotated[str, "Valid Python cell to execute."]) -> str:
+            pass
+
+        register_function(
+            exec_python,
+            caller=agent,
+            executor=user_proxy,
+            description="run cell in ipython and return the execution result.",
+        )
+
+        expected_function_map = {"exec_python": exec_python}
+        assert get_origin(user_proxy.function_map) == expected_function_map
+
+        expected = [
+            {
+                "type": "function",
+                "function": {
+                    "description": "run cell in ipython and return the execution result.",
+                    "name": "exec_python",
+                    "parameters": {
+                        "type": "object",
+                        "properties": {
+                            "cell": {
+                                "type": "string",
+                                "description": "Valid Python cell to execute.",
+                            }
+                        },
+                        "required": ["cell"],
+                    },
+                },
+            }
+        ]
+        assert agent.llm_config["tools"] == expected
+
+
 @pytest.mark.skipif(
     skip or not sys.version.startswith("3.10"),
     reason="do not run if openai is not installed or py!=3.10",
@@ -860,7 +902,7 @@ def test_function_registration_e2e_sync() -> None:
     timer_mock = unittest.mock.MagicMock()
     stopwatch_mock = unittest.mock.MagicMock()
 
-    # An example async function
+    # An example async function registered using decorators
     @user_proxy.register_for_execution()
     @coder.register_for_llm(description="create a timer for N seconds")
     def timer(num_seconds: Annotated[str, "Number of seconds in the timer."]) -> str:
@@ -873,9 +915,7 @@ def test_function_registration_e2e_sync() -> None:
         timer_mock(num_seconds=num_seconds)
         return "Timer is done!"
 
-    # An example sync function
-    @user_proxy.register_for_execution()
-    @coder.register_for_llm(description="create a stopwatch for N seconds")
+    # An example sync function registered using register_function
     def stopwatch(num_seconds: Annotated[str, "Number of seconds in the stopwatch."]) -> str:
         print("stopwatch is running")
         # assert False, "stopwatch's alive!"
@@ -887,6 +927,8 @@ def test_function_registration_e2e_sync() -> None:
         stopwatch_mock(num_seconds=num_seconds)
         return "Stopwatch is done!"
 
+    register_function(stopwatch, caller=coder, executor=user_proxy, description="create a stopwatch for N seconds")
+
     # start the conversation
     # 'await' is used to pause and resume code execution for async IO operations.
     # Without 'await', an async function returns a coroutine object but doesn't execute the function.
@@ -938,9 +980,7 @@ async def test_function_registration_e2e_async() -> None:
     timer_mock = unittest.mock.MagicMock()
     stopwatch_mock = unittest.mock.MagicMock()
 
-    # An example async function
-    @user_proxy.register_for_execution()
-    @coder.register_for_llm(description="create a timer for N seconds")
+    # An example async function registered using register_function
     async def timer(num_seconds: Annotated[str, "Number of seconds in the timer."]) -> str:
         print("timer is running")
         for i in range(int(num_seconds)):
@@ -951,7 +991,9 @@ async def test_function_registration_e2e_async() -> None:
         timer_mock(num_seconds=num_seconds)
         return "Timer is done!"
 
-    # An example sync function
+    register_function(timer, caller=coder, executor=user_proxy, description="create a timer for N seconds")
+
+    # An example sync function registered using decorators
     @user_proxy.register_for_execution()
     @coder.register_for_llm(description="create a stopwatch for N seconds")
     def stopwatch(num_seconds: Annotated[str, "Number of seconds in the stopwatch."]) -> str:
diff --git a/test/agentchat/test_function_and_tool_calling.py b/test/agentchat/test_function_and_tool_calling.py
new file mode 100644
index 00000000..893fbe35
--- /dev/null
+++ b/test/agentchat/test_function_and_tool_calling.py
@@ -0,0 +1,378 @@
+import json
+from typing import Any, Callable, Dict, List
+
+import pytest
+
+from autogen.agentchat.conversable_agent import ConversableAgent
+
+
+def _tool_func_1(arg1: str, arg2: str) -> str:
+    return f"_tool_func_1: {arg1} {arg2}"
+
+
+def _tool_func_2(arg1: str, arg2: str) -> str:
+    return f"_tool_func_2: {arg1} {arg2}"
+
+
+def _tool_func_error(arg1: str, arg2: str) -> str:
+    raise RuntimeError("Error in tool function")
+
+
+async def _a_tool_func_1(arg1: str, arg2: str) -> str:
+    return f"_tool_func_1: {arg1} {arg2}"
+
+
+async def _a_tool_func_2(arg1: str, arg2: str) -> str:
+    return f"_tool_func_2: {arg1} {arg2}"
+
+
+async def _a_tool_func_error(arg1: str, arg2: str) -> str:
+    raise RuntimeError("Error in tool function")
+
+
+_tool_use_message_1 = {
+    "role": "assistant",
+    "content": None,
+    "tool_calls": [
+        {
+            "id": "1",
+            "type": "function",
+            "function": {
+                "name": "_tool_func_1",
+                "arguments": json.dumps({"arg1": "value1", "arg2": "value2"}),
+            },
+        },
+        {
+            "id": "2",
+            "type": "function",
+            "function": {
+                "name": "_tool_func_2",
+                "arguments": json.dumps({"arg1": "value3", "arg2": "value4"}),
+            },
+        },
+    ],
+}
+
+_tool_use_message_1_bad_json = {
+    "role": "assistant",
+    "content": None,
+    "tool_calls": [
+        {
+            "id": "1",
+            "type": "function",
+            "function": {
+                "name": "_tool_func_1",
+                # add extra comma to make json invalid
+                "arguments": json.dumps({"arg1": "value3", "arg2": "value4"})[:-1] + ",}",
+            },
+        },
+        {
+            "id": "2",
+            "type": "function",
+            "function": {
+                "name": "_tool_func_2",
+                "arguments": json.dumps({"arg1": "value3", "arg2": "value4"}),
+            },
+        },
+    ],
+}
+
+_tool_use_message_1_expected_reply = {
+    "role": "tool",
+    "tool_responses": [
+        {"tool_call_id": "1", "role": "tool", "content": "_tool_func_1: value1 value2"},
+        {"tool_call_id": "2", "role": "tool", "content": "_tool_func_2: value3 value4"},
+    ],
+    # "content": "Tool Call Id: 1\n_tool_func_1: value1 value2\n\nTool Call Id: 2\n_tool_func_2: value3 value4",
+    "content": "_tool_func_1: value1 value2\n\n_tool_func_2: value3 value4",
+}
+
+
+_tool_use_message_1_bad_json_expected_reply = {
+    "role": "tool",
+    "tool_responses": [
+        {
+            "tool_call_id": "1",
+            "role": "tool",
+            "content": "Error: Expecting property name enclosed in double quotes: line 1 column 37 (char 36)\n You argument should follow json format.",
+        },
+        {"tool_call_id": "2", "role": "tool", "content": "_tool_func_2: value3 value4"},
+    ],
+    "content": "Error: Expecting property name enclosed in double quotes: line 1 column 37 (char 36)\n You argument should follow json format.\n\n_tool_func_2: value3 value4",
+}
+
+_tool_use_message_1_error_expected_reply = {
+    "role": "tool",
+    "tool_responses": [
+        {"tool_call_id": "1", "role": "tool", "content": "_tool_func_1: value1 value2"},
+        {
+            "tool_call_id": "2",
+            "role": "tool",
+            "content": "Error: Error in tool function",
+        },
+    ],
+    "content": "_tool_func_1: value1 value2\n\nError: Error in tool function",
+}
+
+_tool_use_message_1_not_found_expected_reply = {
+    "role": "tool",
+    "tool_responses": [
+        {"tool_call_id": "1", "role": "tool", "content": "_tool_func_1: value1 value2"},
+        {
+            "tool_call_id": "2",
+            "role": "tool",
+            "content": "Error: Function _tool_func_2 not found.",
+        },
+    ],
+    "content": "_tool_func_1: value1 value2\n\nError: Function _tool_func_2 not found.",
+}
+
+_function_use_message_1 = {
+    "role": "assistant",
+    "content": None,
+    "function_call": {
+        "name": "_tool_func_1",
+        "arguments": json.dumps({"arg1": "value1", "arg2": "value2"}),
+    },
+}
+
+_function_use_message_1_bad_json = {
+    "role": "assistant",
+    "content": None,
+    "function_call": {
+        "name": "_tool_func_1",
+        "arguments": json.dumps({"arg1": "value1", "arg2": "value2"})[:-1] + ",}",
+    },
+}
+
+_function_use_message_1_expected_reply = {
+    "name": "_tool_func_1",
+    "role": "function",
+    "content": "_tool_func_1: value1 value2",
+}
+
+_function_use_message_1_bad_json_expected_reply = {
+    "name": "_tool_func_1",
+    "role": "function",
+    "content": "Error: Expecting property name enclosed in double quotes: line 1 column 37 (char 36)\n You argument should follow json format.",
+}
+
+_function_use_message_1_error_expected_reply = {
+    "name": "_tool_func_1",
+    "role": "function",
+    "content": "Error: Error in tool function",
+}
+
+_function_use_message_1_not_found_expected_reply = {
+    "name": "_tool_func_1",
+    "role": "function",
+    "content": "Error: Function _tool_func_1 not found.",
+}
+
+_text_message = {"content": "Hi!", "role": "user"}
+
+
+def _get_function_map(is_function_async: bool, drop_tool_2: bool = False) -> Dict[str, Callable[..., Any]]:
+    if is_function_async:
+        return (
+            {
+                "_tool_func_1": _a_tool_func_1,
+                "_tool_func_2": _a_tool_func_2,
+            }
+            if not drop_tool_2
+            else {
+                "_tool_func_1": _a_tool_func_1,
+            }
+        )
+    else:
+        return (
+            {
+                "_tool_func_1": _tool_func_1,
+                "_tool_func_2": _tool_func_2,
+            }
+            if not drop_tool_2
+            else {
+                "_tool_func_1": _tool_func_1,
+            }
+        )
+
+
+def _get_error_function_map(
+    is_function_async: bool, error_on_tool_func_2: bool = True
+) -> Dict[str, Callable[..., Any]]:
+    if is_function_async:
+        return {
+            "_tool_func_1": _a_tool_func_1 if error_on_tool_func_2 else _a_tool_func_error,
+            "_tool_func_2": _a_tool_func_error if error_on_tool_func_2 else _a_tool_func_2,
+        }
+    else:
+        return {
+            "_tool_func_1": _tool_func_1 if error_on_tool_func_2 else _tool_func_error,
+            "_tool_func_2": _tool_func_error if error_on_tool_func_2 else _tool_func_2,
+        }
+
+
+@pytest.mark.parametrize("is_function_async", [True, False])
+def test_generate_function_call_reply_on_function_call_message(is_function_async: bool) -> None:
+    agent = ConversableAgent(name="agent", llm_config=False)
+
+    # empty function_map
+    agent._function_map = {}
+    messages = [_function_use_message_1]
+    finished, retval = agent.generate_function_call_reply(messages)
+    assert (finished, retval) == (True, _function_use_message_1_not_found_expected_reply)
+
+    # function map set
+    agent._function_map = _get_function_map(is_function_async)
+
+    # correct function call, multiple times to make sure cleanups are done properly
+    for _ in range(3):
+        messages = [_function_use_message_1]
+        finished, retval = agent.generate_function_call_reply(messages)
+        assert (finished, retval) == (True, _function_use_message_1_expected_reply)
+
+    # bad JSON
+    messages = [_function_use_message_1_bad_json]
+    finished, retval = agent.generate_function_call_reply(messages)
+    assert (finished, retval) == (True, _function_use_message_1_bad_json_expected_reply)
+
+    # tool call
+    messages = [_tool_use_message_1]
+    finished, retval = agent.generate_function_call_reply(messages)
+    assert (finished, retval) == (False, None)
+
+    # text message
+    messages: List[Dict[str, str]] = [_text_message]
+    finished, retval = agent.generate_function_call_reply(messages)
+    assert (finished, retval) == (False, None)
+
+    # error in function (raises Exception)
+    agent._function_map = _get_error_function_map(is_function_async, error_on_tool_func_2=False)
+    messages = [_function_use_message_1]
+    finished, retval = agent.generate_function_call_reply(messages)
+    assert (finished, retval) == (True, _function_use_message_1_error_expected_reply)
+
+
+@pytest.mark.asyncio()
+@pytest.mark.parametrize("is_function_async", [True, False])
+async def test_a_generate_function_call_reply_on_function_call_message(is_function_async: bool) -> None:
+    agent = ConversableAgent(name="agent", llm_config=False)
+
+    # empty function_map
+    agent._function_map = {}
+    messages = [_function_use_message_1]
+    finished, retval = await agent.a_generate_function_call_reply(messages)
+    assert (finished, retval) == (True, _function_use_message_1_not_found_expected_reply)
+
+    # function map set
+    agent._function_map = _get_function_map(is_function_async)
+
+    # correct function call, multiple times to make sure cleanups are done properly
+    for _ in range(3):
+        messages = [_function_use_message_1]
+        finished, retval = await agent.a_generate_function_call_reply(messages)
+        assert (finished, retval) == (True, _function_use_message_1_expected_reply)
+
+    # bad JSON
+    messages = [_function_use_message_1_bad_json]
+    finished, retval = await agent.a_generate_function_call_reply(messages)
+    assert (finished, retval) == (True, _function_use_message_1_bad_json_expected_reply)
+
+    # tool call
+    messages = [_tool_use_message_1]
+    finished, retval = await agent.a_generate_function_call_reply(messages)
+    assert (finished, retval) == (False, None)
+
+    # text message
+    messages: List[Dict[str, str]] = [_text_message]
+    finished, retval = await agent.a_generate_function_call_reply(messages)
+    assert (finished, retval) == (False, None)
+
+    # error in function (raises Exception)
+    agent._function_map = _get_error_function_map(is_function_async, error_on_tool_func_2=False)
+    messages = [_function_use_message_1]
+    finished, retval = await agent.a_generate_function_call_reply(messages)
+    assert (finished, retval) == (True, _function_use_message_1_error_expected_reply)
+
+
+@pytest.mark.parametrize("is_function_async", [True, False])
+def test_generate_tool_calls_reply_on_function_call_message(is_function_async: bool) -> None:
+    agent = ConversableAgent(name="agent", llm_config=False)
+
+    # empty function_map
+    agent._function_map = _get_function_map(is_function_async, drop_tool_2=True)
+    messages = [_tool_use_message_1]
+    finished, retval = agent.generate_tool_calls_reply(messages)
+    assert (finished, retval) == (True, _tool_use_message_1_not_found_expected_reply)
+
+    # function map set
+    agent._function_map = _get_function_map(is_function_async)
+
+    # correct function call, multiple times to make sure cleanups are done properly
+    for _ in range(3):
+        messages = [_tool_use_message_1]
+        finished, retval = agent.generate_tool_calls_reply(messages)
+        assert (finished, retval) == (True, _tool_use_message_1_expected_reply)
+
+    # bad JSON
+    messages = [_tool_use_message_1_bad_json]
+    finished, retval = agent.generate_tool_calls_reply(messages)
+    assert (finished, retval) == (True, _tool_use_message_1_bad_json_expected_reply)
+
+    # function call
+    messages = [_function_use_message_1]
+    finished, retval = agent.generate_tool_calls_reply(messages)
+    assert (finished, retval) == (False, None)
+
+    # text message
+    messages: List[Dict[str, str]] = [_text_message]
+    finished, retval = agent.generate_tool_calls_reply(messages)
+    assert (finished, retval) == (False, None)
+
+    # error in function (raises Exception)
+    agent._function_map = _get_error_function_map(is_function_async)
+    messages = [_tool_use_message_1]
+    finished, retval = agent.generate_tool_calls_reply(messages)
+    assert (finished, retval) == (True, _tool_use_message_1_error_expected_reply)
+
+
+@pytest.mark.asyncio()
+@pytest.mark.parametrize("is_function_async", [True, False])
+async def test_a_generate_tool_calls_reply_on_function_call_message(is_function_async: bool) -> None:
+    agent = ConversableAgent(name="agent", llm_config=False)
+
+    # empty function_map
+    agent._function_map = _get_function_map(is_function_async, drop_tool_2=True)
+    messages = [_tool_use_message_1]
+    finished, retval = await agent.a_generate_tool_calls_reply(messages)
+    assert (finished, retval) == (True, _tool_use_message_1_not_found_expected_reply)
+
+    # function map set
+    agent._function_map = _get_function_map(is_function_async)
+
+    # correct function call, multiple times to make sure cleanups are done properly
+    for _ in range(3):
+        messages = [_tool_use_message_1]
+        finished, retval = await agent.a_generate_tool_calls_reply(messages)
+        assert (finished, retval) == (True, _tool_use_message_1_expected_reply)
+
+    # bad JSON
+    messages = [_tool_use_message_1_bad_json]
+    finished, retval = await agent.a_generate_tool_calls_reply(messages)
+    assert (finished, retval) == (True, _tool_use_message_1_bad_json_expected_reply)
+
+    # function call
+    messages = [_function_use_message_1]
+    finished, retval = await agent.a_generate_tool_calls_reply(messages)
+    assert (finished, retval) == (False, None)
+
+    # text message
+    messages: List[Dict[str, str]] = [_text_message]
+    finished, retval = await agent.a_generate_tool_calls_reply(messages)
+    assert (finished, retval) == (False, None)
+
+    # error in function (raises Exception)
+    agent._function_map = _get_error_function_map(is_function_async)
+    messages = [_tool_use_message_1]
+    finished, retval = await agent.a_generate_tool_calls_reply(messages)
+    assert (finished, retval) == (True, _tool_use_message_1_error_expected_reply)
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/agentchat/test_conversable_agent.py test/agentchat/test_function_and_tool_calling.py
: '>>>>> End Test Output'
git checkout 0107b52d5a7dc0125f9a155338bff1c08511bc23 test/agentchat/test_conversable_agent.py
