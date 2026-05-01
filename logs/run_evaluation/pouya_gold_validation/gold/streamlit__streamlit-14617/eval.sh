#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 406f31edc94703e22907a1cfd36c219508b7407b
source /opt/miniconda3/bin/activate
conda activate testbed
cd lib && python -m pip install -e '.[testing]' || cd lib && python -m pip install -e .
git checkout 406f31edc94703e22907a1cfd36c219508b7407b lib/tests/streamlit/components_test.py lib/tests/streamlit/dataframe_util_test.py
git apply -v - <<'EOF_114329324912'
diff --git a/lib/tests/streamlit/components_test.py b/lib/tests/streamlit/components_test.py
index de2e02376..39b6b44e8 100644
--- a/lib/tests/streamlit/components_test.py
+++ b/lib/tests/streamlit/components_test.py
@@ -38,7 +38,10 @@ from streamlit.components.v1.component_registry import (
     _get_module_name,
 )
 from streamlit.components.v1.custom_component import CustomComponent
-from streamlit.dataframe_util import is_pyarrow_version_less_than
+from streamlit.dataframe_util import (
+    is_pandas_version_less_than,
+    is_pyarrow_version_less_than,
+)
 from streamlit.errors import DuplicateWidgetID, StreamlitAPIException
 from streamlit.proto.Components_pb2 import ArrowTable as ArrowTableProto
 from streamlit.proto.Components_pb2 import SpecialArg
@@ -766,6 +769,101 @@ class ComponentArrowTest(unittest.TestCase):
         assert len(proto.data) > 0
         assert len(proto.columns) > 0
 
+    @pytest.mark.skipif(
+        is_pandas_version_less_than("3.0.0"),
+        reason="Downcasting is only enabled for pandas >= 3.0",
+    )
+    def test_marshall_downcasts_large_string(self):
+        """Test that large_string columns are downcast to string for custom components."""
+        import pyarrow as pa
+
+        df = pd.DataFrame({"col": pd.array(["a", "b", "c"], dtype="string[pyarrow]")})
+
+        proto = ArrowTableProto()
+        component_arrow.marshall(proto, df)
+
+        result_table = pa.ipc.open_stream(proto.data).read_all()
+        for field in result_table.schema:
+            assert field.type == pa.string(), f"Expected string type, got {field.type}"
+
+    @pytest.mark.skipif(
+        is_pandas_version_less_than("3.0.0"),
+        reason="Downcasting is only enabled for pandas >= 3.0",
+    )
+    def test_marshall_downcasts_large_binary(self):
+        """Test that large_binary columns are downcast to binary for custom components."""
+        import pyarrow as pa
+
+        table = pa.table({"col": pa.array([b"x", b"y", b"z"], type=pa.large_binary())})
+        df = table.to_pandas()
+
+        proto = ArrowTableProto()
+        component_arrow.marshall(proto, df)
+
+        result_table = pa.ipc.open_stream(proto.data).read_all()
+        for field in result_table.schema:
+            if field.name == "col":
+                assert field.type == pa.binary(), (
+                    f"Expected binary type, got {field.type}"
+                )
+
+    @pytest.mark.skipif(
+        is_pandas_version_less_than("3.0.0"),
+        reason="Downcasting is only enabled for pandas >= 3.0",
+    )
+    def test_marshall_downcasts_large_list(self):
+        """Test that large_list columns are downcast to list for custom components."""
+        import pyarrow as pa
+
+        large_list_type = pa.large_list(pa.int64())
+        table = pa.table({"col": pa.array([[1, 2], [3]], type=large_list_type)})
+        df = table.to_pandas()
+
+        proto = ArrowTableProto()
+        component_arrow.marshall(proto, df)
+
+        result_table = pa.ipc.open_stream(proto.data).read_all()
+        for field in result_table.schema:
+            if field.name == "col":
+                assert field.type == pa.list_(pa.int64()), (
+                    f"Expected list type, got {field.type}"
+                )
+
+    @pytest.mark.skipif(
+        is_pandas_version_less_than("3.0.0"),
+        reason="Downcasting is only enabled for pandas >= 3.0",
+    )
+    def test_marshall_downcasts_nested_large_list_with_large_string(self):
+        """Test that large_list(large_string()) is recursively downcast to list(string)."""
+        import pyarrow as pa
+
+        nested_type = pa.large_list(pa.large_string())
+        table = pa.table({"col": pa.array([["a", "b"], ["c"]], type=nested_type)})
+        df = table.to_pandas()
+
+        proto = ArrowTableProto()
+        component_arrow.marshall(proto, df)
+
+        result_table = pa.ipc.open_stream(proto.data).read_all()
+        col_field = result_table.schema.field("col")
+        assert col_field.type == pa.list_(pa.string()), (
+            f"Expected list(string), got {col_field.type}"
+        )
+
+    def test_marshall_preserves_non_large_types(self):
+        """Test that non-large types are not modified during marshalling."""
+        import pyarrow as pa
+
+        df = pd.DataFrame({"int_col": [1, 2, 3], "float_col": [1.0, 2.0, 3.0]})
+
+        proto = ArrowTableProto()
+        component_arrow.marshall(proto, df)
+
+        result_table = pa.ipc.open_stream(proto.data).read_all()
+        type_names = {field.name: field.type for field in result_table.schema}
+        assert pa.types.is_integer(type_names["int_col"])
+        assert pa.types.is_floating(type_names["float_col"])
+
 
 @pytest.mark.parametrize(
     ("input_value", "expected"),
diff --git a/lib/tests/streamlit/dataframe_util_test.py b/lib/tests/streamlit/dataframe_util_test.py
index 02c21ec9a..590e99b13 100644
--- a/lib/tests/streamlit/dataframe_util_test.py
+++ b/lib/tests/streamlit/dataframe_util_test.py
@@ -60,6 +60,33 @@ class DataframeUtilTest(unittest.TestCase):
         except Exception as ex:
             self.fail(f"Converting dtype dataframes to Arrow should not fail: {ex}")
 
+    def test_convert_pandas_df_to_arrow_bytes_downcasts_large_types(self):
+        """Test that downcast_large_types converts large Arrow types to standard ones."""
+        import pyarrow as pa
+
+        df = pd.DataFrame(
+            {"col": pd.array(["hello", "world"], dtype="string[pyarrow]")}
+        )
+        result_bytes = dataframe_util.convert_pandas_df_to_arrow_bytes(
+            df, downcast_large_types=True
+        )
+        result_table = pa.ipc.open_stream(result_bytes).read_all()
+        assert result_table.schema.field("col").type == pa.string()
+
+    def test_convert_pandas_df_to_arrow_bytes_no_downcast_by_default(self):
+        """Test that large types are preserved when downcast_large_types is False."""
+        import pyarrow as pa
+
+        df = pd.DataFrame(
+            {"col": pd.array(["hello", "world"], dtype="string[pyarrow]")}
+        )
+        result_bytes = dataframe_util.convert_pandas_df_to_arrow_bytes(df)
+        result_table = pa.ipc.open_stream(result_bytes).read_all()
+        # The default ArrowDtype("string[pyarrow]") uses large_string on
+        # pandas >= 3.0. Without downcasting the type should be preserved.
+        col_type = result_table.schema.field("col").type
+        assert col_type in {pa.string(), pa.large_string()}
+
     @parameterized.expand(
         SHARED_TEST_CASES,
     )

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA lib/tests/streamlit/components_test.py lib/tests/streamlit/dataframe_util_test.py
: '>>>>> End Test Output'
git checkout 406f31edc94703e22907a1cfd36c219508b7407b lib/tests/streamlit/components_test.py lib/tests/streamlit/dataframe_util_test.py
