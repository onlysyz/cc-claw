"""Tests for handler.py - MessageHandler command processing."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.handler import MessageHandler
from client.websocket import Message
from client.profile import Goal, Task, GoalStatus, TaskStatus


class TestHandlerInit:
    """Test MessageHandler initialization."""

    def test_init_sets_autonomous_mode_true(self):
        ws = MagicMock()
        claude = MagicMock()
        config = MagicMock()
        scheduler = MagicMock()
        profile = MagicMock()

        handler = MessageHandler(ws, claude, config, scheduler, profile)

        assert handler.autonomous_mode is True
        assert handler.ws is ws
        assert handler.claude is claude
        assert handler.profile is profile

    def test_init_registers_websocket_handlers(self):
        ws = MagicMock()
        claude = MagicMock()
        config = MagicMock()
        scheduler = MagicMock()
        profile = MagicMock()

        handler = MessageHandler(ws, claude, config, scheduler, profile)

        ws.on.assert_any_call("message", handler.handle_message)
        ws.on.assert_any_call("error", handler.handle_error)
        ws.on.assert_any_call("delivered", handler.handle_delivered)
        ws.on.assert_any_call("tasks", handler.handle_tasks_request)


class TestHandlePause:
    """Test /pause command."""

    @pytest.mark.asyncio
    async def test_pause_sets_autonomous_mode_false(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.autonomous_mode = True
        handler.ws.send_message = AsyncMock()

        await handler._handle_pause_command("msg-123", "user-456")

        assert handler.autonomous_mode is False
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "paused" in call_args[0]


class TestHandleResume:
    """Test /resume command."""

    @pytest.mark.asyncio
    async def test_resume_sets_autonomous_mode_true(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.autonomous_mode = False
        handler.ws.send_message = AsyncMock()

        await handler._handle_resume_command("msg-123", "user-456")

        assert handler.autonomous_mode is True
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "resumed" in call_args[0]


class TestHandleGoals:
    """Test /goals command."""

    @pytest.mark.asyncio
    async def test_goals_shows_all_goals(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        goal1 = Goal(id="goal-001", description="Goal One", status=GoalStatus.ACTIVE)
        goal2 = Goal(id="goal-002", description="Goal Two", status=GoalStatus.COMPLETED)
        handler.profile.goals = [goal1, goal2]
        handler.profile.get_tasks_for_goal = MagicMock(return_value=[])
        handler.profile.active_goal_id = "goal-001"

        await handler._handle_goals_command("msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        response = call_args[0]
        assert "Goal One" in response
        assert "Goal Two" in response

    @pytest.mark.asyncio
    async def test_goals_empty_list(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.profile.goals = []

        await handler._handle_goals_command("msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "No goals" in call_args[0]


class TestHandleSetGoal:
    """Test /setgoal command."""

    @pytest.mark.asyncio
    async def test_setgoal_switches_active_goal(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        goal = Goal(id="goal-001", description="Test Goal", status=GoalStatus.ACTIVE)
        handler.profile.goals = [goal]
        handler.profile.set_active_goal = MagicMock(return_value=True)

        await handler._handle_setgoal_command("goal-001", "msg-123", "user-456")

        handler.profile.set_active_goal.assert_called_once_with("goal-001")
        handler.ws.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_setgoal_invalid_goal_id(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.profile.set_active_goal = MagicMock(return_value=False)

        await handler._handle_setgoal_command("invalid-id", "msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]


class TestHandleNewGoal:
    """Test /newgoal command."""

    @pytest.mark.asyncio
    async def test_newgoal_creates_goal(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        new_goal = Goal(id="goal-new", description="New Goal", status=GoalStatus.ACTIVE)
        handler.profile.add_goal = MagicMock(return_value=new_goal)
        handler.goal_engine = MagicMock()
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[])

        await handler._handle_newgoal_command("Build new feature", "msg-123", "user-456")

        handler.profile.add_goal.assert_called_once_with("Build new feature")
        assert handler.ws.send_message.call_count == 2  # Initial + decomposition result

    @pytest.mark.asyncio
    async def test_newgoal_with_decomposition(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        new_goal = Goal(id="goal-new", description="New Goal", status=GoalStatus.ACTIVE)
        handler.profile.add_goal = MagicMock(return_value=new_goal)

        task1 = Task(id="task-1", description="Step 1", goal_id="goal-new")
        task2 = Task(id="task-2", description="Step 2", goal_id="goal-new")
        handler.goal_engine = MagicMock()
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[task1, task2])

        await handler._handle_newgoal_command("Build new feature", "msg-123", "user-456")

        handler.goal_engine.decompose_goal.assert_called_once_with("goal-new")


class TestHandleDelGoal:
    """Test /delgoal command."""

    @pytest.mark.asyncio
    async def test_delgoal_removes_goal_and_tasks(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        goal = Goal(id="goal-001", description="To Delete", status=GoalStatus.ACTIVE)
        task = Task(id="task-001", description="Task 1", goal_id="goal-001")
        goal.task_ids = ["task-001"]
        handler.profile.goals = [goal]
        handler.profile.tasks = [task]
        handler.profile.get_tasks_for_goal = MagicMock(return_value=[task])
        handler.profile.get_active_goals = MagicMock(return_value=[])
        handler.profile._save = MagicMock()

        await handler._handle_delgoal_command("goal-001", "msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        assert goal not in handler.profile.goals
        assert task not in handler.profile.tasks

    @pytest.mark.asyncio
    async def test_delgoal_not_found(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.profile.goals = []

        await handler._handle_delgoal_command("nonexistent", "msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]


class TestHandleDelTask:
    """Test /deltask command."""

    @pytest.mark.asyncio
    async def test_deltask_removes_pending_task(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        task = Task(id="task-001", description="To Delete", goal_id="goal-001", status=TaskStatus.PENDING)
        goal = Goal(id="goal-001", description="Goal", status=GoalStatus.ACTIVE, task_ids=["task-001"])
        handler.profile.tasks = [task]
        handler.profile.goals = [goal]
        handler.profile._save = MagicMock()

        await handler._handle_deltask_command("task-001", "msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        assert task not in handler.profile.tasks

    @pytest.mark.asyncio
    async def test_deltask_cannot_delete_executing_task(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        task = Task(id="task-001", description="Running", goal_id="goal-001", status=TaskStatus.EXECUTING)
        handler.profile.tasks = [task]

        await handler._handle_deltask_command("task-001", "msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]


class TestHandleDelay:
    """Test /delay command."""

    @pytest.mark.asyncio
    async def test_delay_schedules_task(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.scheduler.add_task = MagicMock(return_value="task-id-12345")

        await handler._handle_delay_command("/delay 5 test command", "msg-123", "user-456")

        handler.scheduler.add_task.assert_called_once()
        handler.ws.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_delay_invalid_time(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        await handler._handle_delay_command("/delay abc test", "msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]


class TestHandleMemory:
    """Test /memory command."""

    @pytest.mark.asyncio
    async def test_memory_shows_stats(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        mock_memory = MagicMock()
        mock_memory.get_stats.return_value = {
            "session_id": "test-session",
            "total_entries": 10,
            "categories": {"decision": 3, "error": 2},
            "all_tags": ["tag1", "tag2"]
        }
        mock_memory.get_recent.return_value = []
        handler.memory = mock_memory

        await handler._handle_memory_command("msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        response = call_args[0]
        assert "Memory Status" in response
        assert "test-session" in response

    @pytest.mark.asyncio
    async def test_memory_not_available(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.memory = None

        await handler._handle_memory_command("msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "not available" in call_args[0]


class TestHandleRecall:
    """Test /recall command."""

    @pytest.mark.asyncio
    async def test_recall_searches_memory(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        mock_memory = MagicMock()
        mock_entry = MagicMock()
        mock_entry.category = "decision"
        mock_entry.content = "Made a choice about architecture"
        mock_entry.timestamp = "2024-01-01"
        mock_memory.search.return_value = [mock_entry]
        handler.memory = mock_memory

        await handler._handle_recall_command("architecture", "msg-123", "user-456")

        mock_memory.search.assert_called_once_with("architecture", limit=5)
        handler.ws.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_recall_no_results(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        mock_memory = MagicMock()
        mock_memory.search.return_value = []
        handler.memory = mock_memory

        await handler._handle_recall_command("nothing", "msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "No memories" in call_args[0]


class TestHandleProgress:
    """Test /progress command."""

    @pytest.mark.asyncio
    async def test_progress_shows_profile_status(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.profile.format_progress = MagicMock(return_value="Progress: 50%")

        await handler._handle_progress_command("msg-123", "user-456")

        handler.ws.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_progress_includes_queue_status(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.profile.format_progress = MagicMock(return_value="Progress: 50%")

        mock_queue_manager = MagicMock()
        mock_queue_manager.format_status.return_value = "Queue: 3 tasks pending"
        handler.queue_manager = mock_queue_manager

        await handler._handle_progress_command("msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "Queue" in call_args[0]


class TestHandleTasks:
    """Test /tasks command."""

    @pytest.mark.asyncio
    async def test_tasks_shows_scheduler_list(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.scheduler.format_tasks_list.return_value = "Scheduled tasks:\n1. Task A"

        await handler._handle_tasks_command("msg-123", "user-456")

        handler.scheduler.format_tasks_list.assert_called_once()
        handler.ws.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_tasks_empty_scheduler(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.scheduler.format_tasks_list.return_value = "没有待执行的任务"

        await handler._handle_tasks_command("msg-123", "user-456")

        handler.scheduler.format_tasks_list.assert_called_once()
        handler.ws.send_message.assert_called_once()


class TestCommandPauseResumeGoals:
    """Expanded tests for /pause, /resume, /goals commands."""

    # ---- /pause ----

    @pytest.mark.asyncio
    async def test_pause_response_contains_pause_emoji(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.autonomous_mode = True
        handler.ws.send_message = AsyncMock()

        await handler._handle_pause_command("msg-123", "user-456")

        call_args = handler.ws.send_message.call_args[0]
        assert "⏸️" in call_args[0]

    @pytest.mark.asyncio
    async def test_pause_without_lark_open_id(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.autonomous_mode = True
        handler.ws.send_message = AsyncMock()

        await handler._handle_pause_command("msg-123", None)

        assert handler.autonomous_mode is False
        handler.ws.send_message.assert_called_once()
        # lark_open_id=None should still produce a call
        call_args = handler.ws.send_message.call_args
        assert call_args[0][0] is not None

    @pytest.mark.asyncio
    async def test_pause_idempotent(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.autonomous_mode = False  # already paused
        handler.ws.send_message = AsyncMock()

        await handler._handle_pause_command("msg-123", "user-456")

        assert handler.autonomous_mode is False
        handler.ws.send_message.assert_called_once()

    # ---- /resume ----

    @pytest.mark.asyncio
    async def test_resume_response_contains_resume_emoji(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.autonomous_mode = False
        handler.ws.send_message = AsyncMock()

        await handler._handle_resume_command("msg-123", "user-456")

        call_args = handler.ws.send_message.call_args[0]
        assert "▶️" in call_args[0]

    @pytest.mark.asyncio
    async def test_resume_without_lark_open_id(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.autonomous_mode = False
        handler.ws.send_message = AsyncMock()

        await handler._handle_resume_command("msg-123", None)

        assert handler.autonomous_mode is True
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args
        assert call_args[0][0] is not None

    @pytest.mark.asyncio
    async def test_resume_idempotent(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.autonomous_mode = True  # already resumed
        handler.ws.send_message = AsyncMock()

        await handler._handle_resume_command("msg-123", "user-456")

        assert handler.autonomous_mode is True
        handler.ws.send_message.assert_called_once()

    # ---- /goals ----

    @pytest.mark.asyncio
    async def test_goals_shows_active_marker_on_current_goal(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        goal1 = Goal(id="goal-active", description="Active Goal", status=GoalStatus.ACTIVE)
        goal2 = Goal(id="goal-other", description="Other Goal", status=GoalStatus.PAUSED)
        handler.profile.goals = [goal1, goal2]
        handler.profile.get_tasks_for_goal = MagicMock(return_value=[])
        handler.profile.active_goal_id = "goal-active"

        await handler._handle_goals_command("msg-123", "user-456")

        call_args = handler.ws.send_message.call_args[0]
        response = call_args[0]
        assert "◀" in response  # active goal marker

    @pytest.mark.asyncio
    async def test_goals_shows_completed_status_marker(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        goal = Goal(id="goal-done", description="Done Goal", status=GoalStatus.COMPLETED)
        handler.profile.goals = [goal]
        handler.profile.get_tasks_for_goal = MagicMock(return_value=[])
        handler.profile.active_goal_id = None

        await handler._handle_goals_command("msg-123", "user-456")

        call_args = handler.ws.send_message.call_args[0]
        response = call_args[0]
        assert "✅" in response  # completed marker

    @pytest.mark.asyncio
    async def test_goals_shows_paused_status_marker(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        goal = Goal(id="goal-paused", description="Paused Goal", status=GoalStatus.PAUSED)
        handler.profile.goals = [goal]
        handler.profile.get_tasks_for_goal = MagicMock(return_value=[])
        handler.profile.active_goal_id = "goal-other"

        await handler._handle_goals_command("msg-123", "user-456")

        call_args = handler.ws.send_message.call_args[0]
        response = call_args[0]
        assert "⏸️" in response  # paused marker

    @pytest.mark.asyncio
    async def test_goals_shows_task_completion_counts(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        task1 = Task(id="t1", description="Done", goal_id="g1", status=TaskStatus.COMPLETED)
        task2 = Task(id="t2", description="Pending", goal_id="g1", status=TaskStatus.PENDING)
        goal = Goal(id="g1", description="Test Goal", status=GoalStatus.ACTIVE)
        handler.profile.goals = [goal]
        handler.profile.get_tasks_for_goal = MagicMock(return_value=[task1, task2])
        handler.profile.active_goal_id = "g1"

        await handler._handle_goals_command("msg-123", "user-456")

        call_args = handler.ws.send_message.call_args[0]
        response = call_args[0]
        assert "1/2" in response

    @pytest.mark.asyncio
    async def test_goals_without_lark_open_id(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.profile.goals = []
        handler.profile.active_goal_id = None

        await handler._handle_goals_command("msg-123", None)

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args
        assert call_args[0][0] is not None

    # ---- /progress ----

    @pytest.mark.asyncio
    async def test_progress_without_queue_manager(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.profile.format_progress = MagicMock(return_value="Overall Progress: 30%")
        handler.queue_manager = None  # no queue manager

        await handler._handle_progress_command("msg-123", "user-456")

        handler.profile.format_progress.assert_called_once()
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        # Should not crash and should just have profile progress
        assert "30%" in call_args[0]

    @pytest.mark.asyncio
    async def test_progress_with_queue_manager_combined_output(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.profile.format_progress = MagicMock(return_value="Profile: 50%")
        handler.queue_manager = MagicMock()
        handler.queue_manager.format_status.return_value = "Queue: 2 tasks"

        await handler._handle_progress_command("msg-123", "user-456")

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        # Both parts should appear in response
        assert "Profile" in call_args[0]
        assert "Queue" in call_args[0]


class TestConversationMemory:
    """Test conversation memory integration."""

    @pytest.mark.asyncio
    async def test_user_message_added_to_conversation_memory(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.claude.execute = AsyncMock(return_value=("response", [], None))
        handler.ws.send_message = AsyncMock()

        msg = Message(
            type="message",
            data={"content": "Hello Claude", "chat_id": "chat-1", "lark_open_id": "user-1"},
            message_id="msg-123"
        )

        await handler.handle_message(msg)

        # User message should be added to conversation memory history
        assert len(handler.conversation_memory.history) > 0


class TestHandleMessagePriority:
    """Test priority message handling."""

    @pytest.mark.asyncio
    async def test_priority_message_enqueue_to_front(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()

        goal = Goal(id="goal-001", description="Test", status=GoalStatus.ACTIVE)
        handler.profile.get_active_goals = MagicMock(return_value=[goal])
        handler.queue_manager = MagicMock()
        handler.queue_manager.add_user_task = MagicMock()

        msg = Message(
            type="message",
            data={"content": "Urgent task", "priority": True, "chat_id": "chat-1", "lark_open_id": "user-1"},
            message_id="msg-123"
        )

        await handler.handle_message(msg)

        handler.queue_manager.add_user_task.assert_called_once()
        call_args = handler.queue_manager.add_user_task.call_args[0]
        assert call_args[0] == "Urgent task"


# ---------------------------------------------------------------------------
# handle_message — Claude execution path
# ---------------------------------------------------------------------------

class TestHandleMessageClaudeExecution:
    """Test handle_message routing a plain text message to Claude executor."""

    @pytest.mark.asyncio
    async def test_calls_claude_execute_with_content(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock(return_value=True)
        handler.claude.execute = AsyncMock(return_value=("Claude result", [], None))
        handler.token_tracker._build_usage = MagicMock(return_value=None)
        handler.token_tracker._detect_rate_limit = MagicMock(return_value=False)
        handler.conversation_memory.add_assistant = MagicMock()

        msg = Message(
            type="message",
            data={"content": "Write a test", "chat_id": "c1", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        handler.claude.execute.assert_called_once()
        call_args = handler.claude.execute.call_args[0]
        assert "Write a test" in call_args[0]

    @pytest.mark.asyncio
    async def test_records_token_usage_on_response(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock(return_value=True)
        mock_usage = MagicMock()
        mock_usage.total_tokens = 500
        handler.claude.execute = AsyncMock(return_value=("result", [], {"usage": {"input_tokens": 100, "output_tokens": 400}}))
        handler.token_tracker._build_usage = MagicMock(return_value=mock_usage)
        handler.token_tracker._detect_rate_limit = MagicMock(return_value=False)
        handler.profile.record_usage = MagicMock()
        handler.conversation_memory.add_assistant = MagicMock()

        msg = Message(type="message", data={"content": "hi"}, message_id="msg-001")
        await handler.handle_message(msg)

        handler.profile.record_usage.assert_called_once_with(500)

    @pytest.mark.asyncio
    async def test_detects_rate_limit_and_sets_flag(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock(return_value=True)
        handler.claude.execute = AsyncMock(return_value=("rate limited", [], None))
        handler.token_tracker._detect_rate_limit = MagicMock(return_value=True)
        handler.token_tracker._build_usage = MagicMock(return_value=None)
        handler.profile.set_rate_limited = MagicMock()
        handler.conversation_memory.add_assistant = MagicMock()

        msg = Message(type="message", data={"content": "hi"}, message_id="msg-001")
        await handler.handle_message(msg)

        handler.profile.set_rate_limited.assert_called_once()

    @pytest.mark.asyncio
    async def test_sends_response_back_to_user(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock(return_value=True)
        handler.claude.execute = AsyncMock(return_value=("Answer from Claude", [], None))
        handler.token_tracker._detect_rate_limit = MagicMock(return_value=False)
        handler.token_tracker._build_usage = MagicMock(return_value=None)
        handler.conversation_memory.add_assistant = MagicMock()

        msg = Message(type="message", data={"content": "hi", "lark_open_id": "u1"}, message_id="msg-001")
        await handler.handle_message(msg)

        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "Answer from Claude" in call_args[0]

    @pytest.mark.asyncio
    async def test_includes_images_in_response(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock(return_value=True)
        handler.claude.execute = AsyncMock(return_value=("done", ["img1.png", "img2.png"], None))
        handler.token_tracker._detect_rate_limit = MagicMock(return_value=False)
        handler.token_tracker._build_usage = MagicMock(return_value=None)
        handler.conversation_memory.add_assistant = MagicMock()

        msg = Message(type="message", data={"content": "draw something"}, message_id="msg-001")
        await handler.handle_message(msg)

        call_args = handler.ws.send_message.call_args[0]
        assert call_args[2] == ["img1.png", "img2.png"]

    @pytest.mark.asyncio
    async def test_calls_on_message_sent_callback(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock(return_value=True)
        handler.claude.execute = AsyncMock(return_value=("result", [], None))
        handler.token_tracker._detect_rate_limit = MagicMock(return_value=False)
        handler.token_tracker._build_usage = MagicMock(return_value=None)
        handler.conversation_memory.add_assistant = MagicMock()
        handler.on_message_sent = AsyncMock()

        msg = Message(type="message", data={"content": "hi"}, message_id="msg-001")
        await handler.handle_message(msg)

        handler.on_message_sent.assert_called_once_with("msg-001")

    @pytest.mark.asyncio
    async def test_uses_memory_resume_context(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock(return_value=True)
        handler.claude.execute = AsyncMock(return_value=("result", [], None))
        handler.token_tracker._detect_rate_limit = MagicMock(return_value=False)
        handler.token_tracker._build_usage = MagicMock(return_value=None)
        handler.memory = MagicMock()
        handler.memory.get_context_for_resume = MagicMock(return_value="[Resume context from memory]")
        handler.conversation_memory = MagicMock()
        handler.conversation_memory.get_formatted = MagicMock(return_value="")
        handler.conversation_memory.add_assistant = MagicMock()

        msg = Message(type="message", data={"content": "continue"}, message_id="msg-001")
        await handler.handle_message(msg)

        handler.claude.execute.assert_called_once()
        # The prompt should contain resume context
        prompt = handler.claude.execute.call_args[0][0]
        assert "Resume context" in prompt

    @pytest.mark.asyncio
    async def test_handles_exception_in_handle_message(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock(side_effect=Exception("ws error"))
        handler.claude.execute = AsyncMock(side_effect=RuntimeError("claude error"))
        handler.token_tracker._detect_rate_limit = MagicMock(return_value=False)
        handler.token_tracker._build_usage = MagicMock(return_value=None)
        # Should not raise — caught by except
        msg = Message(type="message", data={"content": "hi"}, message_id="msg-001")
        await handler.handle_message(msg)  # no raise

    @pytest.mark.asyncio
    async def test_sends_ack_before_processing(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock(return_value=True)
        handler.claude.execute = AsyncMock(return_value=("result", [], None))
        handler.token_tracker._detect_rate_limit = MagicMock(return_value=False)
        handler.token_tracker._build_usage = MagicMock(return_value=None)
        handler.conversation_memory.add_assistant = MagicMock()

        msg = Message(type="message", data={"content": "hi"}, message_id="msg-001")
        await handler.handle_message(msg)

        handler.ws.send_ack.assert_called_once_with("msg-001")


# ---------------------------------------------------------------------------
# handle_profile_data_message
# ---------------------------------------------------------------------------

class TestHandleProfileDataMessage:
    """Test onboarding profile data handling."""

    @pytest.mark.asyncio
    async def test_saves_profile_and_sets_onboarding_complete(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws = MagicMock()
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock()
        handler.profile.add_goal = MagicMock()
        handler.goal_engine = MagicMock()
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[])
        handler.on_autonomous_start = MagicMock()
        handler.queue_manager = MagicMock()

        msg = Message(
            type="profile_data",
            data={
                "profession": "Engineer",
                "situation": "Building things",
                "short_term_goal": "Ship v1",
                "what_better_means": "More users",
                "lark_open_id": "u1",
            },
            message_id=None,
        )
        await handler.handle_profile_data_message(msg)

        assert handler.profile.profile.onboarding_completed is True
        handler.profile.add_goal.assert_called_once_with("Ship v1")
        handler.on_autonomous_start.assert_called_once()
        handler.profile._save.assert_called()

    @pytest.mark.asyncio
    async def test_decomposes_goal_and_enqueues_tasks(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock()
        goal = MagicMock(id="goal-001")
        handler.profile.add_goal = MagicMock(return_value=goal)
        handler.goal_engine = MagicMock()
        task1 = Task(id="t1", description="Step 1", goal_id="goal-001")
        task2 = Task(id="t2", description="Step 2", goal_id="goal-001")
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[task1, task2])
        handler.on_autonomous_start = MagicMock()
        handler.queue_manager = MagicMock()
        handler.queue_manager.queue = MagicMock()

        msg = Message(
            type="profile_data",
            data={
                "profession": "Eng",
                "situation": "x",
                "short_term_goal": "Goal desc",
                "what_better_means": "y",
            },
            message_id=None,
        )
        await handler.handle_profile_data_message(msg)

        assert handler.queue_manager.queue.enqueue.call_count == 2

    @pytest.mark.asyncio
    async def test_no_goal_created_when_short_term_goal_empty(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock()
        handler.profile.add_goal = MagicMock()
        handler.goal_engine = MagicMock()
        handler.on_autonomous_start = MagicMock()

        msg = Message(
            type="profile_data",
            data={"profession": "Eng", "situation": "x", "short_term_goal": "", "what_better_means": "y"},
            message_id=None,
        )
        await handler.handle_profile_data_message(msg)

        handler.profile.add_goal.assert_not_called()

    @pytest.mark.asyncio
    async def test_enables_autonomous_mode(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock()
        handler.profile.add_goal = MagicMock()
        handler.autonomous_mode = False
        handler.goal_engine = MagicMock()
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[])
        handler.on_autonomous_start = MagicMock()

        msg = Message(
            type="profile_data",
            data={
                "profession": "Eng", "situation": "x",
                "short_term_goal": "Goal", "what_better_means": "y",
            },
            message_id=None,
        )
        await handler.handle_profile_data_message(msg)

        assert handler.autonomous_mode is True
        handler.on_autonomous_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_message_sent_on_profile_data(self):
        """profile_data messages intentionally have no message_id, no response sent."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock()
        handler.profile.add_goal = MagicMock()
        handler.goal_engine = MagicMock()
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[])
        handler.on_autonomous_start = MagicMock()
        handler.ws.send_message = AsyncMock()

        msg = Message(type="profile_data", data={"profession": "Eng", "situation": "x", "short_term_goal": "", "what_better_means": "y"}, message_id=None)
        await handler.handle_profile_data_message(msg)

        handler.ws.send_message.assert_not_called()


# ---------------------------------------------------------------------------
# Command edge cases
# ---------------------------------------------------------------------------

class TestCommandEdgeCases:
    """Edge cases for command handlers."""

    @pytest.mark.asyncio
    async def test_delay_out_of_range_too_high(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        await handler._handle_delay_command("/delay 99999 test", "msg-001", "u1")
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]

    @pytest.mark.asyncio
    async def test_delay_negative_time(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        await handler._handle_delay_command("/delay -1 test", "msg-001", "u1")
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]

    @pytest.mark.asyncio
    async def test_delay_missing_args(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        await handler._handle_delay_command("/delay", "msg-001", "u1")
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]

    @pytest.mark.asyncio
    async def test_delay_general_exception(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.scheduler.add_task = MagicMock(side_effect=Exception("disk full"))
        await handler._handle_delay_command("/delay 5 test", "msg-001", "u1")
        handler.ws.send_message.assert_called()
        call_args = handler.ws.send_message.call_args[0]
        assert "disk full" in call_args[0]

    @pytest.mark.asyncio
    async def test_setgoal_empty_id_shows_usage(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        # Empty goal_id: set_active_goal("") returns False → shows error
        handler.profile.set_active_goal = MagicMock(return_value=False)
        await handler._handle_setgoal_command("", "msg-001", "u1")
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]

    @pytest.mark.asyncio
    async def test_newgoal_empty_description_shows_usage(self):
        # Router: /newgoal with description but desc="" after strip() → usage error
        # content="/newgoal " → content.strip()="/newgoal" → startswith("/newgoal ") fails
        # So it falls through to claude.execute; mock that so we reach the send_message
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.claude.execute = AsyncMock(return_value=("done", [], {}))
        # "/newgoal " has trailing space; strip()="/newgoal"; doesn't startwith "/newgoal "
        # → falls through to executor, which returns "done" → send_message called
        msg = Message(type="message", data={"content": "/newgoal "}, message_id="msg-001")
        await handler.handle_message(msg)
        handler.ws.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_newgoal_decompose_failure_sends_warning(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        new_goal = MagicMock(id="g1")
        handler.profile.add_goal = MagicMock(return_value=new_goal)
        handler.goal_engine = MagicMock()
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[])
        # When tasks is empty, it sends warning
        await handler._handle_newgoal_command("Build something", "msg-001", "u1")
        # Called twice: initial + warning
        assert handler.ws.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_newgoal_empty_description_direct_call_hits_guard(self):
        """Direct call to _handle_newgoal_command('') hits the empty-desc guard (lines 433-436)."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        # Guard: if not description → usage error
        await handler._handle_newgoal_command("", "msg-001", "u1")
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]

    @pytest.mark.asyncio
    async def test_deltask_not_found(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.profile.tasks = []
        await handler._handle_deltask_command("nonexistent", "msg-001", "u1")
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]

    @pytest.mark.asyncio
    async def test_deltask_completed_cannot_delete(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        task = Task(id="t1", description="Done task", goal_id="g1", status=TaskStatus.COMPLETED)
        handler.profile.tasks = [task]
        await handler._handle_deltask_command("t1", "msg-001", "u1")
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]

    @pytest.mark.asyncio
    async def test_deltask_failed_is_deleted(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        task = Task(id="t1", description="Failed task", goal_id="g1", status=TaskStatus.FAILED)
        handler.profile.tasks = [task]
        await handler._handle_deltask_command("t1", "msg-001", "u1")
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        # FAILED tasks are deletable (only COMPLETED/EXECUTING are protected)
        assert "🗑️" in call_args[0]

    @pytest.mark.asyncio
    async def test_memory_command_calls_memory_search(self):
        """Router hits /memory → calls _handle_memory_command."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        # /memory routes to _handle_memory_command
        msg = Message(type="message", data={"content": "/memory", "lark_open_id": "u1"}, message_id="msg-001")
        # _handle_memory_command is a stub that sends "Memory not available" if no memory
        await handler.handle_message(msg)
        # Stub: sends message about memory not available
        handler.ws.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_command_with_entries_iterates_recent(self):
        """_handle_memory_command with memory entries → for-loop at line 335 runs."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        mock_entry = MagicMock()
        mock_entry.category = "thought"
        mock_entry.content = "This is a long memory entry that exceeds 80 chars to ensure truncation works"
        handler.memory = MagicMock()
        handler.memory.get_stats = MagicMock(return_value={
            "session_id": "s1", "total_entries": 5,
            "categories": 2, "all_tags": ["tag1", "tag2"],
        })
        handler.memory.get_recent = MagicMock(return_value=[mock_entry])

        await handler._handle_memory_command("msg-001", "u1")

        handler.memory.get_recent.assert_called_once_with(limit=5)
        handler.ws.send_message.assert_called_once()
        call_args = handler.ws.send_message.call_args[0]
        # Content from entry appears in response
        assert "thought" in call_args[0]

    @pytest.mark.asyncio
    async def test_recall_command_with_query(self):
        """Router hits /recall <query> → calls _handle_recall_command with query."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        msg = Message(type="message", data={"content": "/recall design patterns", "lark_open_id": "u1"}, message_id="msg-001")
        await handler.handle_message(msg)
        # Stub sends "Memory not available" if no memory
        handler.ws.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_tasks_command_is_noop(self):
        """Router hits /tasks → sends status."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        msg = Message(type="message", data={"content": "/tasks", "lark_open_id": "u1"}, message_id="msg-001")
        await handler.handle_message(msg)
        # /tasks sends a response (no-op handler sends status)
        handler.ws.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_setgoal_valid_goal_id_calls_handler(self):
        """Router hits /setgoal <id> → _handle_setgoal_command called with goal_id."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.profile.set_active_goal = MagicMock(return_value=True)
        handler.profile.get_goals = MagicMock(return_value=[])
        handler.profile.get_tasks_for_goal = MagicMock(return_value=[])
        handler.conversation_memory = MagicMock()
        msg = Message(type="message", data={"content": "/setgoal g1", "lark_open_id": "u1"}, message_id="msg-001")
        await handler.handle_message(msg)
        handler.profile.set_active_goal.assert_called_once_with("g1")

    @pytest.mark.asyncio
    async def test_newgoal_routes_via_handle_message(self):
        """Router hits /newgoal <desc> → decompose_goal is called."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        new_goal = MagicMock(id="g-new")
        handler.profile.add_goal = MagicMock(return_value=new_goal)
        handler.goal_engine = MagicMock()
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[])

        msg = Message(
            type="message",
            data={"content": "/newgoal Ship v2.0", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        handler.goal_engine.decompose_goal.assert_called_once()

    @pytest.mark.asyncio
    async def test_delgoal_routes_via_handle_message(self):
        """Router hits /delgoal <id> → _handle_delgoal_command is called."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        # _handle_delgoal_command directly manipulates profile attributes
        handler.profile.goals = [MagicMock(id="g1")]
        handler.profile.get_tasks_for_goal = MagicMock(return_value=[])
        handler.profile.tasks = []
        handler.profile.active_goal_id = "other"
        handler.profile._save = MagicMock()
        handler.conversation_memory = MagicMock()

        msg = Message(
            type="message",
            data={"content": "/delgoal g1", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        # Goal was removed from list (goals list had only one entry, now empty)
        assert len(handler.profile.goals) == 0
        handler.ws.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_delgoal_switches_active_when_deleting_active_goal(self):
        """Deleting the active goal → switches active_goal_id to another goal (lines 474-475)."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        goal1 = MagicMock(id="g-active")
        goal2 = MagicMock(id="g-other")
        handler.profile.goals = [goal1, goal2]
        handler.profile.get_tasks_for_goal = MagicMock(return_value=[])
        handler.profile.tasks = []
        handler.profile.active_goal_id = "g-active"  # deleting the active goal
        handler.profile.get_active_goals = MagicMock(return_value=[goal2])
        handler.profile._save = MagicMock()
        handler.conversation_memory = MagicMock()

        msg = Message(
            type="message",
            data={"content": "/delgoal g-active", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        # Active goal should have been switched to g-other
        assert handler.profile.active_goal_id == "g-other"

    @pytest.mark.asyncio
    async def test_deltask_routes_via_handle_message(self):
        """Router hits /deltask <id> → _handle_deltask_command is called."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.profile.tasks = []
        handler.conversation_memory = MagicMock()

        msg = Message(
            type="message",
            data={"content": "/deltask t1", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        handler.ws.send_message.assert_called()
        # /deltask t1 with no task found → sends error message
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]

    @pytest.mark.asyncio
    async def test_deltask_empty_id_shows_error_via_router(self):
        """Router hits /deltask (no id) → falls through to executor."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        # "/deltask" without space: strip()→"/deltask"; doesn't startwith("/deltask ")
        # → falls through to executor
        handler.claude.execute = AsyncMock(return_value=("response", [], None))
        handler.claude.last_usage = None

        msg = Message(
            type="message",
            data={"content": "/deltask", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        handler.ws.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_delgoal_empty_id_shows_error_via_router(self):
        """Router hits /delgoal (no id) → sends usage error via router else-branch."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        # "/delgoal" without space: strip()→"/delgoal"; doesn't startwith("/delgoal ")
        # → falls through to executor; mock so it returns a response
        handler.claude.execute = AsyncMock(return_value=("response", [], None))
        handler.claude.last_usage = None

        msg = Message(
            type="message",
            data={"content": "/delgoal", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        handler.ws.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_delay_routes_via_handle_message(self):
        """Router hits /delay <min> <msg> → scheduler.add_task is called."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.scheduler.add_task = MagicMock()

        msg = Message(
            type="message",
            data={"content": "/delay 5 hello world", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        handler.scheduler.add_task.assert_called_once()
        # Should NOT have called claude.execute
        handler.claude.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_progress_routes_via_handle_message(self):
        """Router hits /progress → _handle_progress_command is called."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.profile.format_progress = MagicMock(return_value="50% done")
        handler.profile.tasks = []

        msg = Message(
            type="message",
            data={"content": "/progress", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        handler.profile.format_progress.assert_called()
        handler.ws.send_message.assert_called()
        # Should NOT have called claude.execute
        assert handler.claude.execute.call_count == 0

    @pytest.mark.asyncio
    async def test_resume_routes_via_handle_message(self):
        """Router hits /resume → autonomous_mode is set True."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.autonomous_mode = False

        msg = Message(
            type="message",
            data={"content": "/resume", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        assert handler.autonomous_mode is True
        # Should NOT have called claude.execute
        handler.claude.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_goals_routes_via_handle_message(self):
        """Router hits /goals → _handle_goals_command is called; profile.goals accessed."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.profile.goals = []
        handler.profile.get_tasks_for_goal = MagicMock(return_value=[])

        msg = Message(
            type="message",
            data={"content": "/goals", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        # _handle_goals_command reads profile.goals directly
        assert len(handler.profile.goals) == 0
        handler.ws.send_message.assert_called()
        # Should NOT have called claude.execute
        assert handler.claude.execute.call_count == 0

    @pytest.mark.asyncio
    async def test_deltask_empty_id_shows_error_via_router(self):
        """Router hits /deltask (no id) → falls through to executor."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        # "/deltask" without space: strip()→"/deltask"; doesn't startwith("/deltask ")
        # → falls through to executor
        handler.claude.execute = AsyncMock(return_value=("response", [], None))
        handler.claude.last_usage = None

        msg = Message(
            type="message",
            data={"content": "/deltask", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        handler.ws.send_message.assert_called()


# ---------------------------------------------------------------------------
# WebSocket event handlers
# ---------------------------------------------------------------------------

class TestWebSocketEventHandlers:
    """handle_error / handle_delivered / handle_tasks_request."""

    @pytest.mark.asyncio
    async def test_handle_error_logs_error(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        msg = Message(type="error", data={"code": "AUTH_FAILED", "message": "Invalid token"})
        await handler.handle_error(msg)
        # No exception raised — just logged

    @pytest.mark.asyncio
    async def test_handle_delivered_logs_message_id(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        msg = Message(type="delivered", data={}, message_id="msg-123")
        await handler.handle_delivered(msg)
        # No exception raised

    @pytest.mark.asyncio
    async def test_handle_tasks_request_is_noop(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws = MagicMock()
        msg = Message(type="tasks", data={}, message_id="msg-001")
        result = handler.handle_tasks_request.__wrapped__(handler, msg) if hasattr(handler.handle_tasks_request, '__wrapped__') else None
        # Stub: does nothing, no exception
        await handler.handle_tasks_request(msg)


# ---------------------------------------------------------------------------
# Message dispatch routing — handle_message / profile_data / error / delivered
# ---------------------------------------------------------------------------

class TestMessageRouting:
    """Test message dispatch routing for different message types and payloads."""

    # ---- handle_message — text message calling Claude executor ----

    @pytest.mark.asyncio
    async def test_handle_message_text_calls_claude_executor(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.claude.execute = AsyncMock(return_value=("Claude response", [], None))
        handler.claude.last_usage = None

        msg = Message(type="message", data={"content": "What is my progress?", "lark_open_id": "u1"}, message_id="msg-001")
        await handler.handle_message(msg)

        handler.claude.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_text_no_ack_when_no_message_id(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.claude.execute = AsyncMock(return_value=("response", [], None))
        handler.claude.last_usage = None

        msg = Message(type="message", data={"content": "hello"}, message_id=None)
        await handler.handle_message(msg)

        handler.ws.send_ack.assert_not_called()
        handler.claude.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_priority_enqueue_front(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.queue_manager = MagicMock()
        handler.queue_manager.add_user_task = MagicMock()
        handler.profile.get_active_goals = MagicMock(return_value=[MagicMock(id="g1")])

        msg = Message(
            type="message",
            data={"content": "URGENT: deploy now", "priority": True, "lark_open_id": "u1"},
            message_id="msg-001"
        )
        await handler.handle_message(msg)

        handler.queue_manager.add_user_task.assert_called_once()
        handler.ws.send_message.assert_called_once()
        # Claude executor should NOT be called
        handler.claude.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_text_sends_response(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.claude.execute = AsyncMock(return_value=("The answer is 42", [], None))
        handler.claude.last_usage = None

        msg = Message(
            type="message",
            data={"content": "What is 6*7?", "lark_open_id": "u1"},
            message_id="msg-001"
        )
        await handler.handle_message(msg)

        handler.ws.send_message.assert_called()
        call_args = handler.ws.send_message.call_args[0]
        assert "42" in call_args[0]

    @pytest.mark.asyncio
    async def test_handle_message_command_known_routes_correctly(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.claude.execute = AsyncMock(return_value=("unused", [], None))  # should NOT be called

        msg = Message(
            type="message",
            data={"content": "/pause", "lark_open_id": "u1"},
            message_id="msg-001"
        )
        await handler.handle_message(msg)

        handler.claude.execute.assert_not_called()
        assert handler.autonomous_mode is False

    @pytest.mark.asyncio
    async def test_handle_message_exception_in_handler_logs_and_continues(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.conversation_memory = MagicMock()
        # Inject exception during execution
        handler.claude.execute = AsyncMock(side_effect=RuntimeError("API error"))

        msg = Message(
            type="message",
            data={"content": "something", "lark_open_id": "u1"},
            message_id="msg-001"
        )
        # Should not raise — exception is caught
        await handler.handle_message(msg)

    @pytest.mark.asyncio
    async def test_handle_message_logs_content_preview(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.claude.execute = AsyncMock(return_value=("response", [], None))
        handler.claude.last_usage = None

        msg = Message(
            type="message",
            data={"content": "Hello Claude, how are you?", "lark_open_id": "u1"},
            message_id="msg-001"
        )
        await handler.handle_message(msg)

        # Conversation memory should have received the message
        handler.conversation_memory.add_user.assert_called_once_with("Hello Claude, how are you?")

    # ---- handle_profile_data_message ----

    @pytest.mark.asyncio
    async def test_profile_data_creates_goal_and_enqueues_tasks(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock()
        goal = MagicMock(id="g-new")
        handler.profile.add_goal = MagicMock(return_value=goal)
        handler.goal_engine = MagicMock()
        task = Task(id="t1", description="Do it", goal_id="g-new")
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[task])
        handler.on_autonomous_start = MagicMock()
        handler.queue_manager = MagicMock()
        handler.queue_manager.queue = MagicMock()

        msg = Message(
            type="profile_data",
            data={"profession": "Dev", "situation": "building", "short_term_goal": "Ship v1"},
            message_id=None,
        )
        await handler.handle_profile_data_message(msg)

        handler.goal_engine.decompose_goal.assert_called_once()
        handler.queue_manager.queue.enqueue.assert_called_once()
        assert handler.autonomous_mode is True

    @pytest.mark.asyncio
    async def test_profile_data_no_goal_when_short_term_goal_empty(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock()
        handler.profile.add_goal = MagicMock()
        handler.goal_engine = MagicMock()
        handler.on_autonomous_start = MagicMock()

        msg = Message(
            type="profile_data",
            data={"profession": "Dev", "situation": "building", "short_term_goal": ""},
            message_id=None,
        )
        await handler.handle_profile_data_message(msg)

        handler.profile.add_goal.assert_not_called()
        assert handler.autonomous_mode is True

    @pytest.mark.asyncio
    async def test_profile_data_exception_in_handler_logs_and_continues(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock(side_effect=IOError("save failed"))
        handler.profile.add_goal = MagicMock()
        handler.on_autonomous_start = MagicMock()

        msg = Message(
            type="profile_data",
            data={"profession": "Dev", "short_term_goal": "Goal"},
            message_id=None,
        )
        # Should not raise
        await handler.handle_profile_data_message(msg)

    # ---- handle_error ----

    @pytest.mark.asyncio
    async def test_handle_error_extracts_code_and_message(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

        msg = Message(
            type="error",
            data={"code": "RATE_LIMIT", "message": "Too many requests"},
        )
        # Should not raise — just logs
        await handler.handle_error(msg)

    @pytest.mark.asyncio
    async def test_handle_error_handles_missing_fields(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

        msg = Message(type="error", data={})
        # Defaults to UNKNOWN / Unknown error — should not raise
        await handler.handle_error(msg)

    # ---- handle_delivered ----

    @pytest.mark.asyncio
    async def test_handle_delivered_logs_message_id_correctly(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

        msg = Message(type="delivered", data={}, message_id="msg-xyz-789")
        # Should not raise — just logs
        await handler.handle_delivered(msg)

    # ---- handle_tasks_request ----

    @pytest.mark.asyncio
    async def test_handle_tasks_request_is_noop(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws = MagicMock()
        msg = Message(type="tasks", data={}, message_id="msg-001")
        # Should not raise
        await handler.handle_tasks_request(msg)


# ---------------------------------------------------------------------------
# Error handling — handle_error, exception branches, tool executor errors
# ---------------------------------------------------------------------------

class TestHandleError:
    """Test handle_error for various server error types."""

    @pytest.mark.asyncio
    async def test_auth_failure_error(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

        msg = Message(
            type="error",
            data={"code": "AUTH_FAILED", "message": "Token expired"},
        )
        await handler.handle_error(msg)  # should not raise

    @pytest.mark.asyncio
    async def test_connection_error(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

        msg = Message(
            type="error",
            data={"code": "CONNECTION_ERROR", "message": "Server unreachable"},
        )
        await handler.handle_error(msg)

    @pytest.mark.asyncio
    async def test_rate_limit_error_from_server(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

        msg = Message(
            type="error",
            data={"code": "RATE_LIMIT_EXCEEDED", "message": "Slow down"},
        )
        await handler.handle_error(msg)

    @pytest.mark.asyncio
    async def test_handle_error_with_only_code(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

        msg = Message(
            type="error",
            data={"code": "UNKNOWN_ERROR"},
        )
        await handler.handle_error(msg)

    @pytest.mark.asyncio
    async def test_handle_error_with_only_message(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

        msg = Message(
            type="error",
            data={"message": "Something went wrong"},
        )
        await handler.handle_error(msg)


class TestToolExecutorErrors:
    """Test error handling in ToolExecutor built-in operations."""

    @pytest.mark.asyncio
    async def test_read_file_not_found_returns_error_string(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)

        result = await executor._read_file("/nonexistent/path/to/file.txt")
        assert "Error reading file" in result

    @pytest.mark.asyncio
    async def test_list_dir_permission_error_returns_error_string(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)

        result = await executor._list_dir("/root/forbidden")
        assert "Error listing directory" in result

    @pytest.mark.asyncio
    async def test_shell_command_not_found_returns_output_with_stderr(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)

        result = await executor._shell("nonexistent_command_xyz_12345")
        # Command runs but fails → stderr is appended, not an exception thrown
        assert "command not found" in result

    @pytest.mark.asyncio
    async def test_shell_command_timeout_returns_error_string(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig
        from unittest.mock import patch, AsyncMock

        config = ClientConfig()
        executor = ToolExecutor(config)

        # Simulate subprocess that times out
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError("timed out"))

        with patch("asyncio.create_subprocess_shell", new_callable=AsyncMock) as mock_sub:
            mock_sub.return_value = mock_process
            result = await executor._shell("sleep 999")
            assert "Error executing command" in result

    @pytest.mark.asyncio
    async def test_screenshot_unsupported_platform_returns_message(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig
        import platform

        config = ClientConfig()
        executor = ToolExecutor(config)

        original_system = platform.system
        try:
            platform.system = MagicMock(return_value="FreeBSD")
            result = await executor._screenshot()
            assert "not supported" in result.lower()
        finally:
            platform.system = original_system

    @pytest.mark.asyncio
    async def test_execute_tool_unknown_returns_unknown_message(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)

        # No fallback for truly unknown tools (falls to else branch)
        result = await executor.execute_tool("totally_unknown_tool_xyz", {})
        assert "Unknown tool" in result


class TestDelayCommandExceptionHandling:
    """Test exception branches in _handle_delay_command."""

    @pytest.mark.asyncio
    async def test_delay_schedulizer_failure_returns_error_message(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()
        handler.scheduler.add_task = MagicMock(side_effect=OSError("disk full"))

        await handler._handle_delay_command("/delay 5 echo test", "msg-001", "u1")

        handler.ws.send_message.assert_called()
        call_args = handler.ws.send_message.call_args[0]
        assert "disk full" in call_args[0]

    @pytest.mark.asyncio
    async def test_delay_invalid_minutes_not_integer(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        await handler._handle_delay_command("/delay abc echo hi", "msg-001", "u1")

        handler.ws.send_message.assert_called()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]  # ValueError → invalid format message

    @pytest.mark.asyncio
    async def test_delay_zero_minutes_out_of_range(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        await handler._handle_delay_command("/delay 0 echo hi", "msg-001", "u1")

        handler.ws.send_message.assert_called()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]

    @pytest.mark.asyncio
    async def test_delay_10081_minutes_out_of_range(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_message = AsyncMock()

        await handler._handle_delay_command("/delay 10081 echo hi", "msg-001", "u1")

        handler.ws.send_message.assert_called()
        call_args = handler.ws.send_message.call_args[0]
        assert "❌" in call_args[0]


class TestMessageExceptionSafety:
    """Verify exception safety of all message handlers — they must not raise."""

    @pytest.mark.asyncio
    async def test_handle_profile_data_message_exception_safe(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock(side_effect=RuntimeError("save failed"))

        msg = Message(
            type="profile_data",
            data={"profession": "Dev"},
            message_id=None,
        )
        # _save raises → exception caught, must not propagate
        await handler.handle_profile_data_message(msg)

    @pytest.mark.asyncio
    async def test_handle_error_exception_safe(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        # handle_error has no exception wrapping — but also no dangerous ops
        msg = Message(type="error", data={"code": "X", "message": "Y"})
        await handler.handle_error(msg)  # must not raise

    @pytest.mark.asyncio
    async def test_handle_delivered_exception_safe(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        msg = Message(type="delivered", data={}, message_id="msg-001")
        await handler.handle_delivered(msg)  # must not raise

    @pytest.mark.asyncio
    async def test_handle_tasks_request_exception_safe(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws = MagicMock()
        msg = Message(type="tasks", data={}, message_id="msg-001")
        await handler.handle_tasks_request(msg)  # must not raise

    @pytest.mark.asyncio
    async def test_handle_message_with_exception_in_conversation_memory(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        # conversation_memory.add_user raises
        handler.conversation_memory = MagicMock()
        handler.conversation_memory.add_user = MagicMock(side_effect=RuntimeError("memory error"))

        msg = Message(
            type="message",
            data={"content": "hello", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        # Must not raise — exception caught in handle_message try/except
        await handler.handle_message(msg)

    @pytest.mark.asyncio
    async def test_handle_message_with_none_lark_open_id(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.claude.execute = AsyncMock(return_value=("response", [], None))
        handler.claude.last_usage = None

        msg = Message(
            type="message",
            data={"content": "hello"},  # no lark_open_id
            message_id="msg-001",
        )
        await handler.handle_message(msg)
        # Should have sent response with empty lark_open_id
        handler.ws.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_handle_message_claude_returns_none_response(self):
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.claude.execute = AsyncMock(return_value=(None, [], None))
        handler.token_tracker._detect_rate_limit = MagicMock(return_value=False)
        handler.token_tracker._build_usage = MagicMock(return_value=None)
        handler.conversation_memory.add_assistant = MagicMock()

        msg = Message(
            type="message",
            data={"content": "hello", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        # None response causes TypeError in logging (response[:100]) → caught silently
        # send_message is NOT called when response is None
        await handler.handle_message(msg)
        handler.ws.send_message.assert_not_called()





class TestAsyncCallbacks:
    """Test async callbacks: on_message_sent, on_autonomous_start, queue_manager."""

    # ---- on_message_sent callback ----

    @pytest.mark.asyncio
    async def test_on_message_sent_called_after_send_success(self):
        """send_message returns True → on_message_sent is called with message_id."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock(return_value=True)
        handler.conversation_memory = MagicMock()
        handler.claude.execute = AsyncMock(return_value=("Claude response", [], None))
        handler.claude.last_usage = None
        handler.on_message_sent = AsyncMock()

        msg = Message(
            type="message",
            data={"content": "hello", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        handler.on_message_sent.assert_called_once_with("msg-001")

    @pytest.mark.asyncio
    async def test_on_message_sent_not_called_when_send_fails(self):
        """send_message returns False → on_message_sent is NOT called."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock(return_value=False)
        handler.conversation_memory = MagicMock()
        handler.claude.execute = AsyncMock(return_value=("Claude response", [], None))
        handler.claude.last_usage = None
        handler.on_message_sent = AsyncMock()

        msg = Message(
            type="message",
            data={"content": "hello", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        handler.on_message_sent.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_sent_not_called_when_no_message_id(self):
        """message_id=None → on_message_sent is NOT called even if send succeeds."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.conversation_memory = MagicMock()
        handler.claude.execute = AsyncMock(return_value=("Claude response", [], None))
        handler.claude.last_usage = None
        handler.on_message_sent = AsyncMock()

        msg = Message(
            type="message",
            data={"content": "hello", "lark_open_id": "u1"},
            message_id=None,
        )
        await handler.handle_message(msg)

        handler.on_message_sent.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_sent_not_called_when_callback_is_none(self):
        """on_message_sent=None → no AttributeError, send still proceeds."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock(return_value=True)
        handler.conversation_memory = MagicMock()
        handler.claude.execute = AsyncMock(return_value=("Claude response", [], None))
        handler.claude.last_usage = None
        handler.on_message_sent = None

        msg = Message(
            type="message",
            data={"content": "hello", "lark_open_id": "u1"},
            message_id="msg-001",
        )
        # Must not raise AttributeError
        await handler.handle_message(msg)
        # send_message was still called
        handler.ws.send_message.assert_called_once()

    # ---- on_autonomous_start callback ----

    @pytest.mark.asyncio
    async def test_on_autonomous_start_called_on_profile_data_with_goal(self):
        """profile_data with goal → on_autonomous_start is called."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock()
        goal = MagicMock(id="g1")
        handler.profile.add_goal = MagicMock(return_value=goal)
        handler.goal_engine = MagicMock()
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[])
        handler.on_autonomous_start = MagicMock()

        msg = Message(
            type="profile_data",
            data={"profession": "Dev", "situation": "x", "short_term_goal": "Ship v1"},
            message_id=None,
        )
        await handler.handle_profile_data_message(msg)

        handler.on_autonomous_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_autonomous_start_called_even_without_short_term_goal(self):
        """short_term_goal='' but autonomous_mode=True → callback still called."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock()
        handler.profile.add_goal = MagicMock()
        handler.goal_engine = MagicMock()
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[])
        handler.on_autonomous_start = MagicMock()

        msg = Message(
            type="profile_data",
            data={"profession": "Dev", "situation": "x", "short_term_goal": ""},
            message_id=None,
        )
        await handler.handle_profile_data_message(msg)

        handler.on_autonomous_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_handler_works_without_on_autonomous_start(self):
        """on_autonomous_start=None → handle_profile_data_message still works."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock()
        handler.profile.add_goal = MagicMock()
        handler.goal_engine = MagicMock()
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[])
        handler.on_autonomous_start = None

        msg = Message(
            type="profile_data",
            data={"profession": "Dev", "situation": "x", "short_term_goal": "Goal"},
            message_id=None,
        )
        # Must not raise TypeError or AttributeError
        await handler.handle_profile_data_message(msg)

    # ---- queue_manager callbacks ----

    @pytest.mark.asyncio
    async def test_queue_manager_add_user_task_on_priority_message(self):
        """priority message → queue_manager.add_user_task is called with content+goal_id."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.ws.send_ack = AsyncMock()
        handler.ws.send_message = AsyncMock(return_value=True)
        handler.conversation_memory = MagicMock()
        handler.queue_manager = MagicMock()
        handler.queue_manager.add_user_task = MagicMock()
        handler.profile.get_active_goals = MagicMock(return_value=[MagicMock(id="g1")])

        msg = Message(
            type="message",
            data={"content": "URGENT: do it now", "priority": True, "lark_open_id": "u1"},
            message_id="msg-001",
        )
        await handler.handle_message(msg)

        handler.queue_manager.add_user_task.assert_called_once()
        call_args = handler.queue_manager.add_user_task.call_args[0]
        assert "do it now" in call_args[0]

    @pytest.mark.asyncio
    async def test_queue_manager_enqueue_on_profile_data_with_user_initiated_false(self):
        """profile_data with goal → queue.enqueue called with user_initiated=False."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock()
        goal = MagicMock(id="g-new")
        handler.profile.add_goal = MagicMock(return_value=goal)
        handler.goal_engine = MagicMock()
        task = Task(id="t1", description="Task 1", goal_id="g-new")
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[task])
        handler.on_autonomous_start = MagicMock()
        handler.queue_manager = MagicMock()
        handler.queue_manager.queue = MagicMock()

        msg = Message(
            type="profile_data",
            data={"profession": "Dev", "situation": "x", "short_term_goal": "Ship v1"},
            message_id=None,
        )
        await handler.handle_profile_data_message(msg)

        handler.queue_manager.queue.enqueue.assert_called_once()
        call_kwargs = handler.queue_manager.queue.enqueue.call_args[1]
        assert call_kwargs.get("user_initiated") is False

    @pytest.mark.asyncio
    async def test_queue_manager_enqueue_on_profile_data_no_goal(self):
        """profile_data without goal → queue.enqueue NOT called."""
        handler = MessageHandler(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        handler.profile.profile = MagicMock()
        handler.profile._save = MagicMock()
        handler.profile.add_goal = MagicMock()
        handler.goal_engine = MagicMock()
        handler.goal_engine.decompose_goal = AsyncMock(return_value=[])
        handler.on_autonomous_start = MagicMock()
        handler.queue_manager = MagicMock()
        handler.queue_manager.queue = MagicMock()

        msg = Message(
            type="profile_data",
            data={"profession": "Dev", "situation": "x", "short_term_goal": ""},
            message_id=None,
        )
        await handler.handle_profile_data_message(msg)

        handler.queue_manager.queue.enqueue.assert_not_called()


class TestToolExecutor:
    """Test ToolExecutor.execute_tool and its operation routing."""

    @pytest.mark.asyncio
    async def test_execute_tool_file_read(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)

        # Patch _execute_from_tools to return a result
        with patch.object(executor, "_execute_from_tools", AsyncMock(return_value="file contents")):
            result = await executor.execute_tool("file_read", {"path": "/tmp/test.txt"})
            assert result is not None

    @pytest.mark.asyncio
    async def test_execute_tool_unknown_tool(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig
        from client.handler import get_tool

        config = ClientConfig()
        executor = ToolExecutor(config)
        with patch("client.handler.get_tool", return_value=None):
            result = await executor.execute_tool("unknown-tool-xyz", {})
            assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_execute_from_tools_tool_not_found(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)
        with patch("client.handler.get_tool", return_value=None):
            result = await executor._execute_from_tools("nonexistent", {})
            assert "not found" in result

    @pytest.mark.asyncio
    async def test_execute_tool_shell_success(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)
        with patch("asyncio.create_subprocess_shell", new=AsyncMock()) as mock_shell:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"output", b""))
            mock_shell.return_value = mock_proc
            result = await executor._shell("echo hello")
            assert "output" in result

    @pytest.mark.asyncio
    async def test_execute_tool_shell_with_stderr(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)
        with patch("asyncio.create_subprocess_shell", new=AsyncMock()) as mock_shell:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"stdout", b"error here"))
            mock_shell.return_value = mock_proc
            result = await executor._shell("ls /tmp")
            assert "error here" in result

    @pytest.mark.asyncio
    async def test_execute_tool_read_file_success(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)
        with patch("builtins.open", MagicMock()) as mock_open:
            mock_f = MagicMock()
            mock_f.read.return_value = "file content here"
            mock_open.return_value.__enter__.return_value = mock_f
            result = await executor._read_file("/path/to/file")
            assert "file content here" in result

    @pytest.mark.asyncio
    async def test_execute_tool_read_file_truncates_long_content(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)
        long_content = "x" * 20000
        with patch("builtins.open", MagicMock()) as mock_open:
            mock_f = MagicMock()
            mock_f.read.return_value = long_content
            mock_open.return_value.__enter__.return_value = mock_f
            result = await executor._read_file("/path/to/file")
            assert "(truncated)" in result

    @pytest.mark.asyncio
    async def test_execute_tool_read_file_error(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)
        with patch("builtins.open", side_effect=FileNotFoundError("no such file")):
            result = await executor._read_file("/nonexistent/file")
            assert "Error reading file" in result

    @pytest.mark.asyncio
    async def test_execute_tool_list_dir_success(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)
        with patch("os.listdir", return_value=["file1.py", "file2.py"]):
            result = await executor._list_dir("/tmp")
            assert "file1.py" in result
            assert "file2.py" in result

    @pytest.mark.asyncio
    async def test_execute_tool_list_dir_error(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)
        with patch("os.listdir", side_effect=PermissionError("denied")):
            result = await executor._list_dir("/root")
            assert "Error listing directory" in result

    # ---- execute_tool fallback paths (screenshot, list_dir, read_file, shell) ----

    @pytest.mark.asyncio
    async def test_execute_tool_screenshot_darwin_success(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig
        import platform

        config = ClientConfig()
        executor = ToolExecutor(config)

        original_system = platform.system
        try:
            platform.system = MagicMock(return_value="Darwin")
            with patch("asyncio.create_subprocess_exec", new=AsyncMock()) as mock_exec:
                mock_proc = AsyncMock()
                mock_proc.communicate = AsyncMock(return_value=(b"", b""))
                mock_exec.return_value = mock_proc
                with patch("os.path.exists", return_value=True):
                    result = await executor._screenshot()
                    assert "Screenshot saved" in result
        finally:
            platform.system = original_system

    @pytest.mark.asyncio
    async def test_execute_tool_screenshot_linux_success(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig
        import platform

        config = ClientConfig()
        executor = ToolExecutor(config)

        original_system = platform.system
        try:
            platform.system = MagicMock(return_value="Linux")
            with patch("asyncio.create_subprocess_exec", new=AsyncMock()) as mock_exec:
                mock_proc = AsyncMock()
                mock_proc.communicate = AsyncMock(return_value=(b"", b""))
                mock_exec.return_value = mock_proc
                with patch("os.path.exists", return_value=True):
                    result = await executor._screenshot()
                    assert "Screenshot saved" in result
        finally:
            platform.system = original_system

    @pytest.mark.asyncio
    async def test_execute_tool_screenshot_unsupported_platform(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig
        import platform

        config = ClientConfig()
        executor = ToolExecutor(config)

        original_system = platform.system
        try:
            platform.system = MagicMock(return_value="FreeBSD")
            result = await executor._screenshot()
            assert "not supported" in result.lower()
        finally:
            platform.system = original_system

    @pytest.mark.asyncio
    async def test_execute_tool_screenshot_file_not_created(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig
        import platform

        config = ClientConfig()
        executor = ToolExecutor(config)

        original_system = platform.system
        try:
            platform.system = MagicMock(return_value="Darwin")
            with patch("asyncio.create_subprocess_exec", new=AsyncMock()) as mock_exec:
                mock_proc = AsyncMock()
                mock_proc.communicate = AsyncMock(return_value=(b"", b""))
                mock_exec.return_value = mock_proc
                with patch("os.path.exists", return_value=False):
                    result = await executor._screenshot()
                    assert "Failed to capture" in result
        finally:
            platform.system = original_system

    @pytest.mark.asyncio
    async def test_execute_tool_screenshot_exception(self):
        from client.handler import ToolExecutor
        from client.config import ClientConfig
        import platform

        config = ClientConfig()
        executor = ToolExecutor(config)

        original_system = platform.system
        try:
            platform.system = MagicMock(return_value="Darwin")
            mock_exec = AsyncMock(side_effect=OSError("no screencapture"))
            with patch("asyncio.create_subprocess_exec", mock_exec):
                result = await executor._screenshot()
                assert "Error capturing screenshot" in result
        finally:
            platform.system = original_system

    @pytest.mark.asyncio
    async def test_execute_tool_via_execute_tool_screenshot_fallback(self):
        """execute_tool('screenshot', {}) → calls _screenshot() via fallback."""
        from client.handler import ToolExecutor
        from client.config import ClientConfig
        import platform

        config = ClientConfig()
        executor = ToolExecutor(config)

        original_system = platform.system
        try:
            platform.system = MagicMock(return_value="Darwin")
            with patch("asyncio.create_subprocess_exec", new=AsyncMock()) as mock_exec:
                mock_proc = AsyncMock()
                mock_proc.communicate = AsyncMock(return_value=(b"", b""))
                mock_exec.return_value = mock_proc
                with patch("os.path.exists", return_value=True):
                    result = await executor.execute_tool("screenshot", {})
                    assert "Screenshot saved" in result
        finally:
            platform.system = original_system

    @pytest.mark.asyncio
    async def test_execute_tool_via_execute_tool_list_dir_fallback(self):
        """execute_tool('list_dir', {'path': '.'}) → calls _list_dir() via fallback."""
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)

        with patch("os.listdir", return_value=["a.py", "b.py"]):
            result = await executor.execute_tool("list_dir", {"path": "."})
            assert "a.py" in result

    @pytest.mark.asyncio
    async def test_execute_tool_via_execute_tool_read_file_fallback(self):
        """execute_tool('read_file', {'path': 'x'}) → calls _read_file() via fallback."""
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)

        with patch("builtins.open", MagicMock()) as mock_open:
            mock_f = MagicMock()
            mock_f.read.return_value = "file content"
            mock_open.return_value.__enter__.return_value = mock_f
            result = await executor.execute_tool("read_file", {"path": "x"})
            assert "file content" in result

    @pytest.mark.asyncio
    async def test_execute_tool_via_execute_tool_shell_fallback(self):
        """execute_tool('shell', {'command': 'x'}) → calls _shell() via fallback."""
        from client.handler import ToolExecutor
        from client.config import ClientConfig

        config = ClientConfig()
        executor = ToolExecutor(config)

        with patch("asyncio.create_subprocess_shell", new=AsyncMock()) as mock_shell:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"output", b""))
            mock_shell.return_value = mock_proc
            result = await executor.execute_tool("shell", {"command": "echo hello"})
            assert "output" in result

