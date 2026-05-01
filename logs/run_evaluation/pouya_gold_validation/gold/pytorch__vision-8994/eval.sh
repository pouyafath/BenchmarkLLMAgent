#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 251c57a8a66c3b6a1efbbb7a036c32a175776984
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e . --no-build-isolation
git checkout 251c57a8a66c3b6a1efbbb7a036c32a175776984 test/test_transforms_v2.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/test_transforms_v2.py b/test/test_transforms_v2.py
index 9f6817bb6..af52d1fca 100644
--- a/test/test_transforms_v2.py
+++ b/test/test_transforms_v2.py
@@ -3514,6 +3514,14 @@ class TestAutoAugmentTransforms:
         with pytest.raises(ValueError, match="severity must be between"):
             transforms.AugMix(severity=severity)
 
+    @pytest.mark.parametrize("num_ops", [-1, 1.1])
+    def test_rand_augment_num_ops_error(self, num_ops):
+        with pytest.raises(
+            ValueError,
+            match=re.escape(f"num_ops should be a non-negative integer, but got {num_ops} instead."),
+        ):
+            transforms.RandAugment(num_ops=num_ops)
+
 
 class TestConvertBoundingBoxFormat:
     old_new_formats = list(itertools.permutations(SUPPORTED_BOX_FORMATS, 2))
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/test_transforms_v2.py
: '>>>>> End Test Output'
git checkout 251c57a8a66c3b6a1efbbb7a036c32a175776984 test/test_transforms_v2.py
