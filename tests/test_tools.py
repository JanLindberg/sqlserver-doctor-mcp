"""Tests for MCP server tools."""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock
from sqlserver_doctor.utils.connection import get_connection
from sqlserver_doctor.server import (
    get_server_version,
    list_databases,
    get_active_sessions,
    get_scheduler_stats,
    get_server_configurations,
    get_memory_stats,
    execute_select_query,
    _validate_select_query,
    _serialize_value,
    ServerVersionResponse,
    DatabaseListResponse,
    ActiveSessionsResponse,
    SchedulerStatsResponse,
    ServerConfigResponse,
    MemoryStatsResponse,
    ExecuteSelectQueryResponse,
    ConfigSeverity,
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


class TestGetSchedulerStats:
    """Tests for get_scheduler_stats tool."""

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_scheduler_stats_no_pressure(self, mock_get_connection):
        """Test scheduler stats with no CPU pressure."""
        # Setup mock - 4 CPU cores, no runnable tasks (aggregated format)
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "scheduler_count": 4,
                "avg_runnable_tasks": 0.0,
                "avg_pending_disk_io_count": 0.0,
            }
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = get_scheduler_stats()

        # Verify
        assert isinstance(result, SchedulerStatsResponse)
        assert result.success is True
        assert result.scheduler_count == 4
        assert result.total_runnable_tasks == 0
        assert result.avg_runnable_per_scheduler == 0.0
        assert result.cpu_pressure_detected is False
        assert "No CPU pressure" in result.interpretation
        assert result.error is None

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_scheduler_stats_with_pressure(self, mock_get_connection):
        """Test scheduler stats with CPU pressure detected."""
        # Setup mock - CPU pressure (aggregated format)
        # avg_runnable = (0 + 2 + 3 + 0) / 4 = 1.25
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "scheduler_count": 4,
                "avg_runnable_tasks": 1.25,
                "avg_pending_disk_io_count": 0.25,
            }
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = get_scheduler_stats()

        # Verify
        assert isinstance(result, SchedulerStatsResponse)
        assert result.success is True
        assert result.scheduler_count == 4
        assert result.total_runnable_tasks == 5  # 1.25 * 4 = 5
        assert result.avg_runnable_per_scheduler == 1.25
        assert result.cpu_pressure_detected is True
        assert "MILD CPU PRESSURE" in result.interpretation
        assert result.error is None

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_scheduler_stats_error(self, mock_get_connection):
        """Test scheduler stats with database error."""
        mock_conn = MagicMock()
        mock_conn.execute_query.side_effect = Exception("Access denied")
        mock_get_connection.return_value = mock_conn

        result = get_scheduler_stats()

        assert isinstance(result, SchedulerStatsResponse)
        assert result.success is False
        assert result.scheduler_count == 0
        assert result.total_runnable_tasks == 0
        assert result.cpu_pressure_detected is False
        assert "Access denied" in result.error


class TestGetServerConfigurations:
    """Tests for get_server_configurations tool."""

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_server_configurations_success(self, mock_get_connection):
        """Test successful server configurations retrieval."""
        # Setup mock with all three configurations
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "name": "cost threshold for parallelism",
                "value": 50,
                "severity": "OK",
                "message": "Good starting point [Current: 50]",
                "recommendation": None,
            },
            {
                "name": "max degree of parallelism",
                "value": 4,
                "severity": "OK",
                "message": "Set to physical CPU count [Current: 4, Physical CPUs: 4]",
                "recommendation": None,
            },
            {
                "name": "max server memory (MB)",
                "value": 16384,
                "severity": "OK",
                "message": "Configured appropriately [Configured: 16384 MB]",
                "recommendation": None,
            },
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = get_server_configurations()

        # Verify
        assert isinstance(result, ServerConfigResponse)
        assert result.success is True
        assert len(result.configurations) == 3
        assert result.error is None

        # Check that all configs are OK
        for config in result.configurations:
            assert config.severity == ConfigSeverity.OK
            assert config.recommendation is None

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_server_configurations_with_warnings(self, mock_get_connection):
        """Test server configurations with warnings and recommendations."""
        # Setup mock with configurations that need attention
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "name": "cost threshold for parallelism",
                "value": 5,
                "severity": "WARNING",
                "message": "Default value too low for modern servers [Current: 5]",
                "recommendation": "Recommend setting to 50: EXEC sp_configure 'cost threshold for parallelism', 50; RECONFIGURE;",
            },
            {
                "name": "max degree of parallelism",
                "value": 0,
                "severity": "WARNING",
                "message": "Unlimited parallelism can cause CXPACKET waits [CPUs: 8, Physical: 4]",
                "recommendation": "Recommend setting to: 4 (physical CPU count, max 8)",
            },
            {
                "name": "max server memory (MB)",
                "value": 2147483647,
                "severity": "CRITICAL",
                "message": "Unlimited (default) - should be set! [Server Memory: 32768 MB, Edition: Enterprise Edition]",
                "recommendation": "Set max memory to: 28672 MB",
            },
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = get_server_configurations()

        # Verify
        assert isinstance(result, ServerConfigResponse)
        assert result.success is True
        assert len(result.configurations) == 3

        # Check cost threshold
        cost_threshold = result.configurations[0]
        assert cost_threshold.name == "cost threshold for parallelism"
        assert cost_threshold.value == 5
        assert cost_threshold.severity == ConfigSeverity.WARNING
        assert "Default value too low" in cost_threshold.message
        assert cost_threshold.recommendation is not None

        # Check MAXDOP
        maxdop = result.configurations[1]
        assert maxdop.name == "max degree of parallelism"
        assert maxdop.value == 0
        assert maxdop.severity == ConfigSeverity.WARNING
        assert "Unlimited parallelism" in maxdop.message
        assert maxdop.recommendation is not None

        # Check max memory
        max_memory = result.configurations[2]
        assert max_memory.name == "max server memory (MB)"
        assert max_memory.value == 2147483647
        assert max_memory.severity == ConfigSeverity.CRITICAL
        assert "Unlimited" in max_memory.message
        assert max_memory.recommendation is not None

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_server_configurations_mixed_severities(self, mock_get_connection):
        """Test server configurations with different severity levels."""
        # Setup mock with REVIEW and CONSIDER severities
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "name": "cost threshold for parallelism",
                "value": 20,
                "severity": "CONSIDER",
                "message": "Consider increasing to 25-50 to reduce excessive parallelism [Current: 20]",
                "recommendation": None,
            },
            {
                "name": "max degree of parallelism",
                "value": 6,
                "severity": "REVIEW",
                "message": "Check if optimal for workload [Current: 6, CPUs: 8, Physical: 4]",
                "recommendation": None,
            },
            {
                "name": "max server memory (MB)",
                "value": 16384,
                "severity": "OK",
                "message": "Configured appropriately [Configured: 16384 MB]",
                "recommendation": None,
            },
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = get_server_configurations()

        # Verify different severities
        assert result.success is True
        assert result.configurations[0].severity == ConfigSeverity.CONSIDER
        assert result.configurations[1].severity == ConfigSeverity.REVIEW
        assert result.configurations[2].severity == ConfigSeverity.OK

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_server_configurations_error(self, mock_get_connection):
        """Test server configurations with database error."""
        mock_conn = MagicMock()
        mock_conn.execute_query.side_effect = Exception("Insufficient permissions")
        mock_get_connection.return_value = mock_conn

        result = get_server_configurations()

        assert isinstance(result, ServerConfigResponse)
        assert result.success is False
        assert len(result.configurations) == 0
        assert "Insufficient permissions" in result.error

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_server_configurations_empty_results(self, mock_get_connection):
        """Test server configurations with empty results."""
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = []
        mock_get_connection.return_value = mock_conn

        result = get_server_configurations()

        assert isinstance(result, ServerConfigResponse)
        assert result.success is True
        assert len(result.configurations) == 0
        assert result.error is None


class TestGetMemoryStats:
    """Tests for get_memory_stats tool."""

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_memory_stats_healthy(self, mock_get_connection):
        """Test memory stats with healthy memory."""
        # Setup mock - healthy memory state
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "server_name": "TESTSERVER",
                "check_timestamp": "2025-10-25 14:30:00",
                "ple_seconds": 5000,
                "ple_minutes": 83,
                "ple_status": "OK",
                "memory_grants_pending": 0,
                "grants_status": "OK",
                "target_memory_mb": 16384,
                "total_memory_mb": 16384,
                "memory_difference_mb": 0,
                "memory_pressure_status": "OK",
                "max_server_memory_mb": 16384,
                "buffer_pool_committed_mb": 15000,
                "buffer_pool_target_mb": 16000,
                "overall_assessment": "OK: Memory appears healthy",
            }
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = get_memory_stats()

        # Verify
        assert isinstance(result, MemoryStatsResponse)
        assert result.success is True
        assert result.error is None
        assert result.memory_stats is not None

        stats = result.memory_stats
        assert stats.server_name == "TESTSERVER"
        assert stats.ple_seconds == 5000
        assert stats.ple_status == "OK"
        assert stats.memory_grants_pending == 0
        assert stats.grants_status == "OK"
        assert stats.memory_pressure_status == "OK"
        assert "healthy" in stats.overall_assessment

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_memory_stats_low_ple(self, mock_get_connection):
        """Test memory stats with low Page Life Expectancy."""
        # Setup mock - low PLE warning
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "server_name": "TESTSERVER",
                "check_timestamp": "2025-10-25 14:30:00",
                "ple_seconds": 250,
                "ple_minutes": 4,
                "ple_status": "CRITICAL",
                "memory_grants_pending": 0,
                "grants_status": "OK",
                "target_memory_mb": 16384,
                "total_memory_mb": 16384,
                "memory_difference_mb": 0,
                "memory_pressure_status": "OK",
                "max_server_memory_mb": 16384,
                "buffer_pool_committed_mb": 15000,
                "buffer_pool_target_mb": 16000,
                "overall_assessment": "WARNING: Low Page Life Expectancy",
            }
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = get_memory_stats()

        # Verify
        assert result.success is True
        stats = result.memory_stats
        assert stats.ple_seconds == 250
        assert stats.ple_status == "CRITICAL"
        assert "Low Page Life Expectancy" in stats.overall_assessment

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_memory_stats_memory_pressure(self, mock_get_connection):
        """Test memory stats with memory pressure detected."""
        # Setup mock - SQL Server wants more memory
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "server_name": "TESTSERVER",
                "check_timestamp": "2025-10-25 14:30:00",
                "ple_seconds": 1500,
                "ple_minutes": 25,
                "ple_status": "OK",
                "memory_grants_pending": 0,
                "grants_status": "OK",
                "target_memory_mb": 18432,
                "total_memory_mb": 16384,
                "memory_difference_mb": 2048,
                "memory_pressure_status": "UNDER_PRESSURE",
                "max_server_memory_mb": 16384,
                "buffer_pool_committed_mb": 15000,
                "buffer_pool_target_mb": 16000,
                "overall_assessment": "WARNING: SQL Server wants more memory",
            }
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = get_memory_stats()

        # Verify
        assert result.success is True
        stats = result.memory_stats
        assert stats.memory_difference_mb == 2048
        assert stats.memory_pressure_status == "UNDER_PRESSURE"
        assert "wants more memory" in stats.overall_assessment

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_memory_stats_grants_pending(self, mock_get_connection):
        """Test memory stats with memory grants pending (critical)."""
        # Setup mock - queries waiting for memory
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "server_name": "TESTSERVER",
                "check_timestamp": "2025-10-25 14:30:00",
                "ple_seconds": 800,
                "ple_minutes": 13,
                "ple_status": "WARNING",
                "memory_grants_pending": 3,
                "grants_status": "CRITICAL",
                "target_memory_mb": 16384,
                "total_memory_mb": 16384,
                "memory_difference_mb": 0,
                "memory_pressure_status": "OK",
                "max_server_memory_mb": 16384,
                "buffer_pool_committed_mb": 15000,
                "buffer_pool_target_mb": 16000,
                "overall_assessment": "CRITICAL: Queries waiting for memory!",
            }
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = get_memory_stats()

        # Verify
        assert result.success is True
        stats = result.memory_stats
        assert stats.memory_grants_pending == 3
        assert stats.grants_status == "CRITICAL"
        assert "CRITICAL" in stats.overall_assessment
        assert "waiting for memory" in stats.overall_assessment

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_memory_stats_critical_combined(self, mock_get_connection):
        """Test memory stats with both low PLE and memory pressure."""
        # Setup mock - critical state with multiple issues
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = [
            {
                "server_name": "TESTSERVER",
                "check_timestamp": "2025-10-25 14:30:00",
                "ple_seconds": 200,
                "ple_minutes": 3,
                "ple_status": "CRITICAL",
                "memory_grants_pending": 0,
                "grants_status": "OK",
                "target_memory_mb": 18432,
                "total_memory_mb": 16384,
                "memory_difference_mb": 2048,
                "memory_pressure_status": "UNDER_PRESSURE",
                "max_server_memory_mb": 16384,
                "buffer_pool_committed_mb": 15000,
                "buffer_pool_target_mb": 16000,
                "overall_assessment": "CRITICAL: Low PLE and memory pressure detected",
            }
        ]
        mock_get_connection.return_value = mock_conn

        # Execute
        result = get_memory_stats()

        # Verify
        assert result.success is True
        stats = result.memory_stats
        assert stats.ple_status == "CRITICAL"
        assert stats.memory_pressure_status == "UNDER_PRESSURE"
        assert "CRITICAL" in stats.overall_assessment
        assert "Low PLE and memory pressure" in stats.overall_assessment

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_memory_stats_no_results(self, mock_get_connection):
        """Test memory stats with no results returned."""
        mock_conn = MagicMock()
        mock_conn.execute_query.return_value = []
        mock_get_connection.return_value = mock_conn

        result = get_memory_stats()

        assert isinstance(result, MemoryStatsResponse)
        assert result.success is False
        assert result.memory_stats is None
        assert "No results returned" in result.error

    @patch("sqlserver_doctor.server.get_connection")
    def test_get_memory_stats_error(self, mock_get_connection):
        """Test memory stats with database error."""
        mock_conn = MagicMock()
        mock_conn.execute_query.side_effect = Exception("Insufficient permissions")
        mock_get_connection.return_value = mock_conn

        result = get_memory_stats()

        assert isinstance(result, MemoryStatsResponse)
        assert result.success is False
        assert result.memory_stats is None
        assert "Insufficient permissions" in result.error


def _sql_server_reachable():
    """Check if SQL Server is reachable using .env connection settings (5s timeout)."""
    import pyodbc
    from sqlserver_doctor.utils.connection import SQLServerConnection

    try:
        # Create a fresh connection instance (don't use singleton which may be corrupted by tests)
        conn = SQLServerConnection()
        conn_str = conn.get_connection_string()
        with pyodbc.connect(conn_str, timeout=5) as db_conn:
            cursor = db_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        return False


_is_reachable = _sql_server_reachable()

sql_server_available = pytest.mark.skipif(
    not _is_reachable,
    reason="SQL Server not reachable (check .env connection settings)",
)


def _reset_connection_singleton():
    """Reset the global connection singleton so it picks up real .env values."""
    import sqlserver_doctor.utils.connection as conn_module

    conn_module._connection = None


class TestExecuteSelectQuery:
    """Tests for execute_select_query tool (integration tests using .env connection)."""

    def setup_method(self):
        """Reset connection singleton before each test to undo env patches from other tests."""
        _reset_connection_singleton()

    @sql_server_available
    def test_success(self):
        """Test successful SELECT query against real database."""
        result = execute_select_query(
            query="SELECT name, database_id FROM sys.databases WHERE name = 'master'"
        )

        assert isinstance(result, ExecuteSelectQueryResponse)
        assert result.success is True
        assert result.row_count == 1
        assert result.truncated is False
        assert len(result.columns) == 2
        assert result.columns[0].name == "name"
        assert result.columns[1].name == "database_id"
        assert result.rows[0]["name"] == "master"
        assert result.rows[0]["database_id"] == 1
        assert result.error is None
        assert result.execution_time_ms >= 0

    @sql_server_available
    def test_with_database(self):
        """Test query execution with database context."""
        result = execute_select_query(
            query="SELECT TOP 1 name FROM sys.tables",
            database_name="master",
        )

        assert result.success is True
        assert len(result.columns) == 1
        assert result.columns[0].name == "name"

    @sql_server_available
    def test_multiple_rows(self):
        """Test query returning multiple rows."""
        result = execute_select_query(
            query="SELECT name, database_id FROM sys.databases ORDER BY database_id",
            row_limit=5,
        )

        assert result.success is True
        assert result.row_count >= 1
        assert result.row_count <= 5
        # master is always database_id 1
        assert result.rows[0]["name"] == "master"

    @sql_server_available
    def test_row_limit_truncation(self):
        """Test that results are truncated when exceeding row_limit."""
        result = execute_select_query(
            query="SELECT name FROM sys.all_objects",
            row_limit=3,
        )

        assert result.success is True
        assert result.truncated is True
        assert result.row_count == 3
        assert len(result.rows) == 3

    @sql_server_available
    def test_cte_query(self):
        """Test WITH (CTE) queries work."""
        result = execute_select_query(
            query="WITH cte AS (SELECT 1 AS val) SELECT val FROM cte"
        )

        assert result.success is True
        assert result.row_count == 1
        assert result.rows[0]["val"] == 1

    def test_rejects_insert(self):
        """Test that INSERT queries are rejected."""
        result = execute_select_query(query="INSERT INTO foo VALUES (1)")

        assert isinstance(result, ExecuteSelectQueryResponse)
        assert result.success is False
        assert "Only SELECT or WITH" in result.error

    def test_rejects_multi_statement(self):
        """Test that multi-statement queries with dangerous keywords are rejected."""
        result = execute_select_query(query="SELECT 1; DROP TABLE foo")

        assert result.success is False
        assert "DROP" in result.error

    def test_rejects_update(self):
        """Test that UPDATE queries are rejected."""
        result = execute_select_query(query="UPDATE foo SET bar = 1")

        assert result.success is False
        assert "Only SELECT or WITH" in result.error

    @sql_server_available
    def test_invalid_sql_returns_error(self):
        """Test that invalid SQL returns a structured error."""
        result = execute_select_query(query="SELECT FROM WHERE")

        assert result.success is False
        assert result.error is not None

    def test_database_name_injection(self):
        """Test that dangerous database names are rejected."""
        result = execute_select_query(
            query="SELECT 1",
            database_name="master; DROP TABLE foo",
        )

        assert result.success is False
        assert "Invalid database name" in result.error

    def test_type_serialization(self):
        """Test that _serialize_value handles various types."""
        assert _serialize_value(None) is None
        assert _serialize_value("hello") == "hello"
        assert _serialize_value(42) == 42
        assert _serialize_value(3.14) == 3.14
        assert _serialize_value(True) is True
        assert _serialize_value(Decimal("123.45")) == 123.45
        assert _serialize_value(datetime(2024, 1, 15, 10, 30, 0)) == "2024-01-15T10:30:00"
        assert _serialize_value(b"\xde\xad") == "dead"

    def test_validate_select_query_allows_cte(self):
        """Test that WITH (CTE) queries are allowed."""
        assert _validate_select_query("WITH cte AS (SELECT 1) SELECT * FROM cte") is None

    def test_validate_select_query_strips_comments(self):
        """Test that comments are stripped before validation."""
        assert _validate_select_query("-- comment\nSELECT 1") is None
        assert _validate_select_query("/* comment */ SELECT 1") is None
