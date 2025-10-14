"""SQL Server connection management utilities."""

import os
from typing import Any
import pyodbc
from dotenv import load_dotenv

from .logger import setup_logger

# Load environment variables
load_dotenv()

# Setup logger
logger = setup_logger("sqlserver_doctor.connection")


class SQLServerConnection:
    """Manages SQL Server database connections."""

    def __init__(self) -> None:
        """Initialize connection configuration from environment variables."""
        self.host = os.getenv("SQL_SERVER_HOST", "localhost")
        self.port = os.getenv("SQL_SERVER_PORT", "1433")
        self.database = os.getenv("SQL_SERVER_DATABASE", "master")
        self.user = os.getenv("SQL_SERVER_USER", "")
        self.password = os.getenv("SQL_SERVER_PASSWORD", "")
        self.driver = os.getenv("SQL_SERVER_DRIVER", "ODBC Driver 17 for SQL Server")
        self.trust_cert = os.getenv("SQL_SERVER_TRUST_CERT", "yes")
        self.encrypt = os.getenv("SQL_SERVER_ENCRYPT", "no")

        auth_type = "SQL Server Authentication" if self.user else "Windows Authentication"
        logger.info(
            f"Initialized connection config: host={self.host}, port={self.port}, "
            f"database={self.database}, auth_type={auth_type}"
        )

    def get_connection_string(self) -> str:
        """Build the connection string based on configuration."""
        conn_str_parts = [
            f"DRIVER={{{self.driver}}}",
            f"SERVER={self.host},{self.port}",
            f"DATABASE={self.database}",
            f"TrustServerCertificate={self.trust_cert}",
            f"Encrypt={self.encrypt}",
        ]

        if self.user and self.password:
            # SQL Server Authentication
            conn_str_parts.extend([f"UID={self.user}", f"PWD={self.password}"])
        else:
            # Windows Authentication
            conn_str_parts.append("Trusted_Connection=yes")

        return ";".join(conn_str_parts)

    def execute_query(self, query: str) -> list[dict[str, Any]]:
        """
        Execute a SQL query and return results as a list of dictionaries.

        Args:
            query: SQL query to execute

        Returns:
            List of dictionaries where each dict represents a row

        Raises:
            pyodbc.Error: If there's a database connection or query error
        """
        conn_str = self.get_connection_string()

        # Log query (truncate if too long)
        query_preview = query.strip()[:100].replace("\n", " ")
        logger.debug(f"Executing query: {query_preview}...")

        try:
            logger.info(f"Connecting to SQL Server: {self.host}:{self.port}/{self.database}")
            with pyodbc.connect(conn_str) as conn:
                logger.info("Connection established successfully")
                cursor = conn.cursor()
                cursor.execute(query)

                # Get column names
                columns = [column[0] for column in cursor.description]

                # Fetch all rows and convert to list of dicts
                results = []
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))

                logger.info(f"Query executed successfully, returned {len(results)} row(s)")
                return results

        except pyodbc.Error as e:
            logger.error(f"Database error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise

    def test_connection(self) -> dict[str, Any]:
        """
        Test the database connection.

        Returns:
            Dictionary with connection status and server info
        """
        logger.info("Testing database connection...")
        try:
            result = self.execute_query("SELECT @@VERSION AS Version, @@SERVERNAME AS ServerName")
            logger.info("Connection test successful")
            return {"success": True, "message": "Connection successful", "server_info": result[0]}
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return {"success": False, "message": f"Connection failed: {str(e)}"}


# Global connection instance
_connection: SQLServerConnection | None = None


def get_connection() -> SQLServerConnection:
    """Get or create the global SQL Server connection instance."""
    global _connection
    if _connection is None:
        logger.info("Creating new SQL Server connection instance")
        _connection = SQLServerConnection()
    else:
        logger.debug("Reusing existing SQL Server connection instance")
    return _connection
