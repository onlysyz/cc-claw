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
