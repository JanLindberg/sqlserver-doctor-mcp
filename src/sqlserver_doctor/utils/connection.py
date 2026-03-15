"""SQL Server connection management utilities."""

import json
import os
from pathlib import Path
from typing import Any

import pyodbc
from dotenv import find_dotenv, load_dotenv

from .logger import setup_logger

# Load environment variables and determine project root.
# find_dotenv() searches upward from this file's directory, so it finds .env
# in the project root regardless of the process's working directory.
_dotenv_path = find_dotenv()
load_dotenv(_dotenv_path)
_project_root = Path(_dotenv_path).parent if _dotenv_path else Path(__file__).resolve().parents[3]

# Setup logger
logger = setup_logger("sqlserver_doctor.connection")


class SQLServerConnection:
    """Manages SQL Server database connections."""

    def __init__(
        self,
        *,
        name: str = "default",
        host: str | None = None,
        port: str | int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        driver: str | None = None,
        trust_cert: str | None = None,
        encrypt: str | None = None,
    ) -> None:
        """Initialize connection configuration.

        When explicit params are provided, they are used directly.
        When params are None, falls back to environment variables.
        """
        self.name = name
        self.host = host if host is not None else os.getenv("SQL_SERVER_HOST", "localhost")
        self.port = str(port) if port is not None else os.getenv("SQL_SERVER_PORT", "1433")
        self.database = (
            database if database is not None else os.getenv("SQL_SERVER_DATABASE", "master")
        )
        self.user = user if user is not None else os.getenv("SQL_SERVER_USER", "")
        self.password = password if password is not None else os.getenv("SQL_SERVER_PASSWORD", "")
        self.driver = (
            driver
            if driver is not None
            else os.getenv("SQL_SERVER_DRIVER", "ODBC Driver 17 for SQL Server")
        )
        self.trust_cert = (
            trust_cert if trust_cert is not None else os.getenv("SQL_SERVER_TRUST_CERT", "yes")
        )
        self.encrypt = encrypt if encrypt is not None else os.getenv("SQL_SERVER_ENCRYPT", "no")

        auth_type = "SQL Server Authentication" if self.user else "Windows Authentication"
        logger.info(
            f"Initialized connection '{self.name}': host={self.host}, port={self.port}, "
            f"database={self.database}, auth_type={auth_type}"
        )

    def get_connection_string(self) -> str:
        """Build the connection string based on configuration."""
        server_part = self.host if not self.port else f"{self.host},{self.port}"
        conn_str_parts = [
            f"DRIVER={{{self.driver}}}",
            f"SERVER={server_part}",
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

                # Handle multiple result sets (e.g., from "USE database; SELECT ...")
                # Loop through all result sets and return the last non-empty one
                results = []
                while True:
                    # Check if this result set has columns
                    if cursor.description:
                        columns = [column[0] for column in cursor.description]

                        # Fetch all rows from this result set
                        current_results = []
                        for row in cursor.fetchall():
                            current_results.append(dict(zip(columns, row)))

                        # Keep the last non-empty result set
                        if current_results:
                            results = current_results
                            logger.debug(f"Found result set with {len(current_results)} row(s)")

                    # Move to next result set
                    if not cursor.nextset():
                        break

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


# Connection registry
_connections: dict[str, SQLServerConnection] = {}
_active_connection_name: str | None = None


def load_connections_from_json(path: str = "connections.json") -> None:
    """Load named connections from a JSON config file.

    Expected format:
    {
        "default": "connection_name",
        "connections": {
            "connection_name": {
                "host": "...", "port": 1433, "database": "master", ...
            }
        }
    }

    Silently skips if the file does not exist.
    Relative paths are resolved against the project root (where .env lives).
    """
    global _active_connection_name

    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = _project_root / config_path
    if not config_path.is_file():
        logger.debug(f"No connections config file found at {path}, will use env vars")
        return

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load connections config from {path}: {e}")
        return

    connections_dict = config.get("connections", {})
    if not connections_dict:
        logger.warning(f"No connections defined in {path}")
        return

    for name, conn_config in connections_dict.items():
        _connections[name] = SQLServerConnection(
            name=name,
            host=conn_config.get("host"),
            port=conn_config.get("port"),
            database=conn_config.get("database"),
            user=conn_config.get("user"),
            password=conn_config.get("password"),
            driver=conn_config.get("driver"),
            trust_cert=conn_config.get("trust_cert"),
            encrypt=conn_config.get("encrypt"),
        )

    # Set active connection from the "default" field
    default_name = config.get("default")
    if default_name:
        if default_name in _connections:
            _active_connection_name = default_name
            logger.info(f"Active connection set to '{default_name}' from config")
        else:
            logger.warning(
                f"Default connection '{default_name}' not found in connections. "
                f"Available: {list(_connections.keys())}"
            )

    logger.info(f"Loaded {len(_connections)} connection(s) from {path}")


def set_active_connection_name(name: str) -> None:
    """Set the active connection by name."""
    global _active_connection_name

    if name not in _connections:
        available = list(_connections.keys())
        raise ValueError(f"Connection '{name}' not found. Available connections: {available}")

    _active_connection_name = name
    logger.info(f"Active connection set to '{name}'")


def get_all_connections() -> dict[str, SQLServerConnection]:
    """Return the connection registry dict."""
    return _connections


def get_active_connection_name() -> str | None:
    """Return the name of the currently active connection."""
    return _active_connection_name


def get_connection(name: str | None = None) -> SQLServerConnection:
    """Get a connection by name, or the active connection, or create a default from env vars.

    Resolution order:
    1. If name is provided, return that specific connection.
    2. If an active connection is set, return it.
    3. If no connections are loaded, create one from env vars as "default".
    4. If connections exist but no active is set, raise an error.
    """
    global _active_connection_name

    if name is not None:
        if name not in _connections:
            available = list(_connections.keys())
            raise ValueError(f"Connection '{name}' not found. Available connections: {available}")
        return _connections[name]

    if _active_connection_name is not None:
        return _connections[_active_connection_name]

    if not _connections:
        # Backward compat: create connection from env vars
        logger.info("No connections configured, creating default from environment variables")
        _connections["default"] = SQLServerConnection(name="default")
        _active_connection_name = "default"
        return _connections["default"]

    raise ValueError(
        "No active connection set. Use set_active_connection to choose one. "
        f"Available connections: {list(_connections.keys())}"
    )


# Load connections from JSON config at module import time
load_connections_from_json()
