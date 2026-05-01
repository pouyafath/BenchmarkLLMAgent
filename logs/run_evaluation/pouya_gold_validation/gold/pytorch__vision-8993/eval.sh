#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 8a06122218e54993e3c32523a904e847ff20b39c
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e . --no-build-isolation
git checkout 8a06122218e54993e3c32523a904e847ff20b39c test/test_transforms_v2.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/test_transforms_v2.py b/test/test_transforms_v2.py
index a9fd3bc5e..9f6817bb6 100644
--- a/test/test_transforms_v2.py
+++ b/test/test_transforms_v2.py
@@ -4608,6 +4608,14 @@ class TestPosterize:
 
         assert_equal(actual, expected)
 
+    @pytest.mark.parametrize("bits", [-1, 9, 2.1])
+    def test_error_functional(self, bits):
+        with pytest.raises(
+            TypeError,
+            match=re.escape(f"bits must be a positive integer in the range [0, 8], got {bits} instead."),
+        ):
+            F.posterize(make_image(dtype=torch.uint8), bits=bits)
+
 
 class TestSolarize:
     def _make_threshold(self, input, *, factor=0.5):
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/test_transforms_v2.py
: '>>>>> End Test Output'
git checkout 8a06122218e54993e3c32523a904e847ff20b39c test/test_transforms_v2.py
