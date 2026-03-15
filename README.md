# SQL Server Doctor MCP Server

A Model Context Protocol (MCP) server for SQL Server tuning, diagnostics, and performance analysis. This server exposes SQL Server management capabilities to LLM applications.

### Example Usage

Ask your LLM client questions to troubleshoot and diagnose SQL Server issues:

**Configuration checks:**
- "Check my SQL Server configuration"
- "Is my SQL Server properly configured?"
- "Verify server settings"

**General troubleshooting:**
- "Users are complaining about slow queries, what's happening?"
- "Is something blocking my database?"

**Workload analysis:**
- "Analyze current SQL Server workload"
- "What queries are currently running?"
- "Which query is using the most CPU?"
- "Is there CPU pressure on the server?"
- "Show me any blocked sessions"

**Memory analysis:**
- "Does my SQL Server need more memory?"
- "Check memory pressure"
- "What's the Page Life Expectancy?"
- "Analyze SQL Server memory health"
- "Why is memory low?"

**Query performance tuning:**
- "Optimize this query" or "Tune this query"
- "Why is this query slow?"
- "How can I make this query faster?"
- "Find performance issues in this SELECT statement"
- "Analyze query execution plan"
- "Check if my query has antipatterns"
- "What indexes should I create for this query?"

**Data exploration:**
- "Show me the top 10 rows from the Orders table"
- "What columns does the Customers table have?"
- "Query the sales data for last month"
- "Run this SELECT query against the production database"

## Features

Currently implemented tools:

**Connection Management:**
- **list_connections** - List all configured connections and show which is active
- **set_active_connection** - Switch the active connection at runtime

**Server & Database Management:**
- **get_server_version** - Get SQL Server version and instance information
- **list_databases** - List all databases with state, recovery model, and compatibility level
- **find_object_database** - Find which database contains a specific table or view
- **execute_select_query** - Execute SELECT queries and return result sets with column metadata

**Performance Monitoring:**
- **get_server_configurations** - Analyze critical server configurations (max memory, MAXDOP, cost threshold) with recommendations
- **get_active_sessions** - Monitor currently executing queries with CPU usage, wait stats, and blocking information
- **get_scheduler_stats** - Monitor CPU queue depth and detect CPU pressure with automatic interpretation
- **get_memory_stats** - Analyze SQL Server memory health with PLE, memory grants, and pressure detection

**Query Performance Tuning:**
- **analyze_query_execution** - Execute queries with statistics collection and actual execution plan capture
- **detect_query_antipatterns** - Detect SQL antipatterns (non-SARGable predicates, SELECT *, correlated subqueries)
- **get_query_statistics_health** - Check statistics freshness and cardinality estimation quality for tables
- **analyze_missing_indexes** - Analyze missing index recommendations and existing index usage patterns

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

### Multiple connections (recommended)

Copy `connections.json.example` to `connections.json` and define your named connections:

```json
{
  "default": "PRD",
  "connections": {
    "DEV": {
      "host": "dev-server\\INSTANCE",
      "port": "1433",
      "database": "MyDatabase",
      "user": "",
      "password": "",
      "driver": "ODBC Driver 17 for SQL Server",
      "trust_cert": "yes",
      "encrypt": "no"
    },
    "PRD": {
      "host": "prod-server\\INSTANCE",
      "port": "1433",
      "database": "MyDatabase",
      "user": "",
      "password": "",
      "driver": "ODBC Driver 17 for SQL Server",
      "trust_cert": "yes",
      "encrypt": "no"
    }
  }
}
```

The `"default"` field sets which connection is active on startup. Use `set_active_connection` to switch at runtime, or pass `connection_name` to any tool for a one-off override.

### Single connection (environment variables)

For a single connection, copy `.env.example` to `.env` or set the equivalent environment variables directly in your shell/system. The server reads these variables via `python-dotenv`, so both `.env` files and system environment variables work:

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

- **list_connections()** - Lists all configured connections and shows which is active
- **set_active_connection(connection_name)** - Switches the active connection used by all tools
- **get_server_version()** - Returns SQL Server version and instance name
- **list_databases()** - Returns list of all databases with metadata (name, state, recovery model, compatibility level)
- **get_server_configurations()** - Returns configuration diagnostics and recommendations:
  - Max Server Memory analysis (with edition limits)
  - Cost Threshold for Parallelism evaluation
  - Max Degree of Parallelism (MAXDOP) assessment
  - Severity levels (OK, WARNING, CRITICAL, REVIEW, CONSIDER)
  - Context-rich messages with server specifications
  - Actionable SQL recommendations
- **get_active_sessions()** - Returns currently executing queries with detailed performance metrics:
  - SQL query text
  - Session ID, status, and command type
  - CPU time and elapsed time
  - Disk reads and logical reads
  - Wait time and wait type
  - Blocking session information
  - Client host, program, and login details
- **get_scheduler_stats()** - Returns CPU scheduler statistics with automatic interpretation:
  - Runnable task counts (CPU queue depth)
  - Work queue counts
  - Pending I/O operations
  - CPU pressure detection (tasks waiting for CPU)
  - Automatic interpretation of results
- **get_memory_stats()** - Returns comprehensive memory health diagnostics:
  - Page Life Expectancy (PLE) in seconds and minutes
  - PLE status assessment (OK, WARNING, CRITICAL)
  - Memory grants pending (queries waiting for memory)
  - Target vs actual memory allocation
  - Memory pressure status (OK, WATCH, UNDER_PRESSURE)
  - Buffer pool committed and target memory
  - Max server memory configuration
  - Overall memory health assessment with recommendations
- **analyze_query_execution(query, database_name, include_actual_plan, max_execution_time_seconds)** - Executes a query and captures detailed performance metrics:
  - Execution duration, CPU time, logical/physical reads
  - Actual row count returned
  - Query hash and plan hash for plan cache correlation
  - Actual execution plan XML (when include_actual_plan=true)
  - Execution plan summary with high-cost operators
  - Wait statistics during execution
  - Bottleneck type classification (IO_BOUND, CPU_BOUND, WAIT_BOUND, MEMORY_BOUND)
  - WARNING: Executes the query - only use with SELECT statements
- **detect_query_antipatterns(query, execution_plan_xml)** - Detects common SQL query antipatterns:
  - Non-SARGable predicates (functions on columns in WHERE clause)
  - SELECT * antipattern
  - Leading wildcards in LIKE patterns (e.g., LIKE '%search')
  - Implicit type conversions
  - Correlated subqueries
  - Scalar UDFs in SELECT list
  - Returns severity (HIGH, MEDIUM, LOW), location, and fix recommendations
  - Provides rewrite priority (HIGH/MEDIUM = fix query before creating indexes)
- **get_query_statistics_health(database_name, table_names, execution_plan_xml)** - Analyzes statistics freshness and quality:
  - Statistics age (days since last update)
  - Modification counter (rows changed since last stats update)
  - Sampling percentage used for statistics
  - Cardinality estimation mismatches from execution plan
  - Auto-update/auto-create statistics settings
  - Severity assessment (OK, WARNING, HIGH)
  - Provides UPDATE STATISTICS commands when needed
- **analyze_missing_indexes(database_name, execution_plan_xml)** - Analyzes index recommendations:
  - Missing index recommendations from SQL Server DMVs
  - Query-specific missing index hints from execution plan
  - Impact scoring and priority assessment
  - Existing index usage statistics (identifies unused indexes)
  - Index overlap detection
  - Provides CREATE INDEX statements
- **find_object_database(object_name)** - Locates which database contains a table or view:
  - Searches across all accessible databases
  - Supports formats: "TableName", "Schema.TableName", "Database.Schema.TableName"
  - Returns database name, schema name, object name, and object type
  - Useful for query tuning when database context is unclear
- **execute_select_query(query, database_name, row_limit, timeout_seconds)** - Executes SELECT queries and returns result sets:
  - Only allows SELECT and WITH (CTE) queries (read-only safety)
  - Returns column metadata (names and types) alongside data rows
  - Configurable row limit (default 100, max 1000) with truncation detection
  - Query timeout support (default 30s, max 120s)
  - Optional database context via database_name parameter
  - Automatic type serialization (Decimal, datetime, bytes to JSON-safe types)
  - Database name validation to prevent SQL injection

## Diagnostic Skills

This repository includes four diagnostic skills that provide intelligent workflows for using the MCP tools:

### 1. SQL Server Configuration Check (`sql-server-config-check`)

Verifies SQL Server configuration health by checking version and critical settings.

**Triggers on questions like:**
- "Check my SQL Server configuration"
- "Is my SQL Server properly configured?"
- "Verify server settings"

**What it does:**
1. Gets SQL Server version and edition
2. Analyzes max memory, MAXDOP, and cost threshold settings
3. Categorizes issues by severity (CRITICAL → WARNING → REVIEW → OK)
4. Provides prioritized, actionable recommendations

### 2. SQL Server Workload Analysis (`sql-server-workload-analysis`)

Analyzes current workload and resource pressure to identify performance bottlenecks.

**Triggers on questions like:**
- "Analyze SQL Server workload"
- "What's causing slow performance?"
- "Find blocking queries"
- "Is there CPU pressure?"

**What it does:**
1. Analyzes active sessions (blocking, long-running queries, resource consumption)
2. Checks CPU and I/O pressure via scheduler stats
3. Correlates findings (e.g., high CPU with specific sessions)
4. Explains wait types in plain language
5. Provides immediate actions, investigation steps, and preventive measures

### 3. SQL Server Memory Analysis (`sql-server-memory-analysis`)

Diagnoses SQL Server memory health and determines if more memory is needed.

**Triggers on questions like:**
- "Does my SQL Server need more memory?"
- "Check memory pressure"
- "What's the Page Life Expectancy?"
- "Analyze SQL Server memory health"

**What it does:**
1. Analyzes memory metrics (PLE, memory grants pending, pressure status)
2. Determines root cause (need more RAM vs need config changes)
3. Provides decision tree for diagnosing memory issues
4. Distinguishes between physical memory needs and configuration problems
5. Delivers clear recommendations with expected outcomes
6. Focuses on memory-specific tools to avoid unnecessary diagnostics

### 4. SQL Server Query Tuning (`sql-server-query-tuning`)

Systematically diagnoses and optimizes slow SQL Server queries through a phase-based approach that prioritizes query rewrites before index analysis.

**Triggers on questions like:**
- "Optimize this query" or "Tune this query"
- "Why is this query slow?"
- "How can I make this query faster?"
- "Analyze query performance"
- "Find performance issues in this query"
- "Check if my query has antipatterns"

**What it does:**
1. **Phase 1 - Baseline:** Executes query with statistics collection and captures actual execution plan
2. **Phase 2 - Antipatterns:** Detects non-SARGable predicates, SELECT *, correlated subqueries
3. **STOP GATE:** If HIGH/MEDIUM priority antipatterns found → fix query BEFORE creating indexes
4. **Phase 3 - Execution Plan:** Analyzes plan warnings, high-cost operators, cardinality mismatches
5. **Phase 4 - Statistics:** Checks statistics freshness if cardinality issues detected
6. **Phase 5 - Indexes:** Provides strategic index recommendations (lean indexes, key columns only)
7. **Phase 6 - Summary:** Comprehensive report with baseline vs expected improvement

**Key Features:**
- Query rewrites always come before index recommendations
- Detects and fixes non-SARGable predicates (e.g., `WHERE YEAR(col) = 2024`)
- Recommends lean indexes (key columns only) instead of wide covering indexes
- Evaluates columnstore suitability for analytical workloads
- Provides ready-to-execute SQL statements (CREATE INDEX, UPDATE STATISTICS)
- Estimates performance improvement magnitude

### Using the Skills

**Option 1: Project-Local (Recommended)**

The skills in `.claude/skills/` work automatically when you're working in this project directory. No additional setup needed!

**Option 2: Global Installation**

To use these skills across all projects, copy them to your global Claude skills directory:

**macOS/Linux:**
```bash
cp .claude/skills/*.md ~/.config/claude/skills/
```

**Windows:**
```powershell
Copy-Item .claude\skills\*.md "$env:APPDATA\Claude\skills\"
```

Once installed (either way), Claude will automatically use these skills when you ask matching questions!

## Project Structure

```
sqlserver-doctor-mcp/
├── .claude/
│   └── skills/
│       ├── sql-server-config-check.md      # Configuration health check skill
│       ├── sql-server-workload-analysis.md # Workload analysis skill
│       ├── sql-server-memory-analysis.md   # Memory health analysis skill
│       └── sql-server-query-tuning.md      # Query performance tuning skill
├── src/
│   └── sqlserver_doctor/
│       ├── __init__.py
│       ├── server.py          # FastMCP instance and tools
│       ├── main.py            # Entry point
│       └── utils/
│           ├── __init__.py
│           ├── connection.py  # SQL Server connection management
│           └── logger.py      # Logging configuration
├── tests/                     # Unit and integration tests
├── pyproject.toml            # Project configuration
├── connections.json.example  # Example multi-connection config
├── .env.example              # Example environment variables (single connection)
├── run_tests.bat             # Run tests (Windows)
└── README.md
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.
