# Plugin Learnings — DBT Pipeline Toolkit

Working notes and discoveries from building the `dbt-pipeline-toolkit` Claude Code plugin. Intended as source material for a conference presentation on **agentic tooling in data engineering**.

The plugin packages 9 specialized agents, 8 skills, 3 hooks, and an MCP server into a single installable unit distributed through an external marketplace repo (`AI-plugins`). The goal was end-to-end automation: drop CSVs in a folder, get a tested dbt star schema on SQL Server.

Everything in this doc is the result of things that **actually broke** when the plugin was installed on a second machine — not theory.

---

## Why this matters for data engineering

A data engineering pipeline is a *multi-agent problem by nature*. You have distinct roles — requirements, source profiling, staging, dimensions, facts, tests, validation — each with its own expertise and its own tools. Claude Code subagents map cleanly onto these roles, and orchestration lets a "conductor" agent drive the entire workflow with minimal human touch points (2 total in this plugin: a discovery Q&A and a plan approval gate).

The promise: a user drops CSV files in a folder, answers 5 questions, approves a plan, and walks away with a fully tested, validated dbt pipeline. The reality: getting there surfaced several gotchas that aren't obvious from the plugin documentation alone.

---

## Finding 1 — Plugin agents get namespaced at install time (and the docs example is wrong)

### What I learned

When a Claude Code plugin is installed, every agent it ships is registered under a namespace derived from the plugin's `name` field in `plugin.json`. What the docs say vs what actually happens turned out to be two different things, and chasing that gap was the single most expensive lesson of building this plugin.

**What the official plugins reference shows:**

> "This name is used for namespacing components. For example, in the UI, the agent `agent-creator` for the plugin with name `plugin-dev` will appear as `plugin-dev:agent-creator`."

That implies a 2-part format: `<plugin-name>:<agent-name>`. I applied a fix based on that example and renamed every reference in the orchestrator from bare names (e.g. `business-analyst`) to the documented 2-part form (e.g. `dbt-pipeline-toolkit:business-analyst`). That fix was **still broken** on a fresh install.

**What actually happens when the plugin is installed:**

I verified on a clean machine by checking the `/agents` picker, and every registered agent shows up with a **3-part** name:

```
dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator
dbt-pipeline-toolkit:business-analyst:business-analyst
dbt-pipeline-toolkit:data-explorer:data-explorer
...
```

The 3 segments are:

```
<plugin-name> : <subdirectory-under-agents/> : <frontmatter-name-field>
```

For this plugin, every agent's subdirectory name matches its frontmatter `name` field, so every 3-part name has a duplicated middle+last segment — but that's the real registered name, not a display quirk.

**Why the docs example doesn't match reality:**

The official example in the plugins reference is for a **flat** agent file structure: `agents/security-reviewer.md`, `agents/performance-tester.md`. In that layout, the format really is `<plugin>:<filename-without-ext>` — 2 parts. But this plugin (like many real plugins that want per-agent scope for assets, examples, and reference files) uses a **subdirectory** structure: `agents/<name>/agent.md`. When Claude Code discovers agents under nested directories, it uses the subdirectory as an intermediate namespace level, producing 3-part names.

The docs don't document this behavior at all. The only way to discover it is to install the plugin on a fresh machine and look at the registered name. That's a significant gap in the official plugin reference.

### How it broke (three times)

1. **First break** — the orchestrator originally referenced sibling agents by their bare names (`business-analyst`, `dbt-staging-builder`, etc.) in both the `tools: Agent(...)` allowlist and every `Task(subagent_type: "...")` call. That worked in local dev (where agents live under bare names via `.claude/agents/` or `--plugin-dir`) and failed silently on install.
2. **Second break** — I read the docs, saw the 2-part format, and renamed everything to `dbt-pipeline-toolkit:business-analyst` etc. Still broken, still silent, still zero error output. The `Agent(...)` allowlist was still empty because no registered agent matched the 2-part name.
3. **Third break caught it** — testing on a fresh install, checking the `/agents` picker directly, revealed the 3-part name with the subdirectory segment. Only then did the correct format (`dbt-pipeline-toolkit:<dir>:<name>`) become visible.

At every stage, the orchestrator would run, produce no error, spawn nothing, and eventually time out or hit `maxTurns`. The failure was undetectable without a fresh install.

### Fix applied

Every `dbt-pipeline-toolkit:<name>` reference in `agents/dbt-pipeline-orchestrator/agent.md` was updated to `dbt-pipeline-toolkit:<name>:<name>` — the `tools: Agent(...)` allowlist, all 8 `subagent_type:` spawn calls, and all 3 `claude --agent ...` invocation examples. The orchestrator is now invoked as:

```bash
claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator "Build a pipeline"
```

### Takeaway for the talk

> **Don't trust documentation examples — verify the real registered name on a fresh install.** The Claude Code plugins reference shows a 2-part namespace format for agents. The actual format depends on your directory layout: flat files get 2-part names, subdirectory-based agents get 3-part names. This isn't documented. The only reliable way to know what your plugin actually exposes is to install it on a clean machine and look at the picker.
>
> And keep the subdirectory name identical to the frontmatter `name` field. If they diverge, the registered name silently follows the directory, and every in-repo reference to the agent becomes wrong with no error.

This is the finding that most deserves a dedicated slide: it's the exact story of "works in dev, works according to the docs, still broken in production" and it took three fix attempts before a fresh-install test surfaced the real format. **The main point: the docs example is for flat files only; subdirectories add an extra segment.**

---

## Finding 2 — Plugin-shipped agents cannot declare `permissionMode`

### What I learned

From the Claude Code plugins reference, under "Agents":

> "Plugin agents support `name`, `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `skills`, `memory`, `background`, and `isolation` frontmatter fields. **For security reasons, `hooks`, `mcpServers`, and `permissionMode` are not supported for plugin-shipped agents.**"

This is a security boundary: a malicious plugin could otherwise install itself and silently grant itself broad write access, or attach background hooks and MCP servers that run without user awareness. By stripping those three fields at load time, Claude Code forces plugin permissions to come from either the user's explicit approval in-session or from fields the user controls in their settings.

### How it broke

Four of the builder agents (`dbt-staging-builder`, `dbt-dimension-builder`, `dbt-fact-builder`, `dbt-test-writer`) all had:

```yaml
permissionMode: acceptEdits
```

in their frontmatter. During development outside the plugin context this made the agents fully autonomous — they could `Write` and `Edit` files without prompting. When installed as a plugin, that line was silently dropped. The agents still ran, but any `Write`/`Edit` call triggered a permission prompt.

This is only a visible problem when agents run in the foreground — in the background, it's invisible and fatal (see Finding 3).

### Takeaway for the talk

> **Plugin frontmatter isn't a superset of standalone agent frontmatter.** Fields that grant elevated privileges are stripped at load time. If your agent relies on `permissionMode` to function, it will not work as a plugin. You have to either pass the mode at call time (foreground) or design the flow so permission prompts can actually reach a human.

---

## Finding 3 — Background agents cannot satisfy permission prompts

### What I learned

When you spawn a subagent with `run_in_background: true`, it has no interactive channel. There's no way for the background task to surface a "Claude wants to write file X — approve?" prompt to the user. The prompt goes nowhere, the agent blocks waiting for a response that will never arrive, and eventually the task either times out or stalls until the orchestrator gives up.

This is documented in my personal global CLAUDE.md as a hard rule:

> **Background agents CANNOT prompt the user for permissions. Always set the `mode` parameter when spawning agents to prevent silent failures. Background agents (`run_in_background: true`) ALWAYS use `mode: "acceptEdits"`.**

The correct pattern is to pass the permission mode explicitly when spawning, *not* to rely on the spawned agent's own frontmatter:

```
Task(
  subagent_type: "dbt-pipeline-toolkit:dbt-dimension-builder",
  prompt: "...",
  run_in_background: true,
  mode: "acceptEdits"
)
```

### How it broke — the full failure chain

This finding compounds with Finding 2 to produce a spectacular silent failure:

1. The orchestrator enters Stage 8 (build dimensions) and fans out several `dbt-dimension-builder` tasks with `run_in_background: true`.
2. Each builder previously relied on its frontmatter `permissionMode: acceptEdits` — which is stripped because it's plugin-shipped (Finding 2).
3. The orchestrator's spawn call does **not** pass `mode: "acceptEdits"` explicitly.
4. The background builder starts, tries its first `Write` call for a new `dim_*.sql` model file, and hits a permission gate.
5. The permission gate has nowhere to send the prompt.
6. The background task stalls indefinitely.
7. The orchestrator polls, sees no progress, eventually times out (or hits `maxTurns`) and reports "no models built" with no usable error message.

From the user's perspective, the orchestrator appears frozen or inert — "it's not doing anything."

### Takeaway for the talk

> **Background + plugin = you must pass permissions at the call site.** Never trust the spawned agent's own frontmatter to grant write access in a background flow; the rules are different for plugin-shipped agents, and the failure mode is silent.

This is the finding I want to lead the "lessons learned" section with — it combines two subtleties into one extremely confusing user experience, and it's the kind of thing you only catch by actually deploying your plugin.

---

## Finding 4 — Orchestrators only work as main-thread agents

### What I learned

From the subagents docs:

> "This restriction only applies to agents running as the main thread with `claude --agent`. Subagents cannot spawn other subagents, so `Agent(agent_type)` has no effect in subagent definitions."

A subagent cannot recursively spawn more subagents. Claude Code enforces a one-level hierarchy: there's one "main thread" and it can fan out to subagents, but those subagents are leaves. If your orchestrator is auto-invoked by Claude from a regular session (for example, because the user typed a matching prompt and Claude picked the orchestrator as a handler), the orchestrator runs **as a subagent**, and its `Agent(...)` tool is inert.

### What this means for plugin design

The `dbt-pipeline-orchestrator` is designed to be invoked as:

```bash
cd <target-repo-with-csvs>
claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator "Build a pipeline"
```

This is the **only** way it can actually delegate. If a user tries to invoke it any other way — via auto-delegation, @mention, or `/agents` picker from inside an existing Claude session — it becomes a leaf subagent and cannot spawn the specialists.

This needs to be documented prominently in the plugin README, not buried in the agent body.

### Takeaway for the talk

> **Agent hierarchy is shallow.** A main-thread agent can spawn subagents, but subagents are leaves. Plan your orchestration topology around that constraint — and make invocation instructions unmissable.

---

## Finding 5 — `userConfig` env vars are namespaced for subprocesses (and installs don't always prompt)

### What I learned

Claude Code plugins declare install-time configuration through a `userConfig` block in `plugin.json`. Its stated purpose in the official docs:

> "The `userConfig` field declares values that Claude Code prompts the user for when the plugin is enabled. Use this instead of requiring users to hand-edit `settings.json`."

The intended flow: the user runs `/plugin install <plugin>@<marketplace>`, Claude Code parses `userConfig`, prompts interactively for each key (using the `description` as the prompt text), persists non-sensitive values to `settings.json` under `pluginConfigs[<plugin>].options`, and routes sensitive values to the system keychain. Stored values are then surfaced in two forms:

1. **Template substitution**: `${user_config.KEY}` in `mcpServers`, `lspServers`, hooks, and non-sensitive skill/agent content. This is how the MCP server block in `plugin.json` gets its env vars.
2. **Environment variables**: Claude Code exports **every** userConfig value to **every** plugin subprocess as `CLAUDE_PLUGIN_OPTION_<KEY>` (uppercased). These variables are set automatically — the plugin does not have to opt in to see them.

The critical detail: **the env var is `CLAUDE_PLUGIN_OPTION_<KEY>`, not the bare `<KEY>`.** The plugin's own code has to either read the prefixed name or remap it to the bare name it expects.

### How it broke — two problems, same root cause

**Problem A — the env var mismatch:**

The MCP server in this plugin works because `plugin.json` *explicitly* maps userConfig keys to bare env var names in its `mcpServers.sql-server-mcp.env` block:

```json
"env": {
  "SQL_SERVER": "${user_config.sql_server}",
  "SQL_DATABASE": "${user_config.sql_database}",
  ...
}
```

So the Node MCP server subprocess starts with `SQL_SERVER=localhost` etc. — exactly what its code reads via `process.env.SQL_SERVER`.

But the plugin's **Python skill scripts** are not inside the MCP server. They are separate subprocesses spawned by `Bash` tool calls when agents run the skills. Those subprocesses inherit the parent's environment, which includes every `CLAUDE_PLUGIN_OPTION_*` variable — but **no bare `SQL_*` variables**. Meanwhile the Python scripts read:

```python
os.environ.get('SQL_SERVER', 'localhost')
os.environ.get('SQL_DATABASE', '')
os.environ.get('SQL_USER', '')
# ...
```

So every SQL-aware skill (`sql-server-reader`, `sql-executor`, `data-profiler`, `dbt-project-initializer`) silently fell back to defaults — `localhost`, empty database, empty credentials. On a fresh install the MCP tools worked fine from Claude (because they live inside the Node server), which made users believe the connection was good. Then the orchestrator reached Stage 6 (`sql-executor` load) and the Python script tried to bulk-load CSVs against `localhost` with no database name. In background mode, the failure was invisible.

**Problem B — no prompt appeared during install or update:**

Separately, when the plugin was installed and then updated on a second machine, Claude Code **did not show any interactive prompt for the `userConfig` fields**. The plugin was enabled, the MCP server started, but the user was never asked for server, database, credentials. This is a second layer of confusion on top of Problem A: not only do the Python scripts fail to see the values, the user never got a chance to supply them in the first place.

Hypotheses (unverified — worth testing in isolation):

- The `userConfig` schema in `plugin.json` includes `title` and `type` fields that don't appear in the documented schema example (`description` and `sensitive` only). These might be silently ignored or might cause the prompt block to be skipped entirely.
- Every field's `description` says "Leave empty to..." — possibly that phrasing is being interpreted as "field is optional and can be skipped" by whatever logic decides which keys to prompt for.
- Update vs fresh-install behavior may differ: updates may not re-prompt at all, and if the initial install skipped the prompts for some reason, the update won't recover.
- The user's Claude Code version may have different `userConfig` prompt behavior — the feature may have been added or changed after this plugin was authored.

Either way, the failure mode is clear: **the plugin shipped with a userConfig block that was both not being prompted for AND not reachable by the Python scripts even if the user had filled it in manually.**

### Fix applied

The env var mismatch (Problem A) was fixed directly by adding a small helper function `_load_plugin_userconfig_env()` to every Python script that reads SQL connection environment variables. The helper runs at module load time, before `argparse` evaluates its defaults, and copies `CLAUDE_PLUGIN_OPTION_<KEY>` → `<KEY>` for every SQL env var name when the bare name is not already set:

```python
def _load_plugin_userconfig_env():
    keys = (
        'SQL_SERVER', 'SQL_DATABASE', 'SQL_AUTH_TYPE', 'SQL_USER', 'SQL_PASSWORD',
        'SQL_ENCRYPT', 'SQL_TRUST_CERT', 'SQL_DRIVER',
        'AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET',
    )
    for key in keys:
        if not os.environ.get(key):
            fallback = os.environ.get(f'CLAUDE_PLUGIN_OPTION_{key}')
            if fallback:
                os.environ[key] = fallback

_load_plugin_userconfig_env()
```

Applied to five files:
- `skills/sql-connection/scripts/connect.py` (shared connection helper)
- `skills/sql-server-reader/scripts/query_sql_server.py`
- `skills/data-profiler/scripts/profile_data.py`
- `skills/sql-executor/scripts/load_data.py`
- `skills/dbt-project-initializer/scripts/initialize_project.py`

The block is duplicated rather than shared because three of the consumer scripts import `connect.py` lazily (inside their `.connect()` methods), which runs *after* `argparse` has already evaluated its defaults from `os.environ.get(...)`. Putting the helper only in `connect.py` wouldn't fix the argparse defaults. The duplication is ugly, but it's five nearly-identical copies of a 15-line function — tolerable for a clear correctness win.

The no-prompt problem (Problem B) is **not yet fixed** and needs investigation:
- Strip `title` and `type` from the `userConfig` entries and see if a fresh install prompts correctly
- Test uninstall + reinstall versus update behavior
- If prompts still don't fire, add README documentation telling users to edit `settings.json` manually and list the exact key paths

### Takeaway for the talk

> **Plugin-declared config and plugin subprocess env vars are not the same thing.** Template substitution (`${user_config.KEY}`) works inside specific plugin manifest blocks. Subprocess environment variables come through as `CLAUDE_PLUGIN_OPTION_<KEY>`. If your plugin's own scripts expect bare names, you have to remap at the subprocess boundary.
>
> And: **the interactive prompt is not a guarantee.** Even with a well-formed `userConfig` block, the user may never see a prompt on install or update, for reasons that are currently unclear to me. Ship a README that documents how to set the config manually as a fallback.

This finding is the one I most want to lead with in the part of the talk about "deployment surface area is bigger than your code." It's two bugs stacked on top of each other, both invisible in dev, both silent at runtime, and the combination is what users will actually experience.

---

## Finding 6 — Development vs installed behavior diverges

A theme across all five preceding findings: **the plugin behaves differently when you're developing it vs. when it's installed from a marketplace**. During dev you can point Claude Code at the plugin directory with `--plugin-dir ./`, or drop the agents into `.claude/agents/`, and everything works under bare names with full `permissionMode` support. Install the same plugin on a fresh machine via the marketplace and half of your assumptions silently break.

Specific divergences I hit:

| Aspect | Dev (standalone `.claude/agents/`) | Installed (via marketplace) |
|---|---|---|
| Agent name | `business-analyst` | `dbt-pipeline-toolkit:business-analyst` |
| `permissionMode` frontmatter | Respected | Silently stripped |
| `hooks`, `mcpServers` on agents | Respected | Silently stripped |
| Orchestrator reach | "Just works" | Needs explicit main-thread invocation + namespaced names |

> **Test your plugin on a clean machine before calling it done.** Ideally on a machine that has never seen the repo — install from the marketplace, run the happy path, see what breaks. Dev-mode shortcuts hide the exact issues users will hit.

This is probably the biggest single takeaway for anyone building plugins for production use.

---

## Themes worth calling out in the talk

1. **Agentic pipelines need explicit permission contracts.** Foreground + background flows have fundamentally different permission semantics, and plugins strip some of the fields you'd naturally use to paper over the difference.
2. **Namespacing is a silent correctness issue.** Everything looks right in dev and breaks at install time with zero useful error output.
3. **Orchestrator topology is shallow on purpose.** You design around it or you ship something that can't delegate.
4. **Testing on a fresh install is non-optional.** Development shortcuts aren't representative of user experience.
5. **Plugin frontmatter is a security boundary.** Claude Code strips elevated-privilege fields from plugin-shipped agents. That's the right default, but you have to know which fields to route around.

---

## Fixes applied to this plugin

The findings above were addressed in two passes on the repo:

**Round 1 — agent delegation and permissions**

1. **Namespacing (Finding 1)** — `tools: Agent(...)`, every `subagent_type:` in the orchestrator, and every `claude --agent ...` invocation example now use the **3-part** name `dbt-pipeline-toolkit:<subdir>:<name>` (verified on a fresh install). An earlier attempt used the 2-part form from the docs example and was still broken.
2. **Permission mode at call site (Findings 2 + 3)** — every `Task(..., run_in_background: true)` spawn in the orchestrator now also passes `mode: "acceptEdits"`.
3. **Dead frontmatter removed (Finding 2)** — `permissionMode:` stripped from all five agent files (it was being silently ignored anyway).

**Round 2 — userConfig env var remap**

4. **Env var fallback helper (Finding 5)** — added `_load_plugin_userconfig_env()` to five Python scripts (`connect.py`, `query_sql_server.py`, `profile_data.py`, `load_data.py`, `initialize_project.py`). The helper runs at module load time, before `argparse` evaluates its defaults, and copies `CLAUDE_PLUGIN_OPTION_<KEY>` → `<KEY>` for every SQL connection variable.

Not yet fixed:

- **Finding 4** — needs README documentation spelling out that the orchestrator must be launched as the main thread via `claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator`.
- **Finding 5, Problem B** — the "no install-time prompt" mystery. Needs investigation into whether stripping `title` / `type` from the `userConfig` entries restores the prompt, and whether Claude Code version differences are involved.

Details of each fix — including line-level changes and regression-prevention rules — are tracked in `CLAUDE.md` under the "Lessons Learned" section.

---

## Open questions for future iteration

- Can the orchestrator detect at runtime whether it's running as a subagent (and fail fast with a useful error) instead of silently doing nothing?
- Should the plugin ship a `settings.json` with a `subagentStatusLine` that makes background agent progress visible to the user? That would at least help diagnose stalled workers.
- Is there a way to validate plugin frontmatter offline — catching a stray `permissionMode` before it ships?
- How should the README document the invocation command so users can't miss it? A big fence at the top? A `/plugin install` post-install hook that prints usage?
- **Why did `userConfig` not prompt the user on install or update?** Is it the undocumented `title` / `type` fields in each entry, the "Leave empty to..." phrasing in the descriptions, a Claude Code version difference, or something else? Needs a minimal-reproduction test.
- Would it be worth adding a `SessionStart` hook that detects missing SQL connection env vars and prints a clear setup message, as a safety net in case the prompt never fires?
- Should `connect.py` become a proper plugin-internal library instead of living under `skills/sql-connection/` without a `SKILL.md`? Right now it's in skill-land but isn't actually a skill.

Worth a live demo slide in the talk: show the "broken" behavior (orchestrator stalls or Python scripts connect to `localhost` with no database), then the fix, then the working run, side-by-side.
