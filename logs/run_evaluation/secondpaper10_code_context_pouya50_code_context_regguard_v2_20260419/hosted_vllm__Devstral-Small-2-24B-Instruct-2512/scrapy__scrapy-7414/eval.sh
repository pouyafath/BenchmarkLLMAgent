#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 508367664fddf36da0f059142b94747601a3131c
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install hatchling editables && python -m pip install -e '.[test]' --no-build-isolation && python -m pip install pexpect pyftpdlib testfixtures || python -m pip install hatchling editables && python -m pip install -e . --no-build-isolation && python -m pip install pexpect pyftpdlib testfixtures
git checkout 508367664fddf36da0f059142b94747601a3131c tests/test_pipeline_files.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_pipeline_files.py b/tests/test_pipeline_files.py
index c412645f..76f8c251 100644
--- a/tests/test_pipeline_files.py
+++ b/tests/test_pipeline_files.py
@@ -109,6 +109,15 @@ class TestFilesPipeline:
     def teardown_method(self):
         rmtree(self.tempdir)
 
+    def test_file_path_query_parameters(self):
+        file_path = self.pipeline.file_path
+
+        req1 = Request("http://foo.bar/baz.txt?fizz")
+        assert file_path(req1) == "full/a2b4913a62f65445aeae2bac08cd8c3b41d7195e.txt"
+
+        req2 = Request("http://foo.bar/get_img.php?file=photo.jpg")
+        assert file_path(req2) == "full/118230fd648f1080c81c234d5e2463ea496f8c05.jpg"
+
     def test_file_path(self):
         file_path = self.pipeline.file_path
         assert (

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_pipeline_files.py
: '>>>>> End Test Output'
git checkout 508367664fddf36da0f059142b94747601a3131c tests/test_pipeline_files.py
