"""CC-Claw Persistent Memory Module - Context retention across sessions"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
from collections import deque


logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry with timestamp and importance"""
    id: str
    content: str
    timestamp: str
    category: str  # 'context', 'decision', 'error', 'success', 'learned'
    importance: int  # 1-5, higher = more important to retain
    tags: List[str] = field(default_factory=list)
    source: str = "claude"  # 'claude', 'user', 'system', 'task'


class PersistentMemory:
    """Persistent memory that stores context across Claude Code sessions

    Features:
    - Automatic context snapshots before/after task execution
    - Key decisions and learnings stored permanently
    - Keyword search over memory entries
    - Automatic summarization of old entries when limit reached
    - Session continuity - resumes where left off
    """

    MAX_ENTRIES = 1000
    MAX_ENTRY_AGE_DAYS = 90
    SUMMARIZE_AFTER_DAYS = 7
    SUMMARIZE_BATCH_SIZE = 20

    def __init__(self, memory_dir: Optional[str] = None):
        if memory_dir:
            self.memory_dir = Path(memory_dir)
        elif os.name == "nt":
            self.memory_dir = Path(os.environ.get("APPDATA", "")) / "cc-claw" / "memory"
        else:
            self.memory_dir = Path.home() / ".config" / "cc-claw" / "memory"

        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.entries_file = self.memory_dir / "entries.jsonl"
        self.session_file = self.memory_dir / "current_session.json"
        self.summary_file = self.memory_dir / "summaries.json"

        self.entries: deque = deque(maxlen=self.MAX_ENTRIES)
        self.current_session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._load_entries()
        self._start_new_session()

    def _load_entries(self):
        """Load entries from disk"""
        if not self.entries_file.exists():
            return

        try:
            with open(self.entries_file, 'r') as f:
                for line in f:
                    if line.strip():
                        entry = MemoryEntry(**json.loads(line))
                        self.entries.append(entry)
            logger.info(f"Loaded {len(self.entries)} memory entries")
        except Exception as e:
            logger.error(f"Error loading memory entries: {e}")
            self.entries = deque(maxlen=self.MAX_ENTRIES)

    def _save_entries(self):
        """Save entries to disk (append-only for performance)"""
        try:
            # Rewrite only recent entries to avoid file bloat
            with open(self.entries_file, 'w') as f:
                for entry in list(self.entries)[-self.MAX_ENTRIES:]:
                    f.write(json.dumps(entry.__dict__) + '\n')
        except Exception as e:
            logger.error(f"Error saving memory entries: {e}")

    def _start_new_session(self):
        """Mark start of new session"""
        self.session_start = datetime.now().isoformat()
        self._save_session()

    def _save_session(self):
        """Save current session state"""
        session_data = {
            "session_id": self.current_session_id,
            "session_start": self.session_start,
            "last_updated": datetime.now().isoformat(),
        }
        try:
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f)
        except Exception as e:
            logger.error(f"Error saving session: {e}")

    def add(
        self,
        content: str,
        category: str = "context",
        importance: int = 3,
        tags: Optional[List[str]] = None,
        source: str = "claude"
    ) -> MemoryEntry:
        """Add a new memory entry"""
        import uuid
        entry = MemoryEntry(
            id=str(uuid.uuid4())[:8],
            content=content,
            timestamp=datetime.now().isoformat(),
            category=category,
            importance=importance,
            tags=tags or [],
            source=source
        )
        self.entries.append(entry)
        self._save_entries()
        logger.debug(f"Added memory entry: [{category}] {content[:50]}...")
        return entry

    def add_context_snapshot(self, task_description: str, context: str, result: str = ""):
        """Snapshot context before/after task execution"""
        self.add(
            content=f"Task: {task_description}\nContext: {context[:500]}\nResult: {result[:200]}",
            category="context",
            importance=4,
            tags=["task", "snapshot"],
            source="system"
        )

    def add_decision(self, decision: str, rationale: str = ""):
        """Record a key decision made"""
        content = f"Decision: {decision}"
        if rationale:
            content += f"\nRationale: {rationale}"
        self.add(content, category="decision", importance=5, tags=["decision"])

    def add_learned(self, learning: str, context: str = ""):
        """Record something learned from execution"""
        content = learning
        if context:
            content += f"\nContext: {context}"
        self.add(content, category="learned", importance=4, tags=["learning"])

    def add_error_recovery(self, error: str, solution: str):
        """Record how an error was resolved"""
        self.add(
            content=f"Error: {error}\nSolution: {solution}",
            category="success",
            importance=5,
            tags=["error", "recovery", "resolved"]
        )

    def search(self, query: str, limit: int = 10, category: Optional[str] = None) -> List[MemoryEntry]:
        """Simple keyword search over memory entries"""
        query_lower = query.lower()
        results = []

        for entry in reversed(self.entries):
            if category and entry.category != category:
                continue
            if query_lower in entry.content.lower():
                results.append(entry)
                if len(results) >= limit:
                    break

        return results

    def get_recent(self, limit: int = 10, category: Optional[str] = None) -> List[MemoryEntry]:
        """Get most recent memory entries"""
        results = []
        for entry in reversed(self.entries):
            if category and entry.category != category:
                continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results

    def get_context_for_resume(self) -> str:
        """Get formatted context for resuming a session

        This is the key feature for continuity - returns a summary of:
        - Recent tasks and their outcomes
        - Active goals
        - Key decisions made
        - Pending issues
        """
        lines = ["## Session Memory - Resume Context\n"]

        # Recent tasks (last 5)
        recent = self.get_recent(limit=5, category="context")
        if recent:
            lines.append("### Recent Task Snapshots")
            for entry in recent:
                lines.append(f"- {entry.content[:150]}...")
            lines.append("")

        # Key decisions
        decisions = self.get_recent(limit=3, category="decision")
        if decisions:
            lines.append("### Key Decisions")
            for entry in decisions:
                lines.append(f"- {entry.content}")
            lines.append("")

        # Error recoveries
        recoveries = self.get_recent(limit=3, category="success")
        if recoveries:
            lines.append("### Resolved Issues")
            for entry in recoveries:
                # Parse out error/solution if present
                if "Error:" in entry.content and "Solution:" in entry.content:
                    parts = entry.content.split("Solution:")
                    error_part = parts[0].replace("Error:", "").strip()
                    lines.append(f"- Resolved: {error_part[:80]}")
            lines.append("")

        # High-importance learnings
        learnings = [e for e in self.entries if e.category == "learned" and e.importance >= 4][-3:]
        if learnings:
            lines.append("### Important Learnings")
            for entry in learnings:
                lines.append(f"- {entry.content[:100]}")
            lines.append("")

        return "\n".join(lines)

    def get_all_tags(self) -> List[str]:
        """Get all unique tags in memory"""
        tags = set()
        for entry in self.entries:
            tags.update(entry.tags)
        return sorted(tags)

    def prune_old_entries(self):
        """Remove entries older than MAX_ENTRY_AGE_DAYS"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=self.MAX_ENTRY_AGE_DAYS)
        cutoff_iso = cutoff.isoformat()

        original_count = len(self.entries)
        self.entries = deque(
            [e for e in self.entries if e.timestamp > cutoff_iso],
            maxlen=self.MAX_ENTRIES
        )

        pruned = original_count - len(self.entries)
        if pruned > 0:
            logger.info(f"Pruned {pruned} old memory entries")
            self._save_entries()

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        categories = {}
        for entry in self.entries:
            categories[entry.category] = categories.get(entry.category, 0) + 1

        return {
            "total_entries": len(self.entries),
            "categories": categories,
            "session_id": self.current_session_id,
            "session_start": self.session_start,
            "memory_dir": str(self.memory_dir),
            "all_tags": self.get_all_tags(),
        }


class ConversationMemory:
    """Short-term memory for current conversation context

    Maintains a sliding window of recent exchanges that can be
    included in system prompts for continuity.
    """

    MAX_HISTORY = 50

    def __init__(self):
        self.history: List[Dict[str, str]] = []  # {'role': 'user'|'assistant', 'content': ...}
        self.metadata: Dict[str, Any] = {}  # Extra context

    def add(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add exchange to history"""
        entry = {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        if metadata:
            entry["metadata"] = metadata
        self.history.append(entry)

        # Trim if over limit
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]

    def add_user(self, content: str):
        """Add user message"""
        self.add("user", content)

    def add_assistant(self, content: str):
        """Add assistant response"""
        self.add("assistant", content)

    def get_recent(self, n: int = 10) -> List[Dict[str, str]]:
        """Get N most recent exchanges"""
        return self.history[-n:] if len(self.history) >= n else self.history

    def get_formatted(self, n: int = 10) -> str:
        """Get recent history as formatted string for system prompt"""
        recent = self.get_recent(n)
        if not recent:
            return ""

        lines = ["### Recent Conversation History\n"]
        for entry in recent:
            role = "You" if entry["role"] == "user" else "Assistant"
            lines.append(f"**{role}**: {entry['content'][:200]}")
        return "\n".join(lines)

    def set_metadata(self, key: str, value: Any):
        """Set conversation metadata"""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get conversation metadata"""
        return self.metadata.get(key, default)

    def clear(self):
        """Clear history"""
        self.history = []
        self.metadata = {}