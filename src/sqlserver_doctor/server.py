"""SQL Server Doctor MCP Server - Main server implementation."""

from typing import Any
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from sqlserver_doctor.utils.connection import get_connection
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


# Tools
@mcp.tool()
def get_server_version() -> ServerVersionResponse:
    """
    Get SQL Server version and instance information.

    Returns detailed version information about the connected SQL Server instance,
    including the version string and server name.
    """
    logger.info("Tool called: get_server_version")
    try:
        conn = get_connection()
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
def list_databases() -> DatabaseListResponse:
    """
    List all databases on the SQL Server instance.

    Returns information about all databases including name, state, recovery model,
    and compatibility level. This is useful for understanding the server's database
    landscape and identifying databases that may need attention.
    """
    logger.info("Tool called: list_databases")
    try:
        conn = get_connection()
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
def get_active_sessions() -> ActiveSessionsResponse:
    """
    Get currently active sessions and queries on the SQL Server instance.

    Returns detailed information about active sessions including currently executing
    SQL text, CPU usage, wait statistics, blocking information, and client details.
    This is useful for monitoring server activity, identifying performance issues,
    and detecting blocking situations.

    Filters out system databases (master, msdb) and the monitoring query itself.
    """
    logger.info("Tool called: get_active_sessions")
    try:
        conn = get_connection()
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
