# DBT Pipeline Plugin

A Claude Code plugin for end-to-end dbt pipeline automation on SQL Server. This repo is a **standalone plugin store** — it contains no marketplace. The marketplace lives in [AI-plugins](https://github.com/KavasiMihaly/AI-plugins), which references this repo as an installable plugin.

## Architecture

```
.claude-plugin/
  plugin.json          # Plugin manifest (name, version, agents, skills, MCP server, hooks, userConfig)

agents/                # 9 specialized agents
  dbt-pipeline-orchestrator/   # Top-level orchestrator — drives the full CSV-to-star-schema workflow
  business-analyst/            # Requirements gathering and documentation
  data-explorer/               # Source data profiling and discovery
  dbt-architecture-setup/      # Project scaffolding (folders, dbt config, venv)
  dbt-staging-builder/         # stg_* models from raw sources
  dbt-dimension-builder/       # dim_* tables with SCD patterns
  dbt-fact-builder/            # fct_* tables with incremental strategies
  dbt-test-writer/             # Generic, custom, unit tests, and data contracts
  dbt-pipeline-validator/      # End-to-end build + test validation

skills/                # 8 user-invocable skills
  dbt-runner/                  # Execute dbt commands (run, test, build, etc.)
  dbt-test-coverage-analyzer/  # Analyze test coverage gaps
  dbt-docs-generator/          # Generate and serve dbt docs
  dbt-project-initializer/     # Scaffold new dbt projects
  data-profiler/               # Profile SQL Server tables and CSVs
  sql-executor/                # Load CSVs and execute SQL mutations
  sql-server-reader/           # Read-only queries against SQL Server
  sql-connection/              # Connection management script

hooks/                 # 3 lifecycle hooks
  validate-dbt-structure.py    # PreToolUse: validates dbt file naming/placement on Write|Edit
  create-worktree.py           # WorktreeCreate: sets up isolated worktree
  remove-worktree.py           # WorktreeRemove: cleans up worktree

servers/               # MCP server
  src/                         # TypeScript source (database.ts, minimal-mcp-server.ts)
  dist/                        # Compiled JS

reference/             # Style guides and model examples
  sql-style-guide.md
  testing-patterns.md
  examples/                    # Staging, dimension, fact, and test examples
```

## Relationship to AI-plugins Marketplace

- **This repo** = the plugin itself (agents, skills, hooks, MCP server)
- **AI-plugins repo** = the marketplace index that lists this and future plugins
- Users install via the marketplace: `/plugin marketplace add KavasiMihaly/AI-plugins` then `/plugin install dbt-pipeline-toolkit@OneDayBI-Marketplace`
- This repo must NOT contain a `marketplace.json` — only `plugin.json`

## Key Patterns

- **Plugin manifest** is `.claude-plugin/plugin.json` — defines agents, skills, MCP server config, hooks, and user-configurable settings (SQL Server connection details)
- **Agents** each have an `agent.md` file defining their role, tools, and orchestration rules
- **Skills** each have a `SKILL.md` + `scripts/` folder with Python implementations
- **MCP server** provides SQL Server connectivity with 4 auth types (SQL, Windows, Entra Interactive, Entra Service Principal)
- **userConfig** in plugin.json allows users to configure connection details at install time; sensitive values (passwords, secrets) are stored in the system keychain

## Development Notes

- Do not add a `marketplace.json` to this repo
- Agent definitions live in `agents/<name>/agent.md`
- Skill definitions live in `skills/<name>/SKILL.md` with scripts in `skills/<name>/scripts/`
- The MCP server TypeScript source is in `servers/src/`, compiled output in `servers/dist/`
