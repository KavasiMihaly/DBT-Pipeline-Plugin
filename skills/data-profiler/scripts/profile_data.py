#!/usr/bin/env python3
"""
Data Profiler Skill
Automatically profile SQL Server tables and CSV files with intelligent analysis.
Detects primary keys, calculates statistics, infers data types, and recommends dbt tests.
"""

import argparse
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import re
import glob as file_glob

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import URL


class DataProfiler:
    """Intelligent data profiling for SQL Server tables and CSV files."""

    def __init__(
        self,
        server: str = 'localhost',
        database: str = '',
        username: str = '',
        password: str = '',
        driver: str = 'ODBC Driver 17 for SQL Server',
        verbose: bool = False,
        source_type: str = 'sql'  # 'sql' or 'csv'
    ):
        """Initialize data source parameters."""
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.driver = driver
        self.verbose = verbose
        self.source_type = source_type
        self.engine = None
        self.csv_data = None  # For CSV profiling

        # Set up export directory - use current working directory as project root
        # Look for project markers (CLAUDE.md, dbt_project.yml, or standard folders)
        cwd = Path.cwd()
        project_root = cwd

        # Walk up to find project root with documentation folder
        for _ in range(5):
            if (project_root / '1 - Documentation').exists() or (project_root / 'CLAUDE.md').exists():
                break
            if project_root.parent == project_root:
                break
            project_root = project_root.parent

        # Default export to 1 - Documentation/data-profiles/ as per documentation
        self.export_dir = project_root / '1 - Documentation' / 'data-profiles'
        self.export_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _parse_table_name(table_name: str) -> tuple:
        """Parse a potentially schema-qualified table name into (schema, table).

        Examples:
            'raw.epraccur'  -> ('raw', 'epraccur')
            'dbo.customers' -> ('dbo', 'customers')
            'customers'     -> (None, 'customers')
        """
        parts = table_name.split('.')
        if len(parts) == 2:
            return parts[0], parts[1]
        return None, parts[-1]

    def _log(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(f"[INFO] {message}")

    def connect(self) -> bool:
        """Establish connection to SQL Server."""
        try:
            # Import shared connection builder
            sys.path.insert(0, str(Path(__file__).parent / '../../sql-connection/scripts'))
            from connect import build_sqlalchemy_url

            self._log(f"Connecting to {self.server}/{self.database}...")

            url, connect_args = build_sqlalchemy_url(
                self.server, self.database, self.username, self.password, self.driver)
            self.engine = create_engine(url, **({"connect_args": connect_args} if connect_args else {}))

            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            self._log(f"Connected to {self.server}/{self.database}")
            return True

        except Exception as e:
            print(f"Connection failed: {e}", file=sys.stderr)
            return False

    def disconnect(self):
        """Close database connection."""
        if self.engine:
            self.engine.dispose()
            self._log("✓ Disconnected")

    def load_csv(self, file_path: str) -> bool:
        """Load CSV file into pandas DataFrame."""
        try:
            csv_path = Path(file_path)
            if not csv_path.exists():
                print(f"❌ File not found: {file_path}", file=sys.stderr)
                return False

            self._log(f"Loading CSV: {csv_path.name}")
            
            # Read CSV with type inference
            self.csv_data = pd.read_csv(file_path, low_memory=False)
            
            # Attempt to infer better types
            self.csv_data = self._infer_types(self.csv_data)
            
            self._log(f"✓ Loaded {len(self.csv_data):,} rows, {len(self.csv_data.columns)} columns")
            return True

        except Exception as e:
            print(f"❌ Failed to load CSV: {e}", file=sys.stderr)
            return False

    def _infer_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Infer and convert data types more intelligently."""
        for col in df.columns:
            # Skip if already numeric or datetime
            if df[col].dtype in ['int64', 'float64', 'datetime64[ns]']:
                continue

            # Try to convert to numeric
            try:
                converted = pd.to_numeric(df[col], errors='coerce')
                # If most values converted successfully, use numeric type
                if converted.notna().sum() / len(df) > 0.9:
                    df[col] = converted
                    continue
            except:
                pass

            # Try to convert to datetime
            try:
                converted = pd.to_datetime(df[col], errors='coerce')
                # If most values converted successfully, use datetime type
                if converted.notna().sum() / len(df) > 0.9:
                    df[col] = converted
                    continue
            except:
                pass

        return df

    def _map_pandas_to_sql_type(self, dtype) -> str:
        """Map pandas dtype to SQL Server data type."""
        dtype_str = str(dtype)
        
        if 'int' in dtype_str:
            return 'bigint'
        elif 'float' in dtype_str:
            return 'decimal'
        elif 'datetime' in dtype_str:
            return 'datetime2'
        elif 'bool' in dtype_str:
            return 'bit'
        else:
            return 'nvarchar'

    def get_table_row_count(self, table_name: str, sample_size: Optional[int] = None) -> int:
        """Get total row count for table or CSV."""
        if self.source_type == 'csv':
            if sample_size:
                return min(sample_size, len(self.csv_data))
            return len(self.csv_data)
        
        if sample_size:
            return sample_size

        query = f"SELECT COUNT(*) as row_count FROM {table_name}"
        with self.engine.connect() as conn:
            result = conn.execute(text(query))
            return result.fetchone()[0]

    def get_column_info(self, table_name: str) -> pd.DataFrame:
        """Get column metadata from SQL Server or CSV."""
        if self.source_type == 'csv':
            # Build column info from CSV DataFrame
            columns_data = []
            for col in self.csv_data.columns:
                sql_type = self._map_pandas_to_sql_type(self.csv_data[col].dtype)
                columns_data.append({
                    'column_name': col,
                    'data_type': sql_type,
                    'max_length': None,
                    'is_nullable': 'YES' if self.csv_data[col].isna().any() else 'NO',
                    'is_primary_key': 0
                })
            return pd.DataFrame(columns_data)
        
        # Split schema-qualified name for INFORMATION_SCHEMA queries
        schema_name, bare_table = self._parse_table_name(table_name)

        # Build schema filter clause
        if schema_name:
            schema_filter = "AND c.TABLE_SCHEMA = :schema_name"
            pk_schema_filter = "AND ku.TABLE_SCHEMA = :schema_name"
        else:
            schema_filter = ""
            pk_schema_filter = ""

        query = f"""
        SELECT
            COLUMN_NAME as column_name,
            DATA_TYPE as data_type,
            CHARACTER_MAXIMUM_LENGTH as max_length,
            IS_NULLABLE as is_nullable,
            CASE
                WHEN pk.COLUMN_NAME IS NOT NULL THEN 1
                ELSE 0
            END as is_primary_key
        FROM INFORMATION_SCHEMA.COLUMNS c
        LEFT JOIN (
            SELECT ku.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                AND ku.TABLE_NAME = :bare_table
                {pk_schema_filter}
        ) pk ON c.COLUMN_NAME = pk.COLUMN_NAME
        WHERE c.TABLE_NAME = :bare_table
            {schema_filter}
        ORDER BY ORDINAL_POSITION
        """

        params = {'bare_table': bare_table}
        if schema_name:
            params['schema_name'] = schema_name

        return pd.read_sql(text(query), self.engine, params=params)

    def profile_column(
        self,
        table_name: str,
        column_name: str,
        data_type: str,
        total_rows: int,
        sample_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Profile a single column from SQL Server or CSV."""

        self._log(f"  Profiling column: {column_name}")

        if self.source_type == 'csv':
            return self._profile_csv_column(column_name, data_type, total_rows, sample_size)
        else:
            return self._profile_sql_column(table_name, column_name, data_type, total_rows, sample_size)

    def _profile_csv_column(
        self,
        column_name: str,
        data_type: str,
        total_rows: int,
        sample_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Profile a column from CSV data."""
        
        # Get column data (sample if needed)
        col_data = self.csv_data[column_name]
        if sample_size:
            col_data = col_data.head(sample_size)

        # Base statistics
        total_count = len(col_data)
        non_null_count = col_data.notna().sum()
        null_count = col_data.isna().sum()
        distinct_count = col_data.nunique()

        profile = {
            'column_name': column_name,
            'data_type': data_type,
            'total_count': total_count,
            'non_null_count': int(non_null_count),
            'null_count': int(null_count),
            'null_percentage': (null_count / total_count * 100) if total_count > 0 else 0,
            'distinct_count': int(distinct_count),
            'cardinality_percentage': (distinct_count / non_null_count * 100) if non_null_count > 0 else 0
        }

        # Type-specific statistics
        non_null_data = col_data.dropna()

        if data_type in ('bigint', 'decimal', 'int', 'float'):
            # Numeric column
            if len(non_null_data) > 0:
                profile['min_value'] = float(non_null_data.min())
                profile['max_value'] = float(non_null_data.max())
                profile['avg_value'] = float(non_null_data.mean())

        elif data_type in ('nvarchar', 'varchar', 'text'):
            # String column
            if len(non_null_data) > 0:
                str_lengths = non_null_data.astype(str).str.len()
                profile['min_length'] = int(str_lengths.min())
                profile['max_length'] = int(str_lengths.max())
                profile['avg_length'] = float(str_lengths.mean())

                # Pattern detection
                profile['pattern'] = self._detect_pattern_csv(non_null_data)

        elif data_type in ('datetime2', 'date', 'datetime'):
            # Date column
            if len(non_null_data) > 0:
                profile['min_value'] = str(non_null_data.min())
                profile['max_value'] = str(non_null_data.max())

        # Get top 5 most common values if low cardinality
        if distinct_count <= 10 and distinct_count > 0:
            top_values = non_null_data.value_counts().head(5)
            profile['top_values'] = [
                {'value': str(val), 'count': int(count)}
                for val, count in top_values.items()
            ]

        return profile

    def _detect_pattern_csv(self, series: pd.Series) -> Optional[str]:
        """Detect common patterns in CSV string columns."""
        str_series = series.astype(str)
        
        # Email pattern
        email_count = str_series.str.contains(r'@.+\..+', regex=True, na=False).sum()
        if email_count / len(series) > 0.8:
            return 'email'

        # Phone pattern
        phone_count = str_series.str.contains(r'^\+?\d[\d\s\-\(\)]+$', regex=True, na=False).sum()
        if phone_count / len(series) > 0.8:
            return 'phone'

        # URL pattern
        url_count = str_series.str.contains(r'^https?://|^www\.', regex=True, na=False).sum()
        if url_count / len(series) > 0.8:
            return 'url'

        return None

    def _profile_sql_column(
        self,
        table_name: str,
        column_name: str,
        data_type: str,
        total_rows: int,
        sample_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Profile a single column from SQL Server (original logic)."""

        self._log(f"  Profiling column: {column_name}")

        # Build sample clause if needed
        sample_clause = f"TOP {sample_size}" if sample_size else ""

        # Base statistics query
        base_query = f"""
        SELECT
            COUNT(*) as total_count,
            COUNT({column_name}) as non_null_count,
            COUNT(*) - COUNT({column_name}) as null_count,
            COUNT(DISTINCT {column_name}) as distinct_count
        FROM (SELECT {sample_clause} {column_name} FROM {table_name}) sampled
        """

        with self.engine.connect() as conn:
            result = conn.execute(text(base_query)).fetchone()

            profile = {
                'column_name': column_name,
                'data_type': data_type,
                'total_count': result.total_count,
                'non_null_count': result.non_null_count,
                'null_count': result.null_count,
                'null_percentage': (result.null_count / result.total_count * 100) if result.total_count > 0 else 0,
                'distinct_count': result.distinct_count,
                'cardinality_percentage': (result.distinct_count / result.non_null_count * 100) if result.non_null_count > 0 else 0
            }

            # Add type-specific statistics
            if data_type in ('int', 'bigint', 'smallint', 'tinyint', 'decimal', 'numeric', 'float', 'real', 'money', 'smallmoney'):
                # Numeric column
                numeric_query = f"""
                SELECT
                    MIN({column_name}) as min_value,
                    MAX({column_name}) as max_value,
                    AVG(CAST({column_name} as FLOAT)) as avg_value
                FROM (SELECT {sample_clause} {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL) sampled
                """
                num_result = conn.execute(text(numeric_query)).fetchone()
                profile['min_value'] = num_result.min_value
                profile['max_value'] = num_result.max_value
                profile['avg_value'] = num_result.avg_value

            elif data_type in ('varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext'):
                # String column
                string_query = f"""
                SELECT
                    MIN(LEN({column_name})) as min_length,
                    MAX(LEN({column_name})) as max_length,
                    AVG(LEN({column_name})) as avg_length
                FROM (SELECT {sample_clause} {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL) sampled
                """
                str_result = conn.execute(text(string_query)).fetchone()
                profile['min_length'] = str_result.min_length
                profile['max_length'] = str_result.max_length
                profile['avg_length'] = str_result.avg_length

                # Pattern detection for emails, phones, URLs
                profile['pattern'] = self._detect_pattern(conn, table_name, column_name, sample_clause)

            elif data_type in ('date', 'datetime', 'datetime2', 'smalldatetime', 'datetimeoffset'):
                # Date column
                date_query = f"""
                SELECT
                    MIN({column_name}) as min_date,
                    MAX({column_name}) as max_date
                FROM (SELECT {sample_clause} {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL) sampled
                """
                date_result = conn.execute(text(date_query)).fetchone()
                profile['min_value'] = str(date_result.min_date)
                profile['max_value'] = str(date_result.max_date)

            # Get top 5 most common values if low cardinality
            if profile['distinct_count'] <= 10 and profile['distinct_count'] > 0:
                top_values_query = f"""
                SELECT TOP 5
                    {column_name} as value,
                    COUNT(*) as count
                FROM (SELECT {sample_clause} {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL) sampled
                GROUP BY {column_name}
                ORDER BY COUNT(*) DESC
                """
                top_values = conn.execute(text(top_values_query)).fetchall()
                profile['top_values'] = [
                    {'value': str(row.value), 'count': row.count}
                    for row in top_values
                ]

        return profile

    def _detect_pattern(self, conn, table_name: str, column_name: str, sample_clause: str) -> Optional[str]:
        """Detect common patterns in string columns."""

        # Email pattern
        email_query = f"""
        SELECT COUNT(*) as email_count
        FROM (SELECT {sample_clause} {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL) sampled
        WHERE {column_name} LIKE '%@%.%'
        """
        email_result = conn.execute(text(email_query)).fetchone()

        # Phone pattern (various formats)
        phone_query = f"""
        SELECT COUNT(*) as phone_count
        FROM (SELECT {sample_clause} {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL) sampled
        WHERE {column_name} LIKE '[0-9][0-9][0-9]%'
            OR {column_name} LIKE '([0-9][0-9][0-9]%'
            OR {column_name} LIKE '+[0-9]%'
        """
        phone_result = conn.execute(text(phone_query)).fetchone()

        # URL pattern
        url_query = f"""
        SELECT COUNT(*) as url_count
        FROM (SELECT {sample_clause} {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL) sampled
        WHERE {column_name} LIKE 'http%'
            OR {column_name} LIKE 'www.%'
        """
        url_result = conn.execute(text(url_query)).fetchone()

        # Determine pattern based on highest match
        total_query = f"SELECT COUNT(*) as total FROM (SELECT {sample_clause} {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL) sampled"
        total = conn.execute(text(total_query)).fetchone().total

        if total == 0:
            return None

        email_pct = (email_result.email_count / total * 100)
        phone_pct = (phone_result.phone_count / total * 100)
        url_pct = (url_result.url_count / total * 100)

        if email_pct > 80:
            return f"Email format ({email_pct:.1f}%)"
        elif phone_pct > 80:
            return f"Phone format ({phone_pct:.1f}%)"
        elif url_pct > 80:
            return f"URL format ({url_pct:.1f}%)"

        return None

    def identify_primary_key_candidates(self, profiles: List[Dict[str, Any]], pk_threshold: float = 99.0) -> List[str]:
        """Identify columns that could be primary keys."""

        candidates = []

        for profile in profiles:
            # Primary key criteria:
            # 1. High cardinality (near 100%)
            # 2. Low or no nulls (0%)
            # 3. Reasonable data type (int, bigint, uniqueidentifier, etc.)

            is_high_cardinality = profile['cardinality_percentage'] >= pk_threshold
            is_low_null = profile['null_percentage'] <= (100 - pk_threshold)
            is_appropriate_type = profile['data_type'] in (
                'int', 'bigint', 'uniqueidentifier', 'varchar', 'nvarchar'
            )

            if is_high_cardinality and is_low_null and is_appropriate_type:
                candidates.append(profile['column_name'])

        return candidates

    def recommend_tests(self, profile: Dict[str, Any], is_pk_candidate: bool) -> List[str]:
        """Recommend dbt tests based on column profile."""

        tests = []

        # Primary key tests
        if is_pk_candidate:
            tests.append('unique')
            tests.append('not_null')

        # Not null test (if low nulls but not PK)
        elif profile['null_percentage'] < 5 and not is_pk_candidate:
            tests.append('not_null')

        # Accepted values test (low cardinality)
        if profile['distinct_count'] <= 10 and profile['distinct_count'] > 0:
            if 'top_values' in profile:
                values = [v['value'] for v in profile['top_values']]
                tests.append(f"accepted_values: {values}")

        # Relationships test (foreign key pattern)
        column_name = profile['column_name'].lower()
        if (column_name.endswith('_id') or column_name.endswith('_key')) and not is_pk_candidate:
            # Extract potential parent table name
            parent = column_name.replace('_id', '').replace('_key', '')
            tests.append(f"relationships to dim_{parent} or fct_{parent}")

        # Custom tests based on patterns
        if 'pattern' in profile and profile['pattern']:
            if 'Email' in profile['pattern']:
                tests.append('email_format (custom test)')
            elif 'Phone' in profile['pattern']:
                tests.append('phone_format (custom test)')
            elif 'URL' in profile['pattern']:
                tests.append('url_format (custom test)')

        # Range tests for numeric columns with negative values (if business logic prohibits)
        if 'min_value' in profile and profile['min_value'] is not None:
            try:
                min_val = float(profile['min_value'])
                if min_val < 0 and 'amount' in column_name.lower():
                    tests.append('non_negative (custom test)')
            except (ValueError, TypeError):
                # min_value is not numeric, skip negative check
                pass

        return tests

    def identify_data_quality_issues(self, profiles: List[Dict[str, Any]]) -> List[str]:
        """Identify data quality issues from profiles."""

        issues = []

        for profile in profiles:
            column_name = profile['column_name']

            # High null percentage
            if profile['null_percentage'] > 20:
                issues.append(
                    f"⚠️  {column_name} has {profile['null_count']:,} nulls "
                    f"({profile['null_percentage']:.1f}%) - Consider if column is needed"
                )
            elif profile['null_percentage'] > 5:
                issues.append(
                    f"⚠️  {column_name} has {profile['null_count']:,} nulls "
                    f"({profile['null_percentage']:.1f}%) - Handle in staging model"
                )

            # Very low cardinality (potential data quality issue)
            if profile['distinct_count'] <= 3 and profile['cardinality_percentage'] < 1:
                issues.append(
                    f"⚠️  {column_name} has only {profile['distinct_count']} distinct values "
                    f"- Use accepted_values test"
                )

            # Negative values in amount/price columns
            if 'min_value' in profile and profile['min_value'] is not None:
                column_lower = column_name.lower()
                # Only check for negative values if min_value is numeric
                try:
                    min_val = float(profile['min_value'])
                    if min_val < 0 and any(
                        keyword in column_lower
                        for keyword in ['amount', 'price', 'total', 'cost', 'revenue']
                    ):
                        issues.append(
                            f"⚠️  {column_name} has negative values (min: {profile['min_value']}) "
                            f"- Verify business logic"
                        )
                except (ValueError, TypeError):
                    # min_value is not numeric (e.g., datetime string), skip negative check
                    pass

        return issues

    def generate_recommendations(
        self,
        table_name: str,
        profiles: List[Dict[str, Any]],
        pk_candidates: List[str],
        quality_issues: List[str]
    ) -> List[str]:
        """Generate actionable recommendations for staging model."""

        recommendations = []

        # Primary key recommendation
        if pk_candidates:
            pk = pk_candidates[0]  # Use first candidate
            recommendations.append(f"Use {pk} as primary key")
            recommendations.append(f"Add unique + not_null tests to {pk}")
        else:
            recommendations.append(
                "⚠️  No clear primary key candidate - Consider creating surrogate key"
            )

        # Not null tests
        not_null_columns = [
            p['column_name'] for p in profiles
            if p['null_percentage'] < 5 and p['column_name'] not in pk_candidates
        ]
        if not_null_columns:
            recommendations.append(
                f"Add not_null tests to: {', '.join(not_null_columns[:5])}"
            )

        # Accepted values tests
        categorical_columns = [
            p['column_name'] for p in profiles
            if p['distinct_count'] <= 10 and p['distinct_count'] > 0
        ]
        if categorical_columns:
            recommendations.append(
                f"Add accepted_values tests to: {', '.join(categorical_columns)}"
            )

        # Handle nulls
        nullable_columns = [
            p['column_name'] for p in profiles
            if p['null_percentage'] > 5
        ]
        if nullable_columns:
            recommendations.append(
                f"Handle nulls in: {', '.join(nullable_columns[:5])}"
            )

        # Custom tests for patterns
        pattern_columns = [
            p['column_name'] for p in profiles
            if 'pattern' in p and p['pattern']
        ]
        if pattern_columns:
            recommendations.append(
                f"Consider format validation tests for: {', '.join(pattern_columns)}"
            )

        return recommendations

    def generate_dbt_yaml(
        self,
        table_name: str,
        profiles: List[Dict[str, Any]],
        pk_candidates: List[str]
    ) -> str:
        """Generate dbt schema.yml scaffold."""

        # Convert table name to staging model name
        model_name = f"stg_{table_name.replace('raw_', '').replace('.', '__')}"

        yaml_lines = [
            "models:",
            f"  - name: {model_name}",
            f'    description: "Staging model for {table_name}"',
            "    columns:"
        ]

        for profile in profiles:
            column_name = profile['column_name']
            is_pk = column_name in pk_candidates

            yaml_lines.append(f"      - name: {column_name}")

            # Add description
            if is_pk:
                yaml_lines.append(f'        description: "Primary key for {table_name}"')
            else:
                yaml_lines.append(f'        description: "{column_name}"')

            # Add tests
            tests = self.recommend_tests(profile, is_pk)
            if tests:
                yaml_lines.append("        tests:")
                for test in tests:
                    if ':' in test:
                        # Complex test like accepted_values
                        test_name = test.split(':')[0].strip()
                        yaml_lines.append(f"          - {test_name}")
                    else:
                        yaml_lines.append(f"          - {test}")

            yaml_lines.append("")  # Blank line between columns

        return '\n'.join(yaml_lines)

    def profile_table(
        self,
        table_name: str,
        sample_size: Optional[int] = None,
        quick: bool = False,
        columns: Optional[List[str]] = None,
        pk_threshold: float = 99.0
    ) -> Dict[str, Any]:
        """
        Profile a complete table or CSV file.

        Args:
            table_name: Name of table to profile (or CSV file identifier)
            sample_size: Sample size for large tables/files
            quick: Quick mode (basic stats only)
            columns: Specific columns to profile
            pk_threshold: Threshold for PK candidate detection (default 99%)

        Returns:
            Dictionary with complete profile
        """

        self._log(f"Profiling {'file' if self.source_type == 'csv' else 'table'}: {table_name}")

        # Get row count
        total_rows = self.get_table_row_count(table_name, sample_size)
        self._log(f"  Total rows: {total_rows:,}")

        # Get column metadata
        column_info = self.get_column_info(table_name)

        if column_info.empty:
            print(f"❌ Table '{table_name}' not found", file=sys.stderr)
            return None

        # Filter columns if specified
        if columns:
            column_info = column_info[column_info['column_name'].isin(columns)]

        self._log(f"  Total columns: {len(column_info)}")

        # Profile each column
        profiles = []
        for _, col_info in column_info.iterrows():
            profile = self.profile_column(
                table_name,
                col_info['column_name'],
                col_info['data_type'],
                total_rows,
                sample_size
            )
            profiles.append(profile)

        # Identify primary key candidates
        pk_candidates = self.identify_primary_key_candidates(profiles, pk_threshold)

        # Identify data quality issues
        quality_issues = self.identify_data_quality_issues(profiles)

        # Generate recommendations
        recommendations = self.generate_recommendations(
            table_name, profiles, pk_candidates, quality_issues
        )

        # Build complete profile
        table_profile = {
            'table_name': table_name,
            'total_rows': total_rows,
            'total_columns': len(profiles),
            'primary_key_candidates': pk_candidates,
            'profile_date': datetime.now().isoformat(),
            'columns': profiles,
            'quality_issues': quality_issues,
            'recommendations': recommendations
        }

        return table_profile

    def format_profile_output(self, profile: Dict[str, Any]) -> str:
        """Format profile as human-readable text."""

        lines = []
        lines.append("=" * 70)
        lines.append(f"Data Profile: {profile['table_name']}")
        lines.append("=" * 70)
        lines.append("")

        # Table statistics
        lines.append("Table Statistics:")
        lines.append(f"  - Total Rows: {profile['total_rows']:,}")
        lines.append(f"  - Total Columns: {profile['total_columns']}")

        if profile['primary_key_candidates']:
            lines.append(f"  - Primary Key: {profile['primary_key_candidates'][0]} (detected)")
        else:
            lines.append("  - Primary Key: None detected")

        lines.append(f"  - Profile Date: {profile['profile_date']}")
        lines.append("")

        # Column profiles
        lines.append("Column Profiles:")
        lines.append("")

        for col_profile in profile['columns']:
            is_pk = col_profile['column_name'] in profile['primary_key_candidates']

            lines.append("┌" + "─" * 68 + "┐")
            lines.append(f"│ {col_profile['column_name']:<67}│")
            lines.append("├" + "─" * 68 + "┤")

            lines.append(f"│ Data Type      : {col_profile['data_type']:<51}│")
            lines.append(
                f"│ Nulls          : {col_profile['null_count']:,} "
                f"({col_profile['null_percentage']:.1f}%){' ' * (51 - len(str(col_profile['null_count'])) - len(f"{col_profile['null_percentage']:.1f}") - 6)}│"
            )
            lines.append(
                f"│ Distinct Values: {col_profile['distinct_count']:,} "
                f"({col_profile['cardinality_percentage']:.1f}%){' ' * (51 - len(str(col_profile['distinct_count'])) - len(f"{col_profile['cardinality_percentage']:.1f}") - 6)}│"
            )

            # Type-specific stats
            if 'min_value' in col_profile and col_profile['min_value'] is not None:
                lines.append(f"│ Min Value      : {col_profile['min_value']:<51}│")
                lines.append(f"│ Max Value      : {col_profile['max_value']:<51}│")

            if 'min_length' in col_profile:
                lines.append(f"│ Min Length     : {col_profile['min_length']:<51}│")
                lines.append(f"│ Max Length     : {col_profile['max_length']:<51}│")

            if 'pattern' in col_profile and col_profile['pattern']:
                lines.append(f"│ Pattern        : {col_profile['pattern']:<51}│")

            # Top values for low cardinality
            if 'top_values' in col_profile:
                top_vals_str = ', '.join([
                    f"{v['value']} ({v['count']:,})"
                    for v in col_profile['top_values']
                ])
                if len(top_vals_str) > 50:
                    top_vals_str = top_vals_str[:47] + "..."
                lines.append(f"│ Values         : {top_vals_str:<51}│")

            # Primary key indicator
            if is_pk:
                lines.append("│ ✓ PRIMARY KEY CANDIDATE                                            │")

            # Warnings
            if col_profile['null_percentage'] > 20:
                lines.append("│ ⚠️  High null percentage                                            │")
            elif col_profile['null_percentage'] > 5:
                lines.append("│ ⚠️  Contains nulls                                                  │")

            lines.append("│                                                                    │")

            # Recommended tests
            tests = self.recommend_tests(col_profile, is_pk)
            if tests:
                lines.append("│ Recommended Tests:                                                 │")
                for test in tests:
                    test_str = f"  - {test}"
                    if len(test_str) > 66:
                        test_str = test_str[:63] + "..."
                    lines.append(f"│   {test_str:<65}│")

            lines.append("└" + "─" * 68 + "┘")
            lines.append("")

        # Data quality issues
        if profile['quality_issues']:
            lines.append("Data Quality Issues:")
            for issue in profile['quality_issues']:
                lines.append(f"  {issue}")
            lines.append("")

        # Recommendations
        if profile['recommendations']:
            lines.append("Recommendations for Staging Model:")
            for i, rec in enumerate(profile['recommendations'], 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")

        return '\n'.join(lines)

    def save_profile(
        self,
        profile: Dict[str, Any],
        format: str = 'csv',
        output_filename: Optional[str] = None
    ) -> Path:
        """Save profile to file."""

        if output_filename:
            output_file = self.export_dir / output_filename
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Replace dots in schema-qualified names for safe filenames
            safe_name = profile['table_name'].replace('.', '__')
            if format == 'json':
                output_file = self.export_dir / f"profile_{safe_name}_{timestamp}.json"
            else:
                output_file = self.export_dir / f"profile_{safe_name}_{timestamp}.csv"

        if format == 'json':
            with open(output_file, 'w') as f:
                json.dump(profile, f, indent=2, default=str)

        elif format == 'csv':
            # Convert to DataFrame
            df = pd.DataFrame(profile['columns'])

            # Add PK indicator
            df['is_pk_candidate'] = df['column_name'].isin(profile['primary_key_candidates'])

            # Save to CSV
            df.to_csv(output_file, index=False)

        self._log(f"✓ Saved to {output_file}")
        return output_file


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Profile SQL Server tables and CSV files with intelligent analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  SQL Server:
    # Profile a table
    python profile_data.py --table customers

    # Profile multiple tables
    python profile_data.py --tables customers orders products

    # Profile with sample
    python profile_data.py --table large_table --sample 10000

  CSV Files:
    # Profile a CSV file
    python profile_data.py --file "2 - Source Files/casualties-2024.csv"

    # Profile multiple CSV files
    python profile_data.py --files "2 - Source Files/casualties-*.csv"

    # Profile with sample
    python profile_data.py --file data.csv --sample 10000

  General:
    # Quick profile
    python profile_data.py --table orders --quick

    # JSON output
    python profile_data.py --file data.csv --format json

    # Generate dbt YAML
    python profile_data.py --table customers --generate-yaml
        """
    )

    # Source selection
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument('--table', help='SQL Server table to profile')
    source_group.add_argument('--tables', nargs='+', help='Multiple SQL Server tables to profile')
    source_group.add_argument('--file', help='CSV file to profile')
    source_group.add_argument('--files', help='Glob pattern for multiple CSV files (e.g., "*.csv")')

    # SQL Server connection parameters
    parser.add_argument('--server', default='localhost', help='SQL Server instance')
    parser.add_argument('--database', default=os.environ.get('SQL_DATABASE', ''), help='Database name (env: DBT_DATABASE)')
    parser.add_argument('--user', default=os.environ.get('SQL_USER', ''), help='SQL Server username (env: SQL_USER, empty=Windows Auth)')
    parser.add_argument('--password', default=os.environ.get('SQL_PASSWORD', ''), help='SQL Server password (env: SQL_PASSWORD, empty=Windows Auth)')
    parser.add_argument('--driver', default='ODBC Driver 17 for SQL Server', help='ODBC driver')

    # Options
    parser.add_argument('--sample', type=int, help='Sample size for large tables/files')
    parser.add_argument('--quick', action='store_true', help='Quick mode (basic stats only)')
    parser.add_argument('--columns', nargs='+', help='Specific columns to profile')
    parser.add_argument('--pk-threshold', type=float, default=99.0, help='PK detection threshold (default: 99.0)')
    parser.add_argument('--format', choices=['csv', 'json', 'text'], default='text', help='Output format')
    parser.add_argument('--output', help='Custom output filename')
    parser.add_argument('--generate-yaml', action='store_true', help='Generate dbt schema.yml')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    # Validate arguments
    if not args.table and not args.tables and not args.file and not args.files:
        parser.error("Must specify --table, --tables, --file, or --files")

    # Determine source type and get list of sources
    if args.file or args.files:
        source_type = 'csv'
        if args.file:
            sources = [args.file]
        else:
            # Expand glob pattern
            sources = file_glob.glob(args.files)
            if not sources:
                print(f"❌ No files found matching pattern: {args.files}", file=sys.stderr)
                sys.exit(1)
    else:
        source_type = 'sql'
        sources = [args.table] if args.table else args.tables

    # Create profiler instance
    profiler = DataProfiler(
        server=args.server,
        database=args.database,
        username=args.user,
        password=args.password,
        driver=args.driver,
        verbose=args.verbose,
        source_type=source_type
    )

    # Connect to data source
    if source_type == 'sql':
        if not profiler.connect():
            sys.exit(1)

    try:
        for source in sources:
            if source_type == 'csv':
                # Load CSV file
                if not profiler.load_csv(source):
                    continue
                # Use filename as table_name for display
                table_name = Path(source).stem
            else:
                table_name = source

            print(f"\nProfiling {'file' if source_type == 'csv' else 'table'}: {table_name}")
            print("-" * 70)

            # Profile the table/file
            profile = profiler.profile_table(
                table_name,
                sample_size=args.sample,
                quick=args.quick,
                columns=args.columns,
                pk_threshold=args.pk_threshold
            )

            if not profile:
                continue

            # Output profile
            if args.format == 'text':
                print(profiler.format_profile_output(profile))
            elif args.format == 'json':
                print(json.dumps(profile, indent=2, default=str))

            # Generate dbt YAML if requested
            if args.generate_yaml:
                yaml_content = profiler.generate_dbt_yaml(
                    table_name,
                    profile['columns'],
                    profile['primary_key_candidates']
                )
                print("\nSuggested dbt YAML:")
                print(yaml_content)

            # Save profile
            output_format = args.format if args.format != 'text' else 'csv'
            output_file = profiler.save_profile(profile, output_format, args.output)
            print(f"\nExport saved to: {output_file}")

    finally:
        if source_type == 'sql':
            profiler.disconnect()


if __name__ == '__main__':
    main()
