"""Main entry point for SQL Server Doctor MCP Server."""

from sqlserver_doctor.server import mcp


def main() -> None:
    """Run the SQL Server Doctor MCP server."""
    # Run the server with stdio transport (default for MCP servers)
    mcp.run()


if __name__ == "__main__":
    main()
