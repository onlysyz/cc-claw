"""Tests for client/tools.py - All tool utilities."""

import os
import json
import sqlite3
import subprocess
import smtplib
import requests
import socket
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.tools import (
    FileProcessor, DataScraper, ApiClient, ProcessManager,
    SystemInfo, GitHelper, DockerHelper, DatabaseTool,
    ImageTool, NotificationTool, CodeAnalysisTool, MonitorTool
)


class TestApiClient:
    """Test ApiClient.call() and ApiClient.call_with_auth()."""

    @patch('client.tools.requests.request')
    def test_call_get_success(self, mock_request):
        """GET request returns status and data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}
        mock_response.headers = {}
        mock_request.return_value = mock_response

        result = ApiClient.call("https://api.example.com/data")

        assert result['status'] == 200
        assert result['data'] == {"result": "ok"}
        mock_request.assert_called_once()

    @patch('client.tools.requests.request')
    def test_call_post_with_json_data(self, mock_request):
        """POST request with json_data is sent correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 1}
        mock_response.headers = {}
        mock_request.return_value = mock_response

        result = ApiClient.call(
            "https://api.example.com/items",
            method="POST",
            json_data={"name": "test"}
        )

        assert result['status'] == 201
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs['method'] == 'POST'
        assert call_kwargs['json'] == {"name": "test"}

    @patch('client.tools.requests.request')
    def test_call_with_custom_headers(self, mock_request):
        """Custom headers are merged with default headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.headers = {}
        mock_request.return_value = mock_response

        ApiClient.call("https://api.example.com", headers={"X-Custom": "header"})

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs['headers']['X-Custom'] == 'header'
        assert call_kwargs['headers']['User-Agent'] == 'CC-Claw/1.0'

    @patch('client.tools.requests.request')
    def test_call_non_json_response(self, mock_request):
        """Non-JSON response falls back to text in data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("", "", 0)
        mock_response.text = "plain text response"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        result = ApiClient.call("https://api.example.com")

        assert result['data'] == {'text': 'plain text response'}

    @patch('client.tools.requests.request')
    def test_call_request_exception_propagates(self, mock_request):
        """Request exception propagates out of call() - not caught internally."""
        mock_request.side_effect = requests.exceptions.Timeout("Connection timed out")

        with pytest.raises(requests.exceptions.Timeout):
            ApiClient.call("https://api.example.com")

    @patch('client.tools.requests.request')
    def test_call_delete_method(self, mock_request):
        """DELETE request is sent with correct method."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.json.return_value = None
        mock_response.headers = {}
        mock_request.return_value = mock_response

        result = ApiClient.call(
            "https://api.example.com/items/1",
            method="DELETE"
        )

        assert result['status'] == 204
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs['method'] == 'DELETE'

    @patch('client.tools.requests.request')
    def test_call_with_params(self, mock_request):
        """GET request with query params is sent correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_response.headers = {}
        mock_request.return_value = mock_response

        ApiClient.call(
            "https://api.example.com/search",
            params={"q": "test", "page": 1}
        )

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs['params'] == {"q": "test", "page": 1}

    @patch('client.tools.requests.request')
    def test_call_connection_error(self, mock_request):
        """Connection error propagates as exception."""
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            ApiClient.call("https://api.example.com")

    @patch('client.tools.requests.request')
    def test_call_http_error_status(self, mock_request):
        """HTTP error status code is returned in result."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Not found"}
        mock_response.headers = {}
        mock_request.return_value = mock_response

        result = ApiClient.call("https://api.example.com/missing")

        assert result['status'] == 404
        assert result['data'] == {"error": "Not found"}

    @patch('client.tools.requests.request')
    def test_call_timeout_param(self, mock_request):
        """timeout parameter is passed to requests."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.headers = {}
        mock_request.return_value = mock_response

        ApiClient.call("https://api.example.com", timeout=60)

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs['timeout'] == 60

    @patch('client.tools.ApiClient.call')
    def test_call_with_auth(self, mock_call):
        """call_with_auth adds Bearer token to headers."""
        mock_call.return_value = {'status': 200, 'data': {}, 'headers': {}}
        ApiClient.call_with_auth(
            "https://api.example.com",
            token="secret-token",
            method="GET"
        )
        call_args = mock_call.call_args
        auth_headers = call_args[0][2]
        assert auth_headers['Authorization'] == 'Bearer secret-token'


class TestProcessManager:
    """Test ProcessManager list/kill/is_running."""

    @patch('client.tools.subprocess.run')
    def test_list_returns_processes(self, mock_run):
        """ps aux returns parsed process list."""
        mock_result = MagicMock()
        # ps aux columns: USER PID %CPU %MEM VSZ RSS TT STAT STARTED TIME COMMAND
        mock_result.stdout.strip.return_value = "USER PID %CPU %MEM VSZ RSS TT STAT STARTED TIME COMMAND\nroot 1234 0.1 0.2 1234 567 tt00 S 10:00 0:01 python app.py"
        mock_run.return_value = mock_result

        processes = ProcessManager.list()

        assert len(processes) == 1
        assert processes[0]['pid'] == 1234
        assert processes[0]['command'] == 'python app.py'

    @patch('client.tools.subprocess.run')
    def test_list_with_pattern(self, mock_run):
        """Pattern filters processes via grep."""
        mock_result = MagicMock()
        mock_result.stdout = "root 5678 0.0 0.1 grep python"
        mock_result.strip.return_value = mock_result.stdout
        mock_run.return_value = mock_result

        ProcessManager.list("python")

        call_cmd = mock_run.call_args[0][0]
        assert 'grep' in call_cmd and 'python' in call_cmd

    @patch('client.tools.os.kill')
    def test_kill_success(self, mock_kill):
        """Kill with valid PID returns True."""
        result = ProcessManager.kill(1234)
        assert result is True
        mock_kill.assert_called_once_with(1234, 15)

    @patch('client.tools.os.kill')
    def test_kill_process_not_found(self, mock_kill):
        """Kill non-existent PID returns False."""
        mock_kill.side_effect = ProcessLookupError("No such process")
        result = ProcessManager.kill(9999)
        assert result is False

    @patch('client.tools.ProcessManager.list')
    def test_is_running_found(self, mock_list):
        """is_running returns True when process found."""
        mock_list.return_value = [
            {'pid': 1234, 'command': 'python app.py'}
        ]
        assert ProcessManager.is_running("python") is True

    @patch('client.tools.ProcessManager.list')
    def test_is_running_not_found(self, mock_list):
        """is_running returns False when no process found."""
        mock_list.return_value = []
        assert ProcessManager.is_running("nonexistent") is False

    @patch('client.tools.ProcessManager.list')
    def test_is_running_grep_in_command_returns_false(self, mock_list):
        """is_running returns False when only grep process matches."""
        mock_list.return_value = [
            {'pid': 5678, 'command': 'grep python'}
        ]
        assert ProcessManager.is_running("python") is False

    @patch('client.tools.subprocess.run')
    def test_list_empty_output(self, mock_run):
        """ps aux with no matching processes returns empty list."""
        mock_result = MagicMock()
        mock_result.stdout.strip.return_value = "USER PID %CPU %MEM VSZ RSS TT STAT STARTED TIME COMMAND"
        mock_run.return_value = mock_result

        processes = ProcessManager.list()

        assert processes == []

    @patch('client.tools.os.kill')
    def test_kill_oserror_propagates(self, mock_kill):
        """OSError other than ProcessLookupError propagates (only ProcessLookupError is caught)."""
        mock_kill.side_effect = OSError("Permission denied")
        with pytest.raises(OSError):
            ProcessManager.kill(1234)

    @patch('client.tools.subprocess.run')
    def test_list_command_failure(self, mock_run):
        """subprocess CalledProcessError propagates (no try/except in list())."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "ps aux")
        with pytest.raises(subprocess.CalledProcessError):
            ProcessManager.list()


class TestGitHelper:
    """Test GitHelper status/diff/log/branch."""

    @patch('client.tools.subprocess.run')
    def test_status(self, mock_run):
        """git status --porcelain returns output."""
        mock_run.return_value = MagicMock(stdout=" M file.py\n?? new.py")

        status = GitHelper.status()

        assert 'M file.py' in status
        mock_run.assert_called_once()
        assert 'git' in mock_run.call_args[0][0]

    @patch('client.tools.subprocess.run')
    def test_diff_no_file(self, mock_run):
        """git diff without file returns full diff."""
        mock_run.return_value = MagicMock(stdout="--- a/file.py\n+++ b/file.py")

        GitHelper.diff()

        call_args = mock_run.call_args[0][0]
        assert 'git' in call_args and 'diff' in call_args

    @patch('client.tools.subprocess.run')
    def test_diff_with_file(self, mock_run):
        """git diff <filename> returns file diff."""
        mock_run.return_value = MagicMock(stdout="--- a/file.py")

        GitHelper.diff("file.py")

        call_args = mock_run.call_args[0][0]
        assert 'file.py' in call_args

    @patch('client.tools.subprocess.run')
    def test_log_returns_commits(self, mock_run):
        """git log returns parsed commit list."""
        mock_run.return_value = MagicMock(stdout="abc123 | Fix bug | Author | 2024-01-01")

        commits = GitHelper.log(limit=5)

        assert len(commits) >= 1
        assert commits[0]['hash'].strip() == 'abc123'
        assert commits[0]['message'].strip() == 'Fix bug'

    @patch('client.tools.subprocess.run')
    def test_branch(self, mock_run):
        """git branch --show-current returns branch name."""
        mock_run.return_value = MagicMock(stdout="main")

        branch = GitHelper.branch()

        assert branch == "main"

    @patch('client.tools.subprocess.run')
    def test_status_empty(self, mock_run):
        """git status with no changes returns empty string."""
        mock_run.return_value = MagicMock(stdout="")

        status = GitHelper.status()

        assert status == ""

    @patch('client.tools.subprocess.run')
    def test_log_empty_output(self, mock_run):
        """git log with no commits returns empty list."""
        mock_run.return_value = MagicMock(stdout="")

        commits = GitHelper.log()

        assert commits == []

    @patch('client.tools.subprocess.run')
    def test_log_multiple_commits(self, mock_run):
        """git log parses multiple commit lines correctly."""
        mock_run.return_value = MagicMock(stdout=(
            "abc | Fix bug | Alice | 2024-01-01\n"
            "def | Add feat | Bob | 2024-01-02\n"
        ))

        commits = GitHelper.log(limit=10)

        assert len(commits) == 2
        assert commits[0]['author'].strip() == 'Alice'
        assert commits[1]['author'].strip() == 'Bob'

    @patch('client.tools.subprocess.run')
    def test_diff_stderr_included(self, mock_run):
        """git diff stdout includes diff content."""
        mock_run.return_value = MagicMock(stdout="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@")

        diff = GitHelper.diff("test.py")

        assert '--- a/test.py' in diff
        assert mock_run.call_args[0][0] == ['git', 'diff', 'test.py']

    @patch('client.tools.subprocess.run')
    def test_branch_error_propagates(self, mock_run):
        """git branch command failure propagates exception."""
        mock_run.side_effect = subprocess.CalledProcessError(128, "git branch")

        with pytest.raises(subprocess.CalledProcessError):
            GitHelper.branch()

    @patch('client.tools.subprocess.run')
    def test_diff_error_propagates(self, mock_run):
        """git diff command failure propagates exception."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git diff")

        with pytest.raises(subprocess.CalledProcessError):
            GitHelper.diff()


class TestDockerHelper:
    """Test DockerHelper ps/logs/restart/status."""

    @patch('client.tools.subprocess.run')
    def test_ps(self, mock_run):
        """docker ps returns container list."""
        mock_run.return_value = MagicMock(stdout="abc123 | web | running | nginx")

        containers = DockerHelper.ps()

        assert len(containers) == 1
        assert containers[0]['id'].strip() == 'abc123'
        assert containers[0]['name'].strip() == 'web'

    @patch('client.tools.subprocess.run')
    def test_ps_all(self, mock_run):
        """docker ps -a includes all containers."""
        mock_run.return_value = MagicMock(stdout="")

        DockerHelper.ps(all=True)

        call_args = mock_run.call_args[0][0]
        assert '-a' in call_args

    @patch('client.tools.subprocess.run')
    def test_logs(self, mock_run):
        """docker logs returns stdout + stderr."""
        mock_run.return_value = MagicMock(stdout="log line", stderr="")

        logs = DockerHelper.logs("container1", lines=20)

        call_args = mock_run.call_args[0][0]
        assert 'container1' in call_args
        assert '20' in call_args

    @patch('client.tools.subprocess.run')
    def test_restart_success(self, mock_run):
        """docker restart returns True on success."""
        mock_run.return_value = MagicMock(returncode=0)

        result = DockerHelper.restart("container1")

        assert result is True

    @patch('client.tools.subprocess.run')
    def test_restart_failure(self, mock_run):
        """docker restart returns False on failure."""
        mock_run.return_value = MagicMock(returncode=1)

        result = DockerHelper.restart("nonexistent")

        assert result is False

    @patch('client.tools.subprocess.run')
    def test_status(self, mock_run):
        """docker system df returns usage info dict."""
        mock_run.return_value = MagicMock(stdout="Images|10|1.5GB\nContainers|5|200MB")

        info = DockerHelper.status()

        assert 'images' in info or 'containers' in info

    @patch('client.tools.subprocess.run')
    def test_ps_empty(self, mock_run):
        """docker ps with no containers returns empty list."""
        mock_run.return_value = MagicMock(stdout="")

        containers = DockerHelper.ps()

        assert containers == []

    @patch('client.tools.subprocess.run')
    def test_ps_multiple_containers(self, mock_run):
        """docker ps parses multiple containers correctly."""
        mock_run.return_value = MagicMock(stdout=(
            "abc123 | web | running | nginx:latest\n"
            "def456 | db | exited | postgres:15\n"
        ))

        containers = DockerHelper.ps()

        assert len(containers) == 2
        assert containers[0]['name'].strip() == 'web'
        assert containers[1]['name'].strip() == 'db'

    @patch('client.tools.subprocess.run')
    def test_ps_error_propagates(self, mock_run):
        """docker ps error propagates (no try/except)."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "docker ps")

        with pytest.raises(subprocess.CalledProcessError):
            DockerHelper.ps()

    @patch('client.tools.subprocess.run')
    def test_logs_error_propagates(self, mock_run):
        """docker logs error propagates."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "docker logs")

        with pytest.raises(subprocess.CalledProcessError):
            DockerHelper.logs("bad_container")

    @patch('client.tools.subprocess.run')
    def test_status_empty_output(self, mock_run):
        """docker system df with no output returns default info dict."""
        mock_run.return_value = MagicMock(stdout="")

        info = DockerHelper.status()

        assert info == {'images': 0, 'containers': 0, 'volumes': 0}

    @patch('client.tools.subprocess.run')
    def test_status_unknown_type_ignored(self, mock_run):
        """docker system df with unknown type ignores it gracefully."""
        mock_run.return_value = MagicMock(stdout="Images|5|500MB\nBuildCache|20|1GB")

        info = DockerHelper.status()

        assert info['images'] == {'total': 5, 'size': '500MB'}
        assert 'BuildCache' not in info

    @patch('client.tools.subprocess.run')
    def test_restart_error_propagates(self, mock_run):
        """docker restart error propagates."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "docker restart")

        with pytest.raises(subprocess.CalledProcessError):
            DockerHelper.restart("container1")


class TestDatabaseTool:
    """Test DatabaseTool query/execute/list_tables/table_info/create_table."""

    def test_query_select(self, tmp_path):
        """SELECT query returns rows as dicts."""
        db = str(tmp_path / "test.db")
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'alice')")
        conn.commit()
        conn.close()

        result = DatabaseTool.query(db, "SELECT * FROM test")

        assert len(result) == 1
        assert result[0]['name'] == 'alice'

    def test_query_insert_returns_affected_rows(self, tmp_path):
        """INSERT via query returns affected_rows."""
        db = str(tmp_path / "test.db")

        result = DatabaseTool.query(db, "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        result = DatabaseTool.query(db, "INSERT INTO test VALUES (1, 'alice')")

        assert result[0]['affected_rows'] == 1

    def test_query_error(self, tmp_path):
        """Invalid SQL returns error in result."""
        db = str(tmp_path / "test.db")

        result = DatabaseTool.query(db, "INVALID SQL")

        assert 'error' in result[0]

    def test_execute_insert(self, tmp_path):
        """execute() INSERT returns rowcount and lastrowid."""
        db = str(tmp_path / "test.db")
        DatabaseTool.execute(db, "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")

        result = DatabaseTool.execute(db, "INSERT INTO test VALUES (NULL, 'bob')")

        assert result['rowcount'] == 1
        assert result['lastrowid'] == 1

    def test_execute_error(self, tmp_path):
        """execute() with bad SQL returns error dict."""
        db = str(tmp_path / "test.db")

        result = DatabaseTool.execute(db, "bad sql")

        assert 'error' in result

    def test_list_tables(self, tmp_path):
        """list_tables returns table names."""
        db = str(tmp_path / "test.db")
        DatabaseTool.execute(db, "CREATE TABLE t1 (id INTEGER)")
        DatabaseTool.execute(db, "CREATE TABLE t2 (id INTEGER)")

        tables = DatabaseTool.list_tables(db)

        assert 't1' in tables
        assert 't2' in tables

    def test_list_tables_error(self, tmp_path):
        """list_tables with bad db returns error string."""
        result = DatabaseTool.list_tables("/nonexistent/bad.db")
        assert len(result) == 1
        assert 'unable' in result[0] or 'error' in result[0].lower()

    def test_table_info(self, tmp_path):
        """table_info returns column schema."""
        db = str(tmp_path / "test.db")
        DatabaseTool.execute(db, "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")

        info = DatabaseTool.table_info(db, "users")

        assert len(info) >= 2
        assert any(col['name'] == 'id' for col in info)

    def test_create_table(self, tmp_path):
        """create_table creates table with given schema."""
        db = str(tmp_path / "test.db")

        result = DatabaseTool.create_table(db, "items", {"id": "INTEGER PRIMARY KEY", "name": "TEXT"})

        assert result is True
        tables = DatabaseTool.list_tables(db)
        assert 'items' in tables

    def test_create_table_failure(self, tmp_path):
        """create_table with invalid schema returns False."""
        db = str(tmp_path / "test.db")
        # Invalid SQL syntax
        result = DatabaseTool.create_table(db, "123badname", {"col": "INTEGER"})
        assert result is False

    def test_query_update(self, tmp_path):
        """UPDATE via query returns affected_rows."""
        db = str(tmp_path / "test.db")
        DatabaseTool.query(db, "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        DatabaseTool.query(db, "INSERT INTO test VALUES (1, 'alice')")

        result = DatabaseTool.query(db, "UPDATE test SET name='bob' WHERE id=1")

        assert result[0]['affected_rows'] == 1

    def test_query_delete(self, tmp_path):
        """DELETE via query returns affected_rows."""
        db = str(tmp_path / "test.db")
        DatabaseTool.query(db, "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        DatabaseTool.query(db, "INSERT INTO test VALUES (1, 'alice')")

        result = DatabaseTool.query(db, "DELETE FROM test WHERE id=1")

        assert result[0]['affected_rows'] == 1

    def test_execute_update(self, tmp_path):
        """execute() UPDATE returns rowcount."""
        db = str(tmp_path / "test.db")
        DatabaseTool.execute(db, "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        DatabaseTool.execute(db, "INSERT INTO test VALUES (1, 'alice')")

        result = DatabaseTool.execute(db, "UPDATE test SET name='bob' WHERE id=1")

        assert result['rowcount'] == 1

    def test_execute_delete(self, tmp_path):
        """execute() DELETE returns rowcount."""
        db = str(tmp_path / "test.db")
        DatabaseTool.execute(db, "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        DatabaseTool.execute(db, "INSERT INTO test VALUES (1, 'alice')")

        result = DatabaseTool.execute(db, "DELETE FROM test WHERE id=1")

        assert result['rowcount'] == 1

    def test_table_info_nonexistent_table(self, tmp_path):
        """table_info on nonexistent table returns empty list (PRAGMA doesn't raise)."""
        db = str(tmp_path / "test.db")
        DatabaseTool.execute(db, "CREATE TABLE real_table (id INTEGER)")

        result = DatabaseTool.table_info(db, "nonexistent_table")

        assert result == []

    def test_table_info_error_returns_error_dict(self, tmp_path):
        """table_info when sqlite3 raises returns error dict."""
        # Pass a path to a directory instead of a database file
        result = DatabaseTool.table_info(str(tmp_path), "any_table")

        assert isinstance(result, list)
        assert len(result) == 1
        assert 'error' in result[0]


class TestNotificationTool:
    """Test NotificationTool email/push/slack."""

    @patch('smtplib.SMTP')
    def test_send_email_success(self, mock_smtp):
        """send_email with valid params sends email."""
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance

        result = NotificationTool.send_email(
            to="user@example.com",
            subject="Test",
            body="Hello",
            smtp_host="localhost",
            smtp_port=25,
            from_addr="cc-claw@localhost"
        )

        assert result.get('success') is True
        mock_smtp_instance.send_message.assert_called()

    @patch('smtplib.SMTP')
    def test_send_email_smtp_error(self, mock_smtp):
        """SMTP exception returns error dict."""
        mock_smtp.side_effect = ConnectionRefusedError("SMTP not available")

        result = NotificationTool.send_email(
            to="user@example.com",
            subject="Test",
            body="Hello"
        )

        assert result.get('success') is False
        assert 'error' in result

    @patch('os.path.exists')
    @patch('client.tools.subprocess.run')
    def test_push_notify_send(self, mock_run, mock_exists):
        """push uses notify-send when available on Linux."""
        mock_exists.return_value = True

        result = NotificationTool.push(title="Alert", body="Test message", priority="high")

        assert result.get('success') is True
        assert result.get('method') == 'notify-send'

    @patch('client.tools.requests.post')
    def test_slack_webhook(self, mock_post):
        """slack_webhook posts to webhook URL with channel."""
        mock_post.return_value = MagicMock(status_code=200)

        result = NotificationTool.slack_webhook(
            webhook_url="https://hooks.slack.com/test",
            text="Hello Slack",
            channel="#general"
        )

        assert result.get('success') is True
        mock_post.assert_called_once()

    @patch('client.tools.requests.post')
    def test_slack_webhook_without_channel(self, mock_post):
        """slack_webhook works without channel field."""
        mock_post.return_value = MagicMock(status_code=200)

        result = NotificationTool.slack_webhook(
            webhook_url="https://hooks.slack.com/test",
            text="Hello Slack"
        )

        assert result.get('success') is True

    @patch('client.tools.requests.post')
    def test_slack_webhook_error_response(self, mock_post):
        """slack_webhook returns failure for non-200 status."""
        mock_post.return_value = MagicMock(status_code=500)

        result = NotificationTool.slack_webhook(
            webhook_url="https://hooks.slack.com/test",
            text="Hello"
        )

        assert result.get('success') is False
        assert result.get('status') == 500

    @patch('client.tools.requests.post')
    def test_slack_webhook_exception(self, mock_post):
        """slack_webhook returns error dict on exception."""
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        result = NotificationTool.slack_webhook(
            webhook_url="https://hooks.slack.com/test",
            text="Hello"
        )

        assert result.get('success') is False
        assert 'error' in result

    @patch('os.path.exists')
    @patch('client.tools.subprocess.run')
    def test_push_terminal_notifier(self, mock_run, mock_exists):
        """push uses terminal-notifier when available on macOS."""
        def exists_side_effect(path):
            if path == '/usr/bin/notify-send':
                return False
            if path == '/usr/local/bin/terminal-notifier':
                return True
            return False
        mock_exists.side_effect = exists_side_effect

        result = NotificationTool.push(title="Alert", body="Test message")

        assert result.get('success') is True
        assert result.get('method') == 'terminal-notifier'

    @patch('os.path.exists')
    @patch('client.tools.subprocess.run')
    def test_push_no_tool_available(self, mock_run, mock_exists):
        """push returns error when neither notify-send nor terminal-notifier exists."""
        mock_exists.return_value = False

        result = NotificationTool.push(title="Alert", body="Test message")

        assert result.get('success') is False
        assert 'No notification tool available' in result.get('error', '')

    @patch('os.path.exists')
    @patch('client.tools.subprocess.run')
    def test_push_notify_send_exception(self, mock_run, mock_exists):
        """push returns error when notify-send subprocess fails."""
        mock_exists.return_value = True
        mock_run.side_effect = subprocess.CalledProcessError(1, "notify-send")

        result = NotificationTool.push(title="Alert", body="Test message")

        assert result.get('success') is False
        assert 'error' in result

    @patch('smtplib.SMTP')
    def test_send_email_general_exception(self, mock_smtp):
        """send_email catches general Exception (not just SMTP errors)."""
        mock_smtp.side_effect = Exception("Unexpected error")

        result = NotificationTool.send_email(
            to="user@example.com",
            subject="Test",
            body="Hello"
        )

        assert result.get('success') is False
        assert 'error' in result


class TestFileProcessor:
    """Test FileProcessor read/write/append/find/count_lines/search."""

    def test_read_file(self, tmp_path):
        """read returns file content."""
        f = tmp_path / "test.txt"
        f.write_text("hello world")

        content = FileProcessor.read(str(f))

        assert content == "hello world"

    def test_write_file(self, tmp_path):
        """write creates file and returns True."""
        path = str(tmp_path / "written.txt")

        result = FileProcessor.write(path, "new content")

        assert result is True
        assert (tmp_path / "written.txt").read_text() == "new content"

    def test_write_creates_parent_dirs(self, tmp_path):
        """write creates nested parent directories."""
        path = str(tmp_path / "a" / "b" / "c.txt")

        FileProcessor.write(path, "nested")

        assert (tmp_path / "a" / "b" / "c.txt").read_text() == "nested"

    def test_append_file(self, tmp_path):
        """append adds content to existing file."""
        f = tmp_path / "append.txt"
        f.write_text("start")

        FileProcessor.append(str(f), "-end")

        assert f.read_text() == "start-end"

    def test_count_lines(self, tmp_path):
        """count_lines returns number of lines."""
        f = tmp_path / "lines.txt"
        f.write_text("line1\nline2\nline3\n")

        count = FileProcessor.count_lines(str(f))

        assert count == 3

    @patch('client.tools.subprocess.run')
    def test_find_no_matches_returns_empty_list(self, mock_run):
        """find returns [] when find finds no files."""
        mock_run.return_value = MagicMock(stdout='')

        result = FileProcessor.find('*.nonexistent')

        assert result == []

    @patch('client.tools.subprocess.run')
    def test_find_with_matches_returns_file_list(self, mock_run):
        """find returns list of file paths when matches exist."""
        mock_run.return_value = MagicMock(stdout='/path/a.txt\n/path/b.txt')

        result = FileProcessor.find('*.txt')

        assert len(result) == 2
        assert '/path/a.txt' in result

    @patch('client.tools.subprocess.run')
    def test_find_filters_empty_lines(self, mock_run):
        """find filters out empty strings from stdout split."""
        mock_run.return_value = MagicMock(stdout='/path/file.txt\n')

        result = FileProcessor.find('*.txt')

        assert result == ['/path/file.txt']

    @patch('client.tools.subprocess.run')
    def test_search_no_matches_returns_empty_list(self, mock_run):
        """search returns [] when grep finds nothing."""
        mock_run.return_value = MagicMock(stdout='')

        result = FileProcessor.search('nonexistent')

        assert result == []

    @patch('client.tools.subprocess.run')
    def test_search_with_matches_returns_dict_list(self, mock_run):
        """search returns list of dicts with file/line/content."""
        mock_run.return_value = MagicMock(stdout='/path/file.py:10:def hello():\n')

        result = FileProcessor.search('def')

        assert len(result) == 1
        assert result[0]['file'] == '/path/file.py'
        assert result[0]['line'] == 10
        assert result[0]['content'] == 'def hello():'

    @patch('client.tools.subprocess.run')
    def test_search_line_without_colon_skipped(self, mock_run):
        """search skips lines without colons (malformed output)."""
        mock_run.return_value = MagicMock(stdout='No such file or directory\n/path/file.py:5:valid line\n')

        result = FileProcessor.search('def')

        assert len(result) == 1
        assert result[0]['file'] == '/path/file.py'

    @patch('client.tools.subprocess.run')
    def test_search_line_number_nondigit_returns_zero(self, mock_run):
        """search with non-digit line number returns line=0."""
        mock_run.return_value = MagicMock(stdout='/path/file.py:abc:some content\n')

        result = FileProcessor.search('abc')

        assert result[0]['line'] == 0

    @patch('client.tools.subprocess.run')
    def test_search_content_without_third_colon(self, mock_run):
        """search with only 2 colons (no third) returns empty content."""
        # '/path/file.py:1:content' splits to ['/path/file.py', '1', 'content'] - 3 parts, len>2 is True
        # We need a line with ONLY 2 colons: '/path/file.py:1' splits to ['/path/file.py', '1'] - 2 parts
        mock_run.return_value = MagicMock(stdout='/path/file.py:1\n')

        result = FileProcessor.search('no third')

        assert result[0]['content'] == ''


class TestDataScraper:
    """Test DataScraper fetch/fetch_json/extract_links/extract_emails/extract_ips."""

    @patch('client.tools.requests.get')
    def test_fetch(self, mock_get):
        """fetch returns status/content/headers/url."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Test</html>"
        mock_response.url = "https://example.com"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_get.return_value = mock_response

        result = DataScraper.fetch("https://example.com")

        assert result['status'] == 200
        assert result['content'] == "<html>Test</html>"
        assert result['url'] == "https://example.com"

    @patch('client.tools.requests.get')
    def test_fetch_with_custom_headers(self, mock_get):
        """fetch merges custom headers with default User-Agent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_response.url = ""
        mock_response.headers = {}
        mock_get.return_value = mock_response

        DataScraper.fetch("https://example.com", headers={"X-Custom": "value"})

        call_headers = mock_get.call_args[1]['headers']
        assert call_headers['User-Agent'] == 'Mozilla/5.0 (compatible; CC-Claw/1.0)'
        assert call_headers['X-Custom'] == 'value'

    @patch('client.tools.requests.get')
    def test_fetch_json(self, mock_get):
        """fetch_json parses JSON response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": "value"}
        mock_get.return_value = mock_response

        result = DataScraper.fetch_json("https://api.example.com/data")

        assert result == {"key": "value"}

    def test_extract_links(self):
        """extract_links finds href values from HTML."""
        html = '<a href="/page1"><a href="https://example.com/page2">'

        links = DataScraper.extract_links(html, "https://example.com")

        assert any("page1" in l for l in links)
        assert any("page2" in l for l in links)

    def test_extract_links_no_base_url(self):
        """extract_links returns raw hrefs without base_url."""
        html = '<a href="/relative">'

        links = DataScraper.extract_links(html)

        assert "/relative" in links

    def test_extract_emails(self):
        """extract_emails finds email addresses in text."""
        text = "Contact alice@example.com or bob@company.org"

        emails = DataScraper.extract_emails(text)

        assert "alice@example.com" in emails
        assert "bob@company.org" in emails

    def test_extract_ips(self):
        """extract_ips finds IP addresses in text."""
        text = "Server 192.168.1.1 and 10.0.0.1"

        ips = DataScraper.extract_ips(text)

        assert "192.168.1.1" in ips
        assert "10.0.0.1" in ips

    def test_extract_ips_deduplicates(self):
        """extract_ips removes duplicate IPs."""
        text = "IP 8.8.8.8 and also 8.8.8.8"

        ips = DataScraper.extract_ips(text)

        assert ips.count("8.8.8.8") == 1


class TestSystemInfo:
    """Test SystemInfo disk_usage/memory/cpu_load."""

    def test_disk_usage_returns_dict(self):
        """disk_usage returns dict with total/used/free/percent."""
        result = SystemInfo.disk_usage("/")

        assert 'total' in result
        assert 'used' in result
        assert 'free' in result
        assert 'percent' in result
        assert isinstance(result['percent'], float)


class TestCodeAnalysisTool:
    """Test CodeAnalysisTool count_lines/find_functions/complexity/dependencies."""

    def test_count_lines_with_extensions(self, tmp_path):
        """count_lines counts lines for specified extensions."""
        py_file = tmp_path / "test.py"
        py_file.write_text("print('a')\nprint('b')\n")

        result = CodeAnalysisTool.count_lines(str(tmp_path), extensions="py")

        assert result['total'] == 2
        assert result['by_language'].get('py', 0) == 2

    def test_count_lines_nonexistent_path(self):
        """count_lines handles nonexistent path gracefully."""
        result = CodeAnalysisTool.count_lines("/nonexistent/path/xyz")

        assert 'error' in result or result.get('total', 0) == 0

    def test_find_functions_python(self, tmp_path):
        """find_functions finds def statements in Python files."""
        py_file = tmp_path / "demo.py"
        py_file.write_text("def hello(name):\n    pass\n\ndef world(x, y):\n    pass\n")

        funcs = CodeAnalysisTool.find_functions(str(tmp_path), language="python")

        names = [f['name'] for f in funcs]
        assert 'hello' in names
        assert 'world' in names

    def test_complexity_returns_dict(self, tmp_path):
        """complexity returns total/files/avg complexity."""
        py_file = tmp_path / "test.py"
        py_file.write_text("if a:\n    pass\nelif b:\n    pass\n")

        result = CodeAnalysisTool.complexity(str(tmp_path), language="py")

        assert 'total_complexity' in result
        assert 'files_analyzed' in result

    def test_dependencies_returns_dict(self, tmp_path):
        """dependencies returns import counts."""
        py_file = tmp_path / "main.py"
        py_file.write_text("import os\nimport sys\nfrom pathlib import Path\n")

        result = CodeAnalysisTool.dependencies(str(tmp_path))

        assert 'dependencies' in result or 'error' in result or 'total_unique' in result

    @patch('client.tools.os.walk')
    def test_count_lines_oserror_returns_error(self, mock_walk):
        """count_lines outer exception returns error dict."""
        mock_walk.side_effect = OSError("Permission denied")

        result = CodeAnalysisTool.count_lines('/fake/path')

        assert result.get('error') == "Permission denied"

    def test_count_lines_file_read_error_skipped(self, tmp_path):
        """count_lines skips files that fail to read (bare except pass)."""
        py_file = tmp_path / "test.py"
        py_file.write_text("valid line\n")

        with patch('client.tools.open', side_effect=UnicodeDecodeError('utf-8', b'', 0, 1, 'bad')):
            result = CodeAnalysisTool.count_lines(str(tmp_path))

        # Bare except passes, so file contributes 0 lines - returns dict without error
        assert 'total' in result
        assert 'by_language' in result

    @patch('client.tools.os.walk')
    def test_find_functions_oserror_returns_error(self, mock_walk):
        """find_functions outer exception returns error dict."""
        mock_walk.side_effect = OSError("Path not accessible")

        result = CodeAnalysisTool.find_functions('/fake/path')

        assert result == [{'error': "Path not accessible"}]

    def test_find_functions_file_read_error_skipped(self, tmp_path):
        """find_functions skips files that fail to read (bare except pass)."""
        py_file = tmp_path / "demo.py"
        py_file.write_text("def hello():\n    pass\n")

        with patch('client.tools.open', side_effect=OSError("read failed")):
            result = CodeAnalysisTool.find_functions(str(tmp_path))

        # Bare except passes, returns empty list
        assert result == []

    @patch('client.tools.os.walk')
    def test_complexity_oserror_returns_error(self, mock_walk):
        """complexity outer exception returns error dict."""
        mock_walk.side_effect = OSError("Access denied")

        result = CodeAnalysisTool.complexity('/fake/path')

        assert result.get('error') == "Access denied"

    def test_complexity_file_read_error_skipped(self, tmp_path):
        """complexity skips files that fail to read (bare except pass)."""
        py_file = tmp_path / "test.py"
        py_file.write_text("if x:\n    pass\n")

        with patch('client.tools.open', side_effect=OSError("read failed")):
            result = CodeAnalysisTool.complexity(str(tmp_path), language="py")

        # Bare except passes, files_analyzed stays 0 → avg_complexity 0
        assert result.get('files_analyzed') == 0
        assert result.get('avg_complexity') == 0

    @patch('client.tools.os.walk')
    def test_dependencies_oserror_returns_error(self, mock_walk):
        """dependencies outer exception returns error dict."""
        mock_walk.side_effect = OSError("Permission denied")

        result = CodeAnalysisTool.dependencies('/fake/path')

        assert result.get('error') == "Permission denied"

    def test_dependencies_file_read_error_skipped(self, tmp_path):
        """dependencies skips files that fail to read (bare except pass)."""
        py_file = tmp_path / "main.py"
        py_file.write_text("import os\nimport sys\n")

        with patch('client.tools.open', side_effect=OSError("read failed")):
            result = CodeAnalysisTool.dependencies(str(tmp_path))

        # Bare except passes, returns empty deps
        assert result.get('total_unique') == 0
        assert result.get('dependencies') == {}

    def test_dependencies_with_js_file(self, tmp_path):
        """dependencies parses .js require() and import syntax."""
        js_file = tmp_path / "app.js"
        js_file.write_text("const express = require('express');\nimport axios from 'axios';\n")

        result = CodeAnalysisTool.dependencies(str(tmp_path))

        assert result.get('total_unique', 0) >= 1

    def test_complexity_zero_files_returns_zero_avg(self, tmp_path):
        """complexity with no matching files returns avg_complexity 0."""
        # Write a .java file when language='py' → no files match
        java_file = tmp_path / "main.java"
        java_file.write_text("if (true) {}\n")

        result = CodeAnalysisTool.complexity(str(tmp_path), language="py")

        assert result.get('files_analyzed') == 0
        assert result.get('avg_complexity') == 0


class TestMonitorTool:
    """Test MonitorTool health_check/check_disk/check_memory/check_cpu."""

    @patch('client.tools.MonitorTool.check_disk')
    @patch('client.tools.MonitorTool.check_memory')
    @patch('client.tools.MonitorTool.check_cpu')
    @patch('client.tools.MonitorTool.check_port')
    def test_health_check(self, mock_port, mock_cpu, mock_mem, mock_disk):
        """health_check aggregates all monitor results."""
        mock_disk.return_value = {'alert': False}
        mock_mem.return_value = {'alert': False}
        mock_cpu.return_value = {'alert': False}
        mock_port.return_value = {'port_open': True}

        result = MonitorTool.health_check(port=3000)

        assert 'disk' in result
        assert 'memory' in result
        assert 'cpu' in result
        assert 'port_open' in result

    def test_check_disk_returns_alert_info(self):
        """check_disk returns alert/percent/threshold info."""
        result = MonitorTool.check_disk(threshold=90)

        assert 'alert' in result
        assert 'percent' in result
        assert 'threshold' in result

    def test_check_port_open(self):
        """check_port returns port_open status."""
        result = MonitorTool.check_port(80, host="localhost")

        assert 'port_open' in result
        assert 'port' in result

    # Edge case tests for MonitorTool

    @patch('client.tools.SystemInfo.disk_usage')
    def test_check_disk_alert_below_threshold(self, mock_disk):
        """check_disk alert=False when percent < threshold."""
        mock_disk.return_value = {'percent': 50, 'total': 100, 'free': 50}

        result = MonitorTool.check_disk(threshold=90)

        assert result['alert'] is False
        assert result['percent'] == 50
        assert result['threshold'] == 90

    @patch('client.tools.SystemInfo.disk_usage')
    def test_check_disk_alert_at_threshold(self, mock_disk):
        """check_disk alert=True when percent >= threshold."""
        mock_disk.return_value = {'percent': 90, 'total': 100, 'free': 10}

        result = MonitorTool.check_disk(threshold=90)

        assert result['alert'] is True

    @patch('client.tools.SystemInfo.memory')
    def test_check_memory_zero_total_returns_zero_percent(self, mock_mem):
        """check_memory with total=0 returns percent=0 (no division by zero)."""
        mock_mem.return_value = {}

        result = MonitorTool.check_memory(threshold=90)

        assert result['percent'] == 0
        assert result['alert'] is False

    @patch('client.tools.SystemInfo.memory')
    def test_check_memory_with_memtotal_only(self, mock_mem):
        """check_memory falls back to MemFree when MemAvailable missing."""
        mock_mem.return_value = {
            'MemTotal': '1000000 kB',
            'MemFree': '300000 kB'
        }

        result = MonitorTool.check_memory(threshold=90)

        assert result['percent'] > 0
        assert result['total_mb'] == pytest.approx(976.56, rel=0.01)
        assert result['free_mb'] == pytest.approx(292.97, rel=0.01)

    @patch('client.tools.SystemInfo.memory')
    def test_check_memory_alert_above_threshold(self, mock_mem):
        """check_memory alert=True when percent >= threshold."""
        mock_mem.return_value = {
            'MemTotal': '1000000 kB',
            'MemAvailable': '50000 kB'
        }
        # used = 1000000 - 50000 = 950000, percent = 95.0

        result = MonitorTool.check_memory(threshold=90)

        assert result['alert'] is True
        assert result['percent'] == 95.0

    @patch('client.tools.SystemInfo.cpu_load')
    def test_check_cpu_below_threshold(self, mock_cpu):
        """check_cpu alert=False when load < threshold."""
        mock_cpu.return_value = {'1min': 2.0, '5min': 1.5, '15min': 1.0}

        result = MonitorTool.check_cpu(threshold=80.0)

        assert result['alert'] is False
        assert result['load_1min'] == 2.0
        assert result['load_5min'] == 1.5

    @patch('client.tools.SystemInfo.cpu_load')
    def test_check_cpu_at_threshold(self, mock_cpu):
        """check_cpu alert=True when load >= threshold."""
        mock_cpu.return_value = {'1min': 80.0, '5min': 50.0, '15min': 30.0}

        result = MonitorTool.check_cpu(threshold=80.0)

        assert result['alert'] is True

    @patch('socket.socket')
    def test_check_port_socket_exception(self, mock_socket_cls):
        """check_port returns port_open=False with error on socket exception."""
        mock_sock = MagicMock()
        mock_sock.connect_ex.side_effect = socket.gaierror("Name resolution failed")
        mock_socket_cls.return_value = mock_sock

        result = MonitorTool.check_port(80, host="invalidhost")

        assert result['port_open'] is False
        assert result['error'] == "Name resolution failed"

    @patch('client.tools.requests.get')
    def test_check_url_exception_returns_unreachable(self, mock_get):
        """check_url returns reachable=False with error on exception."""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        result = MonitorTool.check_url("http://example.com")

        assert result['reachable'] is False
        assert result['url'] == "http://example.com"
        assert 'error' in result

    @patch('client.tools.requests.get')
    def test_check_url_connection_error(self, mock_get):
        """check_url handles connection errors gracefully."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        result = MonitorTool.check_url("http://192.168.255.255")

        assert result['reachable'] is False
        assert 'error' in result

    @patch('client.tools.requests.get')
    def test_check_url_success_returns_status_and_time(self, mock_get):
        """check_url success includes status_code and response_time_ms."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.elapsed.total_seconds.return_value = 0.150
        mock_get.return_value = mock_resp

        result = MonitorTool.check_url("http://example.com")

        assert result['reachable'] is True
        assert result['status'] == 200
        assert result['response_time_ms'] == 150
    """Test ImageTool info/resize/thumbnail/convert/compress."""

    @patch('client.tools.os.path.getsize')
    @patch('PIL.Image')
    def test_info_success(self, mock_image, mock_getsize):
        """info() returns image metadata."""
        mock_getsize.return_value = 1024
        mock_img = MagicMock()
        mock_img.width = 800
        mock_img.height = 600
        mock_img.format = 'PNG'
        mock_img.mode = 'RGB'
        mock_image.open.return_value = mock_img

        result = ImageTool.info('/fake/image.png')

        assert result['width'] == 800
        assert result['height'] == 600
        assert result['format'] == 'PNG'
        assert result['mode'] == 'RGB'

    @patch('PIL.Image')
    def test_info_exception(self, mock_image):
        """info() when PIL fails returns error dict."""
        mock_image.open.side_effect = Exception("Cannot identify image")

        result = ImageTool.info('/fake/bad.png')

        assert 'error' in result

    @patch('PIL.Image')
    def test_resize_success(self, mock_image):
        """resize() returns True on success."""
        mock_img = MagicMock()
        mock_resized = MagicMock()
        mock_img.resize.return_value = mock_resized
        mock_image.open.return_value = mock_img

        result = ImageTool.resize('/fake/in.png', '/fake/out.png', 100, 200)

        assert result is True

    @patch('PIL.Image')
    def test_resize_exception(self, mock_image):
        """resize() when PIL fails returns False."""
        mock_image.open.side_effect = Exception("read error")

        result = ImageTool.resize('/fake/in.png', '/fake/out.png', 100, 200)

        assert result is False

    @patch('PIL.Image')
    def test_thumbnail_success(self, mock_image):
        """thumbnail() returns True on success."""
        mock_img = MagicMock()
        mock_image.open.return_value = mock_img

        result = ImageTool.thumbnail('/fake/in.png', '/fake/out.png', 256)

        assert result is True

    @patch('PIL.Image')
    def test_thumbnail_exception(self, mock_image):
        """thumbnail() when PIL fails returns False."""
        mock_image.open.side_effect = Exception("corrupt image")

        result = ImageTool.thumbnail('/fake/in.png', '/fake/out.png', 256)

        assert result is False

    @patch('PIL.Image')
    def test_convert_success(self, mock_image):
        """convert() returns True on success."""
        mock_img = MagicMock()
        mock_img.mode = 'RGB'
        mock_image.open.return_value = mock_img

        result = ImageTool.convert('/fake/in.png', '/fake/out.jpg', 'JPEG')

        assert result is True

    @patch('PIL.Image')
    def test_convert_with_rgba(self, mock_image):
        """convert() with RGBA mode converts to RGB before saving."""
        mock_img = MagicMock()
        mock_img.mode = 'RGBA'
        mock_img.convert.return_value = mock_img
        mock_image.open.return_value = mock_img

        result = ImageTool.convert('/fake/in.png', '/fake/out.jpg', 'JPEG')

        assert result is True
        mock_img.convert.assert_called_once_with('RGB')

    @patch('PIL.Image')
    def test_convert_exception(self, mock_image):
        """convert() when PIL fails returns False."""
        mock_image.open.side_effect = Exception("save error")

        result = ImageTool.convert('/fake/in.png', '/fake/out.jpg', 'JPEG')

        assert result is False

    @patch('PIL.Image')
    def test_compress_success(self, mock_image):
        """compress() returns True on success."""
        mock_img = MagicMock()
        mock_img.mode = 'RGB'
        mock_image.open.return_value = mock_img

        result = ImageTool.compress('/fake/in.jpg', '/fake/out.jpg', 85)

        assert result is True

    @patch('PIL.Image')
    def test_compress_with_rgba(self, mock_image):
        """compress() with RGBA mode converts to RGB."""
        mock_img = MagicMock()
        mock_img.mode = 'RGBA'
        mock_img.convert.return_value = mock_img
        mock_image.open.return_value = mock_img

        result = ImageTool.compress('/fake/in.jpg', '/fake/out.jpg', 85)

        assert result is True
        mock_img.convert.assert_called_with('RGB')

    @patch('PIL.Image')
    def test_compress_exception(self, mock_image):
        """compress() when PIL fails returns False."""
        mock_image.open.side_effect = Exception("compress error")

        result = ImageTool.compress('/fake/in.jpg', '/fake/out.jpg', 85)

        assert result is False
