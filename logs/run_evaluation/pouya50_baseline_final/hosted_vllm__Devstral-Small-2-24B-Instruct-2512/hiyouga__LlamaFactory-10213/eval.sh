#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff aab9b400bb9f0582d4b88bc60f41778c3bfc20b3
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[torch,metrics]' || python -m pip install -e .
git checkout aab9b400bb9f0582d4b88bc60f41778c3bfc20b3 tests/data/test_collator.py tests/version.txt
git apply -v - <<'EOF_114329324912'
diff --git a/tests/data/test_collator.py b/tests/data/test_collator.py
index 63370b1b..7222a865 100644
--- a/tests/data/test_collator.py
+++ b/tests/data/test_collator.py
@@ -22,6 +22,7 @@ from transformers import AutoConfig, AutoModelForImageTextToText
 from llamafactory.data import get_template_and_fix_tokenizer
 from llamafactory.data.collator import MultiModalDataCollatorForSeq2Seq, prepare_4d_attention_mask
 from llamafactory.extras.constants import IGNORE_INDEX
+from llamafactory.extras.packages import is_transformers_version_greater_than
 from llamafactory.hparams import get_infer_args
 from llamafactory.model import load_tokenizer
 
@@ -116,14 +117,14 @@ def test_multimodal_collator():
         "labels": [
             [0, 1, 2, 3, q, q, q, q, q, q, q, q],
         ],
-        "position_ids": [
-            [[0, 1, 2, 3, 1, 1, 1, 1, 1, 1, 1, 1]],
-            [[0, 1, 2, 3, 1, 1, 1, 1, 1, 1, 1, 1]],
-            [[0, 1, 2, 3, 1, 1, 1, 1, 1, 1, 1, 1]],
-        ],
-        "rope_deltas": [[-8]],
+        "position_ids": [[[0, 1, 2, 3, 0, 0, 0, 0, 0, 0, 0, 0]]] * 3,
+        "rope_deltas": [[0]],
         **tokenizer_module["processor"].image_processor(fake_image),
     }
+    if not is_transformers_version_greater_than("5.0.0"):
+        expected_input["position_ids"] = [[[0, 1, 2, 3, 1, 1, 1, 1, 1, 1, 1, 1]]] * 3
+        expected_input["rope_deltas"] = [[-8]]
+
     assert batch_input.keys() == expected_input.keys()
     for k in batch_input.keys():
         assert batch_input[k].eq(torch.tensor(expected_input[k])).all()
diff --git a/tests/version.txt b/tests/version.txt
index fdd7d35a..e19c965e 100644
--- a/tests/version.txt
+++ b/tests/version.txt
@@ -1,2 +1,2 @@
 # change if test fails or cache is outdated
-0.9.5.106
+0.9.5.107

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/data/test_collator.py
: '>>>>> End Test Output'
git checkout aab9b400bb9f0582d4b88bc60f41778c3bfc20b3 tests/data/test_collator.py tests/version.txt
