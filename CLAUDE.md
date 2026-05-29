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

skills/                # 9 user-invocable skills
  dbt-runner/                  # Execute dbt commands (run, test, build, etc.)
  dbt-test-coverage-analyzer/  # Analyze test coverage gaps
  dbt-docs-generator/          # Generate and serve dbt docs
  dbt-project-initializer/     # Scaffold new dbt projects
  data-profiler/               # Profile SQL Server tables and CSVs
  sql-executor/                # Load CSVs and execute SQL mutations
  sql-server-reader/           # Read-only queries against SQL Server
  sql-connection/              # Connection management script
  pbip-from-dbt/               # Generate a Power BI Project (PBIP) from the finished star schema

hooks/                 # 4 lifecycle hooks (all registered in plugin.json)
  validate-dbt-structure.py    # PreToolUse(Write|Edit): validates dbt file naming/placement
  approve-plugin-bash.py       # PreToolUse(Bash): auto-approves plugin-internal scripts (allowlist)
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

### Bug-class audit policy

When you discover a bug that matches the *shape* of a previously-resolved issue, do not file it as a single instance. The class is what matters, not the instance.

**Procedure:**

1. **Recognise the class.** Common classes already seen in this plugin: path-prefix leakage (bare `scripts/`, `$HOME/.claude/skills/`, Windows backslashes — I-047, I-021), namespace format mismatches (2-part vs 3-part — Finding 1), compound Bash expressions (Finding 9 atomic refactor), improper agent frontmatter fields (Finding 2), SKILL.md flag names that don't exist in the script's argparse (I-018, I-050), `Path(__file__)` used to find user-project content (I-023).
2. **Grep the entire plugin first.** Before opening an issue, run the matching grep across `agents/`, `skills/`, `hooks/`, `reference/`, and `_Documentation/`. Treat the *count of occurrences* as the size of the problem.
3. **File ONE issue covering the full scope.** Title the row "<class> — N occurrences across M files." Include the grep command in the body so the reviewer can re-derive the list. Do NOT open one issue per file.
4. **Fix all instances in one pass.** The risk of partial fixes is that the next contributor sees mixed forms and concludes the old form is still valid. One pass, one PR, one verification.
5. **Add a regression check.** A new gate in the pre-ship audit suite (see Backlog → Developer tooling) for each new class. If the grep returns >0 after the fix, the audit fails. This is how a bug-class becomes extinct rather than dormant.

**Why this matters:** every cross-plugin learning we've documented in this CLAUDE.md was discovered as one instance, then audit revealed the full footprint. I-047 alone surfaced 14 instances of bare `scripts/` paths across 4 builder agents and 1 docs-generator script. Treating it as a single bug would have left 13 ticking time bombs in the plugin.

Source: codified from a project-specific Claude Code auto-memory feedback entry. This CLAUDE.md is the canonical home for the rule going forward.

### Anti-patterns to avoid

- **Don't file an issue and then forget to add the ID to commits that touch related code.** Reference the `I-###` ID in commit messages ("fix: use --target flag instead of nonexistent --fail-below (I-018)") so the history is searchable.
- **Don't silently close issues because "we're not going to fix that."** Use `wontfix` status with a short explanation in the `Blocker` column. Future contributors will reopen it if they disagree and the explanation will help them decide.
- **Don't reuse IDs.** Even if an issue was closed in error, create a new ID for the rediscovered problem. Link to the old one in the notes.
- **Don't use the issue tracker as a to-do list for this conversation.** Task tracking inside a single session belongs in TaskCreate; the issue tracker is for problems that persist across sessions.
- **Don't mix backlog-style planned work into the issue tracker.** New features go in `Backlog.md`. Only file in `Issues.md` if there's an existing problem to fix.

## Plugin Gotchas — Non-Negotiable Rules

Hard constraints distilled from bugs that were **invisible in `--plugin-dir` dev and only surfaced on a fresh marketplace install**. Each rule lists its source finding. Full narrative and evidence: [`_Documentation/plugin_learnings.md`](_Documentation/plugin_learnings.md) (Findings 1–10). Per-issue tracking: `_Plan/Issues.md`.

> **Golden rule:** any change touching agents, orchestration, permissions, or script paths must be verified on a clean marketplace install — confirm the *side effects* (output files actually written), not just that agents reported "completed." Every rule below was a silent failure in dev.

### Namespacing (Findings 1, 8)
- **Agents are 3-part:** reference every plugin agent as `dbt-pipeline-toolkit:<subdir>:<frontmatter-name>` — in the orchestrator's `tools: Agent(...)` allowlist, every `subagent_type:`, and every `claude --agent` example. The middle+last segments duplicate because each agent's subdir matches its frontmatter `name`; **keep them identical** or every reference breaks silently.
- **Skills are 2-part:** the agent `skills:` frontmatter field uses `dbt-pipeline-toolkit:<skill-dir>` — never 3-part. (The format differs from agents because skills are flat dirs, agents are nested.)
- The marketplace name is **not** part of either namespace.
- Always verify the actual registered name in the `/agents` and `/skills` pickers on a fresh install — the docs example (2-part agents) is for flat files and is wrong for this repo's subdirectory layout.

### Agent frontmatter (Finding 2)
- **Never** add `permissionMode`, `hooks`, or `mcpServers` to agent frontmatter — they are silently stripped at load for plugin-shipped agents. Declare hooks/MCP servers at plugin level in `plugin.json`; set permission mode at the spawn call site. "Not supported for plugin-shipped agents" means "in agent frontmatter," not "anywhere in the plugin."

### Permissions & background subagents (Findings 3, 9)
- Every `Task(..., run_in_background: true)` spawn **must** pass `mode: "acceptEdits"` at the call site — background agents have no channel to answer a permission prompt and will stall silently.
- `acceptEdits` only auto-approves file writes + filesystem Bash (`mkdir`, `cp`, `mv`, `touch`). Arbitrary Bash (`python ...`, `dbt ...`) is auto-approved by the plugin-level PreToolUse hook `hooks/approve-plugin-bash.py`. Any **new** Bash command in an agent/SKILL must be added to that allowlist; new Python scripts under `skills/*/scripts/` are auto-covered by the generic pattern. Never add broad wildcards (`python -c .*`, `Bash(*)`).
- Every orchestrator Task-spawn prompt should include the explicit script path the agent must run (defense-in-depth against agent body content being dropped at spawn — Issue #13627).
- **PreToolUse hook output format:** emit `{"decision": "approve|block|skip", "reason": "..."}` at the **top level**, not nested `hookSpecificOutput`. `{}` = no opinion (defer to default flow). Wrap the hook's `main()` in try/except so it never crashes. ⚠️ `plugin_learnings.md` Finding 9 still shows the old (wrong) nested format — this rule supersedes it.

### Bash must be atomic (Finding 9, Round 2)
- No compound shell expressions **anywhere** (agents, SKILLs, hooks, doc examples): no `&&`, `||`, `;`, `|`, subshells `(...)`, `$(...)`, backticks, heredocs, or `2>/dev/null` redirects. Put sequential/conditional logic in LLM text (multiple atomic calls) or a single Python script. Grep new files for these operators before committing.
- Before documenting a CLI flag in a SKILL.md, verify it exists in the script's argparse (a phantom `--fail-below` was invented once; the real flag is `--target`).

### Script & project paths (Findings 7, I-023)
- Always reference plugin scripts as `${CLAUDE_PLUGIN_ROOT}/skills/<name>/scripts/<file>.py` with **forward slashes**. Never `$HOME/.claude/skills/...` and never backslash separators (`\scripts\`).
- Python scripts find **user project** folders (`2 - Source Files/`, `7 - Data Exports/`, `dbt_project.yml`) via `Path.cwd()`, never `Path(__file__)` (which resolves into the plugin cache). Reserve `Path(__file__)` for files shipped inside the skill. Always honor an explicit `--source-dir` override.

### userConfig env vars (Finding 5)
- Plugin subprocesses receive userConfig as `CLAUDE_PLUGIN_OPTION_<KEY>`, not bare names. Every Python script reading `SQL_*`/`AZURE_*` must call `_load_plugin_userconfig_env()` at module top, **before** argparse defaults are evaluated. When adding a userConfig key, add it to the `keys` tuple in **every** copy of the helper.
- Open issue (Problem B): the install-time userConfig prompt does not reliably fire — document manual `settings.json` setup (`pluginConfigs.dbt-pipeline-toolkit.options`) as fallback in the README.

### Build discipline (I-024–I-030, Finding 6)
- **Compile one, then scale:** build the simplest model first and pass `dbt compile` → `dbt run` → `dbt test` on it before parallelizing the rest. Catches reserved words, date misdetection, EXEC() quoting, duplicate `sources.yml`, materialization issues early. Applies to staging, dimensions, and facts alike.
- Orchestrator-as-main-thread delegation works but is **officially unsupported** (feature request closed "Not Planned"). Keep a fresh-install smoke test each release; the pre-planned fallback (skill-orchestrator) lives in `_Research/plugin-subagent-delegation.md`.
