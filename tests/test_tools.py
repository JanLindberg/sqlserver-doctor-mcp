"""Tests for MCP server tools."""

import pytest
from unittest.mock import patch, MagicMock
from sqlserver_doctor.server import get_server_version, list_databases, ServerVersionResponse, DatabaseListResponse


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
