#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 8112fcc7beb15e1cdc66180c10a3290174866828
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 8112fcc7beb15e1cdc66180c10a3290174866828 .github/workflows/run-tests.yml
git apply -v - <<'EOF_114329324912'
diff --git a/.github/workflows/run-tests.yml b/.github/workflows/run-tests.yml
index 978ab7bd5e..7c7e5fb454 100644
--- a/.github/workflows/run-tests.yml
+++ b/.github/workflows/run-tests.yml
@@ -26,6 +26,7 @@ jobs:
       uses: actions/setup-python@e9aba2c848f5ebd159c070c61ea2c4e2b122355e # v2.3.4
       with:
         python-version: ${{ matrix.python-version }}
+        cache: 'pip'
     - name: Install dependencies
       run: |
         make

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA
: '>>>>> End Test Output'
git checkout 8112fcc7beb15e1cdc66180c10a3290174866828 .github/workflows/run-tests.yml
