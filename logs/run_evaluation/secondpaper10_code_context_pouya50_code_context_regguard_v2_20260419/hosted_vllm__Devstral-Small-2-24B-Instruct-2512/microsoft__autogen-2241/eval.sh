#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 6ca478502dd7d35455881d64e01bbb7cdc7801c3
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]' || python -m pip install -e .
git checkout 6ca478502dd7d35455881d64e01bbb7cdc7801c3 test/coding/test_user_defined_functions.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/coding/test_user_defined_functions.py b/test/coding/test_user_defined_functions.py
index 7a68acdc..53b3c504 100644
--- a/test/coding/test_user_defined_functions.py
+++ b/test/coding/test_user_defined_functions.py
@@ -54,7 +54,7 @@ def function_missing_reqs() -> "pandas.DataFrame":
 def test_can_load_function_with_reqs(cls) -> None:
     with tempfile.TemporaryDirectory() as temp_dir:
         executor = cls(work_dir=temp_dir, functions=[load_data])
-        code = f"""from {cls.FUNCTIONS_MODULE} import load_data
+        code = f"""from {executor.functions_module} import load_data
 import pandas
 
 # Get first row's name
@@ -74,7 +74,7 @@ print(load_data().iloc[0]['name'])"""
 def test_can_load_function(cls) -> None:
     with tempfile.TemporaryDirectory() as temp_dir:
         executor = cls(work_dir=temp_dir, functions=[add_two_numbers])
-        code = f"""from {cls.FUNCTIONS_MODULE} import add_two_numbers
+        code = f"""from {executor.functions_module} import add_two_numbers
 print(add_two_numbers(1, 2))"""
 
         result = executor.execute_code_blocks(
@@ -93,7 +93,7 @@ print(add_two_numbers(1, 2))"""
 # def test_fails_for_missing_reqs(cls) -> None:
 #     with tempfile.TemporaryDirectory() as temp_dir:
 #         executor = cls(work_dir=temp_dir, functions=[function_missing_reqs])
-#         code = f"""from {cls.FUNCTIONS_MODULE} import function_missing_reqs
+#         code = f"""from {executor.functions_module} import function_missing_reqs
 # function_missing_reqs()"""
 
 #         with pytest.raises(ValueError):
@@ -109,7 +109,7 @@ print(add_two_numbers(1, 2))"""
 def test_fails_for_function_incorrect_import(cls) -> None:
     with tempfile.TemporaryDirectory() as temp_dir:
         executor = cls(work_dir=temp_dir, functions=[function_incorrect_import])
-        code = f"""from {cls.FUNCTIONS_MODULE} import function_incorrect_import
+        code = f"""from {executor.functions_module} import function_incorrect_import
 function_incorrect_import()"""
 
         with pytest.raises(ValueError):
@@ -125,7 +125,7 @@ function_incorrect_import()"""
 def test_fails_for_function_incorrect_dep(cls) -> None:
     with tempfile.TemporaryDirectory() as temp_dir:
         executor = cls(work_dir=temp_dir, functions=[function_incorrect_dep])
-        code = f"""from {cls.FUNCTIONS_MODULE} import function_incorrect_dep
+        code = f"""from {executor.functions_module} import function_incorrect_dep
 function_incorrect_dep()"""
 
         with pytest.raises(ValueError):
@@ -183,7 +183,7 @@ def add_two_numbers(a: int, b: int) -> int:
         )
 
         executor = cls(work_dir=temp_dir, functions=[func])
-        code = f"""from {cls.FUNCTIONS_MODULE} import add_two_numbers
+        code = f"""from {executor.functions_module} import add_two_numbers
 print(add_two_numbers(1, 2))"""
 
         result = executor.execute_code_blocks(
@@ -219,10 +219,9 @@ def add_two_numbers(a: int, b: int) -> int:
 '''
         )
 
-        code = f"""from {cls.FUNCTIONS_MODULE} import add_two_numbers
-print(add_two_numbers(object(), False))"""
-
         executor = cls(work_dir=temp_dir, functions=[func])
+        code = f"""from {executor.functions_module} import add_two_numbers
+print(add_two_numbers(object(), False))"""
 
         result = executor.execute_code_blocks(
             code_blocks=[
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/coding/test_user_defined_functions.py
: '>>>>> End Test Output'
git checkout 6ca478502dd7d35455881d64e01bbb7cdc7801c3 test/coding/test_user_defined_functions.py
