#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 57d2f98bc315f1522269a4cad7b2a478cfee3b12
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install hatchling editables && python -m pip install -e '.[test]' --no-build-isolation
git checkout 57d2f98bc315f1522269a4cad7b2a478cfee3b12 test/toolkits/test_mcp_toolkit.py test/utils/test_mcp_client.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/toolkits/test_mcp_toolkit.py b/test/toolkits/test_mcp_toolkit.py
index e36d5b1e..bf6a15ac 100644
--- a/test/toolkits/test_mcp_toolkit.py
+++ b/test/toolkits/test_mcp_toolkit.py
@@ -15,6 +15,7 @@
 Tests for the refactored MCPToolkit.
 """
 
+import asyncio
 import json
 import tempfile
 from contextlib import asynccontextmanager
@@ -193,10 +194,16 @@ class TestMCPToolkitConnectionManagement:
 
         # Set up the second client to raise an exception during __aenter__
         mock_client2.__aenter__.side_effect = Exception("Connection failed")
+        mock_client2._cleanup_connection = AsyncMock()
 
-        toolkit = MCPToolkit(clients=[mock_client1, mock_client2])
+        toolkit = MCPToolkit(
+            clients=[mock_client1, mock_client2],
+            skip_failed=False,
+            max_retries=1,
+            retry_delay=0,
+        )
 
-        expected_msg = "Failed to connect to client 2"
+        expected_msg = "Failed to connect to 1 MCP server"
         with pytest.raises(MCPConnectionError, match=expected_msg):
             await toolkit.connect()
 
@@ -283,12 +290,93 @@ class TestMCPToolkitConnectionManagement:
 
         # Mark as connected
         toolkit._is_connected = True
+        toolkit._connected_clients = [mock_client1, mock_client2]
         assert toolkit.is_connected
 
         # One client disconnected
         mock_client2.is_connected.return_value = False
+        assert toolkit.is_connected
+
+        # No connected clients remain
+        mock_client1.is_connected.return_value = False
         assert not toolkit.is_connected
 
+    @pytest.mark.asyncio
+    async def test_connect_skip_failed_keeps_toolkit_usable(self):
+        """A partial connect should still leave the toolkit usable."""
+        mock_client1 = MagicMock()
+        mock_client2 = MagicMock()
+
+        mock_tool = MagicMock()
+        mock_tool.func.__name__ = "tool1"
+
+        mock_client1.__aenter__.return_value = mock_client1
+        mock_client1.__aexit__.return_value = None
+        mock_client1.is_connected.return_value = True
+        mock_client1.get_tools.return_value = [mock_tool]
+        mock_client1.call_tool = AsyncMock(return_value="tool result")
+
+        mock_client2.__aenter__.side_effect = Exception("Connection failed")
+        mock_client2._cleanup_connection = AsyncMock()
+        mock_client2.is_connected.return_value = False
+        mock_client2.get_tools.side_effect = RuntimeError("not connected")
+
+        toolkit = MCPToolkit(
+            clients=[mock_client1, mock_client2],
+            max_retries=1,
+            retry_delay=0,
+        )
+
+        await toolkit.connect()
+
+        assert toolkit.is_connected
+        assert (
+            await toolkit.call_tool("tool1", {"arg": "value"}) == "tool result"
+        )
+
+    @pytest.mark.asyncio
+    async def test_connect_propagates_cancellation(self):
+        """Cancellation should not be converted into a retry loop."""
+        mock_client = MagicMock()
+        started = asyncio.Event()
+
+        async def slow_enter():
+            started.set()
+            await asyncio.sleep(10)
+
+        mock_client.__aenter__.side_effect = slow_enter
+        mock_client._cleanup_connection = AsyncMock()
+
+        toolkit = MCPToolkit(
+            clients=[mock_client],
+            max_retries=2,
+            retry_delay=0,
+            per_client_timeout=30,
+        )
+
+        task = asyncio.create_task(toolkit.connect())
+        await started.wait()
+        task.cancel()
+
+        with pytest.raises(asyncio.CancelledError):
+            await task
+
+        mock_client._cleanup_connection.assert_awaited_once()
+
+    @pytest.mark.asyncio
+    async def test_connect_all_clients_propagates_cancelled_subtask(self):
+        """A cancelled child task should not be counted as success."""
+        toolkit = MCPToolkit(clients=[MagicMock()])
+
+        async def cancelled_client(*args, **kwargs):
+            raise asyncio.CancelledError()
+
+        with patch.object(
+            toolkit, "_connect_single_client", side_effect=cancelled_client
+        ):
+            with pytest.raises(asyncio.CancelledError):
+                await toolkit._connect_all_clients()
+
     @pytest.mark.asyncio
     async def test_context_manager(self):
         """Test async context manager."""
@@ -338,6 +426,41 @@ class TestMCPToolkitFactoryMethods:
                     assert result is toolkit
                     assert toolkit._is_connected
 
+    @pytest.mark.asyncio
+    async def test_create_forwards_robust_connect_options(self):
+        """Factory method should forward the new connection controls."""
+        with patch.object(
+            MCPToolkit, '__init__', return_value=None
+        ) as init_mock:
+            toolkit = MCPToolkit.__new__(MCPToolkit)
+            toolkit.disconnect = AsyncMock()
+
+            async def mock_connect():
+                return toolkit
+
+            toolkit.connect = mock_connect
+
+            patch_path = 'camel.toolkits.mcp_toolkit.MCPToolkit.__new__'
+            with patch(patch_path, return_value=toolkit):
+                await MCPToolkit.create(
+                    clients=[],
+                    skip_failed=False,
+                    per_client_timeout=12,
+                    max_retries=4,
+                    retry_delay=0.5,
+                )
+
+        init_mock.assert_called_once_with(
+            clients=[],
+            config_path=None,
+            config_dict=None,
+            timeout=None,
+            skip_failed=False,
+            per_client_timeout=12,
+            max_retries=4,
+            retry_delay=0.5,
+        )
+
     @pytest.mark.asyncio
     async def test_create_failure_cleanup(self):
         """Test cleanup on creation failure."""
diff --git a/test/utils/test_mcp_client.py b/test/utils/test_mcp_client.py
index 386cf237..5d27969f 100644
--- a/test/utils/test_mcp_client.py
+++ b/test/utils/test_mcp_client.py
@@ -15,6 +15,7 @@
 Tests for the unified MCP client.
 """
 
+import asyncio
 import json
 import tempfile
 from pathlib import Path
@@ -572,5 +573,261 @@ class TestEdgeCases:
         assert client3.client_info.version == "2.0"
 
 
+class TestSSEFallback:
+    """Test StreamableHTTP -> SSE automatic fallback."""
+
+    @pytest.mark.asyncio
+    async def test_sse_fallback_on_streamablehttp_failure(self):
+        """StreamableHTTP failure should trigger SSE retry."""
+        from contextlib import asynccontextmanager
+        from unittest.mock import AsyncMock, MagicMock, patch
+
+        client = MCPClient(
+            {"url": "http://localhost:8000/mcp", "timeout": 5.0}
+        )
+        assert client.config.transport_type == TransportType.STREAMABLE_HTTP
+
+        call_log = []
+
+        @asynccontextmanager
+        async def fake_transport(override_transport=None):
+            call_log.append(override_transport)
+            if override_transport == TransportType.STREAMABLE_HTTP:
+                raise ConnectionError("streamablehttp timed out")
+            # SSE succeeds: yield fake streams
+            reader = MagicMock()
+            writer = MagicMock()
+            yield reader, writer
+
+        mock_session = AsyncMock()
+        mock_session.initialize = AsyncMock(return_value=None)
+        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
+        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
+        mock_session.__aexit__ = AsyncMock(return_value=None)
+
+        with (
+            patch.object(
+                client, "_create_transport", side_effect=fake_transport
+            ),
+            patch(
+                "camel.utils.mcp_client.ClientSession",
+                return_value=mock_session,
+            ),
+        ):
+            await client._establish_connection()
+
+        # Both transports were attempted in order
+        assert call_log[0] == TransportType.STREAMABLE_HTTP
+        assert call_log[1] == TransportType.SSE
+
+    @pytest.mark.asyncio
+    async def test_no_sse_fallback_for_stdio(self):
+        """stdio transport should NOT attempt SSE fallback on failure."""
+        from contextlib import asynccontextmanager
+        from unittest.mock import patch
+
+        client = MCPClient({"command": "fake-command", "timeout": 5.0})
+        assert client.config.transport_type == TransportType.STDIO
+
+        call_log = []
+
+        @asynccontextmanager
+        async def fake_transport(override_transport=None):
+            call_log.append(override_transport)
+            raise ConnectionError("stdio failed")
+            yield  # make it a generator
+
+        with patch.object(
+            client, "_create_transport", side_effect=fake_transport
+        ):
+            with pytest.raises(ConnectionError):
+                await client._establish_connection()
+
+        # Only stdio was tried, no SSE fallback
+        assert len(call_log) == 1
+        assert call_log[0] == TransportType.STDIO
+
+    @pytest.mark.asyncio
+    async def test_error_raised_when_both_transports_fail(self):
+        """If both StreamableHTTP and SSE fail, ConnectionError is raised."""
+        from contextlib import asynccontextmanager
+        from unittest.mock import patch
+
+        client = MCPClient(
+            {"url": "http://localhost:8000/mcp", "timeout": 5.0}
+        )
+
+        @asynccontextmanager
+        async def fake_transport(override_transport=None):
+            raise ConnectionError(f"{override_transport} failed")
+            yield
+
+        with patch.object(
+            client, "_create_transport", side_effect=fake_transport
+        ):
+            with pytest.raises(ConnectionError):
+                await client._establish_connection()
+
+    @pytest.mark.asyncio
+    async def test_streamablehttp_succeeds_no_fallback(self):
+        """If StreamableHTTP succeeds, SSE fallback should NOT be attempted."""
+        from contextlib import asynccontextmanager
+        from unittest.mock import AsyncMock, MagicMock, patch
+
+        client = MCPClient(
+            {"url": "http://localhost:8000/mcp", "timeout": 5.0}
+        )
+
+        call_log = []
+
+        @asynccontextmanager
+        async def fake_transport(override_transport=None):
+            call_log.append(override_transport)
+            reader = MagicMock()
+            writer = MagicMock()
+            yield reader, writer
+
+        mock_session = AsyncMock()
+        mock_session.initialize = AsyncMock(return_value=None)
+        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
+        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
+        mock_session.__aexit__ = AsyncMock(return_value=None)
+
+        with (
+            patch.object(
+                client, "_create_transport", side_effect=fake_transport
+            ),
+            patch(
+                "camel.utils.mcp_client.ClientSession",
+                return_value=mock_session,
+            ),
+        ):
+            await client._establish_connection()
+
+        # Only StreamableHTTP was used
+        assert call_log == [TransportType.STREAMABLE_HTTP]
+
+    @pytest.mark.asyncio
+    async def test_explicit_streamablehttp_disables_sse_fallback(self):
+        """Explicit StreamableHTTP config should not fall back to SSE."""
+        from unittest.mock import patch
+
+        client = MCPClient(
+            {
+                "url": "http://localhost:8000/mcp",
+                "type": "streamable_http",
+                "timeout": 5.0,
+            }
+        )
+
+        call_log = []
+
+        async def fake_try_connect(transport_type):
+            call_log.append(transport_type)
+            raise ConnectionError("streamablehttp timed out")
+
+        with patch.object(
+            client, "_try_connect", side_effect=fake_try_connect
+        ):
+            with pytest.raises(ConnectionError):
+                await client._establish_connection()
+
+        assert call_log == [TransportType.STREAMABLE_HTTP]
+
+    @pytest.mark.asyncio
+    async def test_cancelled_streamablehttp_falls_back_to_sse(self):
+        """Child-task cancellation should still allow SSE fallback."""
+        from unittest.mock import MagicMock, patch
+
+        client = MCPClient(
+            {"url": "http://localhost:8000/sse", "timeout": 5.0}
+        )
+
+        call_log = []
+
+        async def fake_try_connect(transport_type):
+            call_log.append(transport_type)
+            if transport_type == TransportType.STREAMABLE_HTTP:
+                raise asyncio.CancelledError()
+            client._session = MagicMock()
+            client._tools = []
+
+        with patch.object(
+            client, "_try_connect", side_effect=fake_try_connect
+        ):
+            await client._establish_connection()
+
+        assert call_log == [
+            TransportType.STREAMABLE_HTTP,
+            TransportType.SSE,
+        ]
+
+    @pytest.mark.asyncio
+    async def test_external_cancellation_is_not_swallowed(self):
+        """Real task cancellation should still propagate to the caller."""
+        from unittest.mock import patch
+
+        client = MCPClient(
+            {"url": "http://localhost:8000/sse", "timeout": 5.0}
+        )
+        started = asyncio.Event()
+
+        async def slow_try_connect(transport_type):
+            started.set()
+            await asyncio.sleep(10)
+
+        with patch.object(
+            client, "_try_connect", side_effect=slow_try_connect
+        ):
+            task = asyncio.create_task(client._establish_connection())
+            await started.wait()
+            task.cancel()
+
+            with pytest.raises(asyncio.CancelledError):
+                await task
+
+    @pytest.mark.asyncio
+    async def test_initialize_timeout_uses_config_timeout(self):
+        """Handshake timeout should respect the server config timeout."""
+        from contextlib import asynccontextmanager
+        from unittest.mock import AsyncMock, MagicMock, patch
+
+        client = MCPClient(
+            {"url": "http://localhost:8000/mcp", "timeout": 42.0}
+        )
+
+        observed_timeouts = []
+
+        @asynccontextmanager
+        async def fake_transport(override_transport=None):
+            reader = MagicMock()
+            writer = MagicMock()
+            yield reader, writer
+
+        mock_session = AsyncMock()
+        mock_session.initialize = AsyncMock(return_value=None)
+        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
+        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
+        mock_session.__aexit__ = AsyncMock(return_value=None)
+
+        async def fake_wait_for(awaitable, timeout):
+            observed_timeouts.append(timeout)
+            return await awaitable
+
+        with (
+            patch.object(
+                client, "_create_transport", side_effect=fake_transport
+            ),
+            patch(
+                "camel.utils.mcp_client.ClientSession",
+                return_value=mock_session,
+            ),
+            patch("asyncio.wait_for", side_effect=fake_wait_for),
+        ):
+            await client._try_connect(TransportType.STREAMABLE_HTTP)
+
+        assert observed_timeouts == [42.0, 42.0]
+
+
 if __name__ == "__main__":
     pytest.main([__file__])

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/toolkits/test_mcp_toolkit.py test/utils/test_mcp_client.py
: '>>>>> End Test Output'
git checkout 57d2f98bc315f1522269a4cad7b2a478cfee3b12 test/toolkits/test_mcp_toolkit.py test/utils/test_mcp_client.py
