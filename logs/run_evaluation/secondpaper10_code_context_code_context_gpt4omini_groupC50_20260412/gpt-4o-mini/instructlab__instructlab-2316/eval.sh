#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 16b80885ade5c31dcf27fedd35959164e9ce417c
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose && python -m pip install 'trl>=0.12.2'
git checkout 16b80885ade5c31dcf27fedd35959164e9ce417c tests/test_lab_evaluate.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_lab_evaluate.py b/tests/test_lab_evaluate.py
index 0237ab5f60..822b635b69 100644
--- a/tests/test_lab_evaluate.py
+++ b/tests/test_lab_evaluate.py
@@ -111,16 +111,13 @@ def run_mt_bench(cli_runner, error_rate):
         Evaluating answers...
         # SKILL EVALUATION REPORT
 
-        ## MODEL
-        instructlab/granite-7b-lab
+        ## MODEL (SCORE)
+        instructlab/granite-7b-lab (1.5/10.0)
 
-        ### AVERAGE:
-        1.5 (across 2)
-
-        ### TURN ONE:
+        ### TURN ONE (0.0 to 10.0):
         1.0
 
-        ### TURN TWO:
+        ### TURN TWO (0.0 to 10.0):
         2
         """
     )
@@ -169,25 +166,25 @@ def run_mt_bench_branch(cli_runner, error_rate):
         Evaluating answers for branch main...
         # SKILL EVALUATION REPORT
 
-        ## BASE MODEL
-        instructlab/granite-7b-lab
+        ## BASE MODEL (SCORE)
+        instructlab/granite-7b-lab (0/10.0)
 
-        ## MODEL
-        instructlab/granite-7b-lab
+        ## MODEL (SCORE)
+        instructlab/granite-7b-lab (0/10.0)
 
-        ### IMPROVEMENTS:
-        1. category1/qna.yaml (+0.1)
-        2. category3/qna.yaml (+0.1)
+        ### IMPROVEMENTS (0.0 to 10.0):
+        1. category1/qna.yaml: 0.1 -> 0.2 (+0.1)
+        2. category3/qna.yaml: 0.1 -> 0.2 (+0.1)
 
-        ### REGRESSIONS:
-        1. category2/qna.yaml (-0.1)
-        2. category4/qna.yaml (-0.1)
+        ### REGRESSIONS (0.0 to 10.0):
+        1. category2/qna.yaml: 0.4 -> 0.3 (-0.1)
+        2. category4/qna.yaml: 0.4 -> 0.3 (-0.1)
 
-        ### NO CHANGE:
-        1. category5/qna.yaml
+        ### NO CHANGE (0.0 to 10.0):
+        1. category5/qna.yaml (0.5)
 
-        ### NEW:
-        1. category6/qna.yaml
+        ### NEW (0.0 to 10.0):
+        1. category6/qna.yaml (0.6)
         """
     )
     if error_rate > 0:
@@ -242,10 +239,10 @@ def test_evaluate_mt_bench(
 @patch(
     "instructlab.eval.mt_bench.MTBenchBranchEvaluator.judge_answers",
     side_effect=[
-        (gen_qa_pairs(True), 0),
-        (gen_qa_pairs(False), 0),
-        (gen_qa_pairs(True), 0.4567),
-        (gen_qa_pairs(False), 0.4567),
+        (0, gen_qa_pairs(True), 0),
+        (0, gen_qa_pairs(False), 0),
+        (0, gen_qa_pairs(True), 0.4567),
+        (0, gen_qa_pairs(False), 0.4567),
     ],
 )
 def test_evaluate_mt_bench_branch(
@@ -299,13 +296,10 @@ def test_evaluate_mmlu(
         """\
         # KNOWLEDGE EVALUATION REPORT
 
-        ## MODEL
-        instructlab/granite-7b-lab
-
-        ### AVERAGE:
-        0.5 (across 2)
+        ## MODEL (SCORE)
+        instructlab/granite-7b-lab (0.5/1.0)
 
-        ### SCORES:
+        ### SCORES (0.0 to 1.0):
         task1 - 0.1
         task2 - 0.9
         """
@@ -352,25 +346,22 @@ def test_evaluate_mmlu_branch(
         """\
         # KNOWLEDGE EVALUATION REPORT
 
-        ## BASE MODEL
-        instructlab/granite-7b-lab
-
-        ## MODEL
-        instructlab/granite-7b-lab
+        ## BASE MODEL (SCORE)
+        instructlab/granite-7b-lab (0.6/1.0)
 
-        ### AVERAGE:
-        -0.1 (across 5)
+        ## MODEL (SCORE)
+        instructlab/granite-7b-lab (0.5/1.0)
 
-        ### IMPROVEMENTS:
-        1. task1 (+0.1)
-        2. task3 (+0.1)
+        ### IMPROVEMENTS (0.0 to 1.0):
+        1. task1: 0.1 -> 0.2 (+0.1)
+        2. task3: 0.1 -> 0.2 (+0.1)
 
-        ### REGRESSIONS:
-        1. task2 (-0.1)
-        2. task4 (-0.1)
+        ### REGRESSIONS (0.0 to 1.0):
+        1. task2: 0.4 -> 0.3 (-0.1)
+        2. task4: 0.4 -> 0.3 (-0.1)
 
-        ### NO CHANGE:
-        1. task5
+        ### NO CHANGE (0.0 to 1.0):
+        1. task5 (0.5)
         """
     )
     assert result.output == expected

EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA tests/test_lab_evaluate.py
: '>>>>> End Test Output'
git checkout 16b80885ade5c31dcf27fedd35959164e9ce417c tests/test_lab_evaluate.py
