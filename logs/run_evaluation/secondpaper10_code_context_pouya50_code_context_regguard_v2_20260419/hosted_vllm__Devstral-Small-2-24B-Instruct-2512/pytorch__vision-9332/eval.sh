#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 7a78e5419af9fe0edda5d9c952424defd1f8ffa7
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e . --no-build-isolation
git checkout 7a78e5419af9fe0edda5d9c952424defd1f8ffa7 test/test_tv_tensors.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/test_tv_tensors.py b/test/test_tv_tensors.py
index f9d545eb9..6ec3377e6 100644
--- a/test/test_tv_tensors.py
+++ b/test/test_tv_tensors.py
@@ -333,6 +333,29 @@ def test_wrap(make_input):
     assert dp_new.data_ptr() == output.data_ptr()
 
 
+def test_wrap_preserves_subclass():
+    # Non regression test for https://github.com/pytorch/vision/issues/9328
+    class MyBoundingBoxes(tv_tensors.BoundingBoxes):
+        pass
+
+    class MyKeyPoints(tv_tensors.KeyPoints):
+        pass
+
+    bbox = MyBoundingBoxes(
+        [[0, 0, 10, 10]],
+        format=tv_tensors.BoundingBoxFormat.XYXY,
+        canvas_size=(100, 100),
+    )
+    output = bbox * 2
+    wrapped = tv_tensors.wrap(output, like=bbox)
+    assert type(wrapped) is MyBoundingBoxes
+
+    kp = MyKeyPoints([[5, 5]], canvas_size=(100, 100))
+    output = kp * 2
+    wrapped = tv_tensors.wrap(output, like=kp)
+    assert type(wrapped) is MyKeyPoints
+
+
 @pytest.mark.parametrize(
     "make_input", [make_image, make_bounding_boxes, make_segmentation_mask, make_video, make_keypoints]
 )

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/test_tv_tensors.py
: '>>>>> End Test Output'
git checkout 7a78e5419af9fe0edda5d9c952424defd1f8ffa7 test/test_tv_tensors.py
