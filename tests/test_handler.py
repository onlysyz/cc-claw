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
