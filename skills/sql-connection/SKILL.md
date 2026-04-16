---
name: sql-connection
description: Configure and test SQL Server connections for the dbt-pipeline-toolkit plugin. Supports Azure SQL DB (Entra Interactive), local SQL Server (Windows Auth), and SQL Auth. Use when setting up a new project, switching environments, or troubleshooting connection issues.
allowed-tools: Bash Read
---

# SQL Connection Manager

Configure, test, and manage SQL Server connections for the dbt-pipeline-toolkit plugin.

## Overview

This skill handles connection lifecycle:
- **Configure**: Write connection settings to project-level `.claude/settings.local.json`
- **Test**: Verify connectivity to SQL Server
- **Presets**: One-command setup for Azure SQL DB or local SQL Server

## Quick Start

### Azure SQL DB (conference demo / cloud)

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-connection/scripts/configure.py" --preset azure --server myserver.database.windows.net --database MyDatabase
```

This sets:
- Auth: Entra Interactive (browser popup, no passwords on screen)
- Encrypt: true (required for Azure)
- Driver: ODBC Driver 18 for SQL Server

### Local SQL Server (development)

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-connection/scripts/configure.py" --preset local --database Agentic
```

This sets:
- Server: localhost
- Auth: Windows Authentication (no password needed)
- Encrypt: false
- Driver: ODBC Driver 17 for SQL Server

### Local with SQL Auth

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-connection/scripts/configure.py" --preset local-sql --database Agentic --user sa --password YourPassword
```

## Test Current Connection

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-connection/scripts/configure.py" --test-only
```

## Custom Configuration

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-connection/scripts/configure.py" --server myserver --database MyDB --auth-type entra_interactive --encrypt true --trust-cert false
```

## Available Presets

| Preset | Server | Auth | Encrypt | Trust Cert | Driver |
|--------|--------|------|---------|------------|--------|
| `azure` | (you provide) | Entra Interactive | true | false | ODBC 18 |
| `local` | localhost | Windows | false | true | ODBC 17 |
| `local-sql` | localhost | SQL Auth | false | true | ODBC 17 |

## What It Does

The configure script writes to `.claude/settings.local.json` in your project:

```json
{
  "pluginConfigs": {
    "dbt-pipeline-toolkit": {
      "options": {
        "sql_server": "myserver.database.windows.net",
        "sql_database": "MyDatabase",
        "sql_auth_type": "entra_interactive",
        "sql_encrypt": "true",
        "sql_trust_cert": "false",
        "sql_driver": "ODBC Driver 18 for SQL Server"
      }
    }
  }
}
```

These values are passed to all plugin scripts as `CLAUDE_PLUGIN_OPTION_<KEY>` environment variables, and the `_load_plugin_userconfig_env()` helper in each script remaps them to the bare `SQL_*` names.

## Conference Demo Flow

For a live demo with Azure SQL DB:

1. Install the plugin: `claude plugin install ...`
2. Configure: "Set up Azure SQL connection to myserver.database.windows.net, database ConferenceDemo"
3. Browser popup appears for Entra authentication
4. Connection verified — ready to build pipelines

Total setup: ~30 seconds.

## Shared Connection Library

This skill also contains `scripts/connect.py`, a shared Python module imported by other plugin scripts (`data-profiler`, `sql-executor`, `sql-server-reader`) for building pyodbc and SQLAlchemy connections. It is not invoked directly — it provides `build_pyodbc_connection()` and `build_sqlalchemy_url()` functions.

## Dependencies

- **pyodbc**: SQL Server ODBC connectivity
- **ODBC Driver 17 or 18**: Microsoft ODBC driver for SQL Server

## Troubleshooting

**Problem**: "ODBC Driver not found"
**Solution**: Install Microsoft ODBC Driver 17 or 18 for SQL Server

**Problem**: "Login failed for user"
**Solution**: Check auth type matches your server setup. Use `--preset azure` for Azure SQL DB.

**Problem**: "Connection timeout"
**Solution**: Check server name is correct and firewall allows access on port 1433

**Problem**: "SSL/TLS error"
**Solution**: For Azure, ensure `--encrypt true`. For local dev, use `--trust-cert true`.
