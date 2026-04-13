"""Tests for scheduler.py — TaskScheduler and ScheduledTask."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys
from pathlib import Path as PP
sys.path.insert(0, str(PP(__file__).parent.parent))

from client.scheduler import TaskScheduler, ScheduledTask


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_scheduler(tmp_path) -> TaskScheduler:
    """TaskScheduler backed by a temp file."""
    path = tmp_path / "tasks.json"
    with patch.object(TaskScheduler, '_get_default_path', return_value=path):
        return TaskScheduler()


def add_task(scheduler: TaskScheduler, command: str, delay_minutes: int, **kwargs):
    return scheduler.add_task(command, delay_minutes, **kwargs)


# ---------------------------------------------------------------------------
# ScheduledTask dataclass
# ---------------------------------------------------------------------------

class TestScheduledTaskFromDict:
    def test_from_dict_roundtrip(self):
        d = {
            "id": "abc12345",
            "command": "echo hello",
            "delay_minutes": 5,
            "created_at": "2025-01-01T00:00:00",
            "execute_at": "2025-01-01T00:05:00",
            "status": "pending",
            "original_message_id": "msg-001",
            "lark_open_id": "ou_abc",
        }
        t = ScheduledTask.from_dict(d)
        assert t.id == "abc12345"
        assert t.command == "echo hello"
        assert t.delay_minutes == 5
        assert t.status == "pending"
        assert t.original_message_id == "msg-001"
        assert t.lark_open_id == "ou_abc"

    def test_from_dict_defaults(self):
        d = {"id": "x", "command": "c", "delay_minutes": 1,
             "created_at": "t", "execute_at": "t", "status": "pending"}
        t = ScheduledTask.from_dict(d)
        assert t.original_message_id is None
        assert t.lark_open_id is None


# ---------------------------------------------------------------------------
# TaskScheduler — add / cancel / mark
# ---------------------------------------------------------------------------

class TestSchedulerAddTask:
    def test_add_task_returns_id(self, tmp_path):
        ts = make_scheduler(tmp_path)
        tid = ts.add_task("echo hello", delay_minutes=5)
        assert isinstance(tid, str)
        assert len(tid) <= 8

    def test_add_task_persists_to_file(self, tmp_path):
        path = tmp_path / "tasks.json"
        with patch.object(TaskScheduler, '_get_default_path', return_value=path):
            ts = TaskScheduler()
            tid = ts.add_task("echo hello", delay_minutes=5)
        # reopen to verify file round-trip
        with open(path) as f:
            data = json.load(f)
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["command"] == "echo hello"

    def test_add_task_sets_correct_execute_at(self, tmp_path):
        ts = make_scheduler(tmp_path)
        before = datetime.now()
        tid = ts.add_task("echo hello", delay_minutes=10)
        after = datetime.now()
        task = next(t for t in ts.tasks if t.id == tid)
        execute_at = datetime.fromisoformat(task.execute_at)
        # Should be ~10 minutes from now
        expected_min = before + timedelta(minutes=10)
        expected_max = after + timedelta(minutes=10)
        assert expected_min <= execute_at <= expected_max

    def test_add_task_with_message_ids(self, tmp_path):
        ts = make_scheduler(tmp_path)
        tid = ts.add_task(
            "echo hi", delay_minutes=1,
            original_message_id="msg-123",
            lark_open_id="ou_abc",
        )
        task = next(t for t in ts.tasks if t.id == tid)
        assert task.original_message_id == "msg-123"
        assert task.lark_open_id == "ou_abc"

    def test_add_task_sets_pending_status(self, tmp_path):
        ts = make_scheduler(tmp_path)
        tid = ts.add_task("echo hello", delay_minutes=5)
        task = next(t for t in ts.tasks if t.id == tid)
        assert task.status == "pending"


# ---------------------------------------------------------------------------
# TaskScheduler — get_tasks / get_pending_tasks
# ---------------------------------------------------------------------------

class TestSchedulerGetters:
    def test_get_tasks_returns_all(self, tmp_path):
        ts = make_scheduler(tmp_path)
        ts.add_task("task1", delay_minutes=1)
        ts.add_task("task2", delay_minutes=2)
        assert len(ts.get_tasks()) == 2

    def test_get_pending_tasks_filters_correctly(self, tmp_path):
        ts = make_scheduler(tmp_path)
        tid1 = ts.add_task("task1", delay_minutes=1)
        tid2 = ts.add_task("task2", delay_minutes=2)
        ts.mark_executing(tid1)
        ts.mark_completed(tid2)
        pending = ts.get_pending_tasks()
        assert len(pending) == 0


# ---------------------------------------------------------------------------
# TaskScheduler — get_due_tasks
# ---------------------------------------------------------------------------

class TestSchedulerGetDueTasks:
    def test_task_not_due_when_future(self, tmp_path):
        ts = make_scheduler(tmp_path)
        ts.add_task("future task", delay_minutes=60)
        assert ts.get_due_tasks() == []

    def test_task_due_when_in_past(self, tmp_path):
        ts = make_scheduler(tmp_path)
        # Manually create a task already past due
        from client.scheduler import ScheduledTask
        past = datetime.now() - timedelta(minutes=5)
        past_task = ScheduledTask(
            id="past001",
            command="past task",
            delay_minutes=1,
            created_at=past.isoformat(),
            execute_at=past.isoformat(),
            status="pending",
        )
        ts.tasks.append(past_task)
        due = ts.get_due_tasks()
        assert len(due) == 1
        assert due[0].id == "past001"

    def test_executing_task_not_due(self, tmp_path):
        ts = make_scheduler(tmp_path)
        past = datetime.now() - timedelta(minutes=5)
        task = ScheduledTask(
            id="exec001",
            command="exec task",
            delay_minutes=1,
            created_at=past.isoformat(),
            execute_at=past.isoformat(),
            status="executing",
        )
        ts.tasks.append(task)
        assert ts.get_due_tasks() == []


# ---------------------------------------------------------------------------
# TaskScheduler — mark_executing / mark_completed / cancel_task
# ---------------------------------------------------------------------------

class TestSchedulerStateTransitions:
    def test_mark_executing_changes_status(self, tmp_path):
        ts = make_scheduler(tmp_path)
        tid = ts.add_task("task", delay_minutes=1)
        ts.mark_executing(tid)
        task = next(t for t in ts.tasks if t.id == tid)
        assert task.status == "executing"

    def test_mark_completed_changes_status(self, tmp_path):
        ts = make_scheduler(tmp_path)
        tid = ts.add_task("task", delay_minutes=1)
        ts.mark_completed(tid)
        task = next(t for t in ts.tasks if t.id == tid)
        assert task.status == "completed"

    def test_cancel_task_changes_status(self, tmp_path):
        ts = make_scheduler(tmp_path)
        tid = ts.add_task("task", delay_minutes=1)
        result = ts.cancel_task(tid)
        assert result is True
        task = next(t for t in ts.tasks if t.id == tid)
        assert task.status == "cancelled"

    def test_cancel_task_returns_false_when_not_found(self, tmp_path):
        ts = make_scheduler(tmp_path)
        result = ts.cancel_task("nonexistent")
        assert result is False

    def test_cancel_task_returns_false_when_not_pending(self, tmp_path):
        ts = make_scheduler(tmp_path)
        tid = ts.add_task("task", delay_minutes=1)
        ts.mark_executing(tid)
        result = ts.cancel_task(tid)
        assert result is False


# ---------------------------------------------------------------------------
# TaskScheduler — remove_completed_tasks
# ---------------------------------------------------------------------------

class TestSchedulerRemoveCompletedTasks:
    def test_removes_old_completed_tasks(self, tmp_path):
        ts = make_scheduler(tmp_path)
        old_time = datetime.now() - timedelta(hours=25)
        old_task = ScheduledTask(
            id="old001", command="old", delay_minutes=1,
            created_at=old_time.isoformat(),
            execute_at=old_time.isoformat(),
            status="completed",
        )
        recent_time = datetime.now()
        recent_task = ScheduledTask(
            id="recent001", command="recent", delay_minutes=1,
            created_at=recent_time.isoformat(),
            execute_at=recent_time.isoformat(),
            status="completed",
        )
        ts.tasks.extend([old_task, recent_task])
        ts.remove_completed_tasks(older_than_hours=24)
        ids = {t.id for t in ts.tasks}
        assert "old001" not in ids
        assert "recent001" in ids

    def test_keeps_completed_tasks_within_window(self, tmp_path):
        ts = make_scheduler(tmp_path)
        recent_time = datetime.now() - timedelta(hours=12)
        task = ScheduledTask(
            id="keep001", command="keep", delay_minutes=1,
            created_at=recent_time.isoformat(),
            execute_at=recent_time.isoformat(),
            status="completed",
        )
        ts.tasks.append(task)
        ts.remove_completed_tasks(older_than_hours=24)
        assert len(ts.tasks) == 1

    def test_keeps_non_completed_tasks(self, tmp_path):
        ts = make_scheduler(tmp_path)
        old_time = datetime.now() - timedelta(hours=48)
        task = ScheduledTask(
            id="pending001", command="pending", delay_minutes=1,
            created_at=old_time.isoformat(),
            execute_at=old_time.isoformat(),
            status="pending",
        )
        ts.tasks.append(task)
        ts.remove_completed_tasks(older_than_hours=24)
        assert len(ts.tasks) == 1


# ---------------------------------------------------------------------------
# TaskScheduler — format_tasks_list
# ---------------------------------------------------------------------------

class TestSchedulerFormatTasksList:
    def test_format_empty(self, tmp_path):
        ts = make_scheduler(tmp_path)
        out = ts.format_tasks_list()
        assert "没有待执行的任务" in out

    def test_format_shows_pending_task(self, tmp_path):
        ts = make_scheduler(tmp_path)
        ts.add_task("echo hello", delay_minutes=1)
        out = ts.format_tasks_list()
        assert "echo hello" in out
        assert "待执行任务" in out

    def test_format_shows_executing_task(self, tmp_path):
        ts = make_scheduler(tmp_path)
        tid = ts.add_task("running", delay_minutes=1)
        ts.mark_executing(tid)
        out = ts.format_tasks_list()
        assert "running" in out
        assert "🔄" in out  # executing emoji


# ---------------------------------------------------------------------------
# TaskScheduler — load from file
# ---------------------------------------------------------------------------

class TestSchedulerLoad:
    def test_load_restores_tasks(self, tmp_path):
        path = tmp_path / "tasks.json"
        past = datetime.now() - timedelta(minutes=5)
        data = {
            "tasks": [{
                "id": "loaded001",
                "command": "loaded task",
                "delay_minutes": 5,
                "created_at": past.isoformat(),
                "execute_at": past.isoformat(),
                "status": "pending",
                "original_message_id": None,
                "lark_open_id": None,
            }]
        }
        path.write_text(json.dumps(data))

        with patch.object(TaskScheduler, '_get_default_path', return_value=path):
            ts = TaskScheduler()
        assert len(ts.tasks) == 1
        assert ts.tasks[0].command == "loaded task"

    def test_load_corrupt_file_initialises_empty(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json{{{")
        with patch.object(TaskScheduler, '_get_default_path', return_value=path):
            ts = TaskScheduler()
        assert ts.tasks == []
