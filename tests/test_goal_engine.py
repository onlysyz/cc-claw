"""Tests for goal_engine.py - GoalEngine decomposition logic."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.goal_engine import GoalEngine
from client.profile import Goal, Task, GoalStatus, TaskStatus


class TestBuildDecompositionPrompt:
    """Test prompt building with/without user context."""

    def test_prompt_includes_user_context_when_onboarding_complete(self):
        profile = MagicMock()
        profile.profile.onboarding_completed = True
        profile.profile.profession = "软件工程师"
        profile.profile.situation = "完善单元测试"
        profile.profile.short_term_goal = "提升代码质量"
        profile.profile.what_better_means = "更少的bug"

        goal = Goal(id="goal-001", description="Test goal", status=GoalStatus.ACTIVE)

        engine = GoalEngine(MagicMock(), profile, MagicMock())
        prompt = engine._build_decomposition_prompt_with_system(goal)

        assert "软件工程师" in prompt
        assert "完善单元测试" in prompt

    def test_prompt_includes_goal_description(self):
        profile = MagicMock()
        profile.profile = None

        goal = Goal(id="goal-001", description="My custom goal", status=GoalStatus.ACTIVE)

        engine = GoalEngine(MagicMock(), profile, MagicMock())
        prompt = engine._build_decomposition_prompt_with_system(goal)

        assert "My custom goal" in prompt
        assert "Goal to decompose:" in prompt


class TestParseTasks:
    """Test JSON parsing of task descriptions."""

    def setup_method(self):
        self.engine = GoalEngine(MagicMock(), MagicMock(), MagicMock())

    def test_parse_valid_tasks_array(self):
        response = '{"tasks": ["task 1", "task 2", "task 3"]}'

        tasks = self.engine._parse_tasks(response)

        assert tasks == ["task 1", "task 2", "task 3"]

    def test_parse_empty_tasks_array(self):
        response = '{"tasks": []}'

        tasks = self.engine._parse_tasks(response)

        assert tasks == []

    def test_parse_direct_array_format(self):
        response = '["direct task 1", "direct task 2"]'

        tasks = self.engine._parse_tasks(response)

        assert tasks == ["direct task 1", "direct task 2"]

    def test_parse_array_embedded_in_text(self):
        response = '{"tasks": ["Analyze requirements", "Write code"]}'

        tasks = self.engine._parse_tasks(response)

        assert "Analyze requirements" in tasks
        assert "Write code" in tasks

    def test_parse_strips_whitespace(self):
        response = '{"tasks": ["  task 1  ", "  task 2  "]}'

        tasks = self.engine._parse_tasks(response)

        assert tasks == ["task 1", "task 2"]

    def test_parse_ignores_empty_tasks(self):
        response = '{"tasks": ["task 1", "", "  ", "task 2"]}'

        tasks = self.engine._parse_tasks(response)

        assert tasks == ["task 1", "task 2"]

    def test_parse_invalid_json_returns_empty(self):
        response = "This is not valid JSON at all"

        tasks = self.engine._parse_tasks(response)

        assert tasks == []

    def test_parse_empty_string_returns_empty(self):
        tasks = self.engine._parse_tasks("")
        assert tasks == []

    def test_parse_none_returns_empty(self):
        tasks = self.engine._parse_tasks(None)
        assert tasks == []

    def test_parse_fallback_finds_array_in_text(self):
        """Main json.loads fails but fallback finds [array] in text and succeeds."""
        # Response starts with non-JSON text, but contains ["task 1", "task 2"]
        response = 'Here is the result: ["fallback task 1", "fallback task 2"]'

        tasks = self.engine._parse_tasks(response)

        assert tasks == ["fallback task 1", "fallback task 2"]

    def test_parse_fallback_no_bracket_returns_empty(self):
        """Main fails, no '[' in text → fallback returns empty."""
        response = "Plain text with no JSON or brackets"

        tasks = self.engine._parse_tasks(response)

        assert tasks == []

    def test_parse_fallback_bracket_but_invalid_array_returns_empty(self):
        """Main fails, '[' found but what follows is not a valid array of strings."""
        response = "Text with [123] but not string array"

        tasks = self.engine._parse_tasks(response)

        assert tasks == []


class TestDecomposeGoal:
    """Test goal decomposition into tasks."""

    @pytest.mark.asyncio
    async def test_decompose_goal_success(self):
        profile = MagicMock()
        profile.profile.onboarding_completed = True
        profile.profile.profession = "Engineer"
        profile.profile.situation = "Testing"
        profile.profile.short_term_goal = "Test goal"
        profile.profile.what_better_means = "Better tests"

        goal = Goal(id="goal-001", description="Test goal", status=GoalStatus.ACTIVE)
        profile.goals = [goal]

        mock_claude = AsyncMock()
        mock_claude.execute.return_value = (
            '{"tasks": ["分析现有代码结构", "创建测试目录", "编写测试用例"]}',
            [],
            None
        )

        profile.add_task = MagicMock(side_effect=lambda **kwargs: Task(
            id=f"task-{len(profile.add_task.call_args_list)}",
            description=kwargs.get("description"),
            goal_id=kwargs.get("goal_id")
        ))

        engine = GoalEngine(MagicMock(), profile, mock_claude)

        tasks = await engine.decompose_goal("goal-001")

        assert len(tasks) == 3
        assert mock_claude.execute.called

    @pytest.mark.asyncio
    async def test_decompose_goal_not_found(self):
        profile = MagicMock()
        profile.goals = []

        mock_claude = AsyncMock()
        engine = GoalEngine(MagicMock(), profile, mock_claude)

        tasks = await engine.decompose_goal("nonexistent-goal")

        assert tasks == []
        assert not mock_claude.execute.called

    @pytest.mark.asyncio
    async def test_decompose_goal_handles_parse_failure(self):
        profile = MagicMock()
        goal = Goal(id="goal-001", description="Test goal", status=GoalStatus.ACTIVE)
        profile.goals = [goal]

        mock_claude = AsyncMock()
        mock_claude.execute.return_value = ("Not valid JSON response", [], None)

        engine = GoalEngine(MagicMock(), profile, mock_claude)

        tasks = await engine.decompose_goal("goal-001")

        assert tasks == []


class TestAutoDecomposeIfEmpty:
    """Test auto_decompose_if_empty() branching."""

    @pytest.mark.asyncio
    async def test_returns_pending_when_tasks_exist(self):
        """Has pending tasks → returns pending without calling decompose_goal."""
        profile = MagicMock()
        goal = Goal(id="goal-001", description="Test goal", status=GoalStatus.ACTIVE)
        profile.goals = [goal]

        pending_task = Task(id="task-1", description="pending task", goal_id="goal-001", status=TaskStatus.PENDING)
        profile.get_tasks_for_goal.return_value = [pending_task]

        mock_claude = AsyncMock()
        engine = GoalEngine(MagicMock(), profile, mock_claude)

        result = await engine.auto_decompose_if_empty("goal-001")

        assert result == [pending_task]
        assert not mock_claude.execute.called  # decompose_goal NOT called

    @pytest.mark.asyncio
    async def test_calls_decompose_when_no_pending_tasks(self):
        """No pending tasks → calls decompose_goal and returns its result."""
        profile = MagicMock()
        goal = Goal(id="goal-001", description="Test goal", status=GoalStatus.ACTIVE)
        profile.goals = [goal]
        profile.profile.onboarding_completed = True
        profile.profile.profession = "Engineer"
        profile.profile.situation = "Testing"
        profile.profile.short_term_goal = "Test"
        profile.profile.what_better_means = "Better"

        # No pending tasks
        profile.get_tasks_for_goal.return_value = []

        mock_task = Task(id="new-task", description="decomposed task", goal_id="goal-001")
        profile.add_task = MagicMock(return_value=mock_task)

        mock_claude = AsyncMock()
        mock_claude.execute.return_value = ('{"tasks": ["decomposed task"]}', [], None)

        engine = GoalEngine(MagicMock(), profile, mock_claude)

        result = await engine.auto_decompose_if_empty("goal-001")

        assert result == [mock_task]
        assert mock_claude.execute.called


class TestSuggestNextTask:
    """Test suggest_next_task() branching."""

    @pytest.mark.asyncio
    async def test_returns_task_when_goal_not_found(self):
        """Goal not found → returns None."""
        profile = MagicMock()
        profile.goals = []

        engine = GoalEngine(MagicMock(), profile, AsyncMock())

        result = await engine.suggest_next_task("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_recommendation_when_pending_tasks_exist(self):
        """Has pending tasks → calls claude.execute and returns response."""
        profile = MagicMock()
        goal = Goal(id="goal-001", description="Complete project", status=GoalStatus.ACTIVE)
        profile.goals = [goal]

        pending_task = Task(
            id="task-1", description="Write tests", goal_id="goal-001",
            status=TaskStatus.PENDING, result_summary="done"
        )
        completed_task = Task(
            id="task-0", description="Setup", goal_id="goal-001",
            status=TaskStatus.COMPLETED, result_summary="finished setup"
        )
        profile.get_tasks_for_goal.return_value = [completed_task, pending_task]

        mock_claude = AsyncMock()
        mock_claude.execute.return_value = ("Write more tests", [], None)

        engine = GoalEngine(MagicMock(), profile, mock_claude)

        result = await engine.suggest_next_task("goal-001")

        assert result == "Write more tests"
        mock_claude.execute.assert_called_once()
        call_args = mock_claude.execute.call_args[0][0]
        assert "Write tests" in call_args
        assert "Setup" in call_args

    @pytest.mark.asyncio
    async def test_returns_none_when_no_pending_and_strip_fails(self):
        """No pending tasks, claude returns whitespace → returns None."""
        profile = MagicMock()
        goal = Goal(id="goal-001", description="All done", status=GoalStatus.ACTIVE)
        profile.goals = [goal]

        completed_task = Task(
            id="task-1", description="Finish work", goal_id="goal-001",
            status=TaskStatus.COMPLETED, result_summary="completed"
        )
        profile.get_tasks_for_goal.return_value = [completed_task]

        mock_claude = AsyncMock()
        mock_claude.execute.return_value = ("   ", [], None)  # whitespace only

        engine = GoalEngine(MagicMock(), profile, mock_claude)

        result = await engine.suggest_next_task("goal-001")

        assert result is None

    @pytest.mark.asyncio
    async def test_prompt_includes_completed_and_pending(self):
        """Prompt contains both completed and pending task info."""
        profile = MagicMock()
        goal = Goal(id="goal-001", description="Build feature", status=GoalStatus.ACTIVE)
        profile.goals = [goal]

        pending_tasks = [
            Task(id=f"task-{i}", description=f"Task {i}", goal_id="goal-001", status=TaskStatus.PENDING)
            for i in range(12)
        ]
        completed = Task(id="task-done", description="Init", goal_id="goal-001",
                         status=TaskStatus.COMPLETED, result_summary="initialized")
        profile.get_tasks_for_goal.return_value = completed, *pending_tasks[:10]

        mock_claude = AsyncMock()
        mock_claude.execute.return_value = ("Next task suggestion", [], None)

        engine = GoalEngine(MagicMock(), profile, mock_claude)

        await engine.suggest_next_task("goal-001")

        prompt = mock_claude.execute.call_args[0][0]
        # Only first 10 pending tasks included
        assert prompt.count("Task") == 10
        assert "initialized" in prompt
