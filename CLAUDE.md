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

### 2026-04-14 — Namespace every agent reference to `dbt-pipeline-toolkit:<dir>:<name>` (3-part)

**Change:** In `agents/dbt-pipeline-orchestrator/agent.md`, the `tools: Agent(...)` allowlist, every `subagent_type:` in the workflow body, and every `claude --agent ...` invocation example were updated from bare names (e.g. `business-analyst`) to 3-part namespaced names (e.g. `dbt-pipeline-toolkit:business-analyst:business-analyst`). Because every agent in this plugin has a frontmatter `name` that matches its subdirectory name, every 3-part name has a duplicated middle+last segment — that's expected, not a typo.

**Reason:** Claude Code namespaces plugin-shipped agents as `<plugin-name>:<subdir>:<frontmatter-name>` when the agent lives in a subdirectory like `agents/<dir>/agent.md`. **This contradicts the official Claude Code plugins reference**, which shows a 2-part format (`<plugin-name>:<agent-name>`) in its example — but the docs example uses flat files at `agents/<name>.md`, not subdirectories. We verified the actual 3-part behavior by installing the plugin on a fresh machine and observing the registered agent name in the `/agents` picker. An initial fix applied 2-part names based on the docs example and was still broken; testing on a fresh install caught it.

The marketplace name is **not** part of the namespace — only the plugin name (`dbt-pipeline-toolkit`), the subdirectory, and the frontmatter name.

**How to avoid regression:**
- Any new agent added to this plugin must be referenced as `dbt-pipeline-toolkit:<subdir>:<frontmatter-name>` in the orchestrator's `tools: Agent(...)` allowlist and every `subagent_type:` call.
- Keep the subdirectory name and the frontmatter `name` field identical — if they diverge, the registered name will silently become `<plugin>:<old-dir>:<new-name>` and every reference in the orchestrator will break without a clear error.
- The orchestrator itself is invoked as `claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator "..."` — not the shorter 2-part form, even though the docs example suggests otherwise.
- **Always verify the actual registered name on a fresh install** — check `/agents` or the plugin picker, don't trust the docs example.

### 2026-04-14 — Pass `mode: "acceptEdits"` on every background `Task(...)` spawn

**Change:** Every `Task(..., run_in_background: true)` call in the orchestrator's Stages 2, 7, 8, 9, 10, and 11 now also passes `mode: "acceptEdits"`.

**Reason:** Background agents have no interactive channel — they cannot satisfy a permission prompt. The builder agents previously relied on their own frontmatter `permissionMode: acceptEdits` to grant write access, but plugin-shipped agents have that field **silently stripped** at load time (it's one of Claude Code's security-restricted fields along with `hooks` and `mcpServers`). The combination is fatal: a background builder tries to write a file, the permission prompt goes nowhere, the task stalls, and the orchestrator eventually times out with no useful error.

**How to avoid regression:** Any new background `Task(...)` spawn in this plugin **must** pass `mode: "acceptEdits"` at the call site. Do not rely on the spawned agent's frontmatter. This applies to every `run_in_background: true` call.

### 2026-04-14 — Remove `permissionMode:` from all plugin-shipped agent frontmatter

**Change:** Stripped `permissionMode: default` / `permissionMode: acceptEdits` from the orchestrator and four builder agents (`dbt-staging-builder`, `dbt-dimension-builder`, `dbt-fact-builder`, `dbt-test-writer`).

**Reason:** The Claude Code plugins reference explicitly lists `permissionMode` as **not supported for plugin-shipped agents** — "for security reasons, `hooks`, `mcpServers`, and `permissionMode` are not supported." Leaving those lines in the frontmatter is misleading because they imply behavior that never takes effect once installed. They also hid the real problem (Finding 2 above) during development. Permission control now happens at the call site via the orchestrator's `mode: "acceptEdits"` parameter.

**How to avoid regression:** Never add `permissionMode`, `hooks`, or `mcpServers` fields to any agent frontmatter in this repo. Those concerns belong in `plugin.json` (for plugin-level hooks and MCP servers) or at the spawn call site (for per-invocation permission mode).

### 2026-04-14 — Remap `CLAUDE_PLUGIN_OPTION_*` env vars to bare names in every SQL-aware Python script

**Change:** Added a `_load_plugin_userconfig_env()` helper at module top of five scripts: `skills/sql-connection/scripts/connect.py`, `skills/sql-server-reader/scripts/query_sql_server.py`, `skills/data-profiler/scripts/profile_data.py`, `skills/sql-executor/scripts/load_data.py`, `skills/dbt-project-initializer/scripts/initialize_project.py`. The helper runs at module load, before `argparse` evaluates its defaults, and copies `CLAUDE_PLUGIN_OPTION_<KEY>` → `<KEY>` for every SQL connection variable (`SQL_SERVER`, `SQL_DATABASE`, `SQL_AUTH_TYPE`, `SQL_USER`, `SQL_PASSWORD`, `SQL_ENCRYPT`, `SQL_TRUST_CERT`, `SQL_DRIVER`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`).

**Reason:** Claude Code plugin subprocesses receive `userConfig` values as `CLAUDE_PLUGIN_OPTION_<KEY>` environment variables — **not** as the bare names the plugin's own code expects. The MCP server in `plugin.json` works because its `mcpServers.sql-server-mcp.env` block explicitly maps `${user_config.sql_server}` → `SQL_SERVER`. But the Python skill scripts run as separate subprocesses spawned via `Bash` tool calls, not inside the MCP server, and they only see the prefixed env vars. On a fresh install the MCP tools appeared to work (because they live inside the Node server), creating a false sense that the connection was good — but every skill script silently fell back to `localhost` with no database, which in turn caused background builder agents to stall at Stage 6 with no useful error. The duplicate helper across five files (instead of a single shared import) is necessary because three consumer scripts import `connect.py` **lazily** inside their `.connect()` methods, which runs after `argparse` has already evaluated its defaults — putting the helper only in `connect.py` would not fix them.

**How to avoid regression:** Any new Python script in this plugin that reads `SQL_*` or `AZURE_*` environment variables **must** include the `_load_plugin_userconfig_env()` helper at module top, before any `os.environ.get('SQL_*', ...)` call. When adding a new env var to the plugin's `userConfig` block in `plugin.json`, also add its name to the `keys` tuple in every copy of the helper. A follow-up worth doing: convert `skills/sql-connection/` into a proper importable package so the helper can live in one place — but the import must be eager and happen before argparse, otherwise the fix is incomplete.

**Related open issue (not yet fixed):** During install and update of this plugin on a fresh machine, Claude Code did **not** surface the interactive prompt for `userConfig` fields. Hypotheses include the undocumented `title` / `type` fields in each userConfig entry, the "Leave empty to..." phrasing in descriptions, or a Claude Code version difference. Until the root cause is identified and fixed, users may need to set the config values manually in `settings.json` under `pluginConfigs.dbt-pipeline-toolkit.options` (and in the system keychain for sensitive values). This needs to be documented in the plugin README.

### 2026-04-14 — Main-thread `--agent` delegation to plugin siblings empirically works (despite GitHub issues and "Not Planned" feature request)

**Observation:** On a fresh install of this plugin, invoking `claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator "Build a pipeline"` **successfully delegates to sibling plugin-shipped subagents**. The orchestrator running as the main thread has the `Task`/`Agent` tool available and can spawn specialists via `subagent_type: "dbt-pipeline-toolkit:<subdir>:<name>"`.

**Why this is surprising:** A research pass turned up multiple tracked issues on `anthropics/claude-code` that directly claim this should not work:
- [#19077](https://github.com/anthropics/claude-code/issues/19077) (OPEN) — "Custom agent as main → No `Task()` tool"
- [#23506](https://github.com/anthropics/claude-code/issues/23506) — "Custom agents (`--agent`) cannot spawn subagents … Task tool unavailable"
- [#19276](https://github.com/anthropics/claude-code/issues/19276) — feature request to make plugin agents callable via `Task` was **closed "Not Planned"** on 2026-02-27
- [#13605](https://github.com/anthropics/claude-code/issues/13605) — plugin subagents don't receive declared MCP tools
- [#13627](https://github.com/anthropics/claude-code/issues/13627) — spawned custom agent body content is silently dropped

The research concluded the delegation path was architecturally blocked. Empirical testing on a fresh install proved otherwise. Possible reasons: behavior was silently added after the issues were filed, the `~/.claude/plugins/*/agents/*.md` discovery path differs from the `.claude/agents/*.md` path the issues describe, or the 3-part namespaced invocation takes a different resolver than the bare-name invocation bug reports used. We don't know which.

**Full research archive:** `_Research/plugin-subagent-delegation.md` — contains every issue link, direct quotes, working-alternative architectures (skill-orchestrator, `general-purpose` with injected prompts, slash-command coordinator), and a list of follow-up empirical tests still needed (Issue #13627's body-drop claim, Issue #13605's MCP-strip claim).

**Implications for this plugin:**
- The current orchestrator-as-main-thread architecture is the right design and ships as-is. No fallback rewrite needed right now.
- **But it depends on an officially-unsupported path.** A future Claude Code release could re-break delegation without warning. Treat it like a beta-level dependency.
- Any CI smoke test for this plugin **must include** a minimal end-to-end run on a clean install, verifying the orchestrator actually spawns at least one specialist. A unit test is not enough; the bug this catches is invisible at the file level.
- A documented fallback architecture is worth keeping in `_Research/plugin-subagent-delegation.md` so that if delegation regresses, the conversion to a skill-orchestrator pattern is pre-planned, not panic-designed.

**How to avoid regression:**
- Keep `_Research/plugin-subagent-delegation.md` updated with any new issues or empirical observations about plugin delegation behavior
- Before every plugin release, run a smoke test on a fresh install to confirm the orchestrator still delegates
- If any future Claude Code release breaks delegation, fall back to the skill-orchestrator path documented in the research file — don't try to fix the broken delegation path itself

**Still needs empirical testing:**
1. Does Issue #13627's body-content-drop claim apply to our specialists? Test by asking a spawned specialist to identify its role — if it answers generically instead of from its own agent.md body, the bug is still in effect
2. Does Issue #13605's MCP-tool-strip claim apply to our specialists? Test by having a specialist try to call an `sql-server-mcp:*` tool and verify it resolves
3. Does the MCP server's `userConfig` prompt actually fire on a clean install (Finding 5 Problem B from `plugin_learnings.md`)?

### 2026-04-14 — Plugin-internal script paths must use `${CLAUDE_PLUGIN_ROOT}/skills/<name>/scripts/<file>.py` with forward slashes

**Change:** Every agent body and SKILL.md usage example in the plugin had its Python script invocation path rewritten from `$HOME/.claude/skills/<name>/scripts/<file>.py` to `${CLAUDE_PLUGIN_ROOT}/skills/<name>/scripts/<file>.py`. Applied in two mechanical passes across all 11 plugin files:

1. Prefix replacement: `$HOME/.claude/skills/` → `${CLAUDE_PLUGIN_ROOT}/skills/` (183 occurrences)
2. Backslash normalization: `\scripts\` → `/scripts/` (162 occurrences across 8 SKILL.md files)

Final count: **187 references** to `${CLAUDE_PLUGIN_ROOT}/skills/...` across 11 files. Zero remaining instances of the old `$HOME/.claude/skills/` pattern or Windows-cmd backslash separators in plugin source.

Files modified:
- `agents/data-explorer/agent.md`
- `agents/dbt-architecture-setup/agent.md`
- `agents/dbt-staging-builder/agent.md`
- `agents/dbt-pipeline-orchestrator/agent.md`
- `skills/data-profiler/SKILL.md`
- `skills/sql-server-reader/SKILL.md`
- `skills/sql-executor/SKILL.md`
- `skills/dbt-runner/SKILL.md`
- `skills/dbt-docs-generator/SKILL.md`
- `skills/dbt-project-initializer/SKILL.md`
- `skills/dbt-test-coverage-analyzer/SKILL.md`

**Reason:** On a fresh marketplace install, Claude Code does **not** put plugin skills at `~/.claude/skills/<name>/`. That location is reserved for standalone, non-plugin skills. Plugin contents are copied to the plugin cache at `~/.claude/plugins/cache/<id>/skills/<name>/`, and the official way to reference them from agent/skill markdown is the variable `${CLAUDE_PLUGIN_ROOT}`, which Claude Code substitutes inline at load time. On the user's dev machine the old pattern appeared to work because the standalone-skill copy was still present from earlier development, but on a fresh install every script invocation silently failed with "file not found." In background-spawned subagents (like `data-explorer` at Stage 2, or any builder at Stages 7–9), the failure was invisible to the orchestrator — the agent completed without error and returned an empty result, and the orchestrator stalled with no useful diagnostic. This was the root cause of the user's "data-profiler was called but no profile document was created" symptom, but it equally affected every other SQL-connected specialist and would have broken the entire pipeline at Stage 6 even if the profiler had happened to work.

**How to avoid regression:**
- **Any new Python script invocation** added to this plugin — in an agent body, a SKILL.md usage section, a hook command, or a code block — **must** use `${CLAUDE_PLUGIN_ROOT}/skills/<name>/scripts/<file>.py` with forward slashes.
- **Never use `$HOME/.claude/...` paths** in plugin markdown. That's for standalone-skill dev workflows only, not plugin content.
- **Never use Windows-cmd backslash separators** (`\scripts\`) in path segments. Git Bash interprets backslashes as escape characters inside double-quoted strings, so `"\scripts\profile_data.py"` becomes corrupted on Unix-style shells even though Windows Python accepts it.
- Consider a pre-commit or CI check that greps for `$HOME/.claude/skills/` in any `*.md` file under `agents/` or `skills/` and fails if found. This is a mechanical correctness check that catches this exact regression for free.

**Caveat — needs empirical verification on next fresh install:** We're >90% confident `${CLAUDE_PLUGIN_ROOT}` is substituted inline in agent and skill markdown body content (the plugins-reference doc says so, and `plugin.json` already uses it successfully for the MCP server path). The remaining risk is that substitution might only happen in `plugin.json` / hook / MCP configs and not in markdown body. If that turns out to be the case, the next fresh-install run will still fail to find the scripts — the failure mode would be Bash seeing a literal `${CLAUDE_PLUGIN_ROOT}` with no env var set, and the file not resolving. Fallback plan: add a `SessionStart` hook that exports `PLUGIN_ROOT=$CLAUDE_PLUGIN_ROOT` to the shell environment, then change the markdown references from `${CLAUDE_PLUGIN_ROOT}` to `$PLUGIN_ROOT` so the bash subprocess can resolve it. Worth testing the current fix first before preemptively adding the hook.

### 2026-04-14 — Agent `skills:` frontmatter must use 2-part `dbt-pipeline-toolkit:<skill>` namespace

**Change:** Every `skills:` field in all 8 plugin agent files was rewritten from bare skill names (e.g. `dbt-runner, data-profiler, sql-server-reader`) to the 2-part plugin namespace format (`dbt-pipeline-toolkit:dbt-runner, dbt-pipeline-toolkit:data-profiler, dbt-pipeline-toolkit:sql-server-reader`). This field controls which skills are preloaded into a subagent's context when it spawns.

**Reason:** Plugin skills are registered under a 2-part namespace `<plugin-name>:<skill-directory>`, per the official Claude Code skills docs:

> "Plugin skills use a `plugin-name:skill-name` namespace, so they cannot conflict with other levels."

This is a **different format from plugin agents**, which in this plugin use a 3-part namespace `<plugin>:<subdir>:<frontmatter-name>` because agents live in subdirectories rather than as flat files. The rule is really that each directory level under `agents/` or `skills/` contributes one namespace segment on top of the plugin name. Skills in this plugin are at `skills/<name>/SKILL.md` (depth 1 under `skills/`), giving 2-part names. Agents in this plugin are at `agents/<name>/agent.md` (depth 1 under `agents/` too, but Claude Code also appends the frontmatter `name` as a third segment — a subtlety that only applies to agent discovery, not skill discovery).

Bare-name skill references were failing silently: when an agent declared `skills: data-profiler` and spawned as a subagent, Claude Code resolved "data-profiler" against the plugin-namespace and found nothing. The preload produced an empty skill list, and the specialist started without any of the skill context it was designed to have. This was another silent capability-degradation bug — no error, just quietly less-effective specialists.

**How to avoid regression:**
- **Any new `skills:` field entry** added to an agent in this plugin must use `dbt-pipeline-toolkit:<skill-dir-name>` — 2 segments, not 3.
- **Do not confuse skill and agent namespacing.** Skills are 2-part (`dbt-pipeline-toolkit:data-profiler`). Agents are 3-part (`dbt-pipeline-toolkit:data-explorer:data-explorer`). The formats are not unified.
- **Keep skill directory names descriptive.** Since the directory name becomes the public skill name, renaming a skill directory is a breaking change for every agent that preloads it.

### 2026-04-14 — "Locked by plugin" clarification

**What it means:** Skills (and agents, commands, hooks) that come from an installed plugin appear in the Claude Code UI marked as "locked by plugin." This label indicates:

1. The skill is **owned by the plugin system** and lives in `~/.claude/plugins/cache/<id>/skills/<name>/`, not the user's `~/.claude/skills/` directory.
2. **The user cannot edit it in place** — the plugin cache is rewritten on every `claude plugin update`, so local edits would be destroyed.
3. Its **lifecycle is tied to the plugin**: install adds it, uninstall removes it, update replaces it.
4. It **cannot be overridden by same-name personal or project skills** because plugin skills live in their own `plugin-name:skill-name` namespace — no conflict possible.
5. **To customize, users must fork the plugin**, not hand-edit the cached copy. Same pattern as `node_modules/` or `site-packages/` — managed code, not sandbox.

**Implication for plugin authors:** Plugin releases are production deploys from the user's perspective. Users have no in-place escape hatch for plugin bugs. This raises the bar for pre-release testing on fresh installs — there is no customer-side workaround for shipping a broken plugin.

### General rule — test on a fresh install, not in dev

Every finding above was invisible during local development (`--plugin-dir` or direct `.claude/agents/` drop) and only surfaced after installing from the marketplace on a second machine. Before shipping any plugin change that touches agent definitions, orchestration, or permission flow:

1. Bump the plugin version in `plugin.json`
2. Install from the marketplace on a clean target
3. Run the happy-path scenario end-to-end
4. Verify background agents actually produced output, not just "completed" status
