"""Tests for SQL Server connection utilities."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlserver_doctor.utils.connection import SQLServerConnection, get_connection


class TestSQLServerConnection:
    """Tests for SQLServerConnection class."""

    def test_init_default_values(self):
        """Test connection initialization with default values."""
        with patch.dict(os.environ, {}, clear=True):
            conn = SQLServerConnection()
            assert conn.host == "localhost"
            assert conn.port == "1433"
            assert conn.database == "master"
            assert conn.driver == "ODBC Driver 18 for SQL Server"

    def test_init_from_env_variables(self):
        """Test connection initialization from environment variables."""
        env_vars = {
            "SQL_SERVER_HOST": "test-server",
            "SQL_SERVER_PORT": "1434",
            "SQL_SERVER_DATABASE": "testdb",
            "SQL_SERVER_USER": "testuser",
            "SQL_SERVER_PASSWORD": "testpass",
        }
        with patch.dict(os.environ, env_vars):
            conn = SQLServerConnection()
            assert conn.host == "test-server"
            assert conn.port == "1434"
            assert conn.database == "testdb"
            assert conn.user == "testuser"
            assert conn.password == "testpass"

    def test_connection_string_windows_auth(self):
        """Test connection string with Windows Authentication."""
        with patch.dict(os.environ, {}, clear=True):
            conn = SQLServerConnection()
            conn_str = conn.get_connection_string()
            assert "Trusted_Connection=yes" in conn_str
            assert "UID=" not in conn_str
            assert "PWD=" not in conn_str

    def test_connection_string_sql_auth(self):
        """Test connection string with SQL Server Authentication."""
        env_vars = {
            "SQL_SERVER_USER": "testuser",
            "SQL_SERVER_PASSWORD": "testpass",
        }
        with patch.dict(os.environ, env_vars):
            conn = SQLServerConnection()
            conn_str = conn.get_connection_string()
            assert "UID=testuser" in conn_str
            assert "PWD=testpass" in conn_str
            assert "Trusted_Connection=yes" not in conn_str

    @patch("sqlserver_doctor.utils.connection.pyodbc.connect")
    def test_execute_query_success(self, mock_connect):
        """Test successful query execution."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.description = [("col1",), ("col2",)]
        mock_cursor.fetchall.return_value = [("val1", "val2")]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_connect.return_value = mock_conn

        # Execute
        with patch.dict(os.environ, {}, clear=True):
            conn = SQLServerConnection()
            results = conn.execute_query("SELECT col1, col2 FROM test")

        # Verify
        assert len(results) == 1
        assert results[0] == {"col1": "val1", "col2": "val2"}
        mock_cursor.execute.assert_called_once_with("SELECT col1, col2 FROM test")

    @patch("sqlserver_doctor.utils.connection.pyodbc.connect")
    def test_execute_query_error(self, mock_connect):
        """Test query execution with database error."""
        mock_connect.side_effect = Exception("Connection failed")

        with patch.dict(os.environ, {}, clear=True):
            conn = SQLServerConnection()
            with pytest.raises(Exception, match="Connection failed"):
                conn.execute_query("SELECT 1")

    @patch("sqlserver_doctor.utils.connection.pyodbc.connect")
    def test_test_connection_success(self, mock_connect):
        """Test successful connection test."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.description = [("Version",), ("ServerName",)]
        mock_cursor.fetchall.return_value = [("SQL Server 2019", "TESTSERVER")]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_connect.return_value = mock_conn

        # Execute
        with patch.dict(os.environ, {}, clear=True):
            conn = SQLServerConnection()
            result = conn.test_connection()

        # Verify
        assert result["success"] is True
        assert "Connection successful" in result["message"]
        assert result["server_info"]["ServerName"] == "TESTSERVER"

    @patch("sqlserver_doctor.utils.connection.pyodbc.connect")
    def test_test_connection_failure(self, mock_connect):
        """Test failed connection test."""
        mock_connect.side_effect = Exception("Network error")

        with patch.dict(os.environ, {}, clear=True):
            conn = SQLServerConnection()
            result = conn.test_connection()

        assert result["success"] is False
        assert "Connection failed" in result["message"]


class TestGetConnection:
    """Tests for get_connection function."""

    def test_get_connection_creates_instance(self):
        """Test that get_connection creates a new instance."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear the global connection
            import sqlserver_doctor.utils.connection as conn_module

            conn_module._connection = None

            conn1 = get_connection()
            assert conn1 is not None
            assert isinstance(conn1, SQLServerConnection)

    def test_get_connection_returns_same_instance(self):
        """Test that get_connection returns the same instance."""
        with patch.dict(os.environ, {}, clear=True):
            conn1 = get_connection()
            conn2 = get_connection()
            assert conn1 is conn2
