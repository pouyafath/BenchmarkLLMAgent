#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 659a32fd5b54c45152714385740f520b5e9d68a0
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 659a32fd5b54c45152714385740f520b5e9d68a0 tests/functional/b/bad_reversed_sequence.py tests/functional/c/consider/consider_using_enumerate.py tests/functional/ext/docparams/return/missing_return_doc_Sphinx.py tests/functional/i/iterable_context_py36.py tests/functional/n/non/non_iterator_returned.py tests/functional/s/stop_iteration_inside_generator.py tests/functional/u/undefined/undefined_variable.py tests/functional/u/unpacking/unpacking_non_sequence.py tests/functional/u/use/use_implicit_booleaness_not_len.py tests/functional/y/yield_assign.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/functional/b/bad_reversed_sequence.py b/tests/functional/b/bad_reversed_sequence.py
index c4380491e9..d9c3c68b3f 100644
--- a/tests/functional/b/bad_reversed_sequence.py
+++ b/tests/functional/b/bad_reversed_sequence.py
@@ -1,6 +1,6 @@
 """ Checks that reversed() receive proper argument """
 # pylint: disable=missing-docstring
-# pylint: disable=too-few-public-methods
+# pylint: disable=too-few-public-methods,use-yield-from
 from collections import deque, OrderedDict
 from enum import IntEnum
 
diff --git a/tests/functional/c/consider/consider_using_enumerate.py b/tests/functional/c/consider/consider_using_enumerate.py
index 1b8bb4c6b1..b49ffd9f0b 100644
--- a/tests/functional/c/consider/consider_using_enumerate.py
+++ b/tests/functional/c/consider/consider_using_enumerate.py
@@ -1,6 +1,6 @@
 """Emit a message for iteration through range and len is encountered."""
 
-# pylint: disable=missing-docstring, import-error, unsubscriptable-object, too-few-public-methods, unnecessary-list-index-lookup
+# pylint: disable=missing-docstring, import-error, unsubscriptable-object, too-few-public-methods, unnecessary-list-index-lookup, use-yield-from
 
 def bad():
     iterable = [1, 2, 3]
diff --git a/tests/functional/ext/docparams/return/missing_return_doc_Sphinx.py b/tests/functional/ext/docparams/return/missing_return_doc_Sphinx.py
index 41b0ce1ae5..1351d1cef8 100644
--- a/tests/functional/ext/docparams/return/missing_return_doc_Sphinx.py
+++ b/tests/functional/ext/docparams/return/missing_return_doc_Sphinx.py
@@ -1,7 +1,7 @@
 """Tests for missing-return-doc and missing-return-type-doc for Sphinx style docstrings"""
 # pylint: disable=function-redefined, invalid-name, undefined-variable, missing-function-docstring
 # pylint: disable=unused-argument, disallowed-name, too-few-public-methods, missing-class-docstring
-# pylint: disable=unnecessary-pass
+# pylint: disable=unnecessary-pass, use-yield-from
 import abc
 
 
diff --git a/tests/functional/i/iterable_context_py36.py b/tests/functional/i/iterable_context_py36.py
index d50d3da981..ecb48a241f 100644
--- a/tests/functional/i/iterable_context_py36.py
+++ b/tests/functional/i/iterable_context_py36.py
@@ -1,4 +1,4 @@
-# pylint: disable=missing-docstring,too-few-public-methods,unused-variable,unnecessary-comprehension
+# pylint: disable=missing-docstring,too-few-public-methods,unused-variable,unnecessary-comprehension,use-yield-from
 import asyncio
 
 class AIter:
diff --git a/tests/functional/n/non/non_iterator_returned.py b/tests/functional/n/non/non_iterator_returned.py
index 3bc24a23e0..7dffd711ec 100644
--- a/tests/functional/n/non/non_iterator_returned.py
+++ b/tests/functional/n/non/non_iterator_returned.py
@@ -1,6 +1,6 @@
 """Check non-iterators returned by __iter__ """
 
-# pylint: disable=too-few-public-methods, missing-docstring, consider-using-with, import-error
+# pylint: disable=too-few-public-methods, missing-docstring, consider-using-with, import-error, use-yield-from
 from uninferable import UNINFERABLE
 
 class FirstGoodIterator:
diff --git a/tests/functional/s/stop_iteration_inside_generator.py b/tests/functional/s/stop_iteration_inside_generator.py
index fcd20a6836..4b034e2506 100644
--- a/tests/functional/s/stop_iteration_inside_generator.py
+++ b/tests/functional/s/stop_iteration_inside_generator.py
@@ -2,7 +2,7 @@
 Test that no StopIteration is raised inside a generator
 """
 # pylint: disable=missing-docstring,invalid-name,import-error, try-except-raise, wrong-import-position
-# pylint: disable=not-callable,raise-missing-from,broad-exception-raised
+# pylint: disable=not-callable,raise-missing-from,broad-exception-raised,use-yield-from
 import asyncio
 
 class RebornStopIteration(StopIteration):
diff --git a/tests/functional/u/undefined/undefined_variable.py b/tests/functional/u/undefined/undefined_variable.py
index e1b66910fc..194de114d3 100644
--- a/tests/functional/u/undefined/undefined_variable.py
+++ b/tests/functional/u/undefined/undefined_variable.py
@@ -1,7 +1,7 @@
 # pylint: disable=missing-docstring, multiple-statements, import-outside-toplevel
 # pylint: disable=too-few-public-methods, bare-except, broad-except
 # pylint: disable=using-constant-test, import-error, global-variable-not-assigned, unnecessary-comprehension
-# pylint: disable=unnecessary-lambda-assignment
+# pylint: disable=unnecessary-lambda-assignment, use-yield-from
 
 
 from typing import TYPE_CHECKING
diff --git a/tests/functional/u/unpacking/unpacking_non_sequence.py b/tests/functional/u/unpacking/unpacking_non_sequence.py
index feb465ecbe..0a13c656c8 100644
--- a/tests/functional/u/unpacking/unpacking_non_sequence.py
+++ b/tests/functional/u/unpacking/unpacking_non_sequence.py
@@ -1,6 +1,6 @@
 """Check unpacking non-sequences in assignments. """
 
-# pylint: disable=too-few-public-methods, invalid-name, attribute-defined-outside-init, unused-variable
+# pylint: disable=too-few-public-methods, invalid-name, attribute-defined-outside-init, unused-variable, use-yield-from
 # pylint: disable=using-constant-test, missing-docstring, wrong-import-order,wrong-import-position,no-else-return
 from os import rename as nonseq_func
 from functional.u.unpacking.unpacking import nonseq
diff --git a/tests/functional/u/use/use_implicit_booleaness_not_len.py b/tests/functional/u/use/use_implicit_booleaness_not_len.py
index 79547d99e1..1261aa3014 100644
--- a/tests/functional/u/use/use_implicit_booleaness_not_len.py
+++ b/tests/functional/u/use/use_implicit_booleaness_not_len.py
@@ -1,4 +1,4 @@
-# pylint: disable=too-few-public-methods,import-error, missing-docstring
+# pylint: disable=too-few-public-methods,import-error, missing-docstring, use-yield-from
 # pylint: disable=useless-super-delegation,wrong-import-position,invalid-name, wrong-import-order, condition-evals-to-constant
 
 if len('TEST'):  # [use-implicit-booleaness-not-len]
diff --git a/tests/functional/u/use/use_yield_from.py b/tests/functional/u/use/use_yield_from.py
new file mode 100644
index 0000000000..2ccbb6d77e
--- /dev/null
+++ b/tests/functional/u/use/use_yield_from.py
@@ -0,0 +1,59 @@
+# pylint: disable=missing-docstring, import-error, yield-outside-function
+import factory
+from magic import shazam, turbogen
+
+yield 1
+
+def bad(generator):
+    for item in generator:  # [use-yield-from]
+        yield item
+
+
+def out_of_names():
+    for item in turbogen():  # [use-yield-from]
+        yield item
+
+
+def good(generator):
+    for item in generator:
+        shazam()
+        yield item
+
+
+def yield_something():
+    yield 5
+
+
+def yield_attr():
+    for item in factory.gen():  # [use-yield-from]
+        yield item
+
+
+def yield_attr_nested():
+    for item in factory.kiwi.gen():  # [use-yield-from]
+        yield item
+
+
+def yield_expr():
+    for item in [1, 2, 3]:  # [use-yield-from]
+        yield item
+
+
+def for_else_yield(gen, something):
+    for item in gen():
+        if shazam(item):
+            break
+    else:
+        yield something
+
+
+# yield from is not supported in async functions, so the following are fine
+
+async def async_for_yield(agen):
+    async for item in agen:
+        yield item
+
+
+async def async_yield(agen):
+    for item in agen:
+        yield item
diff --git a/tests/functional/u/use/use_yield_from.txt b/tests/functional/u/use/use_yield_from.txt
new file mode 100644
index 0000000000..fd77d31eb3
--- /dev/null
+++ b/tests/functional/u/use/use_yield_from.txt
@@ -0,0 +1,5 @@
+use-yield-from:8:4:9:18:bad:Use 'yield from' directly instead of yielding each element one by one:HIGH
+use-yield-from:13:4:14:18:out_of_names:Use 'yield from' directly instead of yielding each element one by one:HIGH
+use-yield-from:28:4:29:18:yield_attr:Use 'yield from' directly instead of yielding each element one by one:HIGH
+use-yield-from:33:4:34:18:yield_attr_nested:Use 'yield from' directly instead of yielding each element one by one:HIGH
+use-yield-from:38:4:39:18:yield_expr:Use 'yield from' directly instead of yielding each element one by one:HIGH
diff --git a/tests/functional/y/yield_assign.py b/tests/functional/y/yield_assign.py
index e7a938c692..841fe5db31 100644
--- a/tests/functional/y/yield_assign.py
+++ b/tests/functional/y/yield_assign.py
@@ -1,3 +1,4 @@
+# pylint: disable=use-yield-from
 """https://www.logilab.org/ticket/8771"""
 
 

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/functional/b/bad_reversed_sequence.py tests/functional/c/consider/consider_using_enumerate.py tests/functional/ext/docparams/return/missing_return_doc_Sphinx.py tests/functional/i/iterable_context_py36.py tests/functional/n/non/non_iterator_returned.py tests/functional/s/stop_iteration_inside_generator.py tests/functional/u/undefined/undefined_variable.py tests/functional/u/unpacking/unpacking_non_sequence.py tests/functional/u/use/use_implicit_booleaness_not_len.py tests/functional/u/use/use_yield_from.py tests/functional/y/yield_assign.py
: '>>>>> End Test Output'
git checkout 659a32fd5b54c45152714385740f520b5e9d68a0 tests/functional/b/bad_reversed_sequence.py tests/functional/c/consider/consider_using_enumerate.py tests/functional/ext/docparams/return/missing_return_doc_Sphinx.py tests/functional/i/iterable_context_py36.py tests/functional/n/non/non_iterator_returned.py tests/functional/s/stop_iteration_inside_generator.py tests/functional/u/undefined/undefined_variable.py tests/functional/u/unpacking/unpacking_non_sequence.py tests/functional/u/use/use_implicit_booleaness_not_len.py tests/functional/y/yield_assign.py
