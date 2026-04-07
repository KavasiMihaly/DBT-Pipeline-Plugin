import sql from 'mssql';

export interface ConnectionConfig {
    server: string;
    database?: string;
    authType?: 'sql' | 'windows' | 'entra_default' | 'entra_sp';
    username?: string;
    password?: string;
    encrypt?: boolean;
    trustServerCertificate?: boolean;
    clientId?: string;
    clientSecret?: string;
    tenantId?: string;
    port?: number;
}

/**
 * Database connection manager for SQL Server with connection pooling
 * and error handling optimized for MCP server use.
 * Supports runtime connection via tool arguments or env var fallback.
 */
export class DatabaseManager {
    private static instance: DatabaseManager;
    private pool: sql.ConnectionPool | null = null;
    private config: sql.config | null = null;
    private isConnecting = false;
    private currentDatabase: string = 'master';
    private currentServer: string = '';

    constructor() {
        this.buildConfigFromEnv();
    }

    /**
     * Build connection config from environment variables (fallback/default)
     */
    private buildConfigFromEnv(): void {
        const hasEnvConfig = process.env.SQL_SERVER;
        if (!hasEnvConfig) {
            this.config = null;
            return;
        }

        this.applyConnectionConfig({
            server: process.env.SQL_SERVER!,
            database: process.env.SQL_DATABASE || 'master',
            authType: (process.env.SQL_AUTH_TYPE as ConnectionConfig['authType']) || 'sql',
            username: process.env.SQL_USER,
            password: process.env.SQL_PASSWORD,
            encrypt: process.env.SQL_ENCRYPT === 'true',
            trustServerCertificate: process.env.SQL_TRUST_CERT !== 'false',
            clientId: process.env.AZURE_CLIENT_ID,
            clientSecret: process.env.AZURE_CLIENT_SECRET,
            tenantId: process.env.AZURE_TENANT_ID,
            port: process.env.SQL_PORT ? parseInt(process.env.SQL_PORT) : undefined
        });
    }

    /**
     * Apply a ConnectionConfig to build the mssql config object
     */
    private applyConnectionConfig(connConfig: ConnectionConfig): void {
        const authType = connConfig.authType || 'sql';
        this.currentDatabase = connConfig.database || 'master';
        this.currentServer = connConfig.server;

        this.config = {
            server: connConfig.server,
            database: this.currentDatabase,
            port: connConfig.port,
            options: {
                encrypt: connConfig.encrypt ?? false,
                trustServerCertificate: connConfig.trustServerCertificate ?? true,
                enableArithAbort: true,
                requestTimeout: 30000,
                connectTimeout: 30000
            },
            pool: {
                max: 10,
                min: 0,
                idleTimeoutMillis: 30000,
                acquireTimeoutMillis: 60000,
                createTimeoutMillis: 30000,
                destroyTimeoutMillis: 5000,
                reapIntervalMillis: 1000,
                createRetryIntervalMillis: 200
            }
        };

        switch (authType) {
            case 'windows':
                this.config.options!.trustedConnection = true;
                break;
            case 'entra_default':
                this.config.authentication = {
                    type: 'azure-active-directory-default',
                    options: {}
                } as any;
                break;
            case 'entra_sp':
                this.config.authentication = {
                    type: 'azure-active-directory-service-principal-secret' as any,
                    options: {
                        clientId: connConfig.clientId || '',
                        clientSecret: connConfig.clientSecret || '',
                        tenantId: connConfig.tenantId || ''
                    }
                };
                break;
            case 'sql':
            default:
                this.config.authentication = {
                    type: 'default',
                    options: {
                        userName: connConfig.username || '',
                        password: connConfig.password || ''
                    }
                };
                break;
        }

        console.log(`SQL Server config: ${connConfig.server}/${this.currentDatabase} (auth: ${authType})`);
    }

    /**
     * Connect to a SQL Server using runtime arguments.
     * Closes any existing connection and establishes a new one.
     */
    public async connectWithConfig(connConfig: ConnectionConfig): Promise<void> {
        await this.close();
        this.applyConnectionConfig(connConfig);
        await this.connect();
    }

    /**
     * Get singleton instance of DatabaseManager
     */
    public static getInstance(): DatabaseManager {
        if (!DatabaseManager.instance) {
            DatabaseManager.instance = new DatabaseManager();
        }
        return DatabaseManager.instance;
    }

    /**
     * Connect to SQL Server and return connection pool
     */
    public async connect(): Promise<sql.ConnectionPool> {
        if (!this.config) {
            throw new Error('Not connected. Use the "connect" tool first to provide server, database, and authentication details.');
        }

        if (this.pool && this.pool.connected) {
            return this.pool;
        }

        if (this.isConnecting) {
            while (this.isConnecting) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            if (this.pool && this.pool.connected) {
                return this.pool;
            }
        }

        this.isConnecting = true;

        try {
            if (this.pool) {
                await this.pool.close();
            }

            this.pool = new sql.ConnectionPool(this.config);

            this.pool.on('error', (err) => {
                console.error('SQL Pool Error:', err);
            });

            await this.pool.connect();

            console.log('Connected to SQL Server successfully');
            return this.pool;
        } catch (error) {
            console.error('Failed to connect to SQL Server:', error);
            throw this.handleDatabaseError(error, 'Connection failed');
        } finally {
            this.isConnecting = false;
        }
    }

    /**
     * Get current connection info (safe — no secrets)
     */
    public getConnectionInfo(): { server: string; database: string; connected: boolean } {
        return {
            server: this.currentServer,
            database: this.currentDatabase,
            connected: this.isConnected()
        };
    }

    /**
     * Execute a SQL query with parameters
     */
    public async executeQuery(
        query: string,
        parameters: Record<string, any> = {}
    ): Promise<sql.IResult<any>> {
        const pool = await this.connect();
        const request = pool.request();

        try {
            // Add parameters safely with type inference
            Object.entries(parameters).forEach(([key, value]) => {
                const sqlType = this.inferSQLType(value);
                request.input(key, sqlType, value);
            });

            const result = await request.query(query);
            return result;
        } catch (error) {
            throw this.handleDatabaseError(error, query);
        }
    }

    /**
     * Execute a stored procedure with parameters
     */
    public async executeStoredProcedure(
        procedureName: string,
        parameters: Record<string, any> = {}
    ): Promise<sql.IResult<any>> {
        const pool = await this.connect();
        const request = pool.request();

        try {
            Object.entries(parameters).forEach(([key, value]) => {
                const sqlType = this.inferSQLType(value);
                request.input(key, sqlType, value);
            });

            const result = await request.execute(procedureName);
            return result;
        } catch (error) {
            throw this.handleDatabaseError(error, `EXEC ${procedureName}`);
        }
    }

    /**
     * Get table schema information
     */
    public async getTableSchema(tableName: string): Promise<any[]> {
        const query = `
      SELECT 
        COLUMN_NAME,
        DATA_TYPE,
        IS_NULLABLE,
        CHARACTER_MAXIMUM_LENGTH,
        NUMERIC_PRECISION,
        NUMERIC_SCALE,
        COLUMN_DEFAULT
      FROM INFORMATION_SCHEMA.COLUMNS 
      WHERE TABLE_NAME = @tableName
      ORDER BY ORDINAL_POSITION
    `;

        const result = await this.executeQuery(query, { tableName });
        return result.recordset;
    }

    /**
     * Get all tables in the database
     */
    public async getTables(): Promise<any[]> {
        const query = `
      SELECT
        TABLE_NAME,
        TABLE_TYPE
      FROM INFORMATION_SCHEMA.TABLES
      WHERE TABLE_TYPE = 'BASE TABLE'
      ORDER BY TABLE_NAME
    `;

        const result = await this.executeQuery(query);
        return result.recordset;
    }

    /**
     * Get all user databases (excludes system databases)
     * Falls back to DB_NAME() on Azure SQL Database where sys.databases access is restricted
     */
    public async getDatabases(): Promise<any[]> {
        try {
            const query = `
      SELECT
        name as DATABASE_NAME,
        database_id,
        create_date,
        state_desc as STATE
      FROM sys.databases
      WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')
        AND state = 0  -- Only online databases
      ORDER BY name
    `;

            const result = await this.executeQuery(query);
            return result.recordset;
        } catch {
            // Azure SQL Database (single DB) restricts sys.databases access
            const result = await this.executeQuery(`SELECT DB_NAME() as DATABASE_NAME`);
            return result.recordset;
        }
    }

    /**
     * Get the currently selected database name
     */
    public getCurrentDatabase(): string {
        return this.currentDatabase;
    }

    /**
     * Switch to a different database
     */
    public async useDatabase(databaseName: string): Promise<void> {
        // Close existing connection
        if (this.pool) {
            await this.pool.close();
            this.pool = null;
        }

        // Update config with new database
        if (!this.config) {
            throw new Error('Not connected. Use the "connect" tool first.');
        }
        this.currentDatabase = databaseName;
        this.config.database = databaseName;

        // Reconnect with the new database
        await this.connect();
        console.log(`Switched to database: ${databaseName}`);
    }

    /**
     * Get all views in the database
     */
    public async getViews(): Promise<any[]> {
        const query = `
      SELECT 
        TABLE_NAME as VIEW_NAME,
        TABLE_SCHEMA as SCHEMA_NAME
      FROM INFORMATION_SCHEMA.VIEWS 
      ORDER BY TABLE_NAME
    `;

        const result = await this.executeQuery(query);
        return result.recordset;
    }

    /**
     * Get view definition (CREATE VIEW statement)
     */
    public async getViewDefinition(viewName: string): Promise<any[]> {
        const query = `
      SELECT 
        v.TABLE_NAME as VIEW_NAME,
        v.TABLE_SCHEMA as SCHEMA_NAME,
        v.VIEW_DEFINITION,
        v.CHECK_OPTION,
        v.IS_UPDATABLE
      FROM INFORMATION_SCHEMA.VIEWS v
      WHERE v.TABLE_NAME = @viewName
    `;

        const result = await this.executeQuery(query, { viewName });
        return result.recordset;
    }

    /**
     * Create a new view in the database
     */
    public async createView(viewDefinition: string): Promise<sql.IResult<any>> {
        // Validate that this is a safe CREATE VIEW statement
        if (!this.validateQuery(viewDefinition)) {
            throw new Error('Invalid or unsafe CREATE VIEW statement.');
        }

        // Additional validation specific to CREATE VIEW
        const normalized = viewDefinition.trim().replace(/\s+/g, ' ');
        if (!/^CREATE\s+VIEW\s+/i.test(normalized)) {
            throw new Error('Statement must be a CREATE VIEW command.');
        }

        const pool = await this.connect();
        const request = pool.request();

        try {
            const result = await request.query(viewDefinition);
            return result;
        } catch (error) {
            throw this.handleDatabaseError(error, viewDefinition);
        }
    }

    /**
     * Infer SQL Server data type from JavaScript value
     */
    private inferSQLType(value: any): sql.ISqlType {
        if (value === null || value === undefined) {
            return sql.NVarChar(255);
        }

        switch (typeof value) {
            case 'string':
                return value.length > 4000 ? sql.NText() : sql.NVarChar(Math.max(value.length, 255));
            case 'number':
                return Number.isInteger(value) ? sql.Int() : sql.Float();
            case 'boolean':
                return sql.Bit();
            case 'object':
                if (value instanceof Date) {
                    return sql.DateTime2();
                }
                return sql.NVarChar(sql.MAX);
            default:
                return sql.NVarChar(255);
        }
    }

    /**
     * Handle database errors with appropriate error messages
     */
    private handleDatabaseError(error: any, query: string): Error {
        let message = 'Database operation failed';

        if (error.number) {
            switch (error.number) {
                case 2:
                    message = 'SQL Server not accessible - check connection settings';
                    break;
                case 18456:
                    message = 'Authentication failed - check credentials';
                    break;
                case 208:
                    message = 'Invalid object name - table or view does not exist';
                    break;
                case 207:
                    message = 'Invalid column name';
                    break;
                case 515:
                    message = 'Cannot insert NULL value into required field';
                    break;
                default:
                    message = `SQL Server error ${error.number}: ${error.message}`;
            }
        } else if (error.message) {
            message = error.message;
        }

        console.error(`Database error executing: ${query}`, error);
        return new Error(message);
    }

    /**
     * Validate SQL query for basic security
     */
    public validateQuery(query: string): boolean {
        const dangerousPatterns = [
            /DROP\s+(TABLE|VIEW|DATABASE)/i,
            /DELETE\s+FROM.*WHERE.*1\s*=\s*1/i,
            /DELETE\s+FROM/i,
            /INSERT\s+INTO/i,
            /UPDATE\s+.*SET/i,
            /EXEC\s+xp_/i,
            /EXECUTE\s+/i,
            /sp_executesql/i,
            /TRUNCATE\s+TABLE/i,
            /ALTER\s+(TABLE|VIEW)/i,
            /CREATE\s+TABLE/i,
            /;\s*(DROP|DELETE|INSERT|UPDATE|TRUNCATE|ALTER)/i,
            /--/,
            /\/\*/,
            /OPENROWSET/i,
            /OPENDATASOURCE/i,
            /BULK\s+INSERT/i,
            /sp_/i,
            /xp_/i
        ];

        // Check for multiple statements (semicolon followed by another statement)
        const normalized = query.trim().replace(/\s+/g, ' ');
        const statementCount = normalized.split(';').filter(s => s.trim().length > 0).length;
        if (statementCount > 1) {
            return false;
        }

        return !dangerousPatterns.some(pattern => pattern.test(query));
    }

    /**
     * Close database connection
     */
    public async close(): Promise<void> {
        if (this.pool) {
            await this.pool.close();
            this.pool = null;
            console.log('Database connection closed');
        }
    }

    /**
     * Check if database is connected
     */
    public isConnected(): boolean {
        return this.pool !== null && this.pool.connected;
    }
}