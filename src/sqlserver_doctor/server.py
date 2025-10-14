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
