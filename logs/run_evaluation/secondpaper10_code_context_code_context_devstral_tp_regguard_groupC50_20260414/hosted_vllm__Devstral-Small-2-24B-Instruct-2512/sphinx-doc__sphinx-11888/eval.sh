#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 882a174e48a4dfd22d4fab4b2e3b74f091b3f98e
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 882a174e48a4dfd22d4fab4b2e3b74f091b3f98e tests/test_search.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_search.py b/tests/test_search.py
index d4bbef5b3b3..f13c9a2468e 100644
--- a/tests/test_search.py
+++ b/tests/test_search.py
@@ -157,8 +157,8 @@ def test_IndexBuilder():
     index = IndexBuilder(env, 'en', {}, None)
     index.feed('docname1_1', 'filename1_1', 'title1_1', doc)
     index.feed('docname1_2', 'filename1_2', 'title1_2', doc)
-    index.feed('docname2_1', 'filename2_1', 'title2_1', doc)
     index.feed('docname2_2', 'filename2_2', 'title2_2', doc)
+    index.feed('docname2_1', 'filename2_1', 'title2_1', doc)
     assert index._titles == {'docname1_1': 'title1_1', 'docname1_2': 'title1_2',
                              'docname2_1': 'title2_1', 'docname2_2': 'title2_2'}
     assert index._filenames == {'docname1_1': 'filename1_1', 'docname1_2': 'filename1_2',

EOF_114329324912
: '>>>>> Start Test Output'
python -X dev -X warn_default_encoding -m pytest -v -rA tests/test_search.py
: '>>>>> End Test Output'
git checkout 882a174e48a4dfd22d4fab4b2e3b74f091b3f98e tests/test_search.py
