#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff fcb3e2eb55f1929b09392d05ec54a72999d758d1
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test] --no-build-isolation --verbose || python -m pip install -e . --no-build-isolation --verbose
git checkout fcb3e2eb55f1929b09392d05ec54a72999d758d1 tests/store/test_repository_git.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/store/test_repository_git.py b/tests/store/test_repository_git.py
index 09c7c185092..3bb44423273 100644
--- a/tests/store/test_repository_git.py
+++ b/tests/store/test_repository_git.py
@@ -67,17 +67,30 @@ async def test_git_clone_error(
 
 async def test_git_load(coresys: CoreSys, tmp_path: Path):
     """Test git load."""
-    repo = GitRepo(coresys, tmp_path, REPO_URL)
+    repo_dir = tmp_path / "repo"
+    repo = GitRepo(coresys, repo_dir, REPO_URL)
+    repo.clone = AsyncMock()
 
-    with (
-        patch("pathlib.Path.is_dir", return_value=True),
-        patch.object(
-            GitRepo, "sys_run_in_executor", new_callable=AsyncMock
-        ) as run_in_executor,
-    ):
-        await repo.load()
+    # Test with non-existing git repo root directory
+    await repo.load()
+    assert repo.clone.call_count == 1
+
+    repo.clone.reset_mock()
 
-        assert run_in_executor.call_count == 2
+    # Test with existing git repo root directory, but empty
+    repo_dir.mkdir()
+    await repo.load()
+    assert repo.clone.call_count == 1
+
+    repo.clone.reset_mock()
+
+    # Pretend we have a repo
+    (repo_dir / ".git").mkdir()
+
+    with patch("git.Repo") as mock_repo:
+        await repo.load()
+        assert repo.clone.call_count == 0
+        assert mock_repo.call_count == 1
 
 
 @pytest.mark.parametrize(
@@ -87,21 +100,22 @@ async def test_git_load(coresys: CoreSys, tmp_path: Path):
         NoSuchPathError(),
         GitCommandError("init"),
         UnicodeDecodeError("decode", b"", 0, 0, ""),
-        [AsyncMock(), GitCommandError("fsck")],
+        GitCommandError("fsck"),
     ],
 )
 async def test_git_load_error(coresys: CoreSys, tmp_path: Path, git_errors: Exception):
     """Test git load error."""
+    coresys.hardware.disk.get_disk_free_space = lambda x: 5000
     repo = GitRepo(coresys, tmp_path, REPO_URL)
 
+    # Pretend we have a repo
+    (tmp_path / ".git").mkdir()
+
     with (
-        patch("pathlib.Path.is_dir", return_value=True),
-        patch.object(
-            GitRepo, "sys_run_in_executor", new_callable=AsyncMock
-        ) as run_in_executor,
+        patch("git.Repo") as mock_repo,
         pytest.raises(StoreGitError),
     ):
-        run_in_executor.side_effect = git_errors
+        mock_repo.side_effect = git_errors
         await repo.load()
 
     assert len(coresys.resolution.suggestions) == 0

EOF_114329324912
: '>>>>> Start Test Output'
pytest --timeout=10 -rA tests tests/store/test_repository_git.py
: '>>>>> End Test Output'
git checkout fcb3e2eb55f1929b09392d05ec54a72999d758d1 tests/store/test_repository_git.py
