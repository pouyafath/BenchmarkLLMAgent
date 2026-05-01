#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 9708058dae27d6bdb7d77ae605aa9eee86ca01a7
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 9708058dae27d6bdb7d77ae605aa9eee86ca01a7 test/agentchat/contrib/test_img_utils.py test/agentchat/contrib/test_llava.py test/agentchat/contrib/test_lmm.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/agentchat/contrib/test_img_utils.py b/test/agentchat/contrib/test_img_utils.py
index 9c38153f..39a4a7f6 100644
--- a/test/agentchat/contrib/test_img_utils.py
+++ b/test/agentchat/contrib/test_img_utils.py
@@ -1,6 +1,5 @@
 import base64
 import os
-import pdb
 import unittest
 from unittest.mock import patch
 
@@ -8,9 +7,18 @@ import pytest
 import requests
 
 try:
+    import numpy as np
     from PIL import Image
 
-    from autogen.agentchat.contrib.img_utils import extract_img_paths, get_image_data, gpt4v_formatter, llava_formatter
+    from autogen.agentchat.contrib.img_utils import (
+        convert_base64_to_data_uri,
+        extract_img_paths,
+        get_image_data,
+        get_pil_image,
+        gpt4v_formatter,
+        llava_formatter,
+        message_formatter_pil_to_b64,
+    )
 except ImportError:
     skip = True
 else:
@@ -18,7 +26,8 @@ else:
 
 
 base64_encoded_image = (
-    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4"
+    "data:image/png;base64,"
+    "iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4"
     "//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg=="
 )
 
@@ -27,6 +36,35 @@ raw_encoded_image = (
     "//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg=="
 )
 
+if skip:
+    raw_pil_image = None
+else:
+    raw_pil_image = Image.new("RGB", (10, 10), color="red")
+
+
+@pytest.mark.skipif(skip, reason="dependency is not installed")
+class TestGetPilImage(unittest.TestCase):
+    def test_read_local_file(self):
+        # Create a small red image for testing
+        temp_file = "_temp.png"
+        raw_pil_image.save(temp_file)
+        img2 = get_pil_image(temp_file)
+        self.assertTrue((np.array(raw_pil_image) == np.array(img2)).all())
+
+    def test_read_pil(self):
+        # Create a small red image for testing
+        img2 = get_pil_image(raw_pil_image)
+        self.assertTrue((np.array(raw_pil_image) == np.array(img2)).all())
+
+
+def are_b64_images_equal(x: str, y: str):
+    """
+    Asserts that two base64 encoded images are equal.
+    """
+    img1 = get_pil_image(x)
+    img2 = get_pil_image(y)
+    return (np.array(img1) == np.array(img2)).all()
+
 
 @pytest.mark.skipif(skip, reason="dependency is not installed")
 class TestGetImageData(unittest.TestCase):
@@ -34,20 +72,20 @@ class TestGetImageData(unittest.TestCase):
         with patch("requests.get") as mock_get:
             mock_response = requests.Response()
             mock_response.status_code = 200
-            mock_response._content = b"fake image content"
+            mock_response._content = base64.b64decode(raw_encoded_image)
             mock_get.return_value = mock_response
 
             result = get_image_data("http://example.com/image.png")
-            self.assertEqual(result, base64.b64encode(b"fake image content").decode("utf-8"))
+            self.assertTrue(are_b64_images_equal(result, raw_encoded_image))
 
     def test_base64_encoded_image(self):
         result = get_image_data(base64_encoded_image)
-        self.assertEqual(result, base64_encoded_image.split(",", 1)[1])
+
+        self.assertTrue(are_b64_images_equal(result, base64_encoded_image.split(",", 1)[1]))
 
     def test_local_image(self):
         # Create a temporary file to simulate a local image file.
         temp_file = "_temp.png"
-
         image = Image.new("RGB", (60, 30), color=(73, 109, 137))
         image.save(temp_file)
 
@@ -126,6 +164,36 @@ class TestGpt4vFormatter(unittest.TestCase):
         result = gpt4v_formatter(prompt)
         self.assertEqual(result, expected_output)
 
+    @patch("autogen.agentchat.contrib.img_utils.get_pil_image")
+    def test_with_images_for_pil(self, mock_get_pil_image):
+        """
+        Test the gpt4v_formatter function with a prompt containing images.
+        """
+        # Mock the get_image_data function to return a fixed string.
+        mock_get_pil_image.return_value = raw_pil_image
+
+        prompt = "This is a test with an image <img http://example.com/image.png>."
+        expected_output = [
+            {"type": "text", "text": "This is a test with an image "},
+            {"type": "image_url", "image_url": {"url": raw_pil_image}},
+            {"type": "text", "text": "."},
+        ]
+        result = gpt4v_formatter(prompt, img_format="pil")
+        self.assertEqual(result, expected_output)
+
+    def test_with_images_for_url(self):
+        """
+        Test the gpt4v_formatter function with a prompt containing images.
+        """
+        prompt = "This is a test with an image <img http://example.com/image.png>."
+        expected_output = [
+            {"type": "text", "text": "This is a test with an image "},
+            {"type": "image_url", "image_url": {"url": "http://example.com/image.png"}},
+            {"type": "text", "text": "."},
+        ]
+        result = gpt4v_formatter(prompt, img_format="url")
+        self.assertEqual(result, expected_output)
+
     @patch("autogen.agentchat.contrib.img_utils.get_image_data")
     def test_multiple_images(self, mock_get_image_data):
         """
@@ -189,5 +257,36 @@ class TestExtractImgPaths(unittest.TestCase):
         self.assertEqual(result, expected_output)
 
 
+@pytest.mark.skipif(skip, reason="dependency is not installed")
+class MessageFormatterPILtoB64Test(unittest.TestCase):
+    def test_formatting(self):
+        messages = [
+            {"content": [{"type": "text", "text": "You are a helpful AI assistant."}], "role": "system"},
+            {
+                "content": [
+                    {"type": "text", "text": "What's the breed of this dog here? \n"},
+                    {"type": "image_url", "image_url": {"url": raw_pil_image}},
+                    {"type": "text", "text": "."},
+                ],
+                "role": "user",
+            },
+        ]
+
+        img_uri_data = convert_base64_to_data_uri(get_image_data(raw_pil_image))
+        expected_output = [
+            {"content": [{"type": "text", "text": "You are a helpful AI assistant."}], "role": "system"},
+            {
+                "content": [
+                    {"type": "text", "text": "What's the breed of this dog here? \n"},
+                    {"type": "image_url", "image_url": {"url": img_uri_data}},
+                    {"type": "text", "text": "."},
+                ],
+                "role": "user",
+            },
+        ]
+        result = message_formatter_pil_to_b64(messages)
+        self.assertEqual(result, expected_output)
+
+
 if __name__ == "__main__":
     unittest.main()
diff --git a/test/agentchat/contrib/test_llava.py b/test/agentchat/contrib/test_llava.py
index 385077ff..19f9009a 100644
--- a/test/agentchat/contrib/test_llava.py
+++ b/test/agentchat/contrib/test_llava.py
@@ -8,14 +8,10 @@ import autogen
 from conftest import MOCK_OPEN_AI_API_KEY
 
 try:
-    from autogen.agentchat.contrib.llava_agent import (
-        LLaVAAgent,
-        _llava_call_binary_with_config,
-        llava_call,
-        llava_call_binary,
-    )
+    from autogen.agentchat.contrib.llava_agent import LLaVAAgent, _llava_call_binary_with_config, llava_call
 except ImportError:
     skip = True
+
 else:
     skip = False
 
diff --git a/test/agentchat/contrib/test_lmm.py b/test/agentchat/contrib/test_lmm.py
index 125b5146..5a0d4310 100644
--- a/test/agentchat/contrib/test_lmm.py
+++ b/test/agentchat/contrib/test_lmm.py
@@ -9,6 +9,7 @@ from autogen.agentchat.conversable_agent import ConversableAgent
 from conftest import MOCK_OPEN_AI_API_KEY
 
 try:
+    from autogen.agentchat.contrib.img_utils import get_pil_image
     from autogen.agentchat.contrib.multimodal_conversable_agent import MultimodalConversableAgent
 except ImportError:
     skip = True
@@ -22,6 +23,12 @@ base64_encoded_image = (
 )
 
 
+if skip:
+    pil_image = None
+else:
+    pil_image = get_pil_image(base64_encoded_image)
+
+
 @pytest.mark.skipif(skip, reason="dependency is not installed")
 class TestMultimodalConversableAgent(unittest.TestCase):
     def setUp(self):
@@ -53,7 +60,7 @@ class TestMultimodalConversableAgent(unittest.TestCase):
             self.agent.system_message,
             [
                 {"type": "text", "text": "We will discuss "},
-                {"type": "image_url", "image_url": {"url": base64_encoded_image}},
+                {"type": "image_url", "image_url": {"url": pil_image}},
                 {"type": "text", "text": " in this conversation."},
             ],
         )

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/agentchat/contrib/test_img_utils.py test/agentchat/contrib/test_llava.py test/agentchat/contrib/test_lmm.py
: '>>>>> End Test Output'
git checkout 9708058dae27d6bdb7d77ae605aa9eee86ca01a7 test/agentchat/contrib/test_img_utils.py test/agentchat/contrib/test_llava.py test/agentchat/contrib/test_lmm.py
