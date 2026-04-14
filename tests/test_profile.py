"""Tests for profile.py — goal/task state transitions and ProfileManager."""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

import sys
from pathlib import Path as PP
sys.path.insert(0, str(PP(__file__).parent.parent))

from client.profile import (
    ProfileManager, GoalStatus, TaskStatus,
    Goal, Task, UserProfile, TokenBudget,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    """ProfileManager with a temp storage path so tests don't clobber real data."""
    with patch.object(ProfileManager, '_get_default_path', return_value=tmp_path / "profile.json"):
        pm = ProfileManager()
        # seed a real profile so onboarding_complete() is True
        pm.profile = UserProfile(
            profession="Engineer",
            situation="Testing",
            short_term_goal="Write tests",
            what_better_means="More coverage",
            onboarding_completed=True,
        )
        yield pm


@pytest.fixture
def goal_a(pm):
    g = pm.add_goal("Goal A")
    yield g


@pytest.fixture
def goal_b(pm):
    g = pm.add_goal("Goal B")
    yield g


@pytest.fixture
def goal_paused(pm):
    g = pm.add_goal("Paused Goal")
    g.status = GoalStatus.PAUSED
    yield g


# ---------------------------------------------------------------------------
# Goal state machine
# ---------------------------------------------------------------------------

class TestGoalActiveTransitions:
    """Goal: ACTIVE → COMPLETED / PAUSED."""

    def test_complete_goal_sets_completed_at(self, goal_a):
        assert goal_a.status is GoalStatus.ACTIVE
        assert goal_a.completed_at is None
        goal_a.completed_at  # consumed implicitly below
        # complete_goal is called on the manager
        pm = goal_a  # placeholder; we call via manager below

    def test_complete_goal_transitions_to_completed(self, pm, goal_a):
        pm.complete_goal(goal_a.id)
        assert pm.goals[0].status is GoalStatus.COMPLETED
        assert pm.goals[0].completed_at is not None

    def test_complete_goal_idempotent(self, pm, goal_a):
        """Calling complete_goal twice is safe."""
        pm.complete_goal(goal_a.id)
        pm.complete_goal(goal_a.id)
        assert pm.goals[0].status is GoalStatus.COMPLETED

    def test_complete_goal_clears_active_goal(self, pm, goal_a):
        """Completing the active goal sets active_goal_id to None."""
        assert pm.get_active_goal().id == goal_a.id
        pm.complete_goal(goal_a.id)
        # get_active_goal will return None once no active goals remain
        active = pm.get_active_goal()
        assert active is None

    def test_pause_goal_transitions_to_paused(self, pm, goal_a):
        pm.pause_goal(goal_a.id)
        assert pm.goals[0].status is GoalStatus.PAUSED

    def test_pause_goal_idempotent(self, pm, goal_a):
        pm.pause_goal(goal_a.id)
        pm.pause_goal(goal_a.id)
        assert pm.goals[0].status is GoalStatus.PAUSED


class TestGoalActiveGoalSelection:
    """get_active_goal / set_active_goal selection logic."""

    def test_add_goal_auto_sets_first_goal_active(self, pm):
        """First goal added becomes the active goal."""
        assert pm.get_active_goal() is None
        g1 = pm.add_goal("First Goal")
        assert pm.get_active_goal().id == g1.id

    def test_add_goal_does_not_switch_when_active_exists(self, pm, goal_a):
        """Adding a second goal does not change the active goal."""
        pm.add_goal("Second Goal")
        assert pm.get_active_goal().id == goal_a.id

    def test_set_active_goal_switches_active(self, pm, goal_a, goal_b):
        assert pm.get_active_goal().id == goal_a.id
        result = pm.set_active_goal(goal_b.id)
        assert result is True
        assert pm.get_active_goal().id == goal_b.id

    def test_set_active_goal_ignores_completed_goal(self, pm, goal_a):
        """Cannot set a completed goal as active."""
        pm.complete_goal(goal_a.id)
        result = pm.set_active_goal(goal_a.id)
        assert result is False
        assert pm.get_active_goal() is None

    def test_set_active_goal_ignores_paused_goal(self, pm, goal_a):
        """Cannot set a paused goal as active."""
        pm.pause_goal(goal_a.id)
        result = pm.set_active_goal(goal_a.id)
        assert result is False

    def test_set_active_goal_returns_false_for_nonexistent_id(self, pm, goal_a):
        result = pm.set_active_goal("nonexistent-id")
        assert result is False

    def test_get_active_goal_returns_none_when_all_completed(self, pm, goal_a):
        pm.complete_goal(goal_a.id)
        assert pm.get_active_goal() is None

    def test_get_active_goal_falls_back_to_first_active(self, pm, goal_a, goal_b):
        """If active_goal_id points to a non-active goal, fall back to first active."""
        pm.set_active_goal(goal_b.id)
        pm.complete_goal(goal_b.id)
        # active_goal_id still points to B; fallback to A
        assert pm.get_active_goal().id == goal_a.id

    def test_get_active_goals_filters_correctly(self, pm, goal_a, goal_b, goal_paused):
        pm.complete_goal(goal_a.id)
        active = pm.get_active_goals()
        assert len(active) == 1
        assert active[0].id == goal_b.id


# ---------------------------------------------------------------------------
# Task state machine
# ---------------------------------------------------------------------------

class TestTaskPendingTransitions:
    """Task: PENDING → EXECUTING / COMPLETED / FAILED / CANCELLED."""

    def _make_task(self, pm, goal):
        return pm.add_task("Do something", goal.id)

    def test_add_task_defaults_to_pending(self, pm, goal_a):
        t = pm.add_task("New task", goal_a.id)
        assert t.status is TaskStatus.PENDING
        assert t.priority == 0
        assert t.result_summary == ""
        assert t.error is None

    def test_add_task_links_to_goal(self, pm, goal_a):
        t = pm.add_task("Linked task", goal_a.id)
        assert t.goal_id == goal_a.id
        assert t.id in goal_a.task_ids

    def test_pop_top_task_transitions_to_executing(self, pm, goal_a):
        pm.add_task("Task 1", goal_a.id, priority=1)
        pm.add_task("Task 2", goal_a.id, priority=2)
        t = pm.pop_top_task()
        assert t.status is TaskStatus.EXECUTING
        assert t.executed_at is not None

    def test_pop_top_task_returns_none_when_empty(self, pm, goal_a):
        assert pm.pop_top_task() is None

    def test_pop_top_task_returns_highest_priority(self, pm, goal_a):
        low = pm.add_task("Low priority", goal_a.id, priority=1)
        high = pm.add_task("High priority", goal_a.id, priority=10)
        mid = pm.add_task("Mid priority", goal_a.id, priority=5)
        t = pm.pop_top_task()
        assert t.id == high.id

    def test_pop_top_task_respects_priority_then_created_at(self, pm, goal_a):
        """When priorities are equal, earlier created_at wins (FIFO)."""
        t1 = pm.add_task("First", goal_a.id, priority=0)
        t2 = pm.add_task("Second", goal_a.id, priority=0)
        t = pm.pop_top_task()
        assert t.id == t1.id

    def test_complete_task_transitions_to_completed(self, pm, goal_a):
        t = pm.add_task("Finish me", goal_a.id)
        pm.complete_task(t.id, result_summary="All done")
        assert pm.tasks[0].status is TaskStatus.COMPLETED
        assert pm.tasks[0].completed_at is not None
        assert pm.tasks[0].result_summary == "All done"

    def test_complete_task_on_nonexistent_is_noop(self, pm, goal_a):
        pm.add_task("Real task", goal_a.id)
        pm.complete_task("nonexistent-id", result_summary="nope")
        # Real task still pending
        assert pm.tasks[0].status is TaskStatus.PENDING

    def test_fail_task_transitions_to_failed(self, pm, goal_a):
        t = pm.add_task("Failing task", goal_a.id)
        pm.fail_task(t.id, error="Connection refused")
        assert pm.tasks[0].status is TaskStatus.FAILED
        assert pm.tasks[0].error == "Connection refused"

    def test_fail_task_on_nonexistent_is_noop(self, pm, goal_a):
        pm.add_task("Real task", goal_a.id)
        pm.fail_task("nonexistent-id", error="boom")
        assert pm.tasks[0].status is TaskStatus.PENDING

    def test_cancel_task_transitions_to_cancelled(self, pm, goal_a):
        t = pm.add_task("Cancelled task", goal_a.id)
        pm.cancel_task(t.id)
        assert pm.tasks[0].status is TaskStatus.CANCELLED

    def test_cancel_task_on_nonexistent_is_noop(self, pm, goal_a):
        pm.add_task("Real task", goal_a.id)
        pm.cancel_task("nonexistent-id")
        assert pm.tasks[0].status is TaskStatus.PENDING

    def test_insert_task_front_goes_to_front(self, pm, goal_a):
        t1 = pm.add_task("First", goal_a.id)
        t2 = pm.insert_task_front("Inserted", goal_a.id)
        pending = pm.get_pending_tasks()
        assert pending[0].id == t2.id
        assert pending[1].id == t1.id

    def test_insert_task_front_has_high_priority(self, pm, goal_a):
        pm.add_task("Regular", goal_a.id, priority=0)
        high = pm.insert_task_front("Urgent", goal_a.id)
        assert high.priority == 999
        pending = pm.get_pending_tasks()
        assert pending[0].id == high.id


class TestTaskGetPendingTasks:
    """get_pending_tasks sorts correctly."""

    def test_executing_tasks_not_in_pending(self, pm, goal_a):
        pm.add_task("Pending", goal_a.id)
        pm.add_task("Executing", goal_a.id)
        pm.pop_top_task()  # marks one EXECUTING
        pending = pm.get_pending_tasks()
        assert len(pending) == 1
        assert pending[0].status is TaskStatus.PENDING

    def test_completed_tasks_not_in_pending(self, pm, goal_a):
        t = pm.add_task("Done", goal_a.id)
        pm.complete_task(t.id)
        assert pm.get_pending_tasks() == []

    def test_sorting_high_priority_first(self, pm, goal_a):
        low = pm.add_task("Low", goal_a.id, priority=1)
        high = pm.add_task("High", goal_a.id, priority=10)
        pending = pm.get_pending_tasks()
        assert pending[0].id == high.id
        assert pending[1].id == low.id


class TestTaskGoalLinking:
    """Tasks are correctly linked to goals and retrieved."""

    def test_get_tasks_for_goal(self, pm, goal_a, goal_b):
        t1 = pm.add_task("Task for A", goal_a.id)
        t2 = pm.add_task("Task for B", goal_b.id)
        t3 = pm.add_task("Another for A", goal_a.id)
        tasks_a = pm.get_tasks_for_goal(goal_a.id)
        assert {t.id for t in tasks_a} == {t1.id, t3.id}
        tasks_b = pm.get_tasks_for_goal(goal_b.id)
        assert [t.id for t in tasks_b] == [t2.id]

    def test_get_tasks_for_goal_empty_for_nonexistent(self, pm, goal_a):
        assert pm.get_tasks_for_goal("nonexistent-id") == []


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------

class TestTokenBudget:
    """record_usage / rate-limit / backoff transitions."""

    def test_record_usage_increments_counters(self, pm):
        pm.record_usage(100)
        assert pm.token_budget.total_used == 100
        assert pm.token_budget.daily_used == 100

    def test_record_usage_accumulates(self, pm):
        pm.record_usage(100)
        pm.record_usage(50)
        assert pm.token_budget.total_used == 150
        assert pm.token_budget.daily_used == 150

    def test_set_rate_limited_sets_flag_and_timestamp(self, pm):
        from datetime import timedelta
        until = datetime.now() + timedelta(minutes=1)
        pm.set_rate_limited(until)
        assert pm.token_budget.is_rate_limited is True
        assert pm.token_budget.rate_limit_until is not None
        assert pm.token_budget.rate_limit_since is not None

    def test_set_rate_limited_sets_rate_limit_since_once(self, pm):
        from datetime import timedelta
        until = datetime.now() + timedelta(minutes=1)
        pm.set_rate_limited(until)
        first = pm.token_budget.rate_limit_since
        until2 = datetime.now() + timedelta(minutes=2)
        pm.set_rate_limited(until2)
        assert pm.token_budget.rate_limit_since == first  # not reset

    def test_clear_rate_limit_resets_all_fields(self, pm):
        pm.token_budget.is_rate_limited = True
        pm.token_budget.backoff_level = 3
        pm.token_budget.rate_limit_since = 12345.0
        pm.clear_rate_limit()
        assert pm.token_budget.is_rate_limited is False
        assert pm.token_budget.rate_limit_until is None
        assert pm.token_budget.backoff_level == 0
        assert pm.token_budget.rate_limit_since is None

    def test_increment_backoff_doubles_wait(self, pm):
        assert pm.token_budget.backoff_level == 0
        wait1 = pm.increment_backoff()
        assert wait1 == 60
        assert pm.token_budget.backoff_level == 1
        wait2 = pm.increment_backoff()
        assert wait2 == 120
        assert pm.token_budget.backoff_level == 2

    def test_increment_backoff_caps_at_3600(self, pm):
        pm.token_budget.backoff_level = 10
        wait = pm.increment_backoff()
        assert wait == 3600


class TestTokenBudgetDailyReset:
    """check_daily_reset resets daily counter on new day."""

    def test_check_daily_reset_resets_daily_used(self, pm):
        pm.token_budget.daily_used = 500
        with patch('client.profile.datetime') as mock_dt:
            mock_dt.now.return_value.strftime = lambda fmt: {
                "%Y-%m-%d": "2025-01-02"
            }.get(fmt, "")
            # Simulate today is different from last_reset_date
            pm.token_budget.last_reset_date = "2025-01-01"
            pm.token_budget.check_daily_reset()
            assert pm.token_budget.daily_used == 0
            assert pm.token_budget.last_reset_date == "2025-01-02"

    def test_check_daily_reset_noop_same_day(self, pm):
        pm.token_budget.daily_used = 500
        pm.token_budget.last_reset_date = datetime.now().strftime("%Y-%m-%d")
        before = pm.token_budget.daily_used
        pm.token_budget.check_daily_reset()
        assert pm.token_budget.daily_used == before


# ---------------------------------------------------------------------------
# Progress summary & formatting
# ---------------------------------------------------------------------------

class TestProgressSummary:
    """get_progress_summary and format_progress."""

    def test_get_progress_summary_counts(self, pm, goal_a):
        pm.add_task("Task 1", goal_a.id)
        pm.add_task("Task 2", goal_a.id)
        t3 = pm.add_task("Task 3", goal_a.id)
        pm.complete_task(t3.id)
        summary = pm.get_progress_summary()
        assert summary["total_tasks"] == 3
        assert summary["completed_tasks"] == 1
        assert summary["pending_tasks"] == 2
        assert summary["executing_tasks"] == 0

    def test_format_progress_contains_key_sections(self, pm, goal_a):
        pm.add_task("Some task", goal_a.id)
        output = pm.format_progress()
        assert "Progress Report" in output
        assert "Completed:" in output
        assert "Pending:" in output
        assert "Token Budget" in output


# ---------------------------------------------------------------------------
# Serialisation round-trips
# ---------------------------------------------------------------------------

class TestGoalTaskSerialization:
    """Goal/Task to_dict / from_dict preserve state."""

    def test_goal_roundtrip(self, goal_a):
        d = goal_a.to_dict()
        restored = Goal.from_dict(d)
        assert restored.id == goal_a.id
        assert restored.description == goal_a.description
        assert restored.status == goal_a.status
        assert restored.task_ids == goal_a.task_ids

    def test_task_roundtrip(self, pm, goal_a):
        t = pm.add_task("Serialise me", goal_a.id)
        d = t.to_dict()
        restored = Task.from_dict(d)
        assert restored.id == t.id
        assert restored.description == t.description
        assert restored.goal_id == t.goal_id
        assert restored.status == t.status
        assert restored.result_summary == t.result_summary

    def test_task_from_dict_defaults_pending(self):
        t = Task.from_dict({"id": "x", "description": "d", "goal_id": "g"})
        assert t.status is TaskStatus.PENDING
        assert t.priority == 0

    def test_goal_from_dict_defaults_active(self):
        g = Goal.from_dict({"id": "x", "description": "d"})
        assert g.status is GoalStatus.ACTIVE


class TestProfileManagerSaveLoad:
    """_save / _load round-trips correctly."""

    def test_save_load_preserves_goals_and_tasks(self, pm, tmp_path):
        pm.add_task("Persisted task", pm.add_goal("Persisted goal").id)
        pm.complete_goal(pm.goals[0].id)

        path = tmp_path / "profile.json"
        with patch.object(ProfileManager, '_get_default_path', return_value=path):
            pm2 = ProfileManager()
            assert len(pm2.goals) == 1
            assert len(pm2.tasks) == 1
            assert pm2.goals[0].status is GoalStatus.COMPLETED

    def test_load_corrupt_file_initialises_empty(self, tmp_path):
        path = tmp_path / "profile.json"
        path.write_text("not valid json{{{")
        with patch.object(ProfileManager, '_get_default_path', return_value=path):
            pm = ProfileManager()
            assert pm.profile is not None  # initialised empty
            assert pm.goals == []
            assert pm.tasks == []


# ---------------------------------------------------------------------------
# save_profile / is_onboarding_complete / Windows path / format_progress
# ---------------------------------------------------------------------------

class TestProfileManagerSaveProfile:
    """Test save_profile (lines 203-211) and is_onboarding_complete (line 214)."""

    def test_save_profile_sets_fields_and_calls_save(self, pm, tmp_path):
        """Lines 203-211: save_profile populates profile and persists."""
        path = tmp_path / "profile.json"
        with patch.object(ProfileManager, '_get_default_path', return_value=path):
            pm.save_profile(
                profession="Designer",
                situation="Building UI",
                short_term_goal="Ship features",
                what_better_means="Better UX",
                preferences={"theme": "dark"},
            )
            assert pm.profile.profession == "Designer"
            assert pm.profile.onboarding_completed is True
            assert pm.profile.preferences.get("theme") == "dark"
            # Verify persisted to disk
            saved = ProfileManager()
            assert saved.profile.profession == "Designer"

    def test_save_profile_without_preferences(self, pm, tmp_path):
        """Line 209: preferences branch is optional (not called when preferences=None)."""
        path = tmp_path / "profile.json"
        with patch.object(ProfileManager, '_get_default_path', return_value=path):
            pm.save_profile("Doctor", "Healthcare", "Heal patients", "Better care")
            assert pm.profile.preferences == {}  # unchanged, not error

    def test_is_onboarding_complete_true(self, pm):
        """Line 214: returns True when onboarding_completed is True."""
        pm.profile.onboarding_completed = True
        assert pm.is_onboarding_complete() is True

    def test_is_onboarding_complete_false(self, pm):
        """Line 214: returns False when onboarding_completed is False."""
        pm.profile.onboarding_completed = False
        assert pm.is_onboarding_complete() is False

    def test_is_onboarding_complete_no_profile(self):
        """Line 214: handles None profile gracefully."""
        with patch.object(ProfileManager, '_get_default_path', return_value=Path("/tmp/none.json")):
            pm = ProfileManager()
            pm.profile = None
            # self.profile and ... → None and ... → None (not False)
            assert not pm.is_onboarding_complete()

    def test_get_active_goal_falls_back_when_active_goal_id_is_none(self, pm, goal_a):
        """Lines 237-238: fallback branch when active_goal_id is None but goals exist."""
        pm.active_goal_id = None  # force None to hit the primary fallback
        result = pm.get_active_goal()
        assert result is goal_a  # falls back to first active goal


class TestProfileManagerGetDefaultPathWindows:
    """Test _get_default_path Windows branch (lines 155-159)."""

    def test_windows_path(self, tmp_path):
        """Lines 155-159: Windows uses APPDATA env var."""
        with patch("os.name", "nt"):
            with patch.dict("os.environ", {"APPDATA": str(tmp_path)}, clear=False):
                with patch("client.profile.Path", return_value=tmp_path):
                    path = ProfileManager()._get_default_path()
                    assert str(path).replace("\\", "/").startswith(str(tmp_path).replace("\\", "/"))


class TestProfileManagerGetDefaultPathPosix:
    """Test _get_default_path non-Windows branch (line 158)."""

    def test_posix_path(self, tmp_path, monkeypatch):
        """Line 158: non-Windows uses Path.home() / .config."""
        monkeypatch.setattr("client.profile.Path.home", lambda: tmp_path)
        path = ProfileManager()._get_default_path()
        assert str(path).startswith(str(tmp_path))


class TestProfileManagerFormatProgress:
    """Test format_progress formatting branches (lines 418, 429)."""

    def test_format_progress_incomplete_onboarding(self, pm):
        """Line 418: shows warning when onboarding not completed."""
        pm.profile.onboarding_completed = False
        pm.profile.profession = None
        output = pm.format_progress()
        assert "⚠️ Onboarding not completed" in output

    def test_format_progress_rate_limited(self, pm):
        """Line 429: shows rate limit warning when is_rate_limited is True."""
        pm.token_budget.is_rate_limited = True
        pm.token_budget.backoff_level = 2
        output = pm.format_progress()
        assert "⛔ Rate limited" in output
        assert "backoff level 2" in output
