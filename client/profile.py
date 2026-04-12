"""CC-Claw User Profile and Goals Module"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from enum import Enum


class GoalStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"


class TaskStatus(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class UserProfile:
    """User profile collected during onboarding"""
    profession: str = ""
    situation: str = ""
    short_term_goal: str = ""
    what_better_means: str = ""
    preferences: dict = None  # flexible key-value preferences
    onboarding_completed: bool = False
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.preferences:
            self.preferences = {}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        return cls(**data)


@dataclass
class Goal:
    """A goal the user wants to achieve"""
    id: str
    description: str
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: str = ""
    completed_at: Optional[str] = None
    task_ids: List[str] = None  # IDs of tasks under this goal

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.task_ids:
            self.task_ids = []

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Goal":
        data = dict(data)
        data["status"] = GoalStatus(data.get("status", "active"))
        return cls(**data)


@dataclass
class Task:
    """A concrete task derived from a goal"""
    id: str
    description: str
    goal_id: str
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0  # higher = more important
    created_at: str = ""
    executed_at: Optional[str] = None
    completed_at: Optional[str] = None
    result_summary: str = ""  # brief summary after execution
    error: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        data = dict(data)
        data["status"] = TaskStatus(data.get("status", "pending"))
        return cls(**data)


@dataclass
class TokenBudget:
    """Token consumption tracking"""
    last_usage_check: str = ""  # ISO timestamp
    total_used: int = 0  # tokens used since last reset
    daily_used: int = 0  # tokens used today
    last_reset_date: str = ""  # date string YYYY-MM-DD
    is_rate_limited: bool = False
    rate_limit_until: Optional[str] = None  # ISO timestamp
    backoff_level: int = 0  # exponential backoff: 1min, 2min, 4min, 8min...

    def __post_init__(self):
        if not self.last_usage_check:
            self.last_usage_check = datetime.now().isoformat()
        if not self.last_reset_date:
            self.last_reset_date = datetime.now().strftime("%Y-%m-%d")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TokenBudget":
        return cls(**data)

    def check_daily_reset(self):
        """Reset daily counter if new day"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.last_reset_date != today:
            self.daily_used = 0
            self.last_reset_date = today


class ProfileManager:
    """Manages user profile, goals, tasks, and token budget — file-based storage"""

    def __init__(self):
        self.profile: Optional[UserProfile] = None
        self.goals: List[Goal] = []
        self.tasks: List[Task] = []
        self.token_budget = TokenBudget()
        self.active_goal_id: Optional[str] = None
        self._load()

    def _get_default_path(self) -> Path:
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", ""))
        else:
            base = Path.home() / ".config"
        return base / "cc-claw" / "profile.json"

    def _load(self):
        path = self._get_default_path()
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                    self.profile = UserProfile.from_dict(data.get("profile", {})) if data.get("profile", {}).get("onboarding_completed") else UserProfile()
                    self.goals = [Goal.from_dict(g) for g in data.get("goals", [])]
                    self.tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
                    self.token_budget = TokenBudget.from_dict(data.get("token_budget", {}))
                    self.active_goal_id = data.get("active_goal_id")
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error loading profile: {e}")
                self._init_empty()
        else:
            self._init_empty()

    def _init_empty(self):
        self.profile = UserProfile()
        self.goals = []
        self.tasks = []
        self.token_budget = TokenBudget()
        self.active_goal_id = None

    def _save(self):
        path = self._get_default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        data = {
            "profile": self.profile.to_dict() if self.profile else {},
            "goals": [g.to_dict() for g in self.goals],
            "tasks": [t.to_dict() for t in self.tasks],
            "token_budget": self.token_budget.to_dict(),
            "active_goal_id": self.active_goal_id,
        }
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path.rename(path)

    # --- Profile ---

    def save_profile(self, profession: str, situation: str, short_term_goal: str, what_better_means: str, preferences: dict = None):
        self.profile.profession = profession
        self.profile.situation = situation
        self.profile.short_term_goal = short_term_goal
        self.profile.what_better_means = what_better_means
        self.profile.onboarding_completed = True
        self.profile.updated_at = datetime.now().isoformat()
        if preferences:
            self.profile.preferences.update(preferences)
        self._save()

    def is_onboarding_complete(self) -> bool:
        return self.profile and self.profile.onboarding_completed

    # --- Goals ---

    def add_goal(self, description: str) -> Goal:
        import uuid
        goal = Goal(id=str(uuid.uuid4())[:8], description=description)
        self.goals.append(goal)
        # Auto-set as active goal if none set yet
        if self.active_goal_id is None:
            self.active_goal_id = goal.id
        self._save()
        return goal

    def get_active_goals(self) -> List[Goal]:
        return [g for g in self.goals if g.status == GoalStatus.ACTIVE]

    def get_active_goal(self) -> Optional[Goal]:
        """Get the currently active goal (the one runner is working on)"""
        if not self.active_goal_id:
            # Fall back to first active goal
            active = self.get_active_goals()
            if active:
                self.active_goal_id = active[0].id
                return active[0]
            return None
        for g in self.goals:
            if g.id == self.active_goal_id and g.status == GoalStatus.ACTIVE:
                return g
        # active_goal_id is no longer valid, pick first active
        active = self.get_active_goals()
        if active:
            self.active_goal_id = active[0].id
            return active[0]
        self.active_goal_id = None
        return None

    def set_active_goal(self, goal_id: str) -> bool:
        """Set which goal is the active (working) goal"""
        for g in self.goals:
            if g.id == goal_id and g.status == GoalStatus.ACTIVE:
                self.active_goal_id = goal_id
                self._save()
                return True
        return False

    def complete_goal(self, goal_id: str):
        for g in self.goals:
            if g.id == goal_id:
                g.status = GoalStatus.COMPLETED
                g.completed_at = datetime.now().isoformat()
                self._save()
                return

    def pause_goal(self, goal_id: str):
        for g in self.goals:
            if g.id == goal_id:
                g.status = GoalStatus.PAUSED
                self._save()
                return

    # --- Tasks ---

    def add_task(self, description: str, goal_id: str, priority: int = 0) -> Task:
        import uuid
        task = Task(
            id=str(uuid.uuid4())[:8],
            description=description,
            goal_id=goal_id,
            priority=priority,
        )
        self.tasks.append(task)
        # Link to goal
        for g in self.goals:
            if g.id == goal_id:
                g.task_ids.append(task.id)
                break
        self._save()
        return task

    def get_pending_tasks(self) -> List[Task]:
        """Get all pending tasks sorted by priority (high first), then created_at"""
        pending = [t for t in self.tasks if t.status == TaskStatus.PENDING]
        pending.sort(key=lambda t: (-t.priority, t.created_at))
        return pending

    def pop_top_task(self) -> Optional[Task]:
        """Get and mark as executing the highest priority pending task"""
        pending = self.get_pending_tasks()
        if not pending:
            return None
        task = pending[0]
        task.status = TaskStatus.EXECUTING
        task.executed_at = datetime.now().isoformat()
        self._save()
        return task

    def complete_task(self, task_id: str, result_summary: str = ""):
        for t in self.tasks:
            if t.id == task_id:
                t.status = TaskStatus.COMPLETED
                t.completed_at = datetime.now().isoformat()
                t.result_summary = result_summary
                self._save()
                return

    def fail_task(self, task_id: str, error: str):
        for t in self.tasks:
            if t.id == task_id:
                t.status = TaskStatus.FAILED
                t.error = error
                self._save()
                return

    def cancel_task(self, task_id: str):
        for t in self.tasks:
            if t.id == task_id:
                t.status = TaskStatus.CANCELLED
                self._save()
                return

    def insert_task_front(self, description: str, goal_id: str, priority: int = 999) -> Task:
        """Insert a new task at the front of the queue (user interrupted)"""
        import uuid
        task = Task(
            id=str(uuid.uuid4())[:8],
            description=description,
            goal_id=goal_id,
            priority=priority,
            status=TaskStatus.PENDING,
        )
        # Insert at front of list instead of append
        self.tasks.insert(0, task)
        for g in self.goals:
            if g.id == goal_id:
                g.task_ids.insert(0, task.id)
                break
        self._save()
        return task

    def get_tasks_for_goal(self, goal_id: str) -> List[Task]:
        return [t for t in self.tasks if t.goal_id == goal_id]

    # --- Token Budget ---

    def record_usage(self, tokens_used: int):
        self.token_budget.total_used += tokens_used
        self.token_budget.daily_used += tokens_used
        self.token_budget.last_usage_check = datetime.now().isoformat()
        self.token_budget.check_daily_reset()
        self._save()

    def set_rate_limited(self, until: datetime):
        self.token_budget.is_rate_limited = True
        self.token_budget.rate_limit_until = until.isoformat()
        self._save()

    def clear_rate_limit(self):
        self.token_budget.is_rate_limited = False
        self.token_budget.rate_limit_until = None
        self.token_budget.backoff_level = 0
        self._save()

    def increment_backoff(self) -> int:
        """Increment backoff level and return next wait seconds"""
        self.token_budget.backoff_level += 1
        wait_seconds = 60 * (2 ** (self.token_budget.backoff_level - 1))
        self._save()
        return wait_seconds

    # --- Stats ---

    def get_progress_summary(self) -> dict:
        """Get progress summary for display"""
        active_goals = self.get_active_goals()
        total_tasks = len(self.tasks)
        completed_tasks = len([t for t in self.tasks if t.status == TaskStatus.COMPLETED])
        pending_tasks = len([t for t in self.tasks if t.status == TaskStatus.PENDING])
        executing_tasks = len([t for t in self.tasks if t.status == TaskStatus.EXECUTING])

        return {
            "profile": self.profile.to_dict() if self.profile else None,
            "active_goals": [g.to_dict() for g in active_goals],
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "executing_tasks": executing_tasks,
            "token_budget": self.token_budget.to_dict(),
        }

    def format_progress(self) -> str:
        """Format progress as human-readable string"""
        summary = self.get_progress_summary()
        p = summary["profile"]

        lines = ["📊 **Progress Report**\n"]

        if p and p.get("onboarding_completed"):
            lines.append(f"👤 **{p.get('profession', 'Unknown')}**")
            lines.append(f"🎯 Goal: {p.get('short_term_goal', 'Not set')}\n")
        else:
            lines.append("⚠️ Onboarding not completed\n")

        lines.append(f"✅ Completed: {summary['completed_tasks']} tasks")
        lines.append(f"⏳ Pending: {summary['pending_tasks']} tasks")
        lines.append(f"🔄 Executing: {summary['executing_tasks']} tasks\n")

        tb = summary["token_budget"]
        lines.append(f"📱 Token Budget")
        lines.append(f"   Total used: {tb.get('total_used', 0)}")
        lines.append(f"   Daily used: {tb.get('daily_used', 0)}")
        if tb.get("is_rate_limited"):
            lines.append(f"   ⛔ Rate limited (backoff level {tb.get('backoff_level', 0)})")
        lines.append(f"   Last reset: {tb.get('last_reset_date', 'Never')}")

        return "\n".join(lines)
