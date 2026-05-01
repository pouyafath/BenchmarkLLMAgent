#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff d3b1ef1fe653f4ad9d8a91db87ba1be7b8bde977
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout d3b1ef1fe653f4ad9d8a91db87ba1be7b8bde977 tests/functional/a/async_functions.txt tests/functional/d/duplicate/duplicate_argument_name.py tests/functional/d/duplicate/duplicate_argument_name.txt tests/functional/d/duplicate/duplicate_argument_name_py3.py tests/functional/d/duplicate/duplicate_argument_name_py3.txt
git apply -v - <<'EOF_114329324912'
diff --git a/tests/functional/a/async_functions.txt b/tests/functional/a/async_functions.txt
index 985fddec2d..bfb9e52021 100644
--- a/tests/functional/a/async_functions.txt
+++ b/tests/functional/a/async_functions.txt
@@ -5,6 +5,6 @@ too-many-arguments:26:0:26:26:complex_function:Too many arguments (10/5):UNDEFIN
 too-many-branches:26:0:26:26:complex_function:Too many branches (13/12):UNDEFINED
 too-many-return-statements:26:0:26:26:complex_function:Too many return statements (10/6):UNDEFINED
 dangerous-default-value:59:0:59:14:func:Dangerous default value [] as argument:UNDEFINED
-duplicate-argument-name:59:18:59:19:func:Duplicate argument name a in function definition:HIGH
+duplicate-argument-name:59:18:59:19:func:Duplicate argument name 'a' in function definition:HIGH
 disallowed-name:64:0:64:13:foo:"Disallowed name ""foo""":HIGH
 empty-docstring:64:0:64:13:foo:Empty function docstring:HIGH
diff --git a/tests/functional/d/duplicate/duplicate_argument_name.py b/tests/functional/d/duplicate/duplicate_argument_name.py
index c0c68b43bb..a6654e6bb0 100644
--- a/tests/functional/d/duplicate/duplicate_argument_name.py
+++ b/tests/functional/d/duplicate/duplicate_argument_name.py
@@ -1,14 +1,28 @@
 """Check for duplicate function arguments."""
 
+# pylint: disable=missing-docstring, line-too-long, unused-argument
+
 
 def foo1(_, _): # [duplicate-argument-name]
-    """Function with duplicate argument name."""
+    ...
 
 def foo2(_abc, *, _abc): # [duplicate-argument-name]
-    """Function with duplicate argument name."""
+    ...
 
 def foo3(_, _=3): # [duplicate-argument-name]
-    """Function with duplicate argument name."""
+    ...
 
 def foo4(_, *, _): # [duplicate-argument-name]
-    """Function with duplicate argument name."""
+    ...
+
+def foo5(_, *_, _=3): # [duplicate-argument-name, duplicate-argument-name]
+    ...
+
+def foo6(a, *a): # [duplicate-argument-name]
+    ...
+
+def foo7(a, /, a): # [duplicate-argument-name]
+    ...
+
+def foo8(a, **a): # [duplicate-argument-name]
+    ...
diff --git a/tests/functional/d/duplicate/duplicate_argument_name.txt b/tests/functional/d/duplicate/duplicate_argument_name.txt
index 2925c5ac40..c565e88f40 100644
--- a/tests/functional/d/duplicate/duplicate_argument_name.txt
+++ b/tests/functional/d/duplicate/duplicate_argument_name.txt
@@ -1,4 +1,9 @@
-duplicate-argument-name:4:12:4:13:foo1:Duplicate argument name _ in function definition:HIGH
-duplicate-argument-name:7:18:7:22:foo2:Duplicate argument name _abc in function definition:HIGH
-duplicate-argument-name:10:12:10:13:foo3:Duplicate argument name _ in function definition:HIGH
-duplicate-argument-name:13:15:13:16:foo4:Duplicate argument name _ in function definition:HIGH
+duplicate-argument-name:6:12:6:13:foo1:Duplicate argument name '_' in function definition:HIGH
+duplicate-argument-name:9:18:9:22:foo2:Duplicate argument name '_abc' in function definition:HIGH
+duplicate-argument-name:12:12:12:13:foo3:Duplicate argument name '_' in function definition:HIGH
+duplicate-argument-name:15:15:15:16:foo4:Duplicate argument name '_' in function definition:HIGH
+duplicate-argument-name:18:13:18:14:foo5:Duplicate argument name '_' in function definition:HIGH
+duplicate-argument-name:18:16:18:17:foo5:Duplicate argument name '_' in function definition:HIGH
+duplicate-argument-name:21:13:21:14:foo6:Duplicate argument name 'a' in function definition:HIGH
+duplicate-argument-name:24:15:24:16:foo7:Duplicate argument name 'a' in function definition:HIGH
+duplicate-argument-name:27:14:27:15:foo8:Duplicate argument name 'a' in function definition:HIGH
diff --git a/tests/functional/d/duplicate/duplicate_argument_name_py3.py b/tests/functional/d/duplicate/duplicate_argument_name_py3.py
deleted file mode 100644
index 4751c6f2d3..0000000000
--- a/tests/functional/d/duplicate/duplicate_argument_name_py3.py
+++ /dev/null
@@ -1,5 +0,0 @@
-"""Check for duplicate function keywordonly arguments."""
-
-
-def foo1(_, *_, _=3): # [duplicate-argument-name]
-    """Function with duplicate argument name."""
diff --git a/tests/functional/d/duplicate/duplicate_argument_name_py3.txt b/tests/functional/d/duplicate/duplicate_argument_name_py3.txt
deleted file mode 100644
index 3d6f6f8d9d..0000000000
--- a/tests/functional/d/duplicate/duplicate_argument_name_py3.txt
+++ /dev/null
@@ -1,1 +0,0 @@
-duplicate-argument-name:4:16:4:17:foo1:Duplicate argument name _ in function definition:HIGH

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/functional/d/duplicate/duplicate_argument_name.py tests/functional/d/duplicate/duplicate_argument_name_py3.py
: '>>>>> End Test Output'
git checkout d3b1ef1fe653f4ad9d8a91db87ba1be7b8bde977 tests/functional/a/async_functions.txt tests/functional/d/duplicate/duplicate_argument_name.py tests/functional/d/duplicate/duplicate_argument_name.txt tests/functional/d/duplicate/duplicate_argument_name_py3.py tests/functional/d/duplicate/duplicate_argument_name_py3.txt
