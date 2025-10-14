# SQL Server Doctor MCP Server

A Model Context Protocol (MCP) server for SQL Server tuning, diagnostics, and performance analysis. This server exposes SQL Server management capabilities to LLM applications like Claude Code.

## Features

Currently implemented tools:
- **get_server_version** - Get SQL Server version and instance information
- **list_databases** - List all databases with state, recovery model, and compatibility level

## Prerequisites

- Python 3.10 or higher
- SQL Server (any edition)
- ODBC Driver for SQL Server (Driver 17 recommended for macOS)

### Installing ODBC Driver

**macOS (recommended):**
```bash
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update
brew install msodbcsql17 mssql-tools
```

**Linux (Ubuntu/Debian):**
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

**Windows:**
Download and install from: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

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

### Example Usage

Ask Claude:
- "What version of SQL Server am I running?"
- "List all databases on my SQL Server"
- "Which databases are using FULL recovery model?"

## Troubleshooting

### "spawn python ENOENT" error

This means the Python executable can't be found. Make sure you're using the full path to your venv's Python in the MCP configuration.

Find your Python path:
```bash
# macOS/Linux
which python3

# Windows
where python
```

### "Can't open lib 'ODBC Driver XX for SQL Server'"

The ODBC driver isn't installed or the driver name in `.env` doesn't match.

Check installed drivers:
```bash
# macOS/Linux
odbcinst -q -d

# Windows
Get-OdbcDriver
```

Update `SQL_SERVER_DRIVER` in your `.env` file to match an installed driver.

### Connection fails

Check your SQL Server connection settings:
1. Verify SQL Server is running and accessible
2. Check firewall settings (port 1433)
3. Verify credentials in `.env` file
4. Check SQL Server authentication mode (SQL Server and Windows Authentication mode)

## Development

### Running Tests
```bash
pip install -e ".[dev]"
pytest
```

### Code Formatting
```bash
black .
```

### Type Checking
```bash
mypy src
```

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
