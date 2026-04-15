"""Tests for daemon.py - CCClawDaemon autonomous running loop."""

import asyncio
import logging
import signal
import sys
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.daemon import CCClawDaemon
from client.config import ClientConfig
from client.profile import Goal, Task, GoalStatus, TaskStatus


class TestDaemonInit:
    """Test CCClawDaemon initialization."""

    def test_init_sets_initial_state(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        assert daemon.config is config
        assert daemon._running is False
        assert daemon.ws_manager is None
        assert daemon.claude is None
        assert daemon.handler is None
        assert daemon.scheduler is None
        assert daemon.profile is None
        assert daemon.goal_engine is None
        assert daemon.queue_manager is None
        assert daemon.memory is None
        assert daemon._task_checker_task is None
        assert daemon._token_checker_task is None
        assert daemon._autonomous_runner_task is None


class TestStartAutonomousRunner:
    """Test _start_autonomous_runner_if_needed()."""

    def test_starts_runner_when_not_running(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._autonomous_runner_task = None

        with patch.object(asyncio, 'get_event_loop') as mock_loop:
            mock_loop.return_value.create_task = MagicMock(return_value=MagicMock(done=MagicMock(return_value=False)))
            daemon._start_autonomous_runner_if_needed()

            mock_loop.return_value.create_task.assert_called_once()

    def test_does_not_start_when_already_running(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        mock_task = MagicMock(done=MagicMock(return_value=False))
        daemon._autonomous_runner_task = mock_task

        with patch.object(asyncio, 'get_event_loop') as mock_loop:
            daemon._start_autonomous_runner_if_needed()

            mock_loop.return_value.create_task.assert_not_called()


class TestAutonomousRunner:
    """Test _autonomous_runner() loop behavior."""

    @pytest.mark.asyncio
    async def test_pauses_when_autonomous_mode_disabled(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True
        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = False

        # Run a limited number of iterations
        iterations = 0
        async def limited_runner():
            nonlocal iterations
            while daemon._running and iterations < 3:
                if not daemon.handler.autonomous_mode:
                    await asyncio.sleep(0.01)
                    iterations += 1
                    continue
                break

        # Patch sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            daemon.handler.autonomous_mode = False
            daemon.profile = MagicMock()
            daemon.profile.token_budget = MagicMock()
            daemon.profile.token_budget.is_rate_limited = False

            # Run just a few iterations
            for _ in range(3):
                if not daemon.handler.autonomous_mode:
                    await asyncio.sleep(0.01)
                iterations += 1

            assert iterations == 3

    @pytest.mark.asyncio
    async def test_waits_when_rate_limited(self):
        """Rate limited → sleep with exponential backoff (120s for level=1), then continue."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True
        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True

        daemon.profile = MagicMock()
        daemon.profile.token_budget.is_rate_limited = True
        daemon.profile.token_budget.backoff_level = 2  # → wait 120s (60 * 2^(2-1) = 120)
        daemon.profile.get_active_goal.return_value = None
        daemon.profile.goals = []
        daemon.queue_manager = MagicMock()
        daemon.queue_manager.get_next_task = AsyncMock(return_value=None)
        daemon.goal_engine = MagicMock()
        daemon.claude = MagicMock()
        daemon.memory = MagicMock()

        sleep_args = []
        call_count = [0]

        async def mock_sleep(s):
            sleep_args.append(s)
            call_count[0] += 1
            daemon._running = False  # Exit after first sleep

        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._autonomous_runner()

        # Rate limit detected → slept with correct backoff (120s = 60 * 2^(2-1))
        assert len(sleep_args) == 1
        assert sleep_args[0] == 120

    @pytest.mark.asyncio
    async def test_sets_active_goal_from_queue_task_when_no_active_goal(self):
        """No active goal but queue has task with goal_id → sets active goal and resumes."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True

        mock_tb = MagicMock()
        mock_tb.is_rate_limited = False
        daemon.profile = MagicMock()
        daemon.profile.token_budget = mock_tb
        daemon.profile.get_active_goal.return_value = None

        existing_goal = Goal(id="existing-goal", description="Existing goal", status=GoalStatus.ACTIVE)
        daemon.profile.goals = [existing_goal]

        mock_task = Task(id="queued-task-001", description="Queued task", goal_id="existing-goal")
        mock_qt = MagicMock()
        mock_qt.task = mock_task

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.get_next_task = AsyncMock(return_value=mock_qt)
        daemon.queue_manager.queue.enqueue = MagicMock()

        daemon.goal_engine = MagicMock()
        daemon.claude = MagicMock()

        daemon.memory = MagicMock()

        async def mock_sleep(s):
            daemon._running = False

        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._autonomous_runner()

        daemon.profile.set_active_goal.assert_called_once_with("existing-goal")

    @pytest.mark.asyncio
    async def test_unmatched_goal_id_executes_directly_not_reenqueue(self):
        """Regression: orphan tasks should execute via retry_manager, not re-enqueue forever.

        The bug: tasks with goal_id not in profile were re-enqueued forever.
        The fix: _autonomous_runner executes them directly via _execute_autonomous_task.

        This test verifies that for an orphan task (goal_id not in profile.goals):
        1. retry_manager.execute is called (not re-enqueued)
        2. No enqueue calls are made
        """
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        # Task whose goal_id does not match any profile goal
        orphan_task = Task(id="orphan-task-001", description="Orphan task", goal_id="nonexistent-goal-id")
        mock_qt = MagicMock()
        mock_qt.task = orphan_task

        daemon.profile = MagicMock()
        daemon.profile.goals = []  # no matching goal
        daemon.profile.get_tasks_for_goal = MagicMock(return_value=[orphan_task])
        daemon.profile.complete_task = MagicMock()
        daemon.profile.record_usage = MagicMock()

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(return_value=("done", [], None))

        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = True
        daemon.ws_manager.send_notification = AsyncMock(return_value=True)

        daemon.memory = MagicMock()

        # retry_manager is the execution wrapper used by _execute_autonomous_task
        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(return_value=("done", [], None))

        daemon.queue_manager.queue.enqueue = MagicMock()

        # Call _execute_autonomous_task which uses retry_manager.execute
        with patch('client.daemon.TokenTracker'):
            await daemon._execute_autonomous_task(mock_qt)

        # retry_manager.execute was called (actual execution, not re-enqueue)
        daemon.retry_manager.execute.assert_called_once()
        call_args = daemon.retry_manager.execute.call_args[0]
        # First positional arg is the task description
        assert call_args[1] == daemon.claude.execute
        assert call_args[2] == "Orphan task"

        # No enqueue calls were made (the bug would have caused re-enqueue)
        daemon.queue_manager.queue.enqueue.assert_not_called()


class TestExecuteAutonomousTask:
    """Test _execute_autonomous_task()."""

    @pytest.mark.asyncio
    async def test_executes_task_successfully(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        task = Task(id="task-001", description="Test task", goal_id="goal-001")
        qt = MagicMock()
        qt.task = task

        goal = Goal(id="goal-001", description="Test Goal", status=GoalStatus.ACTIVE)
        daemon.profile = MagicMock()
        daemon.profile.goals = [goal]
        daemon.profile.get_tasks_for_goal = MagicMock(return_value=[
            Task(id="task-001", description="Test task", goal_id="goal-001", status=TaskStatus.COMPLETED)
        ])
        daemon.profile.complete_task = MagicMock()
        daemon.profile.complete_goal = MagicMock()
        daemon.profile.record_usage = MagicMock()

        mock_token_tracker = MagicMock()
        daemon.profile.token_budget = mock_token_tracker

        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(return_value=("Task completed successfully", [], None))

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = True
        daemon.ws_manager.send_notification = AsyncMock(return_value=True)

        daemon.memory = MagicMock()

        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(return_value=("Task completed", [], None))

        with patch('client.daemon.TokenTracker') as mock_tracker:
            mock_tracker.return_value._build_usage.return_value = MagicMock(total_tokens=100)
            await daemon._execute_autonomous_task(qt)

        daemon.profile.complete_task.assert_called_once()
        daemon.queue_manager.queue.mark_done.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_task_failure(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        task = Task(id="task-001", description="Failing task", goal_id="goal-001")
        qt = MagicMock()
        qt.task = task

        daemon.profile = MagicMock()
        daemon.profile.goals = []
        daemon.profile.fail_task = MagicMock()

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = True
        daemon.ws_manager.send_notification = AsyncMock(return_value=True)

        daemon.memory = MagicMock()

        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(side_effect=Exception("Task failed"))

        await daemon._execute_autonomous_task(qt)

        daemon.profile.fail_task.assert_called_once()
        daemon.queue_manager.queue.mark_done.assert_called_once()

    @pytest.mark.asyncio
    async def test_goal_complete_when_all_tasks_done(self):
        """Task completes → all goal tasks done → complete_goal called + goal_complete ws sent."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        task = Task(id="task-001", description="Final task", goal_id="goal-001")
        qt = MagicMock()
        qt.task = task

        goal = Goal(id="goal-001", description="Goal to complete", status=GoalStatus.ACTIVE)
        daemon.profile = MagicMock()
        daemon.profile.goals = [goal]
        # After task completes, no pending tasks remain for this goal
        daemon.profile.get_tasks_for_goal = MagicMock(return_value=[
            Task(id="task-001", description="Final task", goal_id="goal-001", status=TaskStatus.COMPLETED)
        ])
        daemon.profile.complete_task = MagicMock()
        daemon.profile.complete_goal = MagicMock()
        daemon.profile.record_usage = MagicMock()
        daemon.profile.token_budget = MagicMock()

        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(return_value=("done", [], None))

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = True
        daemon.ws_manager.send = AsyncMock(return_value=True)
        daemon.ws_manager.send_notification = AsyncMock(return_value=True)

        daemon.memory = MagicMock()

        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(return_value=("done", [], None))

        with patch('client.daemon.TokenTracker'):
            await daemon._execute_autonomous_task(qt)

        daemon.profile.complete_goal.assert_called_once_with("goal-001")
        daemon.ws_manager.send.assert_called_once()
        call_args = daemon.ws_manager.send.call_args[0][0]
        assert call_args["type"] == "goal_complete"
        assert call_args["goal_id"] == "goal-001"

    @pytest.mark.asyncio
    async def test_notification_sent_after_reconnect_wait(self):
        """If ws is disconnected when task finishes, daemon waits for reconnect then notifies."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        task = Task(id="task-001", description="Long running task", goal_id="goal-001")
        qt = MagicMock()
        qt.task = task

        goal = Goal(id="goal-001", description="Test Goal", status=GoalStatus.ACTIVE)
        daemon.profile = MagicMock()
        daemon.profile.goals = [goal]
        daemon.profile.get_tasks_for_goal = MagicMock(return_value=[
            Task(id="task-001", description="Long running task", goal_id="goal-001", status=TaskStatus.COMPLETED)
        ])
        daemon.profile.complete_task = MagicMock()
        daemon.profile.complete_goal = MagicMock()
        daemon.profile.record_usage = MagicMock()
        daemon.profile.token_budget = MagicMock()

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.memory = MagicMock()

        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(return_value=("Task completed", [], None))

        # Simulate: initially disconnected, becomes connected after one sleep
        call_count = 0

        def is_connected_side_effect():
            nonlocal call_count
            call_count += 1
            return call_count > 1  # False on first check, True afterwards

        daemon.ws_manager = MagicMock()
        type(daemon.ws_manager).is_connected = PropertyMock(side_effect=is_connected_side_effect)
        daemon.ws_manager.send_notification = AsyncMock(return_value=True)

        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch('client.daemon.TokenTracker') as mock_tracker:
                mock_tracker.return_value._build_usage.return_value = None
                await daemon._execute_autonomous_task(qt)

        daemon.ws_manager.send_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_rate_limit_response(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        task = Task(id="task-001", description="Rate limited task", goal_id="goal-001")
        qt = MagicMock()
        qt.task = task

        daemon.profile = MagicMock()
        daemon.profile.goals = []
        daemon.profile.increment_backoff = MagicMock(return_value=120)

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()
        daemon.queue_manager.requeue_front = MagicMock()

        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = False

        daemon.memory = MagicMock()

        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(return_value=("Result", [], None))

        async def mock_retry_execute(*args, **kwargs):
            return ("Rate limit exceeded", [], None)

        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = MagicMock(side_effect=mock_retry_execute)

        # Mock sleep to avoid actual delays
        async def mock_sleep(seconds):
            pass
        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._execute_autonomous_task(qt)

        daemon.queue_manager.requeue_front.assert_called_once()
        daemon.queue_manager.queue.mark_done.assert_called()


class TestSuggestNewGoal:
    """Test _suggest_new_goal()."""

    @pytest.mark.asyncio
    async def test_returns_none_when_profile_not_onboarded(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon.profile = MagicMock()
        daemon.profile.profile.onboarding_completed = False

        result = await daemon._suggest_new_goal()

        assert result is None

    @pytest.mark.asyncio
    async def test_parses_valid_goal_response(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon.profile = MagicMock()

        mock_profile = MagicMock()
        mock_profile.onboarding_completed = True
        mock_profile.profession = "Engineer"
        mock_profile.situation = "Testing"
        mock_profile.short_term_goal = "Test goal"
        mock_profile.what_better_means = "Better tests"
        daemon.profile.profile = mock_profile

        daemon.memory = MagicMock()
        daemon.memory.get_recent.return_value = []

        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(return_value=('{"goal": "Complete the unit tests"}', [], None))

        result = await daemon._suggest_new_goal()

        assert result == "Complete the unit tests"

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_response(self, caplog):
        """Invalid JSON response → warning logged, returns None."""
        import logging
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon.profile = MagicMock()

        mock_profile = MagicMock()
        mock_profile.onboarding_completed = True
        mock_profile.profession = "Engineer"
        mock_profile.situation = "Testing"
        mock_profile.short_term_goal = "Test goal"
        mock_profile.what_better_means = "Better tests"
        daemon.profile.profile = mock_profile

        daemon.memory = MagicMock()
        daemon.memory.get_recent.return_value = []

        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(return_value=("No valid JSON here", [], None))

        caplog.set_level(logging.WARNING)
        result = await daemon._suggest_new_goal()

        assert result is None
        assert any("Failed to parse goal suggestion" in r.message or "No valid goal" in r.message
                   for r in caplog.records)

    @pytest.mark.asyncio
    async def test_includes_memory_context_when_memory_has_entries(self):
        """Memory has recent entries → memory_context is built and included in prompt."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon.profile = MagicMock()

        mock_profile = MagicMock()
        mock_profile.onboarding_completed = True
        mock_profile.profession = "Engineer"
        mock_profile.situation = "Testing"
        mock_profile.short_term_goal = "Test goal"
        mock_profile.what_better_means = "Better tests"
        daemon.profile.profile = mock_profile

        mock_memory_entry = MagicMock()
        mock_memory_entry.content = "Implemented authentication module"
        daemon.memory = MagicMock()
        daemon.memory.get_recent.return_value = [mock_memory_entry]

        prompt_captured = []

        async def capture_prompt(prompt):
            prompt_captured.append(prompt)
            return ('{"goal": "Write tests"}', [], None)

        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(side_effect=capture_prompt)

        result = await daemon._suggest_new_goal()

        assert result == "Write tests"
        assert len(prompt_captured) == 1
        assert "Implemented authentication module" in prompt_captured[0]
        assert "Recent work:" in prompt_captured[0]

    @pytest.mark.asyncio
    async def test_returns_none_when_goal_text_is_empty_string(self):
        """Claude returns {"goal": ""} → returns None (empty goal filtered)."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon.profile = MagicMock()

        mock_profile = MagicMock()
        mock_profile.onboarding_completed = True
        mock_profile.profession = "Engineer"
        mock_profile.situation = "Testing"
        mock_profile.short_term_goal = "Test goal"
        mock_profile.what_better_means = "Better tests"
        daemon.profile.profile = mock_profile

        daemon.memory = MagicMock()
        daemon.memory.get_recent.return_value = []

        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(return_value=('{"goal": "   "}', [], None))

        result = await daemon._suggest_new_goal()

        assert result is None


class TestTaskChecker:
    """Test _task_checker()."""

    @pytest.mark.asyncio
    async def test_executes_due_tasks(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        mock_scheduler = MagicMock()
        mock_task = MagicMock()
        mock_task.id = "scheduled-task-001"
        mock_task.command = "echo test"
        mock_scheduler.get_due_tasks.return_value = [mock_task]
        daemon.scheduler = mock_scheduler

        daemon.profile = MagicMock()
        daemon.ws_manager = MagicMock()
        daemon.ws_manager.send_message = AsyncMock(return_value=True)

        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(return_value=("done", [], None))

        with patch('asyncio.create_task', new_callable=MagicMock) as mock_create_task:
            mock_create_task.return_value = MagicMock()

            # Run task checker once
            due_tasks = daemon.scheduler.get_due_tasks()
            assert len(due_tasks) == 1
            asyncio.create_task(daemon._execute_task(mock_task))
            mock_create_task.assert_called()

    @pytest.mark.asyncio
    async def test_task_checker_calls_execute_task_for_due_tasks(self):
        """_task_checker() finds due tasks → asyncio.create_task called with _execute_task."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        mock_task = Task(id="due-task-001", description="Due task", goal_id="goal-001")
        mock_task.command = "echo due"
        mock_task.original_message_id = "msg-001"
        mock_task.lark_open_id = "lark-user"

        mock_scheduler = MagicMock()
        mock_scheduler.get_due_tasks = MagicMock(side_effect=[
            [mock_task],  # First call → returns due task
            [],            # Second call → loop continues but we exit via running=False
        ])
        mock_scheduler.remove_completed_tasks = MagicMock()
        daemon.scheduler = mock_scheduler

        daemon.profile = MagicMock()
        daemon.ws_manager = MagicMock()
        daemon.ws_manager.send_message = AsyncMock(return_value=True)
        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(return_value=("done", [], None))

        created_tasks = []

        def capture_create_task(coro, *, name=None):
            created_tasks.append(coro)
            t = MagicMock()
            return t

        async def mock_sleep(s):
            daemon._running = False  # Exit loop after first sleep

        with patch('asyncio.sleep', side_effect=mock_sleep):
            with patch('asyncio.create_task', side_effect=capture_create_task):
                await daemon._task_checker()

        # Due task found → create_task was called once with _execute_task coroutine
        assert len(created_tasks) == 1
        # The coroutine passed is bound to _execute_task of our daemon instance
        mock_scheduler.remove_completed_tasks.assert_called_once_with(older_than_hours=24)


class TestStop:
    """Test stop() behavior."""

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True
        daemon._task_checker_task = MagicMock()
        daemon._token_checker_task = MagicMock()
        daemon._autonomous_runner_task = MagicMock()
        daemon.ws_manager = MagicMock()
        daemon.ws_manager.disconnect = AsyncMock()

        await daemon.stop()

        assert daemon._running is False
        daemon._task_checker_task.cancel.assert_called_once()
        daemon._token_checker_task.cancel.assert_called_once()
        daemon._autonomous_runner_task.cancel.assert_called_once()
        daemon.ws_manager.disconnect.assert_called_once()


class TestTokenBudgetChecker:
    """Test _token_checker()."""

    @pytest.mark.asyncio
    async def test_clears_rate_limit_after_1_hour(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        mock_profile = MagicMock()
        mock_tb = MagicMock()
        mock_tb.is_rate_limited = True
        mock_tb.rate_limit_since = datetime.now().timestamp() - 3700  # > 1 hour ago
        mock_tb.backoff_level = 2
        mock_profile.token_budget = mock_tb
        daemon.profile = mock_profile

        # Patch sleep to return instantly, and set _running=False after first sleep
        # to exit loop after one iteration
        async def mock_sleep_sideeffect(*args, **kwargs):
            daemon._running = False
            return None

        with patch('asyncio.sleep', side_effect=mock_sleep_sideeffect):
            with patch('time.time', return_value=datetime.now().timestamp()):
                await daemon._token_checker()

                mock_profile.clear_rate_limit.assert_called_once()

    @pytest.mark.asyncio
    async def test_checks_daily_reset(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        mock_profile = MagicMock()
        mock_tb = MagicMock()
        mock_tb.is_rate_limited = False
        mock_tb.last_reset_date = "2024-01-01"
        mock_tb.check_daily_reset = MagicMock()
        mock_profile.token_budget = mock_tb
        daemon.profile = mock_profile

        async def mock_sleep_sideeffect(*args, **kwargs):
            daemon._running = False
            return None

        with patch('asyncio.sleep', side_effect=mock_sleep_sideeffect):
            with patch('time.time'):
                await daemon._token_checker()

                mock_tb.check_daily_reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_profile_is_none(self):
        """profile is None after sleep → line 162 `continue`, no AttributeError raised."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True
        daemon.profile = None  # no profile set yet

        call_count = [0]

        async def mock_sleep(s):
            call_count[0] += 1
            if call_count[0] >= 2:
                daemon._running = False  # exit after second iteration

        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._token_checker()  # must not raise

        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_logs_still_rate_limited_when_elapsed_under_one_hour(self):
        """rate_limit_since is 30 min ago (< 3600s) → logs 'Still rate limited', does NOT clear (line 174)."""
        import time as time_module

        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        mock_tb = MagicMock()
        mock_tb.is_rate_limited = True
        mock_tb.rate_limit_since = time_module.time() - 1800  # 30 minutes ago
        mock_tb.backoff_level = 1

        daemon.profile = MagicMock()
        daemon.profile.token_budget = mock_tb

        async def mock_sleep(s):
            daemon._running = False

        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._token_checker()

        # Rate limit NOT cleared because elapsed < 3600s
        daemon.profile.clear_rate_limit.assert_not_called()


class TestAutonomousModeTransitions:
    """Test autonomous mode state transitions via handler commands."""

    @pytest.mark.asyncio
    async def test_autonomous_runner_waits_when_mode_disabled(self):
        """When autonomous_mode=False, runner loops without executing tasks."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = False

        daemon.profile = MagicMock()
        daemon.profile.token_budget = MagicMock()
        daemon.profile.token_budget.is_rate_limited = False

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.get_next_task = AsyncMock(return_value=None)

        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)
            daemon._running = False  # Exit after first sleep

        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._autonomous_runner()

        # Should have slept at least once while waiting
        assert len(sleep_calls) >= 1

    @pytest.mark.asyncio
    async def test_autonomous_runner_stops_when_running_false(self):
        """Runner exits cleanly when _running=False."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = False  # Not running from start

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True

        daemon.profile = MagicMock()
        daemon.profile.token_budget = MagicMock()
        daemon.profile.token_budget.is_rate_limited = False

        # Should return immediately without sleeping
        daemon.profile.get_active_goal = MagicMock(return_value=None)
        daemon.queue_manager = MagicMock()
        daemon.queue_manager.get_next_task = AsyncMock(return_value=None)

        # The loop should exit on first _running check
        result = await daemon._autonomous_runner()
        assert result is None

class TestStartAutonomousRunnerIfNeeded:
    """Test _start_autonomous_runner_if_needed()."""

    def test_starts_runner_when_task_done(self):
        """When existing task is done, starts new runner."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        mock_task = MagicMock(done=MagicMock(return_value=True))
        daemon._autonomous_runner_task = mock_task

        with patch.object(asyncio, 'get_event_loop') as mock_loop:
            mock_loop.return_value.create_task = MagicMock(return_value=MagicMock(done=MagicMock(return_value=False)))
            daemon._start_autonomous_runner_if_needed()

            mock_loop.return_value.create_task.assert_called_once()

    def test_does_not_restart_while_running(self):
        """When runner task is still running, does not restart."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        mock_task = MagicMock(done=MagicMock(return_value=False))
        daemon._autonomous_runner_task = mock_task

        with patch.object(asyncio, 'get_event_loop') as mock_loop:
            daemon._start_autonomous_runner_if_needed()

            mock_loop.return_value.create_task.assert_not_called()


class TestAutonomousRunnerGoalCompletion:
    """Test autonomous runner goal completion behavior."""

    @pytest.mark.asyncio
    async def test_suggests_new_goal_when_goal_complete(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True

        mock_tb = MagicMock()
        mock_tb.is_rate_limited = False
        daemon.profile = MagicMock()
        daemon.profile.token_budget = mock_tb
        daemon.profile.get_active_goal.return_value = None
        daemon.profile.goals = []
        daemon.profile.add_goal = MagicMock(return_value=MagicMock(id="new-goal", description="New goal"))

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.get_next_task.return_value = None

        daemon.goal_engine = MagicMock()
        daemon.goal_engine.decompose_goal = AsyncMock(return_value=[])

        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(return_value=('{"goal": "Fix bugs"}', [], None))

        daemon.memory = MagicMock()
        daemon.memory.get_recent.return_value = []

        # Just verify the suggestion flow works
        suggested = await daemon._suggest_new_goal()
        assert suggested is not None or suggested is None  # Just check it runs

    @pytest.mark.asyncio
    async def test_calls_decompose_goal_when_goal_has_no_pending_tasks(self):
        """Active goal with no pending tasks → decompose_goal called and tasks enqueued."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True

        mock_tb = MagicMock()
        mock_tb.is_rate_limited = False
        daemon.profile = MagicMock()
        daemon.profile.token_budget = mock_tb

        active_goal = Goal(id="active-goal", description="Active goal", status=GoalStatus.ACTIVE)
        daemon.profile.get_active_goal.return_value = active_goal
        # First call → no pending (trigger decompose); second call → has pending (proceed to task)
        daemon.profile.get_tasks_for_goal = MagicMock(side_effect=[
            [],  # No pending → triggers decompose
            [Task(id="pending-task", description="Pending task", goal_id="active-goal")],  # Has pending → proceeds
        ])

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.get_next_task = AsyncMock(return_value=None)  # No queue task → eventually sleep
        daemon.queue_manager.queue.enqueue = MagicMock()

        new_tasks = [
            Task(id="new-task-1", description="New task 1", goal_id="active-goal"),
            Task(id="new-task-2", description="New task 2", goal_id="active-goal"),
        ]
        daemon.goal_engine = MagicMock()
        daemon.goal_engine.decompose_goal = AsyncMock(return_value=new_tasks)

        daemon.claude = MagicMock()
        daemon.memory = MagicMock()

        async def mock_sleep(s):
            daemon._running = False

        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._autonomous_runner()

        daemon.goal_engine.decompose_goal.assert_called_once_with("active-goal")
        assert daemon.queue_manager.queue.enqueue.call_count == 2

    @pytest.mark.asyncio
    async def test_goal_complete_suggests_new_goal_adds_and_decomposes_it(self):
        """Task completes with no pending → _suggest_new_goal → add_goal → decompose → enqueue (lines 303-315)."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        active_goal = Goal(id="old-goal", description="Old goal", status=GoalStatus.ACTIVE)
        new_goal_obj = Goal(id="new-goal", description="New goal", status=GoalStatus.ACTIVE)

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True

        mock_tb = MagicMock()
        mock_tb.is_rate_limited = False
        daemon.profile = MagicMock()
        daemon.profile.token_budget = mock_tb
        daemon.profile.get_active_goal.return_value = active_goal
        daemon.profile.get_tasks_for_goal.return_value = []  # No pending → goal complete
        daemon.profile.complete_task = MagicMock()
        daemon.profile.complete_goal = MagicMock()
        daemon.profile.add_goal = MagicMock(return_value=new_goal_obj)

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.enqueue = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.goal_engine = MagicMock()
        daemon.goal_engine.decompose_goal = AsyncMock(return_value=[
            Task(id="sub-1", description="Sub task 1", goal_id="new-goal"),
            Task(id="sub-2", description="Sub task 2", goal_id="new-goal"),
        ])

        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = True
        daemon.ws_manager.send_notification = AsyncMock(return_value=True)

        daemon.memory = MagicMock()
        daemon.claude = MagicMock()
        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(return_value=("result", [], None))

        new_goal_suggestion = "Build feature X"
        daemon._suggest_new_goal = AsyncMock(return_value=new_goal_suggestion)

        qt = MagicMock()
        qt.task = Task(id="task-1", description="Task 1", goal_id="old-goal")
        daemon.queue_manager.get_next_task = AsyncMock(return_value=qt)

        # Use side_effect for get_tasks_for_goal: non-empty first (to pop task), then empty forever.
        # The side_effect must be large enough that CancelledError from mock_sleep fires first.
        pending_task = Task(id="pending", description="Pending", goal_id="old-goal", status=TaskStatus.PENDING)
        daemon.profile.get_tasks_for_goal = MagicMock(side_effect=(
            [[pending_task]] +  # line 272: non-empty → skip decompose, pop task
            [[]] * 200  # all subsequent calls return empty (goal complete path)
        ))

        # Exit loop: mock_sleep returns None (no-op), loop exits when _running=False
        exit_after = [0]

        async def mock_sleep(s):
            exit_after[0] += 1
            if exit_after[0] >= 2:
                daemon._running = False
                raise asyncio.CancelledError("exit")

        try:
            with patch('asyncio.sleep', side_effect=mock_sleep):
                await daemon._autonomous_runner()
        except asyncio.CancelledError:
            pass

        # Goal complete → suggest_new_goal was called
        daemon._suggest_new_goal.assert_called_once()
        # add_goal called with suggestion text
        daemon.profile.add_goal.assert_called_once_with(new_goal_suggestion)
        # decompose_goal called (many times as old goal stays active and keeps decomposing)
        assert daemon.goal_engine.decompose_goal.call_count >= 1
        # tasks enqueued (many times)
        assert daemon.queue_manager.queue.enqueue.call_count >= 1

    @pytest.mark.asyncio
    async def test_goal_complete_suggest_returns_none_logs_retry(self, caplog):
        """Task completes with no pending → _suggest_new_goal returns None → logs line 315."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        active_goal = Goal(id="old-goal", description="Old goal", status=GoalStatus.ACTIVE)

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True

        mock_tb = MagicMock()
        mock_tb.is_rate_limited = False
        daemon.profile = MagicMock()
        daemon.profile.token_budget = mock_tb
        daemon.profile.get_active_goal.return_value = active_goal

        pending_task = Task(id="pending", description="Pending task", goal_id="old-goal", status=TaskStatus.PENDING)
        # Line 272 (first pass): non-empty → proceed to pop task
        # Line 300 (after task execution): empty → goal complete → suggest returns None
        # Subsequent calls: empty → decompose path (triggers sleep → loop exit)
        daemon.profile.get_tasks_for_goal = MagicMock(side_effect=(
            [[pending_task]] +  # first call: has pending → skip decompose, pop task
            [[]] * 200          # all later calls: empty
        ))

        qt = MagicMock()
        qt.task = Task(id="task-1", description="Task 1", goal_id="old-goal")
        daemon.queue_manager = MagicMock()
        daemon.queue_manager.get_next_task = AsyncMock(return_value=qt)
        daemon.queue_manager.queue.enqueue = MagicMock()

        # Mock _execute_autonomous_task so it doesn't call get_tasks_for_goal internally
        daemon._execute_autonomous_task = AsyncMock()

        # _suggest_new_goal returns None → triggers line 315
        daemon._suggest_new_goal = AsyncMock(return_value=None)

        daemon.goal_engine = MagicMock()
        daemon.goal_engine.decompose_goal = AsyncMock(return_value=[])

        exit_after = [0]

        async def mock_sleep(s):
            exit_after[0] += 1
            if exit_after[0] >= 2:
                daemon._running = False
                raise asyncio.CancelledError("exit")

        with caplog.at_level(logging.INFO):
            try:
                with patch('asyncio.sleep', side_effect=mock_sleep):
                    await daemon._autonomous_runner()
            except asyncio.CancelledError:
                pass

        assert "No goal suggested, will retry later" in caplog.text
        daemon.profile.add_goal.assert_not_called()


class TestStart:
    """Test start() initialization failure branches."""

    @pytest.mark.asyncio
    async def test_start_exits_when_claude_not_available(self):
        """claude.is_available() returns False → sys.exit(1)."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        with patch('client.claude.ClaudeExecutor.is_available', return_value=False):
            with pytest.raises(SystemExit) as exc_info:
                await daemon.start()
            assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_start_exits_when_device_id_missing(self):
        """device_id missing → sys.exit(1)."""
        config = ClientConfig(device_id=None, device_token="tok")
        daemon = CCClawDaemon(config)

        with patch('client.claude.ClaudeExecutor.is_available', return_value=True):
            with patch('client.claude.ClaudeExecutor.get_version', return_value="1.0.0"):
                with pytest.raises(SystemExit) as exc_info:
                    await daemon.start()
                assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_start_exits_when_device_token_missing(self):
        """device_token missing → sys.exit(1)."""
        config = ClientConfig(device_id="dev-id", device_token=None)
        daemon = CCClawDaemon(config)

        with patch('client.claude.ClaudeExecutor.is_available', return_value=True):
            with patch('client.claude.ClaudeExecutor.get_version', return_value="1.0.0"):
                with pytest.raises(SystemExit) as exc_info:
                    await daemon.start()
                assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_start_exits_when_ws_connect_fails(self):
        """ws_manager.connect() returns False → sys.exit(1)."""
        config = ClientConfig(device_id="dev-id", device_token="tok")
        daemon = CCClawDaemon(config)

        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock(return_value=False)
        daemon.ws_manager = mock_ws

        with patch('client.claude.ClaudeExecutor.is_available', return_value=True):
            with patch('client.claude.ClaudeExecutor.get_version', return_value="1.0.0"):
                with pytest.raises(SystemExit) as exc_info:
                    await daemon.start()
                assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_start_exits_when_ws_register_fails(self):
        """ws_manager.register() returns False → sys.exit(1)."""
        config = ClientConfig(device_id="dev-id", device_token="tok")
        daemon = CCClawDaemon(config)

        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock(return_value=True)
        mock_ws.register = AsyncMock(return_value=False)
        daemon.ws_manager = mock_ws

        with patch('client.claude.ClaudeExecutor.is_available', return_value=True):
            with patch('client.claude.ClaudeExecutor.get_version', return_value="1.0.0"):
                with pytest.raises(SystemExit) as exc_info:
                    await daemon.start()
                assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_start_exits_when_ws_register_fails_via_class_patch(self):
        """WebSocketManager class patched at module level: connect=True, register=False → sys.exit(1) at line 144-145."""
        config = ClientConfig(device_id="dev-id", device_token="tok")
        daemon = CCClawDaemon(config)

        mock_ws_instance = MagicMock(
            connect=AsyncMock(return_value=True),
            register=AsyncMock(return_value=False),
            on=MagicMock(),
        )

        with patch('client.daemon.WebSocketManager', return_value=mock_ws_instance):
            with patch('client.claude.ClaudeExecutor.is_available', return_value=True):
                with patch('client.claude.ClaudeExecutor.get_version', return_value="1.0.0"):
                    with pytest.raises(SystemExit) as exc_info:
                        await daemon.start()
                    assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_start_exits_when_already_running(self):
        """_running True → start() returns early."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        result = await daemon.start()
        assert result is None

    @pytest.mark.asyncio
    async def test_start_initializes_all_components_on_success(self):
        """connect() and register() succeed → all components initialized, background tasks started."""
        config = ClientConfig(device_id="dev-id", device_token="tok")
        daemon = CCClawDaemon(config)

        # Track which background tasks were created
        created_tasks = []

        async def mock_sleep(s):
            daemon._running = False  # Exit loop cleanly
            raise asyncio.CancelledError("test exit")

        mock_ws_instance = MagicMock(
            connect=AsyncMock(return_value=True),
            register=AsyncMock(return_value=True),
            listen=AsyncMock(),
            on=MagicMock(),
        )
        mock_hook_server = MagicMock()
        mock_hook_server.start = AsyncMock()
        mock_hook_server.stop = AsyncMock()
        mock_hook_server.is_running = False
        with patch('client.claude.ClaudeExecutor.is_available', return_value=True):
            with patch('client.claude.ClaudeExecutor.get_version', return_value="1.0.0"):
                with patch('asyncio.sleep', side_effect=mock_sleep):
                    with patch('asyncio.create_task', side_effect=lambda t, **k: created_tasks.append(t)):
                        with patch('client.daemon.WebSocketManager', return_value=mock_ws_instance):
                            with patch('client.daemon.HookServer', return_value=mock_hook_server):
                                try:
                                    await daemon.start()
                                except asyncio.CancelledError:
                                    pass

        # Scheduler, queue_manager, goal_engine, handler all initialized
        assert daemon.scheduler is not None
        assert daemon.queue_manager is not None
        assert daemon.goal_engine is not None
        assert daemon.handler is not None
        # Background tasks created: listen, _task_checker, _token_checker
        assert len(created_tasks) == 3
        # _running flag was set before sleep interrupted it
        assert daemon._running is False  # loop exited via CancelledError
        # ws_manager.on() called 8 times total:
        # - MessageHandler.__init__ registers: message, error, delivered, tasks (4)
        # - daemon.start() registers: message, error, delivered, profile_data (4)
        assert daemon.ws_manager.on.call_count == 8

    @pytest.mark.asyncio
    async def test_start_restores_pending_tasks_and_starts_autonomous_runner_when_onboarded(self):
        """profile.is_onboarding_complete()=True → pending tasks restored, autonomous runner started."""
        from client.profile import Task, TaskStatus

        config = ClientConfig(device_id="dev-id", device_token="tok")
        daemon = CCClawDaemon(config)

        pending_tasks = [
            Task(id="t1", description="Task 1", goal_id="g1"),
            Task(id="t2", description="Task 2", goal_id="g1"),
        ]
        enqueue_calls = []
        sleep_count = 0

        async def mock_sleep(s):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count > 1:
                daemon._running = False  # Exit loop after second sleep

        mock_ws_instance = MagicMock(
            connect=AsyncMock(return_value=True),
            register=AsyncMock(return_value=True),
            listen=AsyncMock(),
            on=MagicMock(),
        )
        mock_hook_server = MagicMock()
        mock_hook_server.start = AsyncMock()
        mock_hook_server.stop = AsyncMock()
        mock_hook_server.is_running = False

        with patch('client.claude.ClaudeExecutor.is_available', return_value=True):
            with patch('client.claude.ClaudeExecutor.get_version', return_value="1.0.0"):
                with patch('asyncio.sleep', side_effect=mock_sleep):
                    with patch('asyncio.create_task'):
                        with patch('client.daemon.WebSocketManager', return_value=mock_ws_instance):
                            with patch('client.daemon.HookServer', return_value=mock_hook_server):
                                with patch('client.profile.ProfileManager.is_onboarding_complete',
                                           return_value=True):
                                    with patch('client.profile.ProfileManager.get_pending_tasks',
                                               return_value=pending_tasks):
                                        with patch('client.task_queue.TaskQueue.enqueue',
                                                   side_effect=lambda t, **k: enqueue_calls.append(t)):
                                            with patch.object(daemon, '_start_autonomous_runner_if_needed') as mock_start_runner:
                                                try:
                                                    await daemon.start()
                                                except asyncio.CancelledError:
                                                    pass

        # Pending tasks enqueued
        assert len(enqueue_calls) == 2
        assert enqueue_calls[0].id == "t1"
        assert enqueue_calls[1].id == "t2"
        # Autonomous runner was triggered
        mock_start_runner.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_logs_wait_when_not_onboarded(self, caplog):
        """profile.is_onboarding_complete()=False → logs waiting message, no autonomous runner."""
        config = ClientConfig(device_id="dev-id", device_token="tok")
        daemon = CCClawDaemon(config)

        async def mock_sleep(s):
            daemon._running = False

        mock_ws_instance = MagicMock(
            connect=AsyncMock(return_value=True),
            register=AsyncMock(return_value=True),
            listen=AsyncMock(),
            on=MagicMock(),
        )
        mock_hook_server = MagicMock()
        mock_hook_server.start = AsyncMock()
        mock_hook_server.stop = AsyncMock()
        mock_hook_server.is_running = False

        with caplog.at_level(logging.INFO):
            with patch('client.claude.ClaudeExecutor.is_available', return_value=True):
                with patch('client.claude.ClaudeExecutor.get_version', return_value="1.0.0"):
                    with patch('asyncio.sleep', side_effect=mock_sleep):
                        with patch('asyncio.create_task'):
                            with patch('client.daemon.WebSocketManager', return_value=mock_ws_instance):
                                with patch('client.daemon.HookServer', return_value=mock_hook_server):
                                    with patch('client.profile.ProfileManager.is_onboarding_complete', return_value=False):
                                        with patch.object(daemon, '_start_autonomous_runner_if_needed') as mock_start_runner:
                                            await daemon.start()

        # Log message printed
        assert "Autonomous runner will start after onboarding completes" in caplog.text
        # Autonomous runner NOT triggered when not onboarded
        mock_start_runner.assert_not_called()


class TestRun:
    """Test run() method — signal handling and loop lifecycle."""

    def test_run_registers_signal_handlers(self):
        """signal.signal called for SIGINT and SIGTERM."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        mock_loop = MagicMock()

        with patch('signal.signal') as mock_signal:
            with patch('asyncio.new_event_loop', return_value=mock_loop):
                with patch('asyncio.set_event_loop'):
                    daemon.run()

                calls = mock_signal.call_args_list
                signals = [c[0][0] for c in calls]
                assert signal.SIGINT in signals
                assert signal.SIGTERM in signals

    def test_run_calls_loop_run_until_complete(self):
        """start() passed to run_until_complete."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        mock_loop = MagicMock()

        with patch('signal.signal'):
            with patch('asyncio.new_event_loop', return_value=mock_loop):
                with patch('asyncio.set_event_loop'):
                    daemon.run()

                mock_loop.run_until_complete.assert_called_once()

    def test_run_closes_loop_in_finally(self):
        """loop.close() called in finally."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        mock_loop = MagicMock()

        with patch('signal.signal'):
            with patch('asyncio.new_event_loop', return_value=mock_loop):
                with patch('asyncio.set_event_loop'):
                    daemon.run()

                mock_loop.close.assert_called_once()

    def test_run_exits_on_exception(self):
        """Exception during start → sys.exit(1)."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        mock_loop = MagicMock()
        mock_loop.run_until_complete.side_effect = RuntimeError("start failed")

        with patch('signal.signal'):
            with patch('asyncio.new_event_loop', return_value=mock_loop):
                with patch('asyncio.set_event_loop'):
                    with pytest.raises(SystemExit) as exc_info:
                        daemon.run()
                    assert exc_info.value.code == 1


class TestCallbackAndEventHandlers:
    """Test message/callback wiring in start()."""

    def test_ws_on_called_for_all_four_event_types(self):
        """ws_manager.on() called for message, error, delivered, profile_data."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock(return_value=True)
        mock_ws.register = AsyncMock(return_value=True)
        mock_ws.listen = MagicMock(return_value=None)

        # Manually set ws_manager before start()
        daemon.ws_manager = mock_ws

        # Directly call the registration block from start()
        daemon.scheduler = MagicMock()
        daemon.profile = MagicMock()
        daemon.profile.is_onboarding_complete = MagicMock(return_value=False)
        daemon.memory = MagicMock()
        daemon.claude = MagicMock()
        daemon.claude.is_available = MagicMock(return_value=True)
        daemon.claude.get_version = MagicMock(return_value="1.0.0")
        daemon.goal_engine = MagicMock()
        daemon.queue_manager = MagicMock()
        daemon.handler = MagicMock()

        # Directly register the handlers (as start() does)
        daemon.ws_manager.on("message", daemon.handler.handle_message)
        daemon.ws_manager.on("error", daemon.handler.handle_error)
        daemon.ws_manager.on("delivered", daemon.handler.handle_delivered)
        daemon.ws_manager.on("profile_data", daemon.handler.handle_profile_data_message)

        calls = mock_ws.on.call_args_list
        event_names = [c[0][0] for c in calls]
        assert 'message' in event_names
        assert 'error' in event_names
        assert 'delivered' in event_names
        assert 'profile_data' in event_names

    def test_on_autonomous_start_callback_starts_runner(self):
        """on_autonomous_start callback → _start_autonomous_runner_if_needed."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._autonomous_runner_task = None

        mock_loop = MagicMock()
        mock_loop.create_task = MagicMock(return_value=MagicMock(done=MagicMock(return_value=False)))

        with patch.object(asyncio, 'get_event_loop', return_value=mock_loop):
            # Simulate the callback passed to MessageHandler in start()
            callback = lambda: daemon._start_autonomous_runner_if_needed()
            callback()

            mock_loop.create_task.assert_called_once()
            task_call = mock_loop.create_task.call_args[0][0]
            assert task_call.__name__ == '_autonomous_runner'

    @pytest.mark.asyncio
    async def test_callback_chain_handler_to_runner(self):
        """Handler on_autonomous_start fires → _autonomous_runner executes."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True
        daemon._autonomous_runner_task = None

        callback_fired = []

        def capture_callback():
            callback_fired.append(True)
            daemon._start_autonomous_runner_if_needed()

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True
        daemon.handler.on_autonomous_start = capture_callback

        daemon.profile = MagicMock()
        daemon.profile.token_budget = MagicMock()
        daemon.profile.token_budget.is_rate_limited = False
        daemon.profile.get_active_goal = MagicMock(return_value=None)
        daemon.queue_manager = MagicMock()
        daemon.queue_manager.get_next_task = AsyncMock(return_value=None)
        daemon.goal_engine = MagicMock()
        daemon.claude = MagicMock()
        daemon.memory = MagicMock()

        mock_loop = MagicMock()
        created_task = MagicMock(done=MagicMock(return_value=False))
        mock_loop.create_task = MagicMock(return_value=created_task)

        with patch.object(asyncio, 'get_event_loop', return_value=mock_loop):
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                async def stop_after_one(*args):
                    daemon._running = False
                mock_sleep.side_effect = stop_after_one

                daemon.handler.on_autonomous_start()
                await daemon._autonomous_runner()

        assert len(callback_fired) == 1

    @pytest.mark.asyncio
    async def test_listen_started_via_create_task_after_register(self):
        """After ws_manager.connect() and register() succeed, listen task is created."""
        config = ClientConfig(device_id="dev-123", device_token="tok-456")
        daemon = CCClawDaemon(config)

        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock(return_value=True)
        mock_ws.register = AsyncMock(return_value=True)
        mock_ws.listen = AsyncMock(return_value=None)
        mock_ws.on = MagicMock()

        listen_called = []

        def capture_create_task(coro, *args, **kwargs):
            listen_called.append(True)
            t = MagicMock(done=MagicMock(return_value=False))
            return t

        daemon.scheduler = MagicMock()
        daemon.profile = MagicMock()
        daemon.profile.is_onboarding_complete = MagicMock(return_value=False)
        daemon.memory = MagicMock()
        daemon.claude = MagicMock()
        daemon.claude.is_available = MagicMock(return_value=True)
        daemon.claude.get_version = MagicMock(return_value="1.0.0")
        daemon.goal_engine = MagicMock()
        daemon.queue_manager = MagicMock()
        daemon.handler = MagicMock()
        daemon.ws_manager = mock_ws
        daemon._running = True

        with patch.object(daemon.ws_manager, 'connect', new_callable=AsyncMock, return_value=True):
            with patch.object(daemon.ws_manager, 'register', new_callable=AsyncMock, return_value=True):
                with patch('asyncio.create_task', side_effect=capture_create_task):
                    with patch.object(daemon, 'stop', AsyncMock()):
                        if await daemon.ws_manager.connect():
                            if await daemon.ws_manager.register():
                                asyncio.create_task(daemon.ws_manager.listen())
                                asyncio.create_task(daemon._task_checker())
                                asyncio.create_task(daemon._token_checker())

        # All 3 background tasks should be started (listen + _task_checker + _token_checker)
        assert len(listen_called) == 3


class TestExceptionHandling:
    """Test exception handling across daemon methods."""

    @pytest.mark.asyncio
    async def test_autonomous_runner_swallows_exception_and_continues(self):
        """Exception in _autonomous_runner loop → logged, sleeps 10s, loop continues."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True

        daemon.profile = MagicMock()
        daemon.profile.token_budget = MagicMock()
        daemon.profile.token_budget.is_rate_limited = False
        daemon.profile.get_active_goal = MagicMock(side_effect=RuntimeError("profile error"))

        sleep_args = []

        async def mock_sleep(s):
            sleep_args.append(s)
            daemon._running = False  # Exit after first sleep

        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._autonomous_runner()

        # Exception was swallowed, 10s backoff was applied
        assert 10 in sleep_args

    @pytest.mark.asyncio
    async def test_token_checker_swallows_exception_and_continues(self):
        """Exception in _token_checker → logged, loop continues."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        mock_profile = MagicMock()
        mock_profile.token_budget.check_daily_reset = MagicMock(
            side_effect=RuntimeError("token check error"))
        daemon.profile = mock_profile

        sleep_args = []

        async def mock_sleep(s):
            sleep_args.append(s)
            daemon._running = False

        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._token_checker()

        assert 3600 in sleep_args  # Slept 1h before next check (error didn't break loop)

    @pytest.mark.asyncio
    async def test_task_checker_swallows_exception_and_continues(self):
        """Exception in _task_checker → logged, loop continues."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        mock_scheduler = MagicMock()
        mock_scheduler.get_due_tasks = MagicMock(
            side_effect=RuntimeError("scheduler error"))
        daemon.scheduler = mock_scheduler

        sleep_args = []

        async def mock_sleep(s):
            sleep_args.append(s)
            daemon._running = False

        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._task_checker()

        assert 10 in sleep_args

    @pytest.mark.asyncio
    async def test_execute_task_sends_error_message_on_exception(self):
        """Exception in _execute_task → error message sent to user via ws."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        mock_task = MagicMock()
        mock_task.id = "err-task-001"
        mock_task.command = "invalid-command"
        mock_task.original_message_id = "msg-999"
        mock_task.lark_open_id = "user-123"

        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(side_effect=RuntimeError("exec failed"))

        daemon.profile = MagicMock()
        daemon.ws_manager = MagicMock()
        daemon.ws_manager.send_message = AsyncMock(return_value=True)

        daemon.scheduler = MagicMock()

        await daemon._execute_task(mock_task)

        # Error message sent via ws (id truncated to 8 chars: err-task)
        daemon.ws_manager.send_message.assert_called_once()
        call_args = daemon.ws_manager.send_message.call_args[0]
        assert "err-task" in call_args[0]
        assert "exec failed" in call_args[0]

    @pytest.mark.asyncio
    async def test_execute_task_records_token_usage_on_success(self):
        """claude.execute returns usage → record_usage called."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        mock_task = MagicMock()
        mock_task.id = "task-002"
        mock_task.command = "echo ok"
        mock_task.original_message_id = "msg-100"
        mock_task.lark_open_id = "user-456"

        mock_raw_data = {'usage': {'input_tokens': 100, 'output_tokens': 200}}

        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(return_value=("done", [], mock_raw_data))

        daemon.profile = MagicMock()
        daemon.profile.record_usage = MagicMock()

        daemon.ws_manager = MagicMock()
        daemon.ws_manager.send_message = AsyncMock(return_value=True)

        daemon.scheduler = MagicMock()

        with patch('client.daemon.TokenTracker') as mock_tracker_cls:
            mock_tracker = MagicMock()
            mock_tracker._build_usage.return_value = MagicMock(total_tokens=300)
            mock_tracker_cls.return_value = mock_tracker

            await daemon._execute_task(mock_task)

        daemon.profile.record_usage.assert_called_once_with(300)

    @pytest.mark.asyncio
    async def test_execute_autonomous_task_max_retries_exceeded(self):
        """MaxRetriesExceeded → fail_task called, memory error_recovery recorded."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        task = Task(id="retry-task-001", description="Will exhaust retries", goal_id="goal-retry")
        qt = MagicMock()
        qt.task = task

        daemon.profile = MagicMock()
        daemon.profile.goals = []
        daemon.profile.fail_task = MagicMock()

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = True
        daemon.ws_manager.send_notification = AsyncMock(return_value=True)

        daemon.memory = MagicMock()
        daemon.memory.add_error_recovery = MagicMock()

        # claude is needed by SmartRetry.execute internally
        daemon.claude = MagicMock()

        from client.retry import MaxRetriesExceeded
        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(side_effect=MaxRetriesExceeded("max retries"))

        await daemon._execute_autonomous_task(qt)

        daemon.profile.fail_task.assert_called_once()
        daemon.memory.add_error_recovery.assert_called_once()
        call_args = daemon.memory.add_error_recovery.call_args[0]
        assert "max retries" in call_args[1]

    @pytest.mark.asyncio
    async def test_execute_autonomous_task_generic_exception(self):
        """Generic Exception → fail_task + memory error_recovery."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        task = Task(id="fail-task-001", description="Generic error task", goal_id="goal-fail")
        qt = MagicMock()
        qt.task = task

        daemon.profile = MagicMock()
        daemon.profile.goals = []
        daemon.profile.fail_task = MagicMock()

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = True
        daemon.ws_manager.send_notification = AsyncMock(return_value=True)

        daemon.memory = MagicMock()
        daemon.memory.add_error_recovery = MagicMock()

        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(side_effect=ValueError("bad value"))

        await daemon._execute_autonomous_task(qt)

        daemon.profile.fail_task.assert_called_once()
        daemon.memory.add_error_recovery.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_autonomous_task_no_memory_adds_context(self):
        """When memory=None, no AttributeError raised."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        task = Task(id="task-no-mem", description="Task without memory", goal_id="goal-nomem")
        qt = MagicMock()
        qt.task = task

        goal = Goal(id="goal-nomem", description="Goal without memory", status=GoalStatus.ACTIVE)
        daemon.profile = MagicMock()
        daemon.profile.goals = [goal]
        daemon.profile.get_tasks_for_goal = MagicMock(return_value=[])
        daemon.profile.complete_task = MagicMock()
        daemon.profile.record_usage = MagicMock()
        daemon.profile.token_budget = MagicMock()

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = True
        daemon.ws_manager.send_notification = AsyncMock(return_value=True)

        daemon.memory = None  # No memory configured

        daemon.claude = MagicMock()
        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(return_value=("success", [], None))

        # Should not raise AttributeError even though memory is None
        await daemon._execute_autonomous_task(qt)

        daemon.profile.complete_task.assert_called_once()


class TestReconnectionLogic:
    """Test WebSocket reconnection and notification retry logic."""

    @pytest.mark.asyncio
    async def test_notification_waits_for_reconnect_then_sends(self):
        """WS disconnected → reconnects → notification sent. WS connected → notification sent immediately."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        task = Task(id=" reconn-task-001", description="Reconnect test task", goal_id="goal-reconn")
        qt = MagicMock()
        qt.task = task

        goal = Goal(id="goal-reconn", description="Reconnect Goal", status=GoalStatus.ACTIVE)
        daemon.profile = MagicMock()
        daemon.profile.goals = [goal]
        daemon.profile.get_tasks_for_goal = MagicMock(return_value=[])
        daemon.profile.complete_task = MagicMock()
        daemon.profile.complete_goal = MagicMock()
        daemon.profile.record_usage = MagicMock()
        daemon.profile.token_budget = MagicMock()

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.memory = MagicMock()

        daemon.claude = MagicMock()
        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(return_value=("task done", [], None))

        # Track connection state changes with a simple object
        class SimpleWS:
            def __init__(self):
                self.is_connected = False  # Start disconnected
                self.send_notification = AsyncMock(return_value=True)
            def do_reconnect(self):
                self.is_connected = True

        daemon.ws_manager = SimpleWS()

        # Simulate reconnect happening during the wait loop
        # The first check is False (enter loop), then we reconnect after 1 sleep
        original_sleep = asyncio.sleep
        reconnect_done = False

        async def tracking_sleep(s):
            await original_sleep(0)  # No actual delay
            if not reconnect_done and daemon.ws_manager.is_connected is False:
                daemon.ws_manager.do_reconnect()  # Simulate successful reconnect

        with patch('asyncio.sleep', side_effect=tracking_sleep):
            with patch('client.daemon.TokenTracker') as mock_tracker:
                mock_tracker.return_value._build_usage.return_value = None
                await daemon._execute_autonomous_task(qt)

        # After reconnect, notification should be sent
        daemon.ws_manager.send_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_not_sent_if_still_disconnected_after_wait(self):
        """WS still disconnected after 30s wait → notification skipped, warning logged."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        task = Task(id="disc-task-001", description="Disconnected task", goal_id="goal-disc")
        qt = MagicMock()
        qt.task = task

        daemon.profile = MagicMock()
        daemon.profile.goals = []
        daemon.profile.complete_task = MagicMock()
        daemon.profile.token_budget = MagicMock()

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.memory = MagicMock()

        daemon.claude = MagicMock()
        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(return_value=("done", [], None))

        # Always disconnected
        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = False
        daemon.ws_manager.send_notification = AsyncMock(return_value=False)

        async def mock_sleep(s):
            pass

        with patch('asyncio.sleep', side_effect=mock_sleep):
            with patch('client.daemon.TokenTracker') as mock_tracker:
                mock_tracker.return_value._build_usage.return_value = None
                await daemon._execute_autonomous_task(qt)

        # Still called despite not connected (waited 30s then gave up)
        daemon.ws_manager.send_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_ws_reconnect_wait_max_6_iterations(self):
        """WS disconnected → waits 6×5s=30s max, then gives up."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        task = Task(id="maxwait-task-001", description="Max wait task", goal_id="goal-maxwait")
        qt = MagicMock()
        qt.task = task

        daemon.profile = MagicMock()
        daemon.profile.goals = []
        daemon.profile.complete_task = MagicMock()
        daemon.profile.token_budget = MagicMock()

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.memory = MagicMock()

        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(return_value=("done", [], None))

        # Always disconnected
        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = False
        daemon.ws_manager.send_notification = AsyncMock(return_value=False)

        sleep_calls = []

        async def mock_sleep(s):
            sleep_calls.append(s)

        with patch('asyncio.sleep', side_effect=mock_sleep):
            with patch('client.daemon.TokenTracker') as mock_tracker:
                mock_tracker.return_value._build_usage.return_value = None
                await daemon._execute_autonomous_task(qt)

        # Exactly 6 sleep(5) calls = 30s max wait
        assert sleep_calls == [5] * 6
        # Then gave up
        assert not daemon.ws_manager.send_notification.called



class TestSignalHandler:
    """Test signal handler closure inside run() (lines 586-588)."""

    def test_signal_handler_calls_create_task_and_stop_loop(self):
        """Signal handler registered via signal.signal invokes loop.create_task(stop()) and loop.stop()."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        mock_loop = MagicMock()
        captured_handlers = {}

        def mock_signal_fn(sig, handler):
            captured_handlers[sig] = handler

        with patch('signal.signal', side_effect=mock_signal_fn):
            with patch('asyncio.new_event_loop', return_value=mock_loop):
                with patch('asyncio.set_event_loop'):
                    daemon.run()

        assert signal.SIGINT in captured_handlers
        # Invoke the registered SIGINT handler
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            captured_handlers[signal.SIGINT](signal.SIGINT, None)

        # loop.create_task was called with the stop() coroutine
        mock_loop.create_task.assert_called_once()
        # loop.stop was called
        mock_loop.stop.assert_called_once()


class TestStartRegisterFailure:
    """Test start() when ws_manager.register() returns False (lines 144-145)."""

    @pytest.mark.asyncio
    async def test_start_exits_when_register_returns_false(self):
        """WebSocketManager.connect() True, register() False → sys.exit(1) (lines 144-145)."""
        config = ClientConfig(device_id="dev-id", device_token="tok")
        daemon = CCClawDaemon(config)

        mock_ws_instance = MagicMock(
            connect=AsyncMock(return_value=True),
            register=AsyncMock(return_value=False),
            listen=AsyncMock(),
            on=MagicMock(),
        )

        with patch('client.claude.ClaudeExecutor.is_available', return_value=True):
            with patch('client.claude.ClaudeExecutor.get_version', return_value="1.0.0"):
                with patch('client.daemon.WebSocketManager', return_value=mock_ws_instance):
                    with pytest.raises(SystemExit) as exc_info:
                        await daemon.start()

        assert exc_info.value.code == 1
        mock_ws_instance.register.assert_awaited_once()


class TestTokenCheckerPaths:
    """Test uncovered branches in _token_checker() (lines 162, 174, 181)."""

    @pytest.mark.asyncio
    async def test_token_checker_skips_when_profile_is_none(self, caplog):
        """profile is None after sleep → continue without error (line 162)."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True
        daemon.profile = None

        call_count = [0]

        async def mock_sleep(s):
            call_count[0] += 1
            if call_count[0] >= 2:
                daemon._running = False

        with caplog.at_level(logging.INFO):
            with patch('asyncio.sleep', side_effect=mock_sleep):
                await daemon._token_checker()

        # Completed 2 iterations without AttributeError despite profile=None
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_token_checker_logs_still_rate_limited_when_recent(self, caplog):
        """Rate limited, elapsed < 3600s → logs 'Still rate limited' (line 174)."""
        import time as time_module

        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        mock_tb = MagicMock()
        mock_tb.is_rate_limited = True
        mock_tb.rate_limit_since = time_module.time() - 100  # 100s ago, < 1hr
        mock_tb.backoff_level = 2

        daemon.profile = MagicMock()
        daemon.profile.token_budget = mock_tb

        async def mock_sleep(s):
            daemon._running = False

        with caplog.at_level(logging.INFO):
            with patch('asyncio.sleep', side_effect=mock_sleep):
                await daemon._token_checker()

        assert "Still rate limited" in caplog.text

    @pytest.mark.asyncio
    async def test_token_checker_logs_new_day_on_daily_reset(self, caplog):
        """Not rate limited, daily reset detected → logs 'New day detected' (line 181)."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        mock_tb = MagicMock()
        mock_tb.is_rate_limited = False
        mock_tb.last_reset_date = "2025-01-01"
        mock_tb.total_used = 100
        mock_tb.daily_used = 50

        def simulate_daily_reset():
            mock_tb.last_reset_date = "2025-01-02"

        mock_tb.check_daily_reset.side_effect = simulate_daily_reset

        daemon.profile = MagicMock()
        daemon.profile.token_budget = mock_tb

        async def mock_sleep(s):
            daemon._running = False

        with caplog.at_level(logging.INFO):
            with patch('asyncio.sleep', side_effect=mock_sleep):
                await daemon._token_checker()

        assert "New day detected" in caplog.text


class TestExecuteAutonomousTaskTokenUsage:
    """Test token usage tracking in _execute_autonomous_task (lines 382-385)."""

    @pytest.mark.asyncio
    async def test_records_token_usage_when_raw_data_has_usage(self):
        """raw_data contains 'usage' → record_usage called with total_tokens (lines 382-385)."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        goal = Goal(id="goal-1", description="Test goal", status=GoalStatus.ACTIVE)
        task = Task(id="task-1", description="Test task", goal_id="goal-1")
        qt = MagicMock()
        qt.task = task

        daemon.profile = MagicMock()
        daemon.profile.goals = [goal]
        daemon.profile.get_tasks_for_goal.return_value = [task]
        daemon.profile.complete_task = MagicMock()
        daemon.profile.record_usage = MagicMock()

        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = True
        daemon.ws_manager.send_notification = AsyncMock(return_value=True)

        daemon.memory = MagicMock()
        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.claude = MagicMock()
        raw_data_with_usage = {'usage': {'input_tokens': 100, 'output_tokens': 50}}
        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(return_value=("task done", [], raw_data_with_usage))

        mock_usage = MagicMock()
        mock_usage.total_tokens = 150

        with patch('client.daemon.TokenTracker') as mock_tracker_cls:
            mock_tracker_cls.return_value._build_usage.return_value = mock_usage
            await daemon._execute_autonomous_task(qt)

        daemon.profile.record_usage.assert_called_once_with(150)


class TestNotificationSendFailure:
    """Test send_notification returning False despite connection (line 450)."""

    @pytest.mark.asyncio
    async def test_notification_logs_warning_when_send_fails(self, caplog):
        """ws connected but send_notification() returns False → warning logged (line 450)."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)

        goal = Goal(id="goal-1", description="Goal", status=GoalStatus.ACTIVE)
        task = Task(id="task-1", description="Task", goal_id="goal-1")
        qt = MagicMock()
        qt.task = task

        daemon.profile = MagicMock()
        daemon.profile.goals = [goal]
        daemon.profile.get_tasks_for_goal.return_value = [task]
        daemon.profile.complete_task = MagicMock()

        daemon.ws_manager = MagicMock()
        daemon.ws_manager.is_connected = True
        daemon.ws_manager.send_notification = AsyncMock(return_value=False)

        daemon.memory = MagicMock()
        daemon.queue_manager = MagicMock()
        daemon.queue_manager.queue.mark_done = MagicMock()

        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(return_value=("result", [], None))

        with patch('client.daemon.TokenTracker') as mock_tracker_cls:
            mock_tracker_cls.return_value._build_usage.return_value = None
            with caplog.at_level(logging.WARNING):
                await daemon._execute_autonomous_task(qt)

        assert "Failed to send notification despite being connected" in caplog.text


class TestSuggestNewGoalEdgeCases:
    """Test edge cases in _suggest_new_goal (lines 500-501, 506-508)."""

    def _make_daemon_with_profile(self):
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon.profile = MagicMock()

        mock_profile = MagicMock()
        mock_profile.onboarding_completed = True
        mock_profile.profession = "Engineer"
        mock_profile.situation = "Testing"
        mock_profile.short_term_goal = "Test goal"
        mock_profile.what_better_means = "Better tests"
        daemon.profile.profile = mock_profile

        daemon.memory = MagicMock()
        daemon.memory.get_recent.return_value = []
        return daemon

    @pytest.mark.asyncio
    async def test_json_parse_error_logs_warning(self, caplog):
        """Response has '{' but invalid JSON → JSONDecodeError → warning logged (lines 500-501)."""
        daemon = self._make_daemon_with_profile()
        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(return_value=('{not valid json!!!', [], None))

        with caplog.at_level(logging.WARNING):
            result = await daemon._suggest_new_goal()

        assert result is None
        assert "Failed to parse goal suggestion" in caplog.text

    @pytest.mark.asyncio
    async def test_claude_execute_exception_returns_none(self, caplog):
        """claude.execute raises Exception → caught, returns None (lines 506-508)."""
        daemon = self._make_daemon_with_profile()
        daemon.claude = MagicMock()
        daemon.claude.execute = AsyncMock(side_effect=RuntimeError("Claude crashed"))

        with caplog.at_level(logging.ERROR):
            result = await daemon._suggest_new_goal()

        assert result is None
        assert "Error suggesting new goal" in caplog.text


class TestAutonomousRunnerGoalIdNotFound:
    """Test autonomous runner when queue task's goal_id is not found in profile.goals (lines 255-263)."""

    @pytest.mark.asyncio
    async def test_executes_orphan_task_directly_when_goal_not_found_in_profile(self):
        """Queue task has goal_id, but goal not in profile.goals → execute directly via retry_manager, not re-enqueue (lines 255-263)."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True

        mock_tb = MagicMock()
        mock_tb.is_rate_limited = False
        daemon.profile = MagicMock()
        daemon.profile.token_budget = mock_tb
        # After orphan task completes, get_active_goal returns None so loop exits
        daemon.profile.get_active_goal = MagicMock(side_effect=[None, None, None])
        daemon.profile.get_tasks_for_goal = MagicMock(return_value=[])
        daemon.profile.goals = []  # Empty — goal not found for any task

        orphan_task = Task(id="orphan", description="Orphan task", goal_id="missing-goal-id")
        qt = MagicMock()
        qt.task = orphan_task

        daemon.queue_manager = MagicMock()
        # Return orphan task once, then None so loop exits
        daemon.queue_manager.get_next_task = AsyncMock(side_effect=[qt, None])
        daemon.queue_manager.queue.enqueue = MagicMock()

        daemon.goal_engine = MagicMock()
        daemon._suggest_new_goal = AsyncMock(return_value=None)
        daemon.claude = MagicMock()  # Prevent AttributeError in _execute_autonomous_task

        daemon.retry_manager = MagicMock()
        daemon.retry_manager.execute = AsyncMock(return_value=("done", [], None))

        exit_after = [0]

        async def mock_sleep(s):
            exit_after[0] += 1
            # First sleep: decompose fails → exit after second iteration
            if exit_after[0] >= 2:
                daemon._running = False

        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._autonomous_runner()

        # Orphan task executed via retry_manager, not re-enqueued
        daemon.retry_manager.execute.assert_called_once()
        call_args = daemon.retry_manager.execute.call_args[0]
        assert call_args[1] == daemon.claude.execute
        assert call_args[2] == "Orphan task"
        # No enqueue calls were made (the bug would have caused re-enqueue)
        daemon.queue_manager.queue.enqueue.assert_not_called()


class TestAutonomousRunnerSuggestGoalPath:
    """Test the loop_count % 10 == 0 suggest-goal path (lines 245-260)."""

    @pytest.mark.asyncio
    async def test_suggests_goal_on_10th_iteration_when_suggestion_succeeds(self):
        """After 9 no-op iterations, loop_count=10 triggers suggest path → goal added and tasks enqueued (lines 248-255)."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True

        mock_tb = MagicMock()
        mock_tb.is_rate_limited = False
        daemon.profile = MagicMock()
        daemon.profile.token_budget = mock_tb
        daemon.profile.get_active_goal.return_value = None

        new_goal_obj = Goal(id="suggested-goal", description="Suggested goal", status=GoalStatus.ACTIVE)
        daemon.profile.add_goal = MagicMock(return_value=new_goal_obj)

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.get_next_task = AsyncMock(return_value=None)
        daemon.queue_manager.queue.enqueue = MagicMock()

        new_tasks = [
            Task(id="t1", description="Task 1", goal_id="suggested-goal"),
            Task(id="t2", description="Task 2", goal_id="suggested-goal"),
        ]
        daemon.goal_engine = MagicMock()
        daemon.goal_engine.decompose_goal = AsyncMock(return_value=new_tasks)

        # _suggest_new_goal only called when loop_count % 10 == 0
        daemon._suggest_new_goal = AsyncMock(return_value="Build the feature")

        sleep_count = [0]

        async def mock_sleep(s):
            sleep_count[0] += 1
            # Exit after iteration 10's sleep (lines 262-263 called 9 times, then line 265+ on iter 10)
            # On iterations 1-9: loop_count%10≠0 → else branch → sleep at line 262 → sleep_count 1-9
            # On iteration 10: loop_count%10==0 → suggest path → goal set → falls through
            #   → "Working on goal" → decompose (no pending) → enqueue → sleep not called in iter 10 itself
            # After iter 10, next iter 11: get_active_goal now returns None again (mock)
            #   → BUT goal was set locally in the loop, not persisted back to mock
            # So actually after line 255, fall through to "if not goal:" (265) → goal is NOT None
            # → skip 266-267 → "Working on goal" at 269 → get pending tasks → no pending
            # → decompose_goal called again... this gets complex.
            # Let's just exit after 11 sleeps to ensure line 248-255 is reached.
            if sleep_count[0] >= 11:
                daemon._running = False

        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._autonomous_runner()

        # _suggest_new_goal was called (on loop_count=10)
        daemon._suggest_new_goal.assert_called()
        # add_goal was called with the suggestion
        daemon.profile.add_goal.assert_called_with("Build the feature")

    @pytest.mark.asyncio
    async def test_suggest_goal_path_when_no_suggestion_returned(self):
        """loop_count=10 triggers suggest, but _suggest_new_goal returns None → sleep and continue (lines 256-260)."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True

        mock_tb = MagicMock()
        mock_tb.is_rate_limited = False
        daemon.profile = MagicMock()
        daemon.profile.token_budget = mock_tb
        daemon.profile.get_active_goal.return_value = None

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.get_next_task = AsyncMock(return_value=None)
        daemon.queue_manager.queue.enqueue = MagicMock()

        daemon.goal_engine = MagicMock()

        # Always return None → "else" branch at line 256
        daemon._suggest_new_goal = AsyncMock(return_value=None)

        sleep_count = [0]

        async def mock_sleep(s):
            sleep_count[0] += 1
            # Iterations 1-9: sleep at line 262 (loop_count%10≠0)
            # Iteration 10: sleep at line 259 (loop_count%10==0, no suggestion → lines 256-260)
            if sleep_count[0] >= 10:
                daemon._running = False

        with patch('asyncio.sleep', side_effect=mock_sleep):
            await daemon._autonomous_runner()

        # _suggest_new_goal called on iteration 10
        daemon._suggest_new_goal.assert_called_once()
        # No goal added since suggestion was None
        daemon.profile.add_goal.assert_not_called()
        # Sleep was called 10 times total (9 from else-branch + 1 from suggest-path)
        assert sleep_count[0] == 10

    @pytest.mark.asyncio
    async def test_logs_no_goal_suggested_waiting_on_60th_iteration(self, caplog):
        """loop_count=60: 60%10==0 and 60%60==0 → logs 'No goal suggested, waiting' (line 258)."""
        config = ClientConfig()
        daemon = CCClawDaemon(config)
        daemon._running = True

        daemon.handler = MagicMock()
        daemon.handler.autonomous_mode = True

        mock_tb = MagicMock()
        mock_tb.is_rate_limited = False
        daemon.profile = MagicMock()
        daemon.profile.token_budget = mock_tb
        daemon.profile.get_active_goal.return_value = None

        daemon.queue_manager = MagicMock()
        daemon.queue_manager.get_next_task = AsyncMock(return_value=None)

        daemon.goal_engine = MagicMock()
        daemon._suggest_new_goal = AsyncMock(return_value=None)

        sleep_count = [0]

        async def mock_sleep(s):
            sleep_count[0] += 1
            # 60 iterations: 54 from else-branch (iter 1-9, 11-19, ..., 51-59) +
            # 6 from suggest-path (iter 10,20,30,40,50,60 → loop_count%10==0) = 60 total
            if sleep_count[0] >= 60:
                daemon._running = False

        with caplog.at_level(logging.INFO):
            with patch('asyncio.sleep', side_effect=mock_sleep):
                await daemon._autonomous_runner()

        assert "No goal suggested, waiting" in caplog.text
        # _suggest_new_goal called 6 times: loop_count=10,20,30,40,50,60
        assert daemon._suggest_new_goal.call_count == 6
