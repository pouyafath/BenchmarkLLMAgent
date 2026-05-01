#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 6aee5eddc8f9b397b45d076bd336c030518b7626
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e . --no-build-isolation
git checkout 6aee5eddc8f9b397b45d076bd336c030518b7626 test/common_utils.py test/test_transforms_v2.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/common_utils.py b/test/common_utils.py
index 9da3cf52d..9af40cec8 100644
--- a/test/common_utils.py
+++ b/test/common_utils.py
@@ -410,6 +410,7 @@ def make_bounding_boxes(
     canvas_size=DEFAULT_SIZE,
     *,
     format=tv_tensors.BoundingBoxFormat.XYXY,
+    clamping_mode="hard",  # TODOBB
     num_boxes=1,
     dtype=None,
     device="cpu",
@@ -474,13 +475,16 @@ def make_bounding_boxes(
         # numerical issues during the testing
         buffer = 4
         out_boxes = clamp_bounding_boxes(
-            out_boxes, format=format, canvas_size=(canvas_size[0] - buffer, canvas_size[1] - buffer)
+            out_boxes,
+            format=format,
+            canvas_size=(canvas_size[0] - buffer, canvas_size[1] - buffer),
+            clamping_mode=clamping_mode,
         )
         if format is tv_tensors.BoundingBoxFormat.XYWHR or format is tv_tensors.BoundingBoxFormat.CXCYWHR:
             out_boxes[:, :2] += buffer // 2
         elif format is tv_tensors.BoundingBoxFormat.XYXYXYXY:
             out_boxes[:, :] += buffer // 2
-    return tv_tensors.BoundingBoxes(out_boxes, format=format, canvas_size=canvas_size)
+    return tv_tensors.BoundingBoxes(out_boxes, format=format, canvas_size=canvas_size, clamping_mode=clamping_mode)
 
 
 def make_detection_masks(size=DEFAULT_SIZE, *, num_masks=1, dtype=None, device="cpu"):
diff --git a/test/test_transforms_v2.py b/test/test_transforms_v2.py
index 7e667586a..dd7746722 100644
--- a/test/test_transforms_v2.py
+++ b/test/test_transforms_v2.py
@@ -492,6 +492,7 @@ INTERPOLATION_MODES = [
 def reference_affine_bounding_boxes_helper(bounding_boxes, *, affine_matrix, new_canvas_size=None, clamp=True):
     format = bounding_boxes.format
     canvas_size = new_canvas_size or bounding_boxes.canvas_size
+    clamping_mode = bounding_boxes.clamping_mode
 
     def affine_bounding_boxes(bounding_boxes):
         dtype = bounding_boxes.dtype
@@ -535,6 +536,7 @@ def reference_affine_bounding_boxes_helper(bounding_boxes, *, affine_matrix, new
                 output,
                 format=format,
                 canvas_size=canvas_size,
+                clamping_mode=clamping_mode,
             )
         else:
             # We leave the bounding box as float64 so the caller gets the full precision to perform any additional
@@ -557,6 +559,7 @@ def reference_affine_rotated_bounding_boxes_helper(
 ):
     format = bounding_boxes.format
     canvas_size = new_canvas_size or bounding_boxes.canvas_size
+    clamping_mode = bounding_boxes.clamping_mode
 
     def affine_rotated_bounding_boxes(bounding_boxes):
         dtype = bounding_boxes.dtype
@@ -618,6 +621,7 @@ def reference_affine_rotated_bounding_boxes_helper(
                 output.to(dtype=dtype, device=device),
                 format=format,
                 canvas_size=canvas_size,
+                clamping_mode=clamping_mode,
             )
             if clamp
             else output.to(dtype=output.dtype, device=device)
@@ -831,7 +835,6 @@ class TestResize:
             (F.resize_image, torch.Tensor),
             (F._geometry._resize_image_pil, PIL.Image.Image),
             (F.resize_image, tv_tensors.Image),
-            (F.resize_bounding_boxes, tv_tensors.BoundingBoxes),
             (F.resize_mask, tv_tensors.Mask),
             (F.resize_video, tv_tensors.Video),
             (F.resize_keypoints, tv_tensors.KeyPoints),
@@ -3289,7 +3292,6 @@ class TestElastic:
             (F.elastic_image, torch.Tensor),
             (F._geometry._elastic_image_pil, PIL.Image.Image),
             (F.elastic_image, tv_tensors.Image),
-            (F.elastic_bounding_boxes, tv_tensors.BoundingBoxes),
             (F.elastic_mask, tv_tensors.Mask),
             (F.elastic_video, tv_tensors.Video),
             (F.elastic_keypoints, tv_tensors.KeyPoints),
@@ -5126,6 +5128,7 @@ class TestPerspective:
     def _reference_perspective_bounding_boxes(self, bounding_boxes, *, startpoints, endpoints):
         format = bounding_boxes.format
         canvas_size = bounding_boxes.canvas_size
+        clamping_mode = bounding_boxes.clamping_mode
         dtype = bounding_boxes.dtype
         device = bounding_boxes.device
         is_rotated = tv_tensors.is_rotated_bounding_format(format)
@@ -5226,6 +5229,7 @@ class TestPerspective:
                 output,
                 format=format,
                 canvas_size=canvas_size,
+                clamping_mode=clamping_mode,
             ).to(dtype=dtype, device=device)
 
         return tv_tensors.BoundingBoxes(
@@ -5506,29 +5510,35 @@ class TestNormalize:
 
 class TestClampBoundingBoxes:
     @pytest.mark.parametrize("format", list(tv_tensors.BoundingBoxFormat))
+    @pytest.mark.parametrize("clamping_mode", ("hard", "none"))  # TODOBB add soft
     @pytest.mark.parametrize("dtype", [torch.int64, torch.float32])
     @pytest.mark.parametrize("device", cpu_and_cuda())
-    def test_kernel(self, format, dtype, device):
-        bounding_boxes = make_bounding_boxes(format=format, dtype=dtype, device=device)
+    def test_kernel(self, format, clamping_mode, dtype, device):
+        bounding_boxes = make_bounding_boxes(format=format, clamping_mode=clamping_mode, dtype=dtype, device=device)
         check_kernel(
             F.clamp_bounding_boxes,
             bounding_boxes,
             format=bounding_boxes.format,
             canvas_size=bounding_boxes.canvas_size,
+            clamping_mode=clamping_mode,
         )
 
     @pytest.mark.parametrize("format", list(tv_tensors.BoundingBoxFormat))
-    def test_functional(self, format):
-        check_functional(F.clamp_bounding_boxes, make_bounding_boxes(format=format))
+    @pytest.mark.parametrize("clamping_mode", ("hard", "none"))  # TODOBB add soft
+    def test_functional(self, format, clamping_mode):
+        check_functional(F.clamp_bounding_boxes, make_bounding_boxes(format=format, clamping_mode=clamping_mode))
 
     def test_errors(self):
         input_tv_tensor = make_bounding_boxes()
         input_pure_tensor = input_tv_tensor.as_subclass(torch.Tensor)
         format, canvas_size = input_tv_tensor.format, input_tv_tensor.canvas_size
 
-        for format_, canvas_size_ in [(None, None), (format, None), (None, canvas_size)]:
+        for format_, canvas_size_, clamping_mode_ in itertools.product(
+            (format, None), (canvas_size, None), (input_tv_tensor.clamping_mode, None)
+        ):
             with pytest.raises(
-                ValueError, match="For pure tensor inputs, `format` and `canvas_size` have to be passed."
+                ValueError,
+                match="For pure tensor inputs, `format`, `canvas_size` and `clamping_mode` have to be passed.",
             ):
                 F.clamp_bounding_boxes(input_pure_tensor, format=format_, canvas_size=canvas_size_)
 
@@ -5541,6 +5551,103 @@ class TestClampBoundingBoxes:
     def test_transform(self):
         check_transform(transforms.ClampBoundingBoxes(), make_bounding_boxes())
 
+    @pytest.mark.parametrize("rotated", (True, False))
+    @pytest.mark.parametrize("constructor_clamping_mode", ("hard", "none"))
+    @pytest.mark.parametrize("clamping_mode", ("hard", "none", None))  # TODOBB add soft here.
+    @pytest.mark.parametrize("pass_pure_tensor", (True, False))
+    @pytest.mark.parametrize("fn", [F.clamp_bounding_boxes, transform_cls_to_functional(transforms.ClampBoundingBoxes)])
+    def test_clamping_mode(self, rotated, constructor_clamping_mode, clamping_mode, pass_pure_tensor, fn):
+        # This test checks 2 things:
+        # - That passing clamping_mode=None to the clamp_bounding_boxes
+        #   functional (or to the class) relies on the box's `.clamping_mode`
+        #   attribute
+        # - That clamping happens when it should, and only when it should, i.e.
+        #   when the clamping mode is not "none". It doesn't validate the
+        #   nunmerical results, only that clamping happened. For that, we create
+        #   a large 100x100 box inside of a small 10x10 image.
+
+        if pass_pure_tensor and fn is not F.clamp_bounding_boxes:
+            # Only the functional supports pure tensors, not the class
+            return
+        if pass_pure_tensor and clamping_mode is None:
+            # cannot leave clamping_mode=None when passing pure tensor
+            return
+
+        if rotated:
+            boxes = tv_tensors.BoundingBoxes(
+                [0, 0, 100, 100, 0], format="XYWHR", canvas_size=(10, 10), clamping_mode=constructor_clamping_mode
+            )
+            expected_clamped_output = torch.tensor([[0, 0, 10, 10, 0]])
+        else:
+            boxes = tv_tensors.BoundingBoxes(
+                [0, 100, 0, 100], format="XYXY", canvas_size=(10, 10), clamping_mode=constructor_clamping_mode
+            )
+            expected_clamped_output = torch.tensor([[0, 10, 0, 10]])
+
+        if pass_pure_tensor:
+            out = fn(
+                boxes.as_subclass(torch.Tensor),
+                format=boxes.format,
+                canvas_size=boxes.canvas_size,
+                clamping_mode=clamping_mode,
+            )
+        else:
+            out = fn(boxes, clamping_mode=clamping_mode)
+
+        clamping_mode_prevailing = constructor_clamping_mode if clamping_mode is None else clamping_mode
+        if clamping_mode_prevailing == "none":
+            assert_equal(boxes, out)  # should be a pass-through
+        else:
+            assert_equal(out, expected_clamped_output)
+
+
+class TestSetClampingMode:
+    @pytest.mark.parametrize("format", list(tv_tensors.BoundingBoxFormat))
+    @pytest.mark.parametrize("constructor_clamping_mode", ("hard", "none"))  # TODOBB add soft
+    @pytest.mark.parametrize("desired_clamping_mode", ("hard", "none"))  # TODOBB add soft
+    def test_setter(self, format, constructor_clamping_mode, desired_clamping_mode):
+
+        in_boxes = make_bounding_boxes(format=format, clamping_mode=constructor_clamping_mode)
+        out_boxes = transforms.SetClampingMode(clamping_mode=desired_clamping_mode)(in_boxes)
+
+        assert in_boxes.clamping_mode == constructor_clamping_mode  # input is unchanged: no leak
+        assert out_boxes.clamping_mode == desired_clamping_mode
+
+    @pytest.mark.parametrize("format", list(tv_tensors.BoundingBoxFormat))
+    @pytest.mark.parametrize("constructor_clamping_mode", ("hard", "none"))  # TODOBB add soft
+    def test_pipeline_no_leak(self, format, constructor_clamping_mode):
+        class AssertClampingMode(transforms.Transform):
+            def __init__(self, expected_clamping_mode):
+                super().__init__()
+                self.expected_clamping_mode = expected_clamping_mode
+
+            _transformed_types = (tv_tensors.BoundingBoxes,)
+
+            def transform(self, inpt, _):
+                assert inpt.clamping_mode == self.expected_clamping_mode
+                return inpt
+
+        t = transforms.Compose(
+            [
+                transforms.SetClampingMode("none"),
+                AssertClampingMode("none"),
+                transforms.SetClampingMode("hard"),
+                AssertClampingMode("hard"),
+                transforms.SetClampingMode("none"),
+                AssertClampingMode("none"),
+                transforms.ClampBoundingBoxes("hard"),
+            ]
+        )
+
+        in_boxes = make_bounding_boxes(format=format, clamping_mode=constructor_clamping_mode)
+        out_boxes = t(in_boxes)
+
+        assert in_boxes.clamping_mode == constructor_clamping_mode  # input is unchanged: no leak
+
+        # assert that the output boxes clamping_mode is the one set by the last SetClampingMode.
+        # ClampBoundingBoxes doesn't set clamping_mode.
+        assert out_boxes.clamping_mode == "none"
+
 
 class TestClampKeyPoints:
     @pytest.mark.parametrize("dtype", [torch.int64, torch.float32])

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/common_utils.py test/test_transforms_v2.py
: '>>>>> End Test Output'
git checkout 6aee5eddc8f9b397b45d076bd336c030518b7626 test/common_utils.py test/test_transforms_v2.py
