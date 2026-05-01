#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff acac63ef35d973b7eff18d8971b64f3dc7249d4e
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[torch,metrics]' || python -m pip install -e .
git checkout acac63ef35d973b7eff18d8971b64f3dc7249d4e tests/data/test_mm_plugin.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/data/test_mm_plugin.py b/tests/data/test_mm_plugin.py
index 3187004a..17c7f08a 100644
--- a/tests/data/test_mm_plugin.py
+++ b/tests/data/test_mm_plugin.py
@@ -57,7 +57,7 @@ TEXT_MESSAGES = [
 ]
 
 VIDEO_MESSAGES = [
-    {"role": "user", "content": "<video>What is in this viode?"},
+    {"role": "user", "content": "<video>What is in this video?"},
     {"role": "assistant", "content": "A cat."},
 ]
 
@@ -210,6 +210,34 @@ def test_gemma3_plugin():
     _check_plugin(**check_inputs)
 
 
+@pytest.mark.runs_on(["cpu", "mps"])
+@pytest.mark.skipif(not is_transformers_version_greater_than("5.6.0"), reason="Requires transformers>=5.6.0")
+def test_gemma4_plugin():
+    tokenizer_module = _load_tokenizer_module(model_name_or_path="google/gemma-4-31B-it")
+    processor = tokenizer_module["processor"]
+    gemma4_plugin = get_mm_plugin(name="gemma4", image_token="<|image|>", video_token="<|video|>")
+    check_inputs = {"plugin": gemma4_plugin, **tokenizer_module}
+    # validate
+    mm_inputs = gemma4_plugin._get_mm_inputs(IMAGES, NO_VIDEOS, NO_AUDIOS, processor)
+    num_image_soft_tokens = 256 # when we use default max_soft_tokens=280
+    image_token = getattr(processor, "image_token")
+    boi_token = getattr(processor, "boi_token")
+    eoi_token = getattr(processor, "eoi_token")
+
+    expected_mm_type_ids = [[int(token_id == getattr(processor, "image_token_id")) for token_id in token_ids] for token_ids in BATCH_IDS]
+    check_inputs["expected_mm_messages"] = [
+        {"role": "user", "content": f"{boi_token}{image_token * num_image_soft_tokens}{eoi_token}What is in this image?"},
+        {"role": "assistant", "content": "A cat."},
+    ]
+    for key in ("num_soft_tokens_per_image",):
+        mm_inputs.pop(key, None)
+
+    mm_inputs["mm_token_type_ids"] = expected_mm_type_ids
+    check_inputs["expected_mm_inputs"] = mm_inputs
+    check_inputs["expected_no_mm_inputs"] = {"mm_token_type_ids": expected_mm_type_ids}
+    _check_plugin(**check_inputs)
+
+
 @pytest.mark.runs_on(["cpu", "mps"])
 @pytest.mark.skipif(not is_transformers_version_greater_than("4.52.0"), reason="Requires transformers>=4.52.0")
 def test_internvl_plugin():

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/data/test_mm_plugin.py
: '>>>>> End Test Output'
git checkout acac63ef35d973b7eff18d8971b64f3dc7249d4e tests/data/test_mm_plugin.py
