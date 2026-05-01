#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff e923a9ac37f845fc2231b2fa50c6f19367d8a9a4
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]'
git checkout e923a9ac37f845fc2231b2fa50c6f19367d8a9a4 tests/test_sft_trainer.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/experimental/test_sdft_trainer.py b/tests/experimental/test_sdft_trainer.py
new file mode 100644
index 00000000..9ca9b6c5
--- /dev/null
+++ b/tests/experimental/test_sdft_trainer.py
@@ -0,0 +1,342 @@
+# Copyright 2020-2026 The HuggingFace Team. All rights reserved.
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+import pytest
+import torch
+from datasets import Dataset
+from transformers import AutoModelForCausalLM, TrainerCallback, TrainerControl, TrainerState, TrainingArguments
+from transformers.utils import is_peft_available
+
+from trl.data_utils import maybe_apply_chat_template
+from trl.experimental.sdft import SDFTConfig, SDFTTrainer
+
+from ..testing_utils import TrlTestCase, require_peft
+
+
+if is_peft_available():
+    from peft import LoraConfig, get_peft_model, get_peft_model_state_dict
+
+    from trl.experimental.self_distillation.peft_adapter_ema_callback import PEFTAdapterEMACallback
+
+
+class SelfDistillationCaptureCallback(TrainerCallback):
+    def __init__(self):
+        self.captured_generation_prompt_text = None
+        self.captured_old_per_token_logps = None
+        self.generation_batch_build_count = 0
+
+    def on_generation_prompts_selected(self, generation_prompt_text=None, **kwargs):
+        if self.captured_generation_prompt_text is None and generation_prompt_text is not None:
+            self.captured_generation_prompt_text = generation_prompt_text[0]
+
+    def on_self_distillation_batch_prepared(self, old_per_token_logps=None, **kwargs):
+        if self.captured_old_per_token_logps is None and old_per_token_logps is not None:
+            self.captured_old_per_token_logps = old_per_token_logps.detach().cpu()
+
+    def on_generation_batch_built(self, **kwargs):
+        self.generation_batch_build_count += 1
+
+
+class TestSDFTTrainer(TrlTestCase):
+    def test_training_rejects_none_privileged_context(self):
+        dataset = Dataset.from_dict(
+            {
+                "prompt": ["Solve 2+2."],
+                "privileged_context": [None],
+            }
+        )
+
+        training_args = SDFTConfig(
+            output_dir=self.tmp_dir,
+            per_device_train_batch_size=1,
+            max_completion_length=8,
+            max_steps=1,
+            num_generations=1,
+        )
+
+        trainer = SDFTTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            args=training_args,
+            train_dataset=dataset,
+        )
+
+        with pytest.raises(ValueError, match="`privileged_context` must not be None"):
+            trainer.train()
+
+    def test_training_with_generate_from_teacher(self):
+        dataset = Dataset.from_dict(
+            {
+                "prompt": ["Solve 2+2.", "Solve 3+3."],
+                "privileged_context": [
+                    "Teacher hint: answer with 4 and explain briefly.",
+                    "Teacher hint: answer with 6 and explain briefly.",
+                ],
+            }
+        )
+
+        training_args = SDFTConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            max_completion_length=8,
+            max_steps=1,
+            num_generations=1,
+            generate_from_teacher=True,
+        )
+
+        capture_callback = SelfDistillationCaptureCallback()
+        trainer = SDFTTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            args=training_args,
+            train_dataset=dataset,
+            callbacks=[capture_callback],
+        )
+
+        trainer.train()
+
+        assert capture_callback.captured_generation_prompt_text is not None
+        assert "Solve 2+2." in capture_callback.captured_generation_prompt_text
+        assert "Teacher hint" in capture_callback.captured_generation_prompt_text
+
+    def test_training_with_chat_template_kwargs(self):
+        dataset = Dataset.from_dict(
+            {
+                "prompt": [
+                    [{"role": "user", "content": "Solve 2+2."}],
+                    [{"role": "user", "content": "Solve 3+3."}],
+                ],
+                "privileged_context": [
+                    "Teacher hint: answer with 4.",
+                    "Teacher hint: answer with 6.",
+                ],
+            }
+        )
+
+        training_args = SDFTConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            max_completion_length=8,
+            max_steps=1,
+            num_generations=1,
+            chat_template_kwargs={"enable_thinking": False},
+        )
+
+        capture_callback = SelfDistillationCaptureCallback()
+        trainer = SDFTTrainer(
+            model="trl-internal-testing/tiny-Qwen3ForCausalLM",
+            args=training_args,
+            train_dataset=dataset,
+            callbacks=[capture_callback],
+        )
+
+        expected_prompt = maybe_apply_chat_template(
+            {"prompt": dataset[0]["prompt"]},
+            trainer.processing_class,
+            **training_args.chat_template_kwargs,
+        )["prompt"]
+
+        trainer.train()
+
+        assert capture_callback.captured_generation_prompt_text == expected_prompt
+
+    @require_peft
+    def test_training_with_peft_model(self):
+        dataset = Dataset.from_dict(
+            {
+                "prompt": ["Solve 2+2.", "Name the capital of France."],
+                "privileged_context": [
+                    "Example answer: 4.",
+                    "Example answer: Paris.",
+                ],
+            }
+        )
+
+        training_args = SDFTConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            max_completion_length=8,
+            max_steps=1,
+            num_generations=1,
+        )
+
+        trainer = SDFTTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            args=training_args,
+            train_dataset=dataset,
+            peft_config=LoraConfig(
+                task_type="CAUSAL_LM",
+                target_modules=["q_proj", "v_proj"],
+            ),
+        )
+
+        trainer.train()
+
+        assert trainer.state.log_history[-1]["train_loss"] is not None
+
+    @require_peft
+    def test_training_with_peft_model_and_sync_ref_model(self):
+        dataset = Dataset.from_dict(
+            {
+                "prompt": ["Solve 2+2.", "Name the capital of France."],
+                "privileged_context": [
+                    "Example answer: 4.",
+                    "Example answer: Paris.",
+                ],
+            }
+        )
+
+        training_args = SDFTConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            max_completion_length=8,
+            max_steps=2,
+            num_generations=1,
+            sync_ref_model=True,
+            ref_model_mixup_alpha=0.05,
+            ref_model_sync_steps=1,
+        )
+
+        trainer = SDFTTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            args=training_args,
+            train_dataset=dataset,
+            peft_config=LoraConfig(
+                task_type="CAUSAL_LM",
+                target_modules=["q_proj", "v_proj"],
+            ),
+        )
+
+        trainer.train()
+
+        assert trainer.state.log_history[-1]["train_loss"] is not None
+
+    @require_peft
+    def test_peft_adapter_ema_callback(self):
+        model = AutoModelForCausalLM.from_pretrained(
+            "trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            device_map="cpu",
+        )
+        lora_config = LoraConfig(
+            task_type="CAUSAL_LM",
+            target_modules=["q_proj", "v_proj"],
+            r=8,
+        )
+        model = get_peft_model(model, lora_config, adapter_name="default")
+
+        update_rate = 0.5
+        callback = PEFTAdapterEMACallback(
+            model=model,
+            teacher_adapter_name="teacher",
+            update_rate=update_rate,
+            sync_steps=1,
+        )
+
+        # Initialize and verify teacher adapter was created with zero weights
+        callback._initialize_teacher_adapter()
+        assert "teacher" in model.peft_config
+        assert callback.shadow_weights is not None
+
+        teacher_state = get_peft_model_state_dict(model, adapter_name="teacher")
+        for key, param in teacher_state.items():
+            assert torch.all(param == 0), f"Teacher param {key} should be zero-initialized"
+
+        # Verify shadow weights keys match student state dict keys
+        student_state = {k: v.clone() for k, v in get_peft_model_state_dict(model, adapter_name="default").items()}
+        assert set(callback.shadow_weights.keys()) == set(student_state.keys())
+
+        # Simulate a training step and verify EMA update
+        args = TrainingArguments(output_dir=self.tmp_dir)
+        state = TrainerState(global_step=1)
+        control = TrainerControl()
+        callback.on_step_end(args, state, control)
+
+        # shadow = (1 - rate) * 0 + rate * student = rate * student
+        for key in callback.shadow_weights:
+            expected = update_rate * student_state[key]
+            torch.testing.assert_close(callback.shadow_weights[key], expected)
+
+        # Verify teacher adapter received the shadow weights
+        teacher_state = get_peft_model_state_dict(model, adapter_name="teacher")
+        for key in teacher_state:
+            torch.testing.assert_close(teacher_state[key].float(), callback.shadow_weights[key])
+
+    def test_training_populates_old_log_probs_for_distillation_clipping_when_misaligned(self):
+        dataset = Dataset.from_dict(
+            {
+                "prompt": ["Solve 2+2.", "Solve 3+3."],
+                "privileged_context": [
+                    "Example answer: 4.",
+                    "Example answer: 6.",
+                ],
+            }
+        )
+
+        training_args = SDFTConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            gradient_accumulation_steps=3,
+            steps_per_generation=2,
+            max_completion_length=8,
+            max_steps=1,
+            num_generations=1,
+        )
+
+        capture_callback = SelfDistillationCaptureCallback()
+        trainer = SDFTTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            args=training_args,
+            train_dataset=dataset,
+            callbacks=[capture_callback],
+        )
+
+        trainer.train()
+
+        assert capture_callback.captured_old_per_token_logps is not None
+
+    def test_training_reuses_buffered_generation_batches(self):
+        dataset = Dataset.from_dict(
+            {
+                "prompt": ["Solve 2+2.", "Solve 3+3."],
+                "privileged_context": [
+                    "Example answer: 4.",
+                    "Example answer: 6.",
+                ],
+            }
+        )
+
+        training_args = SDFTConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            steps_per_generation=2,
+            max_completion_length=8,
+            max_steps=2,
+            num_generations=1,
+        )
+
+        capture_callback = SelfDistillationCaptureCallback()
+        trainer = SDFTTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            args=training_args,
+            train_dataset=dataset,
+            callbacks=[capture_callback],
+        )
+
+        trainer.train()
+
+        assert capture_callback.generation_batch_build_count == 1
diff --git a/tests/experimental/test_sdpo_trainer.py b/tests/experimental/test_sdpo_trainer.py
new file mode 100644
index 00000000..7858442b
--- /dev/null
+++ b/tests/experimental/test_sdpo_trainer.py
@@ -0,0 +1,417 @@
+# Copyright 2020-2026 The HuggingFace Team. All rights reserved.
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+import logging
+
+import torch
+from datasets import Dataset, load_dataset
+from transformers import TrainerCallback
+
+from trl.experimental.sdpo import SDPOConfig, SDPOTrainer
+
+from ..testing_utils import TrlTestCase
+
+
+class SelfDistillationCaptureCallback(TrainerCallback):
+    def __init__(self):
+        self.captured_teacher_input_text = None
+        self.captured_teacher_input_texts = []
+        self.captured_self_distillation_mask = None
+        self.captured_teacher_attention_mask = None
+        self.captured_completion_mask = None
+        self.captured_old_per_token_logps = None
+
+    def on_teacher_context_built(
+        self,
+        processing_class=None,
+        teacher_input_ids=None,
+        teacher_attention_mask=None,
+        completion_mask=None,
+        self_distillation_mask=None,
+        **kwargs,
+    ):
+        if self.captured_teacher_input_text is None and teacher_input_ids is not None:
+            self.captured_teacher_input_text = processing_class.decode(teacher_input_ids[0], skip_special_tokens=True)
+        if teacher_input_ids is not None:
+            self.captured_teacher_input_texts.extend(
+                processing_class.decode(ids, skip_special_tokens=True) for ids in teacher_input_ids
+            )
+        if self.captured_teacher_attention_mask is None and teacher_attention_mask is not None:
+            self.captured_teacher_attention_mask = teacher_attention_mask.detach().cpu()
+        if self.captured_completion_mask is None and completion_mask is not None:
+            self.captured_completion_mask = completion_mask.detach().cpu()
+        if self.captured_self_distillation_mask is None and self_distillation_mask is not None:
+            self.captured_self_distillation_mask = self_distillation_mask.detach().cpu()
+
+    def on_self_distillation_batch_prepared(self, old_per_token_logps=None, **kwargs):
+        if self.captured_old_per_token_logps is None and old_per_token_logps is not None:
+            self.captured_old_per_token_logps = old_per_token_logps.detach().cpu()
+
+
+class TestSDPOTrainer(TrlTestCase):
+    def test_training_with_positional_config_argument(self):
+        dataset = Dataset.from_dict(
+            {
+                "prompt": ["Solve 2+2."],
+                "privileged_context": ["Your earlier answer used the wrong format."],
+            }
+        )
+
+        training_args = SDPOConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            generation_batch_size=2,
+            num_generations=2,
+            max_completion_length=8,
+            include_environment_feedback=True,
+            max_steps=1,
+        )
+
+        trainer = SDPOTrainer(
+            "trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            lambda **kwargs: [0.0] * len(kwargs["prompts"]),
+            training_args,
+            dataset,
+        )
+
+        trainer.train()
+
+        assert trainer.args.output_dir == self.tmp_dir
+        assert trainer.args.include_environment_feedback is True
+        assert trainer.state.log_history[-1]["train_loss"] is not None
+
+    def test_training(self):
+        dataset = load_dataset("trl-internal-testing/zen", "standard_prompt_only", split="train")
+
+        training_args = SDPOConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=3,
+            num_generations=3,
+            max_completion_length=8,
+            distillation_topk=5,
+            full_logit_distillation=True,
+            distillation_is_clip=None,
+        )
+        trainer = SDPOTrainer(
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
+        assert trainer.state.log_history[-1]["train_loss"] is not None
+
+        for n, param in previous_trainable_params.items():
+            new_param = trainer.model.get_parameter(n)
+            if param.sum() != 0:
+                assert not torch.allclose(param, new_param, rtol=1e-12, atol=1e-12), f"Parameter {n} has not changed."
+
+    def test_training_without_successful_rollouts(self):
+        dataset = load_dataset("trl-internal-testing/zen", "standard_prompt_only", split="train")
+
+        training_args = SDPOConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=3,
+            num_generations=3,
+            max_completion_length=8,
+            distillation_is_clip=None,
+        )
+
+        def zero_reward(**kwargs):
+            prompts = kwargs["prompts"]
+            return [0.0] * len(prompts)
+
+        trainer = SDPOTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            reward_funcs=zero_reward,
+            args=training_args,
+            train_dataset=dataset,
+        )
+
+        trainer.train()
+
+        assert trainer.state.log_history[-1]["train_loss"] is not None
+
+    def test_training_populates_old_log_probs_for_distillation_clipping_when_misaligned(self):
+        dataset = Dataset.from_dict({"prompt": ["Solve 2+2.", "Solve 3+3."]})
+
+        training_args = SDPOConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            gradient_accumulation_steps=3,
+            steps_per_generation=2,
+            num_generations=2,
+            max_completion_length=8,
+            max_steps=1,
+        )
+
+        capture_callback = SelfDistillationCaptureCallback()
+        trainer = SDPOTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            reward_funcs=lambda **kwargs: [0.0] * len(kwargs["prompts"]),
+            args=training_args,
+            train_dataset=dataset,
+            callbacks=[capture_callback],
+        )
+
+        trainer.train()
+
+        assert capture_callback.captured_old_per_token_logps is not None
+
+    def test_evaluation_uses_num_generations_eval_for_teacher_grouping(self):
+        eval_dataset = Dataset.from_dict({"prompt": ["Alpha prompt", "Beta prompt", "Gamma prompt", "Delta prompt"]})
+
+        training_args = SDPOConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            per_device_eval_batch_size=4,
+            generation_batch_size=3,
+            num_generations=3,
+            num_generations_eval=2,
+            max_completion_length=8,
+            success_reward_threshold=0.5,
+            dont_reprompt_on_self_success=False,
+            distillation_is_clip=None,
+            max_steps=1,
+        )
+
+        def eval_rewards(**kwargs):
+            prompts = kwargs["prompts"]
+            if len(prompts) == 4 and prompts.count("Alpha prompt") == 2 and prompts.count("Beta prompt") == 2:
+                return [1.0, 0.0, 0.0, 0.0]
+            return [0.0] * len(prompts)
+
+        capture_callback = SelfDistillationCaptureCallback()
+        trainer = SDPOTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            reward_funcs=eval_rewards,
+            args=training_args,
+            train_dataset=eval_dataset.select(range(1)),
+            eval_dataset=eval_dataset,
+            callbacks=[capture_callback],
+        )
+
+        trainer.evaluate()
+
+        assert capture_callback.captured_teacher_input_texts
+        alpha_teachers = [text for text in capture_callback.captured_teacher_input_texts if "Alpha prompt" in text]
+        beta_teachers = [text for text in capture_callback.captured_teacher_input_texts if "Beta prompt" in text]
+        assert alpha_teachers
+        assert beta_teachers
+        assert any("Correct solution:" in text for text in alpha_teachers)
+        assert all("Correct solution:" not in text for text in beta_teachers)
+
+    def test_teacher_reprompt_preserves_curly_braces_in_solution_and_feedback(self):
+        dataset = Dataset.from_dict(
+            {
+                "prompt": ["Solve f(x) = {x^2}."],
+                "privileged_context": ['Feedback: use {"x": 2} as a check.'],
+            }
+        )
+
+        training_args = SDPOConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            generation_batch_size=2,
+            num_generations=2,
+            max_completion_length=8,
+            include_environment_feedback=True,
+            success_reward_threshold=0.5,
+            dont_reprompt_on_self_success=False,
+            max_steps=1,
+        )
+
+        def reward_with_one_success(**kwargs):
+            prompts = kwargs["prompts"]
+            return [1.0, 0.0][: len(prompts)]
+
+        capture_callback = SelfDistillationCaptureCallback()
+        trainer = SDPOTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            reward_funcs=reward_with_one_success,
+            args=training_args,
+            train_dataset=dataset,
+            callbacks=[capture_callback],
+        )
+
+        trainer.train()
+
+        assert capture_callback.captured_teacher_input_text is not None
+        assert "{{" not in capture_callback.captured_teacher_input_text
+        assert "}}" not in capture_callback.captured_teacher_input_text
+
+    def test_training_with_conversational_prompts_preserves_context(self):
+        dataset = Dataset.from_dict(
+            {
+                "prompt": [
+                    [
+                        {"role": "system", "content": "You are a careful assistant."},
+                        {"role": "user", "content": "Solve 2+2."},
+                    ]
+                ]
+            }
+        )
+
+        training_args = SDPOConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            generation_batch_size=2,
+            num_generations=2,
+            max_completion_length=8,
+            distillation_is_clip=None,
+            success_reward_threshold=0.5,
+            max_steps=1,
+        )
+
+        def first_only_reward(**kwargs):
+            """Only the first sample in each group succeeds — exercises dont_reprompt_on_self_success default."""
+            return [1.0, 0.0][: len(kwargs["prompts"])]
+
+        capture_callback = SelfDistillationCaptureCallback()
+        trainer = SDPOTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            reward_funcs=first_only_reward,
+            args=training_args,
+            train_dataset=dataset,
+            callbacks=[capture_callback],
+        )
+
+        trainer.train()
+
+        # With dont_reprompt_on_self_success=True (default), sample 0 skips itself,
+        # but sample 1 finds sample 0's success and gets a teacher reprompt.
+        assert capture_callback.captured_teacher_input_text is not None
+        assert "careful assistant" in capture_callback.captured_teacher_input_text
+        assert "Solve 2+2" in capture_callback.captured_teacher_input_text
+        assert capture_callback.captured_self_distillation_mask is not None
+
+    def test_training_with_feedback_only_reprompts_teacher(self):
+        dataset = Dataset.from_dict(
+            {
+                "prompt": [
+                    [
+                        {"role": "system", "content": "You are a careful assistant."},
+                        {"role": "user", "content": "Try the puzzle again."},
+                    ]
+                ],
+                "privileged_context": ["Your earlier answer violated the format requirements."],
+            }
+        )
+
+        training_args = SDPOConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            generation_batch_size=2,
+            num_generations=2,
+            max_completion_length=8,
+            distillation_is_clip=None,
+            include_environment_feedback=True,
+            max_steps=1,
+        )
+
+        def zero_reward(**kwargs):
+            prompts = kwargs["prompts"]
+            return [0.0] * len(prompts)
+
+        capture_callback = SelfDistillationCaptureCallback()
+        trainer = SDPOTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            reward_funcs=zero_reward,
+            args=training_args,
+            train_dataset=dataset,
+            callbacks=[capture_callback],
+        )
+
+        trainer.train()
+
+        assert capture_callback.captured_teacher_input_text is not None
+        assert "format requirements" in capture_callback.captured_teacher_input_text
+        assert capture_callback.captured_self_distillation_mask is not None
+        assert capture_callback.captured_self_distillation_mask[0].item() == 1.0
+
+    def test_training_warns_when_sdpo_rewards_are_flat(self, caplog):
+        dataset = load_dataset("trl-internal-testing/zen", "standard_prompt_only", split="train")
+
+        training_args = SDPOConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=3,
+            num_generations=3,
+            max_completion_length=8,
+            diagnostics_warning_interval=2,
+            max_steps=2,
+        )
+
+        def zero_reward(**kwargs):
+            return [0.0] * len(kwargs["prompts"])
+
+        trainer = SDPOTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            reward_funcs=zero_reward,
+            args=training_args,
+            train_dataset=dataset,
+        )
+
+        with caplog.at_level(logging.WARNING):
+            trainer.train()
+
+        assert "Observed flat SDPO rewards across all sampled generations" in caplog.text
+        assert "SDPO self-distillation is inactive because no reprompted samples were constructed" in caplog.text
+
+    def test_training_preserves_teacher_completion_attention_mask(self):
+        dataset = Dataset.from_dict({"prompt": ["Solve 2+2."]})
+
+        training_args = SDPOConfig(
+            output_dir=self.tmp_dir,
+            learning_rate=0.1,
+            per_device_train_batch_size=1,
+            generation_batch_size=2,
+            num_generations=2,
+            max_completion_length=8,
+            success_reward_threshold=0.5,
+            max_steps=1,
+        )
+
+        def first_only_reward(**kwargs):
+            return [1.0, 0.0][: len(kwargs["prompts"])]
+
+        capture_callback = SelfDistillationCaptureCallback()
+        trainer = SDPOTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",
+            reward_funcs=first_only_reward,
+            args=training_args,
+            train_dataset=dataset,
+            callbacks=[capture_callback],
+        )
+
+        trainer.train()
+
+        assert capture_callback.captured_teacher_attention_mask is not None
+        assert capture_callback.captured_completion_mask is not None
+
+        completion_length = capture_callback.captured_completion_mask.shape[1]
+        teacher_completion_attention = capture_callback.captured_teacher_attention_mask[0, -completion_length:]
+        assert torch.equal(teacher_completion_attention, capture_callback.captured_completion_mask[0])
diff --git a/tests/test_sft_trainer.py b/tests/test_sft_trainer.py
index 442b9c24..3d2009a3 100644
--- a/tests/test_sft_trainer.py
+++ b/tests/test_sft_trainer.py
@@ -243,6 +243,80 @@ class TestDataCollatorForLanguageModeling(TrlTestCase):
         torch.testing.assert_close(result["attention_mask"], torch.tensor([[1, 1, 1], [1, 1, 0]]))
         torch.testing.assert_close(result["labels"], torch.tensor([[-100, 2, 3], [-100, 5, -100]]))
 
+    def test_max_length_keep_start(self):
+        """Test that sequences longer than max_length are truncated from the start."""
+        collator = DataCollatorForLanguageModeling(pad_token_id=0, max_length=3)
+        examples = [{"input_ids": [1, 2, 3, 4, 5]}, {"input_ids": [6, 7, 8]}]
+
+        result = collator(examples)
+
+        assert set(result.keys()) == {"input_ids", "attention_mask", "labels"}
+        torch.testing.assert_close(result["input_ids"], torch.tensor([[1, 2, 3], [6, 7, 8]]))
+        torch.testing.assert_close(result["attention_mask"], torch.tensor([[1, 1, 1], [1, 1, 1]]))
+        torch.testing.assert_close(result["labels"], torch.tensor([[1, 2, 3], [6, 7, 8]]))
+
+    def test_max_length_keep_end(self):
+        """Test that sequences longer than max_length are truncated from the end (keeping last tokens)."""
+        collator = DataCollatorForLanguageModeling(pad_token_id=0, max_length=3, truncation_mode="keep_end")
+        examples = [{"input_ids": [1, 2, 3, 4, 5]}, {"input_ids": [6, 7, 8]}]
+
+        result = collator(examples)
+
+        assert set(result.keys()) == {"input_ids", "attention_mask", "labels"}
+        torch.testing.assert_close(result["input_ids"], torch.tensor([[3, 4, 5], [6, 7, 8]]))
+        torch.testing.assert_close(result["attention_mask"], torch.tensor([[1, 1, 1], [1, 1, 1]]))
+        torch.testing.assert_close(result["labels"], torch.tensor([[3, 4, 5], [6, 7, 8]]))
+
+    def test_max_length_no_truncation_needed(self):
+        """Test that max_length larger than sequences does not alter the output."""
+        collator = DataCollatorForLanguageModeling(pad_token_id=0, max_length=10)
+        examples = [{"input_ids": [1, 2, 3]}, {"input_ids": [4, 5]}]
+
+        result = collator(examples)
+
+        assert set(result.keys()) == {"input_ids", "attention_mask", "labels"}
+        torch.testing.assert_close(result["input_ids"], torch.tensor([[1, 2, 3], [4, 5, 0]]))
+        torch.testing.assert_close(result["attention_mask"], torch.tensor([[1, 1, 1], [1, 1, 0]]))
+        torch.testing.assert_close(result["labels"], torch.tensor([[1, 2, 3], [4, 5, -100]]))
+
+    def test_max_length_with_completion_mask(self):
+        """Test that truncation is applied correctly when completion masks are present."""
+        collator = DataCollatorForLanguageModeling(pad_token_id=0, max_length=3)
+        examples = [
+            {"input_ids": [1, 2, 3, 4, 5], "completion_mask": [0, 0, 1, 1, 1]},
+            {"input_ids": [6, 7, 8], "completion_mask": [0, 1, 1]},
+        ]
+
+        result = collator(examples)
+
+        assert set(result.keys()) == {"input_ids", "attention_mask", "labels"}
+        torch.testing.assert_close(result["input_ids"], torch.tensor([[1, 2, 3], [6, 7, 8]]))
+        torch.testing.assert_close(result["attention_mask"], torch.tensor([[1, 1, 1], [1, 1, 1]]))
+        torch.testing.assert_close(result["labels"], torch.tensor([[-100, -100, 3], [-100, 7, 8]]))
+
+    def test_max_length_keep_end_with_completion_mask(self):
+        """Test keep_end truncation with completion masks preserves the final tokens."""
+        collator = DataCollatorForLanguageModeling(pad_token_id=0, max_length=3, truncation_mode="keep_end")
+        examples = [
+            {"input_ids": [1, 2, 3, 4, 5], "completion_mask": [0, 0, 1, 1, 1]},
+            {"input_ids": [6, 7, 8], "completion_mask": [0, 1, 1]},
+        ]
+
+        result = collator(examples)
+
+        assert set(result.keys()) == {"input_ids", "attention_mask", "labels"}
+        torch.testing.assert_close(result["input_ids"], torch.tensor([[3, 4, 5], [6, 7, 8]]))
+        torch.testing.assert_close(result["attention_mask"], torch.tensor([[1, 1, 1], [1, 1, 1]]))
+        torch.testing.assert_close(result["labels"], torch.tensor([[3, 4, 5], [-100, 7, 8]]))
+
+    def test_max_length_invalid_truncation_mode(self):
+        """Test that an invalid truncation_mode raises ValueError."""
+        collator = DataCollatorForLanguageModeling(pad_token_id=0, max_length=3, truncation_mode="invalid")
+        examples = [{"input_ids": [1, 2, 3, 4, 5]}]
+
+        with pytest.raises(ValueError, match="Unsupported truncation mode"):
+            collator(examples)
+
     def test_single_example_single_doc(self):
         batch_seq_lengths = [[5]]
         result = DataCollatorForLanguageModeling.get_position_ids_from_packed_seq_lengths(batch_seq_lengths)
@@ -911,6 +985,39 @@ class TestSFTTrainer(TrlTestCase):
             new_param = trainer.model.get_parameter(n)
             assert not torch.allclose(param, new_param), f"Parameter {n} has not changed"
 
+    def test_skip_prepare_dataset_passes_truncation_to_text_collator(self):
+        dataset = load_dataset("trl-internal-testing/zen", "standard_language_modeling", split="train[:2]")
+        training_args = SFTConfig(
+            output_dir=self.tmp_dir,
+            max_length=16,
+            truncation_mode="keep_end",
+            dataset_kwargs={"skip_prepare_dataset": True},
+            report_to="none",
+        )
+
+        trainer = SFTTrainer(
+            model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5", args=training_args, train_dataset=dataset
+        )
+
+        assert isinstance(trainer.data_collator, DataCollatorForLanguageModeling)
+        assert trainer.data_collator.max_length == 16
+        assert trainer.data_collator.truncation_mode == "keep_end"
+
+    def test_skip_prepare_dataset_with_padding_free_and_max_length_raises(self):
+        dataset = load_dataset("trl-internal-testing/zen", "standard_language_modeling", split="train[:2]")
+        training_args = SFTConfig(
+            output_dir=self.tmp_dir,
+            max_length=16,
+            padding_free=True,
+            dataset_kwargs={"skip_prepare_dataset": True},
+            report_to="none",
+        )
+
+        with pytest.raises(ValueError, match="must be enforced during dataset preparation or packing"):
+            SFTTrainer(
+                model="trl-internal-testing/tiny-Qwen2ForCausalLM-2.5", args=training_args, train_dataset=dataset
+            )
+
     def test_train_with_iterable_dataset(self):
         # Get the dataset
         dataset = load_dataset("trl-internal-testing/zen", "standard_language_modeling", split="train", streaming=True)

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/experimental/test_sdft_trainer.py tests/experimental/test_sdpo_trainer.py tests/test_sft_trainer.py
: '>>>>> End Test Output'
git checkout e923a9ac37f845fc2231b2fa50c6f19367d8a9a4 tests/test_sft_trainer.py
