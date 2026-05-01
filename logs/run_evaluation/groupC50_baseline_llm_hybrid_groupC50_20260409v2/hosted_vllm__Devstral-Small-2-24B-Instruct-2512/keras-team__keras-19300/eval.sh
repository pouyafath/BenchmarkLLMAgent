#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff df705d4fc719ab617705197248804d689ad74767
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose && python -m pip install tensorflow-cpu torch jax jaxlib
git checkout df705d4fc719ab617705197248804d689ad74767 keras/ops/nn_test.py
git apply -v - <<'EOF_114329324912'
diff --git a/keras/ops/nn_test.py b/keras/ops/nn_test.py
index e5f9e10a065c..bc77ca2700b8 100644
--- a/keras/ops/nn_test.py
+++ b/keras/ops/nn_test.py
@@ -2,10 +2,12 @@
 import pytest
 from absl.testing import parameterized
 
+import keras
 from keras import backend
 from keras import layers
 from keras import losses
 from keras import models
+from keras import ops
 from keras import testing
 from keras.backend.common import standardize_dtype
 from keras.backend.common.keras_tensor import KerasTensor
@@ -84,6 +86,22 @@ def test_softmax(self):
         self.assertEqual(knn.softmax(x, axis=1).shape, (None, 2, 3))
         self.assertEqual(knn.softmax(x, axis=-1).shape, (None, 2, 3))
 
+    def test_softmax_in_graph(self):
+        class SoftmaxLayer(keras.Layer):
+            def call(self, x):
+                return ops.softmax(x, axis=-1)
+
+        class Model(keras.Model):
+            def __init__(self):
+                x = keras.Input(shape=(None,))
+                y = SoftmaxLayer()(x)
+                super().__init__(inputs=x, outputs=y)
+
+        # Make sure Keras is able to compile the model graph
+        model = Model()
+        x = ops.array([[1.0, 2.0, 3.0, 4.0]])
+        model.predict(x)
+
     def test_log_softmax(self):
         x = KerasTensor([None, 2, 3])
         self.assertEqual(knn.log_softmax(x).shape, (None, 2, 3))

EOF_114329324912
: '>>>>> Start Test Output'
SKIP_APPLICATIONS_TESTS=True pytest -rA keras keras/ops/nn_test.py
: '>>>>> End Test Output'
git checkout df705d4fc719ab617705197248804d689ad74767 keras/ops/nn_test.py
