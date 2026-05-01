#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff e0c7ac640d959e1a1fdaeecd656439607c8a8733
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install hatchling editables && python -m pip install -e '.[test]' --no-build-isolation
git checkout e0c7ac640d959e1a1fdaeecd656439607c8a8733 test/models/test_aws_bedrock_converse_model.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/models/test_aws_bedrock_converse_model.py b/test/models/test_aws_bedrock_converse_model.py
index 35e49f18..01b58b89 100644
--- a/test/models/test_aws_bedrock_converse_model.py
+++ b/test/models/test_aws_bedrock_converse_model.py
@@ -196,10 +196,76 @@ def test_converse_stream_is_supported():
 
 @pytest.mark.model_backend
 @pytest.mark.asyncio
-async def test_converse_async_not_supported():
-    model = _make_model(bedrock_client=object())
-    with pytest.raises(NotImplementedError):
-        await model._arun([{"role": "user", "content": "hi"}])
+async def test_converse_async_non_stream():
+    class DummyClient:
+        def converse(self, **kwargs):
+            return {
+                "output": {
+                    "message": {
+                        "role": "assistant",
+                        "content": [{"text": "hello async"}],
+                    }
+                },
+                "stopReason": "end_turn",
+                "usage": {
+                    "inputTokens": 10,
+                    "outputTokens": 5,
+                },
+                "ResponseMetadata": {
+                    "RequestId": "req-async-123",
+                },
+            }
+
+    model = _make_model(bedrock_client=DummyClient())
+    result = await model._arun(
+        [{"role": "user", "content": "hi"}],
+    )
+    assert result.id == "req-async-123"
+    assert result.choices[0].message.content == "hello async"
+    assert result.usage.prompt_tokens == 10
+    assert result.usage.completion_tokens == 5
+
+
+@pytest.mark.model_backend
+@pytest.mark.asyncio
+async def test_converse_async_stream():
+    class DummyEventStream:
+        def __init__(self, events):
+            self._events = events
+
+        def __iter__(self):
+            return iter(self._events)
+
+    class DummyClient:
+        def converse_stream(self, **kwargs):
+            return {
+                "stream": DummyEventStream(
+                    [
+                        {"messageStart": {"role": "assistant"}},
+                        {
+                            "contentBlockDelta": {
+                                "delta": {"text": "hi async"},
+                            }
+                        },
+                        {
+                            "messageStop": {
+                                "stopReason": "end_turn",
+                            }
+                        },
+                    ]
+                )
+            }
+
+    model = _make_model(
+        BedrockConfig(stream=True).as_dict(),
+        bedrock_client=DummyClient(),
+    )
+    result = await model._arun(
+        [{"role": "user", "content": "hi"}],
+    )
+    chunks = [chunk async for chunk in result]
+    assert len(chunks) >= 2
+    assert chunks[-1].choices[0].finish_reason == "stop"
 
 
 @pytest.mark.model_backend

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/models/test_aws_bedrock_converse_model.py
: '>>>>> End Test Output'
git checkout e0c7ac640d959e1a1fdaeecd656439607c8a8733 test/models/test_aws_bedrock_converse_model.py
