#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 1821e4c7773a0cd075db0c621fb5eb695871e788
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install hatchling editables && python -m pip install -e '.[test]' --no-build-isolation
git checkout 1821e4c7773a0cd075db0c621fb5eb695871e788 test/toolkits/test_search_functions.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/toolkits/test_search_functions.py b/test/toolkits/test_search_functions.py
index b11a7f94..d5951f86 100644
--- a/test/toolkits/test_search_functions.py
+++ b/test/toolkits/test_search_functions.py
@@ -975,3 +975,210 @@ def test_search_serper_http_error(mock_post, search_toolkit):
     assert "error" in result
     assert "Serper API failed with status 401" in result["error"]
     assert "Invalid API key" in result["error"]
+
+
+# ==================== Querit Search Tests ====================
+
+
+@patch('requests.post')
+def test_search_querit_success(mock_post, search_toolkit):
+    """Test successful Querit search."""
+    mock_response = MagicMock()
+    mock_response.status_code = 200
+    mock_response.json.return_value = {
+        "took": "120ms",
+        "error_code": 200,
+        "error_msg": "",
+        "search_id": 12345,
+        "query_context": {"query": "CAMEL-AI"},
+        "results": {
+            "result": [
+                {
+                    "url": "https://www.camel-ai.org/",
+                    "page_age": "2025-01-15T10:30:00Z",
+                    "title": "CAMEL-AI: First Multi-Agent Framework",
+                    "snippet": "CAMEL-AI is an open-source framework...",
+                    "site_name": "camel-ai.org",
+                    "site_icon": "https://www.camel-ai.org/favicon.ico",
+                },
+                {
+                    "url": "https://github.com/camel-ai/camel",
+                    "page_age": "2025-03-20T08:00:00Z",
+                    "title": "camel-ai/camel: Multi-Agent Framework",
+                    "snippet": "Finding the Scaling Law of Agents...",
+                    "site_name": "github.com",
+                    "site_icon": "https://github.com/favicon.ico",
+                },
+            ]
+        },
+    }
+    mock_post.return_value = mock_response
+
+    with patch.dict(os.environ, {'QUERIT_API_KEY': 'fake_api_key'}):
+        result = search_toolkit.search_querit(query="CAMEL-AI")
+
+    assert "results" in result
+    assert len(result["results"]) == 2
+    assert result["took"] == "120ms"
+    assert result["search_id"] == 12345
+    assert result["results"][0] == {
+        "result_id": 1,
+        "title": "CAMEL-AI: First Multi-Agent Framework",
+        "snippet": "CAMEL-AI is an open-source framework...",
+        "url": "https://www.camel-ai.org/",
+        "site_name": "camel-ai.org",
+        "site_icon": "https://www.camel-ai.org/favicon.ico",
+        "page_age": "2025-01-15T10:30:00Z",
+    }
+
+    # Verify the request was made correctly
+    mock_post.assert_called_once()
+    args, kwargs = mock_post.call_args
+    assert args[0] == "https://api.querit.ai/v1/search"
+    assert kwargs['headers']['Authorization'] == 'Bearer fake_api_key'
+    assert kwargs['headers']['Content-Type'] == 'application/json'
+    assert 'timeout' in kwargs
+
+
+@patch('requests.post')
+def test_search_querit_with_filters(mock_post, search_toolkit):
+    """Test Querit search with all filter parameters."""
+    mock_response = MagicMock()
+    mock_response.status_code = 200
+    mock_response.json.return_value = {
+        "took": "80ms",
+        "error_code": 200,
+        "error_msg": "",
+        "search_id": 12346,
+        "query_context": {"query": "AI agents"},
+        "results": {"result": []},
+    }
+    mock_post.return_value = mock_response
+
+    with patch.dict(os.environ, {'QUERIT_API_KEY': 'fake_api_key'}):
+        search_toolkit.search_querit(
+            query="AI agents",
+            number_of_result_pages=5,
+            site_include=["github.com"],
+            site_exclude=["reddit.com"],
+            time_range="m3",
+            country_include=["united states"],
+            language_include=["english"],
+        )
+
+    # Verify the payload contains correct filter parameters
+    import json
+
+    call_args = mock_post.call_args
+    payload = json.loads(call_args[1]['data'])
+
+    assert payload["query"] == "AI agents"
+    assert payload["count"] == 5
+    assert payload["filters"]["sites"]["include"] == ["github.com"]
+    assert payload["filters"]["sites"]["exclude"] == ["reddit.com"]
+    assert payload["filters"]["timeRange"]["date"] == "m3"
+    assert payload["filters"]["geo"]["countries"]["include"] == [
+        "united states"
+    ]
+    assert payload["filters"]["languages"]["include"] == ["english"]
+
+
+@patch('requests.post')
+def test_search_querit_no_filters(mock_post, search_toolkit):
+    """Test Querit search without filters omits filters key."""
+    mock_response = MagicMock()
+    mock_response.status_code = 200
+    mock_response.json.return_value = {
+        "took": "50ms",
+        "error_code": 200,
+        "error_msg": "",
+        "search_id": 12347,
+        "query_context": {"query": "test"},
+        "results": {"result": []},
+    }
+    mock_post.return_value = mock_response
+
+    with patch.dict(os.environ, {'QUERIT_API_KEY': 'fake_api_key'}):
+        search_toolkit.search_querit(query="test")
+
+    import json
+
+    call_args = mock_post.call_args
+    payload = json.loads(call_args[1]['data'])
+
+    assert "filters" not in payload
+    assert payload["query"] == "test"
+    assert payload["count"] == 10
+
+
+@patch('requests.post')
+def test_search_querit_http_error(mock_post, search_toolkit):
+    """Test HTTP error handling in Querit search."""
+    mock_response = MagicMock()
+    mock_response.status_code = 401
+    mock_response.text = '{"error": "Unauthorized"}'
+    mock_post.return_value = mock_response
+
+    with patch.dict(os.environ, {'QUERIT_API_KEY': 'invalid_key'}):
+        result = search_toolkit.search_querit(query="test")
+
+    assert "error" in result
+    assert "401" in result["error"]
+
+
+@patch('requests.post')
+def test_search_querit_api_error(mock_post, search_toolkit):
+    """Test API-level error handling in Querit search."""
+    mock_response = MagicMock()
+    mock_response.status_code = 200
+    mock_response.json.return_value = {
+        "took": "10ms",
+        "error_code": 429,
+        "error_msg": "Rate limit exceeded",
+        "search_id": 0,
+        "query_context": {"query": "test"},
+        "results": {"result": []},
+    }
+    mock_post.return_value = mock_response
+
+    with patch.dict(os.environ, {'QUERIT_API_KEY': 'fake_key'}):
+        result = search_toolkit.search_querit(query="test")
+
+    assert "error" in result
+    assert "429" in result["error"]
+    assert "Rate limit exceeded" in result["error"]
+
+
+@patch('requests.post')
+def test_search_querit_request_exception(mock_post, search_toolkit):
+    """Test request exception handling in Querit search."""
+    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
+
+    with patch.dict(os.environ, {'QUERIT_API_KEY': 'fake_key'}):
+        result = search_toolkit.search_querit(query="test")
+
+    assert "error" in result
+    assert "Querit search request failed" in result["error"]
+
+
+@patch('requests.post')
+def test_search_querit_empty_results(mock_post, search_toolkit):
+    """Test empty results handling in Querit search."""
+    mock_response = MagicMock()
+    mock_response.status_code = 200
+    mock_response.json.return_value = {
+        "took": "30ms",
+        "error_code": 200,
+        "error_msg": "",
+        "search_id": 12348,
+        "query_context": {"query": "xyznonexistent"},
+        "results": {"result": []},
+    }
+    mock_post.return_value = mock_response
+
+    with patch.dict(os.environ, {'QUERIT_API_KEY': 'fake_key'}):
+        result = search_toolkit.search_querit(query="xyznonexistent")
+
+    assert "results" in result
+    assert len(result["results"]) == 0
+    assert result["search_id"] == 12348

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/toolkits/test_search_functions.py
: '>>>>> End Test Output'
git checkout 1821e4c7773a0cd075db0c621fb5eb695871e788 test/toolkits/test_search_functions.py
