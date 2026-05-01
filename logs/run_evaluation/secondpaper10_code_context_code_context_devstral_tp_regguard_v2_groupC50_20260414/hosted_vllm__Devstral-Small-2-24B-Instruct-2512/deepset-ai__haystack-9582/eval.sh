#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 848115c65edb98fe600d71cb398f8a5e4c874f76
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 848115c65edb98fe600d71cb398f8a5e4c874f76 test/components/generators/chat/test_openai.py test/components/generators/test_utils.py test/dataclasses/test_streaming_chunk.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/components/generators/chat/test_openai.py b/test/components/generators/chat/test_openai.py
index dfbb2a39d5..9d051749fd 100644
--- a/test/components/generators/chat/test_openai.py
+++ b/test/components/generators/chat/test_openai.py
@@ -1177,6 +1177,32 @@ def test_convert_chat_completion_chunk_to_streaming_chunk(self, chat_completion_
             assert stream_chunk == haystack_chunk
             previous_chunks.append(stream_chunk)
 
+    def test_convert_chat_completion_chunk_with_empty_tool_calls(self):
+        # This can happen with some LLM providers where tool calls are not present but the pydantic models are still
+        # initialized.
+        chunk = ChatCompletionChunk(
+            id="chatcmpl-BC1y4wqIhe17R8sv3lgLcWlB4tXCw",
+            choices=[
+                chat_completion_chunk.Choice(
+                    delta=chat_completion_chunk.ChoiceDelta(
+                        tool_calls=[ChoiceDeltaToolCall(index=0, function=ChoiceDeltaToolCallFunction())]
+                    ),
+                    index=0,
+                )
+            ],
+            created=1742207200,
+            model="gpt-4o-mini-2024-07-18",
+            object="chat.completion.chunk",
+        )
+        result = _convert_chat_completion_chunk_to_streaming_chunk(chunk=chunk, previous_chunks=[])
+        assert result.content == ""
+        assert result.start is False
+        assert result.tool_calls == [ToolCallDelta(index=0)]
+        assert result.tool_call_result is None
+        assert result.index == 0
+        assert result.meta["model"] == "gpt-4o-mini-2024-07-18"
+        assert result.meta["received_at"] is not None
+
     def test_handle_stream_response(self, chat_completion_chunks):
         openai_chunks = chat_completion_chunks
         comp = OpenAIChatGenerator(api_key=Secret.from_token("test-api-key"))
diff --git a/test/components/generators/test_utils.py b/test/components/generators/test_utils.py
index 80d5372908..b428067224 100644
--- a/test/components/generators/test_utils.py
+++ b/test/components/generators/test_utils.py
@@ -388,6 +388,123 @@ def test_convert_streaming_chunk_to_chat_message_two_tool_calls_in_same_chunk():
     assert result.tool_calls[1].arguments == {"city": "Berlin"}
 
 
+def test_convert_streaming_chunk_to_chat_message_empty_tool_call_delta():
+    chunks = [
+        StreamingChunk(
+            content="",
+            meta={
+                "model": "gpt-4o-mini-2024-07-18",
+                "index": 0,
+                "tool_calls": None,
+                "finish_reason": None,
+                "received_at": "2025-02-19T16:02:55.910076",
+            },
+            component_info=ComponentInfo(name="test", type="test"),
+        ),
+        StreamingChunk(
+            content="",
+            meta={
+                "model": "gpt-4o-mini-2024-07-18",
+                "index": 0,
+                "tool_calls": [
+                    chat_completion_chunk.ChoiceDeltaToolCall(
+                        index=0,
+                        id="call_ZOj5l67zhZOx6jqjg7ATQwb6",
+                        function=chat_completion_chunk.ChoiceDeltaToolCallFunction(
+                            arguments='{"query":', name="rag_pipeline_tool"
+                        ),
+                        type="function",
+                    )
+                ],
+                "finish_reason": None,
+                "received_at": "2025-02-19T16:02:55.913919",
+            },
+            component_info=ComponentInfo(name="test", type="test"),
+            index=0,
+            start=True,
+            tool_calls=[
+                ToolCallDelta(
+                    id="call_ZOj5l67zhZOx6jqjg7ATQwb6", tool_name="rag_pipeline_tool", arguments='{"query":', index=0
+                )
+            ],
+        ),
+        StreamingChunk(
+            content="",
+            meta={
+                "model": "gpt-4o-mini-2024-07-18",
+                "index": 0,
+                "tool_calls": [
+                    chat_completion_chunk.ChoiceDeltaToolCall(
+                        index=0,
+                        function=chat_completion_chunk.ChoiceDeltaToolCallFunction(
+                            arguments=' "Where does Mark live?"}'
+                        ),
+                    )
+                ],
+                "finish_reason": None,
+                "received_at": "2025-02-19T16:02:55.924420",
+            },
+            component_info=ComponentInfo(name="test", type="test"),
+            index=0,
+            tool_calls=[ToolCallDelta(arguments=' "Where does Mark live?"}', index=0)],
+        ),
+        StreamingChunk(
+            content="",
+            meta={
+                "model": "gpt-4o-mini-2024-07-18",
+                "index": 0,
+                "tool_calls": [
+                    chat_completion_chunk.ChoiceDeltaToolCall(
+                        index=0, function=chat_completion_chunk.ChoiceDeltaToolCallFunction()
+                    )
+                ],
+                "finish_reason": "tool_calls",
+                "received_at": "2025-02-19T16:02:55.948772",
+            },
+            tool_calls=[ToolCallDelta(index=0)],
+            component_info=ComponentInfo(name="test", type="test"),
+            finish_reason="tool_calls",
+            index=0,
+        ),
+        StreamingChunk(
+            content="",
+            meta={
+                "model": "gpt-4o-mini-2024-07-18",
+                "index": 0,
+                "tool_calls": None,
+                "finish_reason": None,
+                "received_at": "2025-02-19T16:02:55.948772",
+                "usage": {
+                    "completion_tokens": 42,
+                    "prompt_tokens": 282,
+                    "total_tokens": 324,
+                    "completion_tokens_details": {
+                        "accepted_prediction_tokens": 0,
+                        "audio_tokens": 0,
+                        "reasoning_tokens": 0,
+                        "rejected_prediction_tokens": 0,
+                    },
+                    "prompt_tokens_details": {"audio_tokens": 0, "cached_tokens": 0},
+                },
+            },
+            component_info=ComponentInfo(name="test", type="test"),
+        ),
+    ]
+
+    # Convert chunks to a chat message
+    result = _convert_streaming_chunks_to_chat_message(chunks=chunks)
+
+    assert not result.texts
+    assert not result.text
+
+    # Verify both tool calls were found and processed
+    assert len(result.tool_calls) == 1
+    assert result.tool_calls[0].id == "call_ZOj5l67zhZOx6jqjg7ATQwb6"
+    assert result.tool_calls[0].tool_name == "rag_pipeline_tool"
+    assert result.tool_calls[0].arguments == {"query": "Where does Mark live?"}
+    assert result.meta["finish_reason"] == "tool_calls"
+
+
 def test_print_streaming_chunk_content_only():
     chunk = StreamingChunk(
         content="Hello, world!",
diff --git a/test/dataclasses/test_streaming_chunk.py b/test/dataclasses/test_streaming_chunk.py
index 1d53633026..af9fd8011f 100644
--- a/test/dataclasses/test_streaming_chunk.py
+++ b/test/dataclasses/test_streaming_chunk.py
@@ -99,11 +99,6 @@ def test_tool_call_delta():
     assert tool_call.index == 0
 
 
-def test_tool_call_delta_with_missing_fields():
-    with pytest.raises(ValueError):
-        _ = ToolCallDelta(id="123", index=0)
-
-
 def test_create_chunk_with_finish_reason():
     """Test creating a chunk with the new finish_reason field."""
     chunk = StreamingChunk(content="Test content", finish_reason="stop")

EOF_114329324912
: '>>>>> Start Test Output'
pytest --cov-report xml:coverage.xml --cov="haystack" -m "not integration" -rA test test/components/generators/chat/test_openai.py test/components/generators/test_utils.py test/dataclasses/test_streaming_chunk.py
: '>>>>> End Test Output'
git checkout 848115c65edb98fe600d71cb398f8a5e4c874f76 test/components/generators/chat/test_openai.py test/components/generators/test_utils.py test/dataclasses/test_streaming_chunk.py
