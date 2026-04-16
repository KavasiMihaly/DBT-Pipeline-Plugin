#!/usr/bin/env python3
"""
SQL Executor Skill - Load CSV data into SQL Server
Fast bulk loading of source files into database tables.
Generic CSV loading for any source data files.
"""

import argparse
import sys
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Literal
import glob

import pandas as pd
import pyodbc
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import URL


def _load_plugin_userconfig_env():
    """Populate SQL_* env vars from all available config sources.

    Precedence (first wins):
      1. Bare env vars already set (SQL_SERVER, SQL_DATABASE, etc.)
      2. CLAUDE_PLUGIN_OPTION_* env vars (plugin userConfig)
      3. .claude/settings.local.json pluginConfigs (written by configure.py)

    Must run before argparse defaults are evaluated in main().
    """
    keys = (
        'SQL_SERVER', 'SQL_DATABASE', 'SQL_AUTH_TYPE', 'SQL_USER', 'SQL_PASSWORD',
        'SQL_ENCRYPT', 'SQL_TRUST_CERT', 'SQL_DRIVER',
        'AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET',
    )

    # Source 2: CLAUDE_PLUGIN_OPTION_* env vars
    for key in keys:
        if not os.environ.get(key):
            fallback = os.environ.get(f'CLAUDE_PLUGIN_OPTION_{key}')
            if fallback:
                os.environ[key] = fallback

    # Source 3: .claude/settings.local.json (written by configure.py)
    # Only read if we still have missing values
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        _load_from_settings_json(missing)


def _load_from_settings_json(missing_keys):
    """Read plugin config from .claude/settings.local.json as last resort."""
    from pathlib import Path
    try:
        cwd = Path.cwd()
        for search_dir in [cwd] + list(cwd.parents)[:5]:
            settings_path = search_dir / '.claude' / 'settings.local.json'
            if settings_path.exists():
                import json
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                options = (settings.get('pluginConfigs', {})
                           .get('dbt-pipeline-toolkit', {})
                           .get('options', {}))
                for key in missing_keys:
                    config_key = key.lower()  # SQL_SERVER -> sql_server
                    value = options.get(config_key, '')
                    if value and not os.environ.get(key):
                        os.environ[key] = value
                return
    except Exception:
        pass


_load_plugin_userconfig_env()


def sanitize_column_name(name: str) -> str:
    """
    Sanitize column name for SQL Server compatibility.

    Handles:
    - Spaces → underscores
    - Special characters (parentheses, hyphens, etc.) → removed or replaced
    - Leading numbers → prefixed with underscore
    - Lowercase conversion for consistency
    """
    import re

    # Convert to string in case of non-string
    name = str(name)

    # Replace common special characters
    name = name.replace(' ', '_')
    name = name.replace('-', '_')
    name = name.replace('(', '')
    name = name.replace(')', '')
    name = name.replace('[', '')
    name = name.replace(']', '')
    name = name.replace('{', '')
    name = name.replace('}', '')
    name = name.replace('/', '_')
    name = name.replace('\\', '_')
    name = name.replace('.', '_')
    name = name.replace(',', '')
    name = name.replace('&', 'and')
    name = name.replace('%', 'pct')
    name = name.replace('#', 'num')
    name = name.replace('@', 'at')
    name = name.replace('$', 'dollar')
    name = name.replace('+', 'plus')
    name = name.replace('=', 'eq')
    name = name.replace('*', '')
    name = name.replace('?', '')
    name = name.replace('!', '')
    name = name.replace("'", '')
    name = name.replace('"', '')
    name = name.replace(':', '_')
    name = name.replace(';', '_')
    name = name.replace('<', 'lt')
    name = name.replace('>', 'gt')

    # Remove any remaining non-alphanumeric characters except underscore
    name = re.sub(r'[^a-zA-Z0-9_]', '', name)

    # Replace multiple underscores with single
    name = re.sub(r'_+', '_', name)

    # Remove leading/trailing underscores
    name = name.strip('_')

    # Handle empty names
    if not name:
        name = 'column'

    # Prefix with underscore if starts with number
    if name[0].isdigit():
        name = '_' + name

    # Convert to lowercase for consistency
    name = name.lower()

    return name


def sanitize_dataframe_columns(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Sanitize all column names in a DataFrame for SQL Server compatibility.

    Args:
        df: DataFrame with potentially problematic column names
        verbose: Print column name changes

    Returns:
        DataFrame with sanitized column names
    """
    original_columns = df.columns.tolist()
    new_columns = [sanitize_column_name(col) for col in original_columns]

    # Handle duplicate column names after sanitization
    seen = {}
    final_columns = []
    for col in new_columns:
        if col in seen:
            seen[col] += 1
            final_columns.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            final_columns.append(col)

    # Log changes if verbose
    if verbose:
        changes = [(orig, new) for orig, new in zip(original_columns, final_columns) if orig != new]
        if changes:
            print(f"[INFO] Sanitized {len(changes)} column names:")
            for orig, new in changes[:10]:  # Show first 10
                print(f"  '{orig}' -> '{new}'")
            if len(changes) > 10:
                print(f"  ... and {len(changes) - 10} more")

    df.columns = final_columns
    return df


class SQLExecutor:
    """Execute SQL operations including fast CSV data loading."""

    def __init__(
        self, 
        server: str = 'localhost',
        database: str = '',
        username: str = '',
        password: str = '',
        driver: str = 'ODBC Driver 17 for SQL Server',
        timeout: int = 30,
        verbose: bool = True
    ):
        """Initialize SQL Server connection parameters."""
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.driver = driver
        self.timeout = timeout
        self.verbose = verbose
        self.engine = None
        
        # Set up source data directory
        # Primary: use CWD (Claude Code sets CWD to the user's project)
        # Fallback: walk up from script location (for direct invocation during dev)
        cwd = Path.cwd()
        project_root = None

        if (cwd / '2 - Source Files').exists():
            project_root = cwd
        else:
            # Walk up from CWD looking for the folder
            current_path = cwd
            for _ in range(5):
                if current_path.parent == current_path:
                    break
                current_path = current_path.parent
                if (current_path / '2 - Source Files').exists():
                    project_root = current_path
                    break

        # Last resort: walk up from script location (dev-only fallback)
        if project_root is None:
            script_path = Path(__file__).resolve()
            current_path = script_path.parent
            for _ in range(10):
                if (current_path / '2 - Source Files').exists():
                    project_root = current_path
                    break
                if current_path.parent == current_path:
                    break
                current_path = current_path.parent

        if project_root is None:
            project_root = cwd

        self.source_dir = project_root / '2 - Source Files'

        # Don't fail if source_dir doesn't exist (might be using absolute paths)
        if not self.source_dir.exists():
            self._log(f"Warning: Source directory not found at {self.source_dir}. Using absolute paths if provided.", "WARNING")
        
    def _log(self, message: str, level: str = "INFO"):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(f"[{level}] {message}")
    
    def connect(self) -> bool:
        """Establish connection to SQL Server."""
        try:
            # Import shared connection builder
            sys.path.insert(0, str(Path(__file__).parent / '../../sql-connection/scripts'))
            from connect import build_sqlalchemy_url

            self._log(f"Connecting to {self.server}/{self.database}...")

            url, connect_args = build_sqlalchemy_url(
                self.server, self.database, self.username, self.password,
                self.driver, extra_query={"fast_executemany": "True"})

            engine_connect_args = {"timeout": self.timeout}
            if connect_args:
                engine_connect_args.update(connect_args)

            self.engine = create_engine(
                url,
                connect_args=engine_connect_args,
                fast_executemany=True
            )

            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            self._log("Connection established successfully", "SUCCESS")
            return True

        except Exception as e:
            self._log(f"Connection failed: {str(e)}", "ERROR")
            return False
    
    def create_schema_if_not_exists(self, schema: str):
        """Create schema if it doesn't exist."""
        if self.engine is None:
            raise RuntimeError("Not connected to database. Call connect() first.")
        
        try:
            with self.engine.connect() as conn:
                # Check if schema exists
                result = conn.execute(text(
                    f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{schema}'"
                ))
                
                if result.fetchone() is None:
                    self._log(f"Creating schema '{schema}'...")
                    conn.execute(text(f"CREATE SCHEMA {schema}"))
                    conn.commit()
                    self._log(f"Schema '{schema}' created", "SUCCESS")
                else:
                    self._log(f"Schema '{schema}' already exists")
                    
        except Exception as e:
            self._log(f"Error creating schema: {str(e)}", "ERROR")
            raise
    
    def load_csv_to_table(
        self,
        csv_path: Union[str, Path],
        table_name: str,
        schema: str = 'raw',
        if_exists: Literal['fail', 'replace', 'append'] = 'fail',
        truncate: bool = False,
        chunksize: Optional[int] = None,
        dtype: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Load CSV file into SQL Server table.
        
        Args:
            csv_path: Path to CSV file (relative to source_dir or absolute)
            table_name: Target table name (without schema prefix)
            schema: Schema name (default: 'raw')
            if_exists: {'fail', 'replace', 'append'} - default 'fail'
            truncate: Truncate table before loading (overrides if_exists)
            chunksize: Read CSV in chunks (for large files)
            dtype: Dict of column dtypes to enforce
            
        Returns:
            Number of rows loaded
        """
        if self.engine is None:
            raise RuntimeError("Not connected to database. Call connect() first.")
        
        start_time = datetime.now()
        
        # Resolve CSV path
        if not Path(csv_path).is_absolute():
            csv_path = self.source_dir / csv_path
        else:
            csv_path = Path(csv_path)
        
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        self._log(f"Loading CSV: {csv_path}")
        self._log(f"Target table: {schema}.{table_name}")
        
        # Create schema if needed
        self.create_schema_if_not_exists(schema)
        
        # Handle truncate option
        if truncate:
            try:
                with self.engine.connect() as conn:
                    conn.execute(text(f"TRUNCATE TABLE {schema}.{table_name}"))
                    conn.commit()
                    self._log(f"Table {schema}.{table_name} truncated")
            except Exception as e:
                # Table might not exist yet, that's OK
                self._log(f"Truncate skipped (table may not exist): {str(e)}")
            if_exists = 'append'  # After truncate, always append
        
        # Read CSV
        self._log("Reading CSV file...")
        
        if chunksize:
            # Read in chunks for large files
            self._log(f"Using chunked reading (chunksize={chunksize})")
            total_rows = 0

            for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunksize, low_memory=False)):
                # Sanitize column names on first chunk
                if i == 0:
                    chunk = sanitize_dataframe_columns(chunk, verbose=self.verbose)
                    sanitized_columns = chunk.columns.tolist()
                else:
                    # Apply same column names to subsequent chunks
                    chunk.columns = sanitized_columns

                self._log(f"Loading chunk {i+1} ({len(chunk)} rows)...")
                # Use default executemany (not 'multi') to avoid SQL Server 2100 parameter limit
                # fast_executemany=True in engine provides efficient batch inserts
                chunk.to_sql(
                    table_name,
                    self.engine,
                    schema=schema,
                    if_exists='append' if i > 0 or if_exists == 'append' else if_exists,
                    index=False,
                    dtype=dtype
                )
                total_rows += len(chunk)

            rows_loaded = total_rows
        else:
            # Read entire file at once
            df = pd.read_csv(csv_path, low_memory=False)
            self._log(f"CSV loaded: {len(df):,} rows, {len(df.columns)} columns")

            # Sanitize column names for SQL Server compatibility
            df = sanitize_dataframe_columns(df, verbose=self.verbose)

            # Load to SQL Server using fast_executemany (not 'multi' to avoid 2100 param limit)
            self._log("Bulk loading data to SQL Server...")
            df.to_sql(
                table_name,
                self.engine,
                schema=schema,
                if_exists=if_exists,
                index=False,
                dtype=dtype,
                chunksize=5000  # Process in batches of 5000 rows for memory efficiency
            )
            rows_loaded = len(df)
        
        # Calculate performance
        duration = (datetime.now() - start_time).total_seconds()
        rows_per_sec = rows_loaded / duration if duration > 0 else 0
        
        self._log(
            f"Loaded {rows_loaded:,} rows in {duration:.1f} seconds ({rows_per_sec:,.0f} rows/sec)",
            "SUCCESS"
        )
        
        return rows_loaded
    
    def execute_sql(self, sql: str) -> int:
        """
        Execute SQL statement (INSERT, UPDATE, DELETE, TRUNCATE, etc.).
        
        Args:
            sql: SQL statement to execute
            
        Returns:
            Number of rows affected
        """
        if self.engine is None:
            raise RuntimeError("Not connected to database. Call connect() first.")
        
        self._log(f"Executing SQL: {sql[:100]}...")
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql))
                conn.commit()
                
                rows_affected = result.rowcount if hasattr(result, 'rowcount') else 0
                self._log(f"SQL executed successfully ({rows_affected} rows affected)", "SUCCESS")
                return rows_affected
                
        except Exception as e:
            self._log(f"SQL execution failed: {str(e)}", "ERROR")
            raise
    
    def load_pattern(
        self,
        pattern: str,
        table_prefix: str,
        schema: str = 'raw',
        if_exists: Literal['fail', 'replace', 'append'] = 'replace'
    ) -> Dict[str, int]:
        """
        Load multiple CSV files matching a pattern.
        
        Args:
            pattern: Glob pattern for CSV files (e.g., "casualty-*.csv")
            table_prefix: Prefix for table names (e.g., "dft_casualty")
            schema: Target schema
            if_exists: {'fail', 'replace', 'append'}
            
        Returns:
            Dict mapping table names to row counts
        """
        self._log(f"Loading files matching pattern: {pattern}")
        
        # Find matching files
        matches = list(self.source_dir.glob(pattern))
        
        if not matches:
            self._log(f"No files found matching pattern: {pattern}", "WARNING")
            return {}
        
        self._log(f"Found {len(matches)} matching files")
        results = {}
        
        for csv_file in sorted(matches):
            # Try to extract year from filename
            year_match = re.search(r'(\d{4})', csv_file.stem)
            year_suffix = f"_{year_match.group(1)}" if year_match else ""
            
            table_name = f"{table_prefix}{year_suffix}".replace('-', '_')
            
            try:
                rows = self.load_csv_to_table(
                    csv_path=csv_file,
                    table_name=table_name,
                    schema=schema,
                    if_exists=if_exists
                )
                results[f"{schema}.{table_name}"] = rows
            except Exception as e:
                self._log(f"Failed to load {csv_file.name}: {str(e)}", "ERROR")
                results[f"{schema}.{table_name}"] = -1
        
        return results


def main():
    """Command-line interface for SQL Executor skill."""
    parser = argparse.ArgumentParser(
        description='Load CSV files into SQL Server with fast bulk insert'
    )
    
    # Connection parameters — defaults read from env vars (populated by _load_plugin_userconfig_env)
    parser.add_argument('--server', default=os.environ.get('SQL_SERVER', 'localhost'), help='SQL Server hostname (env: SQL_SERVER)')
    parser.add_argument('--database', default=os.environ.get('SQL_DATABASE', ''), help='Database name (env: SQL_DATABASE)')
    parser.add_argument('--username', default=os.environ.get('SQL_USER', ''), help='SQL Server username (env: SQL_USER, empty=Windows Auth)')
    parser.add_argument('--password', default=os.environ.get('SQL_PASSWORD', ''), help='SQL Server password (env: SQL_PASSWORD, empty=Windows Auth)')
    parser.add_argument('--driver', default=os.environ.get('SQL_DRIVER', 'ODBC Driver 17 for SQL Server'), help='ODBC driver (env: SQL_DRIVER)')
    parser.add_argument('--timeout', type=int, default=30, help='Connection timeout (seconds)')
    parser.add_argument('--source-dir', help='Override source directory path (default: auto-detect)')
    
    # Operation parameters
    parser.add_argument('--file', help='CSV file to load (relative to 2 - Source Files/)')
    parser.add_argument('--table', help='Target table name (with or without schema prefix)')
    parser.add_argument('--schema', default='raw', help='Target schema (default: raw)')
    parser.add_argument('--truncate', action='store_true', help='Truncate table before loading')
    parser.add_argument('--replace', action='store_true', help='Replace table if exists')
    parser.add_argument('--append', action='store_true', help='Append to existing table')
    
    # Pattern loading
    parser.add_argument('--pattern', help='Load files matching glob pattern')
    parser.add_argument('--table-prefix', help='Table name prefix for pattern loading')
    
    # SQL execution
    parser.add_argument('--execute', help='Execute SQL statement')
    parser.add_argument('--sql-file', help='Execute SQL from file')
    
    # Other options
    parser.add_argument('--quiet', action='store_true', help='Suppress output')
    parser.add_argument('--chunksize', type=int, help='Read CSV in chunks (for large files)')
    
    args = parser.parse_args()

    # Initialize executor
    executor = SQLExecutor(
        server=args.server,
        database=args.database,
        username=args.username,
        password=args.password,
        driver=args.driver,
        timeout=args.timeout,
        verbose=not args.quiet
    )

    # Override source_dir if provided
    if args.source_dir:
        executor.source_dir = Path(args.source_dir)
        if not executor.source_dir.exists():
            executor._log(f"Specified source directory not found: {executor.source_dir}", "ERROR")
            sys.exit(1)
    
    # Connect to database
    if not executor.connect():
        sys.exit(1)
    
    try:
        # Determine if_exists parameter
        if args.replace:
            if_exists = 'replace'
        elif args.append:
            if_exists = 'append'
        else:
            if_exists = 'fail'
        
        # Execute requested operation
        if args.pattern:
            # Load files matching pattern
            if not args.table_prefix:
                executor._log("--table-prefix required when using --pattern", "ERROR")
                sys.exit(1)
            
            results = executor.load_pattern(
                pattern=args.pattern,
                table_prefix=args.table_prefix,
                schema=args.schema,
                if_exists=if_exists
            )
            sys.exit(0 if all(r >= 0 for r in results.values()) else 1)
            
        elif args.file:
            # Load single file
            if not args.table:
                executor._log("--table required when using --file", "ERROR")
                sys.exit(1)
            
            # Parse table name (handle schema.table format)
            if '.' in args.table:
                schema, table = args.table.split('.', 1)
            else:
                schema = args.schema
                table = args.table
            
            rows = executor.load_csv_to_table(
                csv_path=args.file,
                table_name=table,
                schema=schema,
                if_exists=if_exists,
                truncate=args.truncate,
                chunksize=args.chunksize
            )
            sys.exit(0)
            
        elif args.execute:
            # Execute SQL statement
            executor.execute_sql(args.execute)
            sys.exit(0)
            
        elif args.sql_file:
            # Execute SQL from file
            with open(args.sql_file, 'r') as f:
                sql = f.read()
            executor.execute_sql(sql)
            sys.exit(0)
            
        else:
            parser.print_help()
            sys.exit(1)
            
    except Exception as e:
        executor._log(f"Operation failed: {str(e)}", "ERROR")
        sys.exit(1)


if __name__ == '__main__':
    main()
