#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 5cffd59a8a814b9132c6d08e5aa88347a41c66e3
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]'
git checkout 5cffd59a8a814b9132c6d08e5aa88347a41c66e3 tests/test_grpo_trainer.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_grpo_trainer.py b/tests/test_grpo_trainer.py
index 1efd2885..e2c924af 100644
--- a/tests/test_grpo_trainer.py
+++ b/tests/test_grpo_trainer.py
@@ -16,7 +16,8 @@ import gc
 import os
 import warnings
 from collections.abc import Callable
-from unittest.mock import patch
+from types import SimpleNamespace
+from unittest.mock import MagicMock, patch
 
 import numpy as np
 import pytest
@@ -37,6 +38,7 @@ from transformers.testing_utils import backend_empty_cache, torch_device
 from transformers.utils import is_peft_available
 
 from trl import GRPOConfig, GRPOTrainer
+from trl.import_utils import is_liger_kernel_available
 from trl.trainer.utils import get_kbit_device_map
 
 from .testing_utils import (
@@ -157,6 +159,59 @@ class TestGetHighEntropyMask(TrlTestCase):
         torch.testing.assert_close(entropy_mask, expected_mask)
 
 
+class TestGRPORolloutDispatch:
+    def _make_trainer(self):
+        trainer = object.__new__(GRPOTrainer)
+        trainer.accelerator = SimpleNamespace(device=torch.device("cpu"), is_main_process=True)
+        trainer.args = SimpleNamespace(report_to=[])
+        trainer.model = SimpleNamespace(training=True)
+        trainer.state = SimpleNamespace(global_step=2)
+        trainer._last_loaded_step = 1
+        trainer.use_vllm = False
+        trainer.use_transformers_paged = False
+        trainer.vllm_generation = SimpleNamespace(sync_weights=MagicMock())
+        return trainer
+
+    def test_generate_single_turn_prefers_rollout_func(self):
+        trainer = self._make_trainer()
+        trainer.rollout_func = MagicMock(
+            return_value={
+                "prompt_ids": [[1]],
+                "completion_ids": [[2]],
+                "logprobs": [[-0.1]],
+                "env_mask": [[1]],
+            }
+        )
+
+        prompt_ids, completion_ids, logprobs, extra_fields = trainer._generate_single_turn(["prompt"])
+
+        assert prompt_ids == [[1]]
+        assert completion_ids == [[2]]
+        assert logprobs == [[-0.1]]
+        assert extra_fields == {"env_mask": [[1]]}
+        trainer.rollout_func.assert_called_once_with(["prompt"], trainer)
+
+    def test_generate_single_turn_rollout_func_syncs_vllm_weights_when_needed(self):
+        trainer = self._make_trainer()
+        trainer.use_vllm = True
+        trainer.rollout_func = MagicMock(
+            return_value={"prompt_ids": [[1]], "completion_ids": [[2]], "logprobs": [[0.0]]}
+        )
+
+        trainer._generate_single_turn(["prompt"])
+
+        trainer.vllm_generation.sync_weights.assert_called_once()
+        assert trainer._last_loaded_step == trainer.state.global_step
+        trainer.rollout_func.assert_called_once_with(["prompt"], trainer)
+
+    def test_generate_single_turn_rollout_func_raises_when_required_keys_are_missing(self):
+        trainer = self._make_trainer()
+        trainer.rollout_func = MagicMock(return_value={"prompt_ids": [[1]], "completion_ids": [[2]]})
+
+        with pytest.raises(ValueError, match="rollout_func must return keys"):
+            trainer._generate_single_turn(["prompt"])
+
+
 class TestGRPOTrainer(TrlTestCase):
     def test_init_minimal(self):
         # Test that GRPOTrainer can be instantiated with only model, reward_model and train_dataset
@@ -1980,7 +2035,14 @@ class TestGRPOTrainer(TrlTestCase):
     @pytest.mark.parametrize(
         "model_id",
         [
-            "trl-internal-testing/tiny-Qwen2_5_VLForConditionalGeneration",
+            pytest.param(
+                "trl-internal-testing/tiny-Qwen2_5_VLForConditionalGeneration",
+                marks=pytest.mark.xfail(
+                    (Version("5.2.0") < Version(transformers.__version__))
+                    and not is_liger_kernel_available(min_version="0.8.0"),
+                    reason="Upstream issue tracked at https://github.com/linkedin/Liger-Kernel/issues/1117",
+                ),
+            ),
         ],
     )
     @require_vision
@@ -2621,6 +2683,47 @@ class TestGRPOTrainerSlow(TrlTestCase):
 
         release_memory(model, trainer)
 
+    @require_liger_kernel
+    def test_liger_grpo_kernel_importance_sampling(self):
+        model_name = "trl-internal-testing/tiny-LlamaForCausalLM-3.2"
+
+        training_args = GRPOConfig(
+            output_dir=self.tmp_dir,
+            per_device_train_batch_size=3,
+            num_generations=3,
+            use_liger_kernel=True,
+            max_completion_length=self.max_length,
+            importance_sampling_level="sequence",
+            report_to="none",
+            logging_strategy="no",
+        )
+
+        model = AutoModelForCausalLM.from_pretrained(model_name, dtype="float32")
+        tokenizer = AutoTokenizer.from_pretrained(model_name)
+        tokenizer.pad_token = tokenizer.eos_token if tokenizer.pad_token is None else tokenizer.pad_token
+
+        trainer = GRPOTrainer(
+            model=model,
+            reward_funcs="trl-internal-testing/tiny-Qwen2ForSequenceClassification-2.5",
+            args=training_args,
+            train_dataset=self.train_dataset,
+            eval_dataset=self.eval_dataset,
+            processing_class=tokenizer,
+        )
+        from liger_kernel.chunked_loss import LigerFusedLinearGRPOLoss
+
+        assert isinstance(trainer.liger_grpo_loss, LigerFusedLinearGRPOLoss)
+
+        previous_trainable_params = {n: param.clone() for n, param in model.named_parameters()}
+
+        trainer.train()
+
+        for n, param in previous_trainable_params.items():
+            new_param = model.get_parameter(n)
+            assert not torch.equal(param, new_param), f"Parameter {n} has not changed."
+
+        release_memory(model, trainer)
+
     @pytest.mark.parametrize(
         "model_name",
         [

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_grpo_trainer.py
: '>>>>> End Test Output'
git checkout 5cffd59a8a814b9132c6d08e5aa88347a41c66e3 tests/test_grpo_trainer.py
