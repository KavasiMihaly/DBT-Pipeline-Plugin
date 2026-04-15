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

## Issue Tracker Maintenance

This plugin has a dedicated issue tracker at **`_Plan/Issues.md`** that captures every known problem, empirical verification need, architectural risk, and enhancement. A companion **`_Plan/Backlog.md`** tracks forward-looking planned work per the user's global CLAUDE.md convention.

**Core policy:** never silently fix an issue or discover a problem without adding an entry to `Issues.md`. If you identify a problem during development, testing, or research — even a small one — create an entry before (or in the same commit as) the fix. Undocumented fixes are invisible to future contributors and to empirical verification passes.

### Where does something go?

| Situation | File |
|---|---|
| Known bug in existing code | `Issues.md` → category `bug` |
| Unverified claim that needs a fresh-install test | `Issues.md` → category `empirical` |
| Missing or wrong documentation | `Issues.md` → category `docs` |
| Improvement to working feature | `Issues.md` → category `enhancement` |
| Architectural concern about current design | `Issues.md` → category `risk` |
| Planned new feature built from scratch | `Backlog.md` as a backlog row |
| Question for the user | Ask in conversation, do not file |
| Conversational context | Do not file |

### Issue entry schema

Every new row in `Issues.md` needs:

```
| I-### | Title (short noun phrase) | category | severity | status | YYYY-MM-DD | Source (finding/session/commit) | Blocker or next step |
```

- **ID:** sequential `I-###`, never reused even after closing. Check the highest existing ID in the file and increment.
- **Category:** `empirical` | `bug` | `docs` | `enhancement` | `risk`
- **Severity:** `critical` (blocks shipping) | `high` | `medium` | `low`
- **Status:** `open` → `in-progress` → `resolved` (fixed, awaiting verification) → `closed` (verified on fresh install) → optionally `archived`. Special states: `blocked` (waiting on something external), `wontfix` (decided not to address).
- **Found date** and **Source** let future contributors trace the origin of the issue without re-reading the whole conversation history.

### Lifecycle

1. **Discovery** — add the row immediately with status `open`. Don't wait until you have time to fix it.
2. **Triage** — set category and severity. If `critical`, flag it in the next status message to the user.
3. **Work** — set status to `in-progress` when you start. Link any supporting research in `_Research/` or plan files in `_Plan/<name>.md` from the `Source` column.
4. **Fix** — commit the fix, set status to `resolved`.
5. **Verify** — after fresh-install testing (or equivalent verification), set status to `closed`. Add a verification note to the `Blocker` column like "verified on fresh install 2026-05-01 — profile JSONs produced as expected."
6. **Archive** — closed items older than 30 days can be moved to `_Plan/Issues-Archive.md` to keep the active tracker tight.

### When to review

- **Before every plugin release:** walk through every `open` and `resolved` `empirical` / `critical` item. Nothing ships with a critical empirical verification unresolved.
- **After every significant development session:** add new entries for anything discovered during the session. The session ends with a clean Issues.md, or it doesn't end.
- **Weekly cleanup:** archive closed items > 30 days old, re-triage items that have been open too long, consolidate any duplicates.

### Anti-patterns to avoid

- **Don't file an issue and then forget to add the ID to commits that touch related code.** Reference the `I-###` ID in commit messages ("fix: use --target flag instead of nonexistent --fail-below (I-018)") so the history is searchable.
- **Don't silently close issues because "we're not going to fix that."** Use `wontfix` status with a short explanation in the `Blocker` column. Future contributors will reopen it if they disagree and the explanation will help them decide.
- **Don't reuse IDs.** Even if an issue was closed in error, create a new ID for the rediscovered problem. Link to the old one in the notes.
- **Don't use the issue tracker as a to-do list for this conversation.** Task tracking inside a single session belongs in TaskCreate; the issue tracker is for problems that persist across sessions.
- **Don't mix backlog-style planned work into the issue tracker.** New features go in `Backlog.md`. Only file in `Issues.md` if there's an existing problem to fix.

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

### 2026-04-14 — Remove `permissionMode:` from all plugin-shipped agent frontmatter (and clarify the plugin-level vs agent-level distinction)

**Change:** Stripped `permissionMode: default` / `permissionMode: acceptEdits` from the orchestrator and four builder agents (`dbt-staging-builder`, `dbt-dimension-builder`, `dbt-fact-builder`, `dbt-test-writer`).

**Reason:** The Claude Code plugins reference explicitly lists `permissionMode`, `hooks`, and `mcpServers` as **not supported for plugin-shipped agents** — "for security reasons, `hooks`, `mcpServers`, and `permissionMode` are not supported." **Crucial distinction:** this restriction applies only to fields declared inside an agent's own `agent.md` YAML frontmatter. It does NOT apply to fields declared at the plugin level in `plugin.json`. The existing `plugin.json` in this repo already demonstrates this: it successfully ships a `sql-server-mcp` MCP server and three `PreToolUse` / `WorktreeCreate` / `WorktreeRemove` hooks at plugin level, and they all load normally.

The asymmetry is deliberate. Plugin-level declarations in `plugin.json` are auditable at install time — users can inspect them before enabling the plugin. Agent-level declarations would move privilege-granting into an unaudited runtime surface (because agents are spawned dynamically, not declared upfront). Stripping those fields from agent frontmatter forces all privilege declarations back into `plugin.json`, which is the audited contract.

Leaving stripped fields in agent frontmatter was misleading in another way: they implied behavior that never took effect once installed, and they hid the real problem during development (the agents appeared fully autonomous in dev because the frontmatter was honored there). Permission control now happens either at the call site via the orchestrator's `mode: "acceptEdits"` parameter on each Task spawn, or at the plugin level via a `PreToolUse` hook (see the 2026-04-14 hook entry below).

**How to avoid regression:**
- **Never add `permissionMode`, `hooks`, or `mcpServers` fields to any agent frontmatter** in this repo. Those concerns belong in `plugin.json` (for plugin-level hooks and MCP servers) or at the spawn call site (for per-invocation permission mode).
- **Do add `hooks` and `mcpServers` to `plugin.json`** when you need them. Plugin-level declarations are fully supported and are the correct place for plugin-wide capabilities.
- **When you see a doc sentence saying "X is not supported for plugins," read the scope carefully.** "For plugin-shipped agents" means "in agent frontmatter," not "anywhere in the plugin." Getting this distinction right unblocks capabilities that would otherwise look forbidden — including the hook-based Bash auto-approval pattern documented in the 2026-04-14 hook entry below.

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

### 2026-04-14 — Plugin-level `PreToolUse` hook auto-approves plugin-internal Bash calls for background subagents

**Change:** Added `hooks/approve-plugin-bash.py` (a Python PreToolUse hook) and registered it in `plugin.json` with matcher `Bash`. The hook reads the PreToolUse JSON payload from stdin, splits the Bash command into subcommands at shell operators (`&&`, `||`, `;`, `|`, `|&`, `&`, newline), and returns `permissionDecision: "allow"` only when **every** subcommand matches a narrow allowlist. If any subcommand is not on the allowlist, the hook returns an empty decision and the call falls through to the default permission flow.

Updated every Task spawn prompt in the orchestrator (Stages 2, 7, 8, 9, 10, 11) to include the explicit script path the agent should run, as defense-in-depth against Issue #13627 (agent body content may be silently dropped at spawn time per the Finding 6 research).

**Reason:** `acceptEdits` permission mode only auto-accepts file edits and filesystem Bash commands (`mkdir`, `cp`, `mv`, `touch`, etc.) — it does NOT auto-accept arbitrary Bash like `python profile_data.py` or `python run_dbt.py run`. In a **background** subagent, any non-filesystem Bash call stalls because the permission layer tries to prompt the user, and background subagents have no interactive channel. This was the root cause of the user's "data-profiler was called but no profile document was created" symptom: the `data-explorer` agent spawned background, tried to run `python profile_data.py`, got silently refused at the permission layer, and fell back to reading CSVs with its Read tool (producing a degraded summary with none of the profiler's intelligence).

The PreToolUse hook is the only supported mechanism that:
1. Works for background subagents (fires before the permission prompt, can skip the prompt entirely)
2. Ships automatically with the plugin (no user setup, no `settings.json` editing)
3. Has a narrow, auditable allowlist (every approved pattern lives in one Python file)
4. Does not require `bypassPermissions` mode (which would unlock *all* Bash, not just the plugin's own scripts)

**Allowlist design:** The allowlist was built from a full audit of every `python` / `git` / `ls` / `find` / `mkdir` / `cp` / `wc` / `echo` command in every `agent.md` and `SKILL.md` in the plugin. Six categories:

1. **Plugin Python scripts** — anything matching `python <path>/skills/<skill-name>/scripts/<file>.py <args>`. Covers `profile_data.py`, `query_sql_server.py`, `load_data.py`, `run_dbt.py`, `analyze_coverage.py`, `generate_docs.py`, `initialize_project.py`, `reset_project.py`.
2. **Narrow `python -c` one-liners** — specific forms only, not all inline Python. Includes the pyodbc driver check (`python -c "import pyodbc; print(pyodbc.drivers())"`) and the CSV file-copy helper in `dbt-architecture-setup` (`python -c "import shutil, glob, os; ..."`). Other `python -c` strings fall through to default flow.
3. **Virtualenv / pip** — `python -m venv`, `pip install`, `pip list`, etc.
4. **Git commands** — `git init`, `git status`, `git add`, `git commit`, `git rev-parse`, `git worktree`, etc. (needed by Stage 5 scaffold init and Stages 8/9 worktree isolation).
5. **Filesystem discovery** — `find . -name "*.csv"`, `ls *.csv`, `ls dbt_project.yml`.
6. **Folder and file ops** — `mkdir -p "2 - Source Files"`, `cp *.csv "2 - Source Files/"`, `wc -l`, `echo` with simple literals.

**Compound-command safety:** The hook uses a proper shell-aware splitter that respects single and double quotes — operators inside string arguments are not treated as split points. It also handles subshell parentheses `(...)`. Every subcommand in a pipeline or sequence must independently match the allowlist; a single non-matching subcommand causes the whole call to fall through. This matches the Claude Code permissions model's "a rule must match each subcommand independently" requirement and prevents smuggling attacks like `python run_dbt.py run && rm -rf /`.

**How to avoid regression:**
- **Any new Bash command** added to an agent body or SKILL.md — whether in the orchestrator, a specialist, or a new skill — **must** be added to the allowlist in `hooks/approve-plugin-bash.py` before it can run in a background subagent.
- **When adding a new Python script to a skill**, no allowlist change is needed — the generic `python <path>/skills/<skill>/scripts/<file>.py` pattern covers it automatically. This is the primary reason the allowlist is structured around a generic pattern for the main case and narrow literal patterns only for exceptions.
- **Never add broad wildcard patterns** like `python -c .*` or `Bash(*)` to the allowlist — every new pattern should be as narrow as possible and have a comment explaining exactly which stage of the pipeline uses it.
- **Audit the allowlist when refactoring commands.** If a stage's Bash call is changed (e.g. from `dbt run` via the Python wrapper to some other form), verify that the allowlist still covers the new form before shipping.
- **Every Task spawn prompt in the orchestrator should include the explicit script path** the spawned agent needs to run. This is defense-in-depth against Issue #13627 (agent body content may be silently dropped at spawn time). Don't rely on the spawned agent's body content to tell it which script to call — put the path in the orchestrator's prompt string.

**Empirical verification needed on next fresh install:**
1. Does the hook actually fire for Bash calls in background subagents? (The docs say yes, but we haven't tested.)
2. Does the `permissionDecision: "allow"` response actually skip the permission prompt for background-mode calls? (Documented as yes, but the interaction with background-mode prompt suppression is not explicitly tested.)
3. Do all the profile JSON files actually appear in `1 - Documentation/data-profiles/` after Stage 2?

If any of those fail, the fallback is either (a) adding more narrow allowlist patterns, (b) switching specific stages to `bypassPermissions` mode, or (c) moving Bash calls out of subagents entirely to the orchestrator main thread.

### 2026-04-14 — Atomic Bash commands only — no compound shell expressions anywhere in the plugin

**Change:** Refactored the orchestrator's Stages 0, 5, and 6 to use single atomic Bash commands instead of compound shell expressions. Simplified `hooks/approve-plugin-bash.py` to remove now-unused compound-only patterns. Added the atomic-command rule to the global `~/.claude/CLAUDE.md` so it applies across all projects and all script generation.

Specific commands changed in `agents/dbt-pipeline-orchestrator/agent.md`:

| Before | After |
|---|---|
| `find . -name "*.csv" -type f 2>/dev/null` | `find . -name "*.csv" -type f` |
| `ls dbt_project.yml 2>/dev/null && echo "INCREMENTAL_MODE" \|\| echo "FRESH_BUILD"` | `ls dbt_project.yml` (orchestrator reads exit code / output and decides the mode in LLM text) |
| `git rev-parse --git-dir 2>/dev/null \|\| (git init && git add -A && git commit -m "Initial scaffold")` | Four atomic calls: `git rev-parse --git-dir`, then if fails `git init`, `git add -A`, `git commit -m "Initial scaffold"` |
| `ls "2 - Source Files/"*.csv \| wc -l` | `find "2 - Source Files" -name "*.csv" -type f` (orchestrator counts lines in LLM text) |

**Reason:** Claude Code's permission layer matches rules per subcommand of any shell expression. Compound operators (`&&`, `||`, `;`, `|`, subshells) force the permission layer to split the command and evaluate each part — and any part that is not allowlisted causes the whole call to fall through to the interactive permission prompt. In background subagents (which have no interactive channel), this means the tool call stalls silently.

Atomic commands bypass this problem entirely:
- **Filesystem atomic commands** (`mkdir`, `touch`, `mv`, `cp`, `rm`) are **auto-approved under `acceptEdits` mode** — no hook needed.
- **Non-filesystem atomic commands** (`python script.py`, `git init`, `find -name`) are individually matchable by a simple allowlist pattern in the plugin's `PreToolUse` hook.
- **Compound expressions** are neither auto-approved nor cleanly allowlistable, requiring a complex compound-command splitter in the hook that is fragile, a security surface, and a maintenance burden.

Before this refactor, `hooks/approve-plugin-bash.py` needed ~60 lines of quote-aware compound-command splitter code just to handle the orchestrator's four compound commands. After the refactor, the splitter could be removed (kept as defensive fallback) and the allowlist collapsed to simple single-command patterns that match individual atomic calls.

**Token cost acknowledged:** converting compound commands to atomic equivalents increases per-session token usage by roughly 1–3% — each extra Bash tool call carries ~50–80 tokens of protocol overhead (tool_use block, tool input JSON, tool_use_id, tool_result block), and breaking one compound into 3–4 atomic calls adds ~200–300 tokens per refactored workflow step. Across a full pipeline build with ~10–15 refactored operations, that's ~2,000–4,500 extra tokens per run. This cost is worth paying because the alternative is a plugin that stalls silently on background subagent invocations, which is not shippable.

**How to avoid regression:**
- **Grep every new agent.md / SKILL.md / hook / orchestrator stage file for `&&`, `||`, `;`, `|` (as shell operators), subshells `(...)`, `$(...)`, backticks, and heredocs before committing.** Any match that is not inside a quoted string argument is a violation.
- **When adding a new pipeline step that needs multiple commands**, split into sequential Bash tool calls that the orchestrator issues in order, reading each command's output before issuing the next. If the logic is genuinely complex (many interdependent commands), write a Python script in the appropriate `skills/<name>/scripts/` directory and call it as a single atomic invocation.
- **Never reintroduce shell-level conditionals or pipelines** to "save a tool call." The token savings are small; the reliability cost of losing background-subagent compatibility is catastrophic.
- **Also applies to SKILL.md documentation code blocks** — users will copy-paste examples from SKILL.md. Ship atomic examples so users don't learn patterns that will break in automation.

### General rule — test on a fresh install, not in dev

Every finding above was invisible during local development (`--plugin-dir` or direct `.claude/agents/` drop) and only surfaced after installing from the marketplace on a second machine. Before shipping any plugin change that touches agent definitions, orchestration, or permission flow:

1. Bump the plugin version in `plugin.json`
2. Install from the marketplace on a clean target
3. Run the happy-path scenario end-to-end
4. Verify background agents actually produced output, not just "completed" status
