#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 16933a1aa41c9d1854dfd4309940b73b3ee008cf
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout 16933a1aa41c9d1854dfd4309940b73b3ee008cf tests/test_signals.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_signals.py b/tests/test_signals.py
index 2d63c47e58..9e2c63ff04 100644
--- a/tests/test_signals.py
+++ b/tests/test_signals.py
@@ -1,8 +1,12 @@
+from itertools import chain
 from unittest import mock
 
 import pytest
 
 from pdm import signals
+from pdm.models.candidates import Candidate
+from pdm.models.repositories import Package
+from pdm.models.requirements import Requirement
 
 
 def test_post_init_signal(project_no_init, pdm):
@@ -26,3 +30,82 @@ def test_post_lock_and_install_signals(project, pdm):
     signals.post_install.disconnect(post_install)
     for mocker in (pre_lock, post_lock, pre_install, post_install):
         mocker.assert_called_once()
+
+
+@pytest.mark.usefixtures("working_set")
+def test_lock_and_install_signals_injection_with_add(project, pdm):
+    pre_lock = signals.pre_lock.connect(mock.Mock(), weak=False)
+    post_lock = signals.post_lock.connect(mock.Mock(), weak=False)
+    pre_install = signals.pre_install.connect(mock.Mock(), weak=False)
+    post_install = signals.post_install.connect(mock.Mock(), weak=False)
+    pdm(["add", "requests"], obj=project, strict=True)
+    signals.pre_lock.disconnect(pre_lock)
+    signals.post_lock.disconnect(post_lock)
+    signals.pre_install.disconnect(pre_install)
+    signals.post_install.disconnect(post_install)
+
+    assert isinstance(pre_lock.call_args.kwargs["requirements"], list)
+    assert all(isinstance(e, Requirement) for e in pre_lock.call_args.kwargs["requirements"])
+    assert len(pre_lock.call_args.kwargs["requirements"]) == 1
+
+    assert isinstance(post_lock.call_args.kwargs["resolution"], dict)
+    assert all(isinstance(e, Candidate) for e in chain.from_iterable(post_lock.call_args.kwargs["resolution"].values()))
+    assert len(post_lock.call_args.kwargs["resolution"]) == 5
+
+    assert isinstance(pre_install.call_args.kwargs["packages"], list)
+    assert all(isinstance(e, Package) for e in pre_install.call_args.kwargs["packages"])
+    assert len(pre_install.call_args.kwargs["packages"]) == 5
+
+    assert isinstance(post_install.call_args.kwargs["packages"], list)
+    assert all(isinstance(e, Package) for e in post_install.call_args.kwargs["packages"])
+    assert len(post_install.call_args.kwargs["packages"]) == 5
+
+
+@pytest.mark.usefixtures("working_set")
+def test_lock_and_install_signals_injection_with_install(project, pdm):
+    project.add_dependencies(["requests"])
+
+    pre_lock = signals.pre_lock.connect(mock.Mock(), weak=False)
+    post_lock = signals.post_lock.connect(mock.Mock(), weak=False)
+    pre_install = signals.pre_install.connect(mock.Mock(), weak=False)
+    post_install = signals.post_install.connect(mock.Mock(), weak=False)
+    pdm(["install"], obj=project, strict=True)
+    signals.pre_lock.disconnect(pre_lock)
+    signals.post_lock.disconnect(post_lock)
+    signals.pre_install.disconnect(pre_install)
+    signals.post_install.disconnect(post_install)
+
+    assert isinstance(pre_lock.call_args.kwargs["requirements"], list)
+    assert all(isinstance(e, Requirement) for e in pre_lock.call_args.kwargs["requirements"])
+    assert len(pre_lock.call_args.kwargs["requirements"]) == 1
+
+    assert isinstance(post_lock.call_args.kwargs["resolution"], dict)
+    assert all(isinstance(e, Candidate) for e in chain.from_iterable(post_lock.call_args.kwargs["resolution"].values()))
+    assert len(post_lock.call_args.kwargs["resolution"]) == 5
+
+    assert isinstance(pre_install.call_args.kwargs["packages"], list)
+    assert all(isinstance(e, Package) for e in pre_install.call_args.kwargs["packages"])
+    assert len(pre_install.call_args.kwargs["packages"]) == 5
+
+    assert isinstance(post_install.call_args.kwargs["packages"], list)
+    assert all(isinstance(e, Package) for e in post_install.call_args.kwargs["packages"])
+    assert len(post_install.call_args.kwargs["packages"]) == 5
+
+
+@pytest.mark.usefixtures("working_set")
+def test_lock_signals_injection_with_update(project, pdm):
+    project.add_dependencies(["requests"])
+
+    pre_lock = signals.pre_lock.connect(mock.Mock(), weak=False)
+    post_lock = signals.post_lock.connect(mock.Mock(), weak=False)
+    pdm(["update"], obj=project, strict=True)
+    signals.pre_lock.disconnect(pre_lock)
+    signals.post_lock.disconnect(post_lock)
+
+    assert isinstance(pre_lock.call_args.kwargs["requirements"], list)
+    assert all(isinstance(e, Requirement) for e in pre_lock.call_args.kwargs["requirements"])
+    assert len(pre_lock.call_args.kwargs["requirements"]) == 1
+
+    assert isinstance(post_lock.call_args.kwargs["resolution"], dict)
+    assert all(isinstance(e, Candidate) for e in chain.from_iterable(post_lock.call_args.kwargs["resolution"].values()))
+    assert len(post_lock.call_args.kwargs["resolution"]) == 5

EOF_114329324912
: '>>>>> Start Test Output'
pdm run pytest -rA tests/test_signals.py
: '>>>>> End Test Output'
git checkout 16933a1aa41c9d1854dfd4309940b73b3ee008cf tests/test_signals.py
