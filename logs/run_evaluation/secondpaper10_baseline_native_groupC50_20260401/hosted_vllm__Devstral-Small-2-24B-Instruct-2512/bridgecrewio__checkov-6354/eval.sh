#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff a902244a6743eff627eaf485e01ae6ae0a9f24d5
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout a902244a6743eff627eaf485e01ae6ae0a9f24d5 tests/terraform/checks/module/generic/example_RevisionVersionTag/main.tf tests/terraform/checks/module/generic/test_RevisionVersionTag.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/terraform/checks/module/generic/example_RevisionVersionTag/main.tf b/tests/terraform/checks/module/generic/example_RevisionVersionTag/main.tf
index f28d74aa52..74862c9a26 100644
--- a/tests/terraform/checks/module/generic/example_RevisionVersionTag/main.tf
+++ b/tests/terraform/checks/module/generic/example_RevisionVersionTag/main.tf
@@ -49,14 +49,15 @@ module "shallow_clone" {
   source = "git::https://github.com/terraform-aws-modules/terraform-aws-vpc.git?depth=1&ref=v1.2.0"
 }
 
+module "module_with_version" {
+  source  = "terraform-aws-modules/iam/aws//modules/iam-github-oidc-role"
+  version = "5.39.1"
+}
+
 # fail
 
-module "tf_registry" {
+module "tf_registry_no_version" {
   source  = "terraform-aws-modules/cloudwatch/aws//modules/log-group"
-  version = "4.3.0"
-
-  name              = "normal"
-  retention_in_days = 120
 }
 
 module "looks_like_a_branch" {
@@ -78,6 +79,22 @@ module "looks_like_a_branch" {
   }
 }
 
+module "github_module" {
+  source = "github.com/hashicorp/example"
+}
+
+module "bitbucket_module" {
+  source = "bitbucket.org/hashicorp/terraform-consul-aws"
+}
+
+module "github_ssh_module" {
+  source = "git@github.com:hashicorp/example.git"
+}
+
+module "generic_git_module" {
+  source = "git::https://example.com/vpc.git"
+}
+
 # unknown
 
 module "relative" {
diff --git a/tests/terraform/checks/module/generic/test_RevisionVersionTag.py b/tests/terraform/checks/module/generic/test_RevisionVersionTag.py
index 505fa57904..ec9031f955 100644
--- a/tests/terraform/checks/module/generic/test_RevisionVersionTag.py
+++ b/tests/terraform/checks/module/generic/test_RevisionVersionTag.py
@@ -21,11 +21,17 @@ def test(self):
             "hash",
             "sub_dir_hash",
             "tag",
-            "shallow_clone"
+            "shallow_clone",
+            "module_with_version"
         }
+
         failing_resources = {
             "looks_like_a_branch",
-            "tf_registry",
+            "tf_registry_no_version",
+            "generic_git_module",
+            "bitbucket_module",
+            "github_ssh_module",
+            "github_module"
         }
 
         passed_check_resources = {c.resource for c in report.passed_checks}

EOF_114329324912
: '>>>>> Start Test Output'
pipenv run pytest -rA tests/terraform/checks/module/generic/example_RevisionVersionTag/main.tf tests/terraform/checks/module/generic/test_RevisionVersionTag.py
: '>>>>> End Test Output'
git checkout a902244a6743eff627eaf485e01ae6ae0a9f24d5 tests/terraform/checks/module/generic/example_RevisionVersionTag/main.tf tests/terraform/checks/module/generic/test_RevisionVersionTag.py
