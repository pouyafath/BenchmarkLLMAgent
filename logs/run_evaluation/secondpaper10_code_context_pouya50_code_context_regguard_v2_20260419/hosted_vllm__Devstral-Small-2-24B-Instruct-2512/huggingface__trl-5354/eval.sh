#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff ffa14ee81f3dc3a50a41de9c856d90819fed9f28
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]'
git checkout ffa14ee81f3dc3a50a41de9c856d90819fed9f28 tests/test_sft_trainer.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_sft_trainer.py b/tests/test_sft_trainer.py
index 3d2009a3..f1e96d09 100644
--- a/tests/test_sft_trainer.py
+++ b/tests/test_sft_trainer.py
@@ -1829,7 +1829,12 @@ class TestSFTTrainer(TrlTestCase):
     )
     @pytest.mark.parametrize(
         "dataset_config",
-        ["conversational_language_modeling", "conversational_prompt_completion", "standard_prompt_completion"],
+        [
+            "conversational_language_modeling",
+            "conversational_prompt_completion",
+            "standard_language_modeling",  # Regression test for #5334
+            "standard_prompt_completion",
+        ],
     )
     @require_vision
     def test_train_vlm_text_only_data(self, model_id, dataset_config):
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_sft_trainer.py
: '>>>>> End Test Output'
git checkout ffa14ee81f3dc3a50a41de9c856d90819fed9f28 tests/test_sft_trainer.py
