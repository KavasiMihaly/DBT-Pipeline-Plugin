# dbt Pipeline Toolkit

> End-to-end dbt pipeline automation for SQL Server — CSV to star schema with agents, skills, a bundled MCP server, and validation hooks.

A Claude Code plugin that automates the full dbt workflow on SQL Server: profile incoming data, scaffold a dbt project, generate staging models, build dimensions and facts, write tests, and validate everything on the way in. Works against local SQL Server, Azure SQL Database, or remote instances, with four supported auth types.

---

## Features

- **9 Agents** — from business analysis and data exploration through staging, dimension, fact, and test generation, to a pipeline orchestrator and validator
- **9 Skills** — connection management, SQL execution, schema reading, data profiling, dbt project init, dbt runs, doc generation, test-coverage analysis, and Power BI Project (PBIP) generation
- **Bundled MCP server** — `sql-server-mcp` (Node.js) for SQL Server introspection and query execution, shipped prebuilt in `servers/dist/`
- **4 Hooks** — structural validation on every Write/Edit, a Bash allowlist that auto-approves plugin-internal scripts for background agents, plus worktree create/remove automation
- **Reference docs** — SQL style guide and testing patterns bundled for the agents to consult

---

## Requirements

Before installing, make sure you have:

- **Claude Code** — CLI, desktop app, or IDE extension
- **Node.js** `>= 18` — required for the bundled `sql-server-mcp` server
- **Python** `>= 3.10` — required for the hook scripts (`validate-dbt-structure.py`, `create-worktree.py`, `remove-worktree.py`)
- **SQL Server access** — local SQL Server, Azure SQL Database, or a reachable remote instance
- **dbt-core + dbt-sqlserver** — install via `pip install dbt-core dbt-sqlserver` if you plan to run the generated project locally

---

## Installation

### 1. Add the marketplace

This plugin is distributed through the **`OneDayBI-Marketplace`**, hosted in the [AI-plugins](https://github.com/KavasiMihaly/AI-plugins) repo (this repo contains only the plugin itself):

```
/plugin marketplace add KavasiMihaly/AI-plugins
```

Or with a full URL:

```
/plugin marketplace add https://github.com/KavasiMihaly/AI-plugins
```

### 2. Install the plugin

```
/plugin install dbt-pipeline-toolkit@OneDayBI-Marketplace
```

Or open the interactive picker:

```
/plugin
```

During install you'll be prompted for the `userConfig` values listed below.

### 3. Reload

```
/reload-plugins
```

If the MCP tools don't appear, fully restart Claude Code.

### 4. Verify

```
/mcp       # should list sql-server-mcp
/agents    # should list the 9 dbt-* / data-explorer / business-analyst agents
```

---

## Configuration

Prompted on install, editable later via `/plugin`. Sensitive values are stored in your OS keychain, never in plain text.

| Key                   | Required | Sensitive | Description                                                                                         |
|-----------------------|----------|-----------|-----------------------------------------------------------------------------------------------------|
| `sql_server`          | no*      | no        | SQL Server hostname (`localhost`, `myserver.database.windows.net`). Leave empty to set at runtime. |
| `sql_database`        | no*      | no        | Default database name. Leave empty to set at runtime.                                              |
| `sql_auth_type`       | no       | no        | `sql` / `windows` / `entra_interactive` / `entra_sp`. Default: `sql`                                |
| `sql_user`            | cond.    | no        | Username (for `sql` auth). Leave empty for Windows or Entra Interactive.                           |
| `sql_password`        | cond.    | **yes**   | Password (for `sql` auth). Stored in system keychain.                                              |
| `sql_encrypt`         | no       | no        | `true` (required for Azure) / `false` (typical local). Default: `false`                             |
| `sql_trust_cert`      | no       | no        | `true` (local dev) / `false` (Azure/prod). Default: `true`                                         |
| `azure_tenant_id`     | cond.    | no        | Entra tenant ID (only for `entra_sp`)                                                              |
| `azure_client_id`     | cond.    | no        | Entra client/application ID (only for `entra_sp`)                                                  |
| `azure_client_secret` | cond.    | **yes**   | Entra client secret (only for `entra_sp`). Stored in system keychain.                              |

\* If left empty, use the MCP server's `connect` tool at runtime to supply values per session.

### Auth type cheatsheet

| `sql_auth_type`     | Needs                                              |
|---------------------|----------------------------------------------------|
| `sql`               | `sql_user`, `sql_password`                         |
| `windows`           | Nothing extra (integrated auth on Windows host)    |
| `entra_interactive` | Browser sign-in on first connect                   |
| `entra_sp`          | `azure_tenant_id`, `azure_client_id`, `azure_client_secret` |

---

## Usage

Describe what you want in natural language and Claude will route through the right agents and tools. Examples:

```
"Connect to my local SQL Server, the AdventureWorksDW database, and profile the FactInternetSales table."
"Initialize a new dbt project in ./warehouse targeting SQL Server."
"Build staging models for every table in the stg schema."
"Generate a date dimension and customer dimension from the raw customers table."
"Write dbt tests covering uniqueness, not-null, and referential integrity for the fact_sales model."
"Validate the current dbt project structure and run all tests."
```

### Agents

Invoke directly via the `Agent` tool, or let Claude pick them automatically.

- **`business-analyst`** — turns business questions into data requirements
- **`data-explorer`** — profiles tables, distributions, and relationships
- **`dbt-architecture-setup`** — scaffolds a new dbt project and configures SQL Server targets
- **`dbt-staging-builder`** — generates `stg_*` models from source tables
- **`dbt-dimension-builder`** — generates conformed dimensions
- **`dbt-fact-builder`** — generates fact tables with grain documentation
- **`dbt-test-writer`** — authors generic + singular tests
- **`dbt-pipeline-orchestrator`** — runs the full CSV-to-star-schema pipeline end to end
- **`dbt-pipeline-validator`** — checks project structure, lineage, and test coverage

### Skills

- **`sql-connection`** — manage active SQL Server connections
- **`sql-executor`** — run arbitrary SQL against the active connection
- **`sql-server-reader`** — introspect schemas, tables, columns, constraints
- **`data-profiler`** — row counts, null rates, cardinality, distributions
- **`dbt-project-initializer`** — scaffold a new dbt project
- **`dbt-runner`** — `dbt run` / `dbt test` / `dbt build`
- **`dbt-docs-generator`** — build and serve dbt docs
- **`dbt-test-coverage-analyzer`** — report which models lack tests
- **`pbip-from-dbt`** — generate an openable Power BI Project (PBIP) from the finished dbt star schema (sources-only, refresh in Power BI Desktop)

### MCP tools (`sql-server-mcp`)

The bundled Node MCP server exposes SQL Server connection and query tools used by the agents and skills. When connected, Claude can list databases/schemas/tables, describe columns, and execute parameterized queries directly.

### Hooks

- **PreToolUse (`Write` | `Edit`)** — runs `hooks/validate-dbt-structure.py` to enforce dbt folder/file conventions before edits are written
- **PreToolUse (`Bash`)** — runs `hooks/approve-plugin-bash.py` to auto-approve plugin-internal scripts (a narrow allowlist) so background agents don't stall on permission prompts
- **WorktreeCreate** — runs `hooks/create-worktree.py` to set up an isolated workspace
- **WorktreeRemove** — runs `hooks/remove-worktree.py` to tear it down cleanly

---

## Repository Layout

```
.claude-plugin/
  └── plugin.json          # plugin manifest (agents, skills, hooks, MCP, userConfig)
                           # NOTE: no marketplace.json here — the marketplace lives in the AI-plugins repo
agents/                    # 9 bundled agents
skills/                    # 9 bundled skills
hooks/                     # validate-dbt-structure.py, approve-plugin-bash.py, create-worktree.py, remove-worktree.py
servers/
  ├── src/                 # TypeScript source for sql-server-mcp
  ├── dist/                # prebuilt JS (minimal-mcp-server.js, database.js)
  ├── package.json
  └── tsconfig.json
reference/
  ├── sql-style-guide.md
  ├── testing-patterns.md
  └── examples/
```

---

## Development

Clone and work on the plugin locally:

```
git clone https://github.com/KavasiMihaly/DBT-Pipeline-Plugin.git
cd DBT-Pipeline-Plugin
cd servers && npm install && npm run build && cd ..
```

This repo has no `marketplace.json`, so to test the plugin locally either point Claude Code at a local checkout of the [AI-plugins](https://github.com/KavasiMihaly/AI-plugins) marketplace that references it, or load this checkout directly:

```
claude --plugin-dir /absolute/path/to/DBT-Pipeline-Plugin
```

> Note: local `--plugin-dir` dev hides several install-time behaviours (agent namespacing, frontmatter stripping, `${CLAUDE_PLUGIN_ROOT}` resolution). Always verify changes on a fresh marketplace install before release — see `CLAUDE.md` → "Plugin Gotchas".

After editing agents/skills/hooks, run `/reload-plugins`. After editing the MCP server, rebuild (`npm run build`) and fully restart Claude Code.

---

## Troubleshooting

| Symptom                                              | Fix                                                                         |
|------------------------------------------------------|-----------------------------------------------------------------------------|
| `Marketplace "OneDayBI-Marketplace" not found`        | Run `/plugin marketplace add KavasiMihaly/AI-plugins` before `/plugin install`. |
| Plugin installs but `sql-server-mcp` tools missing   | Fully restart Claude Code — MCP tools register on fresh sessions only.     |
| `sql-server-mcp` fails to start                      | Check Node `>= 18` is on PATH; verify `servers/dist/minimal-mcp-server.js` exists. |
| Connection fails to Azure SQL                        | Set `sql_encrypt=true` and `sql_trust_cert=false`.                          |
| Connection fails to local SQL Server                 | Set `sql_encrypt=false` and `sql_trust_cert=true`.                          |
| Hook blocks every Write/Edit                         | Read the validator error in the tool result and fix the dbt structure.     |
| `userConfig` prompt keeps reappearing                | A required value is empty or invalid — re-enter via `/plugin`.              |
| Entra SP auth fails                                  | Confirm tenant ID, client ID, and client secret; check the SP has access.  |

---

## Uninstall

```
/plugin                                                      # open manager, select Uninstall
/plugin marketplace remove OneDayBI-Marketplace             # remove the marketplace too
```

Or manually delete `~/.claude/plugins/cache/dbt-pipeline-toolkit/` and run `/reload-plugins`.

---

## Author

**Mihaly Kavasi** — [@KavasiMihaly](https://github.com/KavasiMihaly)
