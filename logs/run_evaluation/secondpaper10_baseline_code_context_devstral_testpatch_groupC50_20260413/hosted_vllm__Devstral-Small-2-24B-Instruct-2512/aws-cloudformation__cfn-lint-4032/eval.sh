#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 7351d0cf7087d759dd24b06190cb759ec3381da6
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 7351d0cf7087d759dd24b06190cb759ec3381da6 test/unit/rules/resources/iam/test_statement_resources.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/unit/rules/resources/iam/test_statement_resources.py b/test/unit/rules/resources/iam/test_statement_resources.py
index a25d77ee92..64c57f0097 100644
--- a/test/unit/rules/resources/iam/test_statement_resources.py
+++ b/test/unit/rules/resources/iam/test_statement_resources.py
@@ -112,6 +112,13 @@ def template():
             },
             [],
         ),
+        (
+            {
+                "Action": "ec2:CreateTags",
+                "Resource": ["arn:aws:ec2:*::snapshot/*"],
+            },
+            [],
+        ),
         (
             {
                 "Action": "cloudformation:CreateStackSet",

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/unit/rules/resources/iam/test_statement_resources.py
: '>>>>> End Test Output'
git checkout 7351d0cf7087d759dd24b06190cb759ec3381da6 test/unit/rules/resources/iam/test_statement_resources.py
