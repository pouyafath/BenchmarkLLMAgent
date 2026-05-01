#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 25f0694290dbee841e39343551e82799e34648e6
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[dev]'
git checkout 25f0694290dbee841e39343551e82799e34648e6 tests/base/test_model.py tests/cross_encoder/test_model.py tests/sparse_encoder/test_model.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/base/test_model.py b/tests/base/test_model.py
index 16092b6..64d6e76 100644
--- a/tests/base/test_model.py
+++ b/tests/base/test_model.py
@@ -747,7 +747,7 @@ def test_is_singular_input_tuple(stsb_bert_tiny_model: SentenceTransformer) -> N
 
 
 def test_is_singular_input_numpy(stsb_bert_tiny_model: SentenceTransformer) -> None:
-    """A numpy array should be singular (not a list type)."""
+    """A numeric numpy array should be singular (treated as an audio waveform)."""
     assert stsb_bert_tiny_model.is_singular_input(np.array([1, 2, 3])) is True
 
 
@@ -756,6 +756,59 @@ def test_is_singular_input_tensor(stsb_bert_tiny_model: SentenceTransformer) ->
     assert stsb_bert_tiny_model.is_singular_input(torch.tensor([1, 2, 3])) is True
 
 
+def test_is_singular_input_numpy_1d_strings(stsb_bert_tiny_model: SentenceTransformer) -> None:
+    """A 1D numpy string array is a batch of texts (e.g. from np.unique), not a single audio input."""
+    assert stsb_bert_tiny_model.is_singular_input(np.array(["hello", "world"])) is False
+    assert stsb_bert_tiny_model.is_singular_input(np.unique(["a", "b", "a"])) is False
+
+
+def test_is_singular_input_numpy_2d_strings(stsb_bert_tiny_model: SentenceTransformer) -> None:
+    """A 2D numpy string array is a batch of text pairs."""
+    assert stsb_bert_tiny_model.is_singular_input(np.array([["q1", "d1"], ["q2", "d2"]])) is False
+
+
+def test_is_singular_input_numpy_bytes(stsb_bert_tiny_model: SentenceTransformer) -> None:
+    """A numpy byte-string array is not treated as a text batch (downstream modality inference
+    does not handle Python ``bytes``), so it falls through to the default singular interpretation."""
+    assert stsb_bert_tiny_model.is_singular_input(np.array([b"hello", b"world"])) is True
+
+
+def test_is_singular_input_numpy_object(stsb_bert_tiny_model: SentenceTransformer) -> None:
+    """A numpy object array is a batch (no valid single-sample type is an object ndarray)."""
+    assert stsb_bert_tiny_model.is_singular_input(np.array(["hello", "world"], dtype=object)) is False
+
+
+def test_is_singular_input_numpy_0d_string(stsb_bert_tiny_model: SentenceTransformer) -> None:
+    """A 0-dim numpy string array represents a single text."""
+    assert stsb_bert_tiny_model.is_singular_input(np.array("hello")) is True
+
+
+def test_encode_numpy_1d_string_array(stsb_bert_tiny_model: SentenceTransformer) -> None:
+    """Regression test for #3718: encoding a 1D numpy string array should not raise and
+    should produce one embedding per element."""
+    texts = np.array(["Access Management", "Press Coordination", "Financial Reports"])
+    embeddings = stsb_bert_tiny_model.encode(texts, show_progress_bar=False)
+    expected = stsb_bert_tiny_model.encode(texts.tolist(), show_progress_bar=False)
+    assert embeddings.shape[0] == 3
+    assert np.allclose(embeddings, expected)
+
+
+def test_encode_numpy_2d_string_array(stsb_bert_tiny_model: SentenceTransformer) -> None:
+    """Encoding a 2D numpy string array should match encoding the equivalent nested list."""
+    pairs = np.array([["what is AI?", "AI is artificial intelligence."], ["what is ML?", "ML is machine learning."]])
+    embeddings = stsb_bert_tiny_model.encode(pairs, show_progress_bar=False)
+    expected = stsb_bert_tiny_model.encode(pairs.tolist(), show_progress_bar=False)
+    assert embeddings.shape[0] == 2
+    assert np.allclose(embeddings, expected)
+
+
+def test_encode_numpy_empty(stsb_bert_tiny_model: SentenceTransformer) -> None:
+    """Encoding an empty string ndarray should return an empty result, like ``encode([])``."""
+    embeddings = stsb_bert_tiny_model.encode(np.array([], dtype=str), show_progress_bar=False)
+    expected = stsb_bert_tiny_model.encode([], show_progress_bar=False)
+    assert np.array_equal(embeddings, expected)
+
+
 @pytest.mark.parametrize(
     "initial_prompts, config_prompts, expected_prompts",
     [
diff --git a/tests/cross_encoder/test_model.py b/tests/cross_encoder/test_model.py
index 112ef3e..e3ab212 100644
--- a/tests/cross_encoder/test_model.py
+++ b/tests/cross_encoder/test_model.py
@@ -154,6 +154,49 @@ def test_predict_single_input(model_name: str):
         assert pair_score.shape == (model.num_labels,)
 
 
+def test_is_singular_input_numpy_1d_pair(reranker_bert_tiny_model: CrossEncoder) -> None:
+    """A 1D numpy string array represents a single (query, document) pair."""
+    assert reranker_bert_tiny_model.is_singular_input(np.array(["query", "document"])) is True
+
+
+def test_is_singular_input_numpy_2d_pairs(reranker_bert_tiny_model: CrossEncoder) -> None:
+    """A 2D numpy string array is a batch of pairs."""
+    assert reranker_bert_tiny_model.is_singular_input(np.array([["q1", "d1"], ["q2", "d2"]])) is False
+
+
+def test_is_singular_input_numpy_empty(reranker_bert_tiny_model: CrossEncoder) -> None:
+    """An empty 1D string ndarray is an empty batch, not a singular pair, matching ``predict([])``."""
+    assert reranker_bert_tiny_model.is_singular_input(np.array([], dtype=str)) is False
+
+
+def test_predict_numpy_empty(reranker_bert_tiny_model: CrossEncoder) -> None:
+    """Predicting on an empty string ndarray should return an empty array, like ``predict([])``."""
+    scores = reranker_bert_tiny_model.predict(np.array([], dtype=str), show_progress_bar=False)
+    expected = reranker_bert_tiny_model.predict([], show_progress_bar=False)
+    assert scores.shape == (0,)
+    assert np.array_equal(scores, expected)
+
+
+def test_predict_numpy_1d_pair(reranker_bert_tiny_model: CrossEncoder) -> None:
+    """Predicting on a 1D numpy string array (a single pair) should match the tuple equivalent
+    and return a scalar score. Exercises the singular-branch .tolist() conversion."""
+    model = reranker_bert_tiny_model
+    pair = np.array(["what is AI?", "AI is artificial intelligence."])
+    score = model.predict(pair, show_progress_bar=False)
+    expected = model.predict(tuple(pair.tolist()), show_progress_bar=False)
+    assert isinstance(score, np.float32)
+    assert np.allclose(score, expected)
+
+
+def test_predict_numpy_2d_pairs(reranker_bert_tiny_model: CrossEncoder) -> None:
+    """Predicting on a 2D numpy string array should match predicting on the equivalent nested list."""
+    pairs = np.array([["what is AI?", "AI is artificial intelligence."], ["what is ML?", "ML is machine learning."]])
+    scores = reranker_bert_tiny_model.predict(pairs, show_progress_bar=False)
+    expected = reranker_bert_tiny_model.predict(pairs.tolist(), show_progress_bar=False)
+    assert scores.shape == (2,)
+    assert np.allclose(scores, expected)
+
+
 def test_predict_batch_size_1(reranker_bert_tiny_model: CrossEncoder) -> None:
     """Regression test: batch_size=1 with num_labels=1 used to fail because squeeze produced a 0-d tensor.
 
diff --git a/tests/sparse_encoder/test_model.py b/tests/sparse_encoder/test_model.py
index fa9a727..ca36a64 100644
--- a/tests/sparse_encoder/test_model.py
+++ b/tests/sparse_encoder/test_model.py
@@ -433,6 +433,35 @@ def test_encode_with_dataset_column(splade_bert_tiny_model: SparseEncoder) -> No
     assert embeddings.shape == (2, model.get_embedding_dimension())
 
 
+def test_encode_numpy_1d_string_array(splade_bert_tiny_model: SparseEncoder) -> None:
+    """Regression test for #3718: encoding a 1D numpy string array should produce one embedding per element."""
+    model = splade_bert_tiny_model
+    texts = np.array(["Access Management", "Press Coordination", "Financial Reports"])
+    embeddings = model.encode(texts, convert_to_tensor=True, save_to_cpu=True)
+    expected = model.encode(texts.tolist(), convert_to_tensor=True, save_to_cpu=True)
+    assert embeddings.shape == (3, model.get_embedding_dimension())
+    assert torch.allclose(embeddings.to_dense(), expected.to_dense())
+
+
+def test_encode_numpy_2d_string_array(splade_bert_tiny_model: SparseEncoder) -> None:
+    """Encoding a 2D numpy string array should match encoding the equivalent nested list."""
+    model = splade_bert_tiny_model
+    pairs = np.array([["what is AI?", "AI is artificial intelligence."], ["what is ML?", "ML is machine learning."]])
+    embeddings = model.encode(pairs, convert_to_tensor=True, save_to_cpu=True)
+    expected = model.encode(pairs.tolist(), convert_to_tensor=True, save_to_cpu=True)
+    assert embeddings.shape == (2, model.get_embedding_dimension())
+    assert torch.allclose(embeddings.to_dense(), expected.to_dense())
+
+
+def test_encode_numpy_empty(splade_bert_tiny_model: SparseEncoder) -> None:
+    """Encoding an empty string ndarray should return an empty tensor, like ``encode([])``."""
+    model = splade_bert_tiny_model
+    embeddings = model.encode(np.array([], dtype=str), convert_to_tensor=True, save_to_cpu=True)
+    expected = model.encode([], convert_to_tensor=True, save_to_cpu=True)
+    assert embeddings.numel() == 0
+    assert torch.equal(embeddings.to_dense(), expected.to_dense())
+
+
 @pytest.mark.parametrize("convert_to_tensor", [True, False])
 @pytest.mark.parametrize("convert_to_sparse_tensor", [True, False])
 @pytest.mark.parametrize("save_to_cpu", [True, False])
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/base/test_model.py tests/cross_encoder/test_model.py tests/sparse_encoder/test_model.py
: '>>>>> End Test Output'
git checkout 25f0694290dbee841e39343551e82799e34648e6 tests/base/test_model.py tests/cross_encoder/test_model.py tests/sparse_encoder/test_model.py
