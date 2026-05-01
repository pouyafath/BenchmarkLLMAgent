#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 8d931240069072d52fe7a8f8581ad4ecf5cd4da4
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[dev]' || python -m pip install -e .
git checkout 8d931240069072d52fe7a8f8581ad4ecf5cd4da4 tests/clients/test_lm.py tests/teleprompt/test_utils.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/clients/test_lm.py b/tests/clients/test_lm.py
index 15e0e02f..71e5ee5a 100644
--- a/tests/clients/test_lm.py
+++ b/tests/clients/test_lm.py
@@ -190,7 +190,7 @@ def test_zero_temperature_rollout_warns_once(monkeypatch):
 
     monkeypatch.setattr(litellm, "completion", fake_completion)
 
-    lm = dspy.LM(model="openai/dspy-test-model", model_type="chat")
+    lm = dspy.LM(model="openai/dspy-test-model", model_type="chat", temperature=0)
     with pytest.warns(UserWarning, match="rollout_id has no effect"):
         lm("Query", rollout_id=1)
     with warnings.catch_warnings(record=True) as record:
@@ -199,6 +199,23 @@ def test_zero_temperature_rollout_warns_once(monkeypatch):
         assert len(record) == 0
 
 
+def test_rollout_id_with_default_temperature_does_not_warn(monkeypatch):
+    def fake_completion(*, cache, num_retries, retry_strategy, **request):
+        return ModelResponse(
+            choices=[Choices(message=Message(role="assistant", content="Hi!"))],
+            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
+            model="openai/gpt-5-nano",
+        )
+
+    monkeypatch.setattr(litellm, "completion", fake_completion)
+
+    with warnings.catch_warnings(record=True) as record:
+        warnings.simplefilter("always")
+        lm = dspy.LM(model="openai/gpt-5-nano", model_type="chat", rollout_id=1)
+        lm("Query")
+        assert len(record) == 0
+
+
 def test_text_lms_can_be_queried(litellm_test_server):
     api_base, _ = litellm_test_server
     expected_response = ["Hi!"]
diff --git a/tests/teleprompt/test_utils.py b/tests/teleprompt/test_utils.py
index 443dc2bd..4d73b6db 100644
--- a/tests/teleprompt/test_utils.py
+++ b/tests/teleprompt/test_utils.py
@@ -1,7 +1,8 @@
-from unittest.mock import Mock
+from unittest.mock import Mock, patch
 
 import dspy
-from dspy.teleprompt.utils import eval_candidate_program
+from dspy.teleprompt.utils import create_n_fewshot_demo_sets, eval_candidate_program
+from dspy.utils.dummies import DummyLM
 
 
 class DummyModule(dspy.Module):
@@ -50,3 +51,47 @@ def test_eval_candidate_program_failure():
     result = eval_candidate_program(batch_size, trainset, candidate_program, evaluate)
 
     assert result.score == 0.0
+
+
+def test_create_n_fewshot_demo_sets_passes_metric_threshold_for_unshuffled():
+    """Verify that metric_threshold is passed to BootstrapFewShot for the unshuffled (seed=-1) case.
+
+    Regression test for https://github.com/stanfordnlp/dspy/issues/9308
+    """
+    student = DummyModule()
+    student.predictor = dspy.Predict("input -> output")
+    trainset = [dspy.Example(input="test", output="test").with_inputs("input")]
+
+    lm = DummyLM([{"output": "test"}])
+    dspy.configure(lm=lm)
+
+    with patch("dspy.teleprompt.utils.BootstrapFewShot") as MockBootstrap:
+        mock_instance = Mock()
+        mock_instance.compile.return_value = student
+        MockBootstrap.return_value = mock_instance
+
+        create_n_fewshot_demo_sets(
+            student=student,
+            num_candidate_sets=4,  # -3, -2, -1, 0 → hits seed=-1
+            trainset=trainset,
+            max_labeled_demos=1,
+            max_bootstrapped_demos=1,
+            metric=lambda ex, pred, trace=None: 1.0,
+            teacher_settings={},
+            metric_threshold=0.9,
+        )
+
+        # Find the call where seed == -1 (unshuffled few-shot)
+        # BootstrapFewShot should be called at least twice: once for seed=-1, once for seed>=0
+        calls = MockBootstrap.call_args_list
+        assert len(calls) >= 1, "BootstrapFewShot was never called"
+
+        # Every BootstrapFewShot call should include metric_threshold
+        for call in calls:
+            _, kwargs = call
+            assert "metric_threshold" in kwargs, (
+                f"metric_threshold missing from BootstrapFewShot call: {kwargs}"
+            )
+            assert kwargs["metric_threshold"] == 0.9, (
+                f"metric_threshold={kwargs['metric_threshold']}, expected 0.9"
+            )

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/clients/test_lm.py tests/teleprompt/test_utils.py
: '>>>>> End Test Output'
git checkout 8d931240069072d52fe7a8f8581ad4ecf5cd4da4 tests/clients/test_lm.py tests/teleprompt/test_utils.py
