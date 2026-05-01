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
git checkout 0741f22463fe439ccaf7f4d233ec09933c0b7973 tests/gateway/test_discord_bot_auth_bypass.py
git apply -v - <<'EOF_114329324912'
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
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/gateway/test_discord_bot_auth_bypass.py
: '>>>>> End Test Output'
git checkout 0741f22463fe439ccaf7f4d233ec09933c0b7973 tests/gateway/test_discord_bot_auth_bypass.py
