#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff f3dad37614c779ab32084f0ee7b4c40ed630cecb
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[dev]'
git checkout f3dad37614c779ab32084f0ee7b4c40ed630cecb tests/test_trainer.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_trainer.py b/tests/test_trainer.py
index 2a140b7..2deaba9 100644
--- a/tests/test_trainer.py
+++ b/tests/test_trainer.py
@@ -8,10 +8,20 @@ from pathlib import Path
 
 import pytest
 import torch
+from datasets.dataset_dict import DatasetDict
+from torch.utils.data import ConcatDataset
 
 from sentence_transformers import SentenceTransformer, SentenceTransformerTrainer, losses
 from sentence_transformers.evaluation import EmbeddingSimilarityEvaluator
 from sentence_transformers.losses import MultipleNegativesRankingLoss
+from sentence_transformers.sampler import (
+    DefaultBatchSampler,
+    GroupByLabelBatchSampler,
+    NoDuplicatesBatchSampler,
+    ProportionalBatchSampler,
+    RoundRobinBatchSampler,
+    SubsetRandomSampler,
+)
 from sentence_transformers.training_args import SentenceTransformerTrainingArguments
 from sentence_transformers.util import is_datasets_available, is_training_available
 from tests.utils import SafeTemporaryDirectory
@@ -668,3 +678,226 @@ def test_trainer_no_eval_dataset_with_eval_strategy(
             loss=loss,
             **kwargs,
         )
+
+
+def test_trainer_get_batch_sampler_class(
+    stsb_bert_tiny_model: SentenceTransformer, stsb_dataset_dict: DatasetDict
+) -> None:
+    """Test that you can specify a batch_sampler class in args."""
+
+    train_dataset = stsb_dataset_dict["train"]
+
+    # Test with a class
+    args = SentenceTransformerTrainingArguments(
+        output_dir="dummy",
+        batch_sampler=GroupByLabelBatchSampler,
+    )
+    trainer = SentenceTransformerTrainer(model=stsb_bert_tiny_model, args=args, train_dataset=train_dataset)
+    batch_sampler = trainer.get_batch_sampler(
+        train_dataset,
+        batch_size=8,
+        drop_last=False,
+        valid_label_columns=trainer.data_collator.valid_label_columns,
+        generator=torch.Generator(),
+        seed=42,
+    )
+    assert isinstance(batch_sampler, GroupByLabelBatchSampler)
+
+    # Test with another class
+    args = SentenceTransformerTrainingArguments(
+        output_dir="dummy",
+        batch_sampler=NoDuplicatesBatchSampler,
+    )
+    trainer = SentenceTransformerTrainer(model=stsb_bert_tiny_model, args=args, train_dataset=train_dataset)
+    batch_sampler = trainer.get_batch_sampler(
+        train_dataset,
+        batch_size=8,
+        drop_last=False,
+        valid_label_columns=["label"],
+        generator=torch.Generator(),
+        seed=42,
+    )
+    assert isinstance(batch_sampler, NoDuplicatesBatchSampler)
+
+
+def test_trainer_get_batch_sampler_function(
+    stsb_bert_tiny_model: SentenceTransformer, stsb_dataset_dict: DatasetDict
+) -> None:
+    """Test that you can specify a batch_sampler function in args."""
+
+    train_dataset = stsb_dataset_dict["train"]
+
+    # Define a custom batch sampler function
+    def custom_batch_sampler(dataset, batch_size, drop_last, valid_label_columns, generator, seed):
+        # This function returns a GroupByLabelBatchSampler regardless of input
+        return GroupByLabelBatchSampler(
+            dataset=dataset,
+            batch_size=batch_size,
+            drop_last=drop_last,
+            valid_label_columns=valid_label_columns,
+            generator=generator,
+            seed=seed,
+        )
+
+    args = SentenceTransformerTrainingArguments(
+        output_dir="dummy",
+        batch_sampler=custom_batch_sampler,
+    )
+    trainer = SentenceTransformerTrainer(model=stsb_bert_tiny_model, args=args, train_dataset=train_dataset)
+
+    batch_sampler = trainer.get_batch_sampler(
+        train_dataset,
+        batch_size=8,
+        drop_last=False,
+        valid_label_columns=trainer.data_collator.valid_label_columns,
+        generator=torch.Generator(),
+        seed=42,
+    )
+
+    # Verify that our custom function was used
+    assert isinstance(batch_sampler, GroupByLabelBatchSampler)
+
+    # Test with a different function that returns None
+    def null_batch_sampler(*args, **kwargs):
+        return None
+
+    args = SentenceTransformerTrainingArguments(
+        output_dir="dummy",
+        batch_sampler=null_batch_sampler,
+    )
+    trainer = SentenceTransformerTrainer(model=stsb_bert_tiny_model, args=args, train_dataset=train_dataset)
+
+    batch_sampler = trainer.get_batch_sampler(
+        train_dataset,
+        batch_size=8,
+        drop_last=False,
+        valid_label_columns=["label"],
+        generator=torch.Generator(),
+        seed=42,
+    )
+
+    assert batch_sampler is None
+
+
+def test_trainer_get_multi_dataset_batch_sampler_class(
+    stsb_bert_tiny_model: SentenceTransformer, stsb_dataset_dict: DatasetDict
+) -> None:
+    """Test that you can specify a multi_dataset_batch_sampler class in args."""
+    train_dataset = stsb_dataset_dict["train"]
+    concat_dataset = ConcatDataset([train_dataset, train_dataset])
+    batch_samplers = [
+        DefaultBatchSampler(
+            SubsetRandomSampler(range(len(train_dataset))),
+            batch_size=8,
+            drop_last=False,
+            valid_label_columns=["label", "score"],
+        ),
+        DefaultBatchSampler(
+            SubsetRandomSampler(range(len(train_dataset))),
+            batch_size=8,
+            drop_last=False,
+            valid_label_columns=["label", "score"],
+        ),
+    ]
+
+    # Test with a class
+    args = SentenceTransformerTrainingArguments(
+        output_dir="dummy",
+        multi_dataset_batch_sampler=RoundRobinBatchSampler,
+    )
+    trainer = SentenceTransformerTrainer(model=stsb_bert_tiny_model, args=args, train_dataset=train_dataset)
+
+    batch_sampler = trainer.get_multi_dataset_batch_sampler(
+        concat_dataset,
+        batch_samplers=batch_samplers,
+        generator=torch.Generator(),
+        seed=42,
+    )
+
+    assert isinstance(batch_sampler, RoundRobinBatchSampler)
+
+    class CopiedProportionalBatchSampler(ProportionalBatchSampler):
+        pass
+
+    # Test with another class
+    args = SentenceTransformerTrainingArguments(
+        output_dir="dummy",
+        multi_dataset_batch_sampler=CopiedProportionalBatchSampler,
+    )
+    trainer = SentenceTransformerTrainer(model=stsb_bert_tiny_model, args=args, train_dataset=train_dataset)
+
+    batch_sampler = trainer.get_multi_dataset_batch_sampler(
+        concat_dataset,
+        batch_samplers=batch_samplers,
+        generator=torch.Generator(),
+        seed=42,
+    )
+
+    assert isinstance(batch_sampler, CopiedProportionalBatchSampler)
+
+
+def test_trainer_get_multi_dataset_batch_sampler_function(
+    stsb_bert_tiny_model: SentenceTransformer, stsb_dataset_dict: DatasetDict
+) -> None:
+    """Test that you can specify a multi_dataset_batch_sampler function in args."""
+    train_dataset = stsb_dataset_dict["train"]
+    concat_dataset = ConcatDataset([train_dataset, train_dataset])
+    batch_samplers = [
+        DefaultBatchSampler(
+            SubsetRandomSampler(range(len(train_dataset))),
+            batch_size=8,
+            drop_last=False,
+            valid_label_columns=["label", "score"],
+        ),
+        DefaultBatchSampler(
+            SubsetRandomSampler(range(len(train_dataset))),
+            batch_size=8,
+            drop_last=False,
+            valid_label_columns=["label", "score"],
+        ),
+    ]
+
+    # Define a custom multi-dataset batch sampler function
+    def custom_multi_dataset_batch_sampler(dataset, batch_samplers, generator, seed):
+        # This function returns a RoundRobinBatchSampler regardless of input
+        return RoundRobinBatchSampler(
+            dataset=dataset,
+            batch_samplers=batch_samplers,
+            generator=generator,
+            seed=seed,
+        )
+
+    args = SentenceTransformerTrainingArguments(
+        output_dir="dummy",
+        multi_dataset_batch_sampler=custom_multi_dataset_batch_sampler,
+    )
+    trainer = SentenceTransformerTrainer(model=stsb_bert_tiny_model, args=args, train_dataset=train_dataset)
+
+    batch_sampler = trainer.get_multi_dataset_batch_sampler(
+        concat_dataset,
+        batch_samplers=batch_samplers,
+        generator=torch.Generator(),
+        seed=42,
+    )
+
+    # Verify that our custom function was used
+    assert isinstance(batch_sampler, RoundRobinBatchSampler)
+
+    # Test with a different function that returns None
+    def null_multi_dataset_batch_sampler(*args, **kwargs):
+        return None
+
+    args = SentenceTransformerTrainingArguments(
+        output_dir="dummy",
+        multi_dataset_batch_sampler=null_multi_dataset_batch_sampler,
+    )
+    trainer = SentenceTransformerTrainer(model=stsb_bert_tiny_model, args=args, train_dataset=train_dataset)
+
+    batch_sampler = trainer.get_multi_dataset_batch_sampler(
+        concat_dataset,
+        batch_samplers=batch_samplers,
+        generator=torch.Generator(),
+        seed=42,
+    )
+
+    assert batch_sampler is None
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_trainer.py
: '>>>>> End Test Output'
git checkout f3dad37614c779ab32084f0ee7b4c40ed630cecb tests/test_trainer.py
