"""Tests for SQL Server connection utilities."""

import json
import os
import tempfile

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlserver_doctor.utils.connection import (
    SQLServerConnection,
    get_connection,
    load_connections_from_json,
    set_active_connection_name,
    get_all_connections,
    get_active_connection_name,
    _connections,
    _active_connection_name,
)
import sqlserver_doctor.utils.connection as conn_module


def _reset_connection_registry():
    """Reset the connection registry to a clean state."""
    conn_module._connections.clear()
    conn_module._active_connection_name = None


class TestSQLServerConnection:
    """Tests for SQLServerConnection class."""

    def test_init_default_values(self):
        """Test connection initialization with default values."""
        with patch.dict(os.environ, {}, clear=True):
            conn = SQLServerConnection()
            assert conn.host == "localhost"
            assert conn.port == "1433"
            assert conn.database == "master"
            assert conn.driver == "ODBC Driver 17 for SQL Server"
            assert conn.name == "default"

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

    def test_init_with_explicit_params(self):
        """Test connection initialization with explicit parameters."""
        conn = SQLServerConnection(
            name="myconn",
            host="explicit-host",
            port=1435,
            database="mydb",
            user="myuser",
            password="mypass",
        )
        assert conn.name == "myconn"
        assert conn.host == "explicit-host"
        assert conn.port == "1435"
        assert conn.database == "mydb"
        assert conn.user == "myuser"
        assert conn.password == "mypass"

    def test_init_explicit_params_override_env(self):
        """Test that explicit params take priority over env vars."""
        env_vars = {"SQL_SERVER_HOST": "env-host"}
        with patch.dict(os.environ, env_vars):
            conn = SQLServerConnection(host="explicit-host")
            assert conn.host == "explicit-host"

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
        mock_cursor.nextset.return_value = False
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
        mock_cursor.nextset.return_value = False
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

    def setup_method(self):
        """Reset connection registry before each test."""
        _reset_connection_registry()

    def test_get_connection_creates_default_from_env(self):
        """Test that get_connection creates a default instance from env vars."""
        with patch.dict(os.environ, {}, clear=True):
            conn = get_connection()
            assert conn is not None
            assert isinstance(conn, SQLServerConnection)
            assert conn.name == "default"

    def test_get_connection_returns_same_instance(self):
        """Test that get_connection returns the same instance."""
        with patch.dict(os.environ, {}, clear=True):
            conn1 = get_connection()
            conn2 = get_connection()
            assert conn1 is conn2

    def test_get_connection_by_name(self):
        """Test getting a connection by name."""
        conn_module._connections["myconn"] = SQLServerConnection(name="myconn", host="myhost")
        conn_module._active_connection_name = "myconn"

        result = get_connection("myconn")
        assert result.name == "myconn"
        assert result.host == "myhost"

    def test_get_connection_by_name_not_found(self):
        """Test getting a connection by name that doesn't exist."""
        with pytest.raises(ValueError, match="not found"):
            get_connection("nonexistent")

    def test_get_connection_uses_active(self):
        """Test that get_connection uses the active connection when no name given."""
        conn_module._connections["conn1"] = SQLServerConnection(name="conn1", host="host1")
        conn_module._connections["conn2"] = SQLServerConnection(name="conn2", host="host2")
        conn_module._active_connection_name = "conn2"

        result = get_connection()
        assert result.name == "conn2"
        assert result.host == "host2"


class TestLoadConnectionsFromJson:
    """Tests for loading connections from JSON config."""

    def setup_method(self):
        """Reset connection registry before each test."""
        _reset_connection_registry()

    def test_load_valid_json(self):
        """Test loading valid connections JSON."""
        config = {
            "default": "prod",
            "connections": {
                "prod": {
                    "host": "prod-server",
                    "port": 1433,
                    "database": "master",
                },
                "staging": {
                    "host": "staging-server",
                    "port": 1434,
                    "database": "testdb",
                    "user": "sa",
                    "password": "pass123",
                },
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            tmp_path = f.name

        try:
            load_connections_from_json(tmp_path)

            all_conns = get_all_connections()
            assert len(all_conns) == 2
            assert "prod" in all_conns
            assert "staging" in all_conns
            assert all_conns["prod"].host == "prod-server"
            assert all_conns["staging"].host == "staging-server"
            assert all_conns["staging"].user == "sa"
            assert get_active_connection_name() == "prod"
        finally:
            os.unlink(tmp_path)

    def test_load_missing_file(self):
        """Test loading from a missing file silently skips."""
        load_connections_from_json("/nonexistent/path/connections.json")
        assert len(get_all_connections()) == 0

    def test_load_malformed_json(self):
        """Test loading malformed JSON logs error and skips."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ not valid json")
            f.flush()
            tmp_path = f.name

        try:
            load_connections_from_json(tmp_path)
            assert len(get_all_connections()) == 0
        finally:
            os.unlink(tmp_path)

    def test_load_invalid_default(self):
        """Test loading JSON with invalid default connection name."""
        config = {
            "default": "nonexistent",
            "connections": {
                "prod": {"host": "prod-server"},
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            tmp_path = f.name

        try:
            load_connections_from_json(tmp_path)
            assert len(get_all_connections()) == 1
            # Active should not be set since default doesn't exist
            assert get_active_connection_name() is None
        finally:
            os.unlink(tmp_path)

    def test_load_no_default_field(self):
        """Test loading JSON without a default field."""
        config = {
            "connections": {
                "prod": {"host": "prod-server"},
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            tmp_path = f.name

        try:
            load_connections_from_json(tmp_path)
            assert len(get_all_connections()) == 1
            assert get_active_connection_name() is None
        finally:
            os.unlink(tmp_path)


class TestSetActiveConnectionName:
    """Tests for set_active_connection_name function."""

    def setup_method(self):
        """Reset connection registry before each test."""
        _reset_connection_registry()

    def test_set_valid_connection(self):
        """Test setting a valid connection as active."""
        conn_module._connections["myconn"] = SQLServerConnection(name="myconn", host="myhost")

        set_active_connection_name("myconn")
        assert get_active_connection_name() == "myconn"

    def test_set_invalid_connection(self):
        """Test setting an invalid connection name raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            set_active_connection_name("nonexistent")
