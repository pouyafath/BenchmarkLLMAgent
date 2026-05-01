#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff fd93c38ca0548beaf512d6e4c3506c04d291cdb4
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[dev]' || python -m pip install -e .
git checkout fd93c38ca0548beaf512d6e4c3506c04d291cdb4 tests/predict/test_predict.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/predict/test_predict.py b/tests/predict/test_predict.py
index f36c7e28..65b73636 100644
--- a/tests/predict/test_predict.py
+++ b/tests/predict/test_predict.py
@@ -763,3 +763,26 @@ def test_per_module_history_disabled():
     for _ in range(10):
         program(question="What is the capital of France?")
     assert len(program.history) == 0
+
+def test_input_field_default_value():
+    class SpyLM(dspy.LM):
+        def __init__(self):
+            super().__init__("dummy")
+            self.calls = []
+
+        def __call__(self, prompt=None, messages=None, **kwargs):
+            self.calls.append({"messages": messages})
+            return ["[[ ## answer ## ]]\ntest"]
+
+    class SignatureWithDefault(dspy.Signature):
+        context: str = dspy.InputField(default="DEFAULT_CONTEXT")
+        question: str = dspy.InputField()
+        answer: str = dspy.OutputField()
+
+    lm = SpyLM()
+    dspy.configure(lm=lm)
+    predictor = Predict(SignatureWithDefault)
+    predictor(question="test")
+
+    user_message = lm.calls[0]["messages"][-1]["content"]
+    assert "DEFAULT_CONTEXT" in user_message
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/predict/test_predict.py
: '>>>>> End Test Output'
git checkout fd93c38ca0548beaf512d6e4c3506c04d291cdb4 tests/predict/test_predict.py
