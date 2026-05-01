#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 7ddd087bdace33a0c6f1420ac9f092e66bb0b7ed
source /opt/miniconda3/bin/activate
conda activate testbed
cd lib && python -m pip install -e '.[testing]' || cd lib && python -m pip install -e .
git checkout 7ddd087bdace33a0c6f1420ac9f092e66bb0b7ed lib/tests/streamlit/dataframe_util_test.py
git apply -v - <<'EOF_114329324912'
diff --git a/lib/tests/streamlit/dataframe_util_test.py b/lib/tests/streamlit/dataframe_util_test.py
index abc8a1366..053b32be2 100644
--- a/lib/tests/streamlit/dataframe_util_test.py
+++ b/lib/tests/streamlit/dataframe_util_test.py
@@ -806,6 +806,22 @@ class DataframeUtilTest(unittest.TestCase):
             df, dataframe_util.DataFormat.KEY_VALUE_DICT
         ) == {0: None, 1: None, 2: None, 3: None}
 
+    def test_convert_df_preserves_none_after_row_assignment(self):
+        """Regression test for https://github.com/streamlit/streamlit/issues/14693.
+
+        In pandas 3.0+, infer_objects() converts None back to np.nan. This test
+        verifies that None values assigned via df.loc[] are preserved as None.
+        """
+        # Simulate how data_editor adds new rows
+        df = pd.DataFrame([{"Text": "Row 1"}])
+        df.loc[1] = {"Text": None}
+
+        result = dataframe_util.convert_pandas_df_to_data_format(
+            df, dataframe_util.DataFormat.LIST_OF_RECORDS
+        )
+        # None must be preserved, not converted to np.nan
+        assert result == [{"Text": "Row 1"}, {"Text": None}]
+
     def test_convert_anything_to_sequence_object_is_indexable(self):
         l1 = ["a", "b", "c"]
         l2 = dataframe_util.convert_anything_to_list(l1)

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA lib/tests/streamlit/dataframe_util_test.py
: '>>>>> End Test Output'
git checkout 7ddd087bdace33a0c6f1420ac9f092e66bb0b7ed lib/tests/streamlit/dataframe_util_test.py
