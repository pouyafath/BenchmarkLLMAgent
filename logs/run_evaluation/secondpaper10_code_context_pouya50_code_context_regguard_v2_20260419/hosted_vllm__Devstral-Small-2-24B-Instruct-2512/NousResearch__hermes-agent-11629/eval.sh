#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 8d7b7feb0d432f3429702922e9a996a4c9e530b3
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[dev]' || python -m pip install -e .
git checkout 8d7b7feb0d432f3429702922e9a996a4c9e530b3 tests/gateway/test_discord_free_response.py tests/gateway/test_discord_slash_commands.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/gateway/test_discord_free_response.py b/tests/gateway/test_discord_free_response.py
index c2ef286d..f1ee9960 100644
--- a/tests/gateway/test_discord_free_response.py
+++ b/tests/gateway/test_discord_free_response.py
@@ -96,7 +96,7 @@ def adapter(monkeypatch):
     return adapter
 
 
-def make_message(*, channel, content: str, mentions=None):
+def make_message(*, channel, content: str, mentions=None, msg_type=None):
     author = SimpleNamespace(id=42, display_name="Jezza", name="Jezza")
     return SimpleNamespace(
         id=123,
@@ -107,6 +107,7 @@ def make_message(*, channel, content: str, mentions=None):
         created_at=datetime.now(timezone.utc),
         channel=channel,
         author=author,
+        type=msg_type if msg_type is not None else discord_platform.discord.MessageType.default,
     )
 
 
@@ -204,6 +205,21 @@ async def test_discord_free_response_channel_overrides_mention_requirement(adapt
     assert event.text == "allowed without mention"
 
 
+@pytest.mark.asyncio
+async def test_discord_free_response_channel_can_come_from_config_extra(adapter, monkeypatch):
+    monkeypatch.delenv("DISCORD_REQUIRE_MENTION", raising=False)
+    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)
+    adapter.config.extra["free_response_channels"] = ["789", "999"]
+
+    message = make_message(channel=FakeTextChannel(channel_id=789), content="allowed from config")
+
+    await adapter._handle_message(message)
+
+    adapter.handle_message.assert_awaited_once()
+    event = adapter.handle_message.await_args.args[0]
+    assert event.text == "allowed from config"
+
+
 @pytest.mark.asyncio
 async def test_discord_forum_parent_in_free_response_list_allows_forum_thread(adapter, monkeypatch):
     monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
@@ -276,6 +292,31 @@ async def test_discord_auto_thread_enabled_by_default(adapter, monkeypatch):
     assert event.source.thread_id == "999"
 
 
+@pytest.mark.asyncio
+async def test_discord_reply_message_skips_auto_thread(adapter, monkeypatch):
+    """Quote-replies should stay in-channel instead of trying to create a thread."""
+    monkeypatch.delenv("DISCORD_AUTO_THREAD", raising=False)
+    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
+    monkeypatch.setenv("DISCORD_FREE_RESPONSE_CHANNELS", "123")
+
+    adapter._auto_create_thread = AsyncMock()
+
+    message = make_message(
+        channel=FakeTextChannel(channel_id=123),
+        content="reply without mention",
+        msg_type=discord_platform.discord.MessageType.reply,
+    )
+
+    await adapter._handle_message(message)
+
+    adapter._auto_create_thread.assert_not_awaited()
+    adapter.handle_message.assert_awaited_once()
+    event = adapter.handle_message.await_args.args[0]
+    assert event.text == "reply without mention"
+    assert event.source.chat_id == "123"
+    assert event.source.chat_type == "group"
+
+
 @pytest.mark.asyncio
 async def test_discord_auto_thread_can_be_disabled(adapter, monkeypatch):
     """Setting auto_thread to false skips thread creation."""
@@ -385,6 +426,33 @@ async def test_discord_voice_linked_channel_skips_mention_requirement_and_auto_t
     assert event.source.chat_type == "group"
 
 
+@pytest.mark.asyncio
+async def test_discord_free_channel_skips_auto_thread(adapter, monkeypatch):
+    """Free-response channels must NOT auto-create threads — bot replies inline.
+
+    Without this, every message in a free-response channel would spin off a
+    thread (since the channel bypasses the @mention gate), defeating the
+    lightweight-chat purpose of free-response mode.
+    """
+    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
+    monkeypatch.setenv("DISCORD_FREE_RESPONSE_CHANNELS", "789")
+    monkeypatch.delenv("DISCORD_AUTO_THREAD", raising=False)  # default true
+
+    adapter._auto_create_thread = AsyncMock()
+
+    message = make_message(
+        channel=FakeTextChannel(channel_id=789),
+        content="free chat message",
+    )
+
+    await adapter._handle_message(message)
+
+    adapter._auto_create_thread.assert_not_awaited()
+    adapter.handle_message.assert_awaited_once()
+    event = adapter.handle_message.await_args.args[0]
+    assert event.source.chat_type == "group"
+
+
 @pytest.mark.asyncio
 async def test_discord_voice_linked_parent_thread_still_requires_mention(adapter, monkeypatch):
     """Threads under a voice-linked channel should still require @mention."""
diff --git a/tests/gateway/test_discord_slash_commands.py b/tests/gateway/test_discord_slash_commands.py
index 310d5182..1c3ec262 100644
--- a/tests/gateway/test_discord_slash_commands.py
+++ b/tests/gateway/test_discord_slash_commands.py
@@ -401,6 +401,8 @@ async def test_auto_create_thread_uses_message_content_as_name(adapter):
     message = SimpleNamespace(
         content="Hello world, how are you?",
         create_thread=AsyncMock(return_value=thread),
+        channel=SimpleNamespace(send=AsyncMock()),
+        author=SimpleNamespace(display_name="Jezza"),
     )
 
     result = await adapter._auto_create_thread(message)
@@ -412,6 +414,48 @@ async def test_auto_create_thread_uses_message_content_as_name(adapter):
     assert call_kwargs["auto_archive_duration"] == 1440
 
 
+@pytest.mark.asyncio
+async def test_auto_create_thread_strips_mention_syntax_from_name(adapter):
+    """Thread names must not contain raw <@id>, <@&id>, or <#id> markers.
+
+    Regression guard for #6336 — previously a message like
+    ``<@&1490963422786093149> help`` would spawn a thread literally
+    named ``<@&1490963422786093149> help``.
+    """
+    thread = SimpleNamespace(id=999, name="help")
+    message = SimpleNamespace(
+        content="<@&1490963422786093149> <@555> please help <#123>",
+        create_thread=AsyncMock(return_value=thread),
+        channel=SimpleNamespace(send=AsyncMock()),
+        author=SimpleNamespace(display_name="Jezza"),
+    )
+
+    await adapter._auto_create_thread(message)
+
+    name = message.create_thread.await_args[1]["name"]
+    assert "<@" not in name, f"role/user mention leaked: {name!r}"
+    assert "<#" not in name, f"channel mention leaked: {name!r}"
+    assert name == "please help"
+
+
+@pytest.mark.asyncio
+async def test_auto_create_thread_falls_back_to_hermes_when_only_mentions(adapter):
+    """If a message contains only mention syntax, the stripped content is
+    empty — fall back to the 'Hermes' default rather than ''."""
+    thread = SimpleNamespace(id=999, name="Hermes")
+    message = SimpleNamespace(
+        content="<@&1490963422786093149>",
+        create_thread=AsyncMock(return_value=thread),
+        channel=SimpleNamespace(send=AsyncMock()),
+        author=SimpleNamespace(display_name="Jezza"),
+    )
+
+    await adapter._auto_create_thread(message)
+
+    name = message.create_thread.await_args[1]["name"]
+    assert name == "Hermes"
+
+
 @pytest.mark.asyncio
 async def test_auto_create_thread_truncates_long_names(adapter):
     long_text = "a" * 200
@@ -419,6 +463,8 @@ async def test_auto_create_thread_truncates_long_names(adapter):
     message = SimpleNamespace(
         content=long_text,
         create_thread=AsyncMock(return_value=thread),
+        channel=SimpleNamespace(send=AsyncMock()),
+        author=SimpleNamespace(display_name="Jezza"),
     )
 
     result = await adapter._auto_create_thread(message)
@@ -430,10 +476,33 @@ async def test_auto_create_thread_truncates_long_names(adapter):
 
 
 @pytest.mark.asyncio
-async def test_auto_create_thread_returns_none_on_failure(adapter):
+async def test_auto_create_thread_falls_back_to_seed_message(adapter):
+    thread = SimpleNamespace(id=555, name="Hello")
+    seed_message = SimpleNamespace(create_thread=AsyncMock(return_value=thread))
+    message = SimpleNamespace(
+        content="Hello",
+        create_thread=AsyncMock(side_effect=RuntimeError("no perms")),
+        channel=SimpleNamespace(send=AsyncMock(return_value=seed_message)),
+        author=SimpleNamespace(display_name="Jezza"),
+    )
+
+    result = await adapter._auto_create_thread(message)
+    assert result is thread
+    message.channel.send.assert_awaited_once_with("🧵 Thread created by Hermes: **Hello**")
+    seed_message.create_thread.assert_awaited_once_with(
+        name="Hello",
+        auto_archive_duration=1440,
+        reason="Auto-threaded from mention by Jezza",
+    )
+
+
+@pytest.mark.asyncio
+async def test_auto_create_thread_returns_none_when_direct_and_fallback_fail(adapter):
     message = SimpleNamespace(
         content="Hello",
         create_thread=AsyncMock(side_effect=RuntimeError("no perms")),
+        channel=SimpleNamespace(send=AsyncMock(side_effect=RuntimeError("send failed"))),
+        author=SimpleNamespace(display_name="Jezza"),
     )
 
     result = await adapter._auto_create_thread(message)

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/gateway/test_discord_free_response.py tests/gateway/test_discord_slash_commands.py
: '>>>>> End Test Output'
git checkout 8d7b7feb0d432f3429702922e9a996a4c9e530b3 tests/gateway/test_discord_free_response.py tests/gateway/test_discord_slash_commands.py
