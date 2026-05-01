#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 3ef663c5b70f934c5e8f4422a34189069208ff72
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -r requirements_versions.txt || python -m pip install gradio
git checkout 3ef663c5b70f934c5e8f4422a34189069208ff72 tests/test_utils.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_utils.py b/tests/test_utils.py
index 6fd550d..c1f49c1 100644
--- a/tests/test_utils.py
+++ b/tests/test_utils.py
@@ -1,5 +1,7 @@
+import os
 import unittest
 
+import modules.flags
 from modules import util
 
 
@@ -77,5 +79,59 @@ class TestUtils(unittest.TestCase):
         for test in test_cases:
             prompt, loras, loras_limit, skip_file_check = test["input"]
             expected = test["output"]
-            actual = util.parse_lora_references_from_prompt(prompt, loras, loras_limit=loras_limit, skip_file_check=skip_file_check)
+            actual = util.parse_lora_references_from_prompt(prompt, loras, loras_limit=loras_limit,
+                                                            skip_file_check=skip_file_check)
+            self.assertEqual(expected, actual)
+
+    def test_can_parse_tokens_and_strip_performance_lora(self):
+        lora_filenames = [
+            'hey-lora.safetensors',
+            modules.flags.PerformanceLoRA.EXTREME_SPEED.value,
+            modules.flags.PerformanceLoRA.LIGHTNING.value,
+            os.path.join('subfolder', modules.flags.PerformanceLoRA.HYPER_SD.value)
+        ]
+
+        test_cases = [
+            {
+                "input": ("some prompt, <lora:hey-lora:0.4>", [], 5, True, modules.flags.Performance.QUALITY),
+                "output": (
+                    [('hey-lora.safetensors', 0.4)],
+                    'some prompt'
+                ),
+            },
+            {
+                "input": ("some prompt, <lora:hey-lora:0.4>", [], 5, True, modules.flags.Performance.SPEED),
+                "output": (
+                    [('hey-lora.safetensors', 0.4)],
+                    'some prompt'
+                ),
+            },
+            {
+                "input": ("some prompt, <lora:sdxl_lcm_lora:1>, <lora:hey-lora:0.4>", [], 5, True, modules.flags.Performance.EXTREME_SPEED),
+                "output": (
+                    [('hey-lora.safetensors', 0.4)],
+                    'some prompt'
+                ),
+            },
+            {
+                "input": ("some prompt, <lora:sdxl_lightning_4step_lora:1>, <lora:hey-lora:0.4>", [], 5, True, modules.flags.Performance.LIGHTNING),
+                "output": (
+                    [('hey-lora.safetensors', 0.4)],
+                    'some prompt'
+                ),
+            },
+            {
+                "input": ("some prompt, <lora:sdxl_hyper_sd_4step_lora:1>, <lora:hey-lora:0.4>", [], 5, True, modules.flags.Performance.HYPER_SD),
+                "output": (
+                    [('hey-lora.safetensors', 0.4)],
+                    'some prompt'
+                ),
+            }
+        ]
+
+        for test in test_cases:
+            prompt, loras, loras_limit, skip_file_check, performance = test["input"]
+            lora_filenames = modules.util.remove_performance_lora(lora_filenames, performance)
+            expected = test["output"]
+            actual = util.parse_lora_references_from_prompt(prompt, loras, loras_limit=loras_limit, lora_filenames=lora_filenames)
             self.assertEqual(expected, actual)

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_utils.py
: '>>>>> End Test Output'
git checkout 3ef663c5b70f934c5e8f4422a34189069208ff72 tests/test_utils.py
