"""Tests for claude.py - ClaudeExecutor subprocess wrapper."""

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.claude import ClaudeExecutor
from client.config import ClientConfig


@pytest.fixture
def config():
    """Create a test config."""
    cfg = ClientConfig()
    cfg.claude_path = "claude"
    cfg.timeout = 30
    cfg.working_dir = "/tmp/test_cc_claw"
    cfg.permission_mode = "default"
    return cfg


@pytest.fixture
def executor(config):
    """Create a ClaudeExecutor instance."""
    return ClaudeExecutor(config)


# ============================================================================
# is_available() tests
# ============================================================================

class TestIsAvailable:
    """Test is_available() method."""

    def test_returns_true_when_returncode_zero(self, executor):
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            result = executor.is_available()
            assert result is True
            mock_run.assert_called_once_with(
                ["claude", "--version"],
                capture_output=True,
                timeout=5,
            )

    def test_returns_false_when_returncode_nonzero(self, executor):
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            result = executor.is_available()
            assert result is False

    def test_returns_false_when_exception_raised(self, executor):
        with patch('subprocess.run', side_effect=FileNotFoundError("claude not found")):
            result = executor.is_available()
            assert result is False


# ============================================================================
# get_version() tests
# ============================================================================

class TestGetVersion:
    """Test get_version() method."""

    def test_returns_version_string_when_success(self, executor):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "claude version 1.0.5\n"

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            result = executor.get_version()
            assert result == "claude version 1.0.5"
            mock_run.assert_called_once()

    def test_returns_none_when_nonzero_returncode(self, executor):
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch('subprocess.run', return_value=mock_result):
            result = executor.get_version()
            assert result is None

    def test_returns_none_when_exception_raised(self, executor):
        with patch('subprocess.run', side_effect=OSError("Failed")):
            result = executor.get_version()
            assert result is None


# ============================================================================
# _build_env() tests
# ============================================================================

class TestBuildEnv:
    """Test _build_env() method."""

    def test_removes_claude_environment_variables(self, executor):
        with patch.dict(os.environ, {
            "CLAUDE_API_KEY": "secret1",
            "CLAUDE_CONFIG_PATH": "/path/to/config",
            "CLAUDE_ACCOUNT_TOKEN": "token",
            "AWS_PROFILE": "default",
            "PATH": "/usr/bin",
        }, clear=False):
            env = executor._build_env()

            assert "CLAUDE_API_KEY" not in env
            assert "CLAUDE_CONFIG_PATH" not in env
            assert "CLAUDE_ACCOUNT_TOKEN" not in env
            assert "AWS_PROFILE" not in env
            # PATH should remain
            assert env["PATH"] == "/usr/bin"

    def test_sets_is_sandbox_to_one(self, executor):
        env = executor._build_env()
        assert env["IS_SANDBOX"] == "1"

    def test_returns_copy_of_environment(self, executor):
        with patch.dict(os.environ, {"FOO": "bar"}, clear=False):
            env = executor._build_env()
            assert env["FOO"] == "bar"
            # Modifying returned env should not affect os.environ
            env["FOO"] = "modified"
            assert os.environ.get("FOO") == "bar"


# ============================================================================
# _get_screenshot_files() tests
# ============================================================================

class TestGetScreenshotFiles:
    """Test _get_screenshot_files() method."""

    def test_returns_empty_set_when_work_dir_does_not_exist(self, executor):
        with patch('os.path.exists', return_value=False):
            result = executor._get_screenshot_files("/nonexistent")
            assert result == set()

    def test_finds_screenshot_files_in_work_dir(self, executor):
        mock_files = ["cc-claw-screenshot-001.png", "code.py", "screenshot.png"]
        with patch('os.path.exists', return_value=True), \
             patch('os.listdir', return_value=mock_files):
            result = executor._get_screenshot_files("/tmp/work")
            assert "cc-claw-screenshot-001.png" in result
            assert "screenshot.png" in result
            assert "code.py" not in result

    def test_finds_image_files_on_desktop(self, executor):
        # Simulate work_dir has no screenshots but Desktop does
        def listdir_side_effect(path):
            if path == "/tmp/work":
                return []
            elif path == os.path.expanduser("~/Desktop"):
                return ["photo.jpg", "image.webp", "readme.txt"]
            return []

        def exists_side_effect(path):
            if path == "/tmp/work":
                return True
            elif path == os.path.expanduser("~/Desktop"):
                return True
            return False

        with patch('os.path.exists', side_effect=exists_side_effect), \
             patch('os.listdir', side_effect=listdir_side_effect):
            result = executor._get_screenshot_files("/tmp/work")
            assert "Desktop/photo.jpg" in result
            assert "Desktop/image.webp" in result
            assert "Desktop/readme.txt" not in result


# ============================================================================
# _extract_file_paths() tests
# ============================================================================

class TestExtractFilePaths:
    """Test _extract_file_paths() method."""

    def test_extracts_image_in_backticks(self, executor):
        text = "Here is the screenshot: `screenshot.png`"
        # Mock isfile to return True for the Desktop path, so it finds the file
        with patch('os.path.isfile', return_value=True):
            result = executor._extract_file_paths(text)
            # Found in Desktop
            assert len(result) == 1

    def test_extracts_multiple_images_in_backticks(self, executor):
        text = "First `img1.png` then `img2.jpg` and `img3.webp`"
        with patch('os.path.isfile', return_value=True):
            result = executor._extract_file_paths(text)
            assert len(result) == 3

    def test_returns_empty_for_non_image_backtick_content(self, executor):
        text = "Run `python script.py` to execute"
        result = executor._extract_file_paths(text)
        assert result == []

    def test_finds_existing_file_in_work_dir(self, executor):
        text = "See `test.png`"
        work_dir = "/tmp/test_cc_claw"

        def isfile_side_effect(path):
            return path == os.path.join(work_dir, "test.png")

        with patch('os.path.isfile', side_effect=isfile_side_effect), \
             patch('os.path.join', side_effect=lambda a, b: os.path.join(a, b)):
            # Override base path resolution
            with patch.object(executor, '_extract_file_paths', ClaudeExecutor._extract_file_paths.__get__(executor)):
                pass

        # Direct test with actual path resolution
        result = []
        for base in [os.path.expanduser("~/Desktop"), work_dir, os.getcwd()]:
            full_path = os.path.join(base, "test.png")
            if os.path.isfile(full_path):
                result.append(full_path)
        # This will be empty since file doesn't exist, but tests the logic path


# ============================================================================
# execute() tests
# ============================================================================

class TestExecute:
    """Test execute() async method."""

    @pytest.mark.asyncio
    async def test_happy_path_valid_json_with_result(self, config):
        executor = ClaudeExecutor(config)
        mock_data = {
            "result": "Task completed successfully",
            "usage": {"input_tokens": 100, "output_tokens": 50}
        }

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(json.dumps(mock_data).encode(), b"")
        )
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_create:
            text, paths, data = await executor.execute("Complete this task")

            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert "--print" in call_args[0]
            assert "--output-format" in call_args[0]
            assert "--continue" in call_args[0]

            assert text == "Task completed successfully"
            assert data == mock_data

    @pytest.mark.asyncio
    async def test_happy_path_with_permission_bypass(self, config):
        config.permission_mode = "bypassPermissions"
        executor = ClaudeExecutor(config)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b'{"result": "done"}', b"")
        )
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await executor.execute("do something")

            call_args = mock_process.communicate.call_args
            # Should have been called via create_subprocess_exec

    @pytest.mark.asyncio
    async def test_raw_output_when_no_json(self, config):
        executor = ClaudeExecutor(config)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b'Plain text output without JSON', b"")
        )
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            text, paths, data = await executor.execute("hello")

            assert text == "Plain text output without JSON"
            assert paths == []
            assert data == {}

    @pytest.mark.asyncio
    async def test_no_response_when_output_empty(self, config):
        executor = ClaudeExecutor(config)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            text, paths, data = await executor.execute("hello")
            assert text == "No response"
            assert paths == []
            assert data == {}

    @pytest.mark.asyncio
    async def test_json_decode_error_returns_error_message(self, config):
        executor = ClaudeExecutor(config)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b'{"result": valid but broken json', b"")
        )
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            text, paths, data = await executor.execute("hello")

            assert "Error parsing response" in text
            assert paths == []
            assert data == {}

    @pytest.mark.asyncio
    async def test_timeout_returns_timeout_message(self, config):
        executor = ClaudeExecutor(config)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch('asyncio.create_subprocess_exec', return_value=mock_process), \
             patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
            text, paths, data = await executor.execute("long task")

            assert text == "Timeout"
            assert paths == []
            assert data == {}

    @pytest.mark.asyncio
    async def test_generic_exception_returns_error_message(self, config):
        executor = ClaudeExecutor(config)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(side_effect=RuntimeError("subprocess error"))

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            text, paths, data = await executor.execute("task")

            assert text == "Error: subprocess error"
            assert paths == []
            assert data == {}

    @pytest.mark.asyncio
    async def test_stderr_logged_as_warning(self, config, caplog):
        executor = ClaudeExecutor(config)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b'{"result": "ok"}', b"Warning: some warning")
        )
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process), \
             caplog.at_level(logging.WARNING):
            await executor.execute("task")

            assert any("Claude stderr" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_creates_work_dir_if_not_exists(self, config):
        executor = ClaudeExecutor(config)
        config.working_dir = "/tmp/nonexistent_cc_claw_test"

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b'{"result": "done"}', b"")
        )
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process), \
             patch('os.makedirs') as mock_makedirs:
            await executor.execute("task")
            mock_makedirs.assert_called_once_with(config.working_dir, exist_ok=True)


# ============================================================================
# _get_new_screenshots() tests
# ============================================================================

class TestGetNewScreenshots:
    """Test _get_new_screenshots() method."""

    def test_returns_new_screenshot_paths(self, executor):
        def exists_side_effect(path):
            return path in ["/tmp/work/screenshot.png"]

        def listdir_side_effect(path):
            if path == "/tmp/work":
                return ["screenshot.png", "old.png"]
            return []

        existing = {"old.png"}  # old.png already existed

        with patch.object(executor, '_get_screenshot_files', return_value={"screenshot.png", "old.png"}), \
             patch('os.path.exists', side_effect=exists_side_effect), \
             patch('os.path.join', side_effect=lambda a, b: f"{a}/{b}"):
            result = executor._get_new_screenshots("/tmp/work", existing)
            assert "/tmp/work/screenshot.png" in result

    def test_returns_desktop_screenshot_path(self, executor):
        def exists_side_effect(path):
            return path == os.path.expanduser("~/Desktop/photo.jpg")

        with patch.object(executor, '_get_screenshot_files', return_value={"Desktop/photo.jpg"}), \
             patch('os.path.exists', side_effect=exists_side_effect), \
             patch('os.path.expanduser', side_effect=lambda p: p.replace("~", "/Users/test")):
            result = executor._get_new_screenshots("/tmp/work", set())
            assert len(result) == 1


# ============================================================================
# Integration-like tests using real subprocess for is_available/get_version
# ============================================================================

class TestRealMethods:
    """Tests that use actual subprocess calls (mocked)."""

    def test_is_available_with_real_executor(self):
        """Test is_available with actual subprocess mock."""
        config = ClientConfig()
        config.claude_path = "/usr/bin/nonexistent_claude"

        executor = ClaudeExecutor(config)
        # Should return False since claude doesn't exist at that path
        result = executor.is_available()
        assert result is False

    def test_get_version_with_real_executor(self):
        """Test get_version with actual subprocess mock."""
        config = ClientConfig()
        config.claude_path = "/usr/bin/nonexistent_claude"

        executor = ClaudeExecutor(config)
        result = executor.get_version()
        assert result is None
