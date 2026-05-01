#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 6fd4873a367d20624105967c5be0d451f72f946d
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose && python -m pip install tensorflow-cpu torch jax jaxlib
git checkout 6fd4873a367d20624105967c5be0d451f72f946d keras/src/ops/core_test.py
git apply -v - <<'EOF_114329324912'
diff --git a/keras/src/ops/core_test.py b/keras/src/ops/core_test.py
index 9610ba06b840..675a2ab357fe 100644
--- a/keras/src/ops/core_test.py
+++ b/keras/src/ops/core_test.py
@@ -583,6 +583,15 @@ def test_stop_gradient_return(self):
         y = ops.stop_gradient(x)
         self.assertAllClose(x, y)
 
+    def test_stop_gradient_functional(self):
+        a = layers.Input(shape=(2,))
+        b = layers.Dense(4, kernel_initializer="ones", use_bias=False)(a)
+        c = layers.Dense(4, kernel_initializer="ones", use_bias=False)(b)
+        d = ops.stop_gradient(b) + c
+        model = models.Model(inputs=a, outputs=d)
+        output = model(ops.convert_to_tensor([[1.0, 2.0]]))
+        self.assertAllClose(ops.convert_to_numpy(output), 15.0)
+
     def test_shape(self):
         x = ops.ones((2, 3, 7, 1))
         self.assertEqual(core.shape(x).__class__, tuple)

EOF_114329324912
: '>>>>> Start Test Output'
SKIP_APPLICATIONS_TESTS=True pytest -rA keras keras/src/ops/core_test.py
: '>>>>> End Test Output'
git checkout 6fd4873a367d20624105967c5be0d451f72f946d keras/src/ops/core_test.py
