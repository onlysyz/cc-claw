"""Tests for memory.py - PersistentMemory and ConversationMemory."""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.memory import (
    PersistentMemory, ConversationMemory, MemoryEntry
)


class TestPersistentMemoryInit:
    """Test PersistentMemory initialization."""

    def test_init_creates_memory_dir(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))

        assert mem.memory_dir == temp_dir
        assert temp_dir.exists()
        assert mem.entries_file == temp_dir / "entries.jsonl"
        assert mem.session_file == temp_dir / "current_session.json"

    def test_init_loads_existing_entries(self, temp_dir):
        mem1 = PersistentMemory(memory_dir=str(temp_dir))
        mem1.add("First entry", category="context")

        mem2 = PersistentMemory(memory_dir=str(temp_dir))
        assert len(mem2.entries) >= 1

    def test_session_id_format(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        assert "_" in mem.current_session_id
        assert len(mem.current_session_id) == 15

    def test_init_windows_path(self, temp_dir):
        """On Windows (os.name == 'nt'), APPDATA path is used (lines 48-49)."""
        fake_path = type("FakePath", (), {
            "__truediv__": lambda self, other: temp_dir / other,
            "__repr__": lambda self: str(temp_dir),
        })()
        with patch("client.memory.os.name", "nt"):
            with patch.dict("client.memory.os.environ", {"APPDATA": str(temp_dir)}, clear=False):
                with patch("client.memory.Path", return_value=fake_path):
                    mem = PersistentMemory()
                    assert "cc-claw" in str(mem.memory_dir)

    def test_init_default_path_via_home(self, temp_dir):
        """Default path uses Path.home() / .config / cc-claw / memory (line 51)."""
        fake_home = type("FakeHome", (), {
            "__truediv__": lambda self, other: temp_dir / other,
            "__repr__": lambda self: str(temp_dir),
        })()
        with patch("client.memory.Path.home", return_value=fake_home):
            mem = PersistentMemory()
            assert ".config" in str(mem.memory_dir)
            assert "cc-claw" in str(mem.memory_dir)


class TestPersistentMemoryAdd:
    """Test adding memory entries."""

    def test_add_returns_memory_entry(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        entry = mem.add("Test content", category="context", importance=3)

        assert isinstance(entry, MemoryEntry)
        assert entry.content == "Test content"
        assert entry.category == "context"
        assert entry.importance == 3
        assert entry.id is not None

    def test_add_multiple_entries(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("Entry 1")
        mem.add("Entry 2")
        mem.add("Entry 3")

        assert len(mem.entries) == 3

    def test_add_with_tags(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        entry = mem.add("Tagged entry", tags=["tag1", "tag2"])

        assert "tag1" in entry.tags
        assert "tag2" in entry.tags

    def test_add_saves_to_disk(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("Persisted entry")

        with open(mem.entries_file) as f:
            lines = f.readlines()

        assert len(lines) >= 1
        data = json.loads(lines[-1])
        assert data["content"] == "Persisted entry"


class TestPersistentMemoryConvenienceMethods:
    """Test convenience methods for adding specific entry types."""

    def test_add_context_snapshot(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add_context_snapshot("Build project", "Using pytest", "Success")

        entries = list(mem.entries)
        assert len(entries) == 1
        assert entries[0].category == "context"
        assert entries[0].importance == 4

    def test_add_decision(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add_decision("Use SQLite", "Simpler than PostgreSQL")

        entry = list(mem.entries)[0]
        assert entry.category == "decision"
        assert entry.importance == 5

    def test_add_learned(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add_learned("pytest fixtures are powerful", "Use @pytest.fixture decorator")

        entry = list(mem.entries)[0]
        assert entry.category == "learned"
        assert entry.importance == 4

    def test_add_error_recovery(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add_error_recovery("Connection timeout", "Increased timeout to 30s")

        entry = list(mem.entries)[0]
        assert entry.category == "success"
        assert entry.importance == 5


class TestPersistentMemorySearch:
    """Test search functionality."""

    def test_search_finds_matching_entries(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("Python is awesome")
        mem.add("JavaScript is popular")
        mem.add("Python dictionaries are fast")

        results = mem.search("Python")
        assert len(results) >= 2

    def test_search_case_insensitive(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("Hello World")

        assert len(mem.search("hello")) == 1
        assert len(mem.search("HELLO")) == 1

    def test_search_with_category_filter(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("Context entry", category="context")
        mem.add("Decision entry", category="decision")
        mem.add("Another context", category="context")

        results = mem.search("entry", category="context")
        assert all(e.category == "context" for e in results)

    def test_search_respects_limit(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        for i in range(20):
            mem.add(f"Entry number {i}")

        results = mem.search("Entry", limit=5)
        assert len(results) == 5


class TestPersistentMemoryGetRecent:
    """Test get_recent functionality."""

    def test_get_recent_returns_reversed_order(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("First")
        mem.add("Second")
        mem.add("Third")

        recent = mem.get_recent(limit=3)
        assert recent[0].content == "Third"
        assert recent[1].content == "Second"
        assert recent[2].content == "First"

    def test_get_recent_with_category_filter(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("Context 1", category="context")
        mem.add("Decision 1", category="decision")
        mem.add("Context 2", category="context")

        recent = mem.get_recent(limit=10, category="context")
        assert all(e.category == "context" for e in recent)
        assert len(recent) == 2


class TestPersistentMemoryGetContextForResume:
    """Test get_context_for_resume formatting."""

    def test_empty_memory_returns_basic_header(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        context = mem.get_context_for_resume()

        assert "## Session Memory - Resume Context" in context

    def test_context_includes_recent_tasks(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add_context_snapshot("Task A", "Context A", "Result A")
        mem.add_context_snapshot("Task B", "Context B", "Result B")

        context = mem.get_context_for_resume()
        assert "### Recent Task Snapshots" in context

    def test_context_includes_decisions(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add_decision("Use TDD", "Improves code quality")

        context = mem.get_context_for_resume()
        assert "### Key Decisions" in context


class TestPersistentMemoryTags:
    """Test tag management."""

    def test_get_all_tags(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("Entry 1", tags=["python", "testing"])
        mem.add("Entry 2", tags=["python", "fixtures"])
        mem.add("Entry 3", tags=["debugging"])

        tags = mem.get_all_tags()
        assert "python" in tags
        assert "testing" in tags


class TestPersistentMemoryPrune:
    """Test pruning old entries."""

    def test_prune_removes_old_entries(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("Old entry")

        old_entry = list(mem.entries)[0]
        old_time = datetime.now() - timedelta(days=100)
        old_entry.timestamp = old_time.isoformat()

        mem.prune_old_entries()

        assert len(mem.entries) == 0

    def test_prune_preserves_recent_entries(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("Recent entry")

        mem.prune_old_entries()

        assert len(mem.entries) == 1


class TestPersistentMemoryStats:
    """Test get_stats()."""

    def test_stats_total_entries(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("Entry 1")
        mem.add("Entry 2")

        stats = mem.get_stats()
        assert stats["total_entries"] == 2

    def test_stats_categories(self, temp_dir):
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("C1", category="context")
        mem.add("C2", category="context")
        mem.add("D1", category="decision")

        stats = mem.get_stats()
        assert stats["categories"]["context"] == 2
        assert stats["categories"]["decision"] == 1


class TestConversationMemory:
    """Test ConversationMemory short-term memory."""

    def test_add_user(self):
        mem = ConversationMemory()
        mem.add_user("Hello")

        assert len(mem.history) == 1
        assert mem.history[0]["role"] == "user"

    def test_add_assistant(self):
        mem = ConversationMemory()
        mem.add_assistant("Hi there!")

        assert len(mem.history) == 1
        assert mem.history[0]["role"] == "assistant"

    def test_get_recent(self):
        mem = ConversationMemory()
        for i in range(15):
            mem.add_user(f"Message {i}")

        recent = mem.get_recent(n=5)
        assert len(recent) == 5
        assert recent[0]["content"] == "Message 10"

    def test_get_formatted(self):
        mem = ConversationMemory()
        mem.add_user("Hello")
        mem.add_assistant("Hi!")

        formatted = mem.get_formatted(n=10)
        assert "### Recent Conversation History" in formatted
        assert "**You**: Hello" in formatted

    def test_get_formatted_empty(self):
        mem = ConversationMemory()
        formatted = mem.get_formatted()
        assert formatted == ""

    def test_metadata(self):
        mem = ConversationMemory()
        mem.set_metadata("key", "value")

        assert mem.get_metadata("key") == "value"
        assert mem.get_metadata("nonexistent", "default") == "default"

    def test_clear(self):
        mem = ConversationMemory()
        mem.add_user("Test")
        mem.set_metadata("key", "value")

        mem.clear()

        assert len(mem.history) == 0
        assert len(mem.metadata) == 0

    def test_add_with_metadata(self, temp_dir):
        """ConversationMemory.add() includes metadata dict in history entry."""
        mem = ConversationMemory()
        mem.add("user", "Hello", metadata={"source": "test"})
        assert mem.history[-1]["metadata"] == {"source": "test"}

    def test_add_trims_over_max_history(self, temp_dir):
        """ConversationMemory trims history when it exceeds MAX_HISTORY."""
        mem = ConversationMemory()
        # MAX_HISTORY is 50; add well over that to hit line 301
        for i in range(120):
            mem.add_user(f"Message {i}")
        assert len(mem.history) == mem.MAX_HISTORY
        # After 120 adds with maxlen=50, history starts at entry 70
        assert mem.history[0]["content"] == "Message 70"


class TestPersistentMemoryErrorHandling:
    """Error-handling branches in PersistentMemory I/O methods."""

    def test_load_entries_handles_corrupt_file(self, temp_dir):
        """Corrupt entries file triggers exception handler in _load_entries."""
        mem = PersistentMemory(memory_dir=str(temp_dir))
        # Write a corrupt line to the entries file
        with open(mem.entries_file, "w") as f:
            f.write("not valid json at all\n")
        # Reload should swallow the error and reset entries
        mem2 = PersistentMemory(memory_dir=str(temp_dir))
        assert len(mem2.entries) == 0

    def test_save_entries_handles_io_error(self, temp_dir):
        """IOError during _save_entries is caught."""
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("Entry 1")
        with patch("builtins.open", side_effect=IOError("disk full")):
            mem._save_entries()  # should not raise

    def test_save_session_handles_io_error(self, temp_dir):
        """IOError during _save_session is caught."""
        mem = PersistentMemory(memory_dir=str(temp_dir))
        with patch("builtins.open", side_effect=IOError("permission denied")):
            mem._save_session()  # should not raise


class TestPersistentMemoryGetContextForResumeDetail:
    """Specific sections in get_context_for_resume formatting."""

    def test_context_includes_resolved_issues(self, temp_dir):
        """'Resolved Issues' section appears when entries have Error:/Solution:."""
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add(
            "Error: Connection timeout. Solution: Increased timeout to 30s",
            category="success",
        )
        context = mem.get_context_for_resume()
        assert "### Resolved Issues" in context

    def test_context_includes_important_learnings(self, temp_dir):
        """'Important Learnings' section appears for high-importance learned entries."""
        mem = PersistentMemory(memory_dir=str(temp_dir))
        mem.add("Use fixtures properly", category="learned", importance=5)
        mem.add("Medium importance", category="learned", importance=3)
        context = mem.get_context_for_resume()
        assert "### Important Learnings" in context
        assert "Use fixtures properly" in context


class TestPersistentMemoryInitDefaultPath:
    """Test __init__ default-path branch (line 51: Path.home() path on non-Windows)."""

    def test_init_without_memory_dir_uses_home_path(self, temp_dir):
        """Line 51: when memory_dir not given and not Windows, Path.home() is used."""
        # Create a fake home path that supports / operator
        fake_home = type("FakeHome", (), {
            "__truediv__": lambda self, other: temp_dir / other,
            "__repr__": lambda self: f"FakeHome({temp_dir})",
        })()
        with patch("client.memory.Path.home", lambda cls=None: fake_home):
            mem = PersistentMemory()
            assert ".config" in str(mem.memory_dir)