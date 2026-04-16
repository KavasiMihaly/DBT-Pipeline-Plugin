#!/usr/bin/env python3
"""
SQL Server Reader Skill
Query local SQL Server with read-only access.
Exports results to CSV in "7 - Data Exports" folder.
"""

import argparse
import sys
import os
import re
from datetime import datetime
from pathlib import Path
import pyodbc
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from typing import Optional, List, Dict, Any


def _load_plugin_userconfig_env():
    """Map CLAUDE_PLUGIN_OPTION_<KEY> -> <KEY> for SQL connection env vars.

    Claude Code plugin subprocesses receive userConfig values as
    CLAUDE_PLUGIN_OPTION_<KEY> environment variables, but this script expects
    bare names (e.g. SQL_SERVER). Must run before argparse defaults are
    evaluated in main(), so it lives at module level.
    """
    keys = (
        'SQL_SERVER', 'SQL_DATABASE', 'SQL_AUTH_TYPE', 'SQL_USER', 'SQL_PASSWORD',
        'SQL_ENCRYPT', 'SQL_TRUST_CERT', 'SQL_DRIVER',
        'AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET',
    )
    for key in keys:
        if not os.environ.get(key):
            fallback = os.environ.get(f'CLAUDE_PLUGIN_OPTION_{key}')
            if fallback:
                os.environ[key] = fallback


_load_plugin_userconfig_env()


class SQLServerReader:
    """Read-only SQL Server query executor with CSV export."""
    
    # SQL keywords that indicate write operations (blocked)
    WRITE_OPERATIONS = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 
        'CREATE', 'TRUNCATE', 'EXECUTE', 'EXEC', 'MERGE',
        'GRANT', 'REVOKE', 'DENY'
    ]
    
    def __init__(
        self, 
        server: str = 'localhost',
        database: str = '',
        username: str = '',
        password: str = '',
        driver: str = 'ODBC Driver 17 for SQL Server',
        timeout: int = 30,
        verbose: bool = False
    ):
        """Initialize SQL Server connection parameters."""
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.driver = driver
        self.timeout = timeout
        self.verbose = verbose
        self.connection = None
        self.engine = None
        
        # Set up export directory
        # Primary: use CWD (Claude Code sets CWD to the user's project)
        # Fallback: walk up from script location (dev-only)
        cwd = Path.cwd()
        if (cwd / '7 - Data Exports').exists():
            project_root = cwd
        else:
            project_root = cwd  # Use CWD anyway; mkdir below creates the folder
        self.export_dir = project_root / '7 - Data Exports'
        self.export_dir.mkdir(exist_ok=True)
        
    def _log(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(f"[INFO] {message}")
    
    def connect(self) -> bool:
        """Establish connection to SQL Server."""
        try:
            # Import shared connection builder
            sys.path.insert(0, str(Path(__file__).parent / '../../sql-connection/scripts'))
            from connect import build_pyodbc_connection, build_sqlalchemy_url

            self._log(f"Connecting to {self.server}/{self.database}...")

            # pyodbc connection for direct queries
            self.connection = build_pyodbc_connection(
                self.server, self.database, self.username, self.password,
                self.driver, self.timeout)

            # SQLAlchemy engine for pandas operations
            url, connect_args = build_sqlalchemy_url(
                self.server, self.database, self.username, self.password, self.driver)
            self.engine = create_engine(url, **({"connect_args": connect_args} if connect_args else {}))

            self._log("Connected successfully")
            return True

        except Exception as e:
            print(f"Connection failed: {e}", file=sys.stderr)
            return False
    
    def disconnect(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
        if self.engine:
            self.engine.dispose()
        self._log("✓ Disconnected")
    
    def validate_query(self, query: str) -> tuple[bool, str]:
        """
        Validate query is read-only (SELECT statements only).
        
        Returns:
            (is_valid, error_message)
        """
        query_upper = query.upper()
        
        # Check for write operations
        for operation in self.WRITE_OPERATIONS:
            # Use word boundaries to avoid false positives (e.g., "INSERTED" in a comment)
            pattern = r'\b' + operation + r'\b'
            if re.search(pattern, query_upper):
                return False, f"Query contains prohibited operation: {operation}"
        
        # Must contain SELECT (or WITH for CTEs)
        if 'SELECT' not in query_upper and 'WITH' not in query_upper:
            return False, "Query must be a SELECT statement"
        
        return True, ""
    
    def list_tables(self) -> pd.DataFrame:
        """List all tables in the database."""
        query = """
        SELECT 
            TABLE_SCHEMA as [Schema],
            TABLE_NAME as [Table],
            TABLE_TYPE as [Type]
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        
        self._log("Fetching table list...")
        df = pd.read_sql(query, self.engine)
        
        # Save to CSV
        output_file = self.export_dir / 'table_list.csv'
        df.to_csv(output_file, index=False)
        self._log(f"✓ Saved to {output_file}")
        
        return df
    
    def get_table_schema(self, table_name: str) -> pd.DataFrame:
        """Get schema information for a specific table."""
        query = """
        SELECT 
            COLUMN_NAME as [Column],
            DATA_TYPE as [Type],
            CHARACTER_MAXIMUM_LENGTH as [Max_Length],
            IS_NULLABLE as [Nullable],
            COLUMN_DEFAULT as [Default],
            CASE 
                WHEN pk.COLUMN_NAME IS NOT NULL THEN 'PK'
                ELSE ''
            END as [Key]
        FROM INFORMATION_SCHEMA.COLUMNS c
        LEFT JOIN (
            SELECT ku.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                AND ku.TABLE_NAME = ?
        ) pk ON c.COLUMN_NAME = pk.COLUMN_NAME
        WHERE c.TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
        """
        
        self._log(f"Fetching schema for table: {table_name}")
        df = pd.read_sql(text(query), self.engine, params={'table_name': table_name})
        
        if df.empty:
            print(f"⚠️  Table '{table_name}' not found", file=sys.stderr)
            return df
        
        # Save to CSV
        output_file = self.export_dir / f'schema_{table_name}.csv'
        df.to_csv(output_file, index=False)
        self._log(f"✓ Saved to {output_file}")
        
        return df
    
    def execute_query(
        self, 
        query: str, 
        limit: Optional[int] = None,
        output_filename: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Execute SELECT query and return results.
        
        Args:
            query: SQL SELECT statement
            limit: Maximum rows to return (adds TOP clause)
            output_filename: Custom filename for CSV export
        """
        # Validate query is read-only
        is_valid, error_msg = self.validate_query(query)
        if not is_valid:
            print(f"❌ Invalid query: {error_msg}", file=sys.stderr)
            print(f"Only SELECT statements are allowed.", file=sys.stderr)
            sys.exit(1)
        
        # Add limit if specified
        if limit:
            # Simple approach: wrap query in SELECT TOP
            query = f"SELECT TOP {limit} * FROM ({query}) AS limited_query"
        
        self._log("Executing query...")
        start_time = datetime.now()
        
        try:
            df = pd.read_sql(query, self.engine)
            elapsed = (datetime.now() - start_time).total_seconds()
            
            self._log(f"✓ Query executed in {elapsed:.2f}s")
            self._log(f"✓ Returned {len(df)} rows, {len(df.columns)} columns")
            
            # Save to CSV
            if output_filename:
                output_file = self.export_dir / output_filename
            else:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = self.export_dir / f'query_results_{timestamp}.csv'
            
            df.to_csv(output_file, index=False)
            self._log(f"✓ Saved to {output_file}")
            
            # Warn if result set is large
            if len(df) >= 10000:
                print(f"⚠️  Large result set: {len(df)} rows. Consider adding --limit")
            
            return df
            
        except pyodbc.Error as e:
            print(f"❌ Query execution failed: {e}", file=sys.stderr)
            sys.exit(1)
    
    def export_table(
        self, 
        table_name: str, 
        limit: Optional[int] = None,
        output_filename: Optional[str] = None
    ) -> pd.DataFrame:
        """Export entire table to CSV."""
        query = f"SELECT * FROM {table_name}"
        
        if not output_filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'{table_name}_{timestamp}.csv'
        
        return self.execute_query(query, limit=limit, output_filename=output_filename)
    
    def test_connection(self) -> bool:
        """Test database connection and print diagnostics."""
        print("Testing SQL Server connection...")
        print(f"Server: {self.server}")
        print(f"Database: {self.database}")
        print(f"User: {self.username}")
        print(f"Driver: {self.driver}")
        print()
        
        if not self.connect():
            return False
        
        try:
            # Test query
            cursor = self.connection.cursor()
            cursor.execute("SELECT @@VERSION as Version, DB_NAME() as DatabaseName")
            row = cursor.fetchone()
            
            print("✓ Connection successful!")
            print(f"Database: {row.DatabaseName}")
            print(f"SQL Server Version: {row.Version[:80]}...")
            
            # List available tables
            df_tables = self.list_tables()
            print(f"\n✓ Found {len(df_tables)} tables/views")
            
            return True
            
        except pyodbc.Error as e:
            print(f"❌ Connection test failed: {e}", file=sys.stderr)
            return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Query SQL Server with read-only access',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all tables
  python query_sql_server.py --list-tables
  
  # Get table schema
  python query_sql_server.py --schema customers
  
  # Execute query
  python query_sql_server.py --query "SELECT TOP 10 * FROM orders"
  
  # Export table
  python query_sql_server.py --export products --limit 1000
  
  # Query from file
  python query_sql_server.py --query-file analysis.sql
  
  # Test connection
  python query_sql_server.py --test-connection
        """
    )
    
    # Connection parameters
    parser.add_argument('--server', default='localhost', help='SQL Server instance')
    parser.add_argument('--database', default=os.environ.get('SQL_DATABASE', ''), help='Database name (env: DBT_DATABASE)')
    parser.add_argument('--user', default=os.environ.get('SQL_USER', ''), help='SQL Server username (env: SQL_USER, empty=Windows Auth)')
    parser.add_argument('--password', default=os.environ.get('SQL_PASSWORD', ''), help='SQL Server password (env: SQL_PASSWORD, empty=Windows Auth)')
    parser.add_argument('--driver', default='ODBC Driver 17 for SQL Server', help='ODBC driver')
    parser.add_argument('--timeout', type=int, default=30, help='Connection timeout (seconds)')
    
    # Operations
    parser.add_argument('--list-tables', action='store_true', help='List all tables')
    parser.add_argument('--schema', metavar='TABLE', help='Get table schema')
    parser.add_argument('--query', metavar='SQL', help='Execute SELECT query')
    parser.add_argument('--query-file', metavar='FILE', help='Execute query from file')
    parser.add_argument('--export', metavar='TABLE', help='Export table to CSV')
    parser.add_argument('--test-connection', action='store_true', help='Test database connection')
    
    # Options
    parser.add_argument('--limit', type=int, help='Limit number of rows returned')
    parser.add_argument('--output', metavar='FILE', help='Custom output filename')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    # Create reader instance
    reader = SQLServerReader(
        server=args.server,
        database=args.database,
        username=args.user,
        password=args.password,
        driver=args.driver,
        timeout=args.timeout,
        verbose=args.verbose
    )
    
    # Test connection mode
    if args.test_connection:
        success = reader.test_connection()
        reader.disconnect()
        sys.exit(0 if success else 1)
    
    # Connect to database
    if not reader.connect():
        sys.exit(1)
    
    try:
        # Execute requested operation
        if args.list_tables:
            df = reader.list_tables()
            print("\n" + df.to_string(index=False))
            print(f"\nTotal: {len(df)} tables/views")
            print(f"Saved to: 7 - Data Exports/table_list.csv")
        
        elif args.schema:
            df = reader.get_table_schema(args.schema)
            if not df.empty:
                print("\n" + df.to_string(index=False))
                print(f"\nSaved to: 7 - Data Exports/schema_{args.schema}.csv")
        
        elif args.query:
            df = reader.execute_query(args.query, limit=args.limit, output_filename=args.output)
            print("\n" + df.to_string(index=False, max_rows=20))
            if len(df) > 20:
                print(f"... ({len(df) - 20} more rows)")
        
        elif args.query_file:
            query_path = Path(args.query_file)
            if not query_path.exists():
                print(f"❌ Query file not found: {args.query_file}", file=sys.stderr)
                sys.exit(1)
            
            query = query_path.read_text()
            df = reader.execute_query(query, limit=args.limit, output_filename=args.output)
            print("\n" + df.to_string(index=False, max_rows=20))
            if len(df) > 20:
                print(f"... ({len(df) - 20} more rows)")
        
        elif args.export:
            df = reader.export_table(args.export, limit=args.limit, output_filename=args.output)
            print(f"✓ Exported {len(df)} rows from '{args.export}'")
            print(f"Columns: {', '.join(df.columns.tolist())}")
        
        else:
            parser.print_help()
    
    finally:
        reader.disconnect()


if __name__ == '__main__':
    main()
