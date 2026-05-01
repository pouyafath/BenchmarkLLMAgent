#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff cfc076a98c1e5299d846e0e544a78f73df6034ac
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[dev]' || python -m pip install -e .
git checkout cfc076a98c1e5299d846e0e544a78f73df6034ac tests/clients/test_lm.py tests/evaluate/test_evaluate.py tests/predict/test_predict.py tests/primitives/test_python_interpreter.py tests/utils/test_parallelizer.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/clients/test_lm.py b/tests/clients/test_lm.py
index 71e5ee5a..0efef3d0 100644
--- a/tests/clients/test_lm.py
+++ b/tests/clients/test_lm.py
@@ -16,7 +16,6 @@ from openai.types.responses import ResponseOutputMessage, ResponseReasoningItem
 from openai.types.responses.response_reasoning_item import Summary
 
 import dspy
-from dspy.utils.dummies import DummyLM
 from dspy.utils.usage_tracker import track_usage
 
 
@@ -122,9 +121,8 @@ def test_disabled_cache_skips_cache_key(monkeypatch):
 
             monkeypatch.setattr(litellm, "completion", fake_completion)
 
-            dummy_lm = DummyLM([{"answer": "ignored"}])
-            # TODO(isaacbmiller): Change from dummy_lm.forward to just dummy_lm.__call__ #8864
-            dummy_lm.forward(messages=[{"role": "user", "content": "Hello"}])
+            lm = dspy.LM("dummy", model_type="chat")
+            lm(messages=[{"role": "user", "content": "Hello"}])
 
             cache_key_spy.assert_not_called()
             cache_get_spy.assert_called_once()
diff --git a/tests/evaluate/test_evaluate.py b/tests/evaluate/test_evaluate.py
index e35f08eb..3ac313be 100644
--- a/tests/evaluate/test_evaluate.py
+++ b/tests/evaluate/test_evaluate.py
@@ -56,6 +56,33 @@ def test_evaluate_call():
     assert score.score == 100.0
 
 
+def test_evaluate_single_thread_runs_in_main_thread():
+    """Evaluate with num_threads=1 should run in the main thread."""
+    dspy.configure(
+        lm=DummyLM({"What is 1+1?": {"answer": "2"}, "What is 2+2?": {"answer": "4"}})
+    )
+    devset = [new_example("What is 1+1?", "2"), new_example("What is 2+2?", "4")]
+
+    execution_threads = []
+
+    original_metric = answer_exact_match
+
+    def tracking_metric(example, prediction, **kwargs):
+        execution_threads.append(threading.current_thread())
+        return original_metric(example, prediction, **kwargs)
+
+    program = Predict("question -> answer")
+    ev = Evaluate(
+        devset=devset,
+        metric=tracking_metric,
+        display_progress=False,
+        num_threads=1,
+    )
+    result = ev(program)
+    assert result.score == 100.0
+    assert all(t is threading.main_thread() for t in execution_threads)
+
+
 @pytest.mark.extra
 def test_construct_result_df():
     import pandas as pd
diff --git a/tests/predict/test_predict.py b/tests/predict/test_predict.py
index 65b73636..b82da3b2 100644
--- a/tests/predict/test_predict.py
+++ b/tests/predict/test_predict.py
@@ -258,6 +258,234 @@ def test_lm_field_after_dump_and_load_state(tmp_path, filename):
     assert original_predict.dump_state() == loaded_predict.dump_state()
 
 
+@pytest.mark.parametrize("endpoint_override_key", ["api_base", "base_url"])
+def test_load_ignores_serialized_endpoint_override_by_default(tmp_path, endpoint_override_key):
+    file_path = tmp_path / "model.json"
+    override_url = "http://override.local/v1"
+    original_predict = dspy.Predict("q->a")
+    original_predict.lm = dspy.LM(model="openai/gpt-4o-mini")
+    original_predict.save(file_path)
+
+    with open(file_path, "rb") as f:
+        saved_state = orjson.loads(f.read())
+    saved_state["lm"][endpoint_override_key] = override_url
+    with open(file_path, "wb") as f:
+        f.write(orjson.dumps(saved_state))
+
+    with patch("dspy.predict.predict.logger.warning") as warning_mock:
+        loaded_predict = dspy.Predict("q->a")
+        loaded_predict.load(file_path)
+
+    assert loaded_predict.lm is not None
+    assert endpoint_override_key not in loaded_predict.lm.kwargs
+    warning_mock.assert_called_once()
+    assert warning_mock.call_args.args[1] == [endpoint_override_key]
+
+
+@pytest.mark.parametrize("endpoint_override_key", ["api_base", "base_url"])
+def test_load_allows_serialized_endpoint_override_with_opt_in(tmp_path, endpoint_override_key):
+    file_path = tmp_path / "model.json"
+    override_url = "http://override.local/v1"
+    original_predict = dspy.Predict("q->a")
+    original_predict.lm = dspy.LM(model="openai/gpt-4o-mini")
+    original_predict.save(file_path)
+
+    with open(file_path, "rb") as f:
+        saved_state = orjson.loads(f.read())
+    saved_state["lm"][endpoint_override_key] = override_url
+    with open(file_path, "wb") as f:
+        f.write(orjson.dumps(saved_state))
+
+    with patch("dspy.predict.predict.logger.warning") as warning_mock:
+        loaded_predict = dspy.Predict("q->a")
+        loaded_predict.load(file_path, allow_unsafe_lm_state=True)
+
+    assert loaded_predict.lm is not None
+    assert loaded_predict.lm.kwargs[endpoint_override_key] == override_url
+    warning_mock.assert_not_called()
+
+
+@pytest.mark.parametrize("endpoint_override_key", ["api_base", "base_url"])
+def test_load_state_ignores_serialized_endpoint_override_by_default(endpoint_override_key):
+    override_url = "http://override.local/v1"
+    original_predict = dspy.Predict("q->a")
+    original_predict.lm = dspy.LM(model="openai/gpt-4o-mini")
+    saved_state = copy.deepcopy(original_predict.dump_state())
+    saved_state["lm"][endpoint_override_key] = override_url
+
+    with patch("dspy.predict.predict.logger.warning") as warning_mock:
+        loaded_predict = dspy.Predict("q->a")
+        loaded_predict.load_state(saved_state)
+
+    assert loaded_predict.lm is not None
+    assert endpoint_override_key not in loaded_predict.lm.kwargs
+    warning_mock.assert_called_once()
+    assert warning_mock.call_args.args[1] == [endpoint_override_key]
+
+
+@pytest.mark.parametrize("endpoint_override_key", ["api_base", "base_url"])
+def test_load_state_allows_serialized_endpoint_override_with_opt_in(endpoint_override_key):
+    override_url = "http://override.local/v1"
+    original_predict = dspy.Predict("q->a")
+    original_predict.lm = dspy.LM(model="openai/gpt-4o-mini")
+    saved_state = copy.deepcopy(original_predict.dump_state())
+    saved_state["lm"][endpoint_override_key] = override_url
+
+    with patch("dspy.predict.predict.logger.warning") as warning_mock:
+        loaded_predict = dspy.Predict("q->a")
+        loaded_predict.load_state(saved_state, allow_unsafe_lm_state=True)
+
+    assert loaded_predict.lm is not None
+    assert loaded_predict.lm.kwargs[endpoint_override_key] == override_url
+    warning_mock.assert_not_called()
+
+
+def test_load_state_ignores_serialized_model_list_endpoint_override_by_default():
+    override_url = "http://override.local/v1"
+    original_predict = dspy.Predict("q->a")
+    original_predict.lm = dspy.LM(model="openai/gpt-4o-mini")
+    saved_state = copy.deepcopy(original_predict.dump_state())
+    saved_state["lm"]["model_list"] = [
+        {
+            "model_name": "openai/gpt-4o-mini",
+            "litellm_params": {
+                "model": "openai/gpt-4o-mini",
+                "api_base": override_url,
+            },
+        }
+    ]
+
+    with patch("dspy.predict.predict.logger.warning") as warning_mock:
+        loaded_predict = dspy.Predict("q->a")
+        loaded_predict.load_state(saved_state)
+
+    assert loaded_predict.lm is not None
+    assert "model_list" not in loaded_predict.lm.kwargs
+    warning_mock.assert_called_once()
+    assert "model_list" in warning_mock.call_args.args[1]
+
+
+@pytest.mark.parametrize("endpoint_override_key", ["api_base", "base_url"])
+def test_load_prevents_serialized_endpoint_override_reaching_litellm(tmp_path, endpoint_override_key):
+    file_path = tmp_path / "model.json"
+    override_url = "http://override.local/v1"
+    original_predict = dspy.Predict("q->a")
+    original_predict.lm = dspy.LM(model="openai/gpt-4o-mini")
+    original_predict.save(file_path)
+
+    with open(file_path, "rb") as f:
+        saved_state = orjson.loads(f.read())
+    saved_state["lm"][endpoint_override_key] = override_url
+    with open(file_path, "wb") as f:
+        f.write(orjson.dumps(saved_state))
+
+    loaded_predict = dspy.Predict("q->a")
+    loaded_predict.load(file_path)
+
+    class FakeResp(dict):
+        cache_hit = False
+        usage = {}
+
+        def __init__(self):
+            super().__init__({"choices": []})
+
+    with patch("litellm.completion", return_value=FakeResp()) as completion_mock:
+        loaded_predict.lm.forward(prompt="hello", cache=False)
+
+    assert completion_mock.call_count == 1
+    assert completion_mock.call_args.kwargs.get(endpoint_override_key) != override_url
+
+
+def test_load_blocks_serialized_model_list_unless_opted_in(tmp_path):
+    file_path = tmp_path / "model.json"
+    override_url = "http://override.local/v1"
+    original_predict = dspy.Predict("q->a")
+    original_predict.lm = dspy.LM(model="openai/gpt-4o-mini")
+    original_predict.save(file_path)
+
+    with open(file_path, "rb") as f:
+        saved_state = orjson.loads(f.read())
+    saved_state["lm"]["model_list"] = [
+        {
+            "model_name": "openai/gpt-4o-mini",
+            "litellm_params": {
+                "model": "openai/gpt-4o-mini",
+                "api_base": override_url,
+            },
+        }
+    ]
+    with open(file_path, "wb") as f:
+        f.write(orjson.dumps(saved_state))
+
+    class FakeResp(dict):
+        cache_hit = False
+        usage = {}
+
+        def __init__(self):
+            super().__init__({"choices": []})
+
+    safe_loaded_predict = dspy.Predict("q->a")
+    safe_loaded_predict.load(file_path)
+    with patch("litellm.batch_completion_models", return_value=FakeResp()) as batch_completion_mock:
+        with patch("litellm.completion", return_value=FakeResp()) as completion_mock:
+            safe_loaded_predict.lm.forward(prompt="hello", cache=False)
+
+    assert completion_mock.called
+    assert not batch_completion_mock.called
+
+    opt_in_loaded_predict = dspy.Predict("q->a")
+    opt_in_loaded_predict.load(file_path, allow_unsafe_lm_state=True)
+    with patch("litellm.batch_completion_models", return_value=FakeResp()) as batch_completion_mock:
+        opt_in_loaded_predict.lm.forward(prompt="hello", cache=False)
+
+    opt_in_deployments = batch_completion_mock.call_args.kwargs["deployments"]
+    assert opt_in_deployments[0]["api_base"] == override_url
+
+
+def test_load_uses_env_api_key_without_honoring_serialized_endpoint_override(tmp_path, monkeypatch):
+    file_path = tmp_path / "model.json"
+    override_url = "http://override.local/v1"
+    env_api_key = "sk-live-test-secret"
+
+    original_predict = dspy.Predict("q->a")
+    original_predict.lm = dspy.LM(model="openai/gpt-4o-mini", model_type="text")
+    original_predict.save(file_path)
+
+    with open(file_path, "rb") as f:
+        saved_state = orjson.loads(f.read())
+    assert "api_key" not in saved_state["lm"]
+    saved_state["lm"]["api_base"] = override_url
+    with open(file_path, "wb") as f:
+        f.write(orjson.dumps(saved_state))
+
+    monkeypatch.setenv("openai_API_KEY", env_api_key)
+
+    class FakeResp(dict):
+        cache_hit = False
+        usage = {}
+
+        def __init__(self):
+            super().__init__({"choices": []})
+
+    # Simulates legacy behavior by allowing serialized endpoint overrides.
+    opt_in_loaded_predict = dspy.Predict("q->a")
+    opt_in_loaded_predict.load(file_path, allow_unsafe_lm_state=True)
+    with patch("litellm.text_completion", return_value=FakeResp()) as text_completion_mock:
+        opt_in_loaded_predict.lm.forward(prompt="hello", cache=False)
+
+    assert text_completion_mock.call_args.kwargs["api_base"] == override_url
+    assert text_completion_mock.call_args.kwargs["api_key"] == env_api_key
+
+    safe_loaded_predict = dspy.Predict("q->a")
+    safe_loaded_predict.load(file_path)
+    with patch("litellm.text_completion", return_value=FakeResp()) as text_completion_mock:
+        safe_loaded_predict.lm.forward(prompt="hello", cache=False)
+
+    # In the safe path, the key still comes from the environment, but the serialized endpoint override does not.
+    assert text_completion_mock.call_args.kwargs["api_key"] == env_api_key
+    assert text_completion_mock.call_args.kwargs["api_base"] != override_url
+
+
 def test_forward_method():
     program = Predict("question -> answer")
     dspy.configure(lm=DummyLM([{"answer": "No more responses"}]))
diff --git a/tests/primitives/test_python_interpreter.py b/tests/primitives/test_python_interpreter.py
index 4a34b7f6..e112db7c 100644
--- a/tests/primitives/test_python_interpreter.py
+++ b/tests/primitives/test_python_interpreter.py
@@ -297,6 +297,86 @@ def test_tool_default_args():
         assert result == "Hi, World!"
 
 
+def test_tools_re_register_after_process_restart():
+    """Tools should remain callable after Deno subprocess restart."""
+    def echo(message: str = "") -> str:
+        return f"Echo: {message}"
+
+    with PythonInterpreter(tools={"echo": echo}) as interpreter:
+        first = interpreter.execute('print(echo(message="one"))')
+        assert "Echo: one" in first
+
+        first_pid = interpreter.deno_process.pid
+        interpreter.deno_process.kill()
+        interpreter.deno_process.wait()
+
+        second = interpreter.execute('print(echo(message="two"))')
+        assert "Echo: two" in second
+        assert interpreter.deno_process.pid != first_pid
+
+
+def test_mounts_replay_after_process_restart(tmp_path):
+    """Mounted files should still be accessible after subprocess restart."""
+    host_file = tmp_path / "mount_restart.txt"
+    host_file.write_text("restarted-ok")
+    virtual_path = f"/sandbox/{host_file.name}"
+
+    with PythonInterpreter(enable_read_paths=[str(host_file)]) as interpreter:
+        first = interpreter.execute(
+            f"with open({virtual_path!r}, 'r') as f:\n"
+            f"    data = f.read()\n"
+            f"data"
+        )
+        assert first == "restarted-ok"
+
+        first_pid = interpreter.deno_process.pid
+        interpreter.deno_process.kill()
+        interpreter.deno_process.wait()
+
+        second = interpreter.execute(
+            f"with open({virtual_path!r}, 'r') as f:\n"
+            f"    data = f.read()\n"
+            f"data"
+        )
+        assert second == "restarted-ok"
+        assert interpreter.deno_process.pid != first_pid
+
+
+def test_tool_all_positional_args():
+    """Test that tools work when all arguments are passed positionally."""
+
+    def add(a: int, b: int, c: int) -> str:
+        return f"{a + b + c}"
+
+    with PythonInterpreter(tools={"add": add}) as sandbox:
+        result = sandbox.execute("add(1, 2, 3)")
+        assert result == "6"
+
+        # Mixed: some positional, some keyword
+        result = sandbox.execute("add(10, 20, c=30)")
+        assert result == "60"
+
+
+def test_tool_error_surfaces_as_runtime_error():
+    """Test that exceptions raised by a tool surface as RuntimeError in the sandbox."""
+
+    def failing_tool(x: int) -> str:
+        raise ValueError(f"bad value: {x}")
+
+    with PythonInterpreter(tools={"failing_tool": failing_tool}) as sandbox:
+        result = sandbox.execute(
+            "try:\n"
+            "    failing_tool(42)\n"
+            "    output = 'no error'\n"
+            "except RuntimeError as e:\n"
+            "    output = str(e)\n"
+            "output"
+        )
+        assert "ValueError" in result
+        assert "bad value: 42" in result
+
+
+
 # =============================================================================
 # Multi-Output SUBMIT Tests
 # =============================================================================
diff --git a/tests/teleprompt/test_bettertogether.py b/tests/teleprompt/test_bettertogether.py
new file mode 100644
index 00000000..8f4ee498
--- /dev/null
+++ b/tests/teleprompt/test_bettertogether.py
@@ -0,0 +1,744 @@
+"""BetterTogether optimizer tests.
+
+Most of the code in this test file was LLM-generated but has been verified
+to correctly test the BetterTogether optimizer functionality.
+"""
+from unittest.mock import Mock, patch
+
+import pytest
+
+import dspy
+from dspy import Example
+from dspy.predict import Predict
+from dspy.teleprompt import BetterTogether, BootstrapFewShotWithRandomSearch, BootstrapFinetune
+from dspy.teleprompt.teleprompt import Teleprompter
+from dspy.utils.dummies import DummyLM
+
+
+# Define a simple metric function for testing
+def simple_metric(example, prediction, trace=None):
+    return 1.0 if example.output == prediction.output else 0.0
+
+
+examples = [
+    Example(input="What is the oldest known human-made monument?", output="Göbekli Tepe in southeastern Turkiye, dating back to around 9600 BCE").with_inputs("input"),
+    Example(input="Why can't fish fall in love?", output="Because love is in the air").with_inputs("input"),
+    Example(input="What would bring world peace?", output="8 billion people meeting for a tea party in my backyard").with_inputs("input"),
+]
+trainset = examples[:2]
+valset = [examples[2]]
+
+
+class SimpleModule(dspy.Module):
+    def __init__(self, signature):
+        super().__init__()
+        self.predictor = Predict(signature)
+
+    def forward(self, **kwargs):
+        return self.predictor(**kwargs)
+
+
+# ============================================================================
+# Reusable Mock Optimizers
+# ============================================================================
+
+class SimpleOptimizer(Teleprompter):
+    """A simple optimizer that returns the student unchanged."""
+    def compile(self, student, **kwargs):
+        return student
+
+
+class MarkedOptimizer(Teleprompter):
+    """An optimizer that marks the program with a specific identifier."""
+    def __init__(self, marker):
+        self.marker = marker
+
+    def compile(self, student, **kwargs):
+        prog = SimpleModule("input -> output")
+        prog.marker = self.marker
+        return prog
+
+
+class CapturingOptimizer(Teleprompter):
+    """An optimizer that captures the kwargs it receives."""
+    def __init__(self):
+        self.received_kwargs = {}
+
+    def compile(self, student, trainset=None, valset=None, teacher=None,
+                num_trials=None, max_bootstrapped_demos=None, **kwargs):
+        self.received_kwargs = {
+            "trainset": trainset,
+            "valset": valset,
+            "teacher": teacher,
+            "num_trials": num_trials,
+            "max_bootstrapped_demos": max_bootstrapped_demos,
+            **kwargs
+        }
+        return student
+
+
+# ============================================================================
+# Pytest Fixtures
+# ============================================================================
+
+@pytest.fixture
+def student_with_lm():
+    """Create a student module with a DummyLM."""
+    student = SimpleModule("input -> output")
+    lm = DummyLM([{"output": "test"}])
+    student.set_lm(lm)
+    return student
+
+
+@pytest.fixture
+def mock_bt_dependencies():
+    """Mock the common BetterTogether dependencies."""
+    with patch("dspy.teleprompt.bettertogether.eval_candidate_program") as mock_eval, \
+         patch("dspy.teleprompt.bettertogether.launch_lms") as mock_launch, \
+         patch("dspy.teleprompt.bettertogether.kill_lms") as mock_kill:
+        mock_eval.return_value = Mock(score=0.8)
+        yield mock_eval, mock_launch, mock_kill
+
+
+# ============================================================================
+# Tests
+# ============================================================================
+
+def test_bettertogether_import():
+    """Sanity check: Test that BetterTogether can be imported."""
+    assert BetterTogether is not None, "Failed to import BetterTogether"
+
+
+def test_bettertogether_initialization_default():
+    """Test BetterTogether initialization with default optimizers."""
+    optimizer = BetterTogether(metric=simple_metric)
+
+    assert optimizer.metric == simple_metric, "Metric not correctly initialized"
+    assert "p" in optimizer.optimizers, "Default 'p' optimizer not created"
+    assert "w" in optimizer.optimizers, "Default 'w' optimizer not created"
+    assert isinstance(optimizer.optimizers["p"], BootstrapFewShotWithRandomSearch), \
+        "Default 'p' should be BootstrapFewShotWithRandomSearch"
+    assert isinstance(optimizer.optimizers["w"], BootstrapFinetune), \
+        "Default 'w' should be BootstrapFinetune"
+
+
+def test_bettertogether_initialization_custom():
+    """Test BetterTogether initialization with custom optimizers."""
+    custom_p = BootstrapFewShotWithRandomSearch(metric=simple_metric)
+    custom_w = BootstrapFinetune(metric=simple_metric)
+
+    optimizer = BetterTogether(
+        metric=simple_metric,
+        p=custom_p,
+        w=custom_w
+    )
+
+    assert optimizer.optimizers["p"] is custom_p, "Custom 'p' optimizer not set"
+    assert optimizer.optimizers["w"] is custom_w, "Custom 'w' optimizer not set"
+
+
+def test_bettertogether_initialization_invalid_optimizer():
+    """Test that BetterTogether rejects non-Teleprompter optimizers."""
+    try:
+        optimizer = BetterTogether(
+            metric=simple_metric,
+            p="not_a_teleprompter"  # Invalid type
+        )
+        assert False, "Should have raised TypeError for invalid optimizer"
+    except TypeError as e:
+        assert "must be a Teleprompter" in str(e)
+
+
+def test_strategy_validation():
+    """Test strategy validation: valid, invalid, and empty strategies."""
+    optimizer = BetterTogether(metric=simple_metric)
+
+    # Valid strategies should parse without errors
+    valid_strategies = ["p", "w", "p -> w", "w -> p", "p -> w -> p"]
+    for strategy in valid_strategies:
+        parsed = optimizer._prepare_strategy(strategy)
+        assert parsed is not None, f"Failed to parse valid strategy: {strategy}"
+
+    # Invalid strategies should raise ValueError
+    with pytest.raises(ValueError, match="invalid optimizer keys"):
+        optimizer._prepare_strategy("p -> x -> w")
+
+    with pytest.raises(ValueError, match="cannot be empty"):
+        optimizer._prepare_strategy("")
+
+
+def test_compile_basic():
+    """Test basic compilation with mocked optimizers."""
+    from dspy.teleprompt.teleprompt import Teleprompter
+
+    student = SimpleModule("input -> output")
+
+    lm = DummyLM([{"output": "blue"}, {"output": "4"}])
+    student.set_lm(lm)
+
+    # Create a mock Teleprompter that returns the student
+    class MockTeleprompter(Teleprompter):
+        def __init__(self):
+            self.compile_called = False
+
+        def compile(self, student, **kwargs):
+            self.compile_called = True
+            return student
+
+    mock_p = MockTeleprompter()
+    optimizer = BetterTogether(metric=simple_metric, p=mock_p)
+
+    # Mock evaluation to avoid actually running the metric
+    with patch("dspy.teleprompt.bettertogether.eval_candidate_program") as mock_eval:
+        mock_eval.return_value = Mock(score=0.8)
+
+        with patch("dspy.teleprompt.bettertogether.launch_lms"):
+            with patch("dspy.teleprompt.bettertogether.kill_lms"):
+                compiled = optimizer.compile(
+                    student,
+                    trainset=trainset,
+                    valset=valset,
+                    strategy="p"
+                )
+
+    assert compiled is not None, "Compilation returned None"
+    assert hasattr(compiled, "candidate_programs"), "Missing candidate_programs attribute"
+    assert hasattr(compiled, "flag_compilation_error_occurred"), "Missing flag_compilation_error_occurred attribute"
+    assert mock_p.compile_called, "Mock optimizer compile was not called"
+
+
+def test_trainset_validation():
+    """Test that empty trainset is rejected."""
+    optimizer = BetterTogether(metric=simple_metric)
+    student = SimpleModule("input -> output")
+
+    lm = DummyLM([{"output": "test"}])
+    student.set_lm(lm)
+
+    try:
+        optimizer.compile(student, trainset=[], valset=valset)
+        assert False, "Should have raised ValueError for empty trainset"
+    except ValueError as e:
+        assert "cannot be empty" in str(e).lower()
+
+
+def test_valset_ratio_validation():
+    """Test that invalid valset_ratio is rejected."""
+    optimizer = BetterTogether(metric=simple_metric)
+    student = SimpleModule("input -> output")
+
+    lm = DummyLM([{"output": "test"}])
+    student.set_lm(lm)
+
+    # Test valset_ratio >= 1
+    try:
+        optimizer.compile(student, trainset=trainset, valset_ratio=1.0)
+        assert False, "Should have raised ValueError for valset_ratio >= 1"
+    except ValueError as e:
+        assert "must be in range [0, 1)" in str(e)
+
+    # Test valset_ratio < 0
+    try:
+        optimizer.compile(student, trainset=trainset, valset_ratio=-0.1)
+        assert False, "Should have raised ValueError for valset_ratio < 0"
+    except ValueError as e:
+        assert "must be in range [0, 1)" in str(e)
+
+
+def test_optimizer_compile_args_validation():
+    """Test that optimizer_compile_args is validated correctly."""
+    optimizer = BetterTogether(metric=simple_metric)
+
+    # Test invalid optimizer key
+    try:
+        optimizer._prepare_optimizer_compile_args(
+            {"invalid_key": {"num_trials": 10}},
+            teacher=None
+        )
+        assert False, "Should have raised ValueError for invalid optimizer key"
+    except ValueError as e:
+        assert "invalid optimizer key" in str(e).lower()
+
+
+def test_student_in_optimizer_compile_args():
+    """Test that 'student' in optimizer_compile_args is rejected."""
+    optimizer = BetterTogether(metric=simple_metric)
+
+    try:
+        optimizer._validate_compile_args(
+            optimizer.optimizers["p"],
+            "p",
+            {"student": SimpleModule("input -> output")}
+        )
+        assert False, "Should have raised ValueError for 'student' in compile_args"
+    except ValueError as e:
+        assert "student" in str(e).lower()
+        assert "not allowed" in str(e).lower()
+
+
+def test_compile_args_passed_to_optimizer(student_with_lm, mock_bt_dependencies):
+    """Test that optimizer_compile_args are correctly passed to optimizers."""
+    mock_eval, _, _ = mock_bt_dependencies
+    mock_eval.return_value = Mock(score=0.9)
+
+    mock_p = CapturingOptimizer()
+    optimizer = BetterTogether(metric=simple_metric, p=mock_p)
+
+    # Define custom compile args for optimizer 'p'
+    custom_args = {"num_trials": 20, "max_bootstrapped_demos": 8}
+
+    optimizer.compile(
+        student_with_lm,
+        trainset=trainset,
+        valset=valset,
+        strategy="p",
+        optimizer_compile_args={"p": custom_args}
+    )
+
+    # Verify the custom args were passed to the optimizer
+    assert mock_p.received_kwargs is not None, "Optimizer compile was not called"
+    assert "num_trials" in mock_p.received_kwargs, "num_trials not passed to optimizer"
+    assert mock_p.received_kwargs["num_trials"] == 20, "num_trials value incorrect"
+    assert "max_bootstrapped_demos" in mock_p.received_kwargs, "max_bootstrapped_demos not passed"
+    assert mock_p.received_kwargs["max_bootstrapped_demos"] == 8, "max_bootstrapped_demos value incorrect"
+
+
+def test_compile_args_multi_optimizer_strategy():
+    """Test that different optimizers in a strategy receive their respective compile_args."""
+    from dspy.teleprompt.teleprompt import Teleprompter
+
+    student = SimpleModule("input -> output")
+    lm = DummyLM([{"output": "test"}])
+    student.set_lm(lm)
+
+    # Create mock Teleprompters that capture their compile kwargs
+    class PromptOptimizer(Teleprompter):
+        def __init__(self):
+            self.received_kwargs = {}
+
+        def compile(self, student, trainset=None, num_trials=None, **kwargs):
+            self.received_kwargs = {
+                "trainset": trainset,
+                "num_trials": num_trials,
+                **kwargs
+            }
+            return student
+
+    class WeightOptimizer(Teleprompter):
+        def __init__(self):
+            self.received_kwargs = {}
+
+        def compile(self, student, trainset=None, num_batches=None, **kwargs):
+            self.received_kwargs = {
+                "trainset": trainset,
+                "num_batches": num_batches,
+                **kwargs
+            }
+            return student
+
+    mock_p = PromptOptimizer()
+    mock_w = WeightOptimizer()
+    optimizer = BetterTogether(metric=simple_metric, p=mock_p, w=mock_w)
+
+    # Define different compile args for each optimizer
+    compile_args = {
+        "p": {"num_trials": 10},
+        "w": {"num_batches": 5}
+    }
+
+    with patch("dspy.teleprompt.bettertogether.eval_candidate_program") as mock_eval:
+        mock_eval.return_value = Mock(score=0.85)
+        with patch("dspy.teleprompt.bettertogether.launch_lms"):
+            with patch("dspy.teleprompt.bettertogether.kill_lms"):
+                with patch.object(optimizer, "_models_changed", return_value=False):
+                    optimizer.compile(
+                        student,
+                        trainset=trainset,
+                        valset=valset,
+                        strategy="p -> w",
+                        optimizer_compile_args=compile_args
+                    )
+
+    # Verify each optimizer received its specific args
+    assert mock_p.received_kwargs is not None, "Optimizer 'p' compile was not called"
+    assert "num_trials" in mock_p.received_kwargs, "num_trials not passed to optimizer 'p'"
+    assert mock_p.received_kwargs["num_trials"] == 10, "num_trials value incorrect for 'p'"
+    assert mock_p.received_kwargs.get("num_batches") is None, "Optimizer 'p' should not receive 'w' args"
+
+    assert mock_w.received_kwargs is not None, "Optimizer 'w' compile was not called"
+    assert "num_batches" in mock_w.received_kwargs, "num_batches not passed to optimizer 'w'"
+    assert mock_w.received_kwargs["num_batches"] == 5, "num_batches value incorrect for 'w'"
+    assert mock_w.received_kwargs.get("num_trials") is None, "Optimizer 'w' should not receive 'p' args"
+
+
+def test_compile_args_override_global_params():
+    """Test that optimizer_compile_args override global trainset/valset/teacher parameters."""
+    from dspy.teleprompt.teleprompt import Teleprompter
+
+    student = SimpleModule("input -> output")
+    lm = DummyLM([{"output": "test"}])
+    student.set_lm(lm)
+
+    # Create a mock Teleprompter that captures compile kwargs
+    class CapturingTeleprompter(Teleprompter):
+        def __init__(self):
+            self.received_kwargs = {}
+
+        def compile(self, student, trainset=None, valset=None, teacher=None, **kwargs):
+            self.received_kwargs = {
+                "trainset": trainset,
+                "valset": valset,
+                "teacher": teacher,
+                **kwargs
+            }
+            return student
+
+    mock_p = CapturingTeleprompter()
+    optimizer = BetterTogether(metric=simple_metric, p=mock_p)
+
+    # Create override values
+    override_trainset = [examples[2]]  # Different from global trainset
+    override_valset = [examples[0]]    # Different from global valset
+    override_teacher = SimpleModule("input -> output")
+
+    # Pass global values to compile, but override them in optimizer_compile_args
+    compile_args = {
+        "p": {
+            "trainset": override_trainset,
+            "valset": override_valset,
+            "teacher": override_teacher,
+        }
+    }
+
+    with patch("dspy.teleprompt.bettertogether.eval_candidate_program") as mock_eval:
+        mock_eval.return_value = Mock(score=0.9)
+        with patch("dspy.teleprompt.bettertogether.launch_lms"):
+            with patch("dspy.teleprompt.bettertogether.kill_lms"):
+                optimizer.compile(
+                    student,
+                    trainset=trainset,  # Global trainset (examples[:2])
+                    valset=valset,      # Global valset (examples[2])
+                    teacher=None,       # Global teacher (None)
+                    strategy="p",
+                    optimizer_compile_args=compile_args
+                )
+
+    # Verify the optimizer received the override values, not the global ones
+    assert mock_p.received_kwargs["trainset"] == override_trainset, \
+        "Optimizer should receive override trainset from compile_args"
+    assert mock_p.received_kwargs["valset"] == override_valset, \
+        "Optimizer should receive override valset from compile_args"
+    assert mock_p.received_kwargs["teacher"] is override_teacher, \
+        "Optimizer should receive override teacher from compile_args"
+
+    # Verify they're different from the global values
+    assert mock_p.received_kwargs["trainset"] != trainset, \
+        "Override trainset should differ from global trainset"
+    assert mock_p.received_kwargs["valset"] != valset, \
+        "Override valset should differ from global valset"
+
+
+def test_trainset_shuffling_between_steps():
+    """Test that trainset is shuffled between steps when shuffle_trainset_between_steps=True."""
+    from dspy.teleprompt.teleprompt import Teleprompter
+
+    student = SimpleModule("input -> output")
+    lm = DummyLM([{"output": "test"}])
+    student.set_lm(lm)
+
+    # Create mock optimizers that capture the trainset they receive
+    trainsets_received = []
+
+    class TrainsetCapturingOptimizer(Teleprompter):
+        def compile(self, student, trainset=None, **kwargs):
+            trainsets_received.append(trainset)
+            return student
+
+    mock_p = TrainsetCapturingOptimizer()
+    mock_w = TrainsetCapturingOptimizer()
+    optimizer = BetterTogether(metric=simple_metric, p=mock_p, w=mock_w)
+
+    with patch("dspy.teleprompt.bettertogether.eval_candidate_program") as mock_eval:
+        mock_eval.return_value = Mock(score=0.8)
+        with patch("dspy.teleprompt.bettertogether.launch_lms"):
+            with patch("dspy.teleprompt.bettertogether.kill_lms"):
+                with patch.object(optimizer, "_models_changed", return_value=False):
+                    optimizer.compile(
+                        student,
+                        trainset=trainset,
+                        valset=valset,
+                        strategy="p -> w",
+                        shuffle_trainset_between_steps=True
+                    )
+
+    # Verify trainset was shuffled between steps
+    assert len(trainsets_received) == 2, "Should have received trainset twice (for p and w)"
+    trainset_p = trainsets_received[0]
+    trainset_w = trainsets_received[1]
+
+    # Both should have same examples but potentially different order
+    assert len(trainset_p) == len(trainset_w), "Trainsets should have same length"
+    # With shuffling enabled and only 2 examples, there's a 50% chance they're in different order
+    # We can't reliably test order difference with small dataset, but we can verify they contain same examples
+    assert set(id(ex) for ex in trainset_p) == set(id(ex) for ex in trainset_w), \
+        "Trainsets should contain the same example objects"
+
+
+def test_strategy_execution_order():
+    """Test that strategy steps are executed in order and programs are passed correctly."""
+    from dspy.teleprompt.teleprompt import Teleprompter
+
+    student = SimpleModule("input -> output")
+    lm = DummyLM([{"output": "test"}])
+    student.set_lm(lm)
+
+    # Track execution order and what program each optimizer receives
+    execution_log = []
+
+    class LoggingOptimizer(Teleprompter):
+        def __init__(self, name):
+            self.name = name
+
+        def compile(self, student, **kwargs):
+            # Create a new student with a marker to track the optimization path
+            optimized = SimpleModule("input -> output")
+            if not hasattr(student, "optimization_path"):
+                optimized.optimization_path = [self.name]
+            else:
+                optimized.optimization_path = student.optimization_path + [self.name]
+            execution_log.append((self.name, optimized.optimization_path.copy()))
+            return optimized
+
+    mock_p = LoggingOptimizer("p")
+    mock_w = LoggingOptimizer("w")
+    optimizer = BetterTogether(metric=simple_metric, p=mock_p, w=mock_w)
+
+    with patch("dspy.teleprompt.bettertogether.eval_candidate_program") as mock_eval:
+        mock_eval.return_value = Mock(score=0.85)
+        with patch("dspy.teleprompt.bettertogether.launch_lms"):
+            with patch("dspy.teleprompt.bettertogether.kill_lms"):
+                with patch.object(optimizer, "_models_changed", return_value=False):
+                    result = optimizer.compile(
+                        student,
+                        trainset=trainset,
+                        valset=valset,
+                        strategy="p -> w -> p"
+                    )
+
+    # Verify execution order
+    assert len(execution_log) == 3, "Should have executed 3 optimization steps"
+    assert execution_log[0] == ("p", ["p"]), "First step should be 'p'"
+    assert execution_log[1] == ("w", ["p", "w"]), "Second step should be 'w' receiving output from 'p'"
+    assert execution_log[2] == ("p", ["p", "w", "p"]), "Third step should be 'p' receiving output from 'w'"
+
+
+def test_lm_lifecycle_management():
+    """Test that launch_lms and kill_lms are called appropriately between steps."""
+    from dspy.teleprompt.teleprompt import Teleprompter
+
+    student = SimpleModule("input -> output")
+    lm = DummyLM([{"output": "test"}])
+    student.set_lm(lm)
+
+    class SimpleOptimizer(Teleprompter):
+        def compile(self, student, **kwargs):
+            return student
+
+    mock_p = SimpleOptimizer()
+    mock_w = SimpleOptimizer()
+    optimizer = BetterTogether(metric=simple_metric, p=mock_p, w=mock_w)
+
+    with patch("dspy.teleprompt.bettertogether.eval_candidate_program") as mock_eval:
+        mock_eval.return_value = Mock(score=0.8)
+        with patch("dspy.teleprompt.bettertogether.launch_lms") as mock_launch:
+            with patch("dspy.teleprompt.bettertogether.kill_lms") as mock_kill:
+                with patch.object(optimizer, "_models_changed", return_value=True):
+                    optimizer.compile(
+                        student,
+                        trainset=trainset,
+                        valset=valset,
+                        strategy="p -> w"
+                    )
+
+    # Verify launch and kill were called
+    # When models change (which we mocked to return True), launch should be called
+    assert mock_launch.called, "launch_lms should be called when models change"
+    assert mock_kill.called, "kill_lms should be called when models change"
+
+
+def test_error_handling_returns_best_program():
+    """Test that if a step fails, the best program found so far is still returned."""
+    from dspy.teleprompt.teleprompt import Teleprompter
+
+    student = SimpleModule("input -> output")
+    lm = DummyLM([{"output": "test"}])
+    student.set_lm(lm)
+
+    # Create optimizers where the second one will fail
+    class SuccessfulOptimizer(Teleprompter):
+        def compile(self, student, **kwargs):
+            optimized = SimpleModule("input -> output")
+            optimized.step_name = "p_success"
+            return optimized
+
+    class FailingOptimizer(Teleprompter):
+        def compile(self, student, **kwargs):
+            raise RuntimeError("Intentional failure for testing")
+
+    mock_p = SuccessfulOptimizer()
+    mock_w = FailingOptimizer()
+    optimizer = BetterTogether(metric=simple_metric, p=mock_p, w=mock_w)
+
+    # First call succeeds with score 0.7, second call (to failing optimizer) fails
+    with patch("dspy.teleprompt.bettertogether.eval_candidate_program") as mock_eval:
+        mock_eval.side_effect = [
+            Mock(score=0.5),  # Baseline
+            Mock(score=0.7),  # After p (success)
+        ]
+        with patch("dspy.teleprompt.bettertogether.launch_lms"):
+            with patch("dspy.teleprompt.bettertogether.kill_lms"):
+                with patch.object(optimizer, "_models_changed", return_value=False):
+                    result = optimizer.compile(
+                        student,
+                        trainset=trainset,
+                        valset=valset,
+                        strategy="p -> w"
+                    )
+
+    # Verify a program was returned despite the failure
+    assert result is not None, "Should return a program even if a step fails"
+    assert hasattr(result, "flag_compilation_error_occurred"), "Should have error flag"
+    assert result.flag_compilation_error_occurred is True, "Error flag should be True"
+    assert hasattr(result, "candidate_programs"), "Should have candidate_programs"
+    assert len(result.candidate_programs) > 0, "Should have at least one candidate program"
+
+
+@pytest.mark.parametrize("test_valset,expected_marker,test_description", [
+    (valset, "p_optimized", "With valset: returns best score (p), not latest (w)"),
+    (None, "w_optimized", "Without valset: returns latest program (w)"),
+])
+def test_program_selection(student_with_lm, test_valset, expected_marker, test_description):
+    """Test program selection logic with and without validation set."""
+    mock_p = MarkedOptimizer("p_optimized")
+    mock_w = MarkedOptimizer("w_optimized")
+    optimizer = BetterTogether(metric=simple_metric, p=mock_p, w=mock_w)
+
+    # Set up scores: baseline=0.5, p=0.9 (best), w=0.7
+    # When test_valset is provided, best score wins; when None, latest wins
+    with patch("dspy.teleprompt.bettertogether.eval_candidate_program") as mock_eval:
+        if test_valset is not None:
+            mock_eval.side_effect = [
+                Mock(score=0.5),  # Baseline
+                Mock(score=0.9),  # After p (best score)
+                Mock(score=0.7),  # After w (lower than p)
+            ]
+        with patch("dspy.teleprompt.bettertogether.launch_lms"):
+            with patch("dspy.teleprompt.bettertogether.kill_lms"):
+                with patch.object(optimizer, "_models_changed", return_value=False):
+                    result = optimizer.compile(
+                        student_with_lm,
+                        trainset=trainset,
+                        valset=test_valset,
+                        strategy="p -> w"
+                    )
+
+    # Verify the correct program was returned based on valset presence
+    assert hasattr(result, "marker"), "Result should have marker"
+    assert result.marker == expected_marker, test_description
+
+
+def test_candidate_programs_structure(student_with_lm):
+    """Test that candidate_programs has the correct structure and content."""
+    mock_p = MarkedOptimizer("p")
+    mock_w = MarkedOptimizer("w")
+    optimizer = BetterTogether(metric=simple_metric, p=mock_p, w=mock_w)
+
+    # Set up scores: baseline=0.5, p=0.8, w=0.9 (best)
+    with patch("dspy.teleprompt.bettertogether.eval_candidate_program") as mock_eval:
+        mock_eval.side_effect = [
+            Mock(score=0.5),  # Baseline
+            Mock(score=0.8),  # After p
+            Mock(score=0.9),  # After w (best)
+        ]
+        with patch("dspy.teleprompt.bettertogether.launch_lms"):
+            with patch("dspy.teleprompt.bettertogether.kill_lms"):
+                with patch.object(optimizer, "_models_changed", return_value=False):
+                    result = optimizer.compile(
+                        student_with_lm,
+                        trainset=trainset,
+                        valset=valset,
+                        strategy="p -> w"
+                    )
+
+    # Verify candidate_programs exists and has correct structure
+    assert hasattr(result, "candidate_programs"), "Result should have candidate_programs attribute"
+    candidates = result.candidate_programs
+
+    # Should have 3 candidates: baseline, p, w
+    assert len(candidates) == 3, f"Should have 3 candidates, got {len(candidates)}"
+
+    # Each candidate should have the required keys
+    for i, candidate in enumerate(candidates):
+        assert "score" in candidate, f"Candidate {i} missing 'score' key"
+        assert "program" in candidate, f"Candidate {i} missing 'program' key"
+        assert "strategy" in candidate, f"Candidate {i} missing 'strategy' key"
+        assert isinstance(candidate["score"], (int, float)), f"Candidate {i} score should be numeric"
+        assert isinstance(candidate["program"], dspy.Module), f"Candidate {i} program should be a Module"
+        assert isinstance(candidate["strategy"], (str, type(None))), f"Candidate {i} strategy should be str or None"
+
+    # Candidates should be sorted by score (best first)
+    scores = [c["score"] for c in candidates]
+    assert scores == sorted(scores, reverse=True), "Candidates should be sorted by score (descending)"
+
+    # Verify the best candidate is first
+    assert candidates[0]["score"] == 0.9, "Best candidate should have score 0.9"
+    assert candidates[0]["program"].marker == "w", "Best candidate should be from optimizer 'w'"
+
+    # Verify baseline candidate
+    baseline = [c for c in candidates if c["strategy"] is None or c["strategy"] == ""]
+    assert len(baseline) == 1, "Should have exactly one baseline candidate"
+    assert baseline[0]["score"] == 0.5, "Baseline should have score 0.5"
+
+
+def test_empty_valset_handling(student_with_lm):
+    """Test behavior when valset is an empty list vs None."""
+    # Test with empty list []
+    mock_p = MarkedOptimizer("optimized")
+    optimizer = BetterTogether(metric=simple_metric, p=mock_p)
+
+    with patch("dspy.teleprompt.bettertogether.launch_lms"):
+        with patch("dspy.teleprompt.bettertogether.kill_lms"):
+            with patch.object(optimizer, "_models_changed", return_value=False):
+                result = optimizer.compile(
+                    student_with_lm,
+                    trainset=trainset,
+                    valset=[],  # Empty list (not None)
+                    strategy="p"
+                )
+
+    # With empty valset, should return latest program (same behavior as valset=None)
+    assert hasattr(result, "marker"), "Result should have marker"
+    assert result.marker == "optimized", "Should return the latest program when valset is empty list"
+    assert hasattr(result, "candidate_programs"), "Should have candidate_programs"
+
+    # Test with None - create fresh student and optimizer
+    student2 = SimpleModule("input -> output")
+    lm = DummyLM([{"output": "test"}])
+    student2.set_lm(lm)
+
+    mock_p2 = MarkedOptimizer("optimized")
+    optimizer2 = BetterTogether(metric=simple_metric, p=mock_p2)
+
+    with patch("dspy.teleprompt.bettertogether.launch_lms"):
+        with patch("dspy.teleprompt.bettertogether.kill_lms"):
+            with patch.object(optimizer2, "_models_changed", return_value=False):
+                result2 = optimizer2.compile(
+                    student2,
+                    trainset=trainset,
+                    valset=None,  # Explicit None
+                    strategy="p"
+                )
+
+    # Both should behave the same way
+    assert hasattr(result2, "marker"), "Result2 should have marker"
+    assert result2.marker == "optimized", "Should return the latest program when valset is None"
diff --git a/tests/utils/test_parallelizer.py b/tests/utils/test_parallelizer.py
index 128614ff..5903f26b 100644
--- a/tests/utils/test_parallelizer.py
+++ b/tests/utils/test_parallelizer.py
@@ -1,3 +1,4 @@
+import threading
 import time
 
 import pytest
@@ -83,3 +84,85 @@ def test_parallel_executor_tracks_failed_indices_and_exceptions():
     assert str(executor.exceptions_map[2]) == "test error for 3"
     assert isinstance(executor.exceptions_map[4], RuntimeError)
     assert str(executor.exceptions_map[4]) == "test error for 5"
+
+
+def test_sequential_execution_runs_on_main_thread():
+    """With num_threads=1, all work should run on the main thread (not in a ThreadPoolExecutor)."""
+    execution_threads = []
+
+    def task(item):
+        execution_threads.append(threading.current_thread())
+        return item * 2
+
+    data = [1, 2, 3, 4, 5]
+    executor = ParallelExecutor(num_threads=1)
+    results = executor.execute(task, data)
+
+    assert results == [2, 4, 6, 8, 10]
+    assert all(t is threading.main_thread() for t in execution_threads)
+
+
+def test_sequential_max_errors_not_met():
+    """Sequential execution should handle errors without crashing when max_errors is not reached."""
+    def task(item):
+        if item == 3:
+            raise ValueError("Intentional error")
+        return item
+
+    data = [1, 2, 3, 4, 5]
+    executor = ParallelExecutor(num_threads=1, max_errors=2)
+
+    results = executor.execute(task, data)
+
+    assert results == [1, 2, None, 4, 5]
+
+
+def test_sequential_max_errors_exceeded():
+    """Sequential execution should cancel when max_errors is reached."""
+    def task(item):
+        if item == 3:
+            raise ValueError("Intentional error")
+        return item
+
+    data = [1, 2, 3, 4, 5]
+    executor = ParallelExecutor(num_threads=1, max_errors=1)
+
+    with pytest.raises(Exception, match="Execution cancelled due to errors or interruption."):
+        executor.execute(task, data)
+
+
+def test_sequential_tracks_failed_indices_and_exceptions():
+    """Sequential execution should track failed indices and exception objects."""
+    def task(item):
+        if item == 3:
+            raise ValueError("test error for 3")
+        if item == 5:
+            raise RuntimeError("test error for 5")
+        return item
+
+    data = [1, 2, 3, 4, 5]
+    executor = ParallelExecutor(num_threads=1, max_errors=3)
+
+    results = executor.execute(task, data)
+
+    assert results == [1, 2, None, 4, None]
+
+    assert sorted(executor.failed_indices) == [2, 4]
+
+    assert len(executor.exceptions_map) == 2
+    assert isinstance(executor.exceptions_map[2], ValueError)
+    assert str(executor.exceptions_map[2]) == "test error for 3"
+    assert isinstance(executor.exceptions_map[4], RuntimeError)
+    assert str(executor.exceptions_map[4]) == "test error for 5"
+
+
+def test_sequential_compare_results():
+    """Sequential execution should track and display comparison metrics correctly."""
+    def task(item):
+        return item, item > 2  # (result, score)
+
+    data = [1, 2, 3, 4, 5]
+    executor = ParallelExecutor(num_threads=1, compare_results=True, disable_progress_bar=True)
+    results = executor.execute(task, data)
+
+    assert results == [(1, False), (2, False), (3, True), (4, True), (5, True)]
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/clients/test_lm.py tests/evaluate/test_evaluate.py tests/predict/test_predict.py tests/primitives/test_python_interpreter.py tests/teleprompt/test_bettertogether.py tests/utils/test_parallelizer.py
: '>>>>> End Test Output'
git checkout cfc076a98c1e5299d846e0e544a78f73df6034ac tests/clients/test_lm.py tests/evaluate/test_evaluate.py tests/predict/test_predict.py tests/primitives/test_python_interpreter.py tests/utils/test_parallelizer.py
