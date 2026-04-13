"""CC-Claw Multi-Agent Collaboration Module

Enables multiple cc-claw instances or specialized agents to work together
on complex goals with task delegation, result sharing, and coordination.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Roles for collaborative agents"""
    COORDINATOR = "coordinator"      # Orchestrates overall goal
    SPECIALIST = "specialist"       # Expert in specific domain
    WORKER = "worker"               # Executes assigned tasks
    REVIEWER = "reviewer"           # Reviews and validates outputs


class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class AgentInfo:
    """Information about a collaborating agent"""
    id: str
    name: str
    role: AgentRole
    capabilities: List[str]  # e.g., ['python', 'docker', 'data-analysis']
    status: str = "online"  # online, busy, offline
    current_task_id: Optional[str] = None
    last_heartbeat: str = field(default_factory=datetime.now().isoformat)


@dataclass
class CollaborationTask:
    """A task in a collaborative workflow"""
    id: str
    description: str
    goal_id: str
    assigned_to: Optional[str] = None  # Agent ID
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    created_at: str = field(default_factory=datetime.now().isoformat)
    assigned_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)  # Task IDs that must complete first
    outputs: Dict[str, Any] = field(default_factory=dict)  # Shared artifacts


class MultiAgentCollaboration:
    """Multi-agent collaboration manager

    Features:
    - Create specialized sub-agents for different aspects of a goal
    - Task delegation with dependency management
    - Result aggregation and synthesis
    - Built-in reviewer agent for quality control
    - Shared knowledge base between agents
    """

    def __init__(self, collaboration_dir: Optional[str] = None):
        if collaboration_dir:
            self.collaboration_dir = Path(collaboration_dir)
        else:
            self.collaboration_dir = Path.home() / ".config" / "cc-claw" / "collaboration"

        self.collaboration_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.collaboration_dir / "tasks.json"
        self.agents_file = self.collaboration_dir / "agents.json"
        self.shared_kb_file = self.collaboration_dir / "shared_knowledge.json"

        self.agents: Dict[str, AgentInfo] = {}
        self.tasks: Dict[str, CollaborationTask] = {}
        self.shared_knowledge: Dict[str, Any] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}

        self._load()
        self._register_main_agent()

    def _load(self):
        """Load persisted state"""
        # Load tasks
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file, 'r') as f:
                    data = json.load(f)
                    self.tasks = {k: CollaborationTask(**v) for k, v in data.items()}
            except Exception as e:
                logger.error(f"Error loading tasks: {e}")

        # Load agents
        if self.agents_file.exists():
            try:
                with open(self.agents_file, 'r') as f:
                    data = json.load(f)
                    self.agents = {k: AgentInfo(**v) for k, v in data.items()}
            except Exception as e:
                logger.error(f"Error loading agents: {e}")

        # Load shared knowledge
        if self.shared_kb_file.exists():
            try:
                with open(self.shared_kb_file, 'r') as f:
                    self.shared_knowledge = json.load(f)
            except Exception as e:
                logger.error(f"Error loading shared knowledge: {e}")

    def _save(self):
        """Persist state"""
        try:
            # Save tasks
            with open(self.tasks_file, 'w') as f:
                json.dump({k: v.__dict__ for k, v in self.tasks.items()}, f, indent=2)

            # Save agents
            with open(self.agents_file, 'w') as f:
                json.dump({k: v.__dict__ for k, v in self.agents.items()}, f, indent=2)

            # Save shared knowledge
            with open(self.shared_kb_file, 'w') as f:
                json.dump(self.shared_knowledge, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving collaboration state: {e}")

    def _register_main_agent(self):
        """Register the main cc-claw agent"""
        self.me = AgentInfo(
            id="main",
            name="CC-Claw Main",
            role=AgentRole.COORDINATOR,
            capabilities=["planning", "execution", "coordination"],
            status="online"
        )
        self.agents["main"] = self.me

    def register_agent(self, name: str, role: AgentRole, capabilities: List[str]) -> AgentInfo:
        """Register a new agent in the collaboration"""
        agent = AgentInfo(
            id=str(uuid.uuid4())[:8],
            name=name,
            role=role,
            capabilities=capabilities,
            status="online"
        )
        self.agents[agent.id] = agent
        self._save()
        logger.info(f"Registered agent: {name} ({role.value})")
        return agent

    def unregister_agent(self, agent_id: str):
        """Remove an agent from collaboration"""
        if agent_id in self.agents and agent_id != "main":
            del self.agents[agent_id]
            # Reassign their tasks
            for task in self.tasks.values():
                if task.assigned_to == agent_id:
                    task.status = TaskStatus.PENDING
                    task.assigned_to = None
            self._save()
            logger.info(f"Unregistered agent: {agent_id}")

    def create_task(
        self,
        description: str,
        goal_id: str,
        priority: int = 0,
        depends_on: Optional[List[str]] = None,
        assigned_to: Optional[str] = None
    ) -> CollaborationTask:
        """Create a new collaborative task"""
        task = CollaborationTask(
            id=str(uuid.uuid4())[:8],
            description=description,
            goal_id=goal_id,
            priority=priority,
            depends_on=depends_on or [],
            assigned_to=assigned_to
        )
        self.tasks[task.id] = task

        if assigned_to:
            task.status = TaskStatus.ASSIGNED
            task.assigned_at = datetime.now().isoformat()
            if assigned_to in self.agents:
                self.agents[assigned_to].current_task_id = task.id

        self._save()
        logger.info(f"Created collaborative task: {task.id[:8]} - {description[:50]}...")
        return task

    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Assign a task to an agent"""
        if task_id not in self.tasks or agent_id not in self.agents:
            return False

        task = self.tasks[task_id]
        agent = self.agents[agent_id]

        # Check dependencies
        for dep_id in task.depends_on:
            dep = self.tasks.get(dep_id)
            if dep and dep.status != TaskStatus.COMPLETED:
                logger.warning(f"Task {task_id} depends on incomplete {dep_id}")
                return False

        task.assigned_to = agent_id
        task.status = TaskStatus.ASSIGNED
        task.assigned_at = datetime.now().isoformat()
        agent.current_task_id = task_id

        self._save()
        logger.info(f"Assigned task {task_id[:8]} to agent {agent.name}")
        return True

    def update_task_status(self, task_id: str, status: TaskStatus, result: Optional[str] = None, error: Optional[str] = None):
        """Update task status and result"""
        if task_id not in self.tasks:
            return

        task = self.tasks[task_id]
        old_status = task.status
        task.status = status

        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now().isoformat()
            task.result = result
            # Clear agent's current task
            if task.assigned_to and task.assigned_to in self.agents:
                self.agents[task.assigned_to].current_task_id = None
            # Unblock dependent tasks
            self._unblock_dependents(task_id)

        elif status == TaskStatus.FAILED:
            task.error = error
            task.completed_at = datetime.now().isoformat()

        self._save()
        logger.info(f"Task {task_id[:8]} status: {old_status.value} -> {status.value}")

    def _unblock_dependents(self, completed_task_id: str):
        """Unblock tasks that depend on completed task"""
        for task in self.tasks.values():
            if completed_task_id in task.depends_on:
                # Check if all dependencies are now complete
                all_deps_done = all(
                    self.tasks.get(dep_id, CollaborationTask(id="", description="", goal_id="")).status == TaskStatus.COMPLETED
                    for dep_id in task.depends_on
                )
                if all_deps_done and task.status == TaskStatus.BLOCKED:
                    task.status = TaskStatus.PENDING
                    logger.info(f"Unblocked task: {task.id[:8]}")

    def complete_task(self, task_id: str, result: str, outputs: Optional[Dict] = None):
        """Mark task as completed with result"""
        if task_id in self.tasks:
            self.tasks[task_id].result = result
            if outputs:
                self.tasks[task_id].outputs = outputs
                # Share outputs to knowledge base
                for key, value in outputs.items():
                    self.share_knowledge(key, value, source_task=task_id)
        self.update_task_status(task_id, TaskStatus.COMPLETED, result)

    def fail_task(self, task_id: str, error: str):
        """Mark task as failed"""
        self.update_task_status(task_id, TaskStatus.FAILED, error=error)

    def get_ready_tasks(self, agent_id: Optional[str] = None) -> List[CollaborationTask]:
        """Get tasks that are ready to be worked on"""
        ready = []
        for task in self.tasks.values():
            if task.status not in (TaskStatus.PENDING, TaskStatus.ASSIGNED):
                continue

            # Check dependencies
            deps_ready = all(
                self.tasks.get(dep_id, CollaborationTask(id="", description="", goal_id="")).status == TaskStatus.COMPLETED
                for dep_id in task.depends_on
            )
            if not deps_ready:
                continue

            # Filter by agent capabilities if specified
            if agent_id and agent_id in self.agents:
                agent = self.agents[agent_id]
                # Simple capability matching
                task_keywords = task.description.lower().split()
                if not any(cap.lower() in task_keywords for cap in agent.capabilities):
                    continue

            ready.append(task)

        return sorted(ready, key=lambda t: (-t.priority, t.created_at))

    def get_agent_workload(self) -> Dict[str, Dict]:
        """Get current workload per agent"""
        workload = {}
        for agent_id, agent in self.agents.items():
            agent_tasks = [t for t in self.tasks.values() if t.assigned_to == agent_id and t.status == TaskStatus.IN_PROGRESS]
            pending_tasks = [t for t in self.tasks.values() if t.assigned_to == agent_id and t.status in (TaskStatus.PENDING, TaskStatus.ASSIGNED)]
            workload[agent_id] = {
                "name": agent.name,
                "role": agent.role.value,
                "status": agent.status,
                "current_task": agent.current_task_id,
                "in_progress": len(agent_tasks),
                "pending": len(pending_tasks),
            }
        return workload

    def share_knowledge(self, key: str, value: Any, source_task: Optional[str] = None):
        """Share knowledge artifact to all agents"""
        entry = {
            "key": key,
            "value": value,
            "source_task": source_task,
            "timestamp": datetime.now().isoformat(),
        }
        self.shared_knowledge[key] = entry

        # Also emit event for listening agents
        self._emit("knowledge_shared", entry)
        self._save()

    def get_shared_knowledge(self, key: str) -> Optional[Any]:
        """Get shared knowledge by key"""
        return self.shared_knowledge.get(key, {}).get("value")

    def get_all_shared_knowledge(self) -> Dict[str, Any]:
        """Get all shared knowledge as dict"""
        return {k: v["value"] for k, v in self.shared_knowledge.items()}

    def on(self, event: str, handler: Callable):
        """Register event handler"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def _emit(self, event: str, data: Any):
        """Emit event to handlers"""
        for handler in self._event_handlers.get(event, []):
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Error in event handler for {event}: {e}")

    def decompose_for_collaboration(self, goal_description: str, goal_id: str) -> List[CollaborationTask]:
        """Decompose a goal into tasks for multiple agents

        This creates a workflow where:
        1. Research/Planning task runs first
        2. Parallel specialized tasks for different components
        3. Integration task at the end
        4. Review task for quality check
        """
        tasks = []

        # Phase 1: Research and planning (sequential)
        research = self.create_task(
            description=f"Research and planning for: {goal_description}",
            goal_id=goal_id,
            priority=10,
        )
        tasks.append(research)

        # Phase 2: Parallel specialized work
        parallel_tasks = [
            ("core", f"Implement core functionality for: {goal_description}"),
            ("testing", f"Write tests for: {goal_description}"),
            ("docs", f"Create documentation for: {goal_description}"),
        ]

        parallel_task_ids = []
        for sub_id, desc in parallel_tasks:
            task = self.create_task(
                description=desc,
                goal_id=goal_id,
                priority=5,
                depends_on=[research.id],
            )
            parallel_task_ids.append(task.id)
            tasks.append(task)

        # Phase 3: Integration
        integration = self.create_task(
            description=f"Integrate and verify: {goal_description}",
            goal_id=goal_id,
            priority=8,
            depends_on=parallel_task_ids,
        )
        tasks.append(integration)

        # Phase 4: Review (if we have a reviewer agent)
        review = self.create_task(
            description=f"Review and quality check: {goal_description}",
            goal_id=goal_id,
            priority=3,
            depends_on=[integration.id],
        )
        tasks.append(review)

        return tasks

    def get_workflow_status(self, goal_id: str) -> Dict[str, Any]:
        """Get status of a collaborative workflow"""
        goal_tasks = [t for t in self.tasks.values() if t.goal_id == goal_id]

        if not goal_tasks:
            return {"status": "no_tasks", "goal_id": goal_id}

        total = len(goal_tasks)
        completed = len([t for t in goal_tasks if t.status == TaskStatus.COMPLETED])
        in_progress = len([t for t in goal_tasks if t.status == TaskStatus.IN_PROGRESS])
        pending = len([t for t in goal_tasks if t.status in (TaskStatus.PENDING, TaskStatus.ASSIGNED)])
        failed = len([t for t in goal_tasks if t.status == TaskStatus.FAILED])

        # Build dependency graph
        task_graph = {}
        for t in goal_tasks:
            task_graph[t.id] = {
                "description": t.description[:50],
                "status": t.status.value,
                "assigned_to": self.agents.get(t.assigned_to, AgentInfo(id="", name="unassigned", role=AgentRole.WORKER, capabilities=[])).name if t.assigned_to else None,
                "depends_on": t.depends_on,
            }

        return {
            "goal_id": goal_id,
            "total_tasks": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "failed": failed,
            "progress_percent": round(completed / total * 100, 1) if total > 0 else 0,
            "task_graph": task_graph,
            "ready_to_start": self.get_ready_tasks(),
        }

    def generate_report(self, goal_id: str) -> str:
        """Generate a collaboration report for a goal"""
        status = self.workflow_status = self.get_workflow_status(goal_id)

        lines = [f"## Collaboration Report: Goal {goal_id[:8]}\n"]
        lines.append(f"Progress: {status['progress_percent']}%")
        lines.append(f"Tasks: {status['completed']}/{status['total_tasks']} completed\n")

        # Agent workload
        workload = self.get_agent_workload()
        lines.append("### Agent Workload\n")
        for agent_id, info in workload.items():
            lines.append(f"- **{info['name']}** ({info['role']}): {info['in_progress']} running, {info['pending']} pending")

        # Shared knowledge
        shared = self.get_all_shared_knowledge()
        if shared:
            lines.append(f"\n### Shared Knowledge ({len(shared)} artifacts)\n")
            for key in list(shared.keys())[:5]:
                lines.append(f"- {key}")

        return "\n".join(lines)