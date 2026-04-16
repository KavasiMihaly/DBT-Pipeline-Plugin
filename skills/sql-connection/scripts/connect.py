"""Shared SQL Server connection builder for all dbt-pipeline-toolkit scripts.

Supports 4 authentication types via SQL_AUTH_TYPE environment variable:
  - windows: Windows/Integrated Authentication (Trusted_Connection)
  - sql: SQL Server Authentication (username/password)
  - entra_interactive: Azure Entra ID with interactive browser login
  - entra_sp: Azure Entra ID with Service Principal (client credentials)

Environment variables (set by plugin userConfig or manually):
  SQL_SERVER       - Server hostname (default: localhost)
  SQL_DATABASE     - Database name
  SQL_AUTH_TYPE    - Auth method: windows, sql, entra_interactive, entra_sp
  SQL_USER         - Username (sql auth)
  SQL_PASSWORD     - Password (sql auth)
  SQL_ENCRYPT      - Encrypt connection: true/false
  SQL_TRUST_CERT   - Trust server certificate: true/false
  SQL_DRIVER       - ODBC driver name
  AZURE_TENANT_ID  - Entra tenant ID (entra_sp)
  AZURE_CLIENT_ID  - Entra client ID (entra_sp)
  AZURE_CLIENT_SECRET - Entra client secret (entra_sp)
"""

import os


_CONFIG_KEYS = (
    'SQL_SERVER', 'SQL_DATABASE', 'SQL_AUTH_TYPE', 'SQL_USER', 'SQL_PASSWORD',
    'SQL_ENCRYPT', 'SQL_TRUST_CERT', 'SQL_DRIVER',
    'AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET',
)


def _load_from_settings_json(missing_keys):
    """Read plugin config from .claude/settings.local.json as last resort.

    The configure.py script writes connection settings here. This fallback
    ensures scripts work even when CLAUDE_PLUGIN_OPTION_* env vars are not
    passed (e.g., flaky env propagation on Windows bash).
    """
    from pathlib import Path
    import json
    try:
        cwd = Path.cwd()
        for search_dir in [cwd] + list(cwd.parents)[:5]:
            settings_path = search_dir / '.claude' / 'settings.local.json'
            if settings_path.exists():
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


def _load_plugin_userconfig_env():
    """Populate SQL_* env vars from all available config sources.

    Precedence (first wins):
      1. Bare env vars already set (SQL_SERVER, SQL_DATABASE, etc.)
      2. CLAUDE_PLUGIN_OPTION_* env vars (plugin userConfig)
      3. .claude/settings.local.json pluginConfigs (written by configure.py)

    Must run at module load time, before any script reads env vars.
    """
    # Source 2: CLAUDE_PLUGIN_OPTION_* env vars
    for key in _CONFIG_KEYS:
        if not os.environ.get(key):
            fallback = os.environ.get(f'CLAUDE_PLUGIN_OPTION_{key}')
            if fallback:
                os.environ[key] = fallback

    # Source 3: settings.local.json fallback
    missing = [k for k in _CONFIG_KEYS if not os.environ.get(k)]
    if missing:
        _load_from_settings_json(missing)


_load_plugin_userconfig_env()


# Default ODBC driver — auto-detect if not set
DEFAULT_DRIVER = "ODBC Driver 17 for SQL Server"


def get_auth_type(username: str = '', password: str = '') -> str:
    """Determine auth type from env var or credentials."""
    explicit = os.environ.get('SQL_AUTH_TYPE', '')
    if explicit:
        return explicit
    # Infer: if credentials provided, use sql; otherwise windows
    return 'sql' if (username and password) else 'windows'


def get_encrypt_settings() -> tuple[bool, bool]:
    """Return (encrypt, trust_cert) based on env vars."""
    encrypt = os.environ.get('SQL_ENCRYPT', 'false').lower() == 'true'
    trust_cert = os.environ.get('SQL_TRUST_CERT', 'true').lower() != 'false'
    return encrypt, trust_cert


def build_pyodbc_connection(server: str, database: str, username: str = '',
                            password: str = '', driver: str = '',
                            timeout: int = 30):
    """Build a pyodbc connection for the configured auth type.

    Returns a pyodbc.Connection object.
    """
    import pyodbc

    driver = driver or os.environ.get('SQL_DRIVER', DEFAULT_DRIVER)
    auth_type = get_auth_type(username, password)
    encrypt, trust_cert = get_encrypt_settings()

    encrypt_str = 'yes' if encrypt else 'no'
    trust_str = 'yes' if trust_cert else 'no'

    if auth_type == 'windows':
        conn_str = (
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
            f"Trusted_Connection=yes;"
            f"Encrypt={encrypt_str};TrustServerCertificate={trust_str};"
            f"Connection Timeout={timeout};"
        )
        return pyodbc.connect(conn_str)

    elif auth_type == 'sql':
        conn_str = (
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
            f"UID={username};PWD={password};"
            f"Encrypt={encrypt_str};TrustServerCertificate={trust_str};"
            f"Connection Timeout={timeout};"
        )
        return pyodbc.connect(conn_str)

    elif auth_type == 'entra_interactive':
        conn_str = (
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
            f"Authentication=ActiveDirectoryInteractive;"
            f"Encrypt=yes;TrustServerCertificate={trust_str};"
            f"Connection Timeout={timeout};"
        )
        return pyodbc.connect(conn_str)

    elif auth_type == 'entra_sp':
        from azure.identity import ClientSecretCredential
        import struct

        credential = ClientSecretCredential(
            tenant_id=os.environ['AZURE_TENANT_ID'],
            client_id=os.environ['AZURE_CLIENT_ID'],
            client_secret=os.environ['AZURE_CLIENT_SECRET']
        )
        token = credential.get_token("https://database.windows.net/.default").token
        token_bytes = token.encode("UTF-16-LE")
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)

        conn_str = (
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
            f"Encrypt=yes;TrustServerCertificate={trust_str};"
            f"Connection Timeout={timeout};"
        )
        # SQL_COPT_SS_ACCESS_TOKEN = 1256
        return pyodbc.connect(conn_str, attrs_before={1256: token_struct})

    else:
        raise ValueError(f"Unknown SQL_AUTH_TYPE: {auth_type}. "
                         f"Valid: windows, sql, entra_interactive, entra_sp")


def build_sqlalchemy_url(server: str, database: str, username: str = '',
                         password: str = '', driver: str = '',
                         extra_query: dict = None):
    """Build a SQLAlchemy connection URL for the configured auth type.

    Returns a sqlalchemy.engine.URL object.
    For entra_sp, returns a tuple (URL, connect_args) where connect_args
    contains the token for pyodbc.
    """
    from sqlalchemy.engine import URL

    driver = driver or os.environ.get('SQL_DRIVER', DEFAULT_DRIVER)
    auth_type = get_auth_type(username, password)
    encrypt, trust_cert = get_encrypt_settings()

    query = {"driver": driver}
    if trust_cert:
        query["TrustServerCertificate"] = "yes"
    if encrypt:
        query["Encrypt"] = "yes"
    if extra_query:
        query.update(extra_query)

    connect_args = {}

    if auth_type == 'windows':
        query["Trusted_Connection"] = "yes"
        url = URL.create("mssql+pyodbc", host=server, database=database, query=query)

    elif auth_type == 'sql':
        url = URL.create("mssql+pyodbc", username=username, password=password,
                         host=server, database=database, query=query)

    elif auth_type == 'entra_interactive':
        query["Authentication"] = "ActiveDirectoryInteractive"
        query["Encrypt"] = "yes"
        url = URL.create("mssql+pyodbc", host=server, database=database, query=query)

    elif auth_type == 'entra_sp':
        from azure.identity import ClientSecretCredential
        import struct

        credential = ClientSecretCredential(
            tenant_id=os.environ['AZURE_TENANT_ID'],
            client_id=os.environ['AZURE_CLIENT_ID'],
            client_secret=os.environ['AZURE_CLIENT_SECRET']
        )
        token = credential.get_token("https://database.windows.net/.default").token
        token_bytes = token.encode("UTF-16-LE")
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)

        query["Encrypt"] = "yes"
        url = URL.create("mssql+pyodbc", host=server, database=database, query=query)
        connect_args = {"attrs_before": {1256: token_struct}}

    else:
        raise ValueError(f"Unknown SQL_AUTH_TYPE: {auth_type}")

    return url, connect_args
