"""Tests for task_queue.py - TaskQueue and QueueManager."""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from unittest.mock import MagicMock

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.task_queue import TaskQueue, QueuedTask
from client.profile import Task, TaskStatus


class TestTaskQueueEnqueue:
    """Test TaskQueue enqueue operations."""

    def setup_method(self):
        self.profile = MagicMock()
        self.queue = TaskQueue(self.profile)

    def test_enqueue_normal_task_goes_to_back(self):
        task1 = Task(id="t1", description="Task 1", goal_id="g1")
        task2 = Task(id="t2", description="Task 2", goal_id="g1")

        self.queue.enqueue(task1)
        self.queue.enqueue(task2)

        assert self.queue.size == 2
        assert self.queue.dequeue().task.id == "t1"
        assert self.queue.dequeue().task.id == "t2"

    def test_enqueue_user_task_goes_to_front(self):
        task1 = Task(id="t1", description="Task 1", goal_id="g1")
        task2 = Task(id="t2", description="Task 2", goal_id="g1", priority=999)

        self.queue.enqueue(task1)
        self.queue.enqueue(task2, user_initiated=True)

        assert self.queue.dequeue().task.id == "t2"
        assert self.queue.dequeue().task.id == "t1"

    def test_enqueue_multiple_user_tasks_all_at_front(self):
        task1 = Task(id="t1", description="Task 1", goal_id="g1")
        task2 = Task(id="t2", description="Task 2", goal_id="g1")
        task3 = Task(id="t3", description="Task 3", goal_id="g1")

        self.queue.enqueue(task1)
        self.queue.enqueue(task2, user_initiated=True)
        self.queue.enqueue(task3, user_initiated=True)

        assert self.queue.dequeue().task.id == "t3"
        assert self.queue.dequeue().task.id == "t2"
        assert self.queue.dequeue().task.id == "t1"


class TestTaskQueueDequeue:
    """Test TaskQueue dequeue operations."""

    def setup_method(self):
        self.profile = MagicMock()
        self.queue = TaskQueue(self.profile)

    def test_dequeue_empty_returns_none(self):
        result = self.queue.dequeue()
        assert result is None

    def test_dequeue_returns_front_task(self):
        task1 = Task(id="t1", description="Task 1", goal_id="g1")
        task2 = Task(id="t2", description="Task 2", goal_id="g1")

        self.queue.enqueue(task1)
        self.queue.enqueue(task2)

        result = self.queue.dequeue()
        assert result.task.id == "t1"

    def test_dequeue_removes_from_queue(self):
        task = Task(id="t1", description="Task 1", goal_id="g1")
        self.queue.enqueue(task)

        self.queue.dequeue()

        assert self.queue.is_empty


class TestTaskQueuePeek:
    """Test TaskQueue peek operation."""

    def setup_method(self):
        self.profile = MagicMock()
        self.queue = TaskQueue(self.profile)

    def test_peek_empty_returns_none(self):
        assert self.queue.peek() is None

    def test_peek_returns_front_without_removing(self):
        task1 = Task(id="t1", description="Task 1", goal_id="g1")
        task2 = Task(id="t2", description="Task 2", goal_id="g1")

        self.queue.enqueue(task1)
        self.queue.enqueue(task2)

        result = self.queue.peek()
        assert result.task.id == "t1"
        assert self.queue.size == 2


class TestTaskQueueProperties:
    """Test TaskQueue properties."""

    def setup_method(self):
        self.profile = MagicMock()
        self.queue = TaskQueue(self.profile)

    def test_is_empty_true_when_empty(self):
        assert self.queue.is_empty is True

    def test_is_empty_false_when_not_empty(self):
        task = Task(id="t1", description="Task 1", goal_id="g1")
        self.queue.enqueue(task)
        assert self.queue.is_empty is False

    def test_size_returns_count(self):
        task1 = Task(id="t1", description="Task 1", goal_id="g1")
        task2 = Task(id="t2", description="Task 2", goal_id="g1")

        self.queue.enqueue(task1)
        self.queue.enqueue(task2)

        assert self.queue.size == 2


class TestTaskQueueExecuting:
    """Test TaskQueue executing state."""

    def setup_method(self):
        self.profile = MagicMock()
        self.queue = TaskQueue(self.profile)

    def test_mark_executing_sets_current(self):
        task = Task(id="t1", description="Task 1", goal_id="g1")
        queued = QueuedTask(task=task)

        self.queue.mark_executing(queued)

        assert self.queue.currently_executing == queued

    def test_mark_done_clears_current(self):
        task = Task(id="t1", description="Task 1", goal_id="g1")
        queued = QueuedTask(task=task)
        self.queue.mark_executing(queued)

        self.queue.mark_done()

        assert self.queue.currently_executing is None


class TestTaskQueueGetAll:
    """Test TaskQueue get_all operation."""

    def setup_method(self):
        self.profile = MagicMock()
        self.queue = TaskQueue(self.profile)

    def test_get_all_returns_list(self):
        task1 = Task(id="t1", description="Task 1", goal_id="g1")
        task2 = Task(id="t2", description="Task 2", goal_id="g1")

        self.queue.enqueue(task1)
        self.queue.enqueue(task2)

        result = self.queue.get_all()

        assert isinstance(result, list)
        assert len(result) == 2
