#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 7ea2b7bcee377f4ae7baccc8126730d25e5fbc83
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 7ea2b7bcee377f4ae7baccc8126730d25e5fbc83 test/unittests/tools/cmake/test_cmake_cmd_line_args.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/unittests/tools/cmake/test_cmake_cmd_line_args.py b/test/unittests/tools/cmake/test_cmake_cmd_line_args.py
index b1c7dd860bb..7aa8a2f2096 100644
--- a/test/unittests/tools/cmake/test_cmake_cmd_line_args.py
+++ b/test/unittests/tools/cmake/test_cmake_cmd_line_args.py
@@ -12,6 +12,7 @@ def conanfile():
     c = ConfDefinition()
     c.loads(textwrap.dedent("""\
         tools.build:jobs=10
+        tools.microsoft.msbuild:max_cpu_count=23
     """))
 
     conanfile = ConanFileMock()
@@ -39,7 +40,7 @@ def test_ninja(conanfile):
 
 def test_visual_studio(conanfile):
     args = _cmake_cmd_line_args(conanfile, 'Visual Studio 16 2019')
-    assert [] == args
+    assert ["/m:23"] == args
 
     args = _cmake_cmd_line_args(conanfile, 'Ninja')
     assert args == ['-j10']

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/unittests/tools/cmake/test_cmake_cmd_line_args.py
: '>>>>> End Test Output'
git checkout 7ea2b7bcee377f4ae7baccc8126730d25e5fbc83 test/unittests/tools/cmake/test_cmake_cmd_line_args.py
