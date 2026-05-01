#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff df421b423f714eb3ae22cab2b0e6e7a6f6bb29be
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e . --no-build-isolation
git checkout df421b423f714eb3ae22cab2b0e6e7a6f6bb29be test/test_ops.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/test_ops.py b/test/test_ops.py
index d2cf8d291..0bb0efa24 100644
--- a/test/test_ops.py
+++ b/test/test_ops.py
@@ -1966,6 +1966,27 @@ class TestMasksToBoxes:
             masks = _create_masks(image, masks)
             masks_box_check(masks, expected)
 
+    def test_empty_masks(self):
+        masks = torch.zeros((3, 64, 64))
+        boxes = ops.masks_to_boxes(masks)
+        expected = torch.zeros((3, 4))
+        torch.testing.assert_close(boxes, expected, rtol=0.0, atol=0.0)
+
+    def test_mixed_empty_and_non_empty_masks(self):
+        masks = torch.zeros((3, 10, 10))
+        masks[1, 2:5, 3:7] = 1
+
+        boxes = ops.masks_to_boxes(masks)
+
+        expected = torch.tensor(
+            [
+                [0.0, 0.0, 0.0, 0.0],
+                [3.0, 2.0, 6.0, 4.0],
+                [0.0, 0.0, 0.0, 0.0],
+            ]
+        )
+        torch.testing.assert_close(boxes, expected, rtol=0.0, atol=0.0)
+
 
 class TestStochasticDepth:
     @pytest.mark.parametrize("seed", range(10))

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/test_ops.py
: '>>>>> End Test Output'
git checkout df421b423f714eb3ae22cab2b0e6e7a6f6bb29be test/test_ops.py
