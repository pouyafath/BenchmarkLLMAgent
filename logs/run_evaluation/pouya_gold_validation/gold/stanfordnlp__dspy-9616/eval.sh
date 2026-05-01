#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff a2b01f3404cf85624f9b6e3215972fc2f1c65c0e
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout a2b01f3404cf85624f9b6e3215972fc2f1c65c0e tests/signatures/test_signature.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/signatures/test_signature.py b/tests/signatures/test_signature.py
index 64602333..ebd3eccb 100644
--- a/tests/signatures/test_signature.py
+++ b/tests/signatures/test_signature.py
@@ -1,6 +1,8 @@
+import pickle
 from types import UnionType
 from typing import Any, Optional, Union
 
+import cloudpickle
 import pydantic
 import pytest
 
@@ -578,3 +580,32 @@ def test_pep604_union_type_with_custom_types():
     custom_obj = CustomType(value="test")
     pred = dspy.Predict(sig)(input=custom_obj)
     assert pred.output == "processed"
+
+
+def test_signature_cloudpickle_roundtrip():
+    class MySignature(Signature):
+        """Answer the question."""
+        context: list[str] = InputField()
+        question: str = InputField()
+        answer: str = OutputField()
+
+    data = cloudpickle.dumps(MySignature)
+    loaded = pickle.loads(data)
+
+    assert loaded.__name__ == "MySignature"
+    assert list(loaded.input_fields.keys()) == ["context", "question"]
+    assert list(loaded.output_fields.keys()) == ["answer"]
+    assert loaded.instructions == "Answer the question."
+
+
+def test_predict_cloudpickle_roundtrip():
+    class QA(Signature):
+        """Answer the question."""
+        question: str = InputField()
+        answer: str = OutputField()
+
+    predict = dspy.Predict(QA)
+    data = cloudpickle.dumps(predict)
+    loaded = pickle.loads(data)
+
+    assert list(loaded.signature.fields.keys()) == ["question", "answer"]

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/signatures/test_signature.py
: '>>>>> End Test Output'
git checkout a2b01f3404cf85624f9b6e3215972fc2f1c65c0e tests/signatures/test_signature.py
