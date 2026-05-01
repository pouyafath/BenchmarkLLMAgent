#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 43d79d3a2428122bf0284ce7f23fb3773a048a9f
source /opt/miniconda3/bin/activate
conda activate testbed
poetry install --with dev || poetry install
git checkout 43d79d3a2428122bf0284ce7f23fb3773a048a9f tests/test_app.py tests/test_state.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_app.py b/tests/test_app.py
index f933149f166..ab7b50bdf2b 100644
--- a/tests/test_app.py
+++ b/tests/test_app.py
@@ -906,7 +906,7 @@ def on_counter(self):
         """Increment the counter var."""
         self.counter = self.counter + 1
 
-    @computed_var
+    @computed_var(cache=True)
     def comp_dynamic(self) -> str:
         """A computed var that depends on the dynamic var.
 
@@ -1049,9 +1049,6 @@ def _dynamic_state_event(name, val, **kwargs):
         assert on_load_update == StateUpdate(
             delta={
                 state.get_name(): {
-                    # These computed vars _shouldn't_ be here, because they didn't change
-                    arg_name: exp_val,
-                    f"comp_{arg_name}": exp_val,
                     "loaded": exp_index + 1,
                 },
             },
@@ -1073,9 +1070,6 @@ def _dynamic_state_event(name, val, **kwargs):
         assert on_set_is_hydrated_update == StateUpdate(
             delta={
                 state.get_name(): {
-                    # These computed vars _shouldn't_ be here, because they didn't change
-                    arg_name: exp_val,
-                    f"comp_{arg_name}": exp_val,
                     "is_hydrated": True,
                 },
             },
@@ -1097,9 +1091,6 @@ def _dynamic_state_event(name, val, **kwargs):
         assert update == StateUpdate(
             delta={
                 state.get_name(): {
-                    # These computed vars _shouldn't_ be here, because they didn't change
-                    f"comp_{arg_name}": exp_val,
-                    arg_name: exp_val,
                     "counter": exp_index + 1,
                 }
             },
diff --git a/tests/test_state.py b/tests/test_state.py
index ba8fc592f33..1f1693156fc 100644
--- a/tests/test_state.py
+++ b/tests/test_state.py
@@ -649,7 +649,12 @@ def test_set_dirty_var(test_state):
     assert test_state.dirty_vars == set()
 
 
-def test_set_dirty_substate(test_state, child_state, child_state2, grandchild_state):
+def test_set_dirty_substate(
+    test_state: TestState,
+    child_state: ChildState,
+    child_state2: ChildState2,
+    grandchild_state: GrandchildState,
+):
     """Test changing substate vars marks the value as dirty.
 
     Args:
@@ -3077,6 +3082,51 @@ def bar(self) -> str:
     assert C1._potentially_dirty_substates() == set()
 
 
+def test_router_var_dep() -> None:
+    """Test that router var dependencies are correctly tracked."""
+
+    class RouterVarParentState(State):
+        """A parent state for testing router var dependency."""
+
+        pass
+
+    class RouterVarDepState(RouterVarParentState):
+        """A state with a router var dependency."""
+
+        @rx.var(cache=True)
+        def foo(self) -> str:
+            return self.router.page.params.get("foo", "")
+
+    foo = RouterVarDepState.computed_vars["foo"]
+    State._init_var_dependency_dicts()
+
+    assert foo._deps(objclass=RouterVarDepState) == {"router"}
+    assert RouterVarParentState._potentially_dirty_substates() == {RouterVarDepState}
+    assert RouterVarParentState._substate_var_dependencies == {
+        "router": {RouterVarDepState.get_name()}
+    }
+    assert RouterVarDepState._computed_var_dependencies == {
+        "router": {"foo"},
+    }
+
+    rx_state = State()
+    parent_state = RouterVarParentState()
+    state = RouterVarDepState()
+
+    # link states
+    rx_state.substates = {RouterVarParentState.get_name(): parent_state}
+    parent_state.parent_state = rx_state
+    state.parent_state = parent_state
+    parent_state.substates = {RouterVarDepState.get_name(): state}
+
+    assert state.dirty_vars == set()
+
+    # Reassign router var
+    state.router = state.router
+    assert state.dirty_vars == {"foo", "router"}
+    assert parent_state.dirty_substates == {RouterVarDepState.get_name()}
+
+
 @pytest.mark.asyncio
 async def test_setvar(mock_app: rx.App, token: str):
     """Test that setvar works correctly.

EOF_114329324912
: '>>>>> Start Test Output'
poetry run pytest -rA tests tests/test_app.py tests/test_state.py
: '>>>>> End Test Output'
git checkout 43d79d3a2428122bf0284ce7f23fb3773a048a9f tests/test_app.py tests/test_state.py
