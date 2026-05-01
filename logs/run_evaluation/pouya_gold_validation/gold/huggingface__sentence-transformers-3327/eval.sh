#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 03dff58425e0b9c2f52f6f29d51f430d0b60795a
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 03dff58425e0b9c2f52f6f29d51f430d0b60795a tests/test_sentence_transformer.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_sentence_transformer.py b/tests/test_sentence_transformer.py
index f9bef5a..96694cd 100644
--- a/tests/test_sentence_transformer.py
+++ b/tests/test_sentence_transformer.py
@@ -376,6 +376,27 @@ def test_save_load_prompts() -> None:
         assert fresh_model.default_prompt_name == "query"
 
 
+def test_prompt_output_value_None(stsb_bert_tiny_model_reused) -> None:
+    model = stsb_bert_tiny_model_reused
+    outputs = model.encode(
+        ["Text one", "Text two"],
+        prompt="query: ",
+        output_value=None,
+    )
+    assert len(outputs) == 2
+    assert isinstance(outputs, list)
+    expected_keys = {
+        "input_ids",
+        "token_type_ids",
+        "attention_mask",
+        "sentence_embedding",
+        "token_embeddings",
+        "prompt_length",
+    }
+    assert set(outputs[0].keys()) == expected_keys
+    assert set(outputs[1].keys()) == expected_keys
+
+
 @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA must be available to test float16 support.")
 def test_load_with_torch_dtype() -> None:
     model = SentenceTransformer("sentence-transformers-testing/stsb-bert-tiny-safetensors")
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_sentence_transformer.py
: '>>>>> End Test Output'
git checkout 03dff58425e0b9c2f52f6f29d51f430d0b60795a tests/test_sentence_transformer.py
