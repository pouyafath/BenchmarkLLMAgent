#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff fd830c8f2c31c940dc4d425f1bd366eba36dbd85
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout fd830c8f2c31c940dc4d425f1bd366eba36dbd85 test/fixtures/templates/bad/resources/primary_identifiers.yaml test/unit/rules/resources/test_primary_identifiers.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/fixtures/templates/bad/resources/primary_identifiers.yaml b/test/fixtures/templates/bad/resources/primary_identifiers.yaml
index 3aea9828ca..632c424adf 100644
--- a/test/fixtures/templates/bad/resources/primary_identifiers.yaml
+++ b/test/fixtures/templates/bad/resources/primary_identifiers.yaml
@@ -162,3 +162,42 @@ Resources:
     Type: MyCompany::MODULE
     Properties:
       Attribute2: test
+  Project1:
+    Type: AWS::CodeBuild::Project
+    Properties:
+      Name: myProjectName
+      ServiceRole: arn
+      Artifacts:
+        Type: no_artifacts
+      Environment:
+        Type: LINUX_CONTAINER
+        ComputeType: BUILD_GENERAL1_SMALL
+        Image: aws/codebuild/java:openjdk-8
+        EnvironmentVariables:
+        - Name: varName
+          Type: varType
+          Value: varValue
+      Source:
+        Location: codebuild-demo-test/0123ab9a371ebf0187b0fe5614fbb72c
+        Type: S3
+      TimeoutInMinutes: 10
+
+  Project2:
+    Type: AWS::CodeBuild::Project
+    Properties:
+      Name: myProjectName
+      ServiceRole: arn
+      Artifacts:
+        Type: no_artifacts
+      Environment:
+        Type: LINUX_CONTAINER
+        ComputeType: BUILD_GENERAL1_SMALL
+        Image: aws/codebuild/java:openjdk-8
+        EnvironmentVariables:
+        - Name: varName
+          Type: varType
+          Value: varValue
+      Source:
+        Location: codebuild-demo-test/0123ab9a371ebf0187b0fe5614fbb72c
+        Type: S3
+      TimeoutInMinutes: 10
diff --git a/test/unit/rules/resources/test_primary_identifiers.py b/test/unit/rules/resources/test_primary_identifiers.py
index c49795f20f..54d4d76e95 100644
--- a/test/unit/rules/resources/test_primary_identifiers.py
+++ b/test/unit/rules/resources/test_primary_identifiers.py
@@ -27,5 +27,5 @@ def test_file_positive(self):
     def test_file_negative_alias(self):
         """Test failure"""
         self.helper_file_negative(
-            "test/fixtures/templates/bad/resources/primary_identifiers.yaml", 8
+            "test/fixtures/templates/bad/resources/primary_identifiers.yaml", 10
         )

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/unit/rules/resources/test_primary_identifiers.py
: '>>>>> End Test Output'
git checkout fd830c8f2c31c940dc4d425f1bd366eba36dbd85 test/fixtures/templates/bad/resources/primary_identifiers.yaml test/unit/rules/resources/test_primary_identifiers.py
