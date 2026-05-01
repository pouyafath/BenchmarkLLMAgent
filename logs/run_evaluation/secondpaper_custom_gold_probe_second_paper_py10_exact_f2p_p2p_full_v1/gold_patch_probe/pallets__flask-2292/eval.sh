#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff fe4003b3c998fde4c9ad8b2340f773f50079ede1
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout fe4003b3c998fde4c9ad8b2340f773f50079ede1 tests/conftest.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/conftest.py b/tests/conftest.py
index 17ff2f3db7..1e1ba0d449 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -18,6 +18,7 @@ def _standard_os_environ():
     """
     mp = monkeypatch.MonkeyPatch()
     out = (
+        (os.environ, "FLASK_ENV_FILE", monkeypatch.notset),
         (os.environ, "FLASK_APP", monkeypatch.notset),
         (os.environ, "FLASK_ENV", monkeypatch.notset),
         (os.environ, "FLASK_DEBUG", monkeypatch.notset),

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/conftest.py
: '>>>>> End Test Output'
git checkout fe4003b3c998fde4c9ad8b2340f773f50079ede1 tests/conftest.py
