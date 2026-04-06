"""CC-Claw Task Scheduler Module"""

import json
import os
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List


@dataclass
class ScheduledTask:
    """A scheduled task"""
    id: str
    command: str
    delay_minutes: int
    created_at: str
    execute_at: str
    status: str  # pending, executing, completed, cancelled
    original_message_id: Optional[str] = None
    lark_open_id: Optional[str] = None  # Lark open_id for routing response

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduledTask":
        return cls(**data)


class TaskScheduler:
    """Manages scheduled tasks with file-based storage"""

    def __init__(self):
        self.tasks: List[ScheduledTask] = []
        self._load()

    def _get_default_path(self) -> Path:
        """Get default tasks file path"""
        if os.name == "nt":  # Windows
            base = Path(os.environ.get("APPDATA", ""))
        else:  # macOS/Linux
            base = Path.home() / ".config"
        return base / "cc-claw" / "tasks.json"

    def _load(self):
        """Load tasks from file"""
        path = self._get_default_path()
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                    self.tasks = [ScheduledTask.from_dict(t) for t in data.get("tasks", [])]
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error loading tasks: {e}")
                self.tasks = []

    def _save(self):
        """Save tasks to file"""
        path = self._get_default_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file then rename
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump({"tasks": [asdict(t) for t in self.tasks]}, f, indent=2)
        temp_path.rename(path)

    def add_task(self, command: str, delay_minutes: int, original_message_id: Optional[str] = None, lark_open_id: Optional[str] = None) -> str:
        """Add a new scheduled task"""
        task_id = str(uuid.uuid4())[:8]
        now = datetime.now()
        execute_at = now + timedelta(minutes=delay_minutes)

        task = ScheduledTask(
            id=task_id,
            command=command,
            delay_minutes=delay_minutes,
            created_at=now.isoformat(),
            execute_at=execute_at.isoformat(),
            status="pending",
            original_message_id=original_message_id,
            lark_open_id=lark_open_id,
        )

        self.tasks.append(task)
        self._save()
        return task_id

    def get_tasks(self) -> List[ScheduledTask]:
        """Get all tasks"""
        return self.tasks

    def get_pending_tasks(self) -> List[ScheduledTask]:
        """Get all pending tasks"""
        return [t for t in self.tasks if t.status == "pending"]

    def get_due_tasks(self) -> List[ScheduledTask]:
        """Get tasks that are due for execution"""
        now = datetime.now()
        due = []
        for task in self.tasks:
            if task.status == "pending":
                execute_at = datetime.fromisoformat(task.execute_at)
                if now >= execute_at:
                    due.append(task)
        return due

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task"""
        for task in self.tasks:
            if task.id == task_id and task.status == "pending":
                task.status = "cancelled"
                self._save()
                return True
        return False

    def mark_executing(self, task_id: str):
        """Mark a task as executing"""
        for task in self.tasks:
            if task.id == task_id:
                task.status = "executing"
                self._save()
                return

    def mark_completed(self, task_id: str):
        """Mark a task as completed"""
        for task in self.tasks:
            if task.id == task_id:
                task.status = "completed"
                self._save()
                return

    def remove_completed_tasks(self, older_than_hours: int = 24):
        """Remove completed tasks older than specified hours"""
        cutoff = datetime.now() - timedelta(hours=older_than_hours)
        self.tasks = [
            t for t in self.tasks
            if not (t.status == "completed" and
                    datetime.fromisoformat(t.created_at) < cutoff)
        ]
        self._save()

    def format_tasks_list(self) -> str:
        """Format tasks list for display"""
        pending = [t for t in self.tasks if t.status in ("pending", "executing")]

        if not pending:
            return "📋 没有待执行的任务"

        lines = ["📋 待执行任务:\n"]
        for i, task in enumerate(pending, 1):
            execute_at = datetime.fromisoformat(task.execute_at)
            now = datetime.now()
            remaining = execute_at - now

            if remaining.total_seconds() > 0:
                mins = int(remaining.total_seconds() / 60)
                secs = int(remaining.total_seconds() % 60)
                time_str = f"{mins}分{secs}秒后"
            else:
                time_str = "即将执行"

            status_emoji = "⏳" if task.status == "pending" else "🔄"
            lines.append(f"{i}. {status_emoji} [{task.id[:8]}] {time_str}\n")
            lines.append(f"   命令: {task.command}\n")

        return "".join(lines)
