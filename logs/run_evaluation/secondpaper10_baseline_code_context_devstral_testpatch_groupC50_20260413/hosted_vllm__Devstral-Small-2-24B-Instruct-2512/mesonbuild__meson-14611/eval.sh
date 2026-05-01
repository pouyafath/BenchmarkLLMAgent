#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 5463c644c86167fc8b4c6a9c389aaa6bd8b116ec
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 5463c644c86167fc8b4c6a9c389aaa6bd8b116ec unittests/optiontests.py
git apply -v - <<'EOF_114329324912'
diff --git a/unittests/optiontests.py b/unittests/optiontests.py
index 0bdd7dc4550a..5758a2d5c8ac 100644
--- a/unittests/optiontests.py
+++ b/unittests/optiontests.py
@@ -35,6 +35,22 @@ def test_toplevel_project(self):
         optstore.initialize_from_top_level_project_call({OptionKey('someoption'): new_value}, {}, {})
         self.assertEqual(optstore.get_value_for(k), new_value)
 
+    def test_machine_vs_project(self):
+        optstore = OptionStore(False)
+        name = 'backend'
+        default_value = 'ninja'
+        proj_value = 'xcode'
+        mfile_value = 'vs2010'
+        k = OptionKey(name)
+        prefix = UserStringOption('prefix', 'This is needed by OptionStore', '/usr')
+        optstore.add_system_option('prefix', prefix)
+        vo = UserStringOption(k.name, 'You know what this is', default_value)
+        optstore.add_system_option(k.name, vo)
+        self.assertEqual(optstore.get_value_for(k), default_value)
+        optstore.initialize_from_top_level_project_call({OptionKey(name): proj_value}, {},
+                                                        {OptionKey(name): mfile_value})
+        self.assertEqual(optstore.get_value_for(k), mfile_value)
+
     def test_subproject_system_option(self):
         """Test that subproject system options get their default value from the global
            option (e.g. "sub:b_lto" can be initialized from "b_lto")."""

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA unittests/optiontests.py
: '>>>>> End Test Output'
git checkout 5463c644c86167fc8b4c6a9c389aaa6bd8b116ec unittests/optiontests.py
