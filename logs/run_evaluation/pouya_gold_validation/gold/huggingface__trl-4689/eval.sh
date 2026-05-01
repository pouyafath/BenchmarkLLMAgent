#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff c3e240ad398b2ed82d39e7a3808b365b78eb2881
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]'
git checkout c3e240ad398b2ed82d39e7a3808b365b78eb2881 tests/conftest.py tests/test_grpo_trainer.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/conftest.py b/tests/conftest.py
index 334d3598..6b92c7dd 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -13,11 +13,99 @@
 # limitations under the License.
 
 import gc
+from functools import wraps
 
 import pytest
 import torch
 
 
+# ============================================================================
+# Model Revision Override
+# ============================================================================
+# To test a tiny model PR before merging to main:
+# 1. Add the full model_id and PR revision to this dict
+# 2. Commit and push to trigger CI
+# 3. Once CI is green, merge the tiny model PR on HF Hub
+# 4. Remove the entry from this dict and commit
+#
+# Example:
+#   MODEL_REVISIONS = {
+#       "trl-internal-testing/tiny-Qwen2ForCausalLM-2.5": "refs/pr/3",
+#       "trl-internal-testing/tiny-LlavaForConditionalGeneration": "refs/pr/5",
+#   }
+# ============================================================================
+
+MODEL_REVISIONS = {
+    # Add model_id: revision mappings here to test PRs
+}
+
+
+@pytest.fixture(autouse=True)
+def apply_model_revisions(monkeypatch):
+    """Auto-inject revision parameter for models defined in MODEL_REVISIONS."""
+    if not MODEL_REVISIONS:
+        return
+
+    from transformers import PreTrainedModel, PreTrainedTokenizerBase, ProcessorMixin
+
+    def create_classmethod_wrapper(original_classmethod):
+        # Extract the underlying function from the classmethod
+        original_func = original_classmethod.__func__
+
+        @wraps(original_func)
+        def wrapper(cls, pretrained_model_name_or_path, *args, **kwargs):
+            # Direct lookup: only inject if model_id is in the override dict
+            if pretrained_model_name_or_path in MODEL_REVISIONS:
+                if "revision" not in kwargs:
+                    kwargs["revision"] = MODEL_REVISIONS[pretrained_model_name_or_path]
+
+            return original_func(cls, pretrained_model_name_or_path, *args, **kwargs)
+
+        # Re-wrap as classmethod
+        return classmethod(wrapper)
+
+    # Patch all transformers Auto* classes
+    for cls in [
+        PreTrainedModel,
+        PreTrainedTokenizerBase,
+        ProcessorMixin,
+    ]:
+        monkeypatch.setattr(cls, "from_pretrained", create_classmethod_wrapper(cls.from_pretrained))
+
+
+@pytest.fixture(autouse=True)
+def set_model_float32_dtype(monkeypatch):
+    """Auto-inject float32 dtype for tiny models defined in trl-internal-testing."""
+    from transformers import PreTrainedModel, PreTrainedTokenizerBase, ProcessorMixin
+
+    def create_classmethod_wrapper(original_classmethod):
+        # Extract the underlying function from the classmethod
+        original_func = original_classmethod.__func__
+
+        @wraps(original_func)
+        def wrapper(cls, pretrained_model_name_or_path, *args, **kwargs):
+            # Only inject if model_id is one of trl-internal-testing
+            if (
+                isinstance(pretrained_model_name_or_path, str)
+                and "trl-internal-testing" in pretrained_model_name_or_path
+            ):
+                if "dtype" not in kwargs:
+                    kwargs["dtype"] = "float32"
+
+            return original_func(cls, pretrained_model_name_or_path, *args, **kwargs)
+
+        # Re-wrap as classmethod
+        return classmethod(wrapper)
+
+    # Patch base classes - this affects all models, tokenizers, and processors
+    for cls in [
+        PreTrainedModel,
+        PreTrainedTokenizerBase,
+        ProcessorMixin,
+    ]:
+        monkeypatch.setattr(cls, "from_pretrained", create_classmethod_wrapper(cls.from_pretrained))
+
+
 @pytest.fixture(autouse=True)
 def cleanup_gpu():
     """
diff --git a/tests/test_grpo_trainer.py b/tests/test_grpo_trainer.py
index 13398481..d22d38cb 100644
--- a/tests/test_grpo_trainer.py
+++ b/tests/test_grpo_trainer.py
@@ -777,6 +777,133 @@ class TestGRPOTrainer(TrlTestCase):
             new_param = trainer.model.get_parameter(n)
             assert not torch.equal(param, new_param), f"Parameter {n} has not changed."
 
+    def test_get_off_policy_mask(self):
+        """
+        Test the logic of off-policy masking:
+        - Keep if Advantage >= 0
+        - Keep if KL <= threshold
+        - Drop if Advantage < 0 AND KL > threshold
+        """
+        mask = torch.ones((3, 4))  # B=3 sequences, T=4 tokens
+
+        advantages = torch.tensor([1.0, -1.0, -1.0]).unsqueeze(-1)
+        old_per_token_logps = torch.zeros((3, 4))
+        per_token_logps = torch.zeros((3, 4))
+
+        per_token_logps[0, :] = -2.0  # Pos adv + High KL (0−(−2)=2) -> Keep
+        per_token_logps[1, :] = -0.5  # Neg adv + Low KL (0.5) -> Keep
+        per_token_logps[2, :] = -2.0  # Neg adv + High KL (2.0) -> Drop
+
+        off_policy_threshold = 1.0
+
+        expected_mask = torch.tensor([[1.0], [1.0], [0.0]])
+
+        off_policy_mask = GRPOTrainer.get_off_policy_mask(
+            advantages, per_token_logps, old_per_token_logps, mask, off_policy_threshold
+        )
+
+        torch.testing.assert_close(off_policy_mask, expected_mask)
+
+    def test_get_off_policy_mask_padding(self):
+        """Test that padding is correctly ignored in KL calculation."""
+        mask = torch.tensor([[1.0, 1.0, 0.0, 0.0]])  # 2 valid tokens
+        advantages = torch.tensor([[-1.0]])  # Negative advantage
+
+        old_per_token_logps = torch.zeros((1, 4))
+        per_token_logps = torch.zeros((1, 4))
+
+        # Valid tokens have High KL (2.0)
+        per_token_logps[0, 0] = -2.0
+        per_token_logps[0, 1] = -2.0
+
+        # Padding tokens have abnormal values (should be ignored)
+        per_token_logps[0, 2] = -10_000.0
+        per_token_logps[0, 3] = 10_000.0
+
+        off_policy_threshold = 1.0
+
+        # Avg KL on valid tokens = (2+2)/2 = 2.0 > 1.0 -> Drop
+        expected_mask = torch.tensor([[0.0]])
+
+        off_policy_mask = GRPOTrainer.get_off_policy_mask(
+            advantages, per_token_logps, old_per_token_logps, mask, off_policy_threshold
+        )
+
+        torch.testing.assert_close(off_policy_mask, expected_mask)
+
+        # Now test with Low KL on valid tokens
+        per_token_logps[0, 0] = -0.5
+        per_token_logps[0, 1] = -0.5
+        # Avg KL = 0.5 <= 1.0 -> Keep
+        expected_mask_keep = torch.tensor([[1.0]])
+
+        off_policy_mask_keep = GRPOTrainer.get_off_policy_mask(
+            advantages, per_token_logps, old_per_token_logps, mask, off_policy_threshold
+        )
+
+        torch.testing.assert_close(off_policy_mask_keep, expected_mask_keep)
+
+    def test_training_with_off_policy_mask(self):
+        dataset = load_dataset("trl-internal-testing/zen", "standard_prompt_only", split="train")
+
+        training_args = GRPOConfig(
+            output_dir=self.tmp_dir,
+            off_policy_mask_threshold=0.5,
+            learning_rate=0.1,  # increase the learning rate to speed up the test
+            per_device_train_batch_size=3,  # reduce the batch size to reduce memory usage
+            num_generations=3,  # reduce the number of generations to reduce memory usage
+            max_completion_length=8,  # reduce the completion length to reduce memory usage
+            report_to="none",
+        )
+
+        trainer = GRPOTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            reward_funcs="trl-internal-testing/tiny-Qwen2ForSequenceClassification-2.5",
+            args=training_args,
+            train_dataset=dataset,
+        )
+
+        previous_trainable_params = {n: param.clone() for n, param in trainer.model.named_parameters()}
+
+        trainer.train()
+
+        # Check that the params have changed
+        for n, param in previous_trainable_params.items():
+            new_param = trainer.model.get_parameter(n)
+            assert not torch.equal(param, new_param), f"Parameter {n} has not changed."
+
+    @require_liger_kernel
+    @pytest.mark.xfail(reason="Off-Policy Masking isn't compatible with Liger yet.")
+    def test_training_with_off_policy_mask_with_liger(self):
+        dataset = load_dataset("trl-internal-testing/zen", "standard_prompt_only", split="train")
+
+        training_args = GRPOConfig(
+            output_dir=self.tmp_dir,
+            off_policy_mask_threshold=0.5,
+            use_liger_kernel=True,
+            learning_rate=0.1,  # increase the learning rate to speed up the test
+            per_device_train_batch_size=3,  # reduce the batch size to reduce memory usage
+            num_generations=3,  # reduce the number of generations to reduce memory usage
+            max_completion_length=8,  # reduce the completion length to reduce memory usage
+            report_to="none",
+        )
+
+        trainer = GRPOTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            reward_funcs="trl-internal-testing/tiny-Qwen2ForSequenceClassification-2.5",
+            args=training_args,
+            train_dataset=dataset,
+        )
+
+        previous_trainable_params = {n: param.clone() for n, param in trainer.model.named_parameters()}
+
+        trainer.train()
+
+        # Check that the params have changed
+        for n, param in previous_trainable_params.items():
+            new_param = trainer.model.get_parameter(n)
+            assert not torch.equal(param, new_param), f"Parameter {n} has not changed."
+
     def test_training_with_bias_correction_kl(self):
         dataset = load_dataset("trl-internal-testing/zen", "standard_prompt_only", split="train")
         training_args = GRPOConfig(

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/conftest.py tests/test_grpo_trainer.py
: '>>>>> End Test Output'
git checkout c3e240ad398b2ed82d39e7a3808b365b78eb2881 tests/conftest.py tests/test_grpo_trainer.py
