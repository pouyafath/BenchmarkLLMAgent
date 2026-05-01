#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 4de6d9ab9e5df5924c0eb4770d36e79d4e4616d1
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install hatchling editables && python -m pip install -e '.[test]' --no-build-isolation
git checkout 4de6d9ab9e5df5924c0eb4770d36e79d4e4616d1 test/models/test_aws_bedrock_model.py test/models/test_gemini_model.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/models/test_aws_bedrock_converse_model.py b/test/models/test_aws_bedrock_converse_model.py
new file mode 100644
index 00000000..35e49f18
--- /dev/null
+++ b/test/models/test_aws_bedrock_converse_model.py
@@ -0,0 +1,224 @@
+# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
+
+import base64
+import sys
+import types
+
+import pytest
+
+from camel.configs import BedrockConfig
+from camel.models import AWSBedrockConverseModel
+from camel.types import ModelType
+
+
+def _make_model(
+    model_config_dict=None,
+    **kwargs,
+) -> AWSBedrockConverseModel:
+    if model_config_dict is None:
+        model_config_dict = BedrockConfig().as_dict()
+    return AWSBedrockConverseModel(
+        ModelType.AWS_CLAUDE_3_HAIKU,
+        model_config_dict=model_config_dict,
+        api_key="dummy_key",
+        region_name="us-west-2",
+        **kwargs,
+    )
+
+
+@pytest.mark.model_backend
+def test_converse_cache_checkpoints_not_shared_object():
+    model = _make_model(
+        BedrockConfig(
+            cache_control="5m",
+        ).as_dict(),
+        bedrock_client=object(),
+    )
+
+    system, messages = model._convert_openai_to_bedrock_messages(
+        [
+            {"role": "system", "content": "sys"},
+            {"role": "user", "content": "hello"},
+        ]
+    )
+    assert system[-1] == {"cachePoint": {"type": "default"}}
+    assert messages[-1]["content"][-1] == {"cachePoint": {"type": "default"}}
+    assert system[-1] is not messages[-1]["content"][-1]
+
+
+@pytest.mark.model_backend
+def test_converse_builds_tool_config_and_tool_messages():
+    model = _make_model(
+        BedrockConfig(
+            cache_control="5m",
+            tool_choice="auto",
+        ).as_dict(),
+        bedrock_client=object(),
+    )
+
+    request = model._build_converse_request(
+        messages=[
+            {"role": "system", "content": "sys"},
+            {"role": "user", "content": "question"},
+            {
+                "role": "assistant",
+                "content": "",
+                "tool_calls": [
+                    {
+                        "id": "call_1",
+                        "type": "function",
+                        "function": {
+                            "name": "search_docs",
+                            "arguments": '{"q":"camel"}',
+                        },
+                    }
+                ],
+            },
+            {
+                "role": "tool",
+                "tool_call_id": "call_1",
+                "content": '{"answer":"ok"}',
+            },
+        ],
+        tools=[
+            {
+                "type": "function",
+                "function": {
+                    "name": "search_docs",
+                    "description": "Search docs",
+                    "parameters": {
+                        "type": "object",
+                        "properties": {"q": {"type": "string"}},
+                        "required": ["q"],
+                    },
+                },
+            }
+        ],
+    )
+
+    assert request["toolConfig"]["toolChoice"] == {"auto": {}}
+    assert (
+        request["toolConfig"]["tools"][0]["toolSpec"]["name"] == "search_docs"
+    )
+    assert request["messages"][1]["role"] == "assistant"
+    assert any(
+        isinstance(block, dict) and "toolUse" in block
+        for block in request["messages"][1]["content"]
+    )
+    assert request["messages"][2]["role"] == "user"
+    assert "toolResult" in request["messages"][2]["content"][0]
+
+
+@pytest.mark.model_backend
+def test_converse_tool_choice_none_disables_tools():
+    model = _make_model(
+        BedrockConfig(tool_choice="none").as_dict(),
+        bedrock_client=object(),
+    )
+    request = model._build_converse_request(
+        messages=[{"role": "user", "content": "hello"}],
+        tools=[
+            {
+                "type": "function",
+                "function": {
+                    "name": "search_docs",
+                    "parameters": {"type": "object"},
+                },
+            }
+        ],
+    )
+    assert "toolConfig" not in request
+
+
+@pytest.mark.model_backend
+def test_converse_supports_data_url_image_conversion():
+    image_bytes = b"test-image"
+    data_url = (
+        "data:image/png;base64," + base64.b64encode(image_bytes).decode()
+    )
+    model = _make_model(bedrock_client=object())
+
+    blocks = model._to_bedrock_content_blocks(
+        [{"type": "image_url", "image_url": {"url": data_url}}]
+    )
+    assert blocks[0]["image"]["format"] == "png"
+    assert blocks[0]["image"]["source"]["bytes"] == image_bytes
+
+
+@pytest.mark.model_backend
+def test_parse_json_or_text_scalar_json_is_text():
+    model = _make_model(bedrock_client=object())
+    assert model._parse_json_or_text("42") == {"text": "42"}
+    assert model._parse_json_or_text("true") == {"text": "true"}
+
+
+@pytest.mark.model_backend
+def test_converse_stream_is_supported():
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
+                        {"contentBlockDelta": {"delta": {"text": "hello"}}},
+                        {"messageStop": {"stopReason": "end_turn"}},
+                    ]
+                )
+            }
+
+    model = _make_model(
+        BedrockConfig(stream=True).as_dict(),
+        bedrock_client=DummyClient(),
+    )
+    chunks = list(model._run([{"role": "user", "content": "hi"}]))
+    assert len(chunks) >= 2
+    assert chunks[-1].choices[0].finish_reason == "stop"
+
+
+@pytest.mark.model_backend
+@pytest.mark.asyncio
+async def test_converse_async_not_supported():
+    model = _make_model(bedrock_client=object())
+    with pytest.raises(NotImplementedError):
+        await model._arun([{"role": "user", "content": "hi"}])
+
+
+@pytest.mark.model_backend
+def test_bedrock_client_supports_api_key_and_region_name(monkeypatch):
+    def _fake_boto3_client(service_name, **kwargs):
+        return {"service_name": service_name, "kwargs": kwargs}
+
+    fake_boto3 = types.SimpleNamespace(client=_fake_boto3_client)
+    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
+    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
+
+    model = AWSBedrockConverseModel(
+        ModelType.AWS_CLAUDE_3_HAIKU,
+        model_config_dict=BedrockConfig().as_dict(),
+        api_key="AKIA_TEST_KEY",
+        region_name="us-east-1",
+    )
+
+    client = model.bedrock_client
+    assert client["service_name"] == "bedrock-runtime"
+    assert client["kwargs"]["region_name"] == "us-east-1"
+    assert "aws_access_key_id" not in client["kwargs"]
diff --git a/test/models/test_aws_bedrock_model.py b/test/models/test_aws_bedrock_model.py
index 8d0b617b..e3fc7004 100644
--- a/test/models/test_aws_bedrock_model.py
+++ b/test/models/test_aws_bedrock_model.py
@@ -43,7 +43,9 @@ def test_aws_bedrock_model(model_type: ModelType):
         url="http://dummy.url",
     )
     assert model.model_type == model_type
-    assert model.model_config_dict == BedrockConfig().as_dict()
+    expected_config = BedrockConfig().as_dict()
+    expected_config.pop("cache_control", None)
+    assert model.model_config_dict == expected_config
     assert isinstance(model.token_counter, OpenAITokenCounter)
     assert isinstance(model.model_type.value_for_tiktoken, str)
     assert isinstance(model.model_type.token_limit, int)
@@ -71,3 +73,15 @@ async def test_aws_bedrock_async_supported():
     # and fail with a connection error (not NotImplementedError)
     with pytest.raises(APIConnectionError):
         await model._arun([{"role": "user", "content": "Test message"}])
+
+
+@pytest.mark.model_backend
+def test_bedrock_config_accepts_prompt_cache_params():
+    config = BedrockConfig(
+        temperature=0.3,
+        cache_control="5m",
+    )
+    config_dict = config.as_dict()
+
+    assert config_dict["temperature"] == 0.3
+    assert config_dict["cache_control"] == "5m"
diff --git a/test/models/test_gemini_model.py b/test/models/test_gemini_model.py
index 5013f0f1..2fedb6cf 100644
--- a/test/models/test_gemini_model.py
+++ b/test/models/test_gemini_model.py
@@ -13,6 +13,8 @@
 # ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
 
 import pytest
+from google.genai.errors import ClientError
+from pydantic import BaseModel
 
 from camel.configs import GeminiConfig
 from camel.models import GeminiModel
@@ -20,6 +22,20 @@ from camel.types import ModelType
 from camel.utils import OpenAITokenCounter
 
 
+def _make_stale_cache_error() -> ClientError:
+    """Create a ClientError that mimics a deleted/expired cached content."""
+    return ClientError(
+        code=403,
+        response_json={
+            "error": {
+                "code": 403,
+                "message": "CachedContent not found (or permission denied)",
+                "status": "PERMISSION_DENIED",
+            }
+        },
+    )
+
+
 @pytest.mark.model_backend
 @pytest.mark.parametrize(
     "model_type",
@@ -175,3 +191,274 @@ def test_gemini_process_messages_single_tool_call_unchanged():
     assert assistant_msg['role'] == 'assistant'
     assert len(assistant_msg['tool_calls']) == 1
     assert 'extra_content' in assistant_msg['tool_calls'][0]
+
+
+@pytest.mark.model_backend
+def test_gemini_config_accepts_cache_parameters():
+    r"""Test that GeminiConfig accepts cache_control and cached_content
+    parameters.
+    """
+    config = GeminiConfig(
+        temperature=0.5,
+        cache_control="300s",
+        cached_content="cachedContents/abc123",
+    )
+    config_dict = config.as_dict()
+
+    assert config_dict["cache_control"] == "300s"
+    assert config_dict["cached_content"] == "cachedContents/abc123"
+    assert config_dict["temperature"] == 0.5
+
+
+@pytest.mark.model_backend
+def test_gemini_model_extracts_cache_params():
+    r"""Test that GeminiModel extracts cache params from config and stores
+    them.
+    """
+    model_config_dict = GeminiConfig(
+        temperature=0.5,
+        cache_control="300s",
+        cached_content="cachedContents/abc123",
+    ).as_dict()
+
+    model = GeminiModel(
+        model_type=ModelType.GEMINI_2_0_FLASH,
+        model_config_dict=model_config_dict,
+    )
+
+    # Cache params should be extracted and stored
+    assert model._cache_control == "300s"
+    assert model._cached_content == "cachedContents/abc123"
+
+    # Cache params should not be in model_config_dict (passed to API)
+    assert "cache_control" not in model.model_config_dict
+    assert "cached_content" not in model.model_config_dict
+
+    # Other params should remain
+    assert model.model_config_dict["temperature"] == 0.5
+
+
+@pytest.mark.model_backend
+def test_gemini_model_has_cache_management_methods():
+    r"""Test that GeminiModel has cache management methods."""
+    model_config_dict = GeminiConfig().as_dict()
+    model = GeminiModel(
+        model_type=ModelType.GEMINI_2_0_FLASH,
+        model_config_dict=model_config_dict,
+    )
+
+    # Verify cache management methods exist
+    assert hasattr(model, 'create_cache')
+    assert hasattr(model, 'list_caches')
+    assert hasattr(model, 'get_cache')
+    assert hasattr(model, 'update_cache')
+    assert hasattr(model, 'delete_cache')
+    assert hasattr(model, 'native_client')
+
+    # Verify methods are callable
+    assert callable(model.create_cache)
+    assert callable(model.list_caches)
+    assert callable(model.get_cache)
+    assert callable(model.update_cache)
+    assert callable(model.delete_cache)
+
+
+@pytest.mark.model_backend
+def test_gemini_model_cached_content_property():
+    r"""Test that cached_content property can be set and cleared at runtime."""
+    model_config_dict = GeminiConfig(
+        temperature=0.5,
+        cached_content="cachedContents/initial",
+    ).as_dict()
+
+    model = GeminiModel(
+        model_type=ModelType.GEMINI_2_0_FLASH,
+        model_config_dict=model_config_dict,
+    )
+
+    # Initial cache should be extracted from config
+    assert model.cached_content == "cachedContents/initial"
+    assert "cached_content" not in model.model_config_dict
+
+    # Can change cache at runtime via property
+    model.cached_content = "cachedContents/updated"
+    assert model.cached_content == "cachedContents/updated"
+
+    # Can clear cache
+    model.cached_content = None
+    assert model.cached_content is None
+
+
+@pytest.mark.model_backend
+def test_gemini_cached_content_sent_via_nested_extra_body():
+    r"""Test cached_content is injected under extra_body.google."""
+    model = GeminiModel(
+        model_type=ModelType.GEMINI_2_0_FLASH,
+        model_config_dict=GeminiConfig(
+            cached_content="cachedContents/test-cache",
+        ).as_dict(),
+    )
+
+    class DummyCompletions:
+        def __init__(self):
+            self.calls = []
+
+        def create(self, **kwargs):
+            self.calls.append(kwargs)
+            return {"id": "ok"}
+
+    dummy_completions = DummyCompletions()
+    model._client = type(  # type: ignore[assignment]
+        "DummyClient",
+        (),
+        {
+            "chat": type(
+                "DummyChat",
+                (),
+                {"completions": dummy_completions},
+            )()
+        },
+    )()
+
+    model._request_chat_completion(
+        messages=[{"role": "user", "content": "hi"}]
+    )
+
+    assert len(dummy_completions.calls) == 1
+    assert (
+        dummy_completions.calls[0]["extra_body"]["extra_body"]["google"][
+            "cached_content"
+        ]
+        == "cachedContents/test-cache"
+    )
+
+
+@pytest.mark.model_backend
+def test_gemini_cached_content_retries_without_cache_on_stale_error():
+    r"""Test stale cached_content triggers a single retry without cache."""
+    model = GeminiModel(
+        model_type=ModelType.GEMINI_2_0_FLASH,
+        model_config_dict=GeminiConfig(
+            cached_content="cachedContents/stale-cache",
+        ).as_dict(),
+    )
+
+    class RetryCompletions:
+        def __init__(self):
+            self.calls = []
+
+        def create(self, **kwargs):
+            self.calls.append(kwargs)
+            if len(self.calls) == 1:
+                raise _make_stale_cache_error()
+            return {"id": "ok"}
+
+    retry_completions = RetryCompletions()
+    model._client = type(  # type: ignore[assignment]
+        "DummyClient",
+        (),
+        {
+            "chat": type(
+                "DummyChat",
+                (),
+                {"completions": retry_completions},
+            )()
+        },
+    )()
+
+    model._request_chat_completion(
+        messages=[{"role": "user", "content": "hi"}]
+    )
+
+    assert len(retry_completions.calls) == 2
+    assert (
+        retry_completions.calls[0]["extra_body"]["extra_body"]["google"][
+            "cached_content"
+        ]
+        == "cachedContents/stale-cache"
+    )
+    assert "extra_body" not in retry_completions.calls[1]
+    assert model.cached_content is None
+
+
+@pytest.mark.model_backend
+def test_gemini_parse_path_applies_cached_content_and_retry():
+    r"""Test parse path uses cache field and retries on stale cache."""
+    model = GeminiModel(
+        model_type=ModelType.GEMINI_2_0_FLASH,
+        model_config_dict=GeminiConfig(
+            cached_content="cachedContents/stale-cache",
+        ).as_dict(),
+    )
+
+    class DummySchema(BaseModel):
+        value: str
+
+    class RetryParseCompletions:
+        def __init__(self):
+            self.calls = []
+
+        def parse(self, **kwargs):
+            self.calls.append(kwargs)
+            if len(self.calls) == 1:
+                raise _make_stale_cache_error()
+            return {"id": "ok"}
+
+    retry_parse_completions = RetryParseCompletions()
+    model._client = type(  # type: ignore[assignment]
+        "DummyClient",
+        (),
+        {
+            "beta": type(
+                "DummyBeta",
+                (),
+                {
+                    "chat": type(
+                        "DummyChat",
+                        (),
+                        {"completions": retry_parse_completions},
+                    )()
+                },
+            )()
+        },
+    )()
+
+    model._request_parse(
+        messages=[{"role": "user", "content": "hi"}],
+        response_format=DummySchema,
+    )
+
+    assert len(retry_parse_completions.calls) == 2
+    assert (
+        retry_parse_completions.calls[0]["extra_body"]["extra_body"]["google"][
+            "cached_content"
+        ]
+        == "cachedContents/stale-cache"
+    )
+    assert "extra_body" not in retry_parse_completions.calls[1]
+    assert model.cached_content is None
+
+
+@pytest.mark.model_backend
+def test_gemini_cached_content_merges_with_existing_extra_body():
+    r"""Test cached_content merges with existing nested extra_body fields."""
+    model = GeminiModel(
+        model_type=ModelType.GEMINI_2_0_FLASH,
+        model_config_dict={
+            "temperature": 0.2,
+            "extra_body": {
+                "extra_body": {
+                    "google": {"thinking_config": {"type": "enabled"}}
+                }
+            },
+            "cached_content": "cachedContents/merge-cache",
+        },
+    )
+
+    request_config = model._prepare_request_config()
+    assert request_config["extra_body"]["extra_body"]["google"][
+        "thinking_config"
+    ] == {"type": "enabled"}
+    assert request_config["extra_body"]["extra_body"]["google"][
+        "cached_content"
+    ] == ("cachedContents/merge-cache")

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/models/test_aws_bedrock_converse_model.py test/models/test_aws_bedrock_model.py test/models/test_gemini_model.py
: '>>>>> End Test Output'
git checkout 4de6d9ab9e5df5924c0eb4770d36e79d4e4616d1 test/models/test_aws_bedrock_model.py test/models/test_gemini_model.py
