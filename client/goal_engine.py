"""CC-Claw Goal Engine - Decomposes goals into executable tasks using Claude Code"""

import json
import logging
from typing import List, Optional

from .claude import ClaudeExecutor
from .profile import ProfileManager, Goal, Task, TaskStatus


logger = logging.getLogger(__name__)


class GoalEngine:
    """Breaks down goals into executable tasks using Claude Code"""

    def __init__(self, config, profile: ProfileManager, claude: ClaudeExecutor):
        self.config = config
        self.profile = profile
        self.claude = claude

    def _build_decomposition_prompt_with_system(self, goal: Goal) -> str:
        """Build the prompt for goal decomposition including system instructions"""
        p = self.profile.profile
        context = ""
        if p and p.onboarding_completed:
            context = f"""User Context:
- Profession: {p.profession}
- Current Situation: {p.situation}
- Short-term Goal: {p.short_term_goal}
- What 'Better' Means: {p.what_better_means}

"""

        return f"""{context}You are a task decomposition assistant. Given a goal, break it down into 5-10 concrete, actionable tasks.

Output format (MUST be valid JSON):
{{"tasks": ["task 1 description", "task 2 description", ...]}}

Rules:
- Each task should be a single, clear action
- Tasks should be ordered: foundation first, then incremental
- Return ONLY the JSON object, no markdown, no explanation

Goal to decompose: {goal.description}

Break this goal down into 5-10 concrete tasks. Consider:
1. What needs to be done first (foundation, setup, research)
2. What are the main components or steps
3. What can be done in parallel vs sequentially
4. What constitutes "done" for this goal

Output the tasks as a JSON object with a "tasks" array."""

    async def decompose_goal(self, goal_id: str) -> List[Task]:
        """Decompose a goal into tasks using Claude Code
        Returns list of created Task objects
        """
        # Find the goal
        goal = None
        for g in self.profile.goals:
            if g.id == goal_id:
                goal = g
                break

        if not goal:
            logger.error(f"Goal {goal_id} not found")
            return []

        logger.info(f"Decomposing goal: {goal.description}")

        prompt = self._build_decomposition_prompt_with_system(goal)

        # Call Claude Code to decompose goal
        response, _, _ = await self.claude.execute(prompt)

        # Parse the JSON response
        task_descriptions = self._parse_tasks(response)

        if not task_descriptions:
            logger.warning(f"No tasks parsed from response: {response[:200] if response else 'empty'}")
            return []

        # Create Task objects
        created_tasks = []
        for i, desc in enumerate(task_descriptions):
            task = self.profile.add_task(
                description=desc,
                goal_id=goal_id,
                priority=len(task_descriptions) - i,  # Higher priority for earlier tasks
            )
            created_tasks.append(task)
            logger.info(f"  Created task: {desc[:50]}...")

        logger.info(f"Decomposed goal {goal_id} into {len(created_tasks)} tasks")
        return created_tasks

    def _parse_tasks(self, response: str) -> List[str]:
        """Parse task list from Claude's JSON response"""
        if not response:
            return []

        # Strip markdown code blocks if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if len(lines) >= 2:
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines[1:])

        try:
            # Try to find JSON object with tasks array
            data = json.loads(cleaned)
            if isinstance(data, dict) and "tasks" in data:
                tasks = data["tasks"]
                if isinstance(tasks, list) and all(isinstance(t, str) for t in tasks):
                    return [t.strip() for t in tasks if t.strip()]
            elif isinstance(data, list):
                # Direct array format
                if all(isinstance(t, str) for t in data):
                    return [t.strip() for t in data if t.strip()]
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse tasks JSON: {e}")

        # Fallback: try to find array in text
        try:
            json_start = response.find('[')
            if json_start != -1:
                json_str = response[json_start:]
                tasks = json.loads(json_str)
                if isinstance(tasks, list) and all(isinstance(t, str) for t in tasks):
                    return [t.strip() for t in tasks if t.strip()]
        except (json.JSONDecodeError, ValueError):
            pass

        return []

    async def auto_decompose_if_empty(self, goal_id: str) -> List[Task]:
        """Check if goal has no tasks, if so decompose it automatically"""
        existing = self.profile.get_tasks_for_goal(goal_id)
        pending = [t for t in existing if t.status == TaskStatus.PENDING]

        if not pending:
            # Goal has no pending tasks — try to decompose
            logger.info(f"Goal {goal_id} has no pending tasks, attempting auto-decomposition")
            return await self.decompose_goal(goal_id)

        return pending

    async def suggest_next_task(self, goal_id: str) -> Optional[str]:
        """Ask Claude what the next logical task should be"""
        goal = None
        for g in self.profile.goals:
            if g.id == goal_id:
                goal = g
                break

        if not goal:
            return None

        tasks = self.profile.get_tasks_for_goal(goal_id)
        completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        pending = [t for t in tasks if t.status == TaskStatus.PENDING]

        completed_summaries = [f"- {t.description}: {t.result_summary}" for t in completed if t.result_summary]

        prompt = f"""Goal: {goal.description}

Completed tasks:
{chr(10).join(completed_summaries) if completed_summaries else "(none yet)"}

Pending tasks:
{chr(10).join(f"- {t.description}" for t in pending[:10])}

Based on what has been completed, suggest the single most important next task from the pending list.
If pending tasks exist, pick the most logical next one.
If all tasks are done, suggest a new task that would further the goal.
Return ONLY the task description as a plain string, no markdown or explanation."""

        response, _, _ = await self.claude.execute(prompt)
        return response.strip() if response.strip() else None
