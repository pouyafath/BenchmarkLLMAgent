#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 5e7c7b4d53ce320a4de201c31c4fdd153ab207bc
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 5e7c7b4d53ce320a4de201c31c4fdd153ab207bc tests/test_lab_train.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_lab_train.py b/tests/test_lab_train.py
index 81a0922b28..85152a058c 100644
--- a/tests/test_lab_train.py
+++ b/tests/test_lab_train.py
@@ -652,7 +652,9 @@ def test_phased_train_failures(
         run_training_patch.start()
         result = run_default_phased_train(cli_runner)
         run_training_patch.stop()
-        assert TRAINING_FAILURE_MESSAGE in result.output
+        assert (
+            f"Failed during training loop: {TRAINING_FAILURE_MESSAGE}" in result.output
+        )
         assert "Training Phase 1/2..." in result.output
         assert result.exit_code == 1
 

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_lab_train.py
: '>>>>> End Test Output'
git checkout 5e7c7b4d53ce320a4de201c31c4fdd153ab207bc tests/test_lab_train.py
