#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 0d4a3b9b940b6749ec1e4b89ef63572d8bc2f896
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[dev]'
git checkout 0d4a3b9b940b6749ec1e4b89ef63572d8bc2f896 tests/cross_encoder/test_cross_encoder.py tests/models/test_router.py tests/sparse_encoder/models/test_sparse_static_embedding.py tests/sparse_encoder/test_sparse_encoder.py tests/test_sentence_transformer.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/cross_encoder/test_cross_encoder.py b/tests/cross_encoder/test_cross_encoder.py
index 5437961..f8d5969 100644
--- a/tests/cross_encoder/test_cross_encoder.py
+++ b/tests/cross_encoder/test_cross_encoder.py
@@ -599,3 +599,25 @@ def test_bge_reranker_max_length():
     model.max_length = 256
     assert model.max_length == 256
     assert model.tokenizer.model_max_length == 256
+
+
+def test_predict_with_dataset_column(reranker_bert_tiny_model: CrossEncoder) -> None:
+    """Test that predict can handle a dataset column as input."""
+    model = reranker_bert_tiny_model
+    from datasets import Dataset
+
+    # Create a simple dataset with a text column
+    dataset = Dataset.from_dict(
+        {
+            "text": [
+                ["This is the start of a pair.", "And this the end."],
+                ["This is a second pair.", "And this the end of the second pair."],
+            ]
+        }
+    )
+
+    # Encode the dataset column
+    embeddings = model.predict(dataset["text"], convert_to_tensor=True)
+
+    # Check the shape of the embeddings
+    assert embeddings.shape == (2,)
diff --git a/tests/models/test_router.py b/tests/models/test_router.py
index 4818dd5..91e0684 100644
--- a/tests/models/test_router.py
+++ b/tests/models/test_router.py
@@ -9,6 +9,7 @@ from pathlib import Path
 
 import pytest
 import torch
+from torch import nn
 
 from sentence_transformers import (
     SentenceTransformer,
@@ -53,8 +54,8 @@ class InvertMockModule(MockModule):
         return features
 
 
-# Create a custom dict subclass to track access
-class TaskTypesTrackingDict(dict):
+# Create a custom ModuleDict subclass to track access
+class TaskTypesTrackingModuleDict(nn.ModuleDict):
     def __init__(self, *args, **kwargs):
         super().__init__(*args, **kwargs)
         self.tasks = []
@@ -115,7 +116,12 @@ def test_router_init_basic():
 
     router = Router({"query": [query_module], "document": [doc_module]})
 
-    assert router.sub_modules == {"query": [query_module], "document": [doc_module]}
+    assert isinstance(router.sub_modules, nn.ModuleDict)
+    assert list(router.sub_modules.keys()) == ["query", "document"]
+    assert isinstance(router.sub_modules["query"], nn.Sequential)
+    assert router.sub_modules["query"][0] == query_module
+    assert isinstance(router.sub_modules["document"], nn.Sequential)
+    assert router.sub_modules["document"][0] == doc_module
     assert router.default_route == "query"  # First key with allow_empty_key=True
 
     router = Router(
@@ -125,7 +131,12 @@ def test_router_init_basic():
         }
     )
 
-    assert router.sub_modules == {"query": [query_module], "document": [doc_module]}
+    assert isinstance(router.sub_modules, nn.ModuleDict)
+    assert list(router.sub_modules.keys()) == ["document", "query"]
+    assert isinstance(router.sub_modules["document"], nn.Sequential)
+    assert router.sub_modules["document"][0] == doc_module
+    assert isinstance(router.sub_modules["query"], nn.Sequential)
+    assert router.sub_modules["query"][0] == query_module
     assert router.default_route == "document"  # First key with allow_empty_key=True
 
 
@@ -165,8 +176,8 @@ def test_router_init_multiple_modules_per_route():
 
     router = Router({"query": [module1, module2], "document": [module3]})
 
-    assert router.sub_modules["query"] == [module1, module2]
-    assert router.sub_modules["document"] == [module3]
+    assert list(router.sub_modules["query"].children()) == [module1, module2]
+    assert list(router.sub_modules["document"].children()) == [module3]
 
 
 def test_router_encode(static_embedding_model):
@@ -175,7 +186,7 @@ def test_router_encode(static_embedding_model):
     router = Router({"query": [static_embedding_model], "document": [static_embedding_model]})
 
     # Replace the dictionary with our tracking version
-    tracking_dict = TaskTypesTrackingDict(router.sub_modules)
+    tracking_dict = TaskTypesTrackingModuleDict(router.sub_modules)
     router.sub_modules = tracking_dict
 
     model = SentenceTransformer(modules=[router])
@@ -233,7 +244,7 @@ def test_router_backwards_compatibility(static_embedding_model):
     asym_model = Asym({"query": [static_embedding_model], "document": [static_embedding_model]})
 
     # Replace the dictionary with our tracking version
-    tracking_dict = TaskTypesTrackingDict(asym_model.sub_modules)
+    tracking_dict = TaskTypesTrackingModuleDict(asym_model.sub_modules)
     asym_model.sub_modules = tracking_dict
 
     model = SentenceTransformer(modules=[asym_model])
@@ -391,10 +402,12 @@ def test_router_save_load_with_multiple_modules_per_route(static_embedding_model
     assert loaded_model.get_sentence_embedding_dimension() == 128
 
     # If we swap the order of the routes, the new first route should be used
-    loaded_router.sub_modules = {
-        "document": loaded_router.sub_modules["document"],
-        "query": loaded_router.sub_modules["query"],
-    }
+    loaded_router.sub_modules = nn.ModuleDict(
+        {
+            "document": loaded_router.sub_modules["document"],
+            "query": loaded_router.sub_modules["query"],
+        }
+    )
     assert loaded_model.get_sentence_embedding_dimension() == 768
 
 
@@ -406,7 +419,7 @@ def test_router_with_trainer(static_embedding_model: StaticEmbedding, tmp_path:
     model = SentenceTransformer(modules=[router])
     model.model_card_data.generate_widget_examples = False  # Disable widget examples generation for testing
 
-    tracking_dict = TaskTypesTrackingDict(router.sub_modules)
+    tracking_dict = TaskTypesTrackingModuleDict(router.sub_modules)
     router.sub_modules = tracking_dict
 
     train_dataset = Dataset.from_dict(
@@ -622,7 +635,7 @@ def test_router_as_middle_module(static_embedding_model: StaticEmbedding, tmp_pa
     model = SentenceTransformer(modules=[static_embedding_model, router, normalize])
 
     # Create tracking dicts to monitor module usage
-    tracking_dict = TaskTypesTrackingDict(router.sub_modules)
+    tracking_dict = TaskTypesTrackingModuleDict(router.sub_modules)
     router.sub_modules = tracking_dict
 
     # Test texts
diff --git a/tests/sparse_encoder/models/test_sparse_static_embedding.py b/tests/sparse_encoder/models/test_sparse_static_embedding.py
index 7f7d98d..65901ef 100644
--- a/tests/sparse_encoder/models/test_sparse_static_embedding.py
+++ b/tests/sparse_encoder/models/test_sparse_static_embedding.py
@@ -31,6 +31,11 @@ def test_sparse_static_embedding_save_load(
 ) -> None:
     model = inference_free_splade_bert_tiny_model
 
+    assert isinstance(model[0].sub_modules.query[0], SparseStaticEmbedding), "SparseStaticEmbedding component missing"
+
+    # Let's randomize the weights to ensure that we can check if they are maintained after saving and loading
+    model[0].sub_modules.query[0].weight == torch.rand_like(model[0].sub_modules.query[0].weight)
+
     # Define test inputs
     test_inputs = ["This is a simple test.", "Another example text for testing."]
 
@@ -52,8 +57,8 @@ def test_sparse_static_embedding_save_load(
 
     # Check if SparseStaticEmbedding weights are maintained after loading
     assert isinstance(
-        loaded_model[0].query_0_SparseStaticEmbedding, SparseStaticEmbedding
+        loaded_model[0].sub_modules.query[0], SparseStaticEmbedding
     ), "SparseStaticEmbedding component missing after loading"
     assert torch.allclose(
-        model[0].query_0_SparseStaticEmbedding.weight, loaded_model[0].query_0_SparseStaticEmbedding.weight
+        model[0].sub_modules.query[0].weight, loaded_model[0].sub_modules.query[0].weight
     ), "SparseStaticEmbedding weights changed after save and load"
diff --git a/tests/sparse_encoder/test_sparse_encoder.py b/tests/sparse_encoder/test_sparse_encoder.py
index 8c3764c..d0945c0 100644
--- a/tests/sparse_encoder/test_sparse_encoder.py
+++ b/tests/sparse_encoder/test_sparse_encoder.py
@@ -546,3 +546,18 @@ def test_intersection(splade_bert_tiny_model: SparseEncoder):
 
     decoded_intersection_batch = model.decode(intersection_batch)
     assert len(decoded_intersection_batch) == len(documents)
+
+
+def test_encode_with_dataset_column(splade_bert_tiny_model: SparseEncoder) -> None:
+    """Test that encode can handle a dataset column as input."""
+    model = splade_bert_tiny_model
+    from datasets import Dataset
+
+    # Create a simple dataset with a text column
+    dataset = Dataset.from_dict({"text": ["This is a test.", "Another sentence."]})
+
+    # Encode the dataset column
+    embeddings = model.encode(dataset["text"], convert_to_tensor=True)
+
+    # Check the shape of the embeddings
+    assert embeddings.shape == (2, model.get_sentence_embedding_dimension())
diff --git a/tests/test_sentence_transformer.py b/tests/test_sentence_transformer.py
index b0e40b3..9c4382a 100644
--- a/tests/test_sentence_transformer.py
+++ b/tests/test_sentence_transformer.py
@@ -1134,3 +1134,18 @@ def test_encode_query_document_vs_encode(stsb_bert_tiny_model: SentenceTransform
         np.testing.assert_allclose(query_embeddings_without_prompt, query_embeddings)
     with pytest.raises(AssertionError):
         np.testing.assert_allclose(document_embeddings_without_prompt, document_embeddings)
+
+
+def test_encode_with_dataset_column(stsb_bert_tiny_model: SentenceTransformer) -> None:
+    """Test that encode can handle a dataset column as input."""
+    model = stsb_bert_tiny_model
+    from datasets import Dataset
+
+    # Create a simple dataset with a text column
+    dataset = Dataset.from_dict({"text": ["This is a test.", "Another sentence."]})
+
+    # Encode the dataset column
+    embeddings = model.encode(dataset["text"], convert_to_tensor=True)
+
+    # Check the shape of the embeddings
+    assert embeddings.shape == (2, model.get_sentence_embedding_dimension())

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/cross_encoder/test_cross_encoder.py tests/models/test_router.py tests/sparse_encoder/models/test_sparse_static_embedding.py tests/sparse_encoder/test_sparse_encoder.py tests/test_sentence_transformer.py
: '>>>>> End Test Output'
git checkout 0d4a3b9b940b6749ec1e4b89ef63572d8bc2f896 tests/cross_encoder/test_cross_encoder.py tests/models/test_router.py tests/sparse_encoder/models/test_sparse_static_embedding.py tests/sparse_encoder/test_sparse_encoder.py tests/test_sentence_transformer.py
