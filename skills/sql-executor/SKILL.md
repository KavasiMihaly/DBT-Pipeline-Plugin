---
name: sql-executor
description: Execute SQL operations on SQL Server including data loading from CSV files. Loads source data from "2 - Source Files" into database tables using fast bulk insert. Supports INSERT, UPDATE, DELETE, TRUNCATE, and MERGE operations. Use for loading test data, preparing validation datasets, and managing database content during pipeline development.
allowed-tools: Bash Read Glob
---

# SQL Executor

Execute SQL operations on SQL Server, with specialized support for loading CSV data from the source files directory.

## Overview

This skill provides write access to SQL Server, enabling agents to:
- **Load CSV files** from `2 - Source Files/` into database tables using fast bulk insert
- Execute INSERT, UPDATE, DELETE, TRUNCATE statements
- Prepare test datasets for pipeline validation
- Clean and reset tables between test runs
- Bulk load data efficiently using pandas `to_sql()` with fast_executemany

**Primary Use Case**: Load any CSV source data into database tables for testing and development.

## Connection Details

- **Server**: localhost
- **Database**: Set via SQL_DATABASE env var
- **Authentication**: SQL Server Authentication
- **User**: Set via `SQL_USER` env var (empty = Windows Auth)
- **Mode**: Read/Write (full DML access)

## Usage

The skill is invoked through the Python script located in `scripts/load_data.py`.

### Load CSV file into a table

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" --file "source_data.csv" --table raw.source_table --schema raw
```

**What it does**:
- Reads CSV from `2 - Source Files/source_data.csv`
- Creates table if it doesn't exist (auto-detects schema)
- Loads data using fast bulk insert
- Reports rows loaded and execution time

### Load multiple files with pattern matching

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" --pattern "customer-*.csv" --table-prefix raw.customer --schema raw
```

**What it does**:
- Finds all matching CSV files in `2 - Source Files/`
- Extracts identifiers from filename (e.g., year, region)
- Creates table for each file with prefix
- Loads all files in sequence

### Truncate table before loading

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" --file "source_data.csv" --table raw.source_table --truncate
```

**What it does**:
- Truncates existing table first
- Then loads fresh data from CSV

### Execute custom SQL

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" --execute "DELETE FROM raw.source_table WHERE status = 'inactive'"
```

**What it does**:
- Executes the provided SQL statement
- Reports rows affected

### Execute SQL from file

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" --sql-file "scripts/cleanup.sql"
```

**What it does**:
- Reads SQL from file
- Executes each statement
- Reports results

## Python API

Can also be imported and used programmatically:

```python
from load_data import SQLExecutor

# Initialize executor
executor = SQLExecutor(
    server='localhost',
    database=os.environ.get('SQL_DATABASE', ''),
    username=os.environ.get('SQL_USER', ''),
    password=os.environ.get('SQL_PASSWORD', '')
)

# Load single CSV file
executor.load_csv_to_table(
    csv_path='2 - Source Files/source_data.csv',
    table_name='source_table',
    schema='raw',
    if_exists='replace'  # or 'append' or 'fail'
)

# Execute custom SQL
executor.execute_sql("TRUNCATE TABLE raw.source_table")

# Load multiple files by pattern
executor.load_pattern(
    pattern='customer-*.csv',
    table_prefix='customer',
    schema='raw'
)
```

## Column Name Sanitization

**IMPORTANT**: When loading CSV files, column names are automatically sanitized for SQL Server compatibility. Downstream consumers (like staging models) must reference the sanitized names, not the original CSV headers.

### Sanitization Rules

| Original | Sanitized | Rule |
|----------|-----------|------|
| `Field Name` | `field_name` | Spaces → underscores, lowercase |
| `Code/Format` | `code_format` | Slashes → underscores |
| `Sales (USD)` | `sales_usd` | Parentheses removed |
| `Order-ID` | `order_id` | Hyphens → underscores |
| `Sales & Revenue` | `sales_and_revenue` | `&` → `and` |
| `Profit %` | `profit_pct` | `%` → `pct` |
| `Item #` | `item_num` | `#` → `num` |
| `123_column` | `_123_column` | Leading numbers prefixed with `_` |
| `Multiple___underscores` | `multiple_underscores` | Multiple underscores collapsed |

### Complete Transformation List

- Spaces → underscores
- Hyphens → underscores
- Slashes (/ \\) → underscores
- Dots → underscores
- Colons/semicolons → underscores
- Parentheses, brackets, braces → removed
- `&` → `and`
- `%` → `pct`
- `#` → `num`
- `@` → `at`
- `$` → `dollar`
- `+` → `plus`
- `=` → `eq`
- `<` → `lt`
- `>` → `gt`
- Quotes, asterisks, question marks → removed
- All other special characters → removed
- Multiple consecutive underscores → single underscore
- Leading/trailing underscores → stripped
- All letters → lowercase

### Verification After Load

Always verify actual column names after loading CSV data:

```sql
-- Using sql-server-reader skill
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'raw' AND TABLE_NAME = 'your_table'
ORDER BY ORDINAL_POSITION;
```

Or use the MCP tool:
```
mcp__sql-server-mcp__get_table_schema --tableName "raw.your_table"
```

### Default Schema

The default target schema is `raw` (not `dbo`). Always specify the schema explicitly when referencing loaded tables in staging models:

```yaml
sources:
  - name: source_name
    schema: raw  # NOT dbo - data loaded by sql-executor defaults to raw
    tables:
      - name: your_table
```

## Performance

- **Bulk Insert**: Uses pandas `to_sql()` with `method='multi'` and `fast_executemany=True`
- **Typical Speed**: ~50,000 rows/second for wide tables
- **Large Files**: For files >1GB, uses chunked reading to avoid memory issues
- **Schema Detection**: Automatically infers data types from CSV

## Common Use Cases

### 1. Pipeline Validator: Load test data

```bash
# Load source data for testing
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" --file "source_data.csv" --table raw.source_table --schema raw --truncate
```

### 2. Load multiple related files

```bash
# Load all customer files from different regions
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" --pattern "customer-*.csv" --table-prefix raw.customer --schema raw
```

### 3. Clean up test data

```bash
# Remove all data from test run
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" --execute "TRUNCATE TABLE raw.source_table"
```

### 4. Load specific file subset

```bash
# Load only recent data files
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" --pattern "*-202[45].csv" --table-prefix raw.data --schema raw
```

## Error Handling

- **File not found**: Reports clear error with expected path
- **Table exists**: Default behavior is to fail (use `--replace` or `--append` to override)
- **Schema mismatch**: Reports column differences if table exists with different schema
- **Connection errors**: Reports detailed SQL Server connection issues
- **SQL errors**: Reports full error message with statement that failed

## Safety Features

- **Transaction Support**: All operations are transactional (rollback on error)
- **Dry Run Mode**: Use `--dry-run` to preview without executing
- **Row Count Validation**: Confirms CSV rows match loaded rows
- **Schema Validation**: Warns if existing table schema differs from CSV

## Output

All operations log to console with:
- Start time and end time
- Rows loaded/affected
- Execution duration
- Success/failure status

Example output:
```
[INFO] Loading CSV: 2 - Source Files/source_data.csv
[INFO] Target table: raw.source_table
[INFO] Reading CSV file... (125,432 rows)
[INFO] Creating table in schema 'raw'...
[INFO] Bulk loading data...
[SUCCESS] Loaded 125,432 rows in 2.5 seconds (50,172 rows/sec)
```

## Dependencies

- **pandas**: CSV reading and data manipulation
- **pyodbc**: SQL Server connectivity
- **sqlalchemy**: ORM and connection pooling

Install with:
```bash
pip install pandas pyodbc sqlalchemy
```

## Configuration

Connection parameters can be overridden:
```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" \
  --server localhost \
  --database $SQL_DATABASE \
  --username "$SQL_USER" \
  --password "$SQL_PASSWORD" \
  --file "source_data.csv" \
  --table raw.source_table
```

Or use environment variables:
```bash
export SQL_SERVER=localhost
export SQL_DATABASE=YourDatabase
export SQL_USER="your_username"
export SQL_PASSWORD="your_password"
```

## Integration with Pipeline Validator

The dbt-pipeline-validator agent uses this skill to:
1. **Truncate source tables** before test run
2. **Load test data** from source CSV files
3. **Verify row counts** after load
4. **Clean up** after validation complete

Example workflow in dbt-pipeline-validator:
```python
# Load test data for validation
Task(skill="sql-executor", 
     command="python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" --pattern '*.csv' --table-prefix raw.source --schema raw")

# After dbt build and tests pass, clean up
Task(skill="sql-executor",
     command="python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" --execute 'TRUNCATE TABLE raw.source_table'")
```

## Best Practices

1. **Always use schema prefix**: Specify `--schema raw` to organize source tables
2. **Truncate before reloading**: Use `--truncate` flag to avoid duplicate data
3. **Validate row counts**: Check that CSV rows match loaded rows
4. **Use patterns for bulk loads**: Load multiple years with `--pattern` flag
5. **Test with small files first**: Validate process before loading large datasets

## Troubleshooting

**Problem**: "Table already exists" error
**Solution**: Use `--replace` flag or `--truncate` flag

**Problem**: Slow loading performance
**Solution**: Ensure fast_executemany is enabled in connection string

**Problem**: Memory error on large files
**Solution**: Script automatically chunks files >1GB

**Problem**: Connection timeout
**Solution**: Increase `--timeout` parameter (default 30 seconds)

---

**Location**: `6 - Agentic Resources/Skills/sql-executor/`
**Primary Script**: `scripts/load_data.py`
**Use Cases**: Data loading, test data preparation, database management
**Status**: Implemented
