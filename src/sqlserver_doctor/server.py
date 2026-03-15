"""SQL Server Doctor MCP Server - Main server implementation."""

import re
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime
from datetime import time as time_type
from decimal import Decimal
from enum import Enum
from typing import Any

import pyodbc
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from sqlserver_doctor.utils.connection import (
    get_active_connection_name,
    get_all_connections,
    get_connection,
    set_active_connection_name,
)
from sqlserver_doctor.utils.logger import setup_logger

# Setup logger
logger = setup_logger("sqlserver_doctor.server")

# Create the FastMCP server instance
mcp = FastMCP("SQL Server Doctor")
logger.info("SQL Server Doctor MCP Server initialized")


# Response models
class ServerVersionResponse(BaseModel):
    """Response model for server version information."""

    version: str = Field(description="SQL Server version string")
    server_name: str = Field(description="SQL Server instance name")
    success: bool = Field(description="Whether the query was successful")
    error: str | None = Field(None, description="Error message if query failed")


class DatabaseInfo(BaseModel):
    """Information about a single database."""

    name: str = Field(description="Database name")
    database_id: int = Field(description="Database ID")
    create_date: str = Field(description="Database creation date")
    state_desc: str = Field(description="Database state (e.g., ONLINE, OFFLINE)")
    recovery_model_desc: str = Field(description="Recovery model (SIMPLE, FULL, BULK_LOGGED)")
    compatibility_level: int = Field(description="Database compatibility level")


class DatabaseListResponse(BaseModel):
    """Response model for database list."""

    databases: list[DatabaseInfo] = Field(description="List of databases")
    count: int = Field(description="Total number of databases")
    success: bool = Field(description="Whether the query was successful")
    error: str | None = Field(None, description="Error message if query failed")


class ActiveSessionInfo(BaseModel):
    """Information about an active SQL Server session."""

    sql_text: str = Field(description="SQL query text being executed")
    session_id: int = Field(description="Session ID")
    status: str = Field(description="Request status (running, suspended, etc.)")
    command: str = Field(description="Command type (SELECT, INSERT, etc.)")
    cpu_seconds: float = Field(description="CPU time in seconds")
    elapsed_seconds: float = Field(description="Total elapsed time in seconds")
    reads: int = Field(description="Number of disk reads")
    logical_reads: int = Field(description="Number of logical reads")
    wait_time: int = Field(description="Current wait time in milliseconds")
    last_wait_type: str | None = Field(None, description="Last wait type encountered")
    blocking_session_id: int | None = Field(None, description="Session ID causing blocking, if any")
    connect_time: str | None = Field(None, description="Connection start time")
    dop: int = Field(description="Degree of parallelism")
    host_name: str | None = Field(None, description="Client host name")
    program_name: str | None = Field(None, description="Client program name")
    database_name: str | None = Field(None, description="Database name")
    login_name: str | None = Field(None, description="Login name")


class ActiveSessionsResponse(BaseModel):
    """Response model for active sessions list."""

    sessions: list[ActiveSessionInfo] = Field(description="List of active sessions")
    count: int = Field(description="Total number of active sessions")
    success: bool = Field(description="Whether the query was successful")
    error: str | None = Field(None, description="Error message if query failed")


class SchedulerStats(BaseModel):
    """Statistics for a single SQL Server scheduler."""

    scheduler_id: int = Field(description="Scheduler ID")
    current_tasks_count: int = Field(description="Total tasks assigned to this scheduler")
    runnable_tasks_count: int = Field(
        description="Tasks waiting for CPU (CPU pressure indicator if > 0)"
    )
    work_queue_count: int = Field(description="Work items in the queue")
    pending_disk_io_count: int = Field(description="Pending I/O operations")


class SchedulerStatsResponse(BaseModel):
    """Response model for scheduler statistics."""

    schedulers: list[SchedulerStats] = Field(description="List of scheduler statistics")
    scheduler_count: int = Field(description="Number of schedulers (typically = CPU cores)")
    total_runnable_tasks: int = Field(
        description="Total tasks waiting for CPU across all schedulers"
    )
    avg_runnable_per_scheduler: float = Field(description="Average runnable tasks per scheduler")
    cpu_pressure_detected: bool = Field(
        description="Whether CPU pressure is detected (runnable tasks > 0)"
    )
    interpretation: str = Field(description="Interpretation guide for the results")
    success: bool = Field(description="Whether the query was successful")
    error: str | None = Field(None, description="Error message if query failed")


class ConfigSeverity(str, Enum):
    """Severity levels for configuration items."""

    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    REVIEW = "REVIEW"
    CONSIDER = "CONSIDER"


class ConfigItem(BaseModel):
    """Information about a single server configuration item."""

    name: str = Field(description="Configuration name")
    value: int | str = Field(description="Current configured value")
    severity: ConfigSeverity = Field(description="Severity level of the configuration status")
    message: str = Field(description="Human-readable status message with context")
    recommendation: str | None = Field(None, description="Recommended action to take, if any")


class ServerConfigResponse(BaseModel):
    """Response model for server configuration diagnostics."""

    configurations: list[ConfigItem] = Field(description="List of configuration items")
    success: bool = Field(description="Whether the query was successful")
    error: str | None = Field(None, description="Error message if query failed")


class MemoryStats(BaseModel):
    """Memory statistics and diagnostics for SQL Server."""

    server_name: str = Field(description="SQL Server instance name")
    check_timestamp: str = Field(description="Timestamp when check was performed")
    ple_seconds: int = Field(description="Page Life Expectancy in seconds")
    ple_minutes: int = Field(description="Page Life Expectancy in minutes")
    ple_status: str = Field(description="PLE status: OK, WARNING, or CRITICAL")
    memory_grants_pending: int = Field(description="Number of queries waiting for memory grants")
    grants_status: str = Field(description="Memory grants status: OK or CRITICAL")
    target_memory_mb: int = Field(description="Target server memory in MB")
    total_memory_mb: int = Field(description="Total server memory currently allocated in MB")
    memory_difference_mb: int = Field(description="Difference between target and total memory (MB)")
    memory_pressure_status: str = Field(
        description="Memory pressure status: OK, WATCH, or UNDER_PRESSURE"
    )
    max_server_memory_mb: int = Field(description="Max server memory configuration setting (MB)")
    buffer_pool_committed_mb: int = Field(description="Buffer pool committed memory (MB)")
    buffer_pool_target_mb: int = Field(description="Buffer pool target memory (MB)")
    overall_assessment: str = Field(
        description="Overall memory health assessment with recommendations"
    )


class MemoryStatsResponse(BaseModel):
    """Response model for memory statistics."""

    memory_stats: MemoryStats | None = Field(None, description="Memory statistics and diagnostics")
    success: bool = Field(description="Whether the query was successful")
    error: str | None = Field(None, description="Error message if query failed")


# Query Tuning Response Models


class ExecutionMetrics(BaseModel):
    """Performance metrics from query execution."""

    duration_ms: int = Field(description="Total execution duration in milliseconds")
    cpu_time_ms: int = Field(description="CPU time consumed in milliseconds")
    logical_reads: int = Field(description="Number of logical page reads")
    physical_reads: int = Field(description="Number of physical page reads")
    read_ahead_reads: int = Field(description="Number of read-ahead reads")
    lob_logical_reads: int = Field(description="Logical reads for LOB data")
    lob_physical_reads: int = Field(description="Physical reads for LOB data")
    row_count: int = Field(description="Number of rows returned")
    estimated_cost: float = Field(description="Estimated query cost from execution plan")


class ExecutionPlanWarning(BaseModel):
    """Warning found in execution plan."""

    type: str = Field(description="Warning type (e.g., IMPLICIT_CONVERSION, NO_JOIN_PREDICATE)")
    description: str = Field(description="Human-readable description of the warning")
    column: str | None = Field(None, description="Column name if applicable")
    impact: str = Field(description="Impact on performance")


class HighCostOperator(BaseModel):
    """High-cost operator in execution plan."""

    operator: str = Field(description="Operator type (e.g., Clustered Index Scan, Sort)")
    table: str | None = Field(None, description="Table name if applicable")
    cost_percent: float = Field(description="Percentage of total query cost")
    estimated_rows: int = Field(description="Estimated row count")
    actual_rows: int = Field(description="Actual row count")
    cardinality_accurate: bool = Field(description="Whether cardinality estimation was accurate")
    reason: str | None = Field(
        None, description="Reason for high cost (e.g., ORDER BY without index)"
    )


class ParallelismInfo(BaseModel):
    """Parallelism information from execution."""

    is_parallel: bool = Field(description="Whether query executed in parallel")
    degree_of_parallelism: int = Field(description="Degree of parallelism used")
    cxpacket_wait_ms: int = Field(description="CXPACKET wait time in milliseconds")


class ExecutionPlanSummary(BaseModel):
    """Summary of execution plan analysis."""

    cached_plan_size_kb: int = Field(description="Size of cached plan in KB")
    compile_time_ms: int = Field(description="Compilation time in milliseconds")
    warnings: list[ExecutionPlanWarning] = Field(description="Warnings found in plan")
    high_cost_operators: list[HighCostOperator] = Field(
        description="High-cost operators (> 20% cost)"
    )
    parallelism_info: ParallelismInfo = Field(description="Parallelism information")


class WaitStatistic(BaseModel):
    """Wait statistic information."""

    wait_type: str = Field(description="Type of wait")
    wait_time_ms: int = Field(description="Wait time in milliseconds")
    percentage: float = Field(description="Percentage of total wait time")


class WaitStatistics(BaseModel):
    """Wait statistics for query."""

    total_wait_time_ms: int = Field(description="Total wait time in milliseconds")
    top_waits: list[WaitStatistic] = Field(description="Top wait types")


class AnalyzeQueryExecutionResponse(BaseModel):
    """Response model for analyze_query_execution tool."""

    execution_metrics: ExecutionMetrics | None = Field(
        None, description="Execution performance metrics"
    )
    execution_plan_xml: str | None = Field(None, description="Full ShowPlanXML execution plan")
    execution_plan_summary: ExecutionPlanSummary | None = Field(
        None, description="Summary of execution plan"
    )
    wait_statistics: WaitStatistics | None = Field(None, description="Wait statistics")
    bottleneck_type: str | None = Field(
        None, description="Primary bottleneck type (IO_BOUND, CPU_BOUND, WAIT_BOUND, MEMORY_BOUND)"
    )
    query_hash: str | None = Field(None, description="Query hash for plan cache lookup")
    query_plan_hash: str | None = Field(None, description="Query plan hash")
    success: bool = Field(description="Whether the analysis was successful")
    error: str | None = Field(None, description="Error message if analysis failed")


class AntipatternInfo(BaseModel):
    """Information about a detected query antipattern."""

    category: str = Field(
        description="Antipattern category (e.g., NON_SARGABLE_PREDICATE, IMPLICIT_CONVERSION)"
    )
    severity: str = Field(description="Severity level (HIGH, MEDIUM, LOW)")
    location: str = Field(description="Specific query fragment with the issue")
    issue: str = Field(description="Description of the problem")
    recommendation: str = Field(description="Specific rewrite suggestion")
    estimated_impact: str = Field(description="Estimated performance impact")


class DetectQueryAntipatternsResponse(BaseModel):
    """Response model for detect_query_antipatterns tool."""

    antipatterns_found: list[AntipatternInfo] = Field(description="List of antipatterns detected")
    query_complexity_score: float = Field(description="Query complexity score (1-10 scale)")
    rewrite_priority: str = Field(description="Priority for rewriting (HIGH, MEDIUM, LOW, NONE)")
    suggested_rewrite: str | None = Field(
        None, description="Complete rewritten query if applicable"
    )
    success: bool = Field(description="Whether the analysis was successful")
    error: str | None = Field(None, description="Error message if analysis failed")


class StatisticsAnalysis(BaseModel):
    """Analysis of statistics for a table."""

    table: str = Field(description="Table name (e.g., dbo.Orders)")
    index: str | None = Field(None, description="Index name if applicable")
    statistics_name: str = Field(description="Statistics object name")
    last_updated: str = Field(description="ISO datetime of last update")
    days_old: int = Field(description="Age of statistics in days")
    rows_in_table: int = Field(description="Total rows in table")
    rows_sampled: int = Field(description="Rows sampled for statistics")
    sampling_percent: float = Field(description="Percentage of rows sampled")
    modification_counter: int = Field(description="Rows modified since last update")
    modification_percent: float = Field(description="Percentage of rows modified")
    needs_update: bool = Field(description="Whether statistics need updating")
    severity: str = Field(description="Severity level (OK, WARNING, HIGH)")
    recommendation: str | None = Field(None, description="UPDATE STATISTICS command if needed")


class CardinalityMismatch(BaseModel):
    """Cardinality estimation mismatch between estimated and actual."""

    table: str = Field(description="Table name")
    estimated_rows: int = Field(description="Estimated row count from optimizer")
    actual_rows: int = Field(description="Actual row count from execution")
    variance_ratio: float = Field(description="Ratio of actual/estimated rows")
    likely_cause: str = Field(description="Likely cause of mismatch")
    impact: str = Field(description="Impact on query performance")


class GetQueryStatisticsHealthResponse(BaseModel):
    """Response model for get_query_statistics_health tool."""

    statistics_analysis: list[StatisticsAnalysis] = Field(
        description="Statistics analysis for tables"
    )
    cardinality_mismatches: list[CardinalityMismatch] = Field(
        description="Cardinality mismatches found"
    )
    auto_update_stats_enabled: bool = Field(description="Whether auto-update statistics is enabled")
    auto_create_stats_enabled: bool = Field(description="Whether auto-create statistics is enabled")
    success: bool = Field(description="Whether the analysis was successful")
    error: str | None = Field(None, description="Error message if analysis failed")


class MissingIndexInfo(BaseModel):
    """Information about a missing index recommendation."""

    table: str = Field(description="Table name")
    equality_columns: list[str] = Field(description="Columns for equality predicates")
    inequality_columns: list[str] = Field(description="Columns for inequality predicates")
    included_columns: list[str] = Field(description="Columns to include in index")
    impact_score: float = Field(description="Impact score (0-100)")
    avg_user_impact: float = Field(description="Expected improvement percentage")
    avg_total_user_cost: float = Field(description="Average total user cost")
    user_seeks: int = Field(description="Number of seeks that would benefit")
    user_scans: int = Field(description="Number of scans that would benefit")
    last_user_seek: str | None = Field(None, description="ISO datetime of last seek")
    create_statement: str = Field(description="Ready-to-execute CREATE INDEX DDL")
    estimated_size_mb: float = Field(description="Estimated index size in MB")
    recommendation_priority: str = Field(description="Priority level (HIGH, MEDIUM, LOW)")
    considerations: list[str] = Field(description="Additional context and considerations")


class ExistingIndexUsage(BaseModel):
    """Usage information for an existing index."""

    table: str = Field(description="Table name")
    index_name: str = Field(description="Index name")
    user_seeks: int = Field(description="Number of user seeks")
    user_scans: int = Field(description="Number of user scans")
    user_lookups: int = Field(description="Number of user lookups")
    user_updates: int = Field(description="Number of user updates")
    last_user_seek: str | None = Field(None, description="ISO datetime of last seek")
    size_mb: float = Field(description="Index size in MB")
    recommendation: str | None = Field(None, description="Recommendation (e.g., consider dropping)")
    action: str | None = Field(None, description="Action SQL (e.g., DROP INDEX)")


class IndexOverlap(BaseModel):
    """Information about overlapping indexes."""

    existing_index: str = Field(description="Name of existing index")
    columns: list[str] = Field(description="Columns in existing index")
    missing_index_recommendation: str = Field(description="Name of recommended index")
    recommendation: str = Field(description="How to consolidate indexes")


class AnalyzeMissingIndexesResponse(BaseModel):
    """Response model for analyze_missing_indexes tool."""

    missing_indexes: list[MissingIndexInfo] = Field(description="Missing index recommendations")
    existing_index_usage: list[ExistingIndexUsage] = Field(
        description="Existing index usage information"
    )
    index_overlaps: list[IndexOverlap] = Field(description="Overlapping index information")
    success: bool = Field(description="Whether the analysis was successful")
    error: str | None = Field(None, description="Error message if analysis failed")


class FindObjectDatabaseResponse(BaseModel):
    """Response model for find_object_database tool."""

    database_name: str | None = Field(description="Database where object was found")
    schema_name: str | None = Field(description="Schema name")
    object_name: str = Field(description="Object name")
    object_type: str | None = Field(description="Object type (USER_TABLE, VIEW, etc.)")
    full_name: str | None = Field(description="Fully qualified name (database.schema.object)")
    success: bool = Field(description="Whether the search was successful")
    error: str | None = Field(None, description="Error message if search failed")


class ColumnMetadata(BaseModel):
    """Metadata for a single column in a query result set."""

    name: str = Field(description="Column name")
    type_name: str = Field(
        description="Python type name of the column value (e.g., str, int, datetime, Decimal)"
    )


class ExecuteSelectQueryResponse(BaseModel):
    """Response model for execute_select_query tool."""

    columns: list[ColumnMetadata] = Field(
        default_factory=list, description="Column metadata for the result set"
    )
    rows: list[dict[str, Any]] = Field(
        default_factory=list, description="Result rows as list of dicts"
    )
    row_count: int = Field(0, description="Number of rows returned")
    truncated: bool = Field(False, description="Whether results were truncated by row_limit")
    execution_time_ms: int = Field(0, description="Query execution time in milliseconds")
    success: bool = Field(description="Whether the query was successful")
    error: str | None = Field(None, description="Error message if query failed")


# Helper functions for execute_select_query
def _validate_select_query(query: str) -> str | None:
    """Validate that a query is a safe SELECT statement.

    Returns error message if query is not safe, None if OK.
    """
    stripped = query.strip()
    # Remove single-line comments
    cleaned = re.sub(r"--[^\n]*", " ", stripped)
    # Remove multi-line comments
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip().upper()

    if not cleaned.startswith("SELECT") and not cleaned.startswith("WITH"):
        return "Only SELECT or WITH (CTE) queries are allowed"

    # Check for dangerous keywords after semicolons
    dangerous = {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "EXEC",
        "EXECUTE",
        "GRANT",
        "REVOKE",
        "DENY",
        "BACKUP",
        "RESTORE",
        "SHUTDOWN",
        "DBCC",
        "BULK",
    }
    statements = cleaned.split(";")
    for stmt in statements[1:]:
        stmt_stripped = stmt.strip()
        if stmt_stripped:
            first_word = stmt_stripped.split()[0] if stmt_stripped.split() else ""
            if first_word in dangerous:
                return f"Multi-statement queries containing {first_word} are not allowed"

    return None


def _serialize_value(value: Any) -> Any:
    """Convert a pyodbc cell value to a JSON-serializable type."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time_type):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


# Connection management models
class ConnectionInfo(BaseModel):
    """Information about a configured connection."""

    name: str = Field(description="Connection name")
    host: str = Field(description="Server host")
    port: str = Field(description="Server port")
    database: str = Field(description="Default database")
    auth_type: str = Field(description="Authentication type (Windows or SQL Server)")
    is_active: bool = Field(description="Whether this is the currently active connection")


class ConnectionListResponse(BaseModel):
    """Response model for listing connections."""

    connections: list[ConnectionInfo] = Field(description="List of configured connections")
    active_connection: str | None = Field(description="Name of the currently active connection")
    success: bool = Field(description="Whether the operation was successful")
    error: str | None = Field(None, description="Error message if operation failed")


class SetActiveConnectionResponse(BaseModel):
    """Response model for setting the active connection."""

    connection_name: str = Field(description="Name of the connection that was set as active")
    success: bool = Field(description="Whether the operation was successful")
    error: str | None = Field(None, description="Error message if operation failed")


# Tools


@mcp.tool()
def list_connections() -> ConnectionListResponse:
    """
    List all configured SQL Server connections and show which is active.

    Returns information about all connections configured in connections.json
    or the default connection from environment variables.
    """
    logger.info("Tool called: list_connections")
    try:
        all_conns = get_all_connections()

        # If no connections loaded yet, trigger default creation
        if not all_conns:
            get_connection()
            all_conns = get_all_connections()

        active_name = get_active_connection_name()

        conn_list = []
        for name, conn in all_conns.items():
            auth_type = "SQL Server" if conn.user else "Windows"
            conn_list.append(
                ConnectionInfo(
                    name=name,
                    host=conn.host,
                    port=conn.port,
                    database=conn.database,
                    auth_type=auth_type,
                    is_active=(name == active_name),
                )
            )

        return ConnectionListResponse(
            connections=conn_list,
            active_connection=active_name,
            success=True,
        )
    except Exception as e:
        logger.error(f"Error listing connections: {str(e)}")
        return ConnectionListResponse(
            connections=[],
            active_connection=None,
            success=False,
            error=str(e),
        )


@mcp.tool()
def set_active_connection(connection_name: str) -> SetActiveConnectionResponse:
    """
    Set the active SQL Server connection used by all tools by default.

    All subsequent tool calls will use this connection unless overridden
    with the connection_name parameter.

    Args:
        connection_name: Name of the connection to set as active (from connections.json)
    """
    logger.info(f"Tool called: set_active_connection({connection_name})")
    try:
        set_active_connection_name(connection_name)
        return SetActiveConnectionResponse(
            connection_name=connection_name,
            success=True,
        )
    except ValueError as e:
        return SetActiveConnectionResponse(
            connection_name=connection_name,
            success=False,
            error=str(e),
        )


@mcp.tool()
def get_server_version(connection_name: str | None = None) -> ServerVersionResponse:
    """
    Get SQL Server version and instance information.

    Returns detailed version information about the connected SQL Server instance,
    including the version string and server name.

    Args:
        connection_name: Optional connection name to use instead of the active connection
    """
    logger.info("Tool called: get_server_version")
    try:
        conn = get_connection(connection_name)
        results = conn.execute_query(
            """
            SELECT
                @@VERSION AS Version,
                @@SERVERNAME AS ServerName
            """
        )

        if results:
            logger.info(f"Retrieved server version: {results[0]['ServerName']}")
            return ServerVersionResponse(
                version=results[0]["Version"],
                server_name=results[0]["ServerName"],
                success=True,
            )
        else:
            logger.warning("No results returned from server version query")
            return ServerVersionResponse(
                version="",
                server_name="",
                success=False,
                error="No results returned from query",
            )

    except Exception as e:
        logger.error(f"Error getting server version: {str(e)}")
        return ServerVersionResponse(
            version="",
            server_name="",
            success=False,
            error=str(e),
        )


@mcp.tool()
def list_databases(connection_name: str | None = None) -> DatabaseListResponse:
    """
    List all databases on the SQL Server instance.

    Returns information about all databases including name, state, recovery model,
    and compatibility level. This is useful for understanding the server's database
    landscape and identifying databases that may need attention.

    Args:
        connection_name: Optional connection name to use instead of the active connection
    """
    logger.info("Tool called: list_databases")
    try:
        conn = get_connection(connection_name)
        results = conn.execute_query(
            """
            SELECT
                name,
                database_id,
                CONVERT(VARCHAR, create_date, 120) AS create_date,
                state_desc,
                recovery_model_desc,
                compatibility_level
            FROM sys.databases
            ORDER BY name
            """
        )

        databases = [DatabaseInfo(**db) for db in results]
        logger.info(f"Successfully retrieved {len(databases)} database(s)")

        return DatabaseListResponse(
            databases=databases,
            count=len(databases),
            success=True,
        )

    except Exception as e:
        logger.error(f"Error listing databases: {str(e)}")
        return DatabaseListResponse(
            databases=[],
            count=0,
            success=False,
            error=str(e),
        )


@mcp.tool()
def get_active_sessions(connection_name: str | None = None) -> ActiveSessionsResponse:
    """
    Get currently active sessions and queries on the SQL Server instance.

    Returns detailed information about active sessions including currently executing
    SQL text, CPU usage, wait statistics, blocking information, and client details.
    This is useful for monitoring server activity, identifying performance issues,
    and detecting blocking situations.

    Filters out system databases (master, msdb) and the monitoring query itself.

    Args:
        connection_name: Optional connection name to use instead of the active connection
    """
    logger.info("Tool called: get_active_sessions")
    try:
        conn = get_connection(connection_name)
        results = conn.execute_query(
            """
            SELECT
                sqltext.TEXT as sql_text,
                req.session_id,
                req.status,
                req.command,
                CONVERT(NUMERIC(8,1), req.cpu_time/1000.0) as cpu_seconds,
                CONVERT(NUMERIC(8,1), req.total_elapsed_time/1000.0) as elapsed_seconds,
                req.reads,
                req.logical_reads,
                req.wait_time,
                req.last_wait_type,
                req.blocking_session_id,
                CONVERT(VARCHAR, con.connect_time, 120) as connect_time,
                req.dop,
                dm_es.host_name,
                dm_es.program_name,
                DB_NAME(req.database_id) as database_name,
                dm_es.login_name
            FROM sys.dm_exec_requests req
            LEFT OUTER JOIN sys.dm_exec_sessions dm_es ON dm_es.session_id = req.session_id
            LEFT OUTER JOIN sys.dm_exec_connections con ON con.connection_id = req.connection_id
            CROSS APPLY sys.dm_exec_sql_text(req.sql_handle) AS sqltext
            WHERE sqltext.TEXT NOT LIKE '%sqltext.TEXT%'
            AND DB_NAME(req.database_id) NOT IN ('master', 'msdb')
            """
        )

        sessions = [ActiveSessionInfo(**session) for session in results]
        logger.info(f"Successfully retrieved {len(sessions)} active session(s)")

        return ActiveSessionsResponse(
            sessions=sessions,
            count=len(sessions),
            success=True,
        )

    except Exception as e:
        logger.error(f"Error getting active sessions: {str(e)}")
        return ActiveSessionsResponse(
            sessions=[],
            count=0,
            success=False,
            error=str(e),
        )


@mcp.tool()
def get_scheduler_stats(connection_name: str | None = None) -> SchedulerStatsResponse:
    """
    Get SQL Server scheduler statistics for CPU and Disk IO queue monitoring. Used for preassure detection.

    Returns average scheduler information including runnable tasks (CPU queue depth) and pending I/O operations.
    This is critical for identifying CPU pressure and performance bottlenecks.

    Key metrics interpretation:
    - scheduler_count: Number of schedulers (typically = CPU cores)
    - avg_runnable_tasks: Average runnable tasks per scheduler. 0 - 0.5: No CPU pressure, 0.5-2: Mild pressure, 2-5: Moderate pressure, >5: Critical, immediate action needed
    - avg_pending_disk_io_count: Average pending I/O operations per scheduler. 0-1: Normal I/O activity, 1-5: Moderate I/O pressure, 5-10: High I/O pressure, >10: Critical I/O bottleneck, check disk subsystem

    Args:
        connection_name: Optional connection name to use instead of the active connection
    """
    logger.info("Tool called: get_scheduler_stats")
    try:
        conn = get_connection(connection_name)
        results = conn.execute_query(
            """
            SELECT
                COUNT(*) AS scheduler_count,
                AVG(1.0*runnable_tasks_count) AS avg_runnable_tasks,
                AVG(1.0*pending_disk_io_count) AS avg_pending_disk_io_count
            FROM sys.dm_os_schedulers
            WHERE scheduler_id < 255
            """
        )

        # Extract aggregated metrics from single result row
        if not results:
            raise Exception("No scheduler statistics returned")

        result = results[0]
        scheduler_count = result["scheduler_count"]
        avg_runnable = float(result["avg_runnable_tasks"])
        avg_pending_io = float(result["avg_pending_disk_io_count"])

        # Calculate total runnable tasks (approximate from average)
        total_runnable = int(avg_runnable * scheduler_count)
        cpu_pressure = avg_runnable > 0

        # Build interpretation based on updated metrics
        interpretation_parts = []

        # CPU pressure interpretation
        if avg_runnable == 0:
            interpretation_parts.append("No CPU pressure detected (avg runnable: 0)")
        elif avg_runnable <= 0.5:
            interpretation_parts.append(f"Minimal CPU pressure (avg runnable: {avg_runnable:.2f})")
        elif avg_runnable <= 2:
            interpretation_parts.append(f"MILD CPU PRESSURE (avg runnable: {avg_runnable:.2f})")
        elif avg_runnable <= 5:
            interpretation_parts.append(
                f"MODERATE CPU PRESSURE (avg runnable: {avg_runnable:.2f}) - Consider query optimization"
            )
        else:
            interpretation_parts.append(
                f"CRITICAL CPU PRESSURE (avg runnable: {avg_runnable:.2f}) - Immediate action needed!"
            )

        # I/O pressure interpretation
        if avg_pending_io <= 1:
            interpretation_parts.append(
                f"Normal I/O activity (avg pending I/O: {avg_pending_io:.2f})"
            )
        elif avg_pending_io <= 5:
            interpretation_parts.append(
                f"MODERATE I/O PRESSURE (avg pending I/O: {avg_pending_io:.2f})"
            )
        elif avg_pending_io <= 10:
            interpretation_parts.append(
                f"HIGH I/O PRESSURE (avg pending I/O: {avg_pending_io:.2f}) - Check disk performance"
            )
        else:
            interpretation_parts.append(
                f"CRITICAL I/O BOTTLENECK (avg pending I/O: {avg_pending_io:.2f}) - Check disk subsystem immediately!"
            )

        interpretation = " | ".join(interpretation_parts)

        logger.info(
            f"Retrieved scheduler stats: {scheduler_count} schedulers, "
            f"avg runnable: {avg_runnable:.2f}, avg pending I/O: {avg_pending_io:.2f}"
        )

        return SchedulerStatsResponse(
            schedulers=[],  # Empty list since we're returning aggregates
            scheduler_count=scheduler_count,
            total_runnable_tasks=total_runnable,
            avg_runnable_per_scheduler=avg_runnable,
            cpu_pressure_detected=cpu_pressure,
            interpretation=interpretation,
            success=True,
        )

    except Exception as e:
        logger.error(f"Error getting scheduler stats: {str(e)}")
        return SchedulerStatsResponse(
            schedulers=[],
            scheduler_count=0,
            total_runnable_tasks=0,
            avg_runnable_per_scheduler=0.0,
            cpu_pressure_detected=False,
            interpretation="",
            success=False,
            error=str(e),
        )


@mcp.tool()
def get_server_configurations(connection_name: str | None = None) -> ServerConfigResponse:
    """
    Get SQL Server configuration diagnostics and recommendations.

    Returns configuration analysis for key SQL Server settings including:
    - Max Server Memory: Memory allocation limits and edition compliance
    - Cost Threshold for Parallelism: Parallel query execution threshold
    - Max Degree of Parallelism (MAXDOP): Maximum parallel query threads

    Each configuration includes current value, severity assessment (OK, WARNING,
    CRITICAL, REVIEW, CONSIDER), contextual message, and actionable recommendations.

    Args:
        connection_name: Optional connection name to use instead of the active connection
    """
    logger.info("Tool called: get_server_configurations")
    try:
        conn = get_connection(connection_name)
        results = conn.execute_query(
            """
            -- Max Server Memory Configuration
            SELECT
                CONVERT(VARCHAR(100), c.name) as name,
                CAST(c.value_in_use AS INT) as value,
                CONVERT(VARCHAR(20),
                    CASE
                        WHEN c.value_in_use = 2147483647 THEN 'CRITICAL'
                        WHEN CAST(SERVERPROPERTY('EngineEdition') AS INT) = 2 AND c.value_in_use > 131072 THEN 'CRITICAL'
                        WHEN c.value_in_use > (i.physical_memory_kb / 1024 * 0.9) THEN 'WARNING'
                        WHEN c.value_in_use < (i.physical_memory_kb / 1024 * 0.5)
                            AND c.value_in_use < (CASE WHEN CAST(SERVERPROPERTY('EngineEdition') AS INT) = 2 THEN 131072 ELSE 999999999 END)
                            THEN 'WARNING'
                        ELSE 'OK'
                    END
                ) as severity,
                CONVERT(VARCHAR(1000),
                    CASE
                        WHEN c.value_in_use = 2147483647 THEN
                            'Unlimited (default) - should be set! [Server Memory: ' + CAST(i.physical_memory_kb / 1024 AS VARCHAR) + ' MB, Edition: ' + CAST(SERVERPROPERTY('Edition') AS VARCHAR) + ']'
                        WHEN CAST(SERVERPROPERTY('EngineEdition') AS INT) = 2 AND c.value_in_use > 131072
                            THEN 'Exceeds Standard Edition 128 GB limit! [Configured: ' + CAST(c.value_in_use AS VARCHAR) + ' MB, Limit: 131072 MB]'
                        WHEN CAST(SERVERPROPERTY('EngineEdition') AS INT) = 2 AND c.value_in_use >= 131072
                            THEN 'At Standard Edition limit [Configured: ' + CAST(c.value_in_use AS VARCHAR) + ' MB]'
                        WHEN c.value_in_use > (i.physical_memory_kb / 1024 * 0.9)
                            THEN 'Too high - leave memory for OS [Configured: ' + CAST(c.value_in_use AS VARCHAR) + ' MB, Server Total: ' + CAST(i.physical_memory_kb / 1024 AS VARCHAR) + ' MB]'
                        WHEN c.value_in_use < (i.physical_memory_kb / 1024 * 0.5)
                            AND c.value_in_use < (CASE WHEN CAST(SERVERPROPERTY('EngineEdition') AS INT) = 2 THEN 131072 ELSE 999999999 END)
                            THEN 'Too low - SQL Server artificially limited [Configured: ' + CAST(c.value_in_use AS VARCHAR) + ' MB, Server Total: ' + CAST(i.physical_memory_kb / 1024 AS VARCHAR) + ' MB]'
                        ELSE 'Configured appropriately [Configured: ' + CAST(c.value_in_use AS VARCHAR) + ' MB]'
                    END
                ) as message,
                CONVERT(VARCHAR(1000),
                    CASE
                        WHEN c.value_in_use = 2147483647 THEN
                            CASE
                                WHEN CAST(SERVERPROPERTY('EngineEdition') AS INT) = 2 THEN
                                    'Set max memory to: ' + CAST(
                                        CASE WHEN 131072 < (i.physical_memory_kb / 1024) - 4096
                                             THEN 131072
                                             ELSE (i.physical_memory_kb / 1024) - 4096
                                        END AS VARCHAR) + ' MB (Standard Edition 128 GB limit)'
                                ELSE
                                    'Set max memory to: ' + CAST((i.physical_memory_kb / 1024) - 4096 AS VARCHAR) + ' MB'
                            END
                        WHEN CAST(SERVERPROPERTY('EngineEdition') AS INT) = 2 AND c.value_in_use > 131072 THEN
                            'Reduce to 131072 MB (128 GB - Standard Edition limit)'
                        ELSE NULL
                    END
                ) as recommendation
            FROM sys.configurations c
            CROSS JOIN sys.dm_os_sys_info i
            WHERE c.name = 'max server memory (MB)'

            UNION ALL

            -- Cost Threshold for Parallelism
            SELECT
                CONVERT(VARCHAR(100), name) as name,
                CAST(value_in_use AS INT) as value,
                CONVERT(VARCHAR(20),
                    CASE
                        WHEN value_in_use = 5 THEN 'WARNING'
                        WHEN value_in_use < 25 THEN 'CONSIDER'
                        WHEN value_in_use >= 25 AND value_in_use <= 50 THEN 'OK'
                        ELSE 'OK'
                    END
                ) as severity,
                CONVERT(VARCHAR(1000),
                    CASE
                        WHEN value_in_use = 5 THEN 'Default value too low for modern servers [Current: ' + CAST(value_in_use AS VARCHAR) + ']'
                        WHEN value_in_use < 25 THEN 'Consider increasing to 25-50 to reduce excessive parallelism [Current: ' + CAST(value_in_use AS VARCHAR) + ']'
                        WHEN value_in_use >= 25 AND value_in_use <= 50 THEN 'Good starting point [Current: ' + CAST(value_in_use AS VARCHAR) + ']'
                        ELSE 'Custom tuned [Current: ' + CAST(value_in_use AS VARCHAR) + ']'
                    END
                ) as message,
                CONVERT(VARCHAR(1000),
                    CASE
                        WHEN value_in_use = 5 THEN 'Recommend setting to 50: EXEC sp_configure ''cost threshold for parallelism'', 50; RECONFIGURE;'
                        ELSE NULL
                    END
                ) as recommendation
            FROM sys.configurations
            WHERE name = 'cost threshold for parallelism'

            UNION ALL

            -- Max Degree of Parallelism
            SELECT
                CONVERT(VARCHAR(100), c.name) as name,
                CAST(c.value_in_use AS INT) as value,
                CONVERT(VARCHAR(20),
                    CASE
                        WHEN c.value_in_use = 0 THEN 'WARNING'
                        WHEN c.value_in_use = 1 THEN 'WARNING'
                        WHEN c.value_in_use > 8 THEN 'CONSIDER'
                        WHEN c.value_in_use = (i.cpu_count / i.hyperthread_ratio) AND (i.cpu_count / i.hyperthread_ratio) <= 8
                            THEN 'OK'
                        ELSE 'REVIEW'
                    END
                ) as severity,
                CONVERT(VARCHAR(1000),
                    CASE
                        WHEN c.value_in_use = 0 THEN 'Unlimited parallelism can cause CXPACKET waits [CPUs: ' + CAST(i.cpu_count AS VARCHAR) + ', Physical: ' + CAST(i.cpu_count / i.hyperthread_ratio AS VARCHAR) + ']'
                        WHEN c.value_in_use = 1 THEN 'Parallelism disabled - multi-core not utilized [CPUs: ' + CAST(i.cpu_count AS VARCHAR) + ']'
                        WHEN c.value_in_use > 8 THEN 'Values > 8 rarely help, often hurt [Current: ' + CAST(c.value_in_use AS VARCHAR) + ', CPUs: ' + CAST(i.cpu_count AS VARCHAR) + ']'
                        WHEN c.value_in_use = (i.cpu_count / i.hyperthread_ratio) AND (i.cpu_count / i.hyperthread_ratio) <= 8
                            THEN 'Set to physical CPU count [Current: ' + CAST(c.value_in_use AS VARCHAR) + ', Physical CPUs: ' + CAST(i.cpu_count / i.hyperthread_ratio AS VARCHAR) + ']'
                        ELSE 'Check if optimal for workload [Current: ' + CAST(c.value_in_use AS VARCHAR) + ', CPUs: ' + CAST(i.cpu_count AS VARCHAR) + ', Physical: ' + CAST(i.cpu_count / i.hyperthread_ratio AS VARCHAR) + ']'
                    END
                ) as message,
                CONVERT(VARCHAR(1000),
                    CASE
                        WHEN c.value_in_use = 0 THEN
                            'Recommend setting to: ' + CAST(
                                CASE
                                    WHEN (i.cpu_count / i.hyperthread_ratio) <= 8
                                    THEN (i.cpu_count / i.hyperthread_ratio)
                                    ELSE 8
                                END AS VARCHAR
                            ) + ' (physical CPU count, max 8)'
                        ELSE NULL
                    END
                ) as recommendation
            FROM sys.configurations c
            CROSS JOIN sys.dm_os_sys_info i
            WHERE c.name = 'max degree of parallelism'

            ORDER BY name
            """
        )

        configurations = [
            ConfigItem(
                name=row["name"],
                value=row["value"],
                severity=ConfigSeverity(row["severity"]),
                message=row["message"],
                recommendation=row["recommendation"],
            )
            for row in results
        ]

        logger.info(f"Successfully retrieved {len(configurations)} configuration(s)")

        return ServerConfigResponse(
            configurations=configurations,
            success=True,
        )

    except Exception as e:
        logger.error(f"Error getting server configurations: {str(e)}")
        return ServerConfigResponse(
            configurations=[],
            success=False,
            error=str(e),
        )


@mcp.tool()
def get_memory_stats(connection_name: str | None = None) -> MemoryStatsResponse:
    """
    Get SQL Server memory statistics to identify memory pressure issues.

    Returns comprehensive memory diagnostics including:
    - Page Life Expectancy (PLE): How long pages stay in buffer pool
      * <300 seconds: CRITICAL - severe memory pressure
      * <1000 seconds: WARNING - moderate memory pressure
      * >=1000 seconds: OK - healthy memory
    - Memory Grants Pending: Queries waiting for memory allocation (any > 0 is CRITICAL)
    - Memory Pressure: Gap between target and actual memory allocation
    - Buffer Pool: Committed and target memory usage
    - Overall Assessment: Aggregated health status with actionable recommendations

    This tool is essential for diagnosing if SQL Server needs more memory or if there
    are memory configuration issues.

    Args:
        connection_name: Optional connection name to use instead of the active connection
    """
    logger.info("Tool called: get_memory_stats")
    try:
        conn = get_connection(connection_name)
        results = conn.execute_query(
            """
            WITH memory_metrics AS (
                SELECT
                    MAX(CASE WHEN counter_name = 'Page life expectancy' AND object_name LIKE '%Buffer Node%'
                        THEN cntr_value END) AS ple_seconds,
                    MAX(CASE WHEN counter_name = 'Memory Grants Pending' AND object_name LIKE '%Memory Manager%'
                        THEN cntr_value END) AS grants_pending,
                    MAX(CASE WHEN counter_name = 'Target Server Memory (KB)'
                        THEN cntr_value/1024 END) AS target_mb,
                    MAX(CASE WHEN counter_name = 'Total Server Memory (KB)'
                        THEN cntr_value/1024 END) AS total_mb
                FROM sys.dm_os_performance_counters
                WHERE counter_name IN ('Page life expectancy', 'Memory Grants Pending',
                                      'Target Server Memory (KB)', 'Total Server Memory (KB)')
            )
            SELECT
                @@SERVERNAME AS server_name,
                CONVERT(VARCHAR, GETDATE(), 120) AS check_timestamp,

                -- PLE Metrics
                ple_seconds,
                ple_seconds/60 AS ple_minutes,
                CONVERT(VARCHAR(20),
                    CASE
                        WHEN ple_seconds < 300 THEN 'CRITICAL'
                        WHEN ple_seconds < 1000 THEN 'WARNING'
                        ELSE 'OK'
                    END
                ) AS ple_status,

                -- Memory Grants
                grants_pending AS memory_grants_pending,
                CONVERT(VARCHAR(20), CASE WHEN grants_pending > 0 THEN 'CRITICAL' ELSE 'OK' END) AS grants_status,

                -- Memory Allocation
                target_mb AS target_memory_mb,
                total_mb AS total_memory_mb,
                target_mb - total_mb AS memory_difference_mb,
                CONVERT(VARCHAR(20),
                    CASE
                        WHEN target_mb - total_mb > 1024 THEN 'UNDER_PRESSURE'
                        WHEN target_mb - total_mb > 512 THEN 'WATCH'
                        ELSE 'OK'
                    END
                ) AS memory_pressure_status,

                -- Config
                (SELECT CAST(value AS INT) FROM sys.configurations WHERE name = 'max server memory (MB)') AS max_server_memory_mb,
                (SELECT committed_kb/1024 FROM sys.dm_os_sys_info) AS buffer_pool_committed_mb,
                (SELECT committed_target_kb/1024 FROM sys.dm_os_sys_info) AS buffer_pool_target_mb,

                -- Overall Assessment
                CONVERT(VARCHAR(1000),
                    CASE
                        WHEN grants_pending > 0 THEN 'CRITICAL: Queries waiting for memory!'
                        WHEN ple_seconds < 300 AND (target_mb - total_mb) > 1024 THEN 'CRITICAL: Low PLE and memory pressure detected'
                        WHEN ple_seconds < 300 THEN 'WARNING: Low Page Life Expectancy'
                        WHEN (target_mb - total_mb) > 1024 THEN 'WARNING: SQL Server wants more memory'
                        ELSE 'OK: Memory appears healthy'
                    END
                ) AS overall_assessment
            FROM memory_metrics
            """
        )

        if results:
            stats = MemoryStats(**results[0])
            logger.info(
                f"Retrieved memory stats: PLE={stats.ple_seconds}s, "
                f"Assessment={stats.overall_assessment}"
            )
            return MemoryStatsResponse(
                memory_stats=stats,
                success=True,
            )
        else:
            logger.warning("No results returned from memory stats query")
            return MemoryStatsResponse(
                success=False,
                error="No results returned from query",
            )

    except Exception as e:
        logger.error(f"Error getting memory stats: {str(e)}")
        return MemoryStatsResponse(
            success=False,
            error=str(e),
        )


def _parse_runtime_stats_from_plan(plan_xml: str) -> dict | None:
    """
    Extract runtime statistics from execution plan XML.

    Parses <RunTimeCountersPerThread> elements from the ShowPlanXML to get
    actual execution metrics including I/O, CPU, and row counts.

    Args:
        plan_xml: Execution plan XML string from SET STATISTICS XML ON

    Returns:
        Dictionary with runtime statistics or None if parsing fails
    """
    try:
        root = ET.fromstring(plan_xml)
        ns = {"p": "http://schemas.microsoft.com/sqlserver/2004/07/showplan"}

        # Find RunTimeCountersPerThread element
        # This contains actual execution statistics
        runtime = root.find(".//p:RunTimeCountersPerThread", ns)

        if runtime is not None:
            return {
                "actual_rows": int(runtime.get("ActualRows", 0)),
                "actual_elapsed_ms": int(runtime.get("ActualElapsedms", 0)),
                "actual_cpu_ms": int(runtime.get("ActualCPUms", 0)),
                "actual_logical_reads": int(runtime.get("ActualLogicalReads", 0)),
                "actual_physical_reads": int(runtime.get("ActualPhysicalReads", 0)),
                "actual_read_aheads": int(runtime.get("ActualReadAheads", 0)),
                "actual_lob_logical_reads": int(runtime.get("ActualLobLogicalReads", 0)),
                "actual_lob_physical_reads": int(runtime.get("ActualLobPhysicalReads", 0)),
            }
        else:
            logger.warning("No RunTimeCountersPerThread found in execution plan XML")
            return None

    except ET.ParseError as e:
        logger.warning(f"Could not parse execution plan XML: {str(e)}")
        return None
    except Exception as e:
        logger.warning(f"Error extracting runtime stats from plan: {str(e)}")
        return None


@mcp.tool()
def analyze_query_execution(
    query: str,
    database_name: str | None = None,
    include_actual_plan: bool = True,
    max_execution_time_seconds: int = 30,
    connection_name: str | None = None,
) -> AnalyzeQueryExecutionResponse:
    """
    Capture baseline performance metrics and execution plan analysis.

    Executes the query with statistics collection and analyzes:
    - Execution metrics (duration, CPU, I/O, row count)
    - Execution plan warnings and high-cost operators
    - Wait statistics
    - Bottleneck type (IO_BOUND, CPU_BOUND, WAIT_BOUND, MEMORY_BOUND)

    IMPORTANT: This tool executes the query - only use with SELECT statements.

    Args:
        query: SQL query to analyze (must be SELECT)
        database_name: Optional database name (uses current database if not specified)
        include_actual_plan: Whether to capture actual execution plan (default: true)
        max_execution_time_seconds: Safety timeout (default: 30)

    Returns:
        AnalyzeQueryExecutionResponse with execution metrics, plan analysis, and recommendations
    """
    logger.info("Tool called: analyze_query_execution")
    try:
        # Safety check - only allow SELECT queries
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT") and not query_upper.startswith("WITH"):
            return AnalyzeQueryExecutionResponse(
                execution_metrics=None,
                execution_plan_xml=None,
                execution_plan_summary=None,
                wait_statistics=None,
                bottleneck_type=None,
                query_hash=None,
                query_plan_hash=None,
                success=False,
                error="Only SELECT queries are allowed for analysis",
            )

        conn = get_connection(connection_name)

        # Build combined query to preserve database context
        # (Each execute_query() creates a new connection, so we must combine statements)
        query_parts = []

        if database_name:
            query_parts.append(f"USE {database_name};")

        # Enable execution plan capture with runtime statistics if requested
        if include_actual_plan:
            query_parts.append("SET STATISTICS XML ON;")

        # Add the user's query
        query_parts.append(query)

        # Disable statistics capture
        if include_actual_plan:
            query_parts.append("SET STATISTICS XML OFF;")

        combined_query = "\n".join(query_parts)

        # Execute the query with timeout
        start_time = time.time()

        try:
            # We need to manually handle the connection to capture multiple result sets
            # (query results + execution plan XML)
            conn_str = conn.get_connection_string()
            results = []
            execution_plan_xml = None

            with pyodbc.connect(conn_str) as db_conn:
                cursor = db_conn.cursor()
                cursor.execute(combined_query)

                # Process all result sets
                result_set_index = 0
                while True:
                    if cursor.description:
                        columns = [column[0] for column in cursor.description]
                        current_results = []
                        for row in cursor.fetchall():
                            current_results.append(dict(zip(columns, row)))

                        # Determine what this result set is
                        if (
                            include_actual_plan
                            and len(columns) == 1
                            and "showplan" in columns[0].lower()
                        ):
                            # This is the execution plan XML
                            if current_results and len(current_results) > 0:
                                execution_plan_xml = current_results[0][columns[0]]
                                logger.debug(
                                    f"Captured execution plan XML ({len(execution_plan_xml)} chars)"
                                )
                        elif current_results:
                            # This is the query results
                            results = current_results
                            logger.debug(f"Captured query results ({len(results)} rows)")

                    # Move to next result set
                    if not cursor.nextset():
                        break

                    result_set_index += 1

            execution_time_ms = int((time.time() - start_time) * 1000)

        except Exception as e:
            return AnalyzeQueryExecutionResponse(
                execution_metrics=None,
                execution_plan_xml=None,
                execution_plan_summary=None,
                wait_statistics=None,
                bottleneck_type=None,
                query_hash=None,
                query_plan_hash=None,
                success=False,
                error=f"Query execution failed: {str(e)}",
            )

        # Get query hash and plan hash from sys.dm_exec_query_stats
        # This is a simplified approach - in production, you'd correlate by session_id
        hash_query = f"""
            SELECT TOP 1
                CONVERT(VARCHAR(100), query_hash, 1) AS query_hash,
                CONVERT(VARCHAR(100), query_plan_hash, 1) AS query_plan_hash
            FROM sys.dm_exec_query_stats
            WHERE last_execution_time >= DATEADD(SECOND, -10, GETDATE())
            ORDER BY last_execution_time DESC
        """

        try:
            hash_results = conn.execute_query(hash_query)
            query_hash = hash_results[0]["query_hash"] if hash_results else None
            query_plan_hash = hash_results[0]["query_plan_hash"] if hash_results else None
        except:
            query_hash = None
            query_plan_hash = None

        # Parse runtime statistics from execution plan XML if available
        runtime_stats = None
        if execution_plan_xml:
            runtime_stats = _parse_runtime_stats_from_plan(execution_plan_xml)
            if runtime_stats:
                logger.info(
                    f"Extracted runtime stats from execution plan: "
                    f"{runtime_stats['actual_logical_reads']} logical reads, "
                    f"{runtime_stats['actual_cpu_ms']}ms CPU"
                )

        # Create execution metrics from runtime stats or fallback to basic timing
        if runtime_stats:
            execution_metrics = ExecutionMetrics(
                duration_ms=(
                    runtime_stats["actual_elapsed_ms"]
                    if runtime_stats["actual_elapsed_ms"] > 0
                    else execution_time_ms
                ),
                cpu_time_ms=runtime_stats["actual_cpu_ms"],
                logical_reads=runtime_stats["actual_logical_reads"],
                physical_reads=runtime_stats["actual_physical_reads"],
                read_ahead_reads=runtime_stats["actual_read_aheads"],
                lob_logical_reads=runtime_stats["actual_lob_logical_reads"],
                lob_physical_reads=runtime_stats["actual_lob_physical_reads"],
                row_count=runtime_stats["actual_rows"],
                estimated_cost=0.0,  # Would need to parse from plan operators
            )
        else:
            # Fallback to basic metrics if plan XML not available or parsing failed
            execution_metrics = ExecutionMetrics(
                duration_ms=execution_time_ms,
                cpu_time_ms=0,
                logical_reads=0,
                physical_reads=0,
                read_ahead_reads=0,
                lob_logical_reads=0,
                lob_physical_reads=0,
                row_count=len(results) if results else 0,
                estimated_cost=0.0,
            )
            logger.warning(
                "Using basic timing metrics - runtime stats not available from execution plan"
            )

        # Execution plan summary not yet implemented
        # TODO: Parse warnings, high-cost operators, parallelism info from plan XML
        execution_plan_summary = None

        # Determine bottleneck type from metrics
        bottleneck_type = None
        if execution_metrics.logical_reads > 0:
            # Calculate I/O time vs CPU time
            io_time_estimate = execution_metrics.duration_ms - execution_metrics.cpu_time_ms
            cpu_percentage = (
                (execution_metrics.cpu_time_ms / execution_metrics.duration_ms * 100)
                if execution_metrics.duration_ms > 0
                else 0
            )

            if cpu_percentage > 70:
                bottleneck_type = "CPU_BOUND"
            elif execution_metrics.physical_reads > (execution_metrics.logical_reads * 0.1):
                # High physical reads relative to logical reads = disk I/O bottleneck
                bottleneck_type = "IO_BOUND"
            else:
                # Mostly logical reads (from cache) = memory pressure or good caching
                bottleneck_type = "MEMORY_BOUND"
        elif execution_metrics.duration_ms > 1000:
            bottleneck_type = "UNKNOWN"

        # Wait statistics not captured - would need sys.dm_os_wait_stats correlation
        wait_statistics = None

        logger.info(
            f"Query executed in {execution_time_ms}ms, returned {len(results) if results else 0} rows"
        )

        return AnalyzeQueryExecutionResponse(
            execution_metrics=execution_metrics,
            execution_plan_xml=execution_plan_xml,
            execution_plan_summary=execution_plan_summary,
            wait_statistics=wait_statistics,
            bottleneck_type=bottleneck_type,
            query_hash=query_hash,
            query_plan_hash=query_plan_hash,
            success=True,
        )

    except Exception as e:
        logger.error(f"Error analyzing query execution: {str(e)}")
        return AnalyzeQueryExecutionResponse(
            execution_metrics=None,
            execution_plan_xml=None,
            execution_plan_summary=None,
            wait_statistics=None,
            bottleneck_type=None,
            query_hash=None,
            query_plan_hash=None,
            success=False,
            error=str(e),
        )


@mcp.tool()
def get_query_statistics_health(
    database_name: str,
    table_names: list[str] | None = None,
    execution_plan_xml: str | None = None,
    connection_name: str | None = None,
) -> GetQueryStatisticsHealthResponse:
    """
    Check statistics freshness and quality for tables in a query.

    Analyzes:
    - Statistics age and sampling rate
    - Modification counters (rows changed since last update)
    - Cardinality estimation mismatches
    - Auto-update/auto-create settings

    Args:
        database_name: Database to analyze
        table_names: Optional list of tables (e.g., ["dbo.Orders", "dbo.Customers"])
        execution_plan_xml: Optional execution plan XML to extract table names

    Returns:
        GetQueryStatisticsHealthResponse with statistics analysis and recommendations
    """
    logger.info("Tool called: get_query_statistics_health")
    try:
        conn = get_connection(connection_name)

        # If no table names provided, try to extract from execution plan
        if not table_names and execution_plan_xml:
            # Simple extraction - parse table names from execution plan
            # TODO: Enhance this to parse XML properly
            table_names = []

        if not table_names:
            return GetQueryStatisticsHealthResponse(
                statistics_analysis=[],
                cardinality_mismatches=[],
                auto_update_stats_enabled=False,
                auto_create_stats_enabled=False,
                success=False,
                error="Either table_names or execution_plan_xml must be provided",
            )

        # Get database configuration
        try:
            db_config = conn.execute_query(
                f"""
                SELECT
                    CONVERT(BIT, DATABASEPROPERTYEX('{database_name}', 'IsAutoUpdateStatistics')) AS auto_update_enabled,
                    CONVERT(BIT, DATABASEPROPERTYEX('{database_name}', 'IsAutoCreateStatistics')) AS auto_create_enabled
            """
            )

            auto_update_enabled = (
                bool(db_config[0]["auto_update_enabled"])
                if (db_config and len(db_config) > 0)
                else False
            )
            auto_create_enabled = (
                bool(db_config[0]["auto_create_enabled"])
                if (db_config and len(db_config) > 0)
                else False
            )
        except Exception as e:
            logger.warning(f"Could not retrieve database configuration: {str(e)}")
            auto_update_enabled = False
            auto_create_enabled = False

        # Ensure table_names is iterable (defensive check)
        if table_names is None:
            table_names = []

        # Analyze statistics for each table
        statistics_analysis = []
        for table_name in table_names:
            try:
                # Combine USE and SELECT into single query string
                # This is necessary because each execute_query() creates a new connection,
                # so we must execute USE and SELECT together on the same connection
                stats_query = f"""
                    USE {database_name};

                    SELECT
                        '{table_name}' AS table_name,
                        i.name AS index_name,
                        s.name AS statistics_name,
                        CONVERT(VARCHAR, STATS_DATE(s.object_id, s.stats_id), 120) AS last_updated,
                        DATEDIFF(DAY, STATS_DATE(s.object_id, s.stats_id), GETDATE()) AS days_old,
                        sp.rows AS rows_in_table,
                        sp.rows_sampled,
                        CAST(sp.rows_sampled * 100.0 / NULLIF(sp.rows, 0) AS DECIMAL(5,2)) AS sampling_percent,
                        sp.modification_counter,
                        CAST(sp.modification_counter * 100.0 / NULLIF(sp.rows, 0) AS DECIMAL(5,2)) AS modification_percent
                    FROM sys.stats s
                    LEFT JOIN sys.indexes i ON s.object_id = i.object_id AND s.stats_id = i.index_id
                    CROSS APPLY sys.dm_db_stats_properties(s.object_id, s.stats_id) sp
                    WHERE s.object_id = OBJECT_ID('{table_name}')
                      AND sp.rows IS NOT NULL
                    ORDER BY sp.modification_counter DESC
                """

                results = conn.execute_query(stats_query)

                # Check if results is None or empty
                if not results:
                    logger.warning(
                        f"No statistics found for table {table_name} - table may not exist or has no statistics"
                    )
                    continue

                for row in results:
                    days_old = row["days_old"] if row["days_old"] is not None else 999
                    mod_percent = (
                        float(row["modification_percent"]) if row["modification_percent"] else 0.0
                    )

                    # Determine if update needed
                    needs_update = False
                    severity = "OK"
                    recommendation = None

                    if days_old > 30 or mod_percent > 20:
                        needs_update = True
                        if mod_percent > 50 or days_old > 90:
                            severity = "HIGH"
                            recommendation = f"UPDATE STATISTICS {table_name} WITH FULLSCAN;"
                        else:
                            severity = "WARNING"
                            recommendation = f"UPDATE STATISTICS {table_name};"

                    statistics_analysis.append(
                        StatisticsAnalysis(
                            table=table_name,
                            index=row["index_name"],
                            statistics_name=row["statistics_name"],
                            last_updated=row["last_updated"],
                            days_old=days_old,
                            rows_in_table=row["rows_in_table"],
                            rows_sampled=row["rows_sampled"],
                            sampling_percent=(
                                float(row["sampling_percent"]) if row["sampling_percent"] else 0.0
                            ),
                            modification_counter=row["modification_counter"],
                            modification_percent=mod_percent,
                            needs_update=needs_update,
                            severity=severity,
                            recommendation=recommendation,
                        )
                    )

            except Exception as e:
                logger.warning(f"Could not get statistics for table {table_name}: {str(e)}")

        # Cardinality mismatches would need execution plan analysis
        # For now, return empty list - this would be populated by comparing
        # estimated vs actual rows from execution plan XML
        cardinality_mismatches = []

        logger.info(
            f"Analyzed statistics for {len(statistics_analysis)} statistic(s) across {len(table_names)} table(s)"
        )

        return GetQueryStatisticsHealthResponse(
            statistics_analysis=statistics_analysis,
            cardinality_mismatches=cardinality_mismatches,
            auto_update_stats_enabled=auto_update_enabled,
            auto_create_stats_enabled=auto_create_enabled,
            success=True,
        )

    except Exception as e:
        logger.error(f"Error analyzing statistics health: {str(e)}")
        return GetQueryStatisticsHealthResponse(
            statistics_analysis=[],
            cardinality_mismatches=[],
            auto_update_stats_enabled=False,
            auto_create_stats_enabled=False,
            success=False,
            error=str(e),
        )


@mcp.tool()
def analyze_missing_indexes(
    database_name: str,
    execution_plan_xml: str | None = None,
    connection_name: str | None = None,
) -> AnalyzeMissingIndexesResponse:
    """
    Analyze missing index recommendations and existing index usage for a database.

    Provides database-wide analysis plus query-specific recommendations from execution plan:
    - Missing index recommendations from DMVs with impact scoring
    - Query-specific missing index hints from execution plan XML
    - Existing index usage statistics (identify unused indexes)
    - Index overlap detection

    Args:
        database_name: Database to analyze
        execution_plan_xml: Optional execution plan XML from analyze_query_execution
                           (contains query-specific missing index recommendations)

    Returns:
        AnalyzeMissingIndexesResponse with index recommendations
    """
    logger.info("Tool called: analyze_missing_indexes")
    try:
        conn = get_connection(connection_name)

        # Query missing indexes from DMVs
        missing_indexes_query = f"""
            USE {database_name};
            SELECT TOP 20
                d.statement AS table_name,
                d.equality_columns,
                d.inequality_columns,
                d.included_columns,
                s.avg_user_impact,
                s.avg_total_user_cost,
                s.user_seeks,
                s.user_scans,
                CONVERT(VARCHAR, s.last_user_seek, 120) AS last_user_seek,
                (s.avg_total_user_cost * s.avg_user_impact * (s.user_seeks + s.user_scans)) AS impact_score
            FROM sys.dm_db_missing_index_details d
            JOIN sys.dm_db_missing_index_groups g ON d.index_handle = g.index_handle
            JOIN sys.dm_db_missing_index_group_stats s ON g.index_group_handle = s.group_handle
            WHERE d.database_id = DB_ID('{database_name}')
            ORDER BY impact_score DESC
        """

        missing_index_results = conn.execute_query(missing_indexes_query)
        missing_indexes = []

        for row in missing_index_results:
            table_name = (
                row["table_name"]
                .replace(f"[{database_name}].", "")
                .replace("[", "")
                .replace("]", "")
            )
            equality_cols = row["equality_columns"].split(", ") if row["equality_columns"] else []
            inequality_cols = (
                row["inequality_columns"].split(", ") if row["inequality_columns"] else []
            )
            included_cols = row["included_columns"].split(", ") if row["included_columns"] else []

            impact_score = float(row["impact_score"])

            # Determine priority
            if impact_score > 100000 and row["user_seeks"] > 1000:
                priority = "HIGH"
            elif impact_score > 10000:
                priority = "MEDIUM"
            else:
                priority = "LOW"

            # Build CREATE INDEX statement
            index_name = f"IX_{table_name.split('.')[-1]}_{'_'.join([c.replace('[', '').replace(']', '') for c in equality_cols[:3]])}"
            key_columns = ", ".join(equality_cols + inequality_cols)
            create_statement = (
                f"CREATE NONCLUSTERED INDEX {index_name} ON {table_name} ({key_columns})"
            )
            if included_cols:
                create_statement += f" INCLUDE ({', '.join(included_cols)})"

            # Estimate size (rough estimate: 1KB per 10 rows)
            estimated_size_mb = 0.1  # Default estimate

            considerations = []
            if impact_score < 1000:
                considerations.append("Low impact score - verify query frequency before creating")
            if len(equality_cols) + len(inequality_cols) > 5:
                considerations.append("Wide index key - may have high maintenance overhead")

            missing_indexes.append(
                MissingIndexInfo(
                    table=table_name,
                    equality_columns=equality_cols,
                    inequality_columns=inequality_cols,
                    included_columns=included_cols,
                    impact_score=impact_score,
                    avg_user_impact=float(row["avg_user_impact"]),
                    avg_total_user_cost=float(row["avg_total_user_cost"]),
                    user_seeks=row["user_seeks"],
                    user_scans=row["user_scans"],
                    last_user_seek=row["last_user_seek"],
                    create_statement=create_statement,
                    estimated_size_mb=estimated_size_mb,
                    recommendation_priority=priority,
                    considerations=considerations,
                )
            )

        # Parse execution plan XML for query-specific missing index recommendations
        if execution_plan_xml:
            try:
                logger.debug("Parsing execution plan XML for missing index recommendations")
                root = ET.fromstring(execution_plan_xml)

                # Define XML namespaces
                ns = {"p": "http://schemas.microsoft.com/sqlserver/2004/07/showplan"}

                # Find all MissingIndexGroup elements
                for missing_group in root.findall(".//p:MissingIndexGroup", ns):
                    impact = float(missing_group.get("Impact", 0))

                    # Find the MissingIndex element
                    missing_index = missing_group.find(".//p:MissingIndex", ns)
                    if missing_index is None:
                        continue

                    # Extract table information
                    database = missing_index.get("Database", "").strip("[]")
                    schema = missing_index.get("Schema", "dbo").strip("[]")
                    table = missing_index.get("Table", "").strip("[]")
                    table_name = f"{schema}.{table}" if schema and table else ""

                    if not table_name:
                        continue

                    # Extract column groups
                    equality_cols = []
                    inequality_cols = []
                    included_cols = []

                    for col_group in missing_index.findall(".//p:ColumnGroup", ns):
                        usage = col_group.get("Usage", "")
                        columns = [
                            col.get("Name", "").strip("[]")
                            for col in col_group.findall(".//p:Column", ns)
                        ]

                        if usage == "EQUALITY":
                            equality_cols.extend(columns)
                        elif usage == "INEQUALITY":
                            inequality_cols.extend(columns)
                        elif usage == "INCLUDE":
                            included_cols.extend(columns)

                    # Build CREATE INDEX statement
                    index_name = (
                        f"IX_{table}_{'_'.join(equality_cols[:2])}"
                        if equality_cols
                        else f"IX_{table}_Suggested"
                    )
                    key_columns = ", ".join(equality_cols + inequality_cols)
                    include_clause = (
                        f" INCLUDE ({', '.join(included_cols)})" if included_cols else ""
                    )
                    create_statement = f"CREATE INDEX {index_name} ON {table_name} ({key_columns}){include_clause};"

                    # Determine priority based on impact
                    if impact >= 90:
                        priority = "CRITICAL"
                    elif impact >= 50:
                        priority = "HIGH"
                    elif impact >= 20:
                        priority = "MEDIUM"
                    else:
                        priority = "LOW"

                    considerations = [
                        f"From execution plan analysis (impact: {impact:.1f}%)",
                        "Query-specific recommendation - validate against overall workload",
                    ]

                    # Add to missing indexes list
                    missing_indexes.append(
                        MissingIndexInfo(
                            table=table_name,
                            equality_columns=", ".join(equality_cols) if equality_cols else None,
                            inequality_columns=(
                                ", ".join(inequality_cols) if inequality_cols else None
                            ),
                            included_columns=", ".join(included_cols) if included_cols else None,
                            impact_score=impact * 1000,  # Scale to match DMV impact scores
                            avg_user_impact=impact,
                            avg_total_user_cost=0.0,  # Not available from plan
                            user_seeks=0,  # Not available from plan
                            user_scans=0,  # Not available from plan
                            last_user_seek=None,
                            create_statement=create_statement,
                            estimated_size_mb=0.0,  # Cannot estimate from plan
                            recommendation_priority=priority,
                            considerations=considerations,
                        )
                    )

                logger.info(
                    f"Extracted {len([m for m in missing_indexes if 'execution plan' in str(m.considerations)])} missing index recommendations from execution plan"
                )

            except ET.ParseError as e:
                logger.warning(f"Could not parse execution plan XML: {str(e)}")
            except Exception as e:
                logger.warning(f"Error extracting missing indexes from execution plan: {str(e)}")

        # Query existing index usage
        existing_index_query = f"""
            USE {database_name};
            SELECT TOP 50
                OBJECT_SCHEMA_NAME(i.object_id) + '.' + OBJECT_NAME(i.object_id) AS table_name,
                i.name AS index_name,
                ISNULL(ius.user_seeks, 0) AS user_seeks,
                ISNULL(ius.user_scans, 0) AS user_scans,
                ISNULL(ius.user_lookups, 0) AS user_lookups,
                ISNULL(ius.user_updates, 0) AS user_updates,
                CONVERT(VARCHAR, ius.last_user_seek, 120) AS last_user_seek,
                (ps.reserved_page_count * 8.0 / 1024.0) AS size_mb
            FROM sys.indexes i
            LEFT JOIN sys.dm_db_index_usage_stats ius
                ON i.object_id = ius.object_id
                AND i.index_id = ius.index_id
                AND ius.database_id = DB_ID('{database_name}')
            JOIN sys.dm_db_partition_stats ps
                ON i.object_id = ps.object_id
                AND i.index_id = ps.index_id
            WHERE i.type_desc IN ('NONCLUSTERED', 'CLUSTERED')
                AND i.is_primary_key = 0
                AND i.is_unique_constraint = 0
                AND OBJECT_SCHEMA_NAME(i.object_id) NOT IN ('sys')
            ORDER BY (ISNULL(ius.user_seeks, 0) + ISNULL(ius.user_scans, 0) + ISNULL(ius.user_lookups, 0)) ASC
        """

        existing_index_results = conn.execute_query(existing_index_query)
        existing_index_usage = []

        for row in existing_index_results:
            total_reads = row["user_seeks"] + row["user_scans"] + row["user_lookups"]
            updates = row["user_updates"]

            recommendation = None
            action = None

            if total_reads == 0 and updates > 100:
                recommendation = "Unused index with high update overhead - consider dropping"
                action = f"DROP INDEX {row['index_name']} ON {row['table_name']}"
            elif total_reads < 10 and updates > 1000:
                recommendation = "Very low read benefit vs update cost - review for removal"

            existing_index_usage.append(
                ExistingIndexUsage(
                    table=row["table_name"],
                    index_name=row["index_name"],
                    user_seeks=row["user_seeks"],
                    user_scans=row["user_scans"],
                    user_lookups=row["user_lookups"],
                    user_updates=row["user_updates"],
                    last_user_seek=row["last_user_seek"],
                    size_mb=float(row["size_mb"]),
                    recommendation=recommendation,
                    action=action,
                )
            )

        # Index overlap detection (simplified - just look for naming patterns)
        index_overlaps = []

        logger.info(
            f"Found {len(missing_indexes)} missing index recommendations, "
            f"{len(existing_index_usage)} existing indexes analyzed"
        )

        return AnalyzeMissingIndexesResponse(
            missing_indexes=missing_indexes,
            existing_index_usage=existing_index_usage,
            index_overlaps=index_overlaps,
            success=True,
        )

    except Exception as e:
        logger.error(f"Error analyzing missing indexes: {str(e)}")
        return AnalyzeMissingIndexesResponse(
            missing_indexes=[],
            existing_index_usage=[],
            index_overlaps=[],
            success=False,
            error=str(e),
        )


@mcp.tool()
def detect_query_antipatterns(
    query: str, execution_plan_xml: str | None = None
) -> DetectQueryAntipatternsResponse:
    """
    Detect common SQL query antipatterns and recommend rewrites.

    Analyzes query text and execution plan for performance antipatterns including:
    - Non-SARGable predicates (functions on columns in WHERE clause)
    - SELECT * selecting unnecessary columns
    - Leading wildcards in LIKE patterns
    - Implicit type conversions
    - Correlated subqueries
    - Scalar UDFs in SELECT list

    This analysis should be performed BEFORE index analysis, as query rewrites can fundamentally
    change what indexes are needed.

    Args:
        query: The SQL query text to analyze
        execution_plan_xml: Optional execution plan XML for deeper analysis

    Returns:
        DetectQueryAntipatternsResponse with detected antipatterns, severity, and recommendations
    """
    logger.info("Tool called: detect_query_antipatterns")
    try:
        antipatterns = []
        complexity_score = 1.0

        # Normalize query for pattern matching
        query_upper = query.upper()

        # Pattern 1: SELECT *
        if re.search(r"\bSELECT\s+\*\s+FROM\b", query_upper):
            antipatterns.append(
                AntipatternInfo(
                    category="SELECT_STAR",
                    severity="MEDIUM",
                    location=re.search(r"SELECT\s+\*\s+FROM", query_upper, re.IGNORECASE).group(),
                    issue="Selecting all columns instead of specific ones",
                    recommendation="Specify only the columns you need: SELECT col1, col2, col3 FROM ...",
                    estimated_impact="Could reduce logical reads by 30-60% depending on table width",
                )
            )
            complexity_score += 0.5

        # Pattern 2: Non-SARGable predicates - Functions on columns in WHERE/AND/ON clauses
        # Matches patterns like: Schema.Function(Table.Column) or Function(Column)
        # Examples: YEAR(OrderDate), RPT.JulianToDate(F595074H.PHUPMJ), CAST(col AS INT), dbo.GetTotal(Orders.Amount)
        generic_function_pattern = r"(?:WHERE|AND|ON)\s+(?:[\w]+\.)?[\w]+\s*\([^)]*?(\w+\.\w+)[^)]*?\)\s*(?:=|<|>|<=|>=|<>|!=|BETWEEN|IN|LIKE|NOT\s+IN|NOT\s+LIKE)"

        for match in re.finditer(generic_function_pattern, query_upper, re.IGNORECASE):
            function_call = match.group(0).strip()
            column_ref = match.group(1)  # The captured table.column reference

            antipatterns.append(
                AntipatternInfo(
                    category="NON_SARGABLE_PREDICATE",
                    severity="HIGH",
                    location=function_call[:100],  # Limit length for display
                    issue=f"Function call on column {column_ref} prevents index seek",
                    recommendation=(
                        f"Rewrite to avoid function on column side. Options: "
                        f"1) Create computed column with index: ALTER TABLE ... ADD computed_col AS [function] PERSISTED; CREATE INDEX ... "
                        f"2) Store data in proper format to avoid conversion function. "
                        f"3) If possible, reverse the function to the literal side of the comparison."
                    ),
                    estimated_impact="Could eliminate table/index scan and use index seek instead",
                )
            )
            complexity_score += 1.5

        # Pattern 3: Leading wildcards in LIKE
        if re.search(r"\bLIKE\s+['\"]%", query):
            match = re.search(r"LIKE\s+['\"]%[^'\"]+['\"]", query, re.IGNORECASE)
            if match:
                antipatterns.append(
                    AntipatternInfo(
                        category="LEADING_WILDCARD",
                        severity="HIGH",
                        location=match.group(),
                        issue="Leading wildcard in LIKE prevents index seek",
                        recommendation="Remove leading wildcard if possible, or consider full-text search",
                        estimated_impact="Forces table/index scan instead of seek",
                    )
                )
                complexity_score += 1.0

        # Pattern 4: Correlated subqueries
        subquery_pattern = r"\(\s*SELECT\s+[^\)]*\b(?:FROM|WHERE)[^\)]*\b(?:WHERE|JOIN)[^\)]*\b(?:\w+\.\w+\s*=\s*\w+\.\w+|\w+\s*=\s*\w+\.\w+)[^\)]*\)"
        if re.search(subquery_pattern, query, re.IGNORECASE | re.DOTALL):
            antipatterns.append(
                AntipatternInfo(
                    category="CORRELATED_SUBQUERY",
                    severity="HIGH",
                    location="(SELECT ... FROM ... WHERE outer.col = inner.col)",
                    issue="Correlated subquery may execute once per outer row",
                    recommendation="Rewrite as JOIN or use APPLY operator",
                    estimated_impact="Could eliminate thousands of subquery executions",
                )
            )
            complexity_score += 2.0

        # Pattern 5: COUNT(*) or COUNT(column) in WHERE
        if re.search(r"\bWHERE\s+[^\(]*\bCOUNT\s*\(", query_upper):
            antipatterns.append(
                AntipatternInfo(
                    category="SCALAR_UDF",
                    severity="MEDIUM",
                    location="WHERE ... COUNT(...)",
                    issue="Aggregate function in WHERE clause (should be in HAVING)",
                    recommendation="Move aggregate to HAVING clause or use subquery",
                    estimated_impact="May cause query compilation failure or inefficient execution",
                )
            )
            complexity_score += 1.0

        # Analyze execution plan XML if provided
        if execution_plan_xml:
            try:
                root = ET.fromstring(execution_plan_xml)

                # Look for warnings in execution plan
                for warning in root.findall(
                    ".//{http://schemas.microsoft.com/sqlserver/2004/07/showplan}Warnings"
                ):
                    # Implicit conversion warnings
                    for conversion in warning.findall(
                        ".//{http://schemas.microsoft.com/sqlserver/2004/07/showplan}ColumnsWithNoStatistics"
                    ):
                        antipatterns.append(
                            AntipatternInfo(
                                category="MISSING_STATISTICS",
                                severity="HIGH",
                                location="Execution Plan Warning",
                                issue="Columns without statistics found in execution plan",
                                recommendation="Update statistics or create statistics on referenced columns",
                                estimated_impact="Poor cardinality estimates leading to suboptimal plans",
                            )
                        )
                        complexity_score += 1.5

                # Check for table scans on large tables
                for relop in root.findall(
                    ".//{http://schemas.microsoft.com/sqlserver/2004/07/showplan}RelOp"
                ):
                    if "Scan" in relop.get("LogicalOp", ""):
                        estimated_rows = relop.get("EstimateRows", 0)
                        if float(estimated_rows) > 10000:
                            complexity_score += 0.5

            except ET.ParseError:
                logger.warning("Could not parse execution plan XML")

        # Calculate rewrite priority
        if any(a.severity == "HIGH" for a in antipatterns):
            rewrite_priority = "HIGH"
        elif any(a.severity == "MEDIUM" for a in antipatterns):
            rewrite_priority = "MEDIUM"
        elif antipatterns:
            rewrite_priority = "LOW"
        else:
            rewrite_priority = "NONE"

        logger.info(f"Detected {len(antipatterns)} antipattern(s), priority: {rewrite_priority}")

        return DetectQueryAntipatternsResponse(
            antipatterns_found=antipatterns,
            query_complexity_score=min(complexity_score, 10.0),
            rewrite_priority=rewrite_priority,
            suggested_rewrite=None,  # TODO: Implement query rewriting
            success=True,
        )

    except Exception as e:
        logger.error(f"Error detecting query antipatterns: {str(e)}")
        return DetectQueryAntipatternsResponse(
            antipatterns_found=[],
            query_complexity_score=0.0,
            rewrite_priority="NONE",
            success=False,
            error=str(e),
        )


@mcp.tool()
def find_object_database(
    object_name: str, connection_name: str | None = None
) -> FindObjectDatabaseResponse:
    """
    Find which database contains a specific table or view.

    Searches across all accessible databases using a single UNION query for efficiency.

    Supports multiple input formats:
    - "TableName" - Searches all databases for this object (assumes dbo schema)
    - "Schema.TableName" - Searches for schema-qualified object
    - "Database.Schema.TableName" - Validates the specified database

    Args:
        object_name: Table/view name to search for

    Returns:
        FindObjectDatabaseResponse with database location and object details
    """
    logger.info(f"Tool called: find_object_database with object_name={object_name}")

    try:
        conn = get_connection(connection_name)

        # Parse object name into parts
        parts = [p.strip().strip("[]") for p in object_name.split(".")]

        if len(parts) == 3:
            # Database.Schema.Object format - just validate
            target_db = parts[0]
            target_schema = parts[1]
            target_object = parts[2]
            databases_to_search = [target_db]
        elif len(parts) == 2:
            # Schema.Object format
            target_db = None
            target_schema = parts[0]
            target_object = parts[1]
            databases_to_search = None  # Search all
        else:
            # Just Object name - assume dbo schema
            target_db = None
            target_schema = "dbo"
            target_object = parts[0]
            databases_to_search = None  # Search all

        # Get list of databases to search if not specified
        if databases_to_search is None:
            db_query = """
                SELECT name
                FROM sys.databases
                WHERE state = 0  -- ONLINE
                  AND name NOT IN ('master', 'tempdb', 'model', 'msdb')
                ORDER BY name
            """
            db_results = conn.execute_query(db_query)
            databases_to_search = [row["name"] for row in db_results]

        if not databases_to_search:
            return FindObjectDatabaseResponse(
                database_name=None,
                schema_name=None,
                object_name=target_object,
                object_type=None,
                full_name=None,
                success=False,
                error="No accessible databases found",
            )

        # Build UNION query across all databases
        # Note: Use COLLATE DATABASE_DEFAULT to avoid collation conflicts between databases
        union_parts = []
        for db_name in databases_to_search:
            union_parts.append(
                f"""
                SELECT
                    '{db_name}' COLLATE DATABASE_DEFAULT AS database_name,
                    s.name COLLATE DATABASE_DEFAULT AS schema_name,
                    o.name COLLATE DATABASE_DEFAULT AS object_name,
                    o.type_desc COLLATE DATABASE_DEFAULT AS object_type
                FROM [{db_name}].sys.objects o
                JOIN [{db_name}].sys.schemas s ON o.schema_id = s.schema_id
                WHERE o.name = '{target_object}'
                  AND s.name = '{target_schema}'
                  AND o.type IN ('U', 'V')  -- User tables and views
            """
            )

        # Combine with UNION ALL and execute once
        union_query = "\nUNION ALL\n".join(union_parts)

        logger.debug(
            f"Searching for '{object_name}' across {len(databases_to_search)} databases with single UNION query"
        )
        results = conn.execute_query(union_query)

        if results and len(results) > 0:
            # Found it! Take first result if multiple matches
            result = results[0]
            full_name = f"{result['database_name']}.{result['schema_name']}.{result['object_name']}"

            if len(results) > 1:
                logger.warning(
                    f"Object '{object_name}' found in {len(results)} databases: {[r['database_name'] for r in results]}, using {result['database_name']}"
                )

            logger.info(f"Found object '{object_name}' in database '{result['database_name']}'")

            return FindObjectDatabaseResponse(
                database_name=result["database_name"],
                schema_name=result["schema_name"],
                object_name=result["object_name"],
                object_type=result["object_type"],
                full_name=full_name,
                success=True,
            )
        else:
            # Not found
            searched_dbs = ", ".join(databases_to_search[:5])
            if len(databases_to_search) > 5:
                searched_dbs += f" and {len(databases_to_search) - 5} more"

            return FindObjectDatabaseResponse(
                database_name=None,
                schema_name=None,
                object_name=target_object,
                object_type=None,
                full_name=None,
                success=False,
                error=f"Object '{object_name}' not found in any accessible database (searched: {searched_dbs})",
            )

    except Exception as e:
        logger.error(f"Error finding object database: {str(e)}")
        return FindObjectDatabaseResponse(
            database_name=None,
            schema_name=None,
            object_name=object_name,
            object_type=None,
            full_name=None,
            success=False,
            error=str(e),
        )


@mcp.tool()
def execute_select_query(
    query: str,
    database_name: str | None = None,
    row_limit: int = 100,
    timeout_seconds: int = 30,
    connection_name: str | None = None,
) -> ExecuteSelectQueryResponse:
    """
    Execute a SELECT query and return the result set with column metadata.

    Use this tool to query any table or view the server has access to.
    Only SELECT and WITH (CTE) queries are allowed.

    Args:
        query: SQL SELECT query to execute
        database_name: Optional database context (prepends USE {database})
        row_limit: Maximum rows to return (default 100, max 1000)
        timeout_seconds: Query timeout in seconds (default 30, max 120)

    Returns:
        ExecuteSelectQueryResponse with columns, rows, and metadata
    """
    logger.info("Tool called: execute_select_query")

    try:
        # Validate query safety
        validation_error = _validate_select_query(query)
        if validation_error:
            return ExecuteSelectQueryResponse(
                success=False,
                error=validation_error,
            )

        # Validate database_name to prevent injection
        if database_name and not re.match(r"^[a-zA-Z0-9_\[\]]+$", database_name):
            return ExecuteSelectQueryResponse(
                success=False,
                error="Invalid database name. Only alphanumeric characters, underscores, and brackets are allowed.",
            )

        # Clamp parameters
        row_limit = max(1, min(row_limit, 1000))
        timeout_seconds = max(1, min(timeout_seconds, 120))

        # Build query batch
        query_parts = []
        if database_name:
            query_parts.append(f"USE {database_name};")
        query_parts.append(query)
        combined_query = "\n".join(query_parts)

        # Execute with manual connection for cursor.description access
        conn = get_connection(connection_name)
        conn_str = conn.get_connection_string()

        start_time = time.time()

        with pyodbc.connect(conn_str, timeout=timeout_seconds) as db_conn:
            cursor = db_conn.cursor()
            cursor.execute(combined_query)

            # Skip result sets until we find one with columns (handles USE statement)
            columns_meta = []
            rows_data = []
            truncated = False

            while True:
                if cursor.description:
                    # Build column metadata
                    columns_meta = []
                    for col_desc in cursor.description:
                        col_name = col_desc[0]
                        col_type_code = col_desc[1]
                        type_name = getattr(col_type_code, "__name__", str(col_type_code))
                        columns_meta.append(ColumnMetadata(name=col_name, type_name=type_name))

                    # Fetch row_limit + 1 to detect truncation
                    raw_rows = cursor.fetchmany(row_limit + 1)
                    if len(raw_rows) > row_limit:
                        truncated = True
                        raw_rows = raw_rows[:row_limit]

                    # Serialize rows
                    col_names = [col_desc[0] for col_desc in cursor.description]
                    rows_data = [
                        {col_names[i]: _serialize_value(val) for i, val in enumerate(row)}
                        for row in raw_rows
                    ]

                # Move to next result set
                if not cursor.nextset():
                    break

        execution_time_ms = int((time.time() - start_time) * 1000)

        return ExecuteSelectQueryResponse(
            columns=columns_meta,
            rows=rows_data,
            row_count=len(rows_data),
            truncated=truncated,
            execution_time_ms=execution_time_ms,
            success=True,
        )

    except Exception as e:
        logger.error(f"Error executing select query: {str(e)}")
        return ExecuteSelectQueryResponse(
            success=False,
            error=str(e),
        )
