#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 6af299ac2396b0d29d7976c861765022f6df8ee9
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose && python -m pip install 'trl>=0.12.2'
git checkout 6af299ac2396b0d29d7976c861765022f6df8ee9 tests/test_lab_train.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_lab_train.py b/tests/test_lab_train.py
index 4407e6565d..3feb591c6d 100644
--- a/tests/test_lab_train.py
+++ b/tests/test_lab_train.py
@@ -158,7 +158,7 @@ def test_invalid_taxonomy(self):
             result = runner.invoke(lab.train, ["--input-dir", INPUT_DIR])
             self.assertIsNotNone(result.exception)
             self.assertIn(
-                "Could not copy into data directory: list index out of range",
+                f"{INPUT_DIR} does not contain training or test files, did you run `ilab generate`?",
                 result.output,
             )
             self.assertEqual(result.exit_code, 1)

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_lab_train.py
: '>>>>> End Test Output'
git checkout 6af299ac2396b0d29d7976c861765022f6df8ee9 tests/test_lab_train.py
