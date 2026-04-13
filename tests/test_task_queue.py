"""Tests for task_queue.py — TaskQueue and QueueManager."""

import asyncio
from collections import deque
from unittest.mock import MagicMock

import pytest

import sys
from pathlib import Path as PP
sys.path.insert(0, str(PP(__file__).parent.parent))

from client.task_queue import TaskQueue, QueueManager, QueuedTask
from client.profile import Task, TaskStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_task(task_id: str, description: str = "task", goal_id: str = "g0") -> Task:
    return Task(id=task_id, description=description, goal_id=goal_id)


# ---------------------------------------------------------------------------
# QueuedTask
# ---------------------------------------------------------------------------

class TestQueuedTask:
    def test_defaults_to_not_user_initiated(self):
        qt = QueuedTask(task=make_task("t1"))
        assert qt.is_user_initiated is False
        assert qt.inserted_at != ""

    def test_accepts_user_initiated_flag(self):
        qt = QueuedTask(task=make_task("t1"), is_user_initiated=True)
        assert qt.is_user_initiated is True


# ---------------------------------------------------------------------------
# TaskQueue — enqueue / dequeue
# ---------------------------------------------------------------------------

class TestTaskQueueBasic:
    def test_is_empty_true_when_new(self):
        tq = TaskQueue(MagicMock())
        assert tq.is_empty is True
        assert tq.size == 0

    def test_enqueue_normal_appends_to_back(self):
        tq = TaskQueue(MagicMock())
        tq.enqueue(make_task("t1"), user_initiated=False)
        tq.enqueue(make_task("t2"), user_initiated=False)
        tq.enqueue(make_task("t3"), user_initiated=False)
        assert tq.size == 3
        assert tq.dequeue().task.id == "t1"
        assert tq.dequeue().task.id == "t2"
        assert tq.dequeue().task.id == "t3"

    def test_enqueue_user_initiated_inserts_at_front(self):
        tq = TaskQueue(MagicMock())
        tq.enqueue(make_task("t1"), user_initiated=False)
        tq.enqueue(make_task("urgent"), user_initiated=True)
        tq.enqueue(make_task("t3"), user_initiated=False)
        assert tq.dequeue().task.id == "urgent"
        assert tq.dequeue().task.id == "t1"
        assert tq.dequeue().task.id == "t3"

    def test_enqueue_user_initiated_multiple_preserves_order(self):
        tq = TaskQueue(MagicMock())
        tq.enqueue(make_task("first"), user_initiated=True)
        tq.enqueue(make_task("second"), user_initiated=True)
        tq.enqueue(make_task("third"), user_initiated=True)
        # Last inserted is at front (appendleft per item)
        assert tq.dequeue().task.id == "third"
        assert tq.dequeue().task.id == "second"
        assert tq.dequeue().task.id == "first"

    def test_dequeue_returns_none_when_empty(self):
        tq = TaskQueue(MagicMock())
        assert tq.dequeue() is None

    def test_dequeue_removes_front(self):
        tq = TaskQueue(MagicMock())
        tq.enqueue(make_task("t1"))
        tq.enqueue(make_task("t2"))
        assert tq.dequeue().task.id == "t1"
        assert tq.size == 1

    def test_peek_does_not_remove(self):
        tq = TaskQueue(MagicMock())
        tq.enqueue(make_task("t1"))
        tq.enqueue(make_task("t2"))
        assert tq.peek().task.id == "t1"
        assert tq.size == 2

    def test_peek_returns_none_when_empty(self):
        assert TaskQueue(MagicMock()).peek() is None

    def test_get_all_returns_all_tasks(self):
        tq = TaskQueue(MagicMock())
        tq.enqueue(make_task("t1"))
        tq.enqueue(make_task("t2"))
        all_tasks = tq.get_all()
        assert len(all_tasks) == 2
        assert [qt.task.id for qt in all_tasks] == ["t1", "t2"]


# ---------------------------------------------------------------------------
# TaskQueue — executing state
# ---------------------------------------------------------------------------

class TestTaskQueueExecuting:
    def test_currently_executing_none_when_idle(self):
        assert TaskQueue(MagicMock()).currently_executing is None

    def test_mark_executing_sets_currently_executing(self):
        tq = TaskQueue(MagicMock())
        qt = QueuedTask(task=make_task("t1"))
        tq.mark_executing(qt)
        assert tq.currently_executing is qt
        assert tq.currently_executing.task.id == "t1"

    def test_mark_done_clears_currently_executing(self):
        tq = TaskQueue(MagicMock())
        qt = QueuedTask(task=make_task("t1"))
        tq.mark_executing(qt)
        tq.mark_done()
        assert tq.currently_executing is None

    def test_mark_executing_does_not_remove_from_queue(self):
        tq = TaskQueue(MagicMock())
        qt = QueuedTask(task=make_task("t1"))
        tq.enqueue(make_task("t2"))
        tq.enqueue(make_task("t3"))
        tq.mark_executing(qt)
        assert tq.size == 2


# ---------------------------------------------------------------------------
# TaskQueue — format_queue_status
# ---------------------------------------------------------------------------

class TestTaskQueueFormat:
    def test_format_empty_queue(self):
        out = TaskQueue(MagicMock()).format_queue_status()
        assert "Task Queue" in out
        assert "(empty)" in out

    def test_format_shows_executing_task(self):
        tq = TaskQueue(MagicMock())
        qt = QueuedTask(task=make_task("t1", description="MyTask"), is_user_initiated=True)
        tq.mark_executing(qt)
        out = tq.format_queue_status()
        assert "MyTask" in out
        assert "Executing" in out

    def test_format_shows_pending_count(self):
        tq = TaskQueue(MagicMock())
        tq.enqueue(make_task("t1", description="First"))
        tq.enqueue(make_task("t2", description="Second"))
        out = tq.format_queue_status()
        assert "Pending" in out
        assert "First" in out
        assert "Second" in out

    def test_format_user_task_has_bullet_marker(self):
        tq = TaskQueue(MagicMock())
        tq.enqueue(make_task("urgent"), user_initiated=True)
        out = tq.format_queue_status()
        assert "🔴" in out  # user task marker


# ---------------------------------------------------------------------------
# QueueManager — add tasks
# ---------------------------------------------------------------------------

class TestQueueManagerAddTasks:
    def test_add_user_task_creates_task_and_enqueues(self):
        pm = MagicMock()
        pm.insert_task_front = MagicMock(return_value=make_task("t1"))
        qm = QueueManager(pm)

        task = qm.add_user_task("User task", "g0")

        pm.insert_task_front.assert_called_once_with("User task", "g0", priority=999)
        assert qm.queue.size == 1

    def test_add_autonomous_task_creates_task_and_enqueues(self):
        pm = MagicMock()
        pm.add_task = MagicMock(return_value=make_task("t2"))
        qm = QueueManager(pm)

        task = qm.add_autonomous_task("Autonomous task", "g0")

        pm.add_task.assert_called_once_with("Autonomous task", "g0")
        assert qm.queue.size == 1

    def test_add_user_task_sets_user_initiated_flag(self):
        pm = MagicMock()
        pm.insert_task_front = MagicMock(return_value=make_task("t1"))
        qm = QueueManager(pm)
        qm.add_user_task("Urgent", "g0")
        assert qm.queue.dequeue().is_user_initiated is True

    def test_add_autonomous_task_sets_user_initiated_false(self):
        pm = MagicMock()
        pm.add_task = MagicMock(return_value=make_task("t1"))
        qm = QueueManager(pm)
        qm.add_autonomous_task("Background", "g0")
        assert qm.queue.dequeue().is_user_initiated is False

    def test_add_user_task_returns_created_task(self):
        pm = MagicMock()
        expected = make_task("t1")
        pm.insert_task_front = MagicMock(return_value=expected)
        qm = QueueManager(pm)
        assert qm.add_user_task("Desc", "g0").id == "t1"


# ---------------------------------------------------------------------------
# QueueManager — get_next_task
# ---------------------------------------------------------------------------

class TestQueueManagerGetNextTask:
    @pytest.mark.asyncio
    async def test_returns_from_queue_when_available(self):
        pm = MagicMock()
        pm.insert_task_front = MagicMock(return_value=make_task("qt_t1"))
        qm = QueueManager(pm)
        qm.add_user_task("Queued task", "g0")

        result = await qm.get_next_task()

        assert result is not None
        assert result.task.id == "qt_t1"
        pm.pop_top_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_profile_when_queue_empty(self):
        pm = MagicMock()
        pm.pop_top_task = MagicMock(return_value=make_task("profile_t1"))
        qm = QueueManager(pm)

        result = await qm.get_next_task()

        assert result is not None
        assert result.task.id == "profile_t1"
        assert result.is_user_initiated is False
        pm.pop_top_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_both_empty(self):
        pm = MagicMock()
        pm.pop_top_task = MagicMock(return_value=None)
        qm = QueueManager(pm)

        result = await qm.get_next_task()

        assert result is None

    @pytest.mark.asyncio
    async def test_exhausts_queue_before_falling_back(self):
        pm = MagicMock()
        pm.add_task = MagicMock(return_value=make_task("auto1"))
        pm.pop_top_task = MagicMock(return_value=make_task("profile_fallback"))
        qm = QueueManager(pm)
        qm.add_autonomous_task("Task 1", "g0")
        qm.add_autonomous_task("Task 2", "g0")

        first = await qm.get_next_task()
        second = await qm.get_next_task()
        fallback = await qm.get_next_task()

        assert first.task.id == "auto1"
        assert second.task.id == "auto1"  # queue exhausted, profile fallback called once
        pm.pop_top_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_profile_fallback_marks_is_user_initiated_false(self):
        pm = MagicMock()
        pm.pop_top_task = MagicMock(return_value=make_task("pf_t1"))
        qm = QueueManager(pm)
        result = await qm.get_next_task()
        assert result.is_user_initiated is False


# ---------------------------------------------------------------------------
# QueueManager — requeue_front
# ---------------------------------------------------------------------------

class TestQueueManagerRequeueFront:
    def test_requeue_front_prepends_task(self):
        pm = MagicMock()
        qm = QueueManager(pm)
        qm.queue.enqueue(make_task("t1"))
        qm.queue.enqueue(make_task("t2"))
        requeued = QueuedTask(task=make_task("executing"))

        qm.requeue_front(requeued)

        assert qm.queue.dequeue().task.id == "executing"

    def test_requeue_front_clears_currently_executing(self):
        pm = MagicMock()
        qm = QueueManager(pm)
        qm.queue.enqueue(make_task("t1"))
        qt = QueuedTask(task=make_task("executing"))
        qm.queue.mark_executing(qt)
        qm.requeue_front(qt)
        assert qm.queue.currently_executing is None

    def test_requeue_front_on_empty_queue(self):
        pm = MagicMock()
        qm = QueueManager(pm)
        qt = QueuedTask(task=make_task("solo"))
        qm.requeue_front(qt)
        assert qm.queue.dequeue().task.id == "solo"


# ---------------------------------------------------------------------------
# QueueManager — format_status
# ---------------------------------------------------------------------------

class TestQueueManagerFormatStatus:
    def test_format_status_returns_queue_status(self):
        pm = MagicMock()
        pm.add_task = MagicMock(return_value=make_task("t1", description="MyTask"))
        qm = QueueManager(pm)
        qm.add_autonomous_task("MyTask", "g0")
        out = qm.format_status()
        assert "Task Queue" in out
        assert "MyTask" in out


# ---------------------------------------------------------------------------
# Priority integration: user interrupts autonomous queue
# ---------------------------------------------------------------------------

class TestQueuePriorityIntegration:
    @pytest.mark.asyncio
    async def test_user_task_runs_before_autonomous_tasks(self):
        auto1 = make_task("auto1", description="Auto task")
        auto2 = make_task("auto2", description="Auto task 2")
        user_task = make_task("user1", description="User interrupt")
        pm = MagicMock()
        pm.add_task = MagicMock(side_effect=[auto1, auto2])
        pm.insert_task_front = MagicMock(return_value=user_task)
        pm.pop_top_task = MagicMock(return_value=None)
        qm = QueueManager(pm)

        qm.add_autonomous_task("Auto task", "g0")
        qm.add_autonomous_task("Auto task 2", "g0")
        qm.add_user_task("User interrupt", "g0")

        first = await qm.get_next_task()
        second = await qm.get_next_task()
        third = await qm.get_next_task()

        assert first.task.description == "User interrupt"
        assert first.is_user_initiated is True
        assert second.task.description == "Auto task"
        assert third.task.description == "Auto task 2"

    @pytest.mark.asyncio
    async def test_ratelimited_task_requeued_at_front_runs_next(self):
        """Task hit rate-limit, got requeued at front, should run before other autons."""
        auto1 = make_task("a1", description="Auto 1")
        pm = MagicMock()
        pm.add_task = MagicMock(return_value=auto1)
        pm.pop_top_task = MagicMock(return_value=None)
        qm = QueueManager(pm)

        qm.add_autonomous_task("Auto 1", "g0")
        qm.add_autonomous_task("Auto 2", "g0")

        executing = await qm.get_next_task()       # Auto 1 starts
        qm.queue.mark_executing(executing)

        ratelimited = QueuedTask(task=make_task("rl", description="ratelimited"), is_user_initiated=False)
        qm.requeue_front(ratelimited)              # push back to front
        qm.queue.mark_done()

        next_task = await qm.get_next_task()
        assert next_task.task.description == "ratelimited"

    @pytest.mark.asyncio
    async def test_multiple_user_interrupts_preserve_relative_order(self):
        """Multiple user interrupts interleave correctly with autonomous tasks."""
        auto1 = make_task("a1", description="Auto 1")
        auto2 = make_task("a2", description="Auto 2")
        userA = make_task("uA", description="User A")
        userB = make_task("uB", description="User B")
        pm = MagicMock()
        pm.add_task = MagicMock(side_effect=[auto1, auto2])
        pm.insert_task_front = MagicMock(side_effect=[userA, userB])
        pm.pop_top_task = MagicMock(return_value=None)
        qm = QueueManager(pm)

        qm.add_autonomous_task("Auto 1", "g0")          # pos 1
        qm.add_user_task("User A", "g0")                # pos 0 (front)
        qm.add_autonomous_task("Auto 2", "g0")          # pos 2
        qm.add_user_task("User B", "g0")                # pos 0 (front, most recent)

        order = []
        for _ in range(4):
            qt = await qm.get_next_task()
            order.append((qt.task.description, qt.is_user_initiated))

        # User B most recent → first out; then User A; then Auto FIFO
        assert order[0] == ("User B", True)
        assert order[1] == ("User A", True)
        assert order[2] == ("Auto 1", False)
        assert order[3] == ("Auto 2", False)
