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

## Lessons Learned (plugin-specific gotchas)

Running notes on issues discovered while building and installing this plugin on fresh machines. Every entry includes the change, the reason, and the date. Full context and conference-talk narrative: [`_Documentation/plugin_learnings.md`](_Documentation/plugin_learnings.md).

### 2026-04-14 — Namespace every agent reference to `dbt-pipeline-toolkit:<name>`

**Change:** In `agents/dbt-pipeline-orchestrator/agent.md`, the `tools: Agent(...)` allowlist and every `subagent_type:` in the workflow body were updated from bare names (e.g. `business-analyst`) to namespaced names (e.g. `dbt-pipeline-toolkit:business-analyst`).

**Reason:** Claude Code namespaces plugin-shipped agents as `<plugin-name>:<agent-name>` once installed. The marketplace name is **not** part of the namespace — only the plugin name. Bare-name references worked in local dev (where agents live in `.claude/agents/` or via `--plugin-dir`) but produced an empty `Agent(...)` allowlist once installed from the marketplace. The orchestrator would run, spawn nothing, and appear frozen.

**How to avoid regression:** Any new agent added to this plugin must be referenced from the orchestrator as `dbt-pipeline-toolkit:<name>` in both the tools allowlist and every `subagent_type:` call. Never use bare names for intra-plugin delegation.

### 2026-04-14 — Pass `mode: "acceptEdits"` on every background `Task(...)` spawn

**Change:** Every `Task(..., run_in_background: true)` call in the orchestrator's Stages 2, 7, 8, 9, 10, and 11 now also passes `mode: "acceptEdits"`.

**Reason:** Background agents have no interactive channel — they cannot satisfy a permission prompt. The builder agents previously relied on their own frontmatter `permissionMode: acceptEdits` to grant write access, but plugin-shipped agents have that field **silently stripped** at load time (it's one of Claude Code's security-restricted fields along with `hooks` and `mcpServers`). The combination is fatal: a background builder tries to write a file, the permission prompt goes nowhere, the task stalls, and the orchestrator eventually times out with no useful error.

**How to avoid regression:** Any new background `Task(...)` spawn in this plugin **must** pass `mode: "acceptEdits"` at the call site. Do not rely on the spawned agent's frontmatter. This applies to every `run_in_background: true` call.

### 2026-04-14 — Remove `permissionMode:` from all plugin-shipped agent frontmatter

**Change:** Stripped `permissionMode: default` / `permissionMode: acceptEdits` from the orchestrator and four builder agents (`dbt-staging-builder`, `dbt-dimension-builder`, `dbt-fact-builder`, `dbt-test-writer`).

**Reason:** The Claude Code plugins reference explicitly lists `permissionMode` as **not supported for plugin-shipped agents** — "for security reasons, `hooks`, `mcpServers`, and `permissionMode` are not supported." Leaving those lines in the frontmatter is misleading because they imply behavior that never takes effect once installed. They also hid the real problem (Finding 2 above) during development. Permission control now happens at the call site via the orchestrator's `mode: "acceptEdits"` parameter.

**How to avoid regression:** Never add `permissionMode`, `hooks`, or `mcpServers` fields to any agent frontmatter in this repo. Those concerns belong in `plugin.json` (for plugin-level hooks and MCP servers) or at the spawn call site (for per-invocation permission mode).

### General rule — test on a fresh install, not in dev

Every finding above was invisible during local development (`--plugin-dir` or direct `.claude/agents/` drop) and only surfaced after installing from the marketplace on a second machine. Before shipping any plugin change that touches agent definitions, orchestration, or permission flow:

1. Bump the plugin version in `plugin.json`
2. Install from the marketplace on a clean target
3. Run the happy-path scenario end-to-end
4. Verify background agents actually produced output, not just "completed" status
