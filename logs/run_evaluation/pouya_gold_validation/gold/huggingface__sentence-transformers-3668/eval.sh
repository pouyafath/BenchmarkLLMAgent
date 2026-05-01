#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 9ea6509dfe415ca47101094e94c222823232d3df
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[dev]'
git checkout 9ea6509dfe415ca47101094e94c222823232d3df tests/samplers/test_group_by_label_batch_sampler.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/samplers/test_group_by_label_batch_sampler.py b/tests/samplers/test_group_by_label_batch_sampler.py
index 99a2659..0667261 100644
--- a/tests/samplers/test_group_by_label_batch_sampler.py
+++ b/tests/samplers/test_group_by_label_batch_sampler.py
@@ -17,87 +17,222 @@ else:
 
 
 @pytest.fixture
-def dummy_dataset():
-    """
-
-    Dummy dataset for testing purposes. The dataset looks as follows:
-    {
-        "data": [0, 1, 2, ..., 99],
-        "label_a": [0, 1, 0, 1, ..., 0, 1],
-        "label_b": [0, 1, 2, 3, 4, 0, ..., 4]
-    }
-    """
-    data = {"data": list(range(100)), "label_a": [i % 2 for i in range(100)], "label_b": [i % 5 for i in range(100)]}
+def balanced_dataset():
+    """100 samples, 5 labels with 20 samples each."""
+    data = {"data": list(range(100)), "label": [i % 5 for i in range(100)]}
     return Dataset.from_dict(data)
 
 
 @pytest.fixture
-def dummy_uneven_dataset():
-    """
-    Dummy dataset for testing purposes. The dataset looks as follows:
-    {
-        "data": ["a"] * 51,
-        "label": [0] * 17 + [1] * 17 + [2] * 17,
-    }
-    """
-    data = {"data": ["a"] * 51, "label": [0] * 17 + [1] * 17 + [2] * 17}
+def two_label_dataset():
+    """100 samples, 2 labels with 50 samples each."""
+    data = {"data": list(range(100)), "label": [i % 2 for i in range(100)]}
     return Dataset.from_dict(data)
 
 
-def test_group_by_label_batch_sampler_label_a(dummy_dataset: Dataset) -> None:
-    batch_size = 10
+@pytest.fixture
+def imbalanced_dataset():
+    """140 samples: label 0 has 90, label 1 has 30, label 2 has 20."""
+    labels = [0] * 90 + [1] * 30 + [2] * 20
+    data = {"data": list(range(140)), "label": labels}
+    return Dataset.from_dict(data)
+
 
+def test_every_label_appears_at_least_twice_per_batch(balanced_dataset: Dataset) -> None:
     sampler = GroupByLabelBatchSampler(
-        dataset=dummy_dataset, batch_size=batch_size, drop_last=False, valid_label_columns=["label_a", "label_b"]
+        dataset=balanced_dataset, batch_size=16, drop_last=True, valid_label_columns=["label"]
     )
+    labels_col = balanced_dataset["label"]
+    for batch in sampler:
+        counts = Counter(labels_col[i] for i in batch)
+        for label, count in counts.items():
+            assert count >= 2, f"Label {label} appears only {count} time(s) in batch"
 
-    batches = list(iter(sampler))
-    assert all(len(batch) == batch_size for batch in batches)
 
-    # Check if all labels within each batch are identical
-    # In this case, label_a has 50 0's and 50 1's, so with a batch size of 10 we expect each batch to
-    # have only 0's or only 1's.
+def test_drop_last_true_no_short_batches(balanced_dataset: Dataset) -> None:
+    batch_size = 16
+    sampler = GroupByLabelBatchSampler(
+        dataset=balanced_dataset, batch_size=batch_size, drop_last=True, valid_label_columns=["label"]
+    )
+    batches = list(sampler)
     for batch in batches:
-        labels = [dummy_dataset[int(idx)]["label_a"] for idx in batch]
-        assert len(set(labels)) == 1, f"Batch {batch} does not have identical labels: {labels}"
+        assert len(batch) == batch_size
+
 
+def test_drop_last_false_yields_remainder(two_label_dataset: Dataset) -> None:
+    batch_size = 32
+    sampler_drop = GroupByLabelBatchSampler(
+        dataset=two_label_dataset, batch_size=batch_size, drop_last=True, valid_label_columns=["label"]
+    )
+    sampler_keep = GroupByLabelBatchSampler(
+        dataset=two_label_dataset, batch_size=batch_size, drop_last=False, valid_label_columns=["label"]
+    )
+    batches_drop = list(sampler_drop)
+    batches_keep = list(sampler_keep)
+    assert len(batches_keep) >= len(batches_drop)
+    total_samples_keep = sum(len(b) for b in batches_keep)
+    total_samples_drop = sum(len(b) for b in batches_drop)
+    assert total_samples_keep >= total_samples_drop
 
-def test_group_by_label_batch_sampler_label_b(dummy_dataset: Dataset) -> None:
-    batch_size = 8
 
+def test_sample_coverage(balanced_dataset: Dataset) -> None:
+    """Nearly all samples should be used exactly once per epoch."""
     sampler = GroupByLabelBatchSampler(
-        dataset=dummy_dataset, batch_size=batch_size, drop_last=True, valid_label_columns=["label_b"]
+        dataset=balanced_dataset, batch_size=16, drop_last=False, valid_label_columns=["label"]
     )
+    all_indices = []
+    for batch in sampler:
+        all_indices.extend(batch)
+    assert len(all_indices) == len(set(all_indices)), "Some samples appear more than once"
+    assert len(all_indices) >= len(balanced_dataset) * 0.8, "Too many samples dropped"
+
+
+def test_len_matches_iteration(balanced_dataset: Dataset) -> None:
+    for drop_last in [True, False]:
+        sampler = GroupByLabelBatchSampler(
+            dataset=balanced_dataset, batch_size=16, drop_last=drop_last, valid_label_columns=["label"]
+        )
+        batches = list(sampler)
+        assert len(sampler) == len(batches), f"drop_last={drop_last}: __len__={len(sampler)} != actual={len(batches)}"
 
-    # drop_last=True, so each batch should be the same length and the last batch is dropped.
-    batches = list(iter(sampler))
-    assert all(len(batch) == batch_size for batch in batches), (
-        "Not all batches are the same size, while drop_last was True."
-    )
 
-    # Assert that we have the expected number of total samples in the batches.
-    assert sum(len(batch) for batch in batches) == 100 // batch_size * batch_size
+def test_len_matches_iteration_remainder_of_two() -> None:
+    """When stream_length % batch_size == 2, __len__ and __iter__ must agree.
+
+    2 labels with 6 and 4 samples -> stream_length=8, batch_size=6 -> remainder=2.
+    """
+    labels = [0] * 6 + [1] * 4
+    ds = Dataset.from_dict({"data": list(range(10)), "label": labels})
+    sampler = GroupByLabelBatchSampler(dataset=ds, batch_size=6, drop_last=False, valid_label_columns=["label"])
+    batches = list(sampler)
+    assert len(sampler) == len(batches), f"__len__={len(sampler)} but __iter__ yielded {len(batches)} batches"
 
-    # Since we have 20 occurrences each of label_b values 0, 1, 2, 3 and 4 and a batch_size of 8, we expect each batch
-    # to have either 4 or 8 samples with the same label. (The first two batches are 16 samples of the first label,
-    # leaving 4 for the third batch. There 4 of the next label are added, leaving 16 for the next two batches, and so on.)
+
+def test_raises_on_single_label() -> None:
+    data = {"data": list(range(20)), "label": [0] * 20}
+    ds = Dataset.from_dict(data)
+    with pytest.raises(ValueError, match="at least 2"):
+        GroupByLabelBatchSampler(dataset=ds, batch_size=8, drop_last=False, valid_label_columns=["label"])
+
+
+def test_raises_on_invalid_batch_size(two_label_dataset: Dataset) -> None:
+    with pytest.raises(ValueError):
+        GroupByLabelBatchSampler(
+            dataset=two_label_dataset, batch_size=7, drop_last=False, valid_label_columns=["label"]
+        )
+    with pytest.raises(ValueError):
+        GroupByLabelBatchSampler(
+            dataset=two_label_dataset, batch_size=2, drop_last=False, valid_label_columns=["label"]
+        )
+
+
+def test_imbalanced_dataset_multi_class(imbalanced_dataset: Dataset) -> None:
+    sampler = GroupByLabelBatchSampler(
+        dataset=imbalanced_dataset, batch_size=16, drop_last=True, valid_label_columns=["label"]
+    )
+    labels_col = imbalanced_dataset["label"]
+    batches = list(sampler)
+    assert len(batches) > 0
     for batch in batches:
-        labels = [dummy_dataset[int(idx)]["label_b"] for idx in batch]
-        counts = list(Counter(labels).values())
-        assert counts == [8] or counts == [4, 4]
+        batch_labels = {labels_col[i] for i in batch}
+        assert len(batch_labels) >= 2
+
 
+def test_minority_labels_participate() -> None:
+    """Labels with >= 2 samples should have their (even-trimmed) samples appear in the output."""
+    labels = [0] * 1000 + [1] * 500 + [2] * 3
+    ds = Dataset.from_dict({"data": list(range(len(labels))), "label": labels})
+    sampler = GroupByLabelBatchSampler(dataset=ds, batch_size=32, drop_last=False, valid_label_columns=["label"])
+    all_indices = set()
+    for batch in sampler:
+        all_indices.update(batch)
+    # Label 2 has 3 samples (indices 1500-1502); trimmed to 2 (even), so at least 2 should appear
+    minority_in_output = all_indices & set(range(1500, 1503))
+    assert len(minority_in_output) >= 2, "Minority label samples should participate in batches"
 
-def test_group_by_label_batch_sampler_uneven_dataset(dummy_uneven_dataset: Dataset) -> None:
-    batch_size = 8
 
+def test_two_labels_with_large_batch(two_label_dataset: Dataset) -> None:
+    """With 2 labels and batch_size=32, each batch should have exactly 32 samples with both labels."""
+    sampler = GroupByLabelBatchSampler(
+        dataset=two_label_dataset, batch_size=32, drop_last=True, valid_label_columns=["label"]
+    )
+    labels_col = two_label_dataset["label"]
+    for batch in sampler:
+        assert len(batch) == 32
+        counts = Counter(labels_col[i] for i in batch)
+        assert len(counts) == 2
+
+
+def _compute_scheduled_efficiency(label_sizes: list[int], batch_size: int) -> float:
+    """Helper: return fraction of samples that appear in properly balanced batches (not the remainder)."""
+    labels = []
+    for i, size in enumerate(label_sizes):
+        labels.extend([i] * size)
+    data = {"data": list(range(len(labels))), "label": labels}
+    ds = Dataset.from_dict(data)
     sampler = GroupByLabelBatchSampler(
-        dataset=dummy_uneven_dataset, batch_size=batch_size, drop_last=False, valid_label_columns=["label"]
+        dataset=ds, batch_size=batch_size, valid_label_columns=["label"], drop_last=True
     )
+    scheduled = sum(len(b) for b in sampler)
+    return scheduled / len(labels)
 
-    # With a batch_size of 8 and 17 samples per label; verify that every label in a batch occurs at least twice.
-    # We accept some tiny data loss (1 sample per label) due to the uneven number of samples per label.
-    batches = list(iter(sampler))
-    for batch in batches:
-        labels = [dummy_uneven_dataset[int(idx)]["label"] for idx in batch]
-        counts = list(Counter(labels).values())
-        assert [count > 1 for count in counts]
+
+def test_efficiency_few_imbalanced_labels() -> None:
+    """6 imbalanced labels."""
+    label_sizes = [1250, 1223, 1162, 896, 835, 86]
+    efficiency = _compute_scheduled_efficiency(label_sizes, batch_size=32)
+    assert efficiency >= 0.99, f"Efficiency {efficiency:.1%} is too low. Most training data is being ignored"
+
+
+def test_efficiency_many_imbalanced_labels() -> None:
+    """Many imbalanced labels."""
+    label_sizes = [962, 464, 421, 363, 276, 274, 218, 217, 207, 191]
+    label_sizes += [80 - i * 3 for i in range(10)]
+    label_sizes += [20 - i for i in range(10)]
+    label_sizes += [4, 4, 6, 8, 9, 9, 9, 10, 11, 11]
+    efficiency = _compute_scheduled_efficiency(label_sizes, batch_size=32)
+    assert efficiency >= 0.85, f"Efficiency {efficiency:.1%} is too low. Dominant labels are underused"
+
+
+@pytest.mark.parametrize("drop_last", [True, False])
+def test_batch_guarantees(drop_last: bool) -> None:
+    """Every batch must satisfy three invariants:
+
+    1. Contains >= 2 distinct labels.
+    2. Every label in the batch appears >= 2 times.
+    3. Non-last batches are exactly batch_size; the last may be smaller only when drop_last=False.
+    """
+    # Use several dataset shapes to stress-test the guarantees.
+    datasets = {
+        "balanced": [20, 20, 20, 20, 20],
+        "imbalanced": [90, 30, 20],
+        "heavy_imbalance": [1000, 500, 3],
+        "many_labels": [50, 45, 40, 35, 30, 25, 20, 15, 10, 5],
+    }
+    batch_size = 16
+    for name, label_sizes in datasets.items():
+        labels = []
+        for i, size in enumerate(label_sizes):
+            labels.extend([i] * size)
+        ds = Dataset.from_dict({"data": list(range(len(labels))), "label": labels})
+        sampler = GroupByLabelBatchSampler(
+            dataset=ds, batch_size=batch_size, drop_last=drop_last, valid_label_columns=["label"]
+        )
+        batches = list(sampler)
+        for batch_idx, batch in enumerate(batches):
+            is_last = batch_idx == len(batches) - 1
+            # (3) Size check
+            if not is_last or drop_last:
+                assert len(batch) == batch_size, (
+                    f"{name}, drop_last={drop_last}: batch {batch_idx} has {len(batch)} samples, expected {batch_size}"
+                )
+            else:
+                assert len(batch) <= batch_size
+            # (1) Multi-label check
+            counts = Counter(labels[i] for i in batch)
+            assert len(counts) >= 2, f"{name}, drop_last={drop_last}: batch {batch_idx} has only labels {set(counts)}"
+            # (2) Each label appears >= 2 times
+            for label, count in counts.items():
+                assert count >= 2, (
+                    f"{name}, drop_last={drop_last}: label {label} appears only {count} time(s) in batch {batch_idx}"
+                )
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/samplers/test_group_by_label_batch_sampler.py
: '>>>>> End Test Output'
git checkout 9ea6509dfe415ca47101094e94c222823232d3df tests/samplers/test_group_by_label_batch_sampler.py
