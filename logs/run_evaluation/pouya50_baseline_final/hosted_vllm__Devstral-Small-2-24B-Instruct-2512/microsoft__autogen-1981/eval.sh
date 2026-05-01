#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 99df2c5d5e63f1edd82fd13a22573ce15807a40d
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]' || python -m pip install -e .
git checkout 99df2c5d5e63f1edd82fd13a22573ce15807a40d test/coding/test_commandline_code_executor.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/coding/test_commandline_code_executor.py b/test/coding/test_commandline_code_executor.py
index 31e6ad9e..352a7170 100644
--- a/test/coding/test_commandline_code_executor.py
+++ b/test/coding/test_commandline_code_executor.py
@@ -103,7 +103,6 @@ def _test_execute_code(executor: CodeExecutor) -> None:
             assert file_line.strip() == code_line.strip()
 
 
-@pytest.mark.skipif(sys.platform in ["win32"], reason="do not run on windows")
 @pytest.mark.parametrize("cls", classes_to_test)
 def test_commandline_code_executor_timeout(cls) -> None:
     with tempfile.TemporaryDirectory() as temp_dir:
@@ -193,36 +192,29 @@ def test_dangerous_commands(lang, code, expected_message):
     ), f"Expected message '{expected_message}' not found in '{str(exc_info.value)}'"
 
 
-# This is kind of hard to test because each exec is a new env
-@pytest.mark.skipif(
-    skip_docker or not is_docker_running(),
-    reason="docker is not running or requested to skip docker tests",
-)
-def test_docker_invalid_relative_path() -> None:
-    with DockerCommandLineCodeExecutor() as executor:
-        code = """# filename: /tmp/test.py
+@pytest.mark.parametrize("cls", classes_to_test)
+def test_invalid_relative_path(cls) -> None:
+    executor = cls()
+    code = """# filename: /tmp/test.py
 
 print("hello world")
 """
-        result = executor.execute_code_blocks([CodeBlock(code=code, language="python")])
-        assert result.exit_code == 1 and "Filename is not in the workspace" in result.output
+    result = executor.execute_code_blocks([CodeBlock(code=code, language="python")])
+    assert result.exit_code == 1 and "Filename is not in the workspace" in result.output
 
 
-@pytest.mark.skipif(
-    skip_docker or not is_docker_running(),
-    reason="docker is not running or requested to skip docker tests",
-)
-def test_docker_valid_relative_path() -> None:
+@pytest.mark.parametrize("cls", classes_to_test)
+def test_valid_relative_path(cls) -> None:
     with tempfile.TemporaryDirectory() as temp_dir:
         temp_dir = Path(temp_dir)
-        with DockerCommandLineCodeExecutor(work_dir=temp_dir) as executor:
-            code = """# filename: test.py
+        executor = cls(work_dir=temp_dir)
+        code = """# filename: test.py
 
 print("hello world")
 """
-            result = executor.execute_code_blocks([CodeBlock(code=code, language="python")])
-            assert result.exit_code == 0
-            assert "hello world" in result.output
-            assert "test.py" in result.code_file
-            assert (temp_dir / "test.py") == Path(result.code_file)
-            assert (temp_dir / "test.py").exists()
+        result = executor.execute_code_blocks([CodeBlock(code=code, language="python")])
+        assert result.exit_code == 0
+        assert "hello world" in result.output
+        assert "test.py" in result.code_file
+        assert (temp_dir / "test.py").resolve() == Path(result.code_file).resolve()
+        assert (temp_dir / "test.py").exists()

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/coding/test_commandline_code_executor.py
: '>>>>> End Test Output'
git checkout 99df2c5d5e63f1edd82fd13a22573ce15807a40d test/coding/test_commandline_code_executor.py
