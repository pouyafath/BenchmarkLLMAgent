#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 05cfc90c5d0e44427fb75e2fb0f68bd7f8acb7ba
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]'
git checkout 05cfc90c5d0e44427fb75e2fb0f68bd7f8acb7ba tests/test_grpo_trainer.py tests/test_rloo_trainer.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_grpo_trainer.py b/tests/test_grpo_trainer.py
index bacb0a02..10bb0d81 100644
--- a/tests/test_grpo_trainer.py
+++ b/tests/test_grpo_trainer.py
@@ -803,6 +803,45 @@ class TestGRPOTrainer(TrlTestCase):
             new_param = trainer.model.get_parameter(n)
             assert not torch.equal(param, new_param), f"Parameter {n} has not changed."
 
+    @pytest.mark.parametrize("multi_objective_aggregation", ["sum_then_normalize", "normalize_then_sum"])
+    def test_reward_metric_reflects_reward_weights(self, multi_objective_aggregation):
+        """Test that the logged 'reward' metric uses reward_weights, not an unweighted sum."""
+        dataset = load_dataset("trl-internal-testing/zen", "standard_prompt_only", split="train")
+
+        def constant_reward_1(completions, **kwargs):
+            return [1.0] * len(completions)
+
+        def constant_reward_0(completions, **kwargs):
+            return [0.0] * len(completions)
+
+        training_args = GRPOConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,  # use higher lr because gradients are tiny and default lr can stall updates
+            per_device_train_batch_size=3,  # reduce the batch size to reduce memory usage
+            num_generations=3,  # reduce the number of generations to reduce memory usage
+            max_completion_length=8,  # reduce the completion length to reduce memory usage
+            report_to="none",
+            reward_weights=[0.7, 0.3],
+            multi_objective_aggregation=multi_objective_aggregation,
+        )
+        trainer = GRPOTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            reward_funcs=[constant_reward_1, constant_reward_0],
+            args=training_args,
+            train_dataset=dataset,
+        )
+
+        trainer.train()
+
+        log = trainer.state.log_history[-1]
+        # With reward_weights=[0.7, 0.3] and rewards [1.0, 0.0]:
+        # weighted reward = 0.7*1.0 + 0.3*0.0 = 0.7
+        # unweighted reward = 1.0 + 0.0 = 1.0
+        assert abs(log["reward"] - 0.7) < 1e-5, (
+            f"Expected logged reward to be ~0.7 (weighted), got {log['reward']}. "
+            "The reward metric should reflect reward_weights."
+        )
+
     def test_training_multiple_mixed_reward_funcs(self):
         # Test if the trainer can handle a mix of reward functions and reward models
         dataset = load_dataset("trl-internal-testing/zen", "standard_prompt_only", split="train")
diff --git a/tests/test_rloo_trainer.py b/tests/test_rloo_trainer.py
index 278e0ff8..8d903120 100644
--- a/tests/test_rloo_trainer.py
+++ b/tests/test_rloo_trainer.py
@@ -541,6 +541,43 @@ class TestRLOOTrainer(TrlTestCase):
             new_param = trainer.model.get_parameter(n)
             assert not torch.equal(param, new_param), f"Parameter {n} has not changed."
 
+    def test_reward_metric_reflects_reward_weights(self):
+        """Test that the logged 'reward' metric uses reward_weights, not an unweighted sum."""
+        dataset = load_dataset("trl-internal-testing/zen", "standard_prompt_only", split="train")
+
+        def constant_reward_1(completions, **kwargs):
+            return [1.0] * len(completions)
+
+        def constant_reward_0(completions, **kwargs):
+            return [0.0] * len(completions)
+
+        training_args = RLOOConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,  # use higher lr because gradients are tiny and default lr can stall updates
+            per_device_train_batch_size=3,  # reduce the batch size to reduce memory usage
+            num_generations=3,  # reduce the number of generations to reduce memory usage
+            max_completion_length=8,  # reduce the completion length to reduce memory usage
+            report_to="none",
+            reward_weights=[0.7, 0.3],
+        )
+        trainer = RLOOTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            reward_funcs=[constant_reward_1, constant_reward_0],
+            args=training_args,
+            train_dataset=dataset,
+        )
+
+        trainer.train()
+
+        log = trainer.state.log_history[-1]
+        # With reward_weights=[0.7, 0.3] and rewards [1.0, 0.0]:
+        # weighted reward = 0.7*1.0 + 0.3*0.0 = 0.7
+        # unweighted reward = 1.0 + 0.0 = 1.0
+        assert abs(log["reward"] - 0.7) < 1e-5, (
+            f"Expected logged reward to be ~0.7 (weighted), got {log['reward']}. "
+            "The reward metric should reflect reward_weights."
+        )
+
     def test_training_multiple_mixed_reward_funcs(self):
         # Test if the trainer can handle a mix of reward functions and reward models
         dataset = load_dataset("trl-internal-testing/zen", "standard_prompt_only", split="train")

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_grpo_trainer.py tests/test_rloo_trainer.py
: '>>>>> End Test Output'
git checkout 05cfc90c5d0e44427fb75e2fb0f68bd7f8acb7ba tests/test_grpo_trainer.py tests/test_rloo_trainer.py
