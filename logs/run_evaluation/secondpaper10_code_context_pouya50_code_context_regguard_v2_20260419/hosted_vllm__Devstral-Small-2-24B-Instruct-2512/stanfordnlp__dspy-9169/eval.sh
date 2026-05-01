#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff a5e068efa457cc40255dbf46e26e19f75bbe803b
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[dev]' || python -m pip install -e .
git checkout a5e068efa457cc40255dbf46e26e19f75bbe803b tests/mock_interpreter.py tests/predict/test_program_of_thought.py tests/predict/test_rlm.py tests/primitives/test_python_interpreter.py tests/teleprompt/test_gepa_instruction_proposer.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/mock_interpreter.py b/tests/mock_interpreter.py
index 8b26ff58..e36ceecf 100644
--- a/tests/mock_interpreter.py
+++ b/tests/mock_interpreter.py
@@ -4,7 +4,7 @@ Mock interpreter for testing RLM and other code-executing modules.
 This interpreter doesn't actually execute code - it returns scripted responses
 or uses a custom function to generate responses. Useful for:
 - Unit testing without Deno/Pyodide dependencies
-- Testing specific execution paths (errors, FINAL, etc.)
+- Testing specific execution paths (errors, SUBMIT, etc.)
 - Recording what code was submitted for execution
 """
 
@@ -28,11 +28,11 @@ class MockInterpreter:
             FinalAnswerResult("42"),
         ])
         result1 = mock.execute("print(len(context))")  # Returns "data explored"
-        result2 = mock.execute("FINAL('42')")  # Returns FinalAnswerResult("42")
+        result2 = mock.execute("SUBMIT('42')")  # Returns FinalAnswerResult("42")
 
         # Use custom execution function
         def custom_exec(code, variables):
-            if "FINAL" in code:
+            if "SUBMIT" in code:
                 return FinalAnswerResult("done")
             return f"executed: {code[:20]}..."
 
diff --git a/tests/predict/test_program_of_thought.py b/tests/predict/test_program_of_thought.py
index 04ab78ac..72cf9550 100644
--- a/tests/predict/test_program_of_thought.py
+++ b/tests/predict/test_program_of_thought.py
@@ -22,7 +22,7 @@ def test_pot_code_generation():
         [
             {
                 "reasoning": "Reason_A",
-                "generated_code": "```python\nresult = 1+1\nFINAL({'answer': result})\n```",
+                "generated_code": "```python\nresult = 1+1\nSUBMIT({'answer': result})\n```",
             },
             {"reasoning": "Reason_B", "answer": "2"},
         ]
@@ -62,7 +62,7 @@ def test_pot_support_multiple_fields():
         [
             {
                 "reasoning": "Reason_A",
-                "generated_code": "```python\nmaximum = 6\nminimum = 2\nFINAL({'maximum': maximum, 'minimum': minimum})\n```",
+                "generated_code": "```python\nmaximum = 6\nminimum = 2\nSUBMIT({'maximum': maximum, 'minimum': minimum})\n```",
             },
             {"reasoning": "Reason_B", "maximum": "6", "minimum": "2"},
         ]
@@ -81,11 +81,11 @@ def test_pot_code_generation_with_one_error():
         [
             {
                 "reasoning": "Reason_A",
-                "generated_code": "```python\nresult = 1+0/0\nFINAL({'answer': result})\n```",
+                "generated_code": "```python\nresult = 1+0/0\nSUBMIT({'answer': result})\n```",
             },
             {
                 "reasoning": "Reason_B",
-                "generated_code": "```python\nresult = 1+1\nFINAL({'answer': result})\n```",
+                "generated_code": "```python\nresult = 1+1\nSUBMIT({'answer': result})\n```",
             },
             {"reasoning": "Reason_C", "answer": "2"},
         ]
@@ -104,7 +104,7 @@ def test_pot_code_generation_persistent_errors():
         [
             {
                 "reasoning": "Reason_A",
-                "generated_code": "```python\nresult = 1+0/0\nFINAL({'answer': result})\n```",
+                "generated_code": "```python\nresult = 1+0/0\nSUBMIT({'answer': result})\n```",
             },
         ]
         * max_iters
diff --git a/tests/predict/test_rlm.py b/tests/predict/test_rlm.py
index dd65e269..fbbab742 100644
--- a/tests/predict/test_rlm.py
+++ b/tests/predict/test_rlm.py
@@ -93,7 +93,7 @@ class TestMockInterpreter:
         """Test that MockInterpreter can return FinalAnswerResult."""
         mock = MockInterpreter(responses=["exploring", FinalAnswerResult("42")])
         assert mock.execute("print(len(data))") == "exploring"
-        result = mock.execute("FINAL('42')")
+        result = mock.execute("SUBMIT('42')")
         assert isinstance(result, FinalAnswerResult)
         assert result.answer == "42"
 
@@ -156,7 +156,7 @@ class TestRLMInitialization:
         with pytest.raises(ValueError, match="must be a valid Python identifier"):
             RLM("context -> answer", tools={tool_name: my_tool})
 
-    @pytest.mark.parametrize("tool_name", ["llm_query", "FINAL", "print"])
+    @pytest.mark.parametrize("tool_name", ["llm_query", "SUBMIT", "print"])
     def test_tool_validation_reserved_names(self, tool_name):
         """Test RLM rejects tool names that conflict with built-in functions."""
         def my_tool() -> str:
@@ -443,7 +443,7 @@ class TestRLMCallMethod:
         mock = MockInterpreter(responses=[FinalAnswerResult({"answer": "42"})])
         rlm = RLM("query -> answer", max_iterations=3, interpreter=mock)
         rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Return answer", "code": 'FINAL("42")'},
+            {"reasoning": "Return answer", "code": 'SUBMIT("42")'},
         ])
 
         result = rlm(query="What is the answer?")
@@ -491,7 +491,7 @@ class TestRLMToolExceptions:
         rlm = RLM("query -> answer", max_iterations=5, interpreter=mock, tools={"failing_tool": failing_tool})
         rlm.generate_action = make_mock_predictor([
             {"reasoning": "Call tool", "code": "failing_tool()"},
-            {"reasoning": "Recover", "code": 'FINAL("recovered")'},
+            {"reasoning": "Recover", "code": 'SUBMIT("recovered")'},
         ])
 
         result = rlm.forward(query="test")
@@ -516,7 +516,7 @@ class TestRLMDynamicSignature:
         instructions = action_sig.instructions
         assert "llm_query" in instructions
         assert "llm_query_batched" in instructions
-        assert "FINAL" in instructions
+        assert "SUBMIT" in instructions
         assert "`document`" in instructions
         assert "`question`" in instructions
         assert "`summary`" in instructions
@@ -715,7 +715,7 @@ class TestRLMAsyncMock:
         mock = MockInterpreter(responses=[FinalAnswerResult({"answer": "42"})])
         rlm = RLM("query -> answer", max_iterations=3, interpreter=mock)
         rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Return answer", "code": 'FINAL("42")'},
+            {"reasoning": "Return answer", "code": 'SUBMIT("42")'},
         ])
 
         result = await rlm.aforward(query="What is the answer?")
@@ -727,7 +727,7 @@ class TestRLMAsyncMock:
         mock = MockInterpreter(responses=[FinalAnswerResult({"count": 42})])
         rlm = RLM("query -> count: int", max_iterations=3, interpreter=mock)
         rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Return count", "code": "FINAL(42)"},
+            {"reasoning": "Return count", "code": "SUBMIT(42)"},
         ])
 
         result = await rlm.aforward(query="count items")
@@ -736,7 +736,7 @@ class TestRLMAsyncMock:
 
     @pytest.mark.asyncio
     async def test_aforward_multi_iteration_mock(self):
-        """Test aforward() handles multiple iterations before FINAL (MockInterpreter)."""
+        """Test aforward() handles multiple iterations before SUBMIT (MockInterpreter)."""
         mock = MockInterpreter(responses=[
             "explored data",
             FinalAnswerResult({"answer": "done"}),
@@ -744,7 +744,7 @@ class TestRLMAsyncMock:
         rlm = RLM("query -> answer", max_iterations=5, interpreter=mock)
         rlm.generate_action = make_mock_predictor([
             {"reasoning": "Explore first", "code": "print('exploring')"},
-            {"reasoning": "Now finish", "code": 'FINAL("done")'},
+            {"reasoning": "Now finish", "code": 'SUBMIT("done")'},
         ])
 
         result = await rlm.aforward(query="test")
@@ -755,11 +755,11 @@ class TestRLMTypeCoercionMock:
     """Unit tests for RLM type coercion using MockInterpreter (no Deno required)."""
 
     @pytest.mark.parametrize("output_field,output_type,final_value,code,expected", [
-        ("count", "int", 42, "FINAL(42)", 42),
-        ("score", "float", 3.14, "FINAL(3.14)", 3.14),
-        ("valid", "bool", True, "FINAL(True)", True),
-        ("numbers", "list[int]", [1, 2, 3], "FINAL([1, 2, 3])", [1, 2, 3]),
-        ("answer", "Literal['yes', 'no']", "yes", 'FINAL("yes")', "yes"),
+        ("count", "int", 42, "SUBMIT(42)", 42),
+        ("score", "float", 3.14, "SUBMIT(3.14)", 3.14),
+        ("valid", "bool", True, "SUBMIT(True)", True),
+        ("numbers", "list[int]", [1, 2, 3], "SUBMIT([1, 2, 3])", [1, 2, 3]),
+        ("answer", "Literal['yes', 'no']", "yes", 'SUBMIT("yes")', "yes"),
     ])
     def test_type_coercion(self, output_field, output_type, final_value, code, expected):
         """Test RLM type coercion for various types (MockInterpreter)."""
@@ -780,8 +780,8 @@ class TestRLMTypeCoercionMock:
         ])
         rlm = RLM("query -> answer: Literal['yes', 'no']", max_iterations=5, interpreter=mock)
         rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Try maybe", "code": 'FINAL("maybe")'},
-            {"reasoning": "Try yes", "code": 'FINAL("yes")'},
+            {"reasoning": "Try maybe", "code": 'SUBMIT("maybe")'},
+            {"reasoning": "Try yes", "code": 'SUBMIT("yes")'},
         ])
 
         result = rlm.forward(query="is it yes?")
@@ -798,16 +798,16 @@ class TestRLMTypeCoercion:
     """Tests for RLM type coercion through full forward pass with PythonInterpreter.
 
     Note: These tests let RLM create its own PythonInterpreter so it can register
-    typed output_fields for FINAL based on the signature.
+    typed output_fields for SUBMIT based on the signature.
     """
 
     @pytest.mark.parametrize("output_field,output_type,code,expected,expected_type", [
-        ("count", "int", "FINAL(42)", 42, int),
-        ("score", "float", "FINAL(3.14)", 3.14, float),
-        ("valid", "bool", "FINAL(True)", True, bool),
-        ("numbers", "list[int]", "FINAL([1, 2, 3])", [1, 2, 3], list),
-        ("data", "dict[str, str]", 'FINAL({"key": "value"})', {"key": "value"}, dict),
-        ("answer", "Literal['yes', 'no']", 'FINAL("yes")', "yes", str),
+        ("count", "int", "SUBMIT(42)", 42, int),
+        ("score", "float", "SUBMIT(3.14)", 3.14, float),
+        ("valid", "bool", "SUBMIT(True)", True, bool),
+        ("numbers", "list[int]", "SUBMIT([1, 2, 3])", [1, 2, 3], list),
+        ("data", "dict[str, str]", 'SUBMIT({"key": "value"})', {"key": "value"}, dict),
+        ("answer", "Literal['yes', 'no']", 'SUBMIT("yes")', "yes", str),
     ])
     def test_type_coercion(self, output_field, output_type, code, expected, expected_type):
         """Test RLM type coercion for various types with PythonInterpreter."""
@@ -820,11 +820,11 @@ class TestRLMTypeCoercion:
         assert getattr(result, output_field) == expected
         assert isinstance(getattr(result, output_field), expected_type)
 
-    def test_final_var_extracts_typed_value(self):
-        """Test RLM FINAL_VAR correctly extracts typed value."""
+    def test_submit_extracts_typed_value(self):
+        """Test RLM SUBMIT correctly extracts typed value."""
         rlm = RLM("query -> count: int", max_iterations=3)
         rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Compute and return", "code": 'result = 42\nFINAL_VAR("result")'},
+            {"reasoning": "Compute and return", "code": "result = 42\nSUBMIT(result)"},
         ])
 
         result = rlm.forward(query="count items")
@@ -841,14 +841,14 @@ class TestRLMTypeCoercion:
 class TestRLMMultipleOutputs:
     """Tests for signatures with multiple typed output fields.
 
-    Tests FINAL() and FINAL_VAR() calling patterns with multi-output signatures.
+    Tests SUBMIT() calling patterns with multi-output signatures.
     """
 
     def test_multi_output_final_kwargs(self):
-        """FINAL(field1=val1, field2=val2) with keyword args."""
+        """SUBMIT(field1=val1, field2=val2) with keyword args."""
         rlm = RLM("query -> name: str, count: int", max_iterations=3)
         rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Return both outputs", "code": 'FINAL(name="alice", count=5)'},
+            {"reasoning": "Return both outputs", "code": 'SUBMIT(name="alice", count=5)'},
         ])
 
         result = rlm.forward(query="test")
@@ -857,10 +857,10 @@ class TestRLMMultipleOutputs:
         assert isinstance(result.count, int)
 
     def test_multi_output_final_positional(self):
-        """FINAL(val1, val2) with positional args mapped to field order."""
+        """SUBMIT(val1, val2) with positional args mapped to field order."""
         rlm = RLM("query -> name: str, count: int", max_iterations=3)
         rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Return both outputs positionally", "code": 'FINAL("bob", 10)'},
+            {"reasoning": "Return both outputs positionally", "code": 'SUBMIT("bob", 10)'},
         ])
 
         result = rlm.forward(query="test")
@@ -871,7 +871,7 @@ class TestRLMMultipleOutputs:
         """Signature with 3+ output fields of different types."""
         rlm = RLM("query -> name: str, age: int, active: bool", max_iterations=3)
         rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Return all three", "code": 'FINAL(name="carol", age=30, active=True)'},
+            {"reasoning": "Return all three", "code": 'SUBMIT(name="carol", age=30, active=True)'},
         ])
 
         result = rlm.forward(query="test")
@@ -880,11 +880,11 @@ class TestRLMMultipleOutputs:
         assert result.active is True
 
     def test_multi_output_final_missing_field_errors(self):
-        """FINAL() with missing field should return error in output."""
+        """SUBMIT() with missing field should return error in output."""
         rlm = RLM("query -> name: str, count: int", max_iterations=3)
         rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Missing count field", "code": 'FINAL(name="alice")'},
-            {"reasoning": "Now provide both", "code": 'FINAL(name="alice", count=5)'},
+            {"reasoning": "Missing count field", "code": 'SUBMIT(name="alice")'},
+            {"reasoning": "Now provide both", "code": 'SUBMIT(name="alice", count=5)'},
         ])
 
         # RLM should retry after getting error for missing field
@@ -892,46 +892,22 @@ class TestRLMMultipleOutputs:
         assert result.name == "alice"
         assert result.count == 5
 
-    def test_multi_output_final_var(self):
-        """FINAL_VAR("var1", "var2") maps variables to output fields."""
+    def test_multi_output_submit_vars(self):
+        """SUBMIT can pass variables directly for multiple outputs."""
         rlm = RLM("query -> name: str, count: int", max_iterations=3)
         rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Use FINAL_VAR", "code": 'n = "dave"\nc = 15\nFINAL_VAR("n", "c")'},
+            {"reasoning": "Use SUBMIT", "code": 'n = "dave"\nc = 15\nSUBMIT(n, c)'},
         ])
 
         result = rlm.forward(query="test")
         assert result.name == "dave"
         assert result.count == 15
 
-    def test_multi_output_final_var_wrong_count_errors(self):
-        """FINAL_VAR with wrong number of args should error and retry."""
-        rlm = RLM("query -> name: str, count: int", max_iterations=3)
-        rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Wrong arg count", "code": 'n = "eve"\nFINAL_VAR("n")'},  # Missing second arg
-            {"reasoning": "Now correct", "code": 'FINAL(name="eve", count=20)'},
-        ])
-
-        result = rlm.forward(query="test")
-        assert result.name == "eve"
-        assert result.count == 20
-
-    def test_multi_output_final_var_undefined_errors(self):
-        """FINAL_VAR with undefined variable should error and retry."""
-        rlm = RLM("query -> name: str, count: int", max_iterations=3)
-        rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Undefined var", "code": 'n = "frank"\nFINAL_VAR("n", "undefined_var")'},
-            {"reasoning": "Now correct", "code": 'FINAL(name="frank", count=25)'},
-        ])
-
-        result = rlm.forward(query="test")
-        assert result.name == "frank"
-        assert result.count == 25
-
     def test_multi_output_type_coercion(self):
         """Each output field is coerced to its declared type."""
         rlm = RLM("query -> count: int, ratio: float, flag: bool", max_iterations=3)
         rlm.generate_action = make_mock_predictor([
-            {"reasoning": "Return mixed types", "code": "FINAL(count=42, ratio=3.14, flag=True)"},
+            {"reasoning": "Return mixed types", "code": "SUBMIT(count=42, ratio=3.14, flag=True)"},
         ])
 
         result = rlm.forward(query="test")
@@ -953,13 +929,13 @@ class TestRLMWithDummyLM:
     """End-to-end tests using DummyLM with RLM and PythonInterpreter.
 
     Note: These tests let RLM create its own PythonInterpreter so it can register
-    typed output_fields for FINAL based on the signature.
+    typed output_fields for SUBMIT based on the signature.
     """
 
     def test_simple_computation_e2e(self):
         """Test full RLM pipeline: DummyLM -> RLM -> PythonInterpreter -> result."""
         with dummy_lm_context([
-            {"reasoning": "I need to compute 2 + 3", "code": "result = 2 + 3\nFINAL(result)"},
+            {"reasoning": "I need to compute 2 + 3", "code": "result = 2 + 3\nSUBMIT(result)"},
         ]):
             rlm = RLM("query -> answer: int", max_iterations=3)
             result = rlm.forward(query="What is 2 + 3?")
@@ -968,10 +944,10 @@ class TestRLMWithDummyLM:
             assert isinstance(result.answer, int)
 
     def test_multi_turn_computation_e2e(self):
-        """Test RLM with multiple turns before FINAL."""
+        """Test RLM with multiple turns before SUBMIT."""
         with dummy_lm_context([
             {"reasoning": "First explore the data", "code": "x = 10\nprint(f'x = {x}')"},
-            {"reasoning": "Now compute and return", "code": "y = x * 2\nFINAL(y)"},
+            {"reasoning": "Now compute and return", "code": "y = x * 2\nSUBMIT(y)"},
         ]):
             rlm = RLM("query -> answer: int", max_iterations=5)
             result = rlm.forward(query="Double ten")
@@ -982,7 +958,7 @@ class TestRLMWithDummyLM:
     def test_with_input_variables_e2e(self):
         """Test RLM with input variables passed to sandbox."""
         with dummy_lm_context([
-            {"reasoning": "Sum the numbers in the list", "code": "FINAL(sum(numbers))"},
+            {"reasoning": "Sum the numbers in the list", "code": "SUBMIT(sum(numbers))"},
         ]):
             rlm = RLM("numbers: list[int] -> total: int", max_iterations=3)
             result = rlm.forward(numbers=[1, 2, 3, 4, 5])
@@ -995,7 +971,7 @@ class TestRLMWithDummyLM:
             return {"apple": "red", "banana": "yellow"}.get(key, "unknown")
 
         with dummy_lm_context([
-            {"reasoning": "Look up the color of apple", "code": 'color = lookup(key="apple")\nFINAL(color)'},
+            {"reasoning": "Look up the color of apple", "code": 'color = lookup(key="apple")\nSUBMIT(color)'},
         ]):
             rlm = RLM("fruit -> color: str", max_iterations=3, tools={"lookup": lookup})
             result = rlm.forward(fruit="apple")
@@ -1006,7 +982,7 @@ class TestRLMWithDummyLM:
     async def test_aforward_simple_computation_e2e(self):
         """Test aforward() full pipeline: DummyLM -> RLM -> PythonInterpreter -> result."""
         with dummy_lm_context([
-            {"reasoning": "I need to compute 2 + 3", "code": "result = 2 + 3\nFINAL(result)"},
+            {"reasoning": "I need to compute 2 + 3", "code": "result = 2 + 3\nSUBMIT(result)"},
         ]):
             rlm = RLM("query -> answer: int", max_iterations=3)
             result = await rlm.aforward(query="What is 2 + 3?")
@@ -1016,10 +992,10 @@ class TestRLMWithDummyLM:
 
     @pytest.mark.asyncio
     async def test_aforward_multi_turn_e2e(self):
-        """Test aforward() with multiple turns before FINAL."""
+        """Test aforward() with multiple turns before SUBMIT."""
         with dummy_lm_context([
             {"reasoning": "First explore the data", "code": "x = 10\nprint(f'x = {x}')"},
-            {"reasoning": "Now compute and return", "code": "y = x * 2\nFINAL(y)"},
+            {"reasoning": "Now compute and return", "code": "y = x * 2\nSUBMIT(y)"},
         ]):
             rlm = RLM("query -> answer: int", max_iterations=5)
             result = await rlm.aforward(query="Double ten")
@@ -1031,7 +1007,7 @@ class TestRLMWithDummyLM:
     async def test_aforward_with_input_variables_e2e(self):
         """Test aforward() with input variables passed to sandbox."""
         with dummy_lm_context([
-            {"reasoning": "Sum the numbers in the list", "code": "FINAL(sum(numbers))"},
+            {"reasoning": "Sum the numbers in the list", "code": "SUBMIT(sum(numbers))"},
         ]):
             rlm = RLM("numbers: list[int] -> total: int", max_iterations=3)
             result = await rlm.aforward(numbers=[1, 2, 3, 4, 5])
diff --git a/tests/primitives/test_python_interpreter.py b/tests/primitives/test_python_interpreter.py
index bd72145e..fef4965e 100644
--- a/tests/primitives/test_python_interpreter.py
+++ b/tests/primitives/test_python_interpreter.py
@@ -67,16 +67,16 @@ def test_exception_args():
             interpreter.execute(code)
 
 
-def test_final_with_list():
-    """Test FINAL() with a list argument returns FinalAnswerResult with dict format."""
+def test_submit_with_list():
+    """Test SUBMIT() with a list argument returns FinalAnswerResult with dict format."""
 
     with PythonInterpreter() as interpreter:
         token = random.randint(1, 10**9)
-        code = f"FINAL(['The result is', {token}])"
+        code = f"SUBMIT(['The result is', {token}])"
         result = interpreter(code)
 
         assert isinstance(result, FinalAnswerResult)
-        # FINAL now always returns a dict with "answer" key for single-output default
+        # SUBMIT now always returns a dict with "answer" key for single-output default
         assert result.answer == {"answer": ["The result is", token]}
 
 def test_enable_env_vars_flag():
@@ -312,11 +312,11 @@ def test_tool_default_args():
 
 
 # =============================================================================
-# Multi-Output FINAL Tests
+# Multi-Output SUBMIT Tests
 # =============================================================================
 
-def test_final_with_typed_signature():
-    """Test FINAL with typed output signature."""
+def test_submit_with_typed_signature():
+    """Test SUBMIT with typed output signature."""
 
     output_fields = [
         {"name": "answer", "type": "str"},
@@ -324,14 +324,14 @@ def test_final_with_typed_signature():
     ]
 
     with PythonInterpreter(output_fields=output_fields) as sandbox:
-        result = sandbox.execute('FINAL(answer="the answer", confidence=0.95)')
+        result = sandbox.execute('SUBMIT(answer="the answer", confidence=0.95)')
 
         assert isinstance(result, FinalAnswerResult)
         assert result.answer == {"answer": "the answer", "confidence": 0.95}
 
 
-def test_final_positional_args():
-    """Test FINAL with positional arguments."""
+def test_submit_positional_args():
+    """Test SUBMIT with positional arguments."""
 
     output_fields = [
         {"name": "answer", "type": "str"},
@@ -339,14 +339,14 @@ def test_final_positional_args():
     ]
 
     with PythonInterpreter(output_fields=output_fields) as sandbox:
-        result = sandbox.execute('FINAL("the answer", 0.95)')
+        result = sandbox.execute('SUBMIT("the answer", 0.95)')
 
         assert isinstance(result, FinalAnswerResult)
         assert result.answer == {"answer": "the answer", "confidence": 0.95}
 
 
-def test_final_var_multi_output():
-    """Test FINAL_VAR with multiple output fields using positional args."""
+def test_submit_multi_output():
+    """Test SUBMIT with multiple output fields using positional args."""
 
     output_fields = [
         {"name": "answer", "type": "str"},
@@ -354,11 +354,11 @@ def test_final_var_multi_output():
     ]
 
     with PythonInterpreter(output_fields=output_fields) as sandbox:
-        # Positional args: variable names mapped to output fields in order
+        # Positional args: values mapped to output fields in order
         code = """
 a = "my answer"
 s = 42
-FINAL_VAR("a", "s")
+SUBMIT(a, s)
 """
         result = sandbox.execute(code)
 
@@ -366,8 +366,8 @@ FINAL_VAR("a", "s")
         assert result.answer == {"answer": "my answer", "score": 42}
 
 
-def test_final_var_wrong_arg_count():
-    """Test FINAL_VAR with wrong number of args gives clear error."""
+def test_submit_wrong_arg_count():
+    """Test SUBMIT with wrong number of args gives clear error."""
 
     output_fields = [
         {"name": "answer", "type": "str"},
@@ -376,8 +376,8 @@ def test_final_var_wrong_arg_count():
 
     with PythonInterpreter(output_fields=output_fields) as sandbox:
         with pytest.raises(CodeInterpreterError) as exc_info:
-            sandbox.execute('x = 1; FINAL_VAR("x")')  # Only 1 arg, expects 2
-        assert "expects 2 variable names" in str(exc_info.value)
+            sandbox.execute("x = 1; SUBMIT(x)")  # Only 1 arg, expects 2
+        assert "missing 1 required positional argument" in str(exc_info.value)
 
 
 def test_extract_parameters():
@@ -406,4 +406,3 @@ def test_extract_parameters_complex_types():
     # Complex types like Union are not included in type annotation
     assert params[0] == {"name": "items", "default": None}
     assert params[1] == {"name": "data", "default": None}
-
diff --git a/tests/teleprompt/test_gepa_instruction_proposer.py b/tests/teleprompt/test_gepa_instruction_proposer.py
index 56af5e20..22c88f57 100644
--- a/tests/teleprompt/test_gepa_instruction_proposer.py
+++ b/tests/teleprompt/test_gepa_instruction_proposer.py
@@ -1,6 +1,9 @@
+import logging
 from dataclasses import dataclass
 from typing import Any
 
+import pytest
+
 import dspy
 from dspy.teleprompt.gepa import instruction_proposal
 from dspy.utils.dummies import DummyLM
@@ -297,7 +300,8 @@ def test_image_serialization_into_strings():
     )
 
 
-def test_default_proposer():
+@pytest.mark.parametrize("reasoning", [True, False])
+def test_default_proposer(reasoning: bool, caplog):
     student = dspy.Predict("image -> label")
 
     image = dspy.Image("https://picsum.photos/id/237/200/300")
@@ -332,7 +336,8 @@ def test_default_proposer():
             {"improved_instruction": "Consider contextual clues in the image"},
             {"improved_instruction": "Analyze shape, color, and texture patterns"},
             {"improved_instruction": "Look for distinguishing characteristics"},
-        ]
+        ],
+        reasoning=reasoning,
     )
 
     gepa = dspy.GEPA(
@@ -341,7 +346,19 @@ def test_default_proposer():
         reflection_lm=reflection_lm,
     )
 
-    gepa.compile(student, trainset=examples, valset=examples)
+    with caplog.at_level(logging.INFO, logger="dspy.teleprompt.gepa.gepa"):
+        # Let logs propagate up to root because gepa uses try-catch and logs the error
+        # https://github.com/gepa-ai/gepa/blob/1b5eff5133be1015210e0512953c25a4b85ad454/src/gepa/proposer/reflective_mutation/reflective_mutation.py#L128
+        dspy_logger = logging.getLogger("dspy")
+        original_propagate = dspy_logger.propagate
+        dspy_logger.propagate = True
+
+        gepa.compile(student, trainset=examples, valset=examples)
+
+        dspy_logger.propagate = original_propagate
+
+        # Check that no internal GEPA reflection errors occured
+        assert "Exception during reflection/proposal" not in caplog.text
 
     assert len(lm.history) > 0, "LM should have been called"
     assert len(reflection_lm.history) > 0, "Reflection LM should have been called"

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/mock_interpreter.py tests/predict/test_program_of_thought.py tests/predict/test_rlm.py tests/primitives/test_python_interpreter.py tests/teleprompt/test_gepa_instruction_proposer.py
: '>>>>> End Test Output'
git checkout a5e068efa457cc40255dbf46e26e19f75bbe803b tests/mock_interpreter.py tests/predict/test_program_of_thought.py tests/predict/test_rlm.py tests/primitives/test_python_interpreter.py tests/teleprompt/test_gepa_instruction_proposer.py
