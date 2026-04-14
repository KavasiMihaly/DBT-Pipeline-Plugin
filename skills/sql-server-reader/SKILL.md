---
name: sql-server-reader
description: Read metadata and query data from local SQL Server database. List tables, inspect schemas, execute SELECT queries. Results exported as CSV to "7 - Data Exports". Use for data validation, debugging, and sample data inspection during development. Read-only operations - no writes permitted.
allowed-tools: Bash Read Glob
---

# SQL Server Reader

Query a local SQL Server database to inspect metadata and extract data for validation and debugging purposes.

## Overview

This skill provides read-only access to SQL Server tables, enabling agents to:
- List available tables in the configured database
- Inspect table schemas and column definitions
- Execute SELECT queries and export results as CSV
- Validate data during dbt development
- Debug data issues and inspect sample records

All query results are automatically saved to `7 - Data Exports/` as CSV files.

## Connection Details

- **Server**: localhost
- **Database**: Set via SQL_DATABASE env var
- **Authentication**: SQL Server Authentication
- **User**: Set via `SQL_USER` env var (empty = Windows Auth)
- **Mode**: Read-only (SELECT statements only)

## Usage

The skill is invoked through the Python script located in `scripts/query_sql_server.py`.

### List all tables in the database

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --list-tables
```

**Output**: Displays table names and saves list to `7 - Data Exports/table_list.csv`

### Get schema for a specific table

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --schema TABLE_NAME
```

**Example**:
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --schema customers
```

**Output**: 
- Column names, data types, nullability, keys
- Saves schema to `7 - Data Exports/schema_TABLE_NAME.csv`

### Execute a SELECT query

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT * FROM customers WHERE region = 'North'"
```

**Output**: 
- Query results displayed in terminal
- Saves to `7 - Data Exports/query_results_TIMESTAMP.csv`

### Execute query from file

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query-file path/to/query.sql
```

**Output**: 
- Results saved to `7 - Data Exports/query_results_TIMESTAMP.csv`

### Export specific table to CSV

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --export TABLE_NAME
```

**Example**:
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --export customers
```

**Output**: Full table export to `7 - Data Exports/TABLE_NAME_TIMESTAMP.csv`

### Limit result rows

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT * FROM orders" --limit 100
```

**Output**: Returns only first 100 rows

## Common Patterns

### Quick table inspection

```bash
# See what tables exist
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --list-tables

# Check structure of specific table
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --schema orders

# Sample first 10 rows
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT TOP 10 * FROM orders"
```

### Data validation during dbt development

```bash
# Check if staging model data looks correct
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --export stg_erp__customers --limit 100

# Validate business logic
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT customer_id, COUNT(*) as order_count FROM orders GROUP BY customer_id"
```

### Debugging data issues

```bash
# Find null values
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT * FROM products WHERE price IS NULL"

# Check data ranges
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT MIN(order_date), MAX(order_date) FROM orders"

# Find duplicates
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT product_id, COUNT(*) FROM products GROUP BY product_id HAVING COUNT(*) > 1"
```

### Compare source vs transformed data

```bash
# Export raw source table
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --export raw_customers --limit 1000

# Export staging transformation
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --export stg_erp__customers --limit 1000

# Compare CSV files in 7 - Data Exports/
```

## Safety Features

### Read-Only Mode
- Only SELECT statements permitted
- INSERT, UPDATE, DELETE, DROP blocked
- Query validation before execution
- No DDL operations allowed

### Query Validation
The script validates queries before execution:
- ✅ Allowed: SELECT, WITH (CTEs)
- ❌ Blocked: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, EXECUTE

### Result Size Management
- Default limit: 10,000 rows (configurable)
- Large result warnings
- Automatic CSV chunking for very large datasets

## Output Location

All exports are saved to:
```
7 - Data Exports/
├── table_list.csv
├── schema_TABLE_NAME.csv
├── query_results_20260111_143022.csv
├── TABLE_NAME_20260111_143045.csv
└── ...
```

**File naming convention**:
- Table lists: `table_list.csv`
- Schemas: `schema_{TABLE_NAME}.csv`
- Query results: `query_results_{TIMESTAMP}.csv`
- Table exports: `{TABLE_NAME}_{TIMESTAMP}.csv`

## Error Handling

The script provides clear error messages for:
- Connection failures
- Invalid queries
- Non-existent tables
- Authentication issues
- Query timeouts
- CSV write failures

**Example error**:
```
❌ Error: Invalid query - write operations not permitted
Query contained: INSERT INTO
Only SELECT statements are allowed.
```

## Advanced Usage

### Custom output filename

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT * FROM customers" --output customer_snapshot.csv
```

### Query timeout configuration

```bash
# Set 60 second timeout for long queries
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT * FROM large_table" --timeout 60
```

### JSON output instead of CSV

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT * FROM products" --format json
```

**Output**: Saves as `query_results_TIMESTAMP.json`

### Verbose logging

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --list-tables --verbose
```

**Output**: Shows connection details, query execution time, row counts

## Integration with Agents

### business-analyst Agent
Use to explore data landscape during discovery:
```bash
# What tables exist for customer data?
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --list-tables

# What does customer table structure look like?
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --schema customers
```

### dbt-developer Agent
Use to validate transformations:
```bash
# Check staging model output
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --export stg_erp__customers --limit 100

# Validate business logic
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT COUNT(DISTINCT customer_id) FROM stg_erp__customers"
```

### dbt-test-writer Agent
Use to design test expectations:
```bash
# Check for nulls that should trigger test failure
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT COUNT(*) FROM customers WHERE email IS NULL"

# Find data anomalies
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT * FROM orders WHERE order_total < 0"
```

## Requirements

### Python Dependencies
- `pyodbc` - SQL Server ODBC driver
- `pandas` - Data manipulation and CSV export
- `python-dotenv` - Environment variable management (optional)

### Installation
```bash
pip install pyodbc pandas python-dotenv
```

### SQL Server Driver
Windows users typically have ODBC Driver 17+ installed by default.

**Verify driver**:
```bash
python -c "import pyodbc; print(pyodbc.drivers())"
```

## Configuration

### Environment Variables (Optional)
Create `.env` file in project root:
```env
SQL_SERVER_HOST=localhost
SQL_DATABASE=YourDatabase
SQL_USER=your_username
SQL_PASSWORD=your_password
SQL_SERVER_PORT=1433
```

### Script Arguments
All connection details can be passed as arguments:
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" \
  --server localhost \
  --database $SQL_DATABASE \
  --user "$SQL_USER" \
  --password "$SQL_PASSWORD" \
  --query "SELECT * FROM customers"
```

## Troubleshooting

### Connection Refused
```bash
# Test connection
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --test-connection

# Check SQL Server is running
# Services → SQL Server (MSSQLSERVER) → Status: Running
```

### Authentication Failed
- Verify SQL Server Authentication is enabled (not just Windows Auth)
- Confirm SQL_USER and SQL_PASSWORD environment variables are set (or use Windows Auth)
- Check SQL Server Configuration Manager → Network Configuration → TCP/IP enabled

### Table Not Found
```bash
# List all available tables
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --list-tables

# Check database name
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT DB_NAME()"
```

### Driver Not Found
```bash
# Install ODBC Driver 17 for SQL Server
# Download from: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

# Or use ODBC Driver 11 if 17 not available
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --driver "ODBC Driver 11 for SQL Server"
```

## Best Practices

### Performance
- Use `--limit` for exploratory queries on large tables
- Create indexes on frequently queried columns
- Use WHERE clauses to filter data before export
- Avoid `SELECT *` on wide tables - specify columns

### Security
- Never commit credentials to git
- Use environment variables or Azure Key Vault
- Regularly rotate SQL Server passwords
- Use least-privilege account (read-only access only)

### Data Exports
- Clean up old CSV files regularly (7 - Data Exports/)
- Use meaningful query filenames with `--output`
- Document complex queries in .sql files
- Add .csv files to .gitignore

### Query Development
1. Test query in SQL Server Management Studio first
2. Start with `--limit 10` for quick validation
3. Use `--verbose` to debug issues
4. Save complex queries as .sql files for reuse

## Examples

### Comprehensive data validation workflow

```bash
# 1. List all tables
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --list-tables

# 2. Inspect customer table structure
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --schema customers

# 3. Export sample data
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --export customers --limit 1000 --output customer_sample.csv

# 4. Check data quality
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "
SELECT 
  COUNT(*) as total_rows,
  COUNT(DISTINCT customer_id) as unique_customers,
  COUNT(CASE WHEN email IS NULL THEN 1 END) as null_emails,
  MIN(created_date) as earliest_record,
  MAX(created_date) as latest_record
FROM customers
"

# 5. Find specific issues
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT * FROM customers WHERE email IS NULL OR email = ''" --output customers_missing_email.csv
```

### Quick reference guide

```bash
# List tables
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --list-tables

# Get schema
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --schema TABLE_NAME

# Sample data
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "SELECT TOP 10 * FROM TABLE_NAME"

# Export full table
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --export TABLE_NAME

# Custom query
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query "YOUR_SELECT_QUERY"

# Query from file
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --query-file path/to/query.sql

# Test connection
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-server-reader/scripts/query_sql_server.py" --test-connection
```
