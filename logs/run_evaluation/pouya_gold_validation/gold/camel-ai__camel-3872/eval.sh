#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 4a8b2667ac66c830c256a9ef33a034fa79c940e8
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install hatchling editables && python -m pip install -e '.[test]' --no-build-isolation
git checkout 4a8b2667ac66c830c256a9ef33a034fa79c940e8 test/agents/test_chat_agent.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/agents/test_chat_agent.py b/test/agents/test_chat_agent.py
index 058db434..1d771a74 100644
--- a/test/agents/test_chat_agent.py
+++ b/test/agents/test_chat_agent.py
@@ -15,7 +15,7 @@ import asyncio
 import json
 from copy import deepcopy
 from io import BytesIO
-from typing import List
+from typing import List, Literal
 from unittest.mock import AsyncMock, MagicMock
 
 import pytest
@@ -589,6 +589,351 @@ async def test_chat_agent_astep_with_external_tools(step_call_count=3):
         ), f"Error in calling round {i + 1}"
 
 
+def _mock_completion_with_usage(
+    response_id: str,
+    *,
+    finish_reason: Literal[
+        "stop", "length", "tool_calls", "content_filter", "function_call"
+    ],
+    content: str | None,
+    created: int,
+    prompt_tokens: int,
+    completion_tokens: int,
+    total_tokens: int,
+    tool_call: ChatCompletionMessageFunctionToolCall | None = None,
+) -> ChatCompletion:
+    return ChatCompletion(
+        id=response_id,
+        choices=[
+            Choice(
+                finish_reason=finish_reason,
+                index=0,
+                logprobs=None,
+                message=ChatCompletionMessage(
+                    content=content,
+                    role="assistant",
+                    function_call=None,
+                    tool_calls=[tool_call] if tool_call else None,
+                ),
+            )
+        ],
+        created=created,
+        model="gpt-5-mini",
+        object="chat.completion",
+        usage=CompletionUsage(
+            completion_tokens=completion_tokens,
+            prompt_tokens=prompt_tokens,
+            total_tokens=total_tokens,
+        ),
+    )
+
+
+def _assert_request_usage_event(
+    event: dict,
+    *,
+    request_index: int,
+    response_id: str,
+    request_total_tokens: int,
+    step_total_tokens: int,
+) -> None:
+    assert event["request_index"] == request_index
+    assert event["response_id"] == response_id
+    assert event["request_usage"]["total_tokens"] == request_total_tokens
+    assert event["step_usage"]["total_tokens"] == step_total_tokens
+
+
+@pytest.mark.model_backend
+def test_chat_agent_step_on_request_usage_callback():
+    model = ModelFactory.create(
+        model_platform=ModelPlatformType.OPENAI,
+        model_type=ModelType.GPT_5_MINI,
+    )
+
+    def add(a: int, b: int) -> int:
+        return a + b
+
+    request_events = []
+
+    first_response = _mock_completion_with_usage(
+        "mock_step_usage_1",
+        finish_reason="tool_calls",
+        content=None,
+        created=123456789,
+        prompt_tokens=10,
+        completion_tokens=3,
+        total_tokens=13,
+        tool_call=ChatCompletionMessageFunctionToolCall(
+            id="call_mock_add_1",
+            function=Function(arguments='{"a": 1, "b": 2}', name="add"),
+            type="function",
+        ),
+    )
+    second_response = _mock_completion_with_usage(
+        "mock_step_usage_2",
+        finish_reason="stop",
+        content="The result is 3.",
+        created=123456790,
+        prompt_tokens=20,
+        completion_tokens=4,
+        total_tokens=24,
+    )
+    model.run = MagicMock(side_effect=[first_response, second_response])
+
+    agent = ChatAgent(
+        system_message="You are a helpful assistant.",
+        model=model,
+        tools=[FunctionTool(add)],
+        on_request_usage=lambda payload: request_events.append(payload),
+    )
+    response = agent.step("Please add 1 and 2.")
+
+    assert len(request_events) == 2
+    _assert_request_usage_event(
+        request_events[0],
+        request_index=1,
+        response_id="mock_step_usage_1",
+        request_total_tokens=13,
+        step_total_tokens=13,
+    )
+    _assert_request_usage_event(
+        request_events[1],
+        request_index=2,
+        response_id="mock_step_usage_2",
+        request_total_tokens=24,
+        step_total_tokens=37,
+    )
+    assert response.info["usage"]["total_tokens"] == 37
+
+
+@pytest.mark.model_backend
+@pytest.mark.asyncio
+async def test_chat_agent_astep_on_request_usage_callback():
+    model = ModelFactory.create(
+        model_platform=ModelPlatformType.OPENAI,
+        model_type=ModelType.GPT_5_MINI,
+    )
+
+    def add(a: int, b: int) -> int:
+        return a + b
+
+    request_events = []
+
+    async def on_request_usage(payload):
+        request_events.append(payload)
+
+    first_response = _mock_completion_with_usage(
+        "mock_astep_usage_1",
+        finish_reason="tool_calls",
+        content=None,
+        created=123456791,
+        prompt_tokens=12,
+        completion_tokens=5,
+        total_tokens=17,
+        tool_call=ChatCompletionMessageFunctionToolCall(
+            id="call_mock_add_2",
+            function=Function(arguments='{"a": 2, "b": 3}', name="add"),
+            type="function",
+        ),
+    )
+    second_response = _mock_completion_with_usage(
+        "mock_astep_usage_2",
+        finish_reason="stop",
+        content="The result is 5.",
+        created=123456792,
+        prompt_tokens=18,
+        completion_tokens=6,
+        total_tokens=24,
+    )
+    model.arun = AsyncMock(side_effect=[first_response, second_response])
+
+    agent = ChatAgent(
+        system_message="You are a helpful assistant.",
+        model=model,
+        tools=[FunctionTool(add)],
+        on_request_usage=on_request_usage,
+    )
+    response = await agent.astep("Please add 2 and 3.")
+
+    assert len(request_events) == 2
+    _assert_request_usage_event(
+        request_events[0],
+        request_index=1,
+        response_id="mock_astep_usage_1",
+        request_total_tokens=17,
+        step_total_tokens=17,
+    )
+    _assert_request_usage_event(
+        request_events[1],
+        request_index=2,
+        response_id="mock_astep_usage_2",
+        request_total_tokens=24,
+        step_total_tokens=41,
+    )
+    assert response.info["usage"]["total_tokens"] == 41
+
+
+@pytest.mark.model_backend
+def test_chat_agent_stream_step_on_request_usage_callback():
+    from openai.types.chat.chat_completion_chunk import (
+        ChatCompletionChunk,
+        ChoiceDelta,
+    )
+    from openai.types.chat.chat_completion_chunk import (
+        Choice as ChunkChoice,
+    )
+
+    model = ModelFactory.create(
+        model_platform=ModelPlatformType.OPENAI,
+        model_type=ModelType.GPT_5_MINI,
+        model_config_dict={"stream": True},
+    )
+    request_events = []
+
+    chunks = [
+        ChatCompletionChunk(
+            id="mock_stream_usage_1",
+            choices=[
+                ChunkChoice(
+                    delta=ChoiceDelta(content="Hello", role="assistant"),
+                    index=0,
+                    finish_reason=None,
+                )
+            ],
+            created=1234567890,
+            model="gpt-5-mini",
+            object="chat.completion.chunk",
+        ),
+        ChatCompletionChunk(
+            id="mock_stream_usage_1",
+            choices=[
+                ChunkChoice(
+                    delta=ChoiceDelta(content=" world"),
+                    index=0,
+                    finish_reason="stop",
+                )
+            ],
+            created=1234567890,
+            model="gpt-5-mini",
+            object="chat.completion.chunk",
+            usage={
+                "prompt_tokens": 10,
+                "completion_tokens": 3,
+                "total_tokens": 13,
+            },
+        ),
+    ]
+
+    def mock_stream():
+        for chunk in chunks:
+            yield chunk
+
+    model.run = MagicMock(return_value=mock_stream())
+
+    agent = ChatAgent(
+        system_message="You are a helpful assistant.",
+        model=model,
+        on_request_usage=lambda payload: request_events.append(payload),
+    )
+
+    responses = list(agent.step("Say hello"))
+    assert len(responses) > 0
+    assert responses[-1].info["usage"]["total_tokens"] == 13
+    assert len(request_events) == 1
+    _assert_request_usage_event(
+        request_events[0],
+        request_index=1,
+        response_id="mock_stream_usage_1",
+        request_total_tokens=13,
+        step_total_tokens=13,
+    )
+
+
+@pytest.mark.model_backend
+@pytest.mark.asyncio
+async def test_chat_agent_async_stream_on_request_usage_callback():
+    from typing import AsyncGenerator
+
+    from openai.types.chat.chat_completion_chunk import (
+        ChatCompletionChunk,
+        ChoiceDelta,
+    )
+    from openai.types.chat.chat_completion_chunk import (
+        Choice as ChunkChoice,
+    )
+
+    model = ModelFactory.create(
+        model_platform=ModelPlatformType.OPENAI,
+        model_type=ModelType.GPT_5_MINI,
+        model_config_dict={"stream": True},
+    )
+    request_events = []
+
+    async def on_request_usage(payload):
+        request_events.append(payload)
+
+    chunks = [
+        ChatCompletionChunk(
+            id="mock_async_stream_usage_1",
+            choices=[
+                ChunkChoice(
+                    delta=ChoiceDelta(content="Hello", role="assistant"),
+                    index=0,
+                    finish_reason=None,
+                )
+            ],
+            created=1234567890,
+            model="gpt-5-mini",
+            object="chat.completion.chunk",
+        ),
+        ChatCompletionChunk(
+            id="mock_async_stream_usage_1",
+            choices=[
+                ChunkChoice(
+                    delta=ChoiceDelta(content=" world"),
+                    index=0,
+                    finish_reason="stop",
+                )
+            ],
+            created=1234567890,
+            model="gpt-5-mini",
+            object="chat.completion.chunk",
+            usage={
+                "prompt_tokens": 11,
+                "completion_tokens": 4,
+                "total_tokens": 15,
+            },
+        ),
+    ]
+
+    async def mock_async_stream() -> AsyncGenerator[ChatCompletionChunk, None]:
+        for chunk in chunks:
+            yield chunk
+
+    model.arun = AsyncMock(return_value=mock_async_stream())
+
+    agent = ChatAgent(
+        system_message="You are a helpful assistant.",
+        model=model,
+        on_request_usage=on_request_usage,
+    )
+
+    responses = []
+    streaming_response = await agent.astep("Say hello")
+    async for response in streaming_response:
+        responses.append(response)
+
+    assert len(responses) > 0
+    assert responses[-1].info["usage"]["total_tokens"] == 15
+    assert len(request_events) == 1
+    _assert_request_usage_event(
+        request_events[0],
+        request_index=1,
+        response_id="mock_async_stream_usage_1",
+        request_total_tokens=15,
+        step_total_tokens=15,
+    )
+
+
 @pytest.mark.model_backend
 def test_chat_agent_messages_window():
     system_msg = BaseMessage(

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/agents/test_chat_agent.py
: '>>>>> End Test Output'
git checkout 4a8b2667ac66c830c256a9ef33a034fa79c940e8 test/agents/test_chat_agent.py
