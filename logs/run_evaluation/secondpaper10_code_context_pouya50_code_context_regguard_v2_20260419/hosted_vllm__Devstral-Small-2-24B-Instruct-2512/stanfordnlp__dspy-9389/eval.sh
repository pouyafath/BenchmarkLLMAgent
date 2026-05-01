#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff ddb09e7dd42676409574aa8e6a14c1d05161658a
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[dev]' || python -m pip install -e .
git checkout ddb09e7dd42676409574aa8e6a14c1d05161658a tests/adapters/test_chat_adapter.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/adapters/test_chat_adapter.py b/tests/adapters/test_chat_adapter.py
index dd6a76c1..86c662b3 100644
--- a/tests/adapters/test_chat_adapter.py
+++ b/tests/adapters/test_chat_adapter.py
@@ -743,3 +743,53 @@ All interactions will be structured in the following way, with the appropriate v
 In adhering to this structure, your objective is: 
         Answer the question with multiple answers and scores"""
     assert system_message == expected_system_message
+
+
+def test_null_content_raises_adapter_parse_error():
+    """When the LM returns content=None with no tool calls (e.g. content filter),
+    the adapter should raise AdapterParseError instead of silently returning None fields."""
+    from dspy.utils.exceptions import AdapterParseError
+
+    lm = dspy.LM("openai/gpt-4o-mini", cache=False)
+    response = ModelResponse(
+        choices=[Choices(message=Message(content=None))],
+        model="openai/gpt-4o-mini",
+    )
+
+    with dspy.context(lm=lm):
+        with mock.patch("litellm.completion", return_value=response):
+            cot = dspy.ChainOfThought("question -> answer")
+            with pytest.raises(AdapterParseError):
+                cot(question="test")
+
+
+def test_empty_string_content_raises_adapter_parse_error():
+    """Same as above but with empty string content."""
+    from dspy.utils.exceptions import AdapterParseError
+
+    lm = dspy.LM("openai/gpt-4o-mini", cache=False)
+    response = ModelResponse(
+        choices=[Choices(message=Message(content=""))],
+        model="openai/gpt-4o-mini",
+    )
+
+    with dspy.context(lm=lm):
+        with mock.patch("litellm.completion", return_value=response):
+            cot = dspy.ChainOfThought("question -> answer")
+            with pytest.raises(AdapterParseError):
+                cot(question="test")
+
+
+def test_tool_call_with_null_content_does_not_raise():
+    """Tool-call-only responses legitimately have content=None.
+    _call_postprocess must NOT raise when tool_calls are present."""
+    adapter = dspy.ChatAdapter(use_native_function_calling=True)
+    sig_cls = dspy.Signature("question, tools: list[dspy.Tool] -> answer, tool_calls: dspy.ToolCalls")
+
+    outputs = [{"text": None, "tool_calls": [
+        {"function": {"name": "search", "arguments": '{"query": "test"}'}, "id": "call_1", "type": "function"}
+    ]}]
+
+    result = adapter._call_postprocess(sig_cls, sig_cls, outputs, None, {})
+    assert result is not None
+    assert len(result) == 1

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/adapters/test_chat_adapter.py
: '>>>>> End Test Output'
git checkout ddb09e7dd42676409574aa8e6a14c1d05161658a tests/adapters/test_chat_adapter.py
