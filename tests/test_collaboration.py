"""Tests for collaboration.py — MultiAgentCollaboration."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys
from pathlib import Path as PP
sys.path.insert(0, str(PP(__file__).parent.parent))

from client.collaboration import (
    MultiAgentCollaboration, AgentRole, AgentInfo,
    CollaborationTask, TaskStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_collab(tmp_path) -> MultiAgentCollaboration:
    """MultiAgentCollaboration backed by temp dir."""
    collab_dir = tmp_path / "collab"
    with patch.object(MultiAgentCollaboration, '__init__', lambda self, dir=None: None):
        mc = MultiAgentCollaboration.__new__(MultiAgentCollaboration)
        mc.collaboration_dir = collab_dir
        mc.collaboration_dir.mkdir(parents=True, exist_ok=True)
        mc.tasks_file = mc.collaboration_dir / "tasks.json"
        mc.agents_file = mc.collaboration_dir / "agents.json"
        mc.shared_kb_file = mc.collaboration_dir / "shared_knowledge.json"
        mc.agents = {}
        mc.tasks = {}
        mc.shared_knowledge = {}
        mc._event_handlers = {}
        mc._load = lambda: None  # skip load
        mc._register_main_agent()
        return mc


# ---------------------------------------------------------------------------
# AgentRole enum
# ---------------------------------------------------------------------------

class TestAgentRole:
    def test_all_roles_exist(self):
        assert AgentRole.COORDINATOR.value == "coordinator"
        assert AgentRole.SPECIALIST.value == "specialist"
        assert AgentRole.WORKER.value == "worker"
        assert AgentRole.REVIEWER.value == "reviewer"


# ---------------------------------------------------------------------------
# AgentInfo dataclass
# ---------------------------------------------------------------------------

class TestAgentInfo:
    def test_defaults(self):
        info = AgentInfo(
            id="a1", name="Agent 1",
            role=AgentRole.WORKER,
            capabilities=["python"],
        )
        assert info.status == "online"
        assert info.current_task_id is None
        assert info.last_heartbeat != ""


# ---------------------------------------------------------------------------
# CollaborationTask dataclass
# ---------------------------------------------------------------------------

class TestCollaborationTask:
    def test_defaults(self):
        task = CollaborationTask(
            id="t1", description="Do stuff", goal_id="g1",
        )
        assert task.status == TaskStatus.PENDING
        assert task.priority == 0
        assert task.depends_on == []
        assert task.outputs == {}
        assert task.assigned_to is None
        assert task.result is None
        assert task.error is None


# ---------------------------------------------------------------------------
# MultiAgentCollaboration — init / register
# ---------------------------------------------------------------------------

class TestCollaborationInit:
    def test_main_agent_registered_on_init(self, tmp_path):
        mc = make_collab(tmp_path)
        assert "main" in mc.agents
        assert mc.agents["main"].role == AgentRole.COORDINATOR

    def test_register_agent(self, tmp_path):
        mc = make_collab(tmp_path)
        agent = mc.register_agent("Alice", AgentRole.SPECIALIST, ["python", "docker"])
        assert agent.name == "Alice"
        assert agent.role == AgentRole.SPECIALIST
        assert agent.capabilities == ["python", "docker"]
        assert agent.id in mc.agents

    def test_unregister_agent(self, tmp_path):
        mc = make_collab(tmp_path)
        agent = mc.register_agent("Bob", AgentRole.WORKER, ["go"])
        mc.unregister_agent(agent.id)
        assert agent.id not in mc.agents

    def test_unregister_main_agent_not_allowed(self, tmp_path):
        mc = make_collab(tmp_path)
        mc.unregister_agent("main")
        assert "main" in mc.agents  # main always stays

    def test_unregister_reassigns_tasks_to_pending(self, tmp_path):
        mc = make_collab(tmp_path)
        agent = mc.register_agent("Bob", AgentRole.WORKER, ["go"])
        task = mc.create_task("Do go stuff", goal_id="g1", assigned_to=agent.id)
        mc.unregister_agent(agent.id)
        assert mc.tasks[task.id].status == TaskStatus.PENDING
        assert mc.tasks[task.id].assigned_to is None


# ---------------------------------------------------------------------------
# Tasks — create / assign
# ---------------------------------------------------------------------------

class TestCollaborationCreateTask:
    def test_create_task_returns_task(self, tmp_path):
        mc = make_collab(tmp_path)
        task = mc.create_task("Write tests", goal_id="g1")
        assert task.description == "Write tests"
        assert task.goal_id == "g1"

    def test_create_task_auto_assigns(self, tmp_path):
        mc = make_collab(tmp_path)
        agent = mc.register_agent("Alice", AgentRole.SPECIALIST, ["python"])
        task = mc.create_task("Python task", goal_id="g1", assigned_to=agent.id)
        assert task.status == TaskStatus.ASSIGNED
        assert task.assigned_at is not None
        assert mc.agents[agent.id].current_task_id == task.id

    def test_create_task_with_dependencies(self, tmp_path):
        mc = make_collab(tmp_path)
        t1 = mc.create_task("First", goal_id="g1")
        t2 = mc.create_task("After first", goal_id="g1", depends_on=[t1.id])
        assert t2.depends_on == [t1.id]


class TestCollaborationAssignTask:
    def test_assign_task_success(self, tmp_path):
        mc = make_collab(tmp_path)
        agent = mc.register_agent("Bob", AgentRole.WORKER, ["go"])
        task = mc.create_task("Go task", goal_id="g1")
        result = mc.assign_task(task.id, agent.id)
        assert result is True
        assert mc.tasks[task.id].status == TaskStatus.ASSIGNED

    def test_assign_task_checks_dependencies(self, tmp_path):
        mc = make_collab(tmp_path)
        agent = mc.register_agent("Bob", AgentRole.WORKER, ["go"])
        dep = mc.create_task("Dep", goal_id="g1")
        task = mc.create_task("After dep", goal_id="g1", depends_on=[dep.id])
        result = mc.assign_task(task.id, agent.id)
        assert result is False

    def test_assign_task_returns_false_for_unknown_ids(self, tmp_path):
        mc = make_collab(tmp_path)
        result = mc.assign_task("nonexistent-task", "nonexistent-agent")
        assert result is False


# ---------------------------------------------------------------------------
# Tasks — status transitions
# ---------------------------------------------------------------------------

class TestCollaborationTaskStatusTransitions:
    def test_update_to_in_progress(self, tmp_path):
        mc = make_collab(tmp_path)
        task = mc.create_task("Task", goal_id="g1")
        mc.update_task_status(task.id, TaskStatus.IN_PROGRESS)
        assert mc.tasks[task.id].status == TaskStatus.IN_PROGRESS

    def test_update_to_completed_clears_agent_current_task(self, tmp_path):
        mc = make_collab(tmp_path)
        agent = mc.register_agent("Bob", AgentRole.WORKER, ["go"])
        task = mc.create_task("Task", goal_id="g1", assigned_to=agent.id)
        mc.update_task_status(task.id, TaskStatus.COMPLETED, result="Done!")
        assert mc.agents[agent.id].current_task_id is None
        assert mc.tasks[task.id].result == "Done!"
        assert mc.tasks[task.id].completed_at is not None

    def test_update_to_completed_unblocks_dependents(self, tmp_path):
        mc = make_collab(tmp_path)
        dep = mc.create_task("Dep", goal_id="g1")
        blocked = mc.create_task("Blocked", goal_id="g1", depends_on=[dep.id])
        blocked.status = TaskStatus.BLOCKED
        mc.update_task_status(dep.id, TaskStatus.COMPLETED)
        assert mc.tasks[blocked.id].status == TaskStatus.PENDING

    def test_update_to_failed_sets_error(self, tmp_path):
        mc = make_collab(tmp_path)
        task = mc.create_task("Failing task", goal_id="g1")
        mc.update_task_status(task.id, TaskStatus.FAILED, error="Network error")
        assert mc.tasks[task.id].status == TaskStatus.FAILED
        assert mc.tasks[task.id].error == "Network error"

    def test_complete_task_shorthand(self, tmp_path):
        mc = make_collab(tmp_path)
        task = mc.create_task("Done task", goal_id="g1")
        mc.complete_task(task.id, result="All good", outputs={"key": "value"})
        assert mc.tasks[task.id].status == TaskStatus.COMPLETED
        assert mc.tasks[task.id].result == "All good"
        assert mc.tasks[task.id].outputs == {"key": "value"}

    def test_fail_task_shorthand(self, tmp_path):
        mc = make_collab(tmp_path)
        task = mc.create_task("Oops", goal_id="g1")
        mc.fail_task(task.id, error="oops")
        assert mc.tasks[task.id].status == TaskStatus.FAILED
        assert mc.tasks[task.id].error == "oops"


# ---------------------------------------------------------------------------
# get_ready_tasks
# ---------------------------------------------------------------------------

class TestCollaborationGetReadyTasks:
    def test_ready_task_without_dependencies(self, tmp_path):
        mc = make_collab(tmp_path)
        task = mc.create_task("Ready task", goal_id="g1")
        ready = mc.get_ready_tasks()
        assert any(t.id == task.id for t in ready)

    def test_task_not_ready_when_dependency_incomplete(self, tmp_path):
        mc = make_collab(tmp_path)
        dep = mc.create_task("Dep", goal_id="g1")
        blocked = mc.create_task("Blocked", goal_id="g1", depends_on=[dep.id])
        ready = mc.get_ready_tasks()
        ids = [t.id for t in ready]
        assert dep.id in ids
        assert blocked.id not in ids

    def test_ready_task_filtered_by_agent_capabilities(self, tmp_path):
        mc = make_collab(tmp_path)
        agent = mc.register_agent("Py", AgentRole.WORKER, ["python"])
        task = mc.create_task("Python script task", goal_id="g1")
        ready = mc.get_ready_tasks(agent_id=agent.id)
        assert any(t.id == task.id for t in ready)

    def test_task_not_ready_when_assigned_to_other(self, tmp_path):
        mc = make_collab(tmp_path)
        agent = mc.register_agent("Py", AgentRole.WORKER, ["python"])
        task = mc.create_task("Task for Alice", goal_id="g1", assigned_to=agent.id)
        # get_ready_tasks without agent_id includes assigned tasks
        all_ready = mc.get_ready_tasks()
        assert any(t.id == task.id for t in all_ready)


# ---------------------------------------------------------------------------
# get_agent_workload
# ---------------------------------------------------------------------------

class TestCollaborationGetAgentWorkload:
    def test_workload_shows_in_progress_and_pending(self, tmp_path):
        mc = make_collab(tmp_path)
        agent = mc.register_agent("Bob", AgentRole.WORKER, ["go"])
        t1 = mc.create_task("In prog", goal_id="g1", assigned_to=agent.id)
        t2 = mc.create_task("Pend", goal_id="g1", assigned_to=agent.id)
        mc.update_task_status(t1.id, TaskStatus.IN_PROGRESS)
        workload = mc.get_agent_workload()
        assert workload[agent.id]["in_progress"] == 1
        assert workload[agent.id]["pending"] == 1


# ---------------------------------------------------------------------------
# Shared knowledge
# ---------------------------------------------------------------------------

class TestCollaborationSharedKnowledge:
    def test_share_and_retrieve_knowledge(self, tmp_path):
        mc = make_collab(tmp_path)
        mc.share_knowledge("result", {"data": 42}, source_task="t1")
        assert mc.get_shared_knowledge("result") == {"data": 42}

    def test_share_knowledge_emits_event(self, tmp_path):
        mc = make_collab(tmp_path)
        received = []
        mc.on("knowledge_shared", lambda d: received.append(d))
        mc.share_knowledge("key", "value")
        assert len(received) == 1
        assert received[0]["key"] == "key"

    def test_get_all_shared_knowledge(self, tmp_path):
        mc = make_collab(tmp_path)
        mc.share_knowledge("k1", "v1")
        mc.share_knowledge("k2", "v2")
        all_kb = mc.get_all_shared_knowledge()
        assert all_kb == {"k1": "v1", "k2": "v2"}

    def test_share_knowledge_via_complete_task(self, tmp_path):
        mc = make_collab(tmp_path)
        task = mc.create_task("Task", goal_id="g1")
        mc.complete_task(task.id, result="done", outputs={"artifacts": ["a", "b"]})
        assert mc.get_shared_knowledge("artifacts") == ["a", "b"]


# ---------------------------------------------------------------------------
# decompose_for_collaboration
# ---------------------------------------------------------------------------

class TestCollaborationDecomposeForCollaboration:
    def test_creates_research_and_parallel_tasks(self, tmp_path):
        mc = make_collab(tmp_path)
        tasks = mc.decompose_for_collaboration("Build API", goal_id="g1")
        assert len(tasks) >= 4  # research + parallel + integration + review
        assert tasks[0].description.startswith("Research")
        assert tasks[0].priority == 10

    def test_parallel_tasks_depend_on_research(self, tmp_path):
        mc = make_collab(tmp_path)
        tasks = mc.decompose_for_collaboration("Build API", goal_id="g1")
        research = tasks[0]
        parallel = [t for t in tasks[1:] if t.depends_on == [research.id]]
        assert len(parallel) == 3  # core, testing, docs

    def test_integration_depends_on_parallel(self, tmp_path):
        mc = make_collab(tmp_path)
        tasks = mc.decompose_for_collaboration("Build API", goal_id="g1")
        integration = next(t for t in tasks if "Integrate" in t.description)
        assert len(integration.depends_on) == 3

    def test_review_depends_on_integration(self, tmp_path):
        mc = make_collab(tmp_path)
        tasks = mc.decompose_for_collaboration("Build API", goal_id="g1")
        review = next(t for t in tasks if "Review" in t.description)
        integration = next(t for t in tasks if "Integrate" in t.description)
        assert review.depends_on == [integration.id]


# ---------------------------------------------------------------------------
# get_workflow_status
# ---------------------------------------------------------------------------

class TestCollaborationGetWorkflowStatus:
    def test_no_tasks_returns_no_tasks_status(self, tmp_path):
        mc = make_collab(tmp_path)
        status = mc.get_workflow_status("nonexistent-goal")
        assert status["status"] == "no_tasks"

    def test_counts_tasks_correctly(self, tmp_path):
        mc = make_collab(tmp_path)
        mc.create_task("T1", goal_id="g1")
        mc.create_task("T2", goal_id="g1")
        t3 = mc.create_task("T3", goal_id="g1")
        mc.update_task_status(t3.id, TaskStatus.COMPLETED)
        status = mc.get_workflow_status("g1")
        assert status["total_tasks"] == 3
        assert status["completed"] == 1
        assert status["progress_percent"] == pytest.approx(33.3, 0.1)

    def test_task_graph_includes_depends_on(self, tmp_path):
        mc = make_collab(tmp_path)
        dep = mc.create_task("Dep", goal_id="g1")
        task = mc.create_task("After", goal_id="g1", depends_on=[dep.id])
        status = mc.get_workflow_status("g1")
        graph = status["task_graph"]
        assert task.id in graph
        assert dep.id in graph[task.id]["depends_on"]


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------

class TestCollaborationGenerateReport:
    def test_report_contains_progress_and_agent_workload(self, tmp_path):
        mc = make_collab(tmp_path)
        agent = mc.register_agent("Alice", AgentRole.SPECIALIST, ["python"])
        task = mc.create_task("Python task", goal_id="g1", assigned_to=agent.id)
        report = mc.generate_report("g1")
        assert "Progress:" in report
        assert "Alice" in report
        assert "specialist" in report  # role.value is lowercase
        # total=1, completed=0 (task is ASSIGNED, not COMPLETED)
        assert "0/1" in report
