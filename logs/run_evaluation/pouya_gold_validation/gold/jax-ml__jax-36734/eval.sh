#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 2eba8d26afda6faef0f1b43af07a137084580400
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e . && python -m pip install absl-py pytest-xdist
git checkout 2eba8d26afda6faef0f1b43af07a137084580400 tests/lax_autodiff_test.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/lax_autodiff_test.py b/tests/lax_autodiff_test.py
index a21536f8f..1bceb8e80 100644
--- a/tests/lax_autodiff_test.py
+++ b/tests/lax_autodiff_test.py
@@ -480,6 +480,20 @@ class LaxAutodiffTest(jtu.JaxTestCase):
                                  preferred_element_type=jax.numpy.float32)
     jax.jacrev(f)(x)  # don't crash!
 
+  def testConvPreferredElementType(self):
+    # Regression test for https://github.com/jax-ml/jax/issues/31592
+    x = jax.numpy.ones((1, 8, 4), dtype=jax.numpy.bfloat16)
+    w = jax.numpy.ones((3, 4, 8), dtype=jax.numpy.bfloat16)
+
+    def f(x, w):
+      return jax.lax.conv_general_dilated(
+          x, w, window_strides=(1,), padding="VALID",
+          rhs_dilation=(1,), dimension_numbers=("NLC", "LIO", "NLC"),
+          preferred_element_type=jax.numpy.float32,
+      ).sum()
+
+    jax.grad(f, argnums=(0, 1))(x, w)  # don't crash!
+
   @jtu.sample_product(
     shape=[(), (2, 3)],
     dtype=float_dtypes,

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/lax_autodiff_test.py
: '>>>>> End Test Output'
git checkout 2eba8d26afda6faef0f1b43af07a137084580400 tests/lax_autodiff_test.py
