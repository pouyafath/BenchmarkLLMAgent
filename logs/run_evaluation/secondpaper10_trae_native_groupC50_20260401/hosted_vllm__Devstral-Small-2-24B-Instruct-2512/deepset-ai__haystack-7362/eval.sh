#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 19d3f39e757ee3488b7e5f581aa970de432a3019
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 19d3f39e757ee3488b7e5f581aa970de432a3019 test/components/converters/test_pypdf_to_document.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/components/converters/test_pypdf_to_document.py b/test/components/converters/test_pypdf_to_document.py
index 330ed9a317..6f07669f80 100644
--- a/test/components/converters/test_pypdf_to_document.py
+++ b/test/components/converters/test_pypdf_to_document.py
@@ -1,9 +1,10 @@
 import logging
 from unittest.mock import patch
+
 import pytest
 
-from haystack import Document
-from haystack.components.converters.pypdf import PyPDFToDocument, CONVERTERS_REGISTRY
+from haystack import Document, default_from_dict, default_to_dict
+from haystack.components.converters.pypdf import CONVERTERS_REGISTRY, DefaultConverter, PyPDFToDocument
 from haystack.dataclasses import ByteStream
 
 
@@ -14,13 +15,46 @@ def pypdf_converter():
 
 class TestPyPDFToDocument:
     def test_init(self, pypdf_converter):
-        assert pypdf_converter.converter_name == "default"
-        assert hasattr(pypdf_converter, "_converter")
+        assert isinstance(pypdf_converter.converter, DefaultConverter)
+        assert pypdf_converter.converter_name is None
 
     def test_init_fail_nonexisting_converter(self):
         with pytest.raises(ValueError):
             PyPDFToDocument(converter_name="non_existing_converter")
 
+    def test_to_dict(self, pypdf_converter):
+        data = pypdf_converter.to_dict()
+        assert data == {
+            "type": "haystack.components.converters.pypdf.PyPDFToDocument",
+            "init_parameters": {
+                "converter": {"type": "haystack.components.converters.pypdf.DefaultConverter", "init_parameters": {}},
+                "converter_name": None,
+            },
+        }
+
+    def test_from_dict(self):
+        data = {
+            "type": "haystack.components.converters.pypdf.PyPDFToDocument",
+            "init_parameters": {
+                "converter": {"type": "haystack.components.converters.pypdf.DefaultConverter", "init_parameters": {}}
+            },
+        }
+        instance = PyPDFToDocument.from_dict(data)
+        assert isinstance(instance, PyPDFToDocument)
+        assert isinstance(instance.converter, DefaultConverter)
+        assert instance.converter_name is None
+
+    def test_from_dict_with_converter_name(self):
+        data = {
+            "type": "haystack.components.converters.pypdf.PyPDFToDocument",
+            "init_parameters": {"converter_name": "default"},
+        }
+
+        instance = PyPDFToDocument.from_dict(data)
+        assert isinstance(instance, PyPDFToDocument)
+        assert isinstance(instance.converter, DefaultConverter)
+        assert instance.converter_name == "default"
+
     @pytest.mark.integration
     def test_run(self, test_files_path, pypdf_converter):
         """
@@ -86,6 +120,30 @@ def test_custom_converter(self, test_files_path):
 
         paths = [test_files_path / "pdf" / "sample_pdf_1.pdf"]
 
+        class MyCustomConverter:
+            def convert(self, reader: PdfReader) -> Document:
+                return Document(content="I don't care about converting given pdfs, I always return this")
+
+            def to_dict(self):
+                return default_to_dict(self)
+
+            @classmethod
+            def from_dict(cls, data):
+                return default_from_dict(cls, data)
+
+        component = PyPDFToDocument(converter=MyCustomConverter())
+        output = component.run(sources=paths)
+        docs = output["documents"]
+        assert len(docs) == 1
+        assert "ReAct" not in docs[0].content
+        assert "I don't care about converting given pdfs, I always return this" in docs[0].content
+
+    @pytest.mark.integration
+    def test_custom_converter_deprecated(self, test_files_path):
+        from pypdf import PdfReader
+
+        paths = [test_files_path / "pdf" / "sample_pdf_1.pdf"]
+
         class MyCustomConverter:
             def convert(self, reader: PdfReader) -> Document:
                 return Document(content="I don't care about converting given pdfs, I always return this")

EOF_114329324912
: '>>>>> Start Test Output'
pytest --cov-report xml:coverage.xml --cov="haystack" -m "not integration" -rA test test/components/converters/test_pypdf_to_document.py
: '>>>>> End Test Output'
git checkout 19d3f39e757ee3488b7e5f581aa970de432a3019 test/components/converters/test_pypdf_to_document.py
