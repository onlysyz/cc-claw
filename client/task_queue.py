"""CC-Claw Task Queue Module - Priority queue for autonomous execution"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from .profile import ProfileManager, Task, TaskStatus


logger = logging.getLogger(__name__)


@dataclass
class QueuedTask:
    """A task in the execution queue"""
    task: Task
    inserted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_user_initiated: bool = False  # True = came from user message (priority)


class TaskQueue:
    """Priority task queue for autonomous execution

    - Normal tasks go to the back
    - User-initiated (priority) tasks go to the front
    - Queue is checked by the autonomous runner
    """

    def __init__(self, profile: ProfileManager):
        self.profile = profile
        self._queue: deque = deque()  # Ordered list of QueuedTask
        self._executing: Optional[QueuedTask] = None
        self._lock = asyncio.Lock()

    def enqueue(self, task: Task, user_initiated: bool = False) -> Task:
        """Add a task to the queue
        - user_initiated=True → insert at front
        - user_initiated=False → append at back
        """
        queued = QueuedTask(task=task, is_user_initiated=user_initiated)

        if user_initiated:
            self._queue.appendleft(queued)  # Front
            logger.info(f"[QUEUE] User task inserted at front: {task.description[:50]}...")
        else:
            self._queue.append(queued)  # Back
            logger.info(f"[QUEUE] Task appended to back: {task.description[:50]}...")

        return task

    def dequeue(self) -> Optional[QueuedTask]:
        """Remove and return the front task"""
        if not self._queue:
            return None
        return self._queue.popleft()

    def peek(self) -> Optional[QueuedTask]:
        """View the front task without removing"""
        if not self._queue:
            return None
        return self._queue[0]

    def get_all(self) -> List[QueuedTask]:
        """Get all queued tasks (for display)"""
        return list(self._queue)

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    @property
    def size(self) -> int:
        return len(self._queue)

    def mark_executing(self, queued_task: QueuedTask):
        """Mark a task as currently executing"""
        self._executing = queued_task

    def mark_done(self):
        """Clear currently executing task"""
        self._executing = None

    @property
    def currently_executing(self) -> Optional[QueuedTask]:
        return self._executing

    def format_queue_status(self) -> str:
        """Format queue status for display"""
        lines = ["📋 **Task Queue**\n"]

        if self._executing:
            lines.append(f"🔄 Executing: {self._executing.task.description[:60]}")
            lines.append(f"   (user_initiated={self._executing.is_user_initiated})\n")

        if not self._queue:
            lines.append("  (empty)")
        else:
            lines.append(f"  Pending ({len(self._queue)} tasks):\n")
            for i, qt in enumerate(self._queue, 1):
                marker = "🔴" if qt.is_user_initiated else "⚪"
                lines.append(f"  {i}. {marker} {qt.task.description[:60]}")

        return "\n".join(lines)


class QueueManager:
    """Manages task queue and coordinates with profile + autonomous runner"""

    def __init__(self, profile: ProfileManager):
        self.profile = profile
        self.queue = TaskQueue(profile)
        self._lock = asyncio.Lock()

    def add_user_task(self, description: str, goal_id: str) -> Task:
        """Add a user-initiated task at front of queue"""
        task = self.profile.insert_task_front(description, goal_id, priority=999)
        self.queue.enqueue(task, user_initiated=True)
        return task

    def add_autonomous_task(self, description: str, goal_id: str) -> Task:
        """Add an autonomous (background) task at back of queue"""
        task = self.profile.add_task(description, goal_id)
        self.queue.enqueue(task, user_initiated=False)
        return task

    async def get_next_task(self) -> Optional[QueuedTask]:
        """Get next task to execute (from queue or profile)"""
        # First check our priority queue
        qt = self.queue.dequeue()
        if qt:
            return qt

        # Queue empty — fall back to profile's pending tasks
        task = self.profile.pop_top_task()
        if task:
            return QueuedTask(task=task, is_user_initiated=False)

        return None

    def requeue_front(self, queued_task: QueuedTask):
        """Put a task back at the front of the queue (e.g., after rate limit)"""
        self.queue._queue.appendleft(queued_task)

    def format_status(self) -> str:
        """Format full queue status"""
        return self.queue.format_queue_status()
