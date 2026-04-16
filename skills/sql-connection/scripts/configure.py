#!/usr/bin/env python3
"""Configure SQL Server connection for the dbt-pipeline-toolkit plugin.

Writes connection settings to the project-level .claude/settings.local.json
under pluginConfigs.dbt-pipeline-toolkit.options. Tests the connection after
writing. Supports presets for common environments (azure, local).

Usage:
    # Azure SQL DB with Entra Interactive auth (conference demo)
    python configure.py --preset azure --server myserver.database.windows.net --database MyDB

    # Local SQL Server with Windows Auth
    python configure.py --preset local --database MyDB

    # Custom configuration
    python configure.py --server myserver --database MyDB --auth-type sql --user sa --password secret

    # Test current connection without changing config
    python configure.py --test-only
"""

import argparse
import json
import os
import sys
from pathlib import Path


# Presets for common environments
PRESETS = {
    'azure': {
        'sql_auth_type': 'entra_interactive',
        'sql_encrypt': 'true',
        'sql_trust_cert': 'false',
        'sql_driver': 'ODBC Driver 18 for SQL Server',
    },
    'local': {
        'sql_server': 'localhost',
        'sql_auth_type': 'windows',
        'sql_encrypt': 'false',
        'sql_trust_cert': 'true',
        'sql_driver': 'ODBC Driver 17 for SQL Server',
    },
    'local-sql': {
        'sql_server': 'localhost',
        'sql_auth_type': 'sql',
        'sql_encrypt': 'false',
        'sql_trust_cert': 'true',
        'sql_driver': 'ODBC Driver 17 for SQL Server',
    },
}


def find_project_root() -> Path:
    """Find the project root (directory with .claude/ or .git/)."""
    cwd = Path.cwd()
    for path in [cwd] + list(cwd.parents):
        if (path / '.claude').exists() or (path / '.git').exists():
            return path
    return cwd


def read_settings(settings_path: Path) -> dict:
    """Read existing settings.local.json or return empty dict."""
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def write_settings(settings_path: Path, settings: dict) -> None:
    """Write settings to settings.local.json."""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
    print(f"[SUCCESS] Settings written to {settings_path}")


def test_connection(options: dict) -> bool:
    """Test the SQL Server connection with the given options."""
    print("\n[INFO] Testing connection...")

    # Set env vars for the connection test
    env_mapping = {
        'sql_server': 'SQL_SERVER',
        'sql_database': 'SQL_DATABASE',
        'sql_auth_type': 'SQL_AUTH_TYPE',
        'sql_user': 'SQL_USER',
        'sql_password': 'SQL_PASSWORD',
        'sql_encrypt': 'SQL_ENCRYPT',
        'sql_trust_cert': 'SQL_TRUST_CERT',
        'sql_driver': 'SQL_DRIVER',
        'azure_tenant_id': 'AZURE_TENANT_ID',
        'azure_client_id': 'AZURE_CLIENT_ID',
        'azure_client_secret': 'AZURE_CLIENT_SECRET',
    }

    for config_key, env_key in env_mapping.items():
        value = options.get(config_key, '')
        if value:
            os.environ[env_key] = value

    try:
        import pyodbc

        server = options.get('sql_server', 'localhost')
        database = options.get('sql_database', '')
        driver = options.get('sql_driver', 'ODBC Driver 17 for SQL Server')
        auth_type = options.get('sql_auth_type', 'windows')
        encrypt = options.get('sql_encrypt', 'false').lower() == 'true'
        trust_cert = options.get('sql_trust_cert', 'true').lower() != 'false'

        encrypt_str = 'yes' if encrypt else 'no'
        trust_str = 'yes' if trust_cert else 'no'

        print(f"  Server:   {server}")
        print(f"  Database: {database}")
        print(f"  Auth:     {auth_type}")
        print(f"  Driver:   {driver}")
        print(f"  Encrypt:  {encrypt_str}")

        if auth_type == 'windows':
            conn_str = (
                f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
                f"Trusted_Connection=yes;"
                f"Encrypt={encrypt_str};TrustServerCertificate={trust_str};"
                f"Connection Timeout=15;"
            )
        elif auth_type == 'sql':
            user = options.get('sql_user', '')
            password = options.get('sql_password', '')
            conn_str = (
                f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
                f"UID={user};PWD={password};"
                f"Encrypt={encrypt_str};TrustServerCertificate={trust_str};"
                f"Connection Timeout=15;"
            )
        elif auth_type == 'entra_interactive':
            conn_str = (
                f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
                f"Authentication=ActiveDirectoryInteractive;"
                f"Encrypt=yes;TrustServerCertificate={trust_str};"
                f"Connection Timeout=30;"
            )
        else:
            print(f"[WARNING] Auth type '{auth_type}' — skipping connection test")
            return True

        print("  Connecting...")
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        # Truncate version string for display
        version_short = version.split('\n')[0][:80]
        print(f"\n[SUCCESS] Connected to: {version_short}")
        return True

    except ImportError:
        print("[ERROR] pyodbc not installed. Install with: pip install pyodbc")
        return False
    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Configure SQL Server connection for dbt-pipeline-toolkit',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Presets:
  azure       Azure SQL DB with Entra Interactive auth (browser login)
              Sets: encrypt=true, trust_cert=false, driver=ODBC 18
  local       Local SQL Server with Windows Auth
              Sets: server=localhost, encrypt=false, trust_cert=true
  local-sql   Local SQL Server with SQL Auth (username/password)
              Sets: server=localhost, encrypt=false, trust_cert=true

Examples:
  # Conference demo with Azure SQL DB
  python configure.py --preset azure --server myserver.database.windows.net --database DemoDB

  # Local development
  python configure.py --preset local --database Agentic

  # Test current connection
  python configure.py --test-only
"""
    )

    parser.add_argument('--preset', choices=['azure', 'local', 'local-sql'],
                        help='Use a preset configuration profile')
    parser.add_argument('--server', help='SQL Server hostname')
    parser.add_argument('--database', help='Database name')
    parser.add_argument('--auth-type', choices=['windows', 'sql', 'entra_interactive', 'entra_sp'],
                        help='Authentication type')
    parser.add_argument('--user', help='SQL username (for sql auth)')
    parser.add_argument('--password', help='SQL password (for sql auth)')
    parser.add_argument('--driver', help='ODBC driver name')
    parser.add_argument('--encrypt', choices=['true', 'false'], help='Encrypt connection')
    parser.add_argument('--trust-cert', choices=['true', 'false'], help='Trust server certificate')
    parser.add_argument('--test-only', action='store_true',
                        help='Only test current connection, do not write config')
    parser.add_argument('--no-test', action='store_true',
                        help='Write config without testing connection')

    args = parser.parse_args()

    # Build options from preset + overrides
    options = {}

    if args.preset:
        options.update(PRESETS[args.preset])
        print(f"[INFO] Using preset: {args.preset}")

    # CLI overrides take precedence over preset
    if args.server:
        options['sql_server'] = args.server
    if args.database:
        options['sql_database'] = args.database
    if args.auth_type:
        options['sql_auth_type'] = args.auth_type
    if args.user:
        options['sql_user'] = args.user
    if args.password:
        options['sql_password'] = args.password
    if args.driver:
        options['sql_driver'] = args.driver
    if args.encrypt:
        options['sql_encrypt'] = args.encrypt
    if args.trust_cert:
        options['sql_trust_cert'] = args.trust_cert

    # Test-only mode: read current config and test
    if args.test_only:
        project_root = find_project_root()
        settings_path = project_root / '.claude' / 'settings.local.json'
        settings = read_settings(settings_path)
        current_options = settings.get('pluginConfigs', {}).get('dbt-pipeline-toolkit', {}).get('options', {})

        if not current_options:
            print("[WARNING] No existing plugin configuration found")
            print(f"  Checked: {settings_path}")
            return 1

        print("[INFO] Current configuration:")
        for k, v in sorted(current_options.items()):
            if 'password' in k or 'secret' in k:
                print(f"  {k}: ****")
            else:
                print(f"  {k}: {v}")

        success = test_connection(current_options)
        return 0 if success else 1

    # Validate minimum required fields
    if not options.get('sql_database'):
        print("[ERROR] --database is required")
        return 1

    if not options.get('sql_server') and not args.preset:
        print("[ERROR] --server is required (or use --preset)")
        return 1

    # Write config
    project_root = find_project_root()
    settings_path = project_root / '.claude' / 'settings.local.json'

    print(f"\n[INFO] Project root: {project_root}")
    print(f"[INFO] Settings file: {settings_path}")

    # Read existing settings and merge
    settings = read_settings(settings_path)

    # Ensure nested structure exists
    if 'pluginConfigs' not in settings:
        settings['pluginConfigs'] = {}
    if 'dbt-pipeline-toolkit' not in settings['pluginConfigs']:
        settings['pluginConfigs']['dbt-pipeline-toolkit'] = {}
    if 'options' not in settings['pluginConfigs']['dbt-pipeline-toolkit']:
        settings['pluginConfigs']['dbt-pipeline-toolkit']['options'] = {}

    # Merge options (don't overwrite unrelated settings)
    settings['pluginConfigs']['dbt-pipeline-toolkit']['options'].update(options)

    # Show what we're writing
    print("\n[INFO] Configuration to write:")
    for k, v in sorted(options.items()):
        if 'password' in k or 'secret' in k:
            print(f"  {k}: ****")
        else:
            print(f"  {k}: {v}")

    write_settings(settings_path, settings)

    # Test connection unless --no-test
    if not args.no_test:
        full_options = settings['pluginConfigs']['dbt-pipeline-toolkit']['options']
        success = test_connection(full_options)
        if not success:
            print("\n[WARNING] Config saved but connection test failed.")
            print("  Check your server name, database, and authentication settings.")
            return 1

    print("\n[SUCCESS] Plugin configured and connection verified!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
