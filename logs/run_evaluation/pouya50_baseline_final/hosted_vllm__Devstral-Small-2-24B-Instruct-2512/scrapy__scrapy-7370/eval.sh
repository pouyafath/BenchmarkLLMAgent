#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 31bf7c3892df3eb0dfdf5223a0aff5e261f0a7c3
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install hatchling editables && python -m pip install -e '.[test]' --no-build-isolation && python -m pip install pexpect pyftpdlib testfixtures || python -m pip install hatchling editables && python -m pip install -e . --no-build-isolation && python -m pip install pexpect pyftpdlib testfixtures
git checkout 31bf7c3892df3eb0dfdf5223a0aff5e261f0a7c3 tests/test_downloader_handlers.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_downloader_handlers.py b/tests/test_downloader_handlers.py
index a8e63570..eadb7740 100644
--- a/tests/test_downloader_handlers.py
+++ b/tests/test_downloader_handlers.py
@@ -156,12 +156,12 @@ class HttpDownloadHandlerMock:
 @pytest.mark.requires_botocore
 class TestS3Anon:
     def setup_method(self):
-        crawler = get_crawler()
-        with mock.patch(
-            "scrapy.core.downloader.handlers.s3.HTTP11DownloadHandler",
-            HttpDownloadHandlerMock,
-        ):
-            self.s3reqh = build_from_crawler(S3DownloadHandler, crawler)
+        crawler = get_crawler(
+            settings_dict={
+                "DOWNLOAD_HANDLERS": {"https": HttpDownloadHandlerMock},
+            }
+        )
+        self.s3reqh = build_from_crawler(S3DownloadHandler, crawler)
         self.download_request = self.s3reqh.download_request
 
     @coroutine_test
@@ -183,13 +183,10 @@ class TestS3:
             settings_dict={
                 "AWS_ACCESS_KEY_ID": "0PN5J17HBGZHT7JJ3X82",
                 "AWS_SECRET_ACCESS_KEY": "uV3F3YluFJax1cknvbcGwgjvx4QpvB+leU8dUj2o",
+                "DOWNLOAD_HANDLERS": {"https": HttpDownloadHandlerMock},
             }
         )
-        with mock.patch(
-            "scrapy.core.downloader.handlers.s3.HTTP11DownloadHandler",
-            HttpDownloadHandlerMock,
-        ):
-            s3reqh = build_from_crawler(S3DownloadHandler, crawler)
+        s3reqh = build_from_crawler(S3DownloadHandler, crawler)
         self.download_request = s3reqh.download_request
 
     @contextlib.contextmanager

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_downloader_handlers.py
: '>>>>> End Test Output'
git checkout 31bf7c3892df3eb0dfdf5223a0aff5e261f0a7c3 tests/test_downloader_handlers.py
