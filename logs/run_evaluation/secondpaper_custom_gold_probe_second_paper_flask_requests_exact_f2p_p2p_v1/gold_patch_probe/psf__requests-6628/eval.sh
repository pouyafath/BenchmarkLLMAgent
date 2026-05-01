#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 7a13c041dbef42f9f3feb14110f02626f6892e9a
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 7a13c041dbef42f9f3feb14110f02626f6892e9a tests/test_requests.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_requests.py b/tests/test_requests.py
index 34796dc7ec..77aac3fecb 100644
--- a/tests/test_requests.py
+++ b/tests/test_requests.py
@@ -2810,3 +2810,13 @@ def test_status_code_425(self):
         assert r4 == 425
         assert r5 == 425
         assert r6 == 425
+
+
+def test_json_decode_errors_are_serializable_deserializable():
+    json_decode_error = requests.exceptions.JSONDecodeError(
+        "Extra data",
+        '{"responseCode":["706"],"data":null}{"responseCode":["706"],"data":null}',
+        36,
+    )
+    deserialized_error = pickle.loads(pickle.dumps(json_decode_error))
+    assert repr(json_decode_error) == repr(deserialized_error)

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_requests.py
: '>>>>> End Test Output'
git checkout 7a13c041dbef42f9f3feb14110f02626f6892e9a tests/test_requests.py
