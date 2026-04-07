"use strict";
/**
 * SQL Server MCP Server
 * Author: Mihaly Kavasi
 *
 * An MCP (Model Context Protocol) server that provides AI assistants with
 * tools to interact with SQL Server databases — both local instances and
 * cloud-hosted (Azure SQL Database, Azure SQL Managed Instance, AWS RDS).
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.MinimalMCPServer = void 0;
const index_js_1 = require("@modelcontextprotocol/sdk/server/index.js");
const stdio_js_1 = require("@modelcontextprotocol/sdk/server/stdio.js");
const types_js_1 = require("@modelcontextprotocol/sdk/types.js");
const database_1 = require("./database");
const dotenv = __importStar(require("dotenv"));
dotenv.config();
class MinimalMCPServer {
    server;
    dbManager;
    constructor() {
        this.server = new index_js_1.Server({ name: 'sql-server-mcp', version: '1.0.0' }, {
            capabilities: {
                tools: {}, // Remove individual tool definitions from here
            },
        });
        this.dbManager = database_1.DatabaseManager.getInstance();
        this.setupHandlers();
    }
    setupHandlers() {
        // Add MCP standard tool discovery handler
        this.server.setRequestHandler(types_js_1.ListToolsRequestSchema, async () => {
            return {
                tools: [
                    {
                        name: 'connect',
                        description: 'Connect to a SQL Server instance. Must be called before using any other tool. Supports local SQL Server, Azure SQL Database, Azure SQL Managed Instance, and AWS RDS.',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                server: {
                                    type: 'string',
                                    description: 'SQL Server hostname or IP (e.g., "localhost", "myserver.database.windows.net")'
                                },
                                database: {
                                    type: 'string',
                                    description: 'Database name to connect to (default: "master")'
                                },
                                authType: {
                                    type: 'string',
                                    enum: ['sql', 'windows', 'entra_default', 'entra_sp'],
                                    description: 'Authentication type: "sql" for username/password, "windows" for Windows/integrated auth, "entra_default" for Microsoft Entra via Azure CLI token (user must run "az login" first), "entra_sp" for Entra service principal with client secret'
                                },
                                username: {
                                    type: 'string',
                                    description: 'SQL login username (required for authType "sql")'
                                },
                                password: {
                                    type: 'string',
                                    description: 'SQL login password (required for authType "sql")'
                                },
                                encrypt: {
                                    type: 'boolean',
                                    description: 'Encrypt the connection (required true for Azure, default: false)'
                                },
                                trustServerCertificate: {
                                    type: 'boolean',
                                    description: 'Trust the server certificate without validation (default: true for local, false for cloud)'
                                },
                                port: {
                                    type: 'number',
                                    description: 'SQL Server port (default: 1433)'
                                },
                                clientId: {
                                    type: 'string',
                                    description: 'Azure app registration client ID (for authType "entra_sp")'
                                },
                                clientSecret: {
                                    type: 'string',
                                    description: 'Azure app registration client secret (for authType "entra_sp")'
                                },
                                tenantId: {
                                    type: 'string',
                                    description: 'Azure tenant ID (for authType "entra_sp")'
                                }
                            },
                            required: ['server'],
                            additionalProperties: false
                        }
                    },
                    {
                        name: 'disconnect',
                        description: 'Disconnect from the current SQL Server instance',
                        inputSchema: {
                            type: 'object',
                            properties: {},
                            additionalProperties: false
                        }
                    },
                    {
                        name: 'get_databases',
                        description: 'List all available user databases on the SQL Server (excludes system databases)',
                        inputSchema: {
                            type: 'object',
                            properties: {},
                            additionalProperties: false
                        }
                    },
                    {
                        name: 'get_current_database',
                        description: 'Get the name of the currently selected database',
                        inputSchema: {
                            type: 'object',
                            properties: {},
                            additionalProperties: false
                        }
                    },
                    {
                        name: 'use_database',
                        description: 'Switch to a different database. Use get_databases first to see available databases.',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                databaseName: {
                                    type: 'string',
                                    description: 'Name of the database to switch to'
                                }
                            },
                            required: ['databaseName'],
                            additionalProperties: false
                        }
                    },
                    {
                        name: 'get_tables',
                        description: 'List all tables in the current database',
                        inputSchema: {
                            type: 'object',
                            properties: {},
                            additionalProperties: false
                        }
                    },
                    {
                        name: 'get_table_schema',
                        description: 'Get schema information for a specific table',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                tableName: {
                                    type: 'string',
                                    description: 'Name of the table to get schema for'
                                }
                            },
                            required: ['tableName'],
                            additionalProperties: false
                        }
                    },
                    {
                        name: 'get_views',
                        description: 'List all views in the database',
                        inputSchema: {
                            type: 'object',
                            properties: {},
                            additionalProperties: false
                        }
                    },
                    {
                        name: 'get_view_definition',
                        description: 'Get the definition of a specific view',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                viewName: {
                                    type: 'string',
                                    description: 'Name of the view to get definition for'
                                }
                            },
                            required: ['viewName'],
                            additionalProperties: false
                        }
                    },
                    {
                        name: 'create_view',
                        description: 'Create a new view in the database',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                viewDefinition: {
                                    type: 'string',
                                    description: 'Complete CREATE VIEW statement (e.g., "CREATE VIEW MyView AS SELECT * FROM MyTable")'
                                }
                            },
                            required: ['viewDefinition'],
                            additionalProperties: false
                        }
                    },
                    {
                        name: 'execute_query',
                        description: 'Execute a SELECT query on SQL Server database',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                query: {
                                    type: 'string',
                                    description: 'SQL SELECT query to execute'
                                },
                                parameters: {
                                    type: 'object',
                                    description: 'Query parameters (optional)',
                                    additionalProperties: true
                                }
                            },
                            required: ['query'],
                            additionalProperties: false
                        }
                    }
                ]
            };
        });
        // Add MCP standard tool execution handler
        this.server.setRequestHandler(types_js_1.CallToolRequestSchema, async (request) => {
            const { name, arguments: args } = request.params;
            switch (name) {
                case 'connect':
                    if (!args || typeof args.server !== 'string') {
                        throw new Error('server parameter is required');
                    }
                    const connConfig = {
                        server: args.server,
                        database: args.database || 'master',
                        authType: args.authType || 'sql',
                        username: args.username,
                        password: args.password,
                        encrypt: args.encrypt,
                        trustServerCertificate: args.trustServerCertificate,
                        port: args.port,
                        clientId: args.clientId,
                        clientSecret: args.clientSecret,
                        tenantId: args.tenantId
                    };
                    await this.dbManager.connectWithConfig(connConfig);
                    const connInfo = this.dbManager.getConnectionInfo();
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify({
                                    success: true,
                                    message: `Connected to ${connInfo.server}/${connInfo.database}`,
                                    ...connInfo
                                }, null, 2)
                            }
                        ]
                    };
                case 'disconnect':
                    await this.dbManager.close();
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify({
                                    success: true,
                                    message: 'Disconnected from SQL Server'
                                }, null, 2)
                            }
                        ]
                    };
                case 'get_databases':
                    const databases = await this.dbManager.getDatabases();
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify({
                                    currentDatabase: this.dbManager.getCurrentDatabase(),
                                    databases
                                }, null, 2)
                            }
                        ]
                    };
                case 'get_current_database':
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify(this.dbManager.getConnectionInfo(), null, 2)
                            }
                        ]
                    };
                case 'use_database':
                    if (!args || typeof args.databaseName !== 'string') {
                        throw new Error('databaseName parameter is required and must be a string');
                    }
                    await this.dbManager.useDatabase(args.databaseName);
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify({
                                    success: true,
                                    message: `Switched to database: ${args.databaseName}`,
                                    currentDatabase: args.databaseName
                                }, null, 2)
                            }
                        ]
                    };
                case 'get_tables':
                    const tables = await this.dbManager.getTables();
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify({
                                    currentDatabase: this.dbManager.getCurrentDatabase(),
                                    tables
                                }, null, 2)
                            }
                        ]
                    };
                case 'get_table_schema':
                    if (!args || typeof args.tableName !== 'string') {
                        throw new Error('tableName parameter is required and must be a string');
                    }
                    const schema = await this.dbManager.getTableSchema(args.tableName);
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify({ schema }, null, 2)
                            }
                        ]
                    };
                case 'get_views':
                    const views = await this.dbManager.getViews();
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify({ views }, null, 2)
                            }
                        ]
                    };
                case 'get_view_definition':
                    if (!args || typeof args.viewName !== 'string') {
                        throw new Error('viewName parameter is required and must be a string');
                    }
                    const viewDefinition = await this.dbManager.getViewDefinition(args.viewName);
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify({ viewDefinition }, null, 2)
                            }
                        ]
                    };
                case 'create_view':
                    if (!args || typeof args.viewDefinition !== 'string') {
                        throw new Error('viewDefinition parameter is required and must be a string');
                    }
                    const createResult = await this.dbManager.createView(args.viewDefinition);
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify({
                                    success: true,
                                    message: 'View created successfully',
                                    rowsAffected: createResult.rowsAffected
                                }, null, 2)
                            }
                        ]
                    };
                case 'execute_query':
                    if (!args || typeof args.query !== 'string') {
                        throw new Error('Query parameter is required and must be a string');
                    }
                    const query = args.query;
                    const parameters = args.parameters || {};
                    const result = await this.dbManager.executeQuery(query, parameters);
                    return {
                        content: [
                            {
                                type: 'text',
                                text: JSON.stringify({ rows: result.recordset }, null, 2)
                            }
                        ]
                    };
                default:
                    throw new Error(`Unknown tool: ${name}`);
            }
        });
    }
    async start() {
        const transport = new stdio_js_1.StdioServerTransport();
        await this.server.connect(transport);
    }
}
exports.MinimalMCPServer = MinimalMCPServer;
// Start the server if this file is run directly
if (require.main === module) {
    new MinimalMCPServer().start();
}
//# sourceMappingURL=minimal-mcp-server.js.map