#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff e345cbdfba9c656b01ef4e116822ad03ffe9d804
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose && python -m pip install tensorflow-cpu torch jax jaxlib
git checkout e345cbdfba9c656b01ef4e116822ad03ffe9d804 keras/src/layers/rnn/time_distributed_test.py
git apply -v - <<'EOF_114329324912'
diff --git a/keras/src/layers/rnn/time_distributed_test.py b/keras/src/layers/rnn/time_distributed_test.py
index f2ad37e9d110..87cc31fe6197 100644
--- a/keras/src/layers/rnn/time_distributed_test.py
+++ b/keras/src/layers/rnn/time_distributed_test.py
@@ -6,6 +6,7 @@
 from keras.src import layers
 from keras.src import ops
 from keras.src import testing
+from keras.src.models import Sequential
 
 
 class TimeDistributedTest(testing.TestCase):
@@ -77,3 +78,24 @@ def call(self, inputs, training=False, mask=None):
             np.array([[[0], [0.22]], [[0.38], [0]], [[0.7], [0.86]]]),
             output,
         )
+
+    @pytest.mark.requires_trainable_backend
+    def test_with_mask_zero(self):
+        model = Sequential(
+            [
+                layers.Input(shape=(20,)),
+                layers.Embedding(input_dim=10, output_dim=5, mask_zero=True),
+                layers.TimeDistributed(
+                    layers.Dense(units=5, activation="softmax")
+                ),
+            ]
+        )
+        model.compile(
+            optimizer="adam",
+            loss="sparse_categorical_crossentropy",
+            metrics=["accuracy"],
+        )
+        X_train = np.random.uniform(1, 10, size=(22, 20))
+        Y_train = np.random.randint(1, 2, size=(22, 20))
+
+        model.fit(X_train, Y_train, epochs=1, batch_size=16)

EOF_114329324912
: '>>>>> Start Test Output'
SKIP_APPLICATIONS_TESTS=True pytest -rA keras keras/src/layers/rnn/time_distributed_test.py
: '>>>>> End Test Output'
git checkout e345cbdfba9c656b01ef4e116822ad03ffe9d804 keras/src/layers/rnn/time_distributed_test.py
