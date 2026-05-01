#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 89716761adb198a943da521cb7f7ce00c49aec4d
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 89716761adb198a943da521cb7f7ce00c49aec4d tests/plugins/test_artetv.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/plugins/test_artetv.py b/tests/plugins/test_artetv.py
index 62f244c3cf6..40492bb8b9c 100644
--- a/tests/plugins/test_artetv.py
+++ b/tests/plugins/test_artetv.py
@@ -5,30 +5,51 @@
 class TestPluginCanHandleUrlArteTV(PluginCanHandleUrl):
     __plugin__ = ArteTV
 
-    should_match = [
-        # new url
-        "http://www.arte.tv/fr/direct/",
-        "http://www.arte.tv/de/live/",
-        "http://www.arte.tv/de/videos/074633-001-A/gesprach-mit-raoul-peck",
-        "http://www.arte.tv/en/videos/071437-010-A/sunday-soldiers",
-        "http://www.arte.tv/fr/videos/074633-001-A/entretien-avec-raoul-peck",
-        "http://www.arte.tv/pl/videos/069873-000-A/supermama-i-businesswoman",
+    should_match_groups = [
+        # live
+        (
+            ("live", "https://www.arte.tv/fr/direct"),
+            {"language": "fr"},
+        ),
+        (
+            ("live", "https://www.arte.tv/fr/direct/"),
+            {"language": "fr"},
+        ),
+        (
+            ("live", "https://www.arte.tv/de/live"),
+            {"language": "de"},
+        ),
+        (
+            ("live", "https://www.arte.tv/de/live/"),
+            {"language": "de"},
+        ),
 
-        # old url - some of them get redirected and some are 404
-        "http://www.arte.tv/guide/fr/direct",
-        "http://www.arte.tv/guide/de/live",
-        "http://www.arte.tv/guide/fr/024031-000-A/le-testament-du-docteur-mabuse",
-        "http://www.arte.tv/guide/de/024031-000-A/das-testament-des-dr-mabuse",
-        "http://www.arte.tv/guide/en/072544-002-A/christmas-carols-from-cork",
-        "http://www.arte.tv/guide/es/068380-000-A/una-noche-en-florencia",
-        "http://www.arte.tv/guide/pl/068916-006-A/belle-and-sebastian-route-du-rock",
+        # vod
+        (
+            ("vod", "https://www.arte.tv/de/videos/097372-001-A/mysterium-satoshi-bitcoin-wie-alles-begann-1-6/"),
+            {"language": "de", "video_id": "097372-001-A"},
+        ),
+        (
+            ("vod", "https://www.arte.tv/en/videos/097372-001-A/the-satoshi-mystery-the-story-of-bitcoin/"),
+            {"language": "en", "video_id": "097372-001-A"},
+        ),
+
+        # old vod URLs with redirects
+        (
+            ("vod", "https://www.arte.tv/guide/de/097372-001-A/mysterium-satoshi-bitcoin-wie-alles-begann-1-6/"),
+            {"language": "de", "video_id": "097372-001-A"},
+        ),
+        (
+            ("vod", "https://www.arte.tv/guide/en/097372-001-A/the-satoshi-mystery-the-story-of-bitcoin/"),
+            {"language": "en", "video_id": "097372-001-A"},
+        ),
     ]
 
     should_not_match = [
-        # shouldn't match
-        "http://www.arte.tv/guide/fr/plus7/",
-        "http://www.arte.tv/guide/de/plus7/",
+        "https://www.arte.tv/guide/de/live/",
+        "https://www.arte.tv/guide/fr/plus7/",
+        "https://www.arte.tv/guide/de/plus7/",
         # shouldn't match - playlists without video ids in url
-        "http://www.arte.tv/en/videos/RC-014457/the-power-of-forests/",
-        "http://www.arte.tv/en/videos/RC-013118/street-art/",
+        "https://www.arte.tv/en/videos/RC-014457/the-power-of-forests/",
+        "https://www.arte.tv/en/videos/RC-013118/street-art/",
     ]

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/plugins/test_artetv.py
: '>>>>> End Test Output'
git checkout 89716761adb198a943da521cb7f7ce00c49aec4d tests/plugins/test_artetv.py
