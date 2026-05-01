#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 0741f22463fe439ccaf7f4d233ec09933c0b7973
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[dev]' || python -m pip install -e .
git checkout 0741f22463fe439ccaf7f4d233ec09933c0b7973 tests/conftest.py tests/cron/test_scheduler.py tests/gateway/test_config.py tests/gateway/test_dingtalk.py tests/gateway/test_discord_bot_auth_bypass.py tests/gateway/test_weixin.py tests/hermes_cli/test_api_key_providers.py tests/hermes_cli/test_arcee_provider.py tests/hermes_cli/test_tools_config.py tests/hermes_cli/test_xiaomi_provider.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/conftest.py b/tests/conftest.py
index 02114046..27950118 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -1,7 +1,27 @@
-"""Shared fixtures for the hermes-agent test suite."""
+"""Shared fixtures for the hermes-agent test suite.
+
+Hermetic-test invariants enforced here (see AGENTS.md for rationale):
+
+1. **No credential env vars.** All provider/credential-shaped env vars
+   (ending in _API_KEY, _TOKEN, _SECRET, _PASSWORD, _CREDENTIALS, etc.)
+   are unset before every test. Local developer keys cannot leak in.
+2. **Isolated HERMES_HOME.** HERMES_HOME points to a per-test tempdir so
+   code reading ``~/.hermes/*`` via ``get_hermes_home()`` can't see the
+   real one. (We do NOT also redirect HOME — that broke subprocesses in
+   CI. Code using ``Path.home() / ".hermes"`` instead of the canonical
+   ``get_hermes_home()`` is a bug to fix at the callsite.)
+3. **Deterministic runtime.** TZ=UTC, LANG=C.UTF-8, PYTHONHASHSEED=0.
+4. **No HERMES_SESSION_* inheritance** — the agent's current gateway
+   session must not leak into tests.
+
+These invariants make the local test run match CI closely. Gaps that
+remain (CPU count, xdist worker count) are addressed by the canonical
+test runner at ``scripts/run_tests.sh``.
+"""
 
 import asyncio
 import os
+import re
 import signal
 import sys
 import tempfile
@@ -16,30 +36,215 @@ if str(PROJECT_ROOT) not in sys.path:
     sys.path.insert(0, str(PROJECT_ROOT))
 
 
+# ── Credential env-var filter ──────────────────────────────────────────────
+#
+# Any env var in the current process matching ONE of these patterns is
+# unset for every test. Developers' local keys cannot leak into assertions
+# about "auto-detect provider when key present".
+
+_CREDENTIAL_SUFFIXES = (
+    "_API_KEY",
+    "_TOKEN",
+    "_SECRET",
+    "_PASSWORD",
+    "_CREDENTIALS",
+    "_ACCESS_KEY",
+    "_SECRET_ACCESS_KEY",
+    "_PRIVATE_KEY",
+    "_OAUTH_TOKEN",
+    "_WEBHOOK_SECRET",
+    "_ENCRYPT_KEY",
+    "_APP_SECRET",
+    "_CLIENT_SECRET",
+    "_CORP_SECRET",
+    "_AES_KEY",
+)
+
+# Explicit names (for ones that don't fit the suffix pattern)
+_CREDENTIAL_NAMES = frozenset({
+    "AWS_ACCESS_KEY_ID",
+    "AWS_SECRET_ACCESS_KEY",
+    "AWS_SESSION_TOKEN",
+    "ANTHROPIC_TOKEN",
+    "FAL_KEY",
+    "GH_TOKEN",
+    "GITHUB_TOKEN",
+    "OPENAI_API_KEY",
+    "OPENROUTER_API_KEY",
+    "NOUS_API_KEY",
+    "GEMINI_API_KEY",
+    "GOOGLE_API_KEY",
+    "GROQ_API_KEY",
+    "XAI_API_KEY",
+    "MISTRAL_API_KEY",
+    "DEEPSEEK_API_KEY",
+    "KIMI_API_KEY",
+    "MOONSHOT_API_KEY",
+    "GLM_API_KEY",
+    "ZAI_API_KEY",
+    "MINIMAX_API_KEY",
+    "OLLAMA_API_KEY",
+    "OPENVIKING_API_KEY",
+    "COPILOT_API_KEY",
+    "CLAUDE_CODE_OAUTH_TOKEN",
+    "BROWSERBASE_API_KEY",
+    "FIRECRAWL_API_KEY",
+    "PARALLEL_API_KEY",
+    "EXA_API_KEY",
+    "TAVILY_API_KEY",
+    "WANDB_API_KEY",
+    "ELEVENLABS_API_KEY",
+    "HONCHO_API_KEY",
+    "MEM0_API_KEY",
+    "SUPERMEMORY_API_KEY",
+    "RETAINDB_API_KEY",
+    "HINDSIGHT_API_KEY",
+    "HINDSIGHT_LLM_API_KEY",
+    "TINKER_API_KEY",
+    "DAYTONA_API_KEY",
+    "TWILIO_AUTH_TOKEN",
+    "TELEGRAM_BOT_TOKEN",
+    "DISCORD_BOT_TOKEN",
+    "SLACK_BOT_TOKEN",
+    "SLACK_APP_TOKEN",
+    "MATTERMOST_TOKEN",
+    "MATRIX_ACCESS_TOKEN",
+    "MATRIX_PASSWORD",
+    "MATRIX_RECOVERY_KEY",
+    "HASS_TOKEN",
+    "EMAIL_PASSWORD",
+    "BLUEBUBBLES_PASSWORD",
+    "FEISHU_APP_SECRET",
+    "FEISHU_ENCRYPT_KEY",
+    "FEISHU_VERIFICATION_TOKEN",
+    "DINGTALK_CLIENT_SECRET",
+    "QQ_CLIENT_SECRET",
+    "QQ_STT_API_KEY",
+    "WECOM_SECRET",
+    "WECOM_CALLBACK_CORP_SECRET",
+    "WECOM_CALLBACK_TOKEN",
+    "WECOM_CALLBACK_ENCODING_AES_KEY",
+    "WEIXIN_TOKEN",
+    "MODAL_TOKEN_ID",
+    "MODAL_TOKEN_SECRET",
+    "TERMINAL_SSH_KEY",
+    "SUDO_PASSWORD",
+    "GATEWAY_PROXY_KEY",
+    "API_SERVER_KEY",
+    "TOOL_GATEWAY_USER_TOKEN",
+    "TELEGRAM_WEBHOOK_SECRET",
+    "WEBHOOK_SECRET",
+    "AI_GATEWAY_API_KEY",
+    "VOICE_TOOLS_OPENAI_KEY",
+    "BROWSER_USE_API_KEY",
+    "CUSTOM_API_KEY",
+    "GATEWAY_PROXY_URL",
+    "GEMINI_BASE_URL",
+    "OPENAI_BASE_URL",
+    "OPENROUTER_BASE_URL",
+    "OLLAMA_BASE_URL",
+    "GROQ_BASE_URL",
+    "XAI_BASE_URL",
+    "AI_GATEWAY_BASE_URL",
+    "ANTHROPIC_BASE_URL",
+})
+
+
+def _looks_like_credential(name: str) -> bool:
+    """True if env var name matches a credential-shaped pattern."""
+    if name in _CREDENTIAL_NAMES:
+        return True
+    return any(name.endswith(suf) for suf in _CREDENTIAL_SUFFIXES)
+
+
+# HERMES_* vars that change test behavior by being set. Unset all of these
+# unconditionally — individual tests that need them set do so explicitly.
+_HERMES_BEHAVIORAL_VARS = frozenset({
+    "HERMES_YOLO_MODE",
+    "HERMES_INTERACTIVE",
+    "HERMES_QUIET",
+    "HERMES_TOOL_PROGRESS",
+    "HERMES_TOOL_PROGRESS_MODE",
+    "HERMES_MAX_ITERATIONS",
+    "HERMES_SESSION_PLATFORM",
+    "HERMES_SESSION_CHAT_ID",
+    "HERMES_SESSION_CHAT_NAME",
+    "HERMES_SESSION_THREAD_ID",
+    "HERMES_SESSION_SOURCE",
+    "HERMES_SESSION_KEY",
+    "HERMES_GATEWAY_SESSION",
+    "HERMES_PLATFORM",
+    "HERMES_INFERENCE_PROVIDER",
+    "HERMES_MANAGED",
+    "HERMES_DEV",
+    "HERMES_CONTAINER",
+    "HERMES_EPHEMERAL_SYSTEM_PROMPT",
+    "HERMES_TIMEZONE",
+    "HERMES_REDACT_SECRETS",
+    "HERMES_BACKGROUND_NOTIFICATIONS",
+    "HERMES_EXEC_ASK",
+    "HERMES_HOME_MODE",
+})
+
+
 @pytest.fixture(autouse=True)
-def _isolate_hermes_home(tmp_path, monkeypatch):
-    """Redirect HERMES_HOME to a temp dir so tests never write to ~/.hermes/."""
-    fake_home = tmp_path / "hermes_test"
-    fake_home.mkdir()
-    (fake_home / "sessions").mkdir()
-    (fake_home / "cron").mkdir()
-    (fake_home / "memories").mkdir()
-    (fake_home / "skills").mkdir()
-    monkeypatch.setenv("HERMES_HOME", str(fake_home))
-    # Reset plugin singleton so tests don't leak plugins from ~/.hermes/plugins/
+def _hermetic_environment(tmp_path, monkeypatch):
+    """Blank out all credential/behavioral env vars so local and CI match.
+
+    Also redirects HOME and HERMES_HOME to per-test tempdirs so code that
+    reads ``~/.hermes/*`` can't touch the real one, and pins TZ/LANG so
+    datetime/locale-sensitive tests are deterministic.
+    """
+    # 1. Blank every credential-shaped env var that's currently set.
+    for name in list(os.environ.keys()):
+        if _looks_like_credential(name):
+            monkeypatch.delenv(name, raising=False)
+
+    # 2. Blank behavioral HERMES_* vars that could change test semantics.
+    for name in _HERMES_BEHAVIORAL_VARS:
+        monkeypatch.delenv(name, raising=False)
+
+    # 3. Redirect HERMES_HOME to a per-test tempdir. Code that reads
+    #    ``~/.hermes/*`` via ``get_hermes_home()`` now gets the tempdir.
+    #
+    #    NOTE: We do NOT also redirect HOME. Doing so broke CI because
+    #    some tests (and their transitive deps) spawn subprocesses that
+    #    inherit HOME and expect it to be stable. If a test genuinely
+    #    needs HOME isolated, it should set it explicitly in its own
+    #    fixture. Any code in the codebase reading ``~/.hermes/*`` via
+    #    ``Path.home() / ".hermes"`` instead of ``get_hermes_home()``
+    #    is a bug to fix at the callsite.
+    fake_hermes_home = tmp_path / "hermes_test"
+    fake_hermes_home.mkdir()
+    (fake_hermes_home / "sessions").mkdir()
+    (fake_hermes_home / "cron").mkdir()
+    (fake_hermes_home / "memories").mkdir()
+    (fake_hermes_home / "skills").mkdir()
+    monkeypatch.setenv("HERMES_HOME", str(fake_hermes_home))
+
+    # 4. Deterministic locale / timezone / hashseed. CI runs in UTC with
+    #    C.UTF-8 locale; local dev often doesn't. Pin everything.
+    monkeypatch.setenv("TZ", "UTC")
+    monkeypatch.setenv("LANG", "C.UTF-8")
+    monkeypatch.setenv("LC_ALL", "C.UTF-8")
+    monkeypatch.setenv("PYTHONHASHSEED", "0")
+
+    # 5. Reset plugin singleton so tests don't leak plugins from
+    #    ~/.hermes/plugins/ (which, per step 3, is now empty — but the
+    #    singleton might still be cached from a previous test).
     try:
         import hermes_cli.plugins as _plugins_mod
         monkeypatch.setattr(_plugins_mod, "_plugin_manager", None)
     except Exception:
         pass
-    # Tests should not inherit the agent's current gateway/messaging surface.
-    # Individual tests that need gateway behavior set these explicitly.
-    monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)
-    monkeypatch.delenv("HERMES_SESSION_CHAT_ID", raising=False)
-    monkeypatch.delenv("HERMES_SESSION_CHAT_NAME", raising=False)
-    monkeypatch.delenv("HERMES_GATEWAY_SESSION", raising=False)
-    # Avoid making real calls during tests if this key is set in the env files
-    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
+
+
+# Backward-compat alias — old tests reference this fixture name. Keep it
+# as a no-op wrapper so imports don't break.
+@pytest.fixture(autouse=True)
+def _isolate_hermes_home(_hermetic_environment):
+    """Alias preserved for any test that yields this name explicitly."""
+    return None
 
 
 @pytest.fixture()
diff --git a/tests/cron/test_scheduler.py b/tests/cron/test_scheduler.py
index e558afab..2717584e 100644
--- a/tests/cron/test_scheduler.py
+++ b/tests/cron/test_scheduler.py
@@ -64,6 +64,60 @@ class TestResolveDeliveryTarget:
             "thread_id": "17585",
         }
 
+    @pytest.mark.parametrize(
+        ("platform", "env_var", "chat_id"),
+        [
+            ("matrix", "MATRIX_HOME_ROOM", "!bot-room:example.org"),
+            ("signal", "SIGNAL_HOME_CHANNEL", "+15551234567"),
+            ("mattermost", "MATTERMOST_HOME_CHANNEL", "team-town-square"),
+            ("sms", "SMS_HOME_CHANNEL", "+15557654321"),
+            ("email", "EMAIL_HOME_ADDRESS", "home@example.com"),
+            ("dingtalk", "DINGTALK_HOME_CHANNEL", "cidNNN"),
+            ("feishu", "FEISHU_HOME_CHANNEL", "oc_home"),
+            ("wecom", "WECOM_HOME_CHANNEL", "wecom-home"),
+            ("weixin", "WEIXIN_HOME_CHANNEL", "wxid_home"),
+            ("qqbot", "QQ_HOME_CHANNEL", "group-openid-home"),
+        ],
+    )
+    def test_origin_delivery_without_origin_falls_back_to_supported_home_channels(
+        self, monkeypatch, platform, env_var, chat_id
+    ):
+        for fallback_env in (
+            "MATRIX_HOME_ROOM",
+            "MATRIX_HOME_CHANNEL",
+            "TELEGRAM_HOME_CHANNEL",
+            "DISCORD_HOME_CHANNEL",
+            "SLACK_HOME_CHANNEL",
+            "SIGNAL_HOME_CHANNEL",
+            "MATTERMOST_HOME_CHANNEL",
+            "SMS_HOME_CHANNEL",
+            "EMAIL_HOME_ADDRESS",
+            "DINGTALK_HOME_CHANNEL",
+            "BLUEBUBBLES_HOME_CHANNEL",
+            "FEISHU_HOME_CHANNEL",
+            "WECOM_HOME_CHANNEL",
+            "WEIXIN_HOME_CHANNEL",
+            "QQ_HOME_CHANNEL",
+        ):
+            monkeypatch.delenv(fallback_env, raising=False)
+        monkeypatch.setenv(env_var, chat_id)
+
+        assert _resolve_delivery_target({"deliver": "origin"}) == {
+            "platform": platform,
+            "chat_id": chat_id,
+            "thread_id": None,
+        }
+
+    def test_bare_matrix_delivery_uses_matrix_home_room(self, monkeypatch):
+        monkeypatch.delenv("MATRIX_HOME_CHANNEL", raising=False)
+        monkeypatch.setenv("MATRIX_HOME_ROOM", "!room123:example.org")
+
+        assert _resolve_delivery_target({"deliver": "matrix"}) == {
+            "platform": "matrix",
+            "chat_id": "!room123:example.org",
+            "thread_id": None,
+        }
+
     def test_explicit_telegram_topic_target_with_thread_id(self):
         """deliver: 'telegram:chat_id:thread_id' parses correctly."""
         job = {
diff --git a/tests/gateway/test_config.py b/tests/gateway/test_config.py
index e60bf1e9..41a7a49f 100644
--- a/tests/gateway/test_config.py
+++ b/tests/gateway/test_config.py
@@ -71,6 +71,51 @@ class TestGetConnectedPlatforms:
         config = GatewayConfig()
         assert config.get_connected_platforms() == []
 
+    def test_dingtalk_recognised_via_extras(self):
+        config = GatewayConfig(
+            platforms={
+                Platform.DINGTALK: PlatformConfig(
+                    enabled=True,
+                    extra={"client_id": "cid", "client_secret": "sec"},
+                ),
+            },
+        )
+        assert Platform.DINGTALK in config.get_connected_platforms()
+
+    def test_dingtalk_recognised_via_env_vars(self, monkeypatch):
+        """DingTalk configured via env vars (no extras) should still be
+        recognised as connected — covers the case where _apply_env_overrides
+        hasn't populated extras yet."""
+        monkeypatch.setenv("DINGTALK_CLIENT_ID", "env_cid")
+        monkeypatch.setenv("DINGTALK_CLIENT_SECRET", "env_sec")
+        config = GatewayConfig(
+            platforms={
+                Platform.DINGTALK: PlatformConfig(enabled=True, extra={}),
+            },
+        )
+        assert Platform.DINGTALK in config.get_connected_platforms()
+
+    def test_dingtalk_missing_creds_not_connected(self, monkeypatch):
+        monkeypatch.delenv("DINGTALK_CLIENT_ID", raising=False)
+        monkeypatch.delenv("DINGTALK_CLIENT_SECRET", raising=False)
+        config = GatewayConfig(
+            platforms={
+                Platform.DINGTALK: PlatformConfig(enabled=True, extra={}),
+            },
+        )
+        assert Platform.DINGTALK not in config.get_connected_platforms()
+
+    def test_dingtalk_disabled_not_connected(self):
+        config = GatewayConfig(
+            platforms={
+                Platform.DINGTALK: PlatformConfig(
+                    enabled=False,
+                    extra={"client_id": "cid", "client_secret": "sec"},
+                ),
+            },
+        )
+        assert Platform.DINGTALK not in config.get_connected_platforms()
+
 
 class TestSessionResetPolicy:
     def test_roundtrip(self):
diff --git a/tests/gateway/test_dingtalk.py b/tests/gateway/test_dingtalk.py
index 8404281d..a004e17a 100644
--- a/tests/gateway/test_dingtalk.py
+++ b/tests/gateway/test_dingtalk.py
@@ -575,3 +575,109 @@ class TestShouldProcessMessage:
         # Different group still blocked
         assert adapter._should_process_message(msg, "hi", is_group=True, chat_id="grp2") is False
 
+
+# ---------------------------------------------------------------------------
+# _IncomingHandler.process — session_webhook extraction & fire-and-forget
+# ---------------------------------------------------------------------------
+
+
+class TestIncomingHandlerProcess:
+    """Verify that _IncomingHandler.process correctly converts callback data
+    and dispatches message processing as a background task (fire-and-forget)
+    so the SDK ACK is returned immediately."""
+
+    @pytest.mark.asyncio
+    async def test_process_extracts_session_webhook(self):
+        """session_webhook must be populated from callback data."""
+        from gateway.platforms.dingtalk import _IncomingHandler, DingTalkAdapter
+
+        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
+        adapter._on_message = AsyncMock()
+        handler = _IncomingHandler(adapter, asyncio.get_running_loop())
+
+        callback = MagicMock()
+        callback.data = {
+            "msgtype": "text",
+            "text": {"content": "hello"},
+            "senderId": "user1",
+            "conversationId": "conv1",
+            "sessionWebhook": "https://oapi.dingtalk.com/robot/sendBySession?session=abc",
+            "msgId": "msg-001",
+        }
+
+        result = await handler.process(callback)
+        # Should return ACK immediately (STATUS_OK = 200)
+        assert result[0] == 200
+
+        # Let the background task run
+        await asyncio.sleep(0.05)
+
+        # _on_message should have been called with a ChatbotMessage
+        adapter._on_message.assert_called_once()
+        chatbot_msg = adapter._on_message.call_args[0][0]
+        assert chatbot_msg.session_webhook == "https://oapi.dingtalk.com/robot/sendBySession?session=abc"
+
+    @pytest.mark.asyncio
+    async def test_process_fallback_session_webhook_when_from_dict_misses_it(self):
+        """If ChatbotMessage.from_dict does not map sessionWebhook (e.g. SDK
+        version mismatch), the handler should fall back to extracting it
+        directly from the raw data dict."""
+        from gateway.platforms.dingtalk import _IncomingHandler, DingTalkAdapter
+
+        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
+        adapter._on_message = AsyncMock()
+        handler = _IncomingHandler(adapter, asyncio.get_running_loop())
+
+        callback = MagicMock()
+        # Use a key that from_dict might not recognise in some SDK versions
+        callback.data = {
+            "msgtype": "text",
+            "text": {"content": "hi"},
+            "senderId": "user2",
+            "conversationId": "conv2",
+            "session_webhook": "https://oapi.dingtalk.com/robot/sendBySession?session=def",
+            "msgId": "msg-002",
+        }
+
+        await handler.process(callback)
+        await asyncio.sleep(0.05)
+
+        adapter._on_message.assert_called_once()
+        chatbot_msg = adapter._on_message.call_args[0][0]
+        assert chatbot_msg.session_webhook == "https://oapi.dingtalk.com/robot/sendBySession?session=def"
+
+    @pytest.mark.asyncio
+    async def test_process_returns_ack_immediately(self):
+        """process() must not block on _on_message — it should return
+        the ACK tuple before the message is fully processed."""
+        from gateway.platforms.dingtalk import _IncomingHandler, DingTalkAdapter
+
+        processing_started = asyncio.Event()
+        processing_gate = asyncio.Event()
+
+        async def slow_on_message(msg):
+            processing_started.set()
+            await processing_gate.wait()  # Block until we release
+
+        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
+        adapter._on_message = slow_on_message
+        handler = _IncomingHandler(adapter, asyncio.get_running_loop())
+
+        callback = MagicMock()
+        callback.data = {
+            "msgtype": "text",
+            "text": {"content": "test"},
+            "senderId": "u",
+            "conversationId": "c",
+            "sessionWebhook": "https://oapi.dingtalk.com/x",
+            "msgId": "m",
+        }
+
+        # process() should return immediately even though _on_message blocks
+        result = await handler.process(callback)
+        assert result[0] == 200
+
+        # Clean up: release the gate so the background task finishes
+        processing_gate.set()
+        await asyncio.sleep(0.05)
+
diff --git a/tests/gateway/test_discord_bot_auth_bypass.py b/tests/gateway/test_discord_bot_auth_bypass.py
index 29e6a889..8ff39a1b 100644
--- a/tests/gateway/test_discord_bot_auth_bypass.py
+++ b/tests/gateway/test_discord_bot_auth_bypass.py
@@ -22,6 +22,23 @@ import pytest
 from gateway.session import Platform, SessionSource
 
 
+@pytest.fixture(autouse=True)
+def _isolate_discord_env(monkeypatch):
+    """Make every test start with a clean Discord env so prior tests in the
+    session (or CI setups) can't leak DISCORD_ALLOWED_ROLES / DISCORD_ALLOWED_USERS
+    / DISCORD_ALLOW_BOTS and silently flip the auth result.
+    """
+    for var in (
+        "DISCORD_ALLOW_BOTS",
+        "DISCORD_ALLOWED_USERS",
+        "DISCORD_ALLOWED_ROLES",
+        "DISCORD_ALLOW_ALL_USERS",
+        "GATEWAY_ALLOW_ALL_USERS",
+        "GATEWAY_ALLOWED_USERS",
+    ):
+        monkeypatch.delenv(var, raising=False)
+
+
 # -----------------------------------------------------------------------------
 # Gate 2: _is_user_authorized bypasses allowlist for permitted bots
 # -----------------------------------------------------------------------------
@@ -152,3 +169,58 @@ def test_bot_bypass_does_not_leak_to_other_platforms(monkeypatch):
         is_bot=True,
     )
     assert runner._is_user_authorized(telegram_bot) is False
+
+
+# -----------------------------------------------------------------------------
+# DISCORD_ALLOWED_ROLES gateway-layer bypass (#7871)
+# -----------------------------------------------------------------------------
+
+
+def test_discord_role_config_bypasses_gateway_allowlist(monkeypatch):
+    """When DISCORD_ALLOWED_ROLES is set, _is_user_authorized must trust
+    the adapter's pre-filter and authorize. Without this, role-only setups
+    (DISCORD_ALLOWED_ROLES populated, DISCORD_ALLOWED_USERS empty) would
+    hit the 'no allowlists configured' branch and get rejected.
+    """
+    runner = _make_bare_runner()
+
+    monkeypatch.setenv("DISCORD_ALLOWED_ROLES", "1493705176387948674")
+    # Note: DISCORD_ALLOWED_USERS is NOT set — the entire point.
+
+    source = _make_discord_human_source(user_id="999888777")
+    assert runner._is_user_authorized(source) is True
+
+
+def test_discord_role_config_still_authorizes_alongside_users(monkeypatch):
+    """Sanity: setting both DISCORD_ALLOWED_ROLES and DISCORD_ALLOWED_USERS
+    doesn't break the user-id path. Users in the allowlist should still be
+    authorized even if they don't have a role. (OR semantics.)
+    """
+    runner = _make_bare_runner()
+
+    monkeypatch.setenv("DISCORD_ALLOWED_ROLES", "1493705176387948674")
+    monkeypatch.setenv("DISCORD_ALLOWED_USERS", "100200300")
+
+    # User on the user allowlist, no role → still authorized at gateway
+    # level via the role bypass (adapter already approved them).
+    source = _make_discord_human_source(user_id="100200300")
+    assert runner._is_user_authorized(source) is True
+
+
+def test_discord_role_bypass_does_not_leak_to_other_platforms(monkeypatch):
+    """DISCORD_ALLOWED_ROLES must only affect Discord. Setting it should
+    not suddenly start authorizing Telegram users whose platform has its
+    own empty allowlist.
+    """
+    runner = _make_bare_runner()
+
+    monkeypatch.setenv("DISCORD_ALLOWED_ROLES", "1493705176387948674")
+    # Telegram has its own empty allowlist and no allow-all flag.
+
+    telegram_user = SessionSource(
+        platform=Platform.TELEGRAM,
+        chat_id="123",
+        chat_type="channel",
+        user_id="999888777",
+    )
+    assert runner._is_user_authorized(telegram_user) is False
diff --git a/tests/gateway/test_weixin.py b/tests/gateway/test_weixin.py
index 8fc29200..a0dfbbb8 100644
--- a/tests/gateway/test_weixin.py
+++ b/tests/gateway/test_weixin.py
@@ -311,6 +311,7 @@ class TestWeixinChunkDelivery:
     def _connected_adapter(self) -> WeixinAdapter:
         adapter = _make_adapter()
         adapter._session = object()
+        adapter._send_session = adapter._session
         adapter._token = "test-token"
         adapter._base_url = "https://weixin.example.com"
         adapter._token_store.get = lambda account_id, chat_id: "ctx-token"
@@ -420,6 +421,7 @@ class TestWeixinBlankMessagePrevention:
     def test_send_empty_content_does_not_call_send_message(self, send_message_mock):
         adapter = _make_adapter()
         adapter._session = object()
+        adapter._send_session = adapter._session
         adapter._token = "test-token"
         adapter._base_url = "https://weixin.example.com"
         adapter._token_store.get = lambda account_id, chat_id: "ctx-token"
@@ -525,6 +527,7 @@ class TestWeixinSendImageFileParameterName:
         """Verify send_image_file accepts image_path and forwards to send_document."""
         adapter = _make_adapter()
         adapter._session = object()
+        adapter._send_session = adapter._session
         adapter._token = "test-token"
 
         send_document_mock.return_value = weixin.SendResult(success=True, message_id="test-id")
@@ -552,6 +555,7 @@ class TestWeixinSendImageFileParameterName:
         """Verify send_image_file works with minimal required params."""
         adapter = _make_adapter()
         adapter._session = object()
+        adapter._send_session = adapter._session
         adapter._token = "test-token"
 
         send_document_mock.return_value = weixin.SendResult(success=True, message_id="test-id")
@@ -576,6 +580,7 @@ class TestWeixinVoiceSending:
     def _connected_adapter(self) -> WeixinAdapter:
         adapter = _make_adapter()
         adapter._session = object()
+        adapter._send_session = adapter._session
         adapter._token = "test-token"
         adapter._base_url = "https://weixin.example.com"
         adapter._token_store.get = lambda account_id, chat_id: "ctx-token"
diff --git a/tests/hermes_cli/test_api_key_providers.py b/tests/hermes_cli/test_api_key_providers.py
index 0e8badc6..97deab89 100644
--- a/tests/hermes_cli/test_api_key_providers.py
+++ b/tests/hermes_cli/test_api_key_providers.py
@@ -1,17 +1,9 @@
 """Tests for API-key provider support (z.ai/GLM, Kimi, MiniMax, AI Gateway)."""
 
 import os
-import sys
-import types
 
 import pytest
 
-# Ensure dotenv doesn't interfere
-if "dotenv" not in sys.modules:
-    fake_dotenv = types.ModuleType("dotenv")
-    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
-    sys.modules["dotenv"] = fake_dotenv
-
 from hermes_cli.auth import (
     PROVIDER_REGISTRY,
     ProviderConfig,
diff --git a/tests/hermes_cli/test_arcee_provider.py b/tests/hermes_cli/test_arcee_provider.py
index 33266588..39b4e578 100644
--- a/tests/hermes_cli/test_arcee_provider.py
+++ b/tests/hermes_cli/test_arcee_provider.py
@@ -1,15 +1,9 @@
 """Tests for Arcee AI provider support — standard direct API provider."""
 
-import sys
 import types
 
 import pytest
 
-if "dotenv" not in sys.modules:
-    fake_dotenv = types.ModuleType("dotenv")
-    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
-    sys.modules["dotenv"] = fake_dotenv
-
 from hermes_cli.auth import (
     PROVIDER_REGISTRY,
     resolve_provider,
diff --git a/tests/hermes_cli/test_tools_config.py b/tests/hermes_cli/test_tools_config.py
index 3a72490b..8911d46d 100644
--- a/tests/hermes_cli/test_tools_config.py
+++ b/tests/hermes_cli/test_tools_config.py
@@ -40,6 +40,19 @@ def test_get_platform_tools_preserves_explicit_empty_selection():
     assert enabled == set()
 
 
+def test_get_platform_tools_handles_null_platform_toolsets():
+    """YAML `platform_toolsets:` with no value parses as None — the old
+    ``config.get("platform_toolsets", {})`` pattern would then crash with
+    ``NoneType has no attribute 'get'`` on the next line. Guard against that.
+    """
+    config = {"platform_toolsets": None}
+
+    enabled = _get_platform_tools(config, "cli")
+
+    # Falls through to defaults instead of raising
+    assert enabled
+
+
 def test_platform_toolset_summary_uses_explicit_platform_list():
     config = {}
 
diff --git a/tests/hermes_cli/test_xiaomi_provider.py b/tests/hermes_cli/test_xiaomi_provider.py
index ed60ed3f..57e5bdda 100644
--- a/tests/hermes_cli/test_xiaomi_provider.py
+++ b/tests/hermes_cli/test_xiaomi_provider.py
@@ -1,17 +1,9 @@
 """Tests for Xiaomi MiMo provider support."""
 
 import os
-import sys
-import types
 
 import pytest
 
-# Ensure dotenv doesn't interfere
-if "dotenv" not in sys.modules:
-    fake_dotenv = types.ModuleType("dotenv")
-    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
-    sys.modules["dotenv"] = fake_dotenv
-
 from hermes_cli.auth import (
     PROVIDER_REGISTRY,
     resolve_provider,

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/conftest.py tests/cron/test_scheduler.py tests/gateway/test_config.py tests/gateway/test_dingtalk.py tests/gateway/test_discord_bot_auth_bypass.py tests/gateway/test_weixin.py tests/hermes_cli/test_api_key_providers.py tests/hermes_cli/test_arcee_provider.py tests/hermes_cli/test_tools_config.py tests/hermes_cli/test_xiaomi_provider.py
: '>>>>> End Test Output'
git checkout 0741f22463fe439ccaf7f4d233ec09933c0b7973 tests/conftest.py tests/cron/test_scheduler.py tests/gateway/test_config.py tests/gateway/test_dingtalk.py tests/gateway/test_discord_bot_auth_bypass.py tests/gateway/test_weixin.py tests/hermes_cli/test_api_key_providers.py tests/hermes_cli/test_arcee_provider.py tests/hermes_cli/test_tools_config.py tests/hermes_cli/test_xiaomi_provider.py
