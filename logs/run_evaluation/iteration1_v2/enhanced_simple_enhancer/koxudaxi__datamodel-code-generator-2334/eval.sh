#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff ef0c97cb34d753aa831fe9f4e71df399d90d746b
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout ef0c97cb34d753aa831fe9f4e71df399d90d746b tests/main/test_main_general.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/main/test_main_general.py b/tests/main/test_main_general.py
index 4c62c5dfa..d520689c3 100644
--- a/tests/main/test_main_general.py
+++ b/tests/main/test_main_general.py
@@ -14,7 +14,7 @@
     generate,
     snooper_to_methods,
 )
-from datamodel_code_generator.__main__ import Exit, main
+from datamodel_code_generator.__main__ import Config, Exit, main
 
 if TYPE_CHECKING:
     from pytest_mock import MockerFixture
@@ -71,6 +71,19 @@ def test_show_help_when_no_input(mocker: MockerFixture) -> None:
     assert print_help_mock.called
 
 
+def test_no_args_has_default(monkeypatch: pytest.MonkeyPatch) -> None:
+    """
+    No argument should have a default value set because it would override pyproject.toml values.
+
+    Default values are set in __main__.Config class.
+    """
+    namespace = Namespace()
+    monkeypatch.setattr("datamodel_code_generator.__main__.namespace", namespace)
+    main([])
+    for field in Config.get_fields():
+        assert getattr(namespace, field, None) is None
+
+
 @freeze_time("2019-07-26")
 def test_space_and_special_characters_dict() -> None:
     with TemporaryDirectory() as output_dir:

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/main/test_main_general.py
: '>>>>> End Test Output'
git checkout ef0c97cb34d753aa831fe9f4e71df399d90d746b tests/main/test_main_general.py
