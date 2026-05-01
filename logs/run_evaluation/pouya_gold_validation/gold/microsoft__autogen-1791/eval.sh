#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 676e8e141855e38b211635307054c7ad95c6262d
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e '.[test]' || python -m pip install -e .
git checkout 676e8e141855e38b211635307054c7ad95c6262d test/agentchat/test_groupchat.py
git apply -v - <<'EOF_114329324912'
diff --git a/test/agentchat/test_groupchat.py b/test/agentchat/test_groupchat.py
index d3d07c5b..54b8e9f7 100755
--- a/test/agentchat/test_groupchat.py
+++ b/test/agentchat/test_groupchat.py
@@ -1,14 +1,13 @@
 #!/usr/bin/env python3 -m pytest
 
 from typing import Any, Dict, List, Optional, Type
-from autogen import AgentNameConflict
+from autogen import AgentNameConflict, Agent, GroupChat
 import pytest
 from unittest import mock
 import builtins
 import autogen
 import json
 import sys
-from autogen import Agent, GroupChat
 
 
 def test_func_call_groupchat():
@@ -663,7 +662,7 @@ def test_graceful_exit_before_max_round():
         max_consecutive_auto_reply=10,
         human_input_mode="NEVER",
         llm_config=False,
-        default_auto_reply="This is sam speaking. TERMINATE",
+        default_auto_reply="This is sam speaking.",
     )
 
     # This speaker_transitions limits the transition to be only from agent1 to agent2, and from agent2 to agent3 and end.
@@ -682,7 +681,7 @@ def test_graceful_exit_before_max_round():
 
     group_chat_manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=False, is_termination_msg=None)
 
-    agent1.initiate_chat(group_chat_manager, message="'None' is_termination_msg function.")
+    agent1.initiate_chat(group_chat_manager, message="")
 
     # Note that 3 is much lower than 10 (max_round), so the conversation should end before 10 rounds.
     assert len(groupchat.messages) == 3
@@ -1007,6 +1006,184 @@ def test_nested_teams_chat():
     assert reply["content"] == team2_msg["content"]
 
 
+def test_custom_speaker_selection():
+    a1 = autogen.UserProxyAgent(
+        name="a1",
+        default_auto_reply="This is a1 speaking.",
+        human_input_mode="NEVER",
+        code_execution_config={},
+    )
+
+    a2 = autogen.UserProxyAgent(
+        name="a2",
+        default_auto_reply="This is a2 speaking.",
+        human_input_mode="NEVER",
+        code_execution_config={},
+    )
+
+    a3 = autogen.UserProxyAgent(
+        name="a3",
+        default_auto_reply="TERMINATE",
+        human_input_mode="NEVER",
+        code_execution_config={},
+    )
+
+    def custom_speaker_selection_func(last_speaker: Agent, groupchat: GroupChat) -> Agent:
+        """Define a customized speaker selection function.
+        A recommended way is to define a transition for each speaker using the groupchat allowed_or_disallowed_speaker_transitions parameter.
+        """
+        if last_speaker is a1:
+            return a2
+        elif last_speaker is a2:
+            return a3
+
+    groupchat = autogen.GroupChat(
+        agents=[a1, a2, a3],
+        messages=[],
+        max_round=20,
+        speaker_selection_method=custom_speaker_selection_func,
+    )
+    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=False)
+
+    result = a1.initiate_chat(manager, message="Hello, this is a1 speaking.")
+    assert len(result.chat_history) == 3
+
+
+def test_custom_speaker_selection_with_transition_graph():
+    """
+    In this test, although speaker_selection_method is defined, the speaker transitions are also defined.
+    There are 26 agents here, a to z.
+    The speaker transitions are defined such that the agents can transition to the next alphabet.
+    In addition, because we want the transition order to be a,u,t,o,g,e,n, we also define the speaker transitions for these agents.
+    The speaker_selection_method is defined to return the next agent in the expected sequence.
+    """
+
+    # For loop that creates UserProxyAgent with names from a to z
+    agents = [
+        autogen.UserProxyAgent(
+            name=chr(97 + i),
+            default_auto_reply=f"My name is {chr(97 + i)}",
+            human_input_mode="NEVER",
+            code_execution_config={},
+        )
+        for i in range(26)
+    ]
+
+    # Initiate allowed speaker transitions
+    allowed_or_disallowed_speaker_transitions = {}
+
+    # Each agent can transition to the next alphabet as a baseline
+    # Key is Agent, value is a list of Agents that the key Agent can transition to
+    for i in range(25):
+        allowed_or_disallowed_speaker_transitions[agents[i]] = [agents[i + 1]]
+
+    # The test is to make sure that the agent sequence is a,u,t,o,g,e,n, so we need to add those transitions
+    expected_sequence = ["a", "u", "t", "o", "g", "e", "n"]
+    current_agent = None
+    previous_agent = None
+
+    for char in expected_sequence:
+        # convert char to i so that we can use chr(97+i)
+        current_agent = agents[ord(char) - 97]
+        if previous_agent is not None:
+            # Add transition
+            allowed_or_disallowed_speaker_transitions[previous_agent].append(current_agent)
+        previous_agent = current_agent
+
+    def custom_speaker_selection_func(last_speaker: Agent, groupchat: GroupChat) -> Optional[Agent]:
+        """
+        Define a customized speaker selection function.
+        """
+        expected_sequence = ["a", "u", "t", "o", "g", "e", "n"]
+
+        last_speaker_char = last_speaker.name
+        # Find the index of last_speaker_char in the expected_sequence
+        last_speaker_index = expected_sequence.index(last_speaker_char)
+        # Return the next agent in the expected sequence
+        if last_speaker_index == len(expected_sequence) - 1:
+            return None  # terminate the conversation
+        else:
+            next_agent = agents[ord(expected_sequence[last_speaker_index + 1]) - 97]
+            return next_agent
+
+    groupchat = autogen.GroupChat(
+        agents=agents,
+        messages=[],
+        max_round=20,
+        speaker_selection_method=custom_speaker_selection_func,
+        allowed_or_disallowed_speaker_transitions=allowed_or_disallowed_speaker_transitions,
+        speaker_transitions_type="allowed",
+    )
+    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=False)
+
+    results = agents[0].initiate_chat(manager, message="My name is a")
+    actual_sequence = []
+
+    # Append to actual_sequence using results.chat_history[idx]['content'][-1]
+    for idx in range(len(results.chat_history)):
+        actual_sequence.append(results.chat_history[idx]["content"][-1])  # append the last character of the content
+
+    assert expected_sequence == actual_sequence
+
+
+def test_custom_speaker_selection_overrides_transition_graph():
+    """
+    In this test, team A engineer can transition to team A executor and team B engineer, but team B engineer cannot transition to team A executor.
+    The expected behaviour is that the custom speaker selection function will override the constraints of the graph.
+    """
+
+    # For loop that creates UserProxyAgent with names from a to z
+    agents = [
+        autogen.UserProxyAgent(
+            name="teamA_engineer",
+            default_auto_reply="My name is teamA_engineer",
+            human_input_mode="NEVER",
+            code_execution_config={},
+        ),
+        autogen.UserProxyAgent(
+            name="teamA_executor",
+            default_auto_reply="My name is teamA_executor",
+            human_input_mode="NEVER",
+            code_execution_config={},
+        ),
+        autogen.UserProxyAgent(
+            name="teamB_engineer",
+            default_auto_reply="My name is teamB_engineer",
+            human_input_mode="NEVER",
+            code_execution_config={},
+        ),
+    ]
+
+    allowed_or_disallowed_speaker_transitions = {}
+
+    # teamA_engineer can transition to teamA_executor and teamB_engineer
+    # teamB_engineer can transition to no one
+    allowed_or_disallowed_speaker_transitions[agents[0]] = [agents[1], agents[2]]
+
+    def custom_speaker_selection_func(last_speaker: Agent, groupchat: GroupChat) -> Optional[Agent]:
+        if last_speaker.name == "teamA_engineer":
+            return agents[2]  # Goto teamB_engineer
+        elif last_speaker.name == "teamB_engineer":
+            return agents[1]  # Goto teamA_executor and contradict the graph
+
+    groupchat = autogen.GroupChat(
+        agents=agents,
+        messages=[],
+        max_round=20,
+        speaker_selection_method=custom_speaker_selection_func,
+        allowed_or_disallowed_speaker_transitions=allowed_or_disallowed_speaker_transitions,
+        speaker_transitions_type="allowed",
+    )
+    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=False)
+    results = agents[0].initiate_chat(manager, message="My name is teamA_engineer")
+
+    speakers = []
+    for idx in range(len(results.chat_history)):
+        speakers.append(results.chat_history[idx].get("name"))
+
+    assert "teamA_executor" in speakers
+
+
 if __name__ == "__main__":
     # test_func_call_groupchat()
     # test_broadcast()
@@ -1017,7 +1194,9 @@ if __name__ == "__main__":
     # test_agent_mentions()
     # test_termination()
     # test_next_agent()
-    test_send_intros()
+    # test_send_intros()
     # test_invalid_allow_repeat_speaker()
     # test_graceful_exit_before_max_round()
     # test_clear_agents_history()
+    test_custom_speaker_selection_overrides_transition_graph()
+    # pass
EOF_114329324912
: '>>>>> Start Test Output'
pytest -rA test/agentchat/test_groupchat.py
: '>>>>> End Test Output'
git checkout 676e8e141855e38b211635307054c7ad95c6262d test/agentchat/test_groupchat.py
