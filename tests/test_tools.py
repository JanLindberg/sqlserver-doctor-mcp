"""Tests for MCP server tools."""

import pytest
from unittest.mock import patch, MagicMock
from sqlserver_doctor.server import (
    get_server_version,
    list_databases,
    get_active_sessions,
    ServerVersionResponse,
    DatabaseListResponse,
    ActiveSessionsResponse,
)


class TestGetServerVersion:
    """Tests for get_server_version tool."""

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_server_version_success(self, mock_get_connection):
        """Test successful server version retrieval."""
        # Setup mock
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "Version": "Microsoft SQL Server 2019 (RTM) - 15.0.2000.5",
                "ServerName": "TESTSERVER",
            }
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = get_server_version()

        # Verify
        assert isinstance(result, ServerVersionResponse)
        assert result.success is True
        assert result.server_name == "TESTSERVER"
        assert "SQL Server 2019" in result.version
        assert result.error is None

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_server_version_no_results(self, mock_get_connection):
        """Test server version with no results."""
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = []
        mock_get_connection.return_value = mock_conn

        result = get_server_version()

        assert isinstance(result, ServerVersionResponse)
        assert result.success is False
        assert result.version == ""
        assert result.server_name == ""
        assert "No results returned" in result.error

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_server_version_error(self, mock_get_connection):
        """Test server version with database error."""
        mock_conn = MagicMock()
        mock_conn.execute_query.side_effect = Exception("Connection timeout")
        mock_get_connection.return_value = mock_conn

        result = get_server_version()

        assert isinstance(result, ServerVersionResponse)
        assert result.success is False
        assert "Connection timeout" in result.error


class TestListDatabases:
    """Tests for list_databases tool."""

    @patch("sqlserver_doctor.server.get_connection")
    def test_list_databases_success(self, mock_get_connection):
        """Test successful database listing."""
        # Setup mock
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "name": "master",
                "database_id": 1,
                "create_date": "2021-01-01 00:00:00",
                "state_desc": "ONLINE",
                "recovery_model_desc": "SIMPLE",
                "compatibility_level": 150,
            },
            {
                "name": "tempdb",
                "database_id": 2,
                "create_date": "2021-01-01 00:00:00",
                "state_desc": "ONLINE",
                "recovery_model_desc": "SIMPLE",
                "compatibility_level": 150,
            },
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = list_databases()

        # Verify
        assert isinstance(result, DatabaseListResponse)
        assert result.success is True
        assert result.count == 2
        assert len(result.databases) == 2
        assert result.databases[0].name == "master"
        assert result.databases[1].name == "tempdb"
        assert result.error is None

    @patch("sqlserver_doctor.server.get_connection")
    def test_list_databases_empty(self, mock_get_connection):
        """Test database listing with no databases."""
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = []
        mock_get_connection.return_value = mock_conn

        result = list_databases()

        assert isinstance(result, DatabaseListResponse)
        assert result.success is True
        assert result.count == 0
        assert len(result.databases) == 0

    @patch("sqlserver_doctor.server.get_connection")
    def test_list_databases_error(self, mock_get_connection):
        """Test database listing with error."""
        mock_conn = MagicMock()
        mock_conn.execute_query.side_effect = Exception("Permission denied")
        mock_get_connection.return_value = mock_conn

        result = list_databases()

        assert isinstance(result, DatabaseListResponse)
        assert result.success is False
        assert result.count == 0
        assert len(result.databases) == 0
        assert "Permission denied" in result.error

    @patch("sqlserver_doctor.server.get_connection")
    def test_list_databases_validates_data(self, mock_get_connection):
        """Test that database info is properly validated."""
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "name": "testdb",
                "database_id": 5,
                "create_date": "2024-01-01 12:00:00",
                "state_desc": "ONLINE",
                "recovery_model_desc": "FULL",
                "compatibility_level": 160,
            }
        ]
        mock_get_connection.return_value = mock_conn

        result = list_databases()

        assert result.success is True
        db = result.databases[0]
        assert db.name == "testdb"
        assert db.database_id == 5
        assert db.state_desc == "ONLINE"
        assert db.recovery_model_desc == "FULL"
        assert db.compatibility_level == 160


class TestGetActiveSessions:
    """Tests for get_active_sessions tool."""

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_active_sessions_success(self, mock_get_connection):
        """Test successful active sessions retrieval."""
        # Setup mock
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "sql_text": "SELECT * FROM users WHERE id = 123",
                "session_id": 52,
                "status": "running",
                "command": "SELECT",
                "cpu_seconds": 1.5,
                "elapsed_seconds": 2.3,
                "reads": 100,
                "logical_reads": 500,
                "wait_time": 0,
                "last_wait_type": None,
                "blocking_session_id": None,
                "connect_time": "2025-10-14 10:30:00",
                "dop": 1,
                "host_name": "WORKSTATION01",
                "program_name": "My Application",
                "database_name": "MyDatabase",
                "login_name": "myuser",
            },
            {
                "sql_text": "UPDATE orders SET status = 'processed'",
                "session_id": 53,
                "status": "suspended",
                "command": "UPDATE",
                "cpu_seconds": 0.5,
                "elapsed_seconds": 10.2,
                "reads": 50,
                "logical_reads": 200,
                "wait_time": 5000,
                "last_wait_type": "LCK_M_X",
                "blocking_session_id": 52,
                "connect_time": "2025-10-14 10:32:00",
                "dop": 1,
                "host_name": "WORKSTATION02",
                "program_name": "Batch Processor",
                "database_name": "MyDatabase",
                "login_name": "batchuser",
            },
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = get_active_sessions()

        # Verify
        assert isinstance(result, ActiveSessionsResponse)
        assert result.success is True
        assert result.count == 2
        assert len(result.sessions) == 2
        assert result.error is None

        # Check first session
        session1 = result.sessions[0]
        assert session1.session_id == 52
        assert session1.status == "running"
        assert session1.cpu_seconds == 1.5
        assert session1.blocking_session_id is None

        # Check second session (blocked)
        session2 = result.sessions[1]
        assert session2.session_id == 53
        assert session2.status == "suspended"
        assert session2.blocking_session_id == 52
        assert session2.last_wait_type == "LCK_M_X"

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_active_sessions_empty(self, mock_get_connection):
        """Test active sessions with no active queries."""
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = []
        mock_get_connection.return_value = mock_conn

        result = get_active_sessions()

        assert isinstance(result, ActiveSessionsResponse)
        assert result.success is True
        assert result.count == 0
        assert len(result.sessions) == 0

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_active_sessions_error(self, mock_get_connection):
        """Test active sessions with database error."""
        mock_conn = MagicMock()
        mock_conn.execute_query.side_effect = Exception("Insufficient permissions")
        mock_get_connection.return_value = mock_conn

        result = get_active_sessions()

        assert isinstance(result, ActiveSessionsResponse)
        assert result.success is False
        assert result.count == 0
        assert len(result.sessions) == 0
        assert "Insufficient permissions" in result.error
