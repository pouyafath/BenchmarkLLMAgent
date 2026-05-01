#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff f75917645f6821e10627c17a25987673dd154d2b
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -v --no-build-isolation -e .
git checkout f75917645f6821e10627c17a25987673dd154d2b sklearn/datasets/tests/data/openml/id_2/data-v1-dl-1666876.arff.gz sklearn/datasets/tests/data/openml/id_42074/api-v1-jd-42074.json.gz sklearn/datasets/tests/test_openml.py
git apply -v - <<'EOF_114329324912'
diff --git a/sklearn/datasets/tests/data/openml/id_2/data-v1-dl-1666876.arff.gz b/sklearn/datasets/tests/data/openml/id_2/data-v1-dl-1666876.arff.gz
index cdf3254add760..2144153771bfa 100644
Binary files a/sklearn/datasets/tests/data/openml/id_2/data-v1-dl-1666876.arff.gz and b/sklearn/datasets/tests/data/openml/id_2/data-v1-dl-1666876.arff.gz differ
diff --git a/sklearn/datasets/tests/data/openml/id_42074/api-v1-jd-42074.json.gz b/sklearn/datasets/tests/data/openml/id_42074/api-v1-jd-42074.json.gz
index 8bfe157eb6dfe..21761d5ca69ba 100644
Binary files a/sklearn/datasets/tests/data/openml/id_42074/api-v1-jd-42074.json.gz and b/sklearn/datasets/tests/data/openml/id_42074/api-v1-jd-42074.json.gz differ
diff --git a/sklearn/datasets/tests/test_openml.py b/sklearn/datasets/tests/test_openml.py
index ee6d75861ada8..6632fecc3ca4c 100644
--- a/sklearn/datasets/tests/test_openml.py
+++ b/sklearn/datasets/tests/test_openml.py
@@ -17,7 +17,6 @@
 from sklearn import config_context
 from sklearn.datasets import fetch_openml as fetch_openml_orig
 from sklearn.datasets._openml import (
-    _OPENML_PREFIX,
     _get_local_path,
     _open_openml_url,
     _retry_with_clean_cache,
@@ -33,6 +32,7 @@
 OPENML_TEST_DATA_MODULE = "sklearn.datasets.tests.data.openml"
 # if True, urlopen will be monkey patched to only use local files
 test_offline = True
+_MONKEY_PATCH_LOCAL_OPENML_PATH = "data/v1/download/{}"
 
 
 class _MockHTTPResponse:
@@ -74,7 +74,7 @@ def _monkey_patch_webbased_functions(context, data_id, gzip_response):
     # stored as cache should not be mixed up with real openml datasets
     url_prefix_data_description = "https://api.openml.org/api/v1/json/data/"
     url_prefix_data_features = "https://api.openml.org/api/v1/json/data/features/"
-    url_prefix_download_data = "https://api.openml.org/data/v1/"
+    url_prefix_download_data = "https://www.openml.org/data/v1/download"
     url_prefix_data_list = "https://api.openml.org/api/v1/json/data/list/"
 
     path_suffix = ".gz"
@@ -105,7 +105,9 @@ def _file_name(url, suffix):
         )
 
     def _mock_urlopen_shared(url, has_gzip_header, expected_prefix, suffix):
-        assert url.startswith(expected_prefix)
+        assert url.startswith(
+            expected_prefix
+        ), f"{expected_prefix!r} does not match {url!r}"
 
         data_file_name = _file_name(url, suffix)
         data_file_path = resources.files(data_module) / data_file_name
@@ -136,15 +138,27 @@ def _mock_urlopen_data_features(url, has_gzip_header):
         )
 
     def _mock_urlopen_download_data(url, has_gzip_header):
+        # For simplicity the mock filenames don't contain the filename, i.e.
+        # the last part of the data description url after the last /.
+        # For example for id_1, data description download url is:
+        # gunzip -c sklearn/datasets/tests/data/openml/id_1/api-v1-jd-1.json.gz | grep '"url" # noqa: E501
+        # "https:\/\/www.openml.org\/data\/v1\/download\/1\/anneal.arff"
+        # but the mock filename does not contain anneal.arff and is:
+        # sklearn/datasets/tests/data/openml/id_1/data-v1-dl-1.arff.gz.
+        # We only keep the part of the url before the last /
+        url_without_filename = url.rsplit("/", 1)[0]
+
         return _mock_urlopen_shared(
-            url=url,
+            url=url_without_filename,
             has_gzip_header=has_gzip_header,
             expected_prefix=url_prefix_download_data,
             suffix=".arff",
         )
 
     def _mock_urlopen_data_list(url, has_gzip_header):
-        assert url.startswith(url_prefix_data_list)
+        assert url.startswith(
+            url_prefix_data_list
+        ), f"{url_prefix_data_list!r} does not match {url!r}"
 
         data_file_name = _file_name(url, ".json")
         data_file_path = resources.files(data_module) / data_file_name
@@ -1343,22 +1357,24 @@ def test_open_openml_url_cache(monkeypatch, gzip_response, tmpdir):
     data_id = 61
 
     _monkey_patch_webbased_functions(monkeypatch, data_id, gzip_response)
-    openml_path = sklearn.datasets._openml._DATA_FILE.format(data_id)
+    openml_path = _MONKEY_PATCH_LOCAL_OPENML_PATH.format(data_id) + "/filename.arff"
+    url = f"https://www.openml.org/{openml_path}"
     cache_directory = str(tmpdir.mkdir("scikit_learn_data"))
     # first fill the cache
-    response1 = _open_openml_url(openml_path, cache_directory)
+    response1 = _open_openml_url(url, cache_directory)
     # assert file exists
     location = _get_local_path(openml_path, cache_directory)
     assert os.path.isfile(location)
     # redownload, to utilize cache
-    response2 = _open_openml_url(openml_path, cache_directory)
+    response2 = _open_openml_url(url, cache_directory)
     assert response1.read() == response2.read()
 
 
 @pytest.mark.parametrize("write_to_disk", [True, False])
 def test_open_openml_url_unlinks_local_path(monkeypatch, tmpdir, write_to_disk):
     data_id = 61
-    openml_path = sklearn.datasets._openml._DATA_FILE.format(data_id)
+    openml_path = _MONKEY_PATCH_LOCAL_OPENML_PATH.format(data_id) + "/filename.arff"
+    url = f"https://www.openml.org/{openml_path}"
     cache_directory = str(tmpdir.mkdir("scikit_learn_data"))
     location = _get_local_path(openml_path, cache_directory)
 
@@ -1371,14 +1387,14 @@ def _mock_urlopen(request, *args, **kwargs):
     monkeypatch.setattr(sklearn.datasets._openml, "urlopen", _mock_urlopen)
 
     with pytest.raises(ValueError, match="Invalid request"):
-        _open_openml_url(openml_path, cache_directory)
+        _open_openml_url(url, cache_directory)
 
     assert not os.path.exists(location)
 
 
 def test_retry_with_clean_cache(tmpdir):
     data_id = 61
-    openml_path = sklearn.datasets._openml._DATA_FILE.format(data_id)
+    openml_path = _MONKEY_PATCH_LOCAL_OPENML_PATH.format(data_id)
     cache_directory = str(tmpdir.mkdir("scikit_learn_data"))
     location = _get_local_path(openml_path, cache_directory)
     os.makedirs(os.path.dirname(location))
@@ -1401,7 +1417,7 @@ def _load_data():
 
 def test_retry_with_clean_cache_http_error(tmpdir):
     data_id = 61
-    openml_path = sklearn.datasets._openml._DATA_FILE.format(data_id)
+    openml_path = _MONKEY_PATCH_LOCAL_OPENML_PATH.format(data_id)
     cache_directory = str(tmpdir.mkdir("scikit_learn_data"))
 
     @_retry_with_clean_cache(openml_path, cache_directory)
@@ -1487,7 +1503,7 @@ def test_fetch_openml_verify_checksum(monkeypatch, as_frame, cache, tmpdir, pars
 
     def swap_file_mock(request, *args, **kwargs):
         url = request.get_full_url()
-        if url.endswith("data/v1/download/1666876"):
+        if url.endswith("data/v1/download/1666876/anneal.arff"):
             with open(corrupt_copy_path, "rb") as f:
                 corrupted_data = f.read()
             return _MockHTTPResponse(BytesIO(corrupted_data), is_gzip=True)
@@ -1515,13 +1531,13 @@ def _mock_urlopen_network_error(request, *args, **kwargs):
         sklearn.datasets._openml, "urlopen", _mock_urlopen_network_error
     )
 
-    invalid_openml_url = "invalid-url"
+    invalid_openml_url = "https://api.openml.org/invalid-url"
 
     with pytest.warns(
         UserWarning,
         match=re.escape(
             "A network error occurred while downloading"
-            f" {_OPENML_PREFIX + invalid_openml_url}. Retrying..."
+            f" {invalid_openml_url}. Retrying..."
         ),
     ) as record:
         with pytest.raises(HTTPError, match="Simulated network error"):

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA sklearn/datasets/tests/data/openml/id_2/data-v1-dl-1666876.arff.gz sklearn/datasets/tests/data/openml/id_42074/api-v1-jd-42074.json.gz sklearn/datasets/tests/test_openml.py
: '>>>>> End Test Output'
git checkout f75917645f6821e10627c17a25987673dd154d2b sklearn/datasets/tests/data/openml/id_2/data-v1-dl-1666876.arff.gz sklearn/datasets/tests/data/openml/id_42074/api-v1-jd-42074.json.gz sklearn/datasets/tests/test_openml.py
