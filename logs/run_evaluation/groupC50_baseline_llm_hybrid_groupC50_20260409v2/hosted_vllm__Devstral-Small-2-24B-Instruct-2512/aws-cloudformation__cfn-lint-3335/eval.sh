#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 3289b0dd509d1c870917aff6f878ab56dd10d790
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 3289b0dd509d1c870917aff6f878ab56dd10d790 test/unit/rules/functions/test_basefn.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/unit/module/jsonschema/test_filter.py b/test/unit/module/jsonschema/test_filter.py
new file mode 100644
index 0000000000..0a012e2d0e
--- /dev/null
+++ b/test/unit/module/jsonschema/test_filter.py
@@ -0,0 +1,50 @@
+"""
+Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
+SPDX-License-Identifier: MIT-0
+"""
+
+from collections import deque
+
+import pytest
+
+from cfnlint.context import Context
+from cfnlint.context.context import Path
+from cfnlint.jsonschema import CfnTemplateValidator
+from cfnlint.jsonschema._filter import FunctionFilter
+
+
+@pytest.fixture(scope="module")
+def filter():
+    filter = FunctionFilter()
+    yield filter
+
+
+@pytest.mark.parametrize(
+    "name,instance,schema,path,expected",
+    [
+        (
+            "Don't validate dynamic references inside of function",
+            "{{resolve:ssm:${AWS::AccountId}/${AWS::Region}/ac}}",
+            {"enum": "Foo"},
+            deque(["Foo", "Test", "Fn::Sub"]),
+            [],
+        ),
+        (
+            "Validate dynamic references",
+            "{{resolve:ssm:secret}}",
+            {"enum": "Foo"},
+            deque(["Foo", "Test"]),
+            [
+                ("{{resolve:ssm:secret}}", {"dynamicReference": {"enum": "Foo"}}),
+            ],
+        ),
+    ],
+)
+def test_filter(name, instance, schema, path, expected, filter):
+    validator = CfnTemplateValidator(
+        context=Context(regions=["us-east-1"], path=Path(path)),
+        schema=schema,
+    )
+    results = list(filter.filter(validator, instance, schema))
+
+    assert results == expected, f"For test {name} got {results!r}"
diff --git a/test/unit/rules/functions/test_basefn.py b/test/unit/rules/functions/test_basefn.py
index f13d0d77d3..a4dc9dabf3 100644
--- a/test/unit/rules/functions/test_basefn.py
+++ b/test/unit/rules/functions/test_basefn.py
@@ -3,11 +3,11 @@
 SPDX-License-Identifier: MIT-0
 """
 
+from collections import deque
+
 import pytest
 
-from cfnlint.context import Context
-from cfnlint.context.context import Parameter, Resource
-from cfnlint.jsonschema import CfnTemplateValidator
+from cfnlint.jsonschema import ValidationError
 from cfnlint.rules.functions._BaseFn import BaseFn
 
 
@@ -17,11 +17,34 @@ def rule():
     yield rule
 
 
-@pytest.fixture(scope="module")
-def validator():
-    context = Context(
-        regions=["us-east-1"],
-        resources={"MyResource": Resource({"Type": "Foo", "Properties": {"A": "B"}})},
-        parameters={"MyParameter": Parameter({"Type": "String"})},
-    )
-    yield CfnTemplateValidator(context=context)
+@pytest.mark.parametrize(
+    "name,instance,schema,expected",
+    [
+        (
+            "Dynamic references are ignored",
+            {"Fn::Sub": "{{resolve:ssm:${AWS::AccountId}/${AWS::Region}/ac}}"},
+            {"enum": ["Foo"]},
+            [],
+        ),
+        ("Everything is fine", {"Fn::Sub": "Foo"}, {"enum": ["Foo"]}, []),
+        (
+            "Standard error",
+            {"Fn::Sub": "Bar"},
+            {"enum": ["Foo"]},
+            [
+                ValidationError(
+                    message=(
+                        "{'Fn::Sub': 'Bar'} is not one of "
+                        "['Foo'] when '' is resolved"
+                    ),
+                    path=deque(["Fn::Sub"]),
+                    validator="",
+                    schema_path=deque(["enum"]),
+                )
+            ],
+        ),
+    ],
+)
+def test_resolve(name, instance, schema, expected, validator, rule):
+    errs = list(rule.resolve(validator, schema, instance, {}))
+    assert errs == expected, f"{name!r} failed and got errors {errs!r}"

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/unit/module/jsonschema/test_filter.py test/unit/rules/functions/test_basefn.py
: '>>>>> End Test Output'
git checkout 3289b0dd509d1c870917aff6f878ab56dd10d790 test/unit/rules/functions/test_basefn.py
