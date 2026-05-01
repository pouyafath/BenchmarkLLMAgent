#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff f6fceb1b568bf08f8244cf123b71cf32af8bec33
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout f6fceb1b568bf08f8244cf123b71cf32af8bec33 test/components/embedders/test_azure_document_embedder.py test/components/embedders/test_openai_document_embedder.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/components/embedders/test_azure_document_embedder.py b/test/components/embedders/test_azure_document_embedder.py
index accc8d254e..52fa72355e 100644
--- a/test/components/embedders/test_azure_document_embedder.py
+++ b/test/components/embedders/test_azure_document_embedder.py
@@ -7,6 +7,7 @@
 
 from haystack.utils.auth import Secret
 import pytest
+import httpx
 
 from haystack import Document
 from haystack.components.embedders import AzureOpenAIDocumentEmbedder
@@ -19,6 +20,7 @@ def test_init_default(self, monkeypatch):
         monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fake-api-key")
         embedder = AzureOpenAIDocumentEmbedder(azure_endpoint="https://example-resource.azure.openai.com/")
         assert embedder.azure_deployment == "text-embedding-ada-002"
+        assert embedder.model == "text-embedding-ada-002"
         assert embedder.dimensions is None
         assert embedder.organization is None
         assert embedder.prefix == ""
@@ -38,6 +40,7 @@ def test_init_with_0_max_retries(self, monkeypatch):
             azure_endpoint="https://example-resource.azure.openai.com/", max_retries=0
         )
         assert embedder.azure_deployment == "text-embedding-ada-002"
+        assert embedder.model == "text-embedding-ada-002"
         assert embedder.dimensions is None
         assert embedder.organization is None
         assert embedder.prefix == ""
@@ -203,7 +206,7 @@ def test_embed_batch_handles_exceptions_gracefully(self, caplog):
         fake_texts_to_embed = {"1": "text1", "2": "text2"}
 
         with patch.object(
-            embedder._client.embeddings,
+            embedder.client.embeddings,
             "create",
             side_effect=APIError(message="Mocked error", request=Mock(), body=None),
         ):
@@ -212,6 +215,21 @@ def test_embed_batch_handles_exceptions_gracefully(self, caplog):
         assert len(caplog.records) == 1
         assert "Failed embedding of documents 1, 2 caused by Mocked error" in caplog.text
 
+    def test_init_http_client(self, monkeypatch):
+        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fake-api-key")
+        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
+
+        embedder = AzureOpenAIDocumentEmbedder()
+        client = embedder._init_http_client()
+        assert client is None
+
+        embedder.http_client_kwargs = {"proxy": "http://example.com:3128"}
+        client = embedder._init_http_client(async_client=False)
+        assert isinstance(client, httpx.Client)
+
+        client = embedder._init_http_client(async_client=True)
+        assert isinstance(client, httpx.AsyncClient)
+
     def test_http_client_kwargs_type_validation(self, monkeypatch):
         monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fake-api-key")
         monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
@@ -257,4 +275,7 @@ def test_run(self):
             assert isinstance(doc.embedding, list)
             assert len(doc.embedding) == 1536
             assert all(isinstance(x, float) for x in doc.embedding)
-        assert metadata == {"model": "text-embedding-ada-002", "usage": {"prompt_tokens": 15, "total_tokens": 15}}
+
+        assert metadata["usage"]["prompt_tokens"] == 15
+        assert metadata["usage"]["total_tokens"] == 15
+        assert "ada" in metadata["model"]
diff --git a/test/components/embedders/test_openai_document_embedder.py b/test/components/embedders/test_openai_document_embedder.py
index 1e85018732..77c5259efe 100644
--- a/test/components/embedders/test_openai_document_embedder.py
+++ b/test/components/embedders/test_openai_document_embedder.py
@@ -167,13 +167,12 @@ def test_prepare_texts_to_embed_w_metadata(self):
 
         prepared_texts = embedder._prepare_texts_to_embed(documents)
 
-        # note that newline is replaced by space
         assert prepared_texts == {
-            "0": "meta_value 0 | document number 0: content",
-            "1": "meta_value 1 | document number 1: content",
-            "2": "meta_value 2 | document number 2: content",
-            "3": "meta_value 3 | document number 3: content",
-            "4": "meta_value 4 | document number 4: content",
+            "0": "meta_value 0 | document number 0:\ncontent",
+            "1": "meta_value 1 | document number 1:\ncontent",
+            "2": "meta_value 2 | document number 2:\ncontent",
+            "3": "meta_value 3 | document number 3:\ncontent",
+            "4": "meta_value 4 | document number 4:\ncontent",
         }
 
     def test_prepare_texts_to_embed_w_suffix(self):

EOF_114329324912
: '>>>>> Start Test Output'
pytest --cov-report xml:coverage.xml --cov="haystack" -m "not integration" -rA test test/components/embedders/test_azure_document_embedder.py test/components/embedders/test_openai_document_embedder.py
: '>>>>> End Test Output'
git checkout f6fceb1b568bf08f8244cf123b71cf32af8bec33 test/components/embedders/test_azure_document_embedder.py test/components/embedders/test_openai_document_embedder.py
