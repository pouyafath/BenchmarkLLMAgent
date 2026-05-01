#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff cf92cb36d9d0a80501ee711968e08b369b472583
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout cf92cb36d9d0a80501ee711968e08b369b472583 tests/clients/test_lm.py tests/predict/test_rlm.py tests/primitives/test_python_interpreter.py tests/teleprompt/test_gepa_tool_optimization.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/clients/test_lm.py b/tests/clients/test_lm.py
index 01d6b90e..15e0e02f 100644
--- a/tests/clients/test_lm.py
+++ b/tests/clients/test_lm.py
@@ -727,11 +727,11 @@ def test_responses_api_converts_images_correctly():
                         "type": "image_url",
                         "image_url": {
                             "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
-                        }
-                    }
-                ]
+                        },
+                    },
+                ],
             }
-        ]
+        ],
     }
 
     result = _convert_chat_request_to_responses_request(request_with_base64_image)
@@ -749,24 +749,17 @@ def test_responses_api_converts_images_correctly():
 
     # Second item should be converted to input_image format
     assert content[1]["type"] == "input_image"
-    assert content[1]["image_url"] == "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
+    assert (
+        content[1]["image_url"]
+        == "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
+    )
 
     # Test with URL image
     request_with_url_image = {
         "model": "openai/gpt-5-mini",
         "messages": [
-            {
-                "role": "user",
-                "content": [
-                    {
-                        "type": "image_url",
-                        "image_url": {
-                            "url": "https://example.com/image.jpg"
-                        }
-                    }
-                ]
-            }
-        ]
+            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}]}
+        ],
     }
 
     result = _convert_chat_request_to_responses_request(request_with_url_image)
@@ -793,11 +786,11 @@ def test_responses_api_converts_files_correctly():
                         "file": {
                             "file_data": "data:text/plain;base64,SGVsbG8gV29ybGQ=",
                             "filename": "test.txt",
-                        }
-                    }
-                ]
+                        },
+                    },
+                ],
             }
-        ]
+        ],
     }
 
     result = _convert_chat_request_to_responses_request(request_with_file)
@@ -830,11 +823,11 @@ def test_responses_api_converts_files_correctly():
                         "file": {
                             "file_id": "file-abc123",
                             "filename": "document.pdf",
-                        }
+                        },
                     }
-                ]
+                ],
             }
-        ]
+        ],
     }
 
     result = _convert_chat_request_to_responses_request(request_with_file_id)
@@ -858,11 +851,11 @@ def test_responses_api_converts_files_correctly():
                             "file_data": "data:application/pdf;base64,JVBERi0xLjQ=",
                             "file_id": "file-xyz789",
                             "filename": "report.pdf",
-                        }
+                        },
                     }
-                ]
+                ],
             }
-        ]
+        ],
     }
 
     result = _convert_chat_request_to_responses_request(request_with_all_fields)
@@ -910,9 +903,9 @@ def test_responses_api_with_image_input():
                         "type": "image_url",
                         "image_url": {
                             "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
-                        }
-                    }
-                ]
+                        },
+                    },
+                ],
             }
         ]
 
@@ -930,7 +923,10 @@ def test_responses_api_with_image_input():
         # Check that image was converted to input_image format
         image_content = [c for c in content if c.get("type") == "input_image"]
         assert len(image_content) == 1
-        assert image_content[0]["image_url"] == "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
+        assert (
+            image_content[0]["image_url"]
+            == "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
+        )
 
 
 def test_responses_api_with_pydantic_model_input():
@@ -985,3 +981,40 @@ def test_responses_api_with_pydantic_model_input():
         "type": "json_schema",
         "schema": TestModel.model_json_schema(),
     }
+
+
+@pytest.mark.asyncio
+async def test_streaming_passes_headers_correctly():
+    from dspy.clients.lm import _get_stream_completion_fn
+
+    custom_headers = {"Authorization": "Bearer my-custom-token"}
+    request = {
+        "model": "openai/gpt-4o-mini",
+        "messages": [{"role": "user", "content": "test"}],
+    }
+
+    mock_stream = mock.AsyncMock()
+    mock_stream.send = mock.AsyncMock()
+
+    async def empty_async_generator():
+        return
+        yield  # Make it a generator
+
+    with mock.patch("dspy.settings") as mock_settings:
+        mock_settings.send_stream = mock_stream
+        mock_settings.caller_predict = None
+        mock_settings.track_usage = False
+
+        with mock.patch("litellm.acompletion") as mock_acompletion:
+            mock_acompletion.return_value = empty_async_generator()
+
+            stream_fn = _get_stream_completion_fn(request, {}, sync=False, headers=custom_headers)
+            assert stream_fn is not None
+
+            with mock.patch("litellm.stream_chunk_builder", return_value={}):
+                await stream_fn()
+
+            # Verify headers were passed to litellm.acompletion
+            mock_acompletion.assert_called_once()
+            call_kwargs = mock_acompletion.call_args.kwargs
+            assert call_kwargs["headers"]["Authorization"] == "Bearer my-custom-token"
diff --git a/tests/predict/test_rlm.py b/tests/predict/test_rlm.py
index 54327c1a..f2f25940 100644
--- a/tests/predict/test_rlm.py
+++ b/tests/predict/test_rlm.py
@@ -10,6 +10,7 @@ from contextlib import contextmanager
 
 import pytest
 
+from dspy.adapters.types.tool import Tool
 from dspy.predict.rlm import RLM
 from dspy.primitives.code_interpreter import CodeInterpreterError, FinalOutput
 from dspy.primitives.prediction import Prediction
@@ -143,7 +144,7 @@ class TestRLMInitialization:
         def custom_tool(x: str = "") -> str:
             return x.upper()
 
-        rlm = RLM("context -> answer", max_iterations=5, tools={"custom_tool": custom_tool})
+        rlm = RLM("context -> answer", max_iterations=5, tools=[custom_tool])
         assert "custom_tool" in rlm.tools
         assert len(rlm.tools) == 1  # Only user tools, not internal llm_query/llm_query_batched
 
@@ -153,8 +154,9 @@ class TestRLMInitialization:
         def my_tool() -> str:
             return "result"
 
+        tool = Tool(my_tool, name=tool_name)
         with pytest.raises(ValueError, match="must be a valid Python identifier"):
-            RLM("context -> answer", tools={tool_name: my_tool})
+            RLM("context -> answer", tools=[tool])
 
     @pytest.mark.parametrize("tool_name", ["llm_query", "SUBMIT", "print"])
     def test_tool_validation_reserved_names(self, tool_name):
@@ -162,14 +164,23 @@ class TestRLMInitialization:
         def my_tool() -> str:
             return "result"
 
+        tool = Tool(my_tool, name=tool_name)
         with pytest.raises(ValueError, match="conflicts with built-in"):
-            RLM("context -> answer", tools={tool_name: my_tool})
+            RLM("context -> answer", tools=[tool])
 
     @pytest.mark.parametrize("invalid_value", ["not a function", 123])
     def test_tool_validation_not_callable(self, invalid_value):
         """Test RLM rejects tools that aren't callable."""
         with pytest.raises(TypeError, match="must be callable"):
-            RLM("context -> answer", tools={"my_tool": invalid_value})
+            RLM("context -> answer", tools=[invalid_value])
+
+    def test_tools_dict_rejected(self):
+        """Test RLM rejects dict format for tools with helpful error."""
+        def my_tool() -> str:
+            return "result"
+
+        with pytest.raises(TypeError, match="tools must be a list, not a dict"):
+            RLM("context -> answer", tools={"my_tool": my_tool})
 
     def test_optional_parameters(self):
         """Test RLM optional parameters and their defaults."""
@@ -488,7 +499,7 @@ class TestRLMToolExceptions:
             CodeInterpreterError("RuntimeError: Tool failed!"),
             FinalOutput({"answer": "recovered"}),
         ])
-        rlm = RLM("query -> answer", max_iterations=5, interpreter=mock, tools={"failing_tool": failing_tool})
+        rlm = RLM("query -> answer", max_iterations=5, interpreter=mock, tools=[failing_tool])
         rlm.generate_action = make_mock_predictor([
             {"reasoning": "Call tool", "code": "failing_tool()"},
             {"reasoning": "Recover", "code": 'SUBMIT("recovered")'},
@@ -584,6 +595,30 @@ class TestPythonInterpreter:
             )
             assert "15" in result
 
+    def test_variable_injection_with_none_values(self):
+        """Test variable injection with None values in dicts/lists (JSON null -> Python None)."""
+        with PythonInterpreter(tools={}) as interp:
+            # Test None in dict
+            result = interp.execute(
+                "print(data['key'] is None)",
+                variables={"data": {"key": None, "other": "value"}}
+            )
+            assert "True" in result
+
+            # Test None in list
+            result = interp.execute(
+                "print(items[1] is None)",
+                variables={"items": [1, None, 3]}
+            )
+            assert "True" in result
+
+            # Test nested None
+            result = interp.execute(
+                "print(nested['inner']['value'] is None)",
+                variables={"nested": {"inner": {"value": None}}}
+            )
+            assert "True" in result
+
     def test_tool_call_kwargs(self):
         """Test tool call with keyword arguments."""
         def echo(message: str = "") -> str:
@@ -973,7 +1008,7 @@ class TestRLMWithDummyLM:
         with dummy_lm_context([
             {"reasoning": "Look up the color of apple", "code": 'color = lookup(key="apple")\nSUBMIT(color)'},
         ]):
-            rlm = RLM("fruit -> color: str", max_iterations=3, tools={"lookup": lookup})
+            rlm = RLM("fruit -> color: str", max_iterations=3, tools=[lookup])
             result = rlm.forward(fruit="apple")
 
             assert result.color == "red"
diff --git a/tests/primitives/test_python_interpreter.py b/tests/primitives/test_python_interpreter.py
index 40b4d1b6..088e5ab2 100644
--- a/tests/primitives/test_python_interpreter.py
+++ b/tests/primitives/test_python_interpreter.py
@@ -406,3 +406,131 @@ def test_extract_parameters_complex_types():
     # Complex types like Union are not included in type annotation
     assert params[0] == {"name": "items", "default": None}
     assert params[1] == {"name": "data", "default": None}
+
+
+# =============================================================================
+# Large Variable Injection Tests
+# =============================================================================
+
+def test_large_variable_injection():
+    """Test that large strings are injected via filesystem to avoid Pyodide's FFI size limit."""
+    from dspy.primitives.python_interpreter import LARGE_VAR_THRESHOLD
+
+    # Create a string just over the threshold
+    large_data = "x" * (LARGE_VAR_THRESHOLD + 1024)
+
+    with PythonInterpreter() as interpreter:
+        result = interpreter.execute("len(data)", variables={"data": large_data})
+        assert result == len(large_data), "Large variable should be correctly injected and accessible"
+
+
+def test_large_variable_content_integrity():
+    """Test that large variable content is preserved exactly through filesystem injection."""
+    from dspy.primitives.python_interpreter import LARGE_VAR_THRESHOLD
+
+    # Create a string with recognizable pattern just over threshold
+    pattern = "ABCDEFGHIJ" * 100
+    large_data = pattern * ((LARGE_VAR_THRESHOLD // len(pattern)) + 1)
+
+    with PythonInterpreter() as interpreter:
+        # Check first and last parts to verify content integrity
+        code = """
+first_100 = data[:100]
+last_100 = data[-100:]
+(first_100, last_100)
+"""
+        result = interpreter.execute(code, variables={"data": large_data})
+        assert result[0] == large_data[:100], "First 100 chars should match"
+        assert result[1] == large_data[-100:], "Last 100 chars should match"
+
+
+def test_mixed_small_and_large_variables():
+    """Test that small and large variables can be used together."""
+    from dspy.primitives.python_interpreter import LARGE_VAR_THRESHOLD
+
+    small_var = "hello"
+    large_var = "x" * (LARGE_VAR_THRESHOLD + 1024)
+
+    with PythonInterpreter() as interpreter:
+        code = "f'{small} has {len(small)} chars, large has {len(large)} chars'"
+        result = interpreter.execute(code, variables={"small": small_var, "large": large_var})
+        expected = f"{small_var} has {len(small_var)} chars, large has {len(large_var)} chars"
+        assert result == expected, "Both small and large variables should work together"
+
+
+def test_multiple_large_variables():
+    """Test that multiple large variables can be injected."""
+    from dspy.primitives.python_interpreter import LARGE_VAR_THRESHOLD
+
+    large_a = "a" * (LARGE_VAR_THRESHOLD + 100)
+    large_b = "b" * (LARGE_VAR_THRESHOLD + 200)
+
+    with PythonInterpreter() as interpreter:
+        code = "(len(var_a), len(var_b), var_a[0], var_b[0])"
+        result = interpreter.execute(code, variables={"var_a": large_a, "var_b": large_b})
+        assert result == [len(large_a), len(large_b), "a", "b"], "Multiple large variables should work"
+
+
+def test_large_list_variable():
+    """Test that large list variables are injected via filesystem and JSON parsed."""
+    from dspy.primitives.python_interpreter import LARGE_VAR_THRESHOLD
+
+    # Each element "x" serializes to ~3 chars, so divide threshold by 3
+    num_elements = LARGE_VAR_THRESHOLD // 3
+    large_list = ["x"] * num_elements
+
+    with PythonInterpreter() as interpreter:
+        code = "(len(data), data[0], data[-1], type(data).__name__)"
+        result = interpreter.execute(code, variables={"data": large_list})
+        assert result == [num_elements, "x", "x", "list"]
+
+
+def test_nested_sets_and_tuples():
+    """Test that nested structures with sets and tuples are converted to JSON-compatible types."""
+    complex_data = {
+        "tags": {1, 2, 3},
+        "coords": (10, 20),
+        "nested": [{"inner_set": {"a", "b"}}]
+    }
+
+    with PythonInterpreter() as interpreter:
+        result = interpreter.execute("data", variables={"data": complex_data})
+        # Sets become sorted lists, tuples become lists
+        assert result["tags"] == [1, 2, 3]
+        assert result["coords"] == [10, 20]
+        assert result["nested"][0]["inner_set"] == ["a", "b"]
+
+
+def test_small_variable_not_using_filesystem():
+    """Test that small variables are embedded in code, not using filesystem."""
+    small_var = "small string"
+
+    interpreter = PythonInterpreter()
+    interpreter._pending_large_vars = {}  # Initialize
+    interpreter._inject_variables("print(x)", {"x": small_var})
+
+    assert interpreter._pending_large_vars == {}, "Small variables should not be in _pending_large_vars"
+
+
+def test_large_variable_threshold_boundary():
+    """Test behavior at exactly the threshold boundary.
+
+    The threshold applies to the serialized size, not the original value.
+    For strings, serialization adds 2 bytes (quotes).
+    """
+    from dspy.primitives.python_interpreter import LARGE_VAR_THRESHOLD
+
+    # Serialized size at threshold - should use embedded (not filesystem)
+    # Account for 2 bytes of quotes added by repr()
+    at_threshold = "x" * (LARGE_VAR_THRESHOLD - 2)
+
+    interpreter = PythonInterpreter()
+    interpreter._pending_large_vars = {}
+    interpreter._inject_variables("print(x)", {"x": at_threshold})
+    assert interpreter._pending_large_vars == {}, "Serialized size at threshold should be embedded"
+
+    # Serialized size over threshold - should use filesystem
+    over_threshold = "x" * (LARGE_VAR_THRESHOLD - 1)
+    interpreter._pending_large_vars = {}
+    interpreter._inject_variables("print(x)", {"x": over_threshold})
+    assert "x" in interpreter._pending_large_vars, "Serialized size over threshold should use filesystem"
diff --git a/tests/retrievers/test_colbertv2.py b/tests/retrievers/test_colbertv2.py
new file mode 100644
index 00000000..3c3144c5
--- /dev/null
+++ b/tests/retrievers/test_colbertv2.py
@@ -0,0 +1,41 @@
+from unittest.mock import MagicMock, patch
+
+import pytest
+
+from dspy.dsp.colbertv2 import colbertv2_get_request_v2, colbertv2_post_request_v2
+
+
+def test_get_request_raises_on_server_error():
+    mock_response = MagicMock()
+    mock_response.json.return_value = {"error": True, "message": "connection failed"}
+
+    with patch("dspy.dsp.colbertv2.requests.get", return_value=mock_response):
+        with pytest.raises(ValueError, match="connection failed"):
+            colbertv2_get_request_v2("http://test", "query", k=3)
+
+
+def test_post_request_raises_on_server_error():
+    mock_response = MagicMock()
+    mock_response.json.return_value = {"error": True, "message": "server error"}
+
+    with patch("dspy.dsp.colbertv2.requests.post", return_value=mock_response):
+        with pytest.raises(ValueError, match="server error"):
+            colbertv2_post_request_v2("http://test2", "query", k=3)
+
+
+def test_get_request_success():
+    mock_response = MagicMock()
+    mock_response.json.return_value = {"topk": [{"text": "doc1", "score": 0.9}]}
+
+    with patch("dspy.dsp.colbertv2.requests.get", return_value=mock_response):
+        result = colbertv2_get_request_v2("http://test3", "query", k=3)
+        assert result[0]["long_text"] == "doc1"
+
+
+def test_post_request_success():
+    mock_response = MagicMock()
+    mock_response.json.return_value = {"topk": [{"text": "doc1", "score": 0.9}]}
+
+    with patch("dspy.dsp.colbertv2.requests.post", return_value=mock_response):
+        result = colbertv2_post_request_v2("http://test4", "query", k=3)
+        assert result[0]["text"] == "doc1"
diff --git a/tests/teleprompt/test_gepa_tool_optimization.py b/tests/teleprompt/test_gepa_tool_optimization.py
deleted file mode 100644
index 0c414e84..00000000
--- a/tests/teleprompt/test_gepa_tool_optimization.py
+++ /dev/null
@@ -1,353 +0,0 @@
-"""Tests for GEPA's tool optimization (ReAct modules).
-
-Test categories:
-1. Detection - Compile-time detection of dspy.ReAct modules
-2. Application - build_program applies optimized instructions and tool descriptions
-
-DSPy ReAct Design Note:
-    DSPy's ReAct uses two predictors:
-    - react: reasoning/acting loop
-    - extract: structured output synthesis
-
-    We optimize extract.predict as it's called once with the complete trajectory
-    and produces all output fields.
-"""
-
-import json
-
-import gepa
-from gepa import optimize as gepa_optimize
-
-import dspy
-from dspy.teleprompt.gepa.gepa_utils import TOOL_MODULE_PREFIX, DspyAdapter
-from dspy.utils.dummies import DummyLM
-
-
-# Test tool fixtures
-def search(query: str) -> str:
-    """Test search tool."""
-    return f"Search: {query}"
-
-
-def calculate(expr: str) -> str:
-    """Test calculator tool."""
-    return str(eval(expr))
-
-
-def analyze(data: str) -> str:
-    """Test analyzer tool."""
-    return f"Analysis: {data}"
-
-
-def setup_seed_candidate_capture(monkeypatch):
-    """Capture seed_candidate dict passed to gepa.optimize."""
-    captured = {}
-
-    def capture_optimize(seed_candidate, **kwargs):
-        captured.update(seed_candidate)
-        return gepa_optimize(seed_candidate=seed_candidate, **kwargs)
-
-    monkeypatch.setattr(gepa, "optimize", capture_optimize)
-    return captured
-
-
-def create_optimizer(task_responses, reflection_responses):
-    """Create GEPA optimizer with explicit LM responses.
-
-    Args:
-        task_responses: List of dicts for task LM (e.g., [{"answer": "test"}])
-        reflection_responses: List of dicts for reflection LM
-
-    Returns:
-        tuple: (optimizer, trainset)
-    """
-    task_lm = DummyLM(task_responses)
-    reflection_lm = DummyLM(reflection_responses)
-
-    dspy.settings.configure(lm=task_lm)
-
-    optimizer = dspy.GEPA(
-        metric=lambda example, pred, trace=None, pred_name=None, pred_trace=None: dspy.Prediction(score=0.5, feedback="ok"),
-        reflection_lm=reflection_lm,
-        max_metric_calls=2,
-        enable_tool_optimization=True,
-    )
-
-    trainset = [dspy.Example(query="test", answer="test").with_inputs("query")]
-    return optimizer, trainset
-
-
-def get_predictor_name(program, predictor):
-    """Find predictor name by object identity in named_predictors().
-
-    Args:
-        program: DSPy module
-        predictor: Predictor object to find
-
-    Returns:
-        str: Predictor name (e.g., "pred", "agent.pred")
-    """
-    for name, pred in program.named_predictors():
-        if pred is predictor:
-            return name
-    raise ValueError(f"Predictor not found: {predictor}")
-
-
-def test_skip_predictor_without_tools(monkeypatch):
-    """Skip predictors without Tool annotations."""
-    seed_candidate = setup_seed_candidate_capture(monkeypatch)
-
-    class PlainSignature(dspy.Signature):
-        """Answer questions."""
-        query: str = dspy.InputField()
-        answer: str = dspy.OutputField()
-
-    class PlainAgent(dspy.Module):
-        def __init__(self):
-            super().__init__()
-            self.pred = dspy.Predict(PlainSignature)
-
-        def forward(self, query):
-            return self.pred(query=query)
-
-    program = PlainAgent()
-    optimizer, trainset = create_optimizer(
-        task_responses=[{"answer": "test"}] * 20,  # Repeat for GEPA iterations
-        reflection_responses=[{"improved_instruction": "optimized"}] * 20  # Repeat for GEPA iterations
-    )
-    optimizer.compile(program, trainset=trainset, valset=trainset)
-
-    predictor_name = get_predictor_name(program, program.pred)
-    assert predictor_name in seed_candidate
-
-    # Should be plain string instruction, not JSON config
-    instruction = seed_candidate[predictor_name]
-    assert isinstance(instruction, str)
-
-
-def test_detect_react_module(monkeypatch):
-    """Detect ReAct module with tools."""
-    seed_candidate = setup_seed_candidate_capture(monkeypatch)
-
-    program = dspy.ReAct("question -> answer", tools=[search])
-    optimizer, trainset = create_optimizer(
-        task_responses=[
-            {"next_thought": "I should search", "next_tool_name": "search", "next_tool_args": {"query": "test"}},
-            {"next_thought": "Done", "next_tool_name": "finish", "next_tool_args": {}},
-            {"reasoning": "Based on search", "answer": "test"},
-        ] * 20,  # Repeat for GEPA iterations
-        reflection_responses=[
-            {
-                "improved_predictor_instruction": "optimized react",
-                "improved_extract_instruction": "optimized extract",
-                "improved_tool_search_desc": "optimized search desc",
-                "improved_tool_search_arg_query_desc": "optimized query desc"
-            }
-        ] * 20  # Repeat for GEPA iterations
-    )
-    optimizer.compile(program, trainset=trainset, valset=trainset)
-
-    # Verify detection - use extract.predict as primary (for tracing)
-    extract_name = get_predictor_name(program, program.extract.predict)
-    component_key = f"{TOOL_MODULE_PREFIX}:{extract_name}"
-    assert component_key in seed_candidate
-
-    tool_config = json.loads(seed_candidate[component_key])
-    assert "tools" in tool_config
-
-
-def test_detect_multiple_react_modules(monkeypatch):
-    """Detect multiple ReAct modules in workflow."""
-    seed_candidate = setup_seed_candidate_capture(monkeypatch)
-
-    class Workflow(dspy.Module):
-        def __init__(self):
-            super().__init__()
-            self.searcher = dspy.ReAct("query -> results", tools=[search])
-            self.analyzer = dspy.ReAct("data -> analysis", tools=[analyze])
-
-        def forward(self, query):
-            results = self.searcher(query=query)
-            return self.analyzer(data=results.results)
-
-    program = Workflow()
-    optimizer, trainset = create_optimizer(
-        task_responses=[
-            {"next_thought": "Searching", "next_tool_name": "search", "next_tool_args": {"query": "test"}},
-            {"next_thought": "Done", "next_tool_name": "finish", "next_tool_args": {}},
-            {"reasoning": "Found results", "results": "data"},
-            {"next_thought": "Analyzing", "next_tool_name": "analyze", "next_tool_args": {"data": "test"}},
-            {"next_thought": "Done", "next_tool_name": "finish", "next_tool_args": {}},
-            {"reasoning": "Analyzed", "analysis": "result"},
-        ] * 20,  # Repeat for GEPA iterations
-        reflection_responses=[
-            {
-                "improved_predictor_instruction": "opt react search",
-                "improved_extract_instruction": "opt extract search",
-                "improved_tool_search_desc": "opt search desc",
-                "improved_tool_search_arg_query_desc": "opt query desc"
-            },
-            {
-                "improved_predictor_instruction": "opt react analyze",
-                "improved_extract_instruction": "opt extract analyze",
-                "improved_tool_analyze_desc": "opt analyze desc",
-                "improved_tool_analyze_arg_data_desc": "opt data desc"
-            }
-        ] * 20  # Repeat for GEPA iterations
-    )
-    optimizer.compile(program, trainset=trainset, valset=trainset)
-
-    # Verify both detected - use extract.predict as primary (for tracing)
-    searcher_name = get_predictor_name(program, program.searcher.extract.predict)
-    analyzer_name = get_predictor_name(program, program.analyzer.extract.predict)
-
-    searcher_key = f"{TOOL_MODULE_PREFIX}:{searcher_name}"
-    analyzer_key = f"{TOOL_MODULE_PREFIX}:{analyzer_name}"
-
-    assert searcher_key in seed_candidate
-    assert analyzer_key in seed_candidate
-
-
-def test_apply_optimized_react_descriptions():
-    """Apply optimized tool descriptions to ReAct modules."""
-
-    program = dspy.ReAct("question -> answer", tools=[search])
-
-    # Create mock optimized candidate - use extract.predict as primary (for tracing)
-    react_name = get_predictor_name(program, program.react)
-    extract_predict_name = get_predictor_name(program, program.extract.predict)
-
-    component_key = f"{TOOL_MODULE_PREFIX}:{extract_predict_name}"
-
-    optimized_candidate = {
-        component_key: json.dumps({
-            react_name: "OPTIMIZED: React instruction",
-            extract_predict_name: "OPTIMIZED: Extract instruction",
-            "tools": {
-                "search": {
-                    "desc": "OPTIMIZED: Search tool",
-                    "args": {"query": {"type": "string"}},
-                }
-            }
-        })
-    }
-
-    # Apply optimizations
-    adapter = DspyAdapter(
-        student_module=program,
-        metric_fn=lambda example, pred, trace=None: 0.5,
-        feedback_map={},
-        enable_tool_optimization=True,
-    )
-    rebuilt = adapter.build_program(optimized_candidate)
-
-    # Verify instructions updated
-    assert rebuilt.react.signature.instructions == "OPTIMIZED: React instruction"
-    assert rebuilt.extract.predict.signature.instructions == "OPTIMIZED: Extract instruction"
-
-    # Verify tool updated
-    assert rebuilt.tools["search"].desc == "OPTIMIZED: Search tool"
-
-
-def test_detect_nested_react_modules(monkeypatch):
-    """Detect ReAct modules in nested program structure."""
-    seed_candidate = setup_seed_candidate_capture(monkeypatch)
-
-    class Worker(dspy.Module):
-        def __init__(self):
-            super().__init__()
-            self.react = dspy.ReAct("task -> result", tools=[analyze])
-
-        def forward(self, task):
-            return self.react(task=task)
-
-    class Orchestrator(dspy.Module):
-        def __init__(self):
-            super().__init__()
-            self.searcher = dspy.ReAct("query -> results", tools=[search])
-            self.worker = Worker()
-
-        def forward(self, query):
-            results = self.searcher(query=query)
-            return self.worker(task=results.results)
-
-    program = Orchestrator()
-    optimizer, trainset = create_optimizer(
-        task_responses=[
-            {"next_thought": "Search", "next_tool_name": "search", "next_tool_args": {"query": "test"}},
-            {"next_thought": "Done", "next_tool_name": "finish", "next_tool_args": {}},
-            {"reasoning": "Found", "results": "data"},
-            {"next_thought": "Analyze", "next_tool_name": "analyze", "next_tool_args": {"data": "test"}},
-            {"next_thought": "Done", "next_tool_name": "finish", "next_tool_args": {}},
-            {"reasoning": "Analyzed", "result": "final"},
-        ] * 20,  # Repeat for GEPA iterations
-        reflection_responses=[
-            {
-                "improved_predictor_instruction": "opt react search",
-                "improved_extract_instruction": "opt extract search",
-                "improved_tool_search_desc": "opt search desc",
-                "improved_tool_search_arg_query_desc": "opt query desc"
-            },
-            {
-                "improved_predictor_instruction": "opt react analyze",
-                "improved_extract_instruction": "opt extract analyze",
-                "improved_tool_analyze_desc": "opt analyze desc",
-                "improved_tool_analyze_arg_data_desc": "opt data desc"
-            }
-        ] * 20  # Repeat for GEPA iterations
-    )
-    optimizer.compile(program, trainset=trainset, valset=trainset)
-
-    # Verify nested modules detected with full paths - use extract.predict as primary (for tracing)
-    searcher_name = get_predictor_name(program, program.searcher.extract.predict)
-    worker_extract_name = get_predictor_name(program, program.worker.react.extract.predict)
-
-    searcher_key = f"{TOOL_MODULE_PREFIX}:{searcher_name}"
-    worker_key = f"{TOOL_MODULE_PREFIX}:{worker_extract_name}"
-
-    assert searcher_key in seed_candidate
-    assert worker_key in seed_candidate
-
-    # Verify full paths preserved (not truncated)
-    assert "searcher" in searcher_name  # Contains parent path
-    assert "worker" in worker_extract_name  # Contains nested path
-
-
-def test_selective_optimization_with_none_returns():
-    """Verify selective optimization when reflection LM returns None for some fields."""
-
-    program = dspy.ReAct("question -> answer", tools=[search, calculate])
-
-    react_name = get_predictor_name(program, program.react)
-    extract_name = get_predictor_name(program, program.extract.predict)
-    component_key = f"{TOOL_MODULE_PREFIX}:{extract_name}"
-
-    # Mock selective optimization (only react instruction and search tool updated)
-    optimized_candidate = {
-        component_key: json.dumps({
-            react_name: "OPTIMIZED: React instruction",
-            extract_name: program.extract.predict.signature.instructions,
-            "tools": {
-                "search": {
-                    "desc": "OPTIMIZED: Search tool",
-                    "args": {"query": {"type": "string"}},
-                }
-            }
-        })
-    }
-
-    adapter = DspyAdapter(
-        student_module=program,
-        metric_fn=lambda example, pred, trace=None: 0.5,
-        feedback_map={},
-        enable_tool_optimization=True,
-    )
-    rebuilt = adapter.build_program(optimized_candidate)
-
-    # Verify selective updates
-    assert rebuilt.react.signature.instructions == "OPTIMIZED: React instruction"
-    assert rebuilt.extract.predict.signature.instructions == program.extract.predict.signature.instructions
-    assert rebuilt.tools["search"].desc == "OPTIMIZED: Search tool"
-
-    # Original unchanged (calculate not in optimized candidate)
-    assert rebuilt.tools["calculate"].desc == program.tools["calculate"].desc

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/clients/test_lm.py tests/predict/test_rlm.py tests/primitives/test_python_interpreter.py tests/retrievers/test_colbertv2.py tests/teleprompt/test_gepa_tool_optimization.py
: '>>>>> End Test Output'
git checkout cf92cb36d9d0a80501ee711968e08b369b472583 tests/clients/test_lm.py tests/predict/test_rlm.py tests/primitives/test_python_interpreter.py tests/teleprompt/test_gepa_tool_optimization.py
