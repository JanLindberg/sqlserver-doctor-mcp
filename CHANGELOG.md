# Changelog

## [0.2.1] - 2026-03-16

- Support `USE`, `DECLARE`, and `SET` preamble statements in queries sent to `execute_select_query` and `analyze_query_execution`
- Queries with an inline `USE` statement no longer conflict with the `database_name` parameter

## [0.2.0] - 2026-03-15

- Multiple named SQL Server connections via `connections.json`
- New tools: `list_connections`, `set_active_connection`, `execute_select_query`
- All tools accept optional `connection_name` parameter

## [0.1.0] - 2025-10-14

- Initial release
