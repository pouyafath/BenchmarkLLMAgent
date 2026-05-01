#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 8a5946ed6bce34bfeb26b964fc8875447d841ae8
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e . --no-build-isolation
git checkout 8a5946ed6bce34bfeb26b964fc8875447d841ae8 test/test_transforms_v2.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/test_transforms_v2.py b/test/test_transforms_v2.py
index 759f1f446..30d7ba69b 100644
--- a/test/test_transforms_v2.py
+++ b/test/test_transforms_v2.py
@@ -3323,6 +3323,15 @@ class TestElastic:
             displacement=self._make_displacement(bounding_boxes),
         )
 
+    def test_kernel_bounding_boxes_at_canvas_boundary(self):
+        # Non-regression test for https://github.com/pytorch/vision/issues/9394
+        H, W = 64, 76
+        bbox = tv_tensors.BoundingBoxes([0, 0, W, H], format=tv_tensors.BoundingBoxFormat.XYXY, canvas_size=(H, W))
+        displacement = self._make_displacement(bbox)
+        F.elastic_bounding_boxes(
+            bbox.as_subclass(torch.Tensor), format=bbox.format, canvas_size=bbox.canvas_size, displacement=displacement
+        )
+
     @pytest.mark.parametrize("dtype", [torch.float32, torch.int64])
     @pytest.mark.parametrize("device", cpu_and_cuda())
     def test_kernel_keypoints(self, dtype, device):

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/test_transforms_v2.py
: '>>>>> End Test Output'
git checkout 8a5946ed6bce34bfeb26b964fc8875447d841ae8 test/test_transforms_v2.py
