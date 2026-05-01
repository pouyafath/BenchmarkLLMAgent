#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 2b232af7f8dbfc8455210b0df0353348a7aa2c91
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[dev]'
git checkout 2b232af7f8dbfc8455210b0df0353348a7aa2c91 
git apply -v - <<'EOF_114329324912'
diff --git a/tests/sentence_transformer/losses/test_triplet.py b/tests/sentence_transformer/losses/test_triplet.py
new file mode 100644
index 0000000..9bfa7c9
--- /dev/null
+++ b/tests/sentence_transformer/losses/test_triplet.py
@@ -0,0 +1,38 @@
+from __future__ import annotations
+
+import pytest
+import torch
+
+from sentence_transformers.sentence_transformer.losses.triplet import TripletDistanceMetric, TripletLoss
+
+
+@pytest.fixture
+def dummy_model():
+    class DummyModel:
+        pass
+
+    return DummyModel()
+
+
+@pytest.mark.parametrize(
+    "distance_metric",
+    [TripletDistanceMetric.COSINE, TripletDistanceMetric.EUCLIDEAN, TripletDistanceMetric.MANHATTAN],
+    ids=["cosine", "euclidean", "manhattan"],
+)
+def test_triplet_loss_correct_direction(dummy_model, distance_metric):
+    """Loss should be lower when the positive is closer to the anchor than the negative."""
+    loss_fn = TripletLoss(model=dummy_model, distance_metric=distance_metric, triplet_margin=1.0)
+
+    anchor = torch.tensor([[1.0, 0.0, 0.0]])
+    positive = torch.tensor([[0.9, 0.1, 0.0]])  # close to anchor
+    negative = torch.tensor([[0.0, 1.0, 0.0]])  # far from anchor
+
+    # Good triplet: positive is closer than negative → should yield low/zero loss
+    good_loss = loss_fn.compute_loss_from_embeddings([anchor, positive, negative], labels=None)
+
+    # Bad triplet: swap positive and negative → should yield higher loss
+    bad_loss = loss_fn.compute_loss_from_embeddings([anchor, negative, positive], labels=None)
+
+    assert good_loss < bad_loss, (
+        f"Good triplet loss ({good_loss:.4f}) should be less than bad triplet loss ({bad_loss:.4f})"
+    )

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/sentence_transformer/losses/test_triplet.py
: '>>>>> End Test Output'
git checkout 2b232af7f8dbfc8455210b0df0353348a7aa2c91 
