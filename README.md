# SQL Server Doctor MCP Server

A Model Context Protocol (MCP) server for SQL Server tuning, diagnostics, and performance analysis. This server exposes SQL Server management capabilities to LLM applications like Claude Code.

## Features

Currently implemented tools:
- **get_server_version** - Get SQL Server version and instance information
- **list_databases** - List all databases with state, recovery model, and compatibility level
- **get_active_sessions** - Monitor currently executing queries with CPU usage, wait stats, and blocking information

## Prerequisites

- Python 3.10 or higher
- SQL Server (any edition)
- ODBC Driver for SQL Server (Driver 17 recommended for macOS)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/sqlserver-doctor-mcp.git
   cd sqlserver-doctor-mcp
   ```

2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the package in editable mode:
   ```bash
   pip install -e .
   ```

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your SQL Server connection details:

   **For SQL Server Authentication:**
   ```env
   SQL_SERVER_HOST=your-server.database.windows.net
   SQL_SERVER_PORT=1433
   SQL_SERVER_DATABASE=master
   SQL_SERVER_USER=your_username
   SQL_SERVER_PASSWORD=your_password
   SQL_SERVER_DRIVER=ODBC Driver 17 for SQL Server
   ```

   **For Windows Authentication (local):**
   ```env
   SQL_SERVER_HOST=localhost
   SQL_SERVER_PORT=1433
   SQL_SERVER_DATABASE=master
   SQL_SERVER_USER=
   SQL_SERVER_PASSWORD=
   SQL_SERVER_DRIVER=ODBC Driver 17 for SQL Server
   ```

## Usage with Claude Code

### Setup

1. In Claude Code, open MCP settings using the `/mcp edit` command

2. Add this configuration (replace `/path/to/` with your actual project path):

   ```json
   {
     "mcpServers": {
       "sqlserver-doctor": {
         "command": "/path/to/sqlserver-doctor-mcp/venv/bin/python3",
         "args": ["-m", "sqlserver_doctor.main"],
         "cwd": "/path/to/sqlserver-doctor-mcp"
       }
     }
   }
   ```

   **Important Notes:**
   - Use the **full path** to your venv's Python (e.g., `/Users/yourname/sqlserver-doctor-mcp/venv/bin/python3`)
   - On Windows, use: `"C:\\path\\to\\sqlserver-doctor-mcp\\venv\\Scripts\\python.exe"`
   - The server will automatically load settings from your `.env` file

3. Save the configuration and reload MCP servers in Claude Code

### Available Tools

Once connected, Claude can use these tools:

- **get_server_version()** - Returns SQL Server version and instance name
- **list_databases()** - Returns list of all databases with metadata (name, state, recovery model, compatibility level)
- **get_active_sessions()** - Returns currently executing queries with detailed performance metrics:
  - SQL query text
  - Session ID, status, and command type
  - CPU time and elapsed time
  - Disk reads and logical reads
  - Wait time and wait type
  - Blocking session information
  - Client host, program, and login details

### Example Usage

Ask Claude:
- "What version of SQL Server am I running?"
- "List all databases on my SQL Server"
- "Which databases are using FULL recovery model?"
- "Show me what queries are currently running"
- "Are there any blocked sessions right now?"
- "Which query is using the most CPU?"
- "What is session 52 currently executing?"


## Project Structure

```
sqlserver-doctor-mcp/
├── src/
│   └── sqlserver_doctor/
│       ├── __init__.py
│       ├── server.py          # FastMCP instance and tools
│       ├── main.py            # Entry point
│       └── utils/
│           ├── __init__.py
│           ├── connection.py  # SQL Server connection management
│           └── logger.py      # Logging configuration
├── tests/                     # Unit tests
├── pyproject.toml            # Project configuration
├── .env.example              # Example environment variables
└── README.md
```

## Roadmap

Future tools to be added:
- Wait statistics analysis
- Database health checks
- Performance counter monitoring
- Blocking and deadlock detection

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.
