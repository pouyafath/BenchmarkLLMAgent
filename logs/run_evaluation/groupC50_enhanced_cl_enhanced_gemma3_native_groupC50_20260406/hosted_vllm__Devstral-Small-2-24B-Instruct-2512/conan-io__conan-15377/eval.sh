#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff c361744fa45be644670a8bf476d2bafccafe7f16
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout c361744fa45be644670a8bf476d2bafccafe7f16 conans/test/functional/tools/scm/test_git.py
git apply -v - <<'EOF_114329324912'
diff --git a/conans/test/functional/tools/scm/test_git.py b/conans/test/functional/tools/scm/test_git.py
index af096464243..3a47bd31b21 100644
--- a/conans/test/functional/tools/scm/test_git.py
+++ b/conans/test/functional/tools/scm/test_git.py
@@ -481,7 +481,7 @@ class TestGitBasicSCMFlow:
     - export() stores it in conandata.yml
     - source() recovers the info from conandata.yml and clones it
     """
-    conanfile = textwrap.dedent("""
+    conanfile_full = textwrap.dedent("""
         import os
         from conan import ConanFile
         from conan.tools.scm import Git
@@ -513,10 +513,40 @@ def build(self):
                 self.output.info("MYCMAKE-BUILD: {}".format(load(self, cmake)))
                 self.output.info("MYFILE-BUILD: {}".format(load(self, file_h)))
         """)
+    conanfile_scm = textwrap.dedent("""
+        import os
+        from conan import ConanFile
+        from conan.tools.scm import Git
+        from conan.tools.files import load, trim_conandata
 
-    def test_full_scm(self):
+        class Pkg(ConanFile):
+            name = "pkg"
+            version = "0.1"
+
+            def export(self):
+                Git(self).coordinates_to_conandata()
+                trim_conandata(self)  # to test it does not affect
+
+            def layout(self):
+                self.folders.source = "."
+
+            def source(self):
+                Git(self).checkout_from_conandata_coordinates()
+                self.output.info("MYCMAKE: {}".format(load(self, "CMakeLists.txt")))
+                self.output.info("MYFILE: {}".format(load(self, "src/myfile.h")))
+
+            def build(self):
+                cmake = os.path.join(self.source_folder, "CMakeLists.txt")
+                file_h = os.path.join(self.source_folder, "src/myfile.h")
+                self.output.info("MYCMAKE-BUILD: {}".format(load(self, cmake)))
+                self.output.info("MYFILE-BUILD: {}".format(load(self, file_h)))
+        """)
+
+    @pytest.mark.parametrize("conanfile_scm", [False, True])
+    def test_full_scm(self, conanfile_scm):
+        conanfile = self.conanfile_scm if conanfile_scm else self.conanfile_full
         folder = os.path.join(temp_folder(), "myrepo")
-        url, commit = create_local_git_repo(files={"conanfile.py": self.conanfile,
+        url, commit = create_local_git_repo(files={"conanfile.py": conanfile,
                                                    "src/myfile.h": "myheader!",
                                                    "CMakeLists.txt": "mycmake"}, folder=folder)
 
@@ -543,15 +573,17 @@ def test_full_scm(self):
         assert "conanfile.py (pkg/0.1): MYCMAKE-BUILD: mycmake" in c.out
         assert "conanfile.py (pkg/0.1): MYFILE-BUILD: myheader!" in c.out
 
-    def test_branch_flow(self):
+    @pytest.mark.parametrize("conanfile_scm", [False, True])
+    def test_branch_flow(self, conanfile_scm):
         """ Testing that when a user creates a branch, and pushes a commit,
         the package can still be built from sources, and get_url_and_commit() captures the
         remote URL and not the local
         """
+        conanfile = self.conanfile_scm if conanfile_scm else self.conanfile_full
         url = git_create_bare_repo()
         c = TestClient(default_server_user=True)
         c.run_command('git clone "{}" .'.format(url))
-        c.save({"conanfile.py": self.conanfile,
+        c.save({"conanfile.py": conanfile,
                 "src/myfile.h": "myheader!",
                 "CMakeLists.txt": "mycmake"})
         c.run_command("git checkout -b mybranch")

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA conans/test/functional/tools/scm/test_git.py
: '>>>>> End Test Output'
git checkout c361744fa45be644670a8bf476d2bafccafe7f16 conans/test/functional/tools/scm/test_git.py
