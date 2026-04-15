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

## Finding 2 — Plugin-shipped agents cannot declare `permissionMode`, `hooks`, or `mcpServers` in their frontmatter — but the plugin itself can

### What I learned

From the Claude Code plugins reference, under "Agents":

> "Plugin agents support `name`, `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `skills`, `memory`, `background`, and `isolation` frontmatter fields. **For security reasons, `hooks`, `mcpServers`, and `permissionMode` are not supported for plugin-shipped agents.**"

The crucial qualifier in that sentence is **"for plugin-shipped agents."** The restriction applies only to fields declared inside an agent's own `agent.md` YAML frontmatter — not to fields declared at the plugin level in `plugin.json`. This distinction is easy to miss on first read, and it confused me early in the build until I noticed the plugin already had a working PreToolUse hook and a working MCP server — both shipped at plugin level, both unaffected by this restriction.

The two scopes:

| Scope | Location | `hooks` | `mcpServers` | `permissionMode` |
|---|---|---|---|---|
| **Plugin level** | `plugin.json` `hooks` block, `mcpServers` block, `settings.json` | ✅ Supported | ✅ Supported | (not a field) |
| **Agent level** | Inside `agents/<name>/agent.md` YAML frontmatter | ❌ Stripped at load | ❌ Stripped at load | ❌ Stripped at load |

**Why the asymmetry is a deliberate security boundary.** A plugin-level hook or MCP server is declared in `plugin.json`, which users can inspect at install time and audit before enabling the plugin. The plugin manifest is the plugin's public contract — it's visible in the marketplace, greppable in the source repo, and surfaced in `/plugin` inspection commands. In contrast, agents are spawned dynamically during sessions, so letting each agent attach its own hooks and MCP servers at spawn time would move privilege-granting into an unaudited surface. Stripping those fields from agent frontmatter forces all plugin-level privilege declarations back into `plugin.json`, where they can be reviewed before the user enables the plugin.

The same reasoning applies to `permissionMode` on agents. Letting a plugin-shipped agent silently upgrade itself to `acceptEdits` or `bypassPermissions` at spawn time would be a privilege escalation without user awareness. So `permissionMode` on an agent is stripped, and permission control must come from the call site (the parent agent passing `mode: "acceptEdits"` at Task invocation) or from session-wide settings.

### Evidence in this plugin

The existing `plugin.json` already demonstrates both supported paths:

```json
{
  "mcpServers": {
    "sql-server-mcp": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/servers/dist/minimal-mcp-server.js"],
      "env": { ... }
    }
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/validate-dbt-structure.py"
          }
        ]
      }
    ],
    "WorktreeCreate": [...],
    "WorktreeRemove": [...]
  }
}
```

The plugin ships **1 MCP server and 3 hook event registrations** at plugin level, and they all load and fire normally. The restriction never applied to them.

### How it broke

Four of the builder agents (`dbt-staging-builder`, `dbt-dimension-builder`, `dbt-fact-builder`, `dbt-test-writer`) plus the orchestrator all had `permissionMode: acceptEdits` in their frontmatter. During development outside the plugin context (via standalone `.claude/agents/` or `--plugin-dir ./`) this made the agents fully autonomous — they could `Write` and `Edit` files without prompting. When installed as a plugin, that line was silently dropped. The agents still ran, but any `Write`/`Edit` call triggered a permission prompt, and in background-spawned subagents the prompt went nowhere and the tool call stalled.

The fix was to remove the dead `permissionMode:` lines from all five agent files and add `mode: "acceptEdits"` at the **call site** in the orchestrator's Task spawn calls instead — the call-site form is the supported equivalent, and it's not stripped because it's declared by the parent agent at spawn time rather than baked into the child's frontmatter.

### One more thing the restriction does NOT block

Since the restriction is agent-frontmatter-only, **the plugin CAN ship additional `PreToolUse` hooks at plugin level** to extend permission evaluation for tools that would otherwise block background subagents. This is the basis for Finding 9 — the plugin now adds a plugin-level PreToolUse hook that auto-approves Bash calls matching specific plugin-internal script patterns, so background subagents can run `python profile_data.py` and `dbt run ...` without getting blocked by permission prompts. This is fully within the security boundary: the hook is visible in `plugin.json`, its allowlist is visible in `hooks/approve-plugin-bash.py`, and the auditable surface is all at install time.

### Takeaway for the talk

> **"Not supported for plugin-shipped agents" means "not supported in agent frontmatter," not "not supported anywhere in the plugin."** Plugin-level `hooks`, `mcpServers`, and auditable permission rules in `plugin.json` are fully available. The restriction is a security boundary that forces privilege declarations into the user-auditable surface (the plugin manifest), not a limitation on what plugins can do overall.
>
> Getting this distinction right matters because it unblocks a whole category of capabilities — like the auto-approval hook pattern in Finding 9 — that would otherwise look impossible. Read the docs twice when they say "X is not supported for plugins": the scope of "for plugins" is often narrower than it sounds.

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
claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator "Build a pipeline"
```

This is the **only** way it can actually delegate. If a user tries to invoke it any other way — via auto-delegation, @mention, or `/agents` picker from inside an existing Claude session — it becomes a leaf subagent and cannot spawn the specialists.

This needs to be documented prominently in the plugin README, not buried in the agent body.

> **Note added later:** After writing this finding, a research pass turned up GitHub issues claiming that even a main-thread `--agent` invocation does not receive the `Task`/`Agent` tool and cannot spawn anything (Issues #19077, #23506, #19276). The research's conclusion was that the path documented above cannot possibly work. **We then tested it on a fresh install and it did work** — so the documented path in this finding is empirically correct, but it's contradicted by the GitHub issue tracker and by an Anthropic-closed "Not Planned" feature request. See Finding 6 for the full reversal and `_Research/plugin-subagent-delegation.md` for the issue links. The implication: this path works today but is not officially supported and could regress.

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

## Finding 6 — The feature is "Not Planned" according to GitHub issues, but it actually works

### What I learned

After we finally got the 3-part namespacing right, the orchestrator still wasn't reliably spawning subagents on the first fresh install attempt. I commissioned a research pass to find out whether plugin-to-plugin subagent delegation is even a supported feature — searching GitHub issues, community forums, the Claude Code documentation, and looking for any public plugin with working multi-agent orchestration via `Task`/`Agent`.

The research came back with unambiguously bad news. Multiple tracked issues on `anthropics/claude-code` pointed at the same architectural wall:

- **[Issue #19077](https://github.com/anthropics/claude-code/issues/19077)** (OPEN) quoted the official sub-agents docs verbatim: *"Subagents cannot spawn other subagents."* And added: "Custom agent as main (via `--agent`) → No `Task()` tool. Worker subagents → No `Task()` tool."
- **[Issue #23506](https://github.com/anthropics/claude-code/issues/23506)** reported directly: *"When running Claude Code with a custom agent (`claude --agent daily`), … the Task tool (subagent spawner) is not present in the session."*
- **[Issue #19276](https://github.com/anthropics/claude-code/issues/19276)** — the explicit feature request to "make custom / plugin agents callable via `Task`" — was **closed as "Not Planned" on 2026-02-27**, meaning Anthropic was asked for this capability and declined it.
- **[Issue #13605](https://github.com/anthropics/claude-code/issues/13605)** showed plugin-shipped agents don't even receive their declared MCP tools, suggesting plugin agents are treated more restrictively than built-in ones across the board.
- **[Issue #13627](https://github.com/anthropics/claude-code/issues/13627)** reported that even when a custom agent *is* spawned via `Task`, its markdown body content is silently dropped — so even if delegation worked, the specialist system prompts wouldn't be injected.
- No public plugin the research agent could find anywhere on GitHub successfully uses `Task`-based intra-plugin orchestration. Every multi-agent plugin it surveyed (77-plugin `wshobson/agents`, `barkain/claude-code-workflow-orchestration`, `baryhuang/claude-code-by-agents`) works around the limitation with `@mention`s, slash commands, or an external coordinator.

The conclusion the research agent drew from all of this was pretty flat: **"The namespace format is a red herring — you could get it perfectly right and it would still fail."**

Full report with direct quotes and URLs lives at `_Research/plugin-subagent-delegation.md`.

### How it broke (or didn't)

After absorbing the research, I was ready to rewrite the entire plugin to either (a) convert the orchestrator into a Skill, (b) spawn `general-purpose` with injected role prompts, or (c) abandon the orchestrator pattern entirely and turn each stage into a slash command.

Then the user tested the current 3-part-name orchestrator on a fresh install, invoked it as:

```bash
claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator "Build a pipeline"
```

…and it **worked**. The orchestrator spawned subagents. Multiple, successfully. The exact thing the research said could never happen happened on the first attempt.

So one of several things is true, and we don't fully know which:

- The behavior changed in a Claude Code release after the issues were filed. Anthropic may have quietly added plugin-agent resolution to the `Task` tool without updating the issue threads or the docs, and without reopening the "Not Planned" feature request.
- The resolver discovers plugin-installed agents (`~/.claude/plugins/<plugin>/agents/<subdir>/agent.md`) differently from `.claude/agents/*.md` or `subagents.json`, and the GitHub issues were only true about the latter.
- The `--agent` invocation path behaves differently for namespaced 3-part plugin agents than it does for bare-name local agents, and the bug reports in #23506 all used the bare-name variant.
- The feature works partially — maybe delegation resolves, but per #13627 the specialist's body content is silently dropped at spawn time, so while we see subagents getting created, they're behaving like `general-purpose` workers with only the orchestrator's short `prompt:` string as context.

We haven't empirically verified which of those is true. The orchestrator appeared to work, but we haven't yet confirmed that the specialist agents actually received their own body content at spawn time (the bug in #13627). A simple test — ask a spawned specialist "what role are you specialized in?" and see whether it answers from its own agent.md body or gives a generic response — would tell us whether #13627 is still in effect.

### Takeaway for the talk

This is the finding I most want to talk about, because it inverts the usual advice.

> **Don't let documentation, GitHub issues, or even a "Not Planned" feature request decide what you can ship.** The docs for Claude Code plugins are incomplete. The GitHub issues are out of date. The community workarounds are based on the bugs people hit before the platform quietly moved on. The only source of truth is a fresh install running your actual plugin.
>
> **But also: don't declare victory on a one-attempt fresh-install test.** "Not Planned" features have a habit of getting un-planned quietly and then re-breaking in later releases. If you ship a plugin that depends on a feature Anthropic has explicitly declined to support, you need a smoke test in CI and a documented fallback architecture (probably the skill-orchestrator path from the research report) that you can flip to when the platform breaks out from under you.

The arc of this finding — "the docs say 2 parts, the docs are wrong, 3 parts works, except nothing works, except actually everything works, except we don't know if it'll stay that way" — is the single best story in the deck for illustrating how fragile the dev-vs-installed-vs-documented triangle is.

### Open follow-ups from this finding

- **Empirically test Issue #13627's body-content-dropped claim.** Add a spawn probe that asks a specialist to identify itself.
- **Empirically test Issue #13605's MCP-tool-stripped claim.** Have a specialist call an `sql-server-mcp:*` tool and see if it resolves.
- **Document the fallback architecture in `_Research/plugin-subagent-delegation.md`.** If the delegation path regresses in a future Claude Code release, the conversion to a skill-orchestrator plus `general-purpose` fanout should be pre-planned, not panic-designed.
- **Consider filing a doc-update suggestion** against the Claude Code docs to clarify that the 3-part format exists and that plugin-agent delegation via `Task` is operational for plugins installed under `~/.claude/plugins/`, even though the feature request is closed "Not Planned."

---

## Finding 7 — Plugin-internal script paths must use `${CLAUDE_PLUGIN_ROOT}`, not `$HOME/.claude/skills/`

### What I learned

Plugins bundled skills and agents typically call Python scripts inside the plugin for the heavy lifting — `profile_data.py`, `query_sql_server.py`, `load_data.py`, `dbt_runner.py`, etc. The natural way to write those invocations, during early development, is to use whatever path the script lives at on your own machine:

```bash
python "$HOME/.claude/skills/data-profiler/scripts/profile_data.py" --file ...
```

That works fine on your dev machine if you've also symlinked or copied the skill into `~/.claude/skills/` as a standalone skill (which is a common dev workflow — you start with a standalone skill, then package it into a plugin later). It keeps working after you package the skill into a plugin as long as you also keep the standalone copy around. And it keeps working if you test the plugin with `--plugin-dir ./` because even in that mode, the standalone copy in `~/.claude/skills/` is still there.

**None of that applies on a fresh install.** When a user installs the plugin from a marketplace, Claude Code copies the plugin to its cache directory:

```
~/.claude/plugins/cache/<id>/skills/data-profiler/scripts/profile_data.py
```

The path `$HOME/.claude/skills/data-profiler/scripts/profile_data.py` **does not exist** on a fresh install unless the user happens to also have a standalone copy. For a brand new user installing from the marketplace, every `python "$HOME/.claude/skills/..."` command silently fails with "file not found" — and in background-spawned subagents, that error is invisible to the orchestrator.

The official convention for referencing plugin-internal resources is the environment variable `${CLAUDE_PLUGIN_ROOT}`, documented in the Claude Code plugins reference:

> "`${CLAUDE_PLUGIN_ROOT}`: the absolute path to your plugin's installation directory. Use this to reference scripts, binaries, and config files bundled with the plugin."
>
> "Both are substituted inline anywhere they appear in skill content, agent content, hook commands, and MCP or LSP server configs."

So script invocations in `agent.md` and `SKILL.md` should be written as:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/data-profiler/scripts/profile_data.py" --file ...
```

Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` at load time with the real absolute path — which in dev mode (`--plugin-dir ./`) resolves to the repo root, and in install mode resolves to the plugin cache directory. The same markdown source works in both contexts.

### How it broke

The data-profiler symptom was exactly what you'd predict if you understood this gap — but we only understood it after working backward from a very confusing observation.

On a fresh install, the user reported: *"The data profiler has not created the profile document. It seems it has been called."* That is, the orchestrator spawned the `data-explorer` subagent (which is responsible for profiling CSVs and producing the `1 - Documentation/data-profiles/profile_*.json` files that later stages depend on). The agent completed without error, but no profile files were created, and the orchestrator stalled at Stage 3 (drafting the data model) because it had no source inventory to work from.

Working backward from the symptom, I traced through `agents/data-explorer/agent.md` and found it calling the profiler via:

```bash
python "$HOME/.claude/skills/data-profiler/scripts/profile_data.py" --table ...
```

And that path, on a fresh install, points nowhere. The Bash tool runs the command, Python exits with "No such file or directory", and because the agent runs in background mode, the error never surfaces to the orchestrator. The agent thinks its job is done (no exception propagated, no explicit failure signal), and returns an empty summary.

Worse: this was **not a data-explorer-specific problem**. A grep across the whole plugin surfaced the same broken path in **11 files with 183 total occurrences**. Every agent body and every SKILL.md usage example — `agents/dbt-architecture-setup`, `agents/dbt-staging-builder`, `agents/dbt-pipeline-orchestrator`, `skills/dbt-runner`, `skills/sql-executor`, `skills/sql-server-reader`, and six more — all used `$HOME/.claude/skills/<name>/scripts/<file>.py`. The entire plugin was broken on a fresh install, not just the profiler. The profiler was simply the first place the orchestrator touched where the failure was visible.

A second, smaller issue rode along with it: about 162 of the 183 paths used **Windows-cmd backslashes** inside the script segment — `\scripts\profile_data.py` instead of `/scripts/profile_data.py`. In Git Bash (which is this project's documented shell), backslashes get interpreted as escape characters in double-quoted strings, so even if the base path had been correct, the backslash-separated paths would have been broken in a subtle, shell-specific way. Mostly this was a latent bug that hadn't fired because we're on Windows and Python accepts either slash style — but it's a pure correctness bug that had to go.

### Fix applied

A two-pass mechanical replacement across all 11 files:

1. **Replace `$HOME/.claude/skills/` with `${CLAUDE_PLUGIN_ROOT}/skills/`** — 183 occurrences across 11 files, one `replace_all` Edit per file.
2. **Normalize backslashes**: replace `\scripts\` with `/scripts/` — 162 occurrences across 8 SKILL.md files (no agent.md files used backslashes).

Final count: **187** occurrences of `${CLAUDE_PLUGIN_ROOT}/skills/<name>/scripts/<file>.py` across 11 plugin files, zero occurrences of the old pattern or backslash variant.

This fix is intentionally narrow — it only touches the script-invocation paths, not the Python scripts themselves (which don't need changes because they run in whatever directory `${CLAUDE_PLUGIN_ROOT}` resolves to). The env-var remap from Finding 5 is still the mechanism that gives those scripts their SQL connection configuration.

### Confidence caveat

We went into this fix with roughly 90% confidence that `${CLAUDE_PLUGIN_ROOT}` gets substituted inline in agent/skill markdown body text. That confidence was based on:

- The plugins-reference doc saying "substituted inline anywhere they appear in skill content, agent content, hook commands, and MCP or LSP server configs"
- The plugin's own `plugin.json` already using `${CLAUDE_PLUGIN_ROOT}` successfully for the MCP server script path
- No counter-evidence in any GitHub issue the research agent surfaced

The remaining 10% uncertainty is: **if this substitution only works in `plugin.json` and hook/MCP configs but NOT in markdown body content**, then the LLM will see the literal string `${CLAUDE_PLUGIN_ROOT}` in its prompt and will either (a) pass it through unchanged to Bash (which also won't have it set as an env var, since bash-tool subprocesses aren't explicitly listed as receiving it), or (b) treat it as a bad variable and the resulting command will fail. We'll only know which on the next fresh-install test. If this happens, the fallback is to add a `SessionStart` hook that exports `PLUGIN_ROOT` to the shell environment, or to encode the relative path differently.

### Takeaway for the talk

> **Your plugin's dev-mode convenience is its install-mode bug.** The pattern `$HOME/.claude/skills/foo/...` works in dev because you have a standalone copy of the skill in that location. On a fresh marketplace install, that path doesn't exist — the skill lives in the plugin cache, not in the standalone directory. Every time you write a script invocation in an agent or skill body, ask yourself: "does this path use `${CLAUDE_PLUGIN_ROOT}`?" If it doesn't, your plugin will appear to call the script on install but the script will never run. And in background mode, you'll never see an error.

This is the quietest failure mode of the entire build: the orchestrator ran, the subagents ran, nothing errored, nothing was produced. It looks like success until you notice that the output files aren't there. It's a good warning for anyone writing multi-step plugin pipelines: **verify side effects, not just exit codes**.

### Open follow-ups

- **Verify the substitution actually works on a fresh install** — the next run should produce profile JSON files in `1 - Documentation/data-profiles/`. If it doesn't, the `${CLAUDE_PLUGIN_ROOT}` path isn't being substituted in agent body and we need a fallback.
- **Audit any other plugin files that might use dev-style paths** — this was the first grep pass for `$HOME/.claude/skills/`, but there could be similar patterns like `$HOME/.claude/plugins/...` or `$HOME/.claude/hooks/...` lurking elsewhere.
- **Update the `dbt-runner` skill to document `${CLAUDE_PLUGIN_ROOT}` usage in its README** so future skills added to this plugin don't regress.
- **Consider adding a pre-commit or CI check** that greps for `$HOME/.claude/skills/` in any `*.md` file under `agents/` or `skills/` and fails if found — this is exactly the kind of bug that mechanical verification catches for free.

---

## Finding 8 — Plugin skills and agents use different namespace formats (2-part vs 3-part), and plugin skills appear as "locked"

### What I learned

After confirming that plugin agents are registered with **three** namespace segments (`<plugin>:<subdir>:<frontmatter-name>` — see Finding 1), I assumed plugin skills would follow the same pattern. They don't. Plugin skills use **exactly two** segments:

```
dbt-pipeline-toolkit:data-profiler
     ^                    ^
plugin name         skill directory name
```

That's it. No duplication. No frontmatter `name` segment. The skills docs say it plainly:

> "Plugin skills use a `plugin-name:skill-name` namespace, so they cannot conflict with other levels."

Why the asymmetry?

- **Skills are flat single-directory units.** A skill lives at `skills/<name>/SKILL.md`, and the `<name>` directory is always the skill's identifier. There's no intermediate level where a subdirectory could become a separate namespace segment — the directory *is* the skill.
- **Agents in this plugin live in subdirectories** (`agents/<name>/agent.md`), and Claude Code uses the subdirectory as a distinct namespace level above the frontmatter `name` field. If the plugin used flat `agents/<name>.md` files (the layout shown in the official docs example), agents would also be 2-part. The 3-part form is a consequence of this plugin's directory-based agent layout.

So the rule is really: **the number of namespace segments equals the depth of the file relative to `agents/` or `skills/`**, plus one for the plugin name. Flat skill files under `skills/<name>/SKILL.md` give 2 segments. Nested agent files under `agents/<name>/agent.md` give 3 segments. If you nested skills like `skills/<category>/<skill>/SKILL.md`, you'd probably get 3-segment skill names too (untested, but consistent with the pattern).

### "Locked by plugin" — what the UI label means

The user also noticed that plugin skills show up in the Claude Code UI marked as **"locked by plugin."** The skills docs don't use that exact phrase, but the meaning is inferable from how plugins work:

1. **The skill is owned by the plugin system.** It lives in the plugin cache (`~/.claude/plugins/cache/<id>/skills/<name>/`) rather than in the user's `~/.claude/skills/` directory.
2. **The user cannot edit it in place.** The plugin cache is managed by Claude Code — specifically, any version of a plugin that is replaced by an update is marked orphaned and removed automatically 7 days later. Local edits would be overwritten the next time the plugin updates.
3. **Its lifecycle is tied to the plugin's lifecycle.** Installing the plugin adds the skill; uninstalling removes it; `claude plugin update` replaces it with the new version from the marketplace.
4. **It cannot be overridden by a same-name personal or project skill**, because plugin skills live in their own `plugin-name:skill-name` namespace. Your personal `~/.claude/skills/data-profiler/SKILL.md` and the plugin's `dbt-pipeline-toolkit:data-profiler` coexist without conflict.
5. **The canonical way to customize a plugin skill is to fork the plugin**, not to hand-edit the cached version. This is the same pattern that package managers use — you don't edit files inside `node_modules/` or `site-packages/`, you override at a higher level or fork upstream.

"Locked" is essentially the plugin system's way of saying "this is managed code, not your sandbox." Which is the right default for anything shipping through a distribution mechanism.

### How it broke

The `skills:` frontmatter field in every agent declaration looked like this:

```yaml
skills: dbt-runner, data-profiler, sql-server-reader
```

The `skills:` field in an agent's frontmatter is the "preload skills into subagents" mechanism — at spawn time, Claude Code loads the named skills' content into the subagent's context so the subagent can use them without re-loading per call. When the agent is plugin-shipped, the bare names (`dbt-runner`, `data-profiler`, `sql-server-reader`) don't match any registered skill — Claude Code resolves them against the same plugin-name:skill-name namespace used by the picker, and bare names resolve to nothing. The preload silently produces an empty skill list, and the specialist agent starts without any of the skill context it was designed around.

This is a quieter version of the same class of bug as the earlier agent-namespace issue (Finding 1) and the script-path issue (Finding 7): the agent reference resolves against a different namespace than the one the author had in mind, the resolution fails silently, and the agent runs with degraded capability instead of failing loudly.

What we don't know — and this needs empirical verification — is whether the `skills:` preload was actually contributing anything the specialist agents needed at runtime, or whether the specialists were functioning with their own agent.md body content as the only source of instruction. Possibly the "dbt-staging-builder works fine without its skills preloaded" theory is true, in which case fixing this issue is a correctness improvement without a visible behavior change. Possibly the theory is false, and the specialists have been subtly under-equipped across the entire test. We haven't disentangled the two, because the plugin has been failing on so many other axes that it's hard to isolate which fix unlocked which capability.

### Fix applied

Every `skills:` field in all 8 plugin agent files rewritten to use the 2-part namespace:

```yaml
# Before
skills: dbt-runner, data-profiler, sql-server-reader

# After
skills: dbt-pipeline-toolkit:dbt-runner, dbt-pipeline-toolkit:data-profiler, dbt-pipeline-toolkit:sql-server-reader
```

Files updated:
- `agents/data-explorer/agent.md`
- `agents/business-analyst/agent.md`
- `agents/dbt-architecture-setup/agent.md`
- `agents/dbt-staging-builder/agent.md`
- `agents/dbt-dimension-builder/agent.md`
- `agents/dbt-fact-builder/agent.md`
- `agents/dbt-test-writer/agent.md`
- `agents/dbt-pipeline-validator/agent.md`

### Takeaway for the talk

> **Namespacing is not uniform across Claude Code plugin concepts.** Skills are 2-part (`plugin:skill`) because skills are flat. Agents *in this plugin* are 3-part (`plugin:subdir:name`) because agents live in subdirectories. If the plugin used flat `agents/<name>.md`, agents would also be 2-part. There's no single "plugin namespacing rule" to memorize — there's a rule about **directory depth translating to namespace segments**, and skills just happen to always have depth 1.
>
> The implication for talk audiences is: **every time you reference something from a plugin — an agent, a skill, a command, a hook, a script path — ask yourself what the exact registered name looks like on a fresh install.** Do not assume. Verify in the picker, verify in `/skills`, verify in the command list. The rules are context-dependent and the docs are incomplete.

### Plus: the "locked by plugin" lesson for the talk

This is worth a quick aside in the part of the talk about plugin ergonomics. "Locked by plugin" is a good thing — it's the plugin system protecting the plugin author's contract. But it also means **users cannot patch around your bugs locally.** If your plugin ships broken on a fresh install, users don't have an escape hatch to fix it in place. They have to uninstall, fork, or wait for an update.

That raises the bar for plugin release quality. Every plugin release should be treated like a production deploy, not a dev push — because that's exactly what it is from the user's perspective. Worth emphasizing in the talk: **plugin skills are not your sandbox; they are shipped artifacts**, and you should test them with that frame of mind.

### Future optimization worth considering

The skills docs mention a skill-scoped variable `${CLAUDE_SKILL_DIR}`:

> "The directory containing the skill's `SKILL.md` file. For plugin skills, this is the skill's subdirectory within the plugin, not the plugin root. Use this in bash injection commands to reference scripts or files bundled with the skill, regardless of the current working directory."

This is more idiomatic than `${CLAUDE_PLUGIN_ROOT}/skills/<name>/` inside a SKILL.md, because it doesn't hardcode the skill's own name inside its own instructions. The script-path fix from Finding 7 could be refined further in SKILL.md files to use `${CLAUDE_SKILL_DIR}/scripts/<file>.py` — but only inside SKILL.md. Agent bodies still need `${CLAUDE_PLUGIN_ROOT}/skills/<skill-name>/scripts/<file>.py` because `${CLAUDE_SKILL_DIR}` isn't available in agent content (it's scoped to the currently-active skill, which is an inapplicable concept for an agent definition).

Not a correctness issue — the current form works. Just a cleanliness improvement for a later pass.

---

## Finding 9 — Background subagents cannot run arbitrary Bash without a plugin-level PreToolUse approval hook

### What I learned

`acceptEdits` permission mode is more limited than its name suggests — and that limit directly blocks every Python-script call inside a background subagent until you work around it at the plugin level. This finding is the direct continuation of Finding 3 (background agents cannot satisfy permission prompts), refined with the specific mechanism that actually solves it.

Here is what `acceptEdits` really does, per the Claude Code permissions reference:

> "`acceptEdits`: Automatically accepts file edits and **common filesystem commands (`mkdir`, `touch`, `mv`, `cp`, etc.)** for paths in the working directory or `additionalDirectories`"

So `acceptEdits` does unlock a narrow slice of Bash — filesystem shuffling commands like `mkdir`, `touch`, `mv`, `cp`, plus the expected `Write`/`Edit` file-modification tools. But **arbitrary Bash like `python profile_data.py` or `dbt run` is still subject to the normal permission flow**, which in a background subagent means "stalls silently waiting for a prompt that will never come."

I had been treating `acceptEdits` as "background agents can do everything" when it's really "background agents can do filesystem moves and file writes." The gap between those two is exactly where every Python invocation and every `dbt` call lives in this plugin's workflow — Stages 2, 6, 7, 8, 9, 10, 11, all of them. The net effect was: the namespacing was right, the permission mode was right for its stated purpose, the script paths were right, the env vars were right, and the plugin still couldn't actually run the data-profiler because Bash was blocked upstream of all of that.

### How it broke (and kept breaking)

Concretely, on a fresh install the user saw the orchestrator successfully spawn the data-explorer subagent, the subagent successfully find the CSV files, and then… produce no profile outputs. When we investigated, the data-explorer agent's own self-report was:

> "I'm unable to execute Bash commands."

It tried to run `python profile_data.py --file customers.csv`, the permission layer wanted to prompt, the background subagent had no channel for the prompt, and the Bash call was silently refused. The agent fell back to reading the CSV file contents with its Read tool — which gave it some of the information, but none of the primary-key detection, type inference, or test recommendations that the profiler script was designed to produce. The "profile" it returned was missing everything the downstream stages actually needed.

This was not a one-off. The same limitation would have affected:

| Stage | Subagent | Blocked command |
|---|---|---|
| 2 | data-explorer | `python profile_data.py` |
| 7 | dbt-staging-builder | `dbt parse`, `dbt run --select stg_*` |
| 8 | dbt-dimension-builder | `dbt run --select dim_*` (per worktree) |
| 9 | dbt-fact-builder | `dbt run --select fct_*` (per worktree) |
| 10 | dbt-test-writer | `dbt test --select <model>` |
| 11 | dbt-pipeline-validator | `dbt build --full-refresh` |

Every stage after the plan approval would have stalled in the same way, producing silent partial failures that look like "the orchestrator is working" until you notice nothing actually ran.

### Fix applied — plugin-level PreToolUse auto-approval hook

From the Claude Code permissions docs:

> "Claude Code hooks provide a way to register custom shell commands to perform permission evaluation at runtime. When Claude Code makes a tool call, **PreToolUse hooks run before the permission prompt. The hook output can deny the tool call, force a prompt, or skip the prompt to let the call proceed.**"

PreToolUse hooks can auto-approve a tool call. The hook contract is an exit-code-0 JSON emit on stdout:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "<human-readable explanation>"
  }
}
```

When a PreToolUse hook returns `permissionDecision: "allow"`, the permission prompt is skipped entirely — which is exactly what we need for background subagents. And crucially, per Finding 2, **plugin-level hooks are fully supported**: it's only agent-frontmatter hooks that are stripped. So a plugin can ship a PreToolUse hook at the plugin level, register it in `plugin.json`, and have it fire for every Bash tool call across every subagent in every session where the plugin is enabled.

The fix we applied:

1. **Created `hooks/approve-plugin-bash.py`** — a Python hook script that reads the PreToolUse JSON from stdin, inspects the Bash command, and auto-approves calls matching a narrow allowlist: plugin-internal Python scripts (`python "${CLAUDE_PLUGIN_ROOT}/skills/*/scripts/*.py" ...`), `dbt` CLI commands (`dbt run/test/build/parse/debug/seed/snapshot/compile/deps/list`), `git` commands used by scaffolding and worktree isolation, filesystem discovery (`find -name "*.csv"`, `ls`), and virtualenv/pip operations used by the initializer. Any Bash command not on the allowlist falls through to the default permission flow — the hook does not broadly unlock the shell.

2. **Registered the hook in `plugin.json`** alongside the existing `validate-dbt-structure.py` hook, with matcher `Bash`:

   ```json
   "PreToolUse": [
     {
       "matcher": "Write|Edit",
       "hooks": [
         { "type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/validate-dbt-structure.py" }
       ]
     },
     {
       "matcher": "Bash",
       "hooks": [
         { "type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/approve-plugin-bash.py" }
       ]
     }
   ]
   ```

3. **Updated the orchestrator's Stage 2 prompt** to include the explicit script path (`python "${CLAUDE_PLUGIN_ROOT}/skills/data-profiler/scripts/profile_data.py" --file <csv-path> --format json`), as defense-in-depth against Issue #13627 (the "agent body content silently dropped at spawn time" concern from Finding 6 research). Even if the data-explorer's own body content isn't reaching the spawned subagent, the orchestrator's prompt alone now contains enough for the subagent to know what to run.

The hook is narrow, auditable (all patterns live in one Python file, greppable at install time), and scoped only to Bash commands the plugin actually needs. Everything else still flows through the normal Claude Code permission layer, so a user running this plugin doesn't lose control over arbitrary Bash — they only auto-approve the things the plugin authored.

### Why this is the right architecture vs. the alternatives

I considered four paths before settling on this one:

1. **`bypassPermissions` mode at the call site** — works, but auto-unlocks *all* Bash for every spawned subagent. Way too broad, violates the user's global rule against `bypassPermissions` in background contexts, and makes the plugin's security surface effectively "everything."
2. **`dontAsk` mode + user-added `permissions.allow` rules** — works, but requires every user to hand-edit their `settings.json` to add `Bash(python *)` allowances before running the plugin. Install-step footgun and bad UX.
3. **Skill `allowed-tools: Bash(python *)`** — officially this pre-approves Bash for the listed patterns while the skill is active, but the contract for "active" when a skill is preloaded into a subagent via the agent's `skills:` frontmatter (vs. invoked directly) is unclear in the docs. Would have been a one-line fix if it worked, and 0% confidence that it would.
4. **PreToolUse hook at plugin level** — the chosen path. Known-to-work per the docs, zero user setup, narrow allowlist auditable in one file, plugin-shipped so it benefits every install automatically.

The hook approach wins on every axis except simplicity — it's more code than Option 3 would have been — but it's the only one that ships as a standalone self-contained fix with a clear security contract.

### Confidence caveat

Two things I want to verify empirically on the next fresh-install run:

1. **The PreToolUse hook actually fires for Bash calls in background subagents.** The docs say it does, but I haven't tested. If the permission layer processes background subagent Bash calls in a different code path that doesn't invoke the PreToolUse hook chain, this fix doesn't help.
2. **The `permissionDecision: "allow"` response actually skips the permission prompt rather than just being a hint that gets overruled by the background-mode check.** Per the docs it's an "allow" decision that bypasses the prompt, but the interaction with background-subagent-mode-specific prompt-suppression is not documented.

If either of those turns out not to work, the fallback options are: (a) switch to `bypassPermissions` mode for specific stages as a last resort, or (b) move all Bash calls to the orchestrator main thread (the Option B from the earlier analysis). The fallbacks aren't great but they exist.

### Takeaway for the talk

> **Permission mode names are marketing, not specification.** `acceptEdits` doesn't accept all edits — it accepts file edits and filesystem Bash. `bypassPermissions` doesn't bypass all permissions — it still prompts for writes to `.git` and a few other protected paths. The actual semantics of each mode are documented, but the names are cleaner than the docs. Read the docs, not the names.
>
> **Background subagents live inside an inherently-limited permission context.** There is no mode flag or spawn parameter that makes a background subagent behave like a foreground main thread. The only escape hatch is a PreToolUse hook at plugin level, and it only works for tool calls whose permission flow goes through the hook chain. Build your plugin architecture assuming background subagents can WRITE files, READ files, and RUN filesystem Bash — and nothing else — unless you ship a hook to extend their reach.
>
> **Security boundaries are asymmetric and worth mapping.** Agent frontmatter can't declare hooks (Finding 2). But plugin-level `plugin.json` CAN declare hooks, and those hooks can auto-approve Bash calls that agent-level mechanisms couldn't authorize. The asymmetry is deliberate: it puts privilege declarations in the user-auditable surface (the plugin manifest) instead of in runtime-only agent metadata. Understanding where the boundary is lets you build capabilities that initially look forbidden.

This is the finding that most deserves a live-demo slide in the talk. Show the broken behavior ("data-explorer runs, claims to profile, produces nothing"), then the hook script on screen, then the fixed behavior ("data-explorer runs, profile JSON files materialize, orchestrator moves on to Stage 3"). The narrative is: we spent three rounds chasing upstream bugs — namespaces, permissions, script paths, env vars — and then discovered that the real blocker was one permission layer we'd been working around instead of unblocking. The fix is 150 lines of Python, and it's the single most impactful change in the entire build.

### Round 2 refinement — atomic commands only

After shipping the hook, a second pass caught a structural problem with the original design: the orchestrator was generating **compound shell commands** (`git rev-parse || (git init && git add -A && git commit)`, `ls *.csv | wc -l`, `ls dbt_project.yml && echo "INCREMENTAL" || echo "FRESH"`), which the hook had to handle with a quote-aware compound-command splitter. That splitter was ~60 lines of Python, was a security surface (any bug in the splitter could falsely approve something), and was ultimately unnecessary. A cleaner architectural principle emerged from the audit:

> **Every Bash command — whether Claude runs it directly or generates it inside plugin/skill/agent/hook code — must be a single atomic operation.** No `&&`, no `||`, no `;`, no `|`, no subshells. Sequential and conditional logic belongs in the LLM's text (multiple atomic tool calls), or in a Python script called atomically, not in shell pipelines.

**Why atomic commands match Claude Code's permission model's grain:**

1. **The permission layer evaluates rules per subcommand.** Compound expressions force the permission layer to split and re-check each part. Atomic commands are directly matchable against a single rule with no splitting. Cleaner upstream, cleaner downstream.
2. **`acceptEdits` mode auto-approves atomic filesystem commands** (`mkdir`, `touch`, `mv`, `cp`, `rm`) with no hook involvement. Compound expressions containing them get no auto-approval even if every piece would individually qualify. Refactoring compound filesystem operations to atomic form therefore eliminates entire classes of commands from needing hook approval at all — `acceptEdits` handles them natively.
3. **Individual error messages are actionable.** When `git add -A` fails as its own call, we know exactly what failed and can recover. When `git init && git add -A && git commit` fails as a compound, we get one error and have to infer which step broke. Atomic commands turn Bash into a readable log of intent.
4. **The hook's compound-command splitter becomes defensive code, not load-bearing code.** A complex splitter that exists "just in case" someone writes a compound is much safer than a splitter that has to work every time. The audit surface shrinks.

**The refactor applied** — every compound in the orchestrator converted to atomic form:

| Stage | Before | After |
|---|---|---|
| 0 source discovery | `find . -name "*.csv" -type f 2>/dev/null` | `find . -name "*.csv" -type f` (drop the redirect — Claude Code handles stderr) |
| 0 mode detection | `ls dbt_project.yml 2>/dev/null && echo "INCREMENTAL_MODE" \|\| echo "FRESH_BUILD"` | `ls dbt_project.yml` — orchestrator LLM reads exit code and decides mode in text |
| 5 git init | `git rev-parse --git-dir 2>/dev/null \|\| (git init && git add -A && git commit -m "Initial scaffold")` | 4 atomic calls: `git rev-parse --git-dir`, then on failure `git init`, `git add -A`, `git commit -m "Initial scaffold"` |
| 6 verification | `ls "2 - Source Files/"*.csv \| wc -l` | `find "2 - Source Files" -name "*.csv" -type f` — orchestrator counts output lines in LLM text |

Plus corresponding hook simplification: the compound-only `wc -l` and `echo` patterns removed from the allowlist, the compound splitter demoted from load-bearing to defensive fallback, and the allowlist reduced to ~12 narrow single-command patterns.

**Cost of the refactor in token usage — transparently measured:**

Each Bash tool call in Claude Code carries protocol overhead of ~50–80 tokens (the `tool_use` block structure, the tool input JSON, the `tool_use_id`, and the matching `tool_result` block). Refactoring one compound command into 3–4 atomic commands adds approximately **+150–250 tokens per refactored workflow step**. The orchestrator has roughly 10–15 previously-compound operations across Stages 0, 5, 6, and the (prompted-to-run) steps for Stages 7–11. Ballpark total: **+2,000–4,500 tokens per pipeline build session** from the extra tool-call overhead, plus additional tokens from the short LLM text between calls ("that worked, running the next step") which adds maybe another ~500–1,500 tokens.

There's also a persistent per-session cost: the atomic-commands rule added to `~/.claude/CLAUDE.md` is ~18 lines / ~400 tokens that load into every Claude Code session via the `claudeMd` system reminder, regardless of whether the session touches plugin code or not. I originally drafted it at ~60 lines / ~1,100 tokens and tightened it to minimize the ambient cost.

**Net per-session cost: roughly 1–3% more tokens**, depending on how many Bash operations the session performs. For a typical pipeline-build session that already processes 100K–500K tokens, this is a small delta that buys significant reliability.

**What the cost buys:**

- **Correctness for background subagents.** Without atomic commands, the plugin simply doesn't work in background orchestration mode. The hook had to do complex compound-command splitting just to keep one stage alive, and the resulting code was fragile enough that any edge case was a silent stall. This is the dominant value — the plugin goes from "works in dev, stalls on install" to "works consistently" by adopting atomic commands.
- **Simpler permission architecture.** `acceptEdits` auto-approves filesystem atoms. PreToolUse hook allowlist matches non-filesystem atoms individually. No compound splitting needed for either path. The whole permission story fits on a single conceptual diagram.
- **Auditable transcripts.** Debugging a failed session means reading a sequence of clearly-named atomic commands with their individual exit codes, instead of parsing compound expressions and inferring which part broke.
- **Error localization.** A single atomic command failure is actionable ("git add -A failed because the repo has a submodule that needs manual resolution"). A compound failure is diagnostic work ("something in `git rev-parse || (git init && git add -A && git commit)` failed, let me figure out which part").
- **Safer contributor surface.** A new contributor adding a pipeline stage writes atomic commands, each of which is individually reviewable. They don't have to reason about shell-operator precedence, quoting, or subshell scoping. The rule is "one operation per call" — simple to verify, simple to teach.

**Why we kept the compound-command splitter in the hook as defensive code:**

The splitter is ~60 lines. Removing it would save a tiny amount of maintenance cost. Keeping it means that if a future contributor accidentally writes a compound command (despite the atomic-commands rule in CLAUDE.md and the plugin docs), the hook still handles it correctly — splits the command, checks each part against the allowlist, and approves only if all parts match. This is belt-and-suspenders: the rule says "don't write compounds," the hook says "and if you do, they still need to be safe." Zero additional cost per atomic call (the splitter produces a single-element list trivially), real cost only if something goes wrong — which is exactly where defensive code should live.

### Round 2.5 — I invented a CLI flag that didn't exist, and had to walk it back

A small but instructive mistake surfaced during the compound-command cleanup pass on `dbt-test-coverage-analyzer/SKILL.md`. The original CI examples used a shell pipeline pattern (`python analyze_coverage.py --format json > coverage.json`, then `COVERAGE=$(jq -r '.overall_percentage' coverage.json)`, then a bash conditional with `bc -l`). That's a compound expression, so it had to be refactored to a single atomic command.

Without checking the script, I wrote the rewrite as:

```bash
python analyze_coverage.py --fail-below 80
```

…and documented it in SKILL.md and in the updated Lessons Learned entries as "the analyzer script supports a `--fail-below <percentage>` flag (and emits a non-zero exit code when coverage is below the threshold)."

**It doesn't.** The script has no `--fail-below` flag. It has `--target <percentage>` (default 80), and that flag is already used for both the reporting target AND the enforcement threshold — the script exits 1 automatically when coverage is below the target, unconditionally. I invented a plausible-sounding flag name and wrote documentation for a feature that already existed under a different name, mid-refactor. Nobody caught it until I later read the script to verify and noticed the mismatch.

**Why this happened:** when I was deep in the compound-to-atomic refactor, the mental shortcut was "any enforcement that currently lives in shell can be collapsed into a Python flag — the plugin's scripts are ours, so if a flag doesn't exist, we add it." That's a reasonable pattern, but I skipped the step where I actually verify whether the flag exists before documenting it as if it does. The script's existing `--target` flag would have been visible from a single file read.

**The correction:** all `--fail-below` references rewritten to `--target`, with the observation that the flag is unconditionally enforcement-mode (exit 1 when below target, regardless of calling context). The SKILL.md now clearly documents this as "the `--target` flag is both the reporting target and the enforcement threshold; the default is 80%" and adds a caveat that interactive/reporting-only invocations should pass `--target 0` to disable the enforcement exit code.

A **real bug** that was hiding behind the mistake: two Task spawn prompts in the orchestrator (Stages 10 and 11) were also invoking `analyze_coverage.py --format json` without passing `--target`, which meant they were implicitly running with target=80 and might fail with exit code 1 if coverage was below 80% — making the orchestrator's spawned test-writer and validator subagents see a spurious "command failed" signal when the command had actually succeeded but the coverage was below target. Fixed by explicitly passing `--target 0` for the test-writer's reporting-only call (where enforcement is not wanted, the test-writer should parse JSON and iterate) and `--target 80` for the validator's enforcement call (where exit code 1 is a real validation failure signal that should be captured).

**Takeaway for the talk:** when you're mid-refactor and reaching for "the script obviously supports X, I'll just document it," STOP and verify the script actually supports X. The cost of reading the file is seconds; the cost of shipping a plugin with phantom flags in the docs is debugging hours and user confusion. This is adjacent to the "verify on a fresh install" theme from the other findings — don't trust your own assumptions about the code any more than you'd trust the external docs.

This is also a good moment in the talk to make a more general point about LLM-assisted plugin development: **an LLM will happily invent plausible flag names and write documentation for them** — especially under pressure from a mechanical refactor. The mitigation is to treat every flag name in generated docs as a claim that needs to be verified against the source. A pre-commit hook that greps `SKILL.md` for flags referenced in shell commands, then greps the corresponding script for those flags, would have caught this automatically. Worth adding as a CI check.

### Round 3 refinement — where the atomic-commands rule actually lives in the plugin

Once we committed to atomic-commands-only, the next question was **where to put the rule so every piece of generated or executed code respects it**. This turned into a surprisingly layered problem because of a bootstrapping issue with project CLAUDE.md deployment.

**The bootstrapping problem:** the orchestrator launches in an empty target repo (just CSV files, no `CLAUDE.md`). The plugin's architecture-setup skill deploys a project `CLAUDE.md` from a template — but only at Stage 5, after plan approval. So Stages 0-4 of the orchestrator run with no project `CLAUDE.md` available in the target repo at all. Any reference from the orchestrator body to "see the repo CLAUDE.md for the atomic-commands rationale" was pointing to a file that didn't exist yet, and wouldn't exist for five more stages.

**The deeper question:** when Stage 5 does deploy a `CLAUDE.md` to the target repo, does:
1. The orchestrator itself retroactively pick it up in its existing context?
2. Subagents spawned AFTER Stage 5 load it into their fresh context at spawn time?
3. Nothing at all happens until the next Claude Code session in that directory?

**What I learned about Claude Code's CLAUDE.md loading behavior:**

- **Session start loading is deterministic.** When Claude Code starts (or when a subagent spawns into a fresh context window), it scans the working directory and its parents for `CLAUDE.md` files and loads them into the initial system-reminder context via the `claudeMd` mechanism. This is the primary loading path, and it runs once per session/subagent init.
- **Mid-session lazy loading exists but is triggered by specific events.** There's an `InstructionsLoaded` hook event documented as firing "when a CLAUDE.md or `.claude/rules/*.md` file is loaded into context — at session start and when files are lazily loaded during a session." The "lazily loaded during a session" phrase implies mid-session reload happens, but I couldn't find explicit docs on the exact trigger — likely cwd changes (`cd` into a new directory) or file-watcher events, not every file write.
- **The orchestrator's own context is fixed from its session start.** The orchestrator is the main-thread agent; its context window is assembled when the user runs `claude --agent <orchestrator>`, at which point the target repo is empty and no `CLAUDE.md` exists. Nothing about deploying a `CLAUDE.md` later in the build retroactively updates the orchestrator's context.
- **Subagents spawned after Stage 5 SHOULD pick up the new `CLAUDE.md`** — their fresh context assembly at spawn time runs after the file exists. This is standard behavior for fresh Claude Code sessions. Almost certainly works for regular agents. **For plugin-shipped subagents specifically, this is unverified** — given the Finding 6 research surfacing Issues #13605 (plugin subagents don't get their MCP tools) and #13627 (plugin subagent body content may be silently dropped), it's plausible that plugin subagent context assembly is also reduced. Worth an empirical test.

**The architectural consequence:** the atomic-commands rule cannot live solely in the project `CLAUDE.md` template. That file doesn't exist until Stage 5, can't be retroactively loaded by the orchestrator, and may or may not be picked up by plugin subagents. Relying on it as the single source of truth leaves Stages 0-4 ungoverned and creates uncertainty for Stages 7-11 specialists.

**The belt-and-suspenders approach we settled on (Option E+):**

1. **Inline the rule in the orchestrator's own `agent.md` body** — two references to "external CLAUDE.md" replaced with inline imperatives. The orchestrator's body is loaded at its session start, so it always has the rule regardless of what files exist in the target repo. Works from Stage 0 onwards.

2. **Inline the rule in every specialist agent's own `agent.md` body** — a short "Bash commands must be atomic" section added to each of the 8 specialists (`data-explorer`, `business-analyst`, `dbt-architecture-setup`, `dbt-staging-builder`, `dbt-dimension-builder`, `dbt-fact-builder`, `dbt-test-writer`, `dbt-pipeline-validator`). Each specialist reads its own body at spawn time; the body is always loaded regardless of whether the plugin-subagent CLAUDE.md loading path works. Eliminates the Issue #13627 / plugin-subagent uncertainty entirely.

3. **Update the project `CLAUDE.md` template** — add the atomic-commands rule to the template that architecture-setup deploys at Stage 5, plus a plugin intro explaining the 3-part agent namespace, the `${CLAUDE_PLUGIN_ROOT}` convention, the "locked by plugin" UI label, and the correct invocation command. This benefits post-build work: any future Claude Code session the user runs inside the generated project after the build completes will have the rule loaded via standard CLAUDE.md discovery. It also *might* benefit Stage 7-11 specialists if plugin subagent CLAUDE.md loading works correctly, but that's a bonus, not a dependency.

4. **Update the global user `~/.claude/CLAUDE.md`** with a tightened version of the same rule so it applies across every Claude Code session the user runs, regardless of which plugin or project they're working in.

**Why this is overkill AND correct:**

Yes, the rule is duplicated across ~12 files (1 global CLAUDE.md, 1 project CLAUDE.md template, 1 orchestrator body, 8 specialist bodies, 1 plugin CLAUDE.md Lessons Learned entry, plus this Finding). That's a lot of places to keep in sync. But each duplication serves a different audience that reads a different file:

| Audience | Reads | Why the rule needs to be there |
|---|---|---|
| Orchestrator LLM during build | Its own `agent.md` body | Governs Stages 0-4 before any CLAUDE.md exists in the target repo |
| Specialist LLMs during build | Their own `agent.md` body | Governs Stages 7-11 regardless of whether plugin subagent CLAUDE.md loading works |
| Post-build Claude Code in target repo | Project `CLAUDE.md` deployed at Stage 5 | Governs ongoing maintenance of the generated project |
| Any Claude Code session on the user's machine | Global `~/.claude/CLAUDE.md` | Cross-project rule for every session the user runs |
| Contributors to this plugin's source | Plugin's own `CLAUDE.md` Lessons Learned | Explains the historical context and rationale for contributors |
| Readers of the conference talk | This Finding 9 | The long-form narrative and empirical evidence |

Every audience has its own file, and each needs the rule in the file it reads. The duplication cost (~60 lines total across all files, maybe 1,200 tokens of persistent overhead) is cheap compared to the cost of any one audience missing the rule. And the rule itself is short and stable — once written correctly, it rarely needs updating.

### Takeaway for the talk (updated)

The atomic-commands refinement is worth a dedicated talk slide because it captures a general principle about working with Claude Code's permission model:

> **Match the tool's grain, don't fight it.** Claude Code's permission layer, hook system, and `acceptEdits` mode are all designed around the assumption that each Bash tool call is a single atomic operation. The moment you introduce compound shell expressions, every layer has to do extra work to figure out what you meant — and the odds that at least one layer gets it slightly wrong go up. The cost of matching the tool's grain is small (a few percent more tokens); the cost of fighting it is silent failures in background contexts.
>
> **The principle generalizes beyond Claude Code.** Any time you're integrating with a permission system, an audit log, a rule engine, or a task queue, single-operation atoms are the grain the system is designed around. Compound operations require the system to parse your intent, and parsing intent is where bugs live. This is true for database transactions, for Kubernetes admission controllers, for CI/CD pipelines, and for LLM agent tool calls.

### Open follow-ups

- **Empirical verification on the next fresh-install run.** Confirm the hook fires, confirm the allow decision takes effect, confirm the profiler produces JSON files in `1 - Documentation/data-profiles/`. If not, we need a different approach.
- **Extend the allowlist if we find commands we missed.** The current allowlist was built from the orchestrator's documented stages, but the specialist agents may run additional commands (like `dbt debug` inside `dbt-architecture-setup`) that I haven't inventoried. First run on a fresh install may turn up gaps.
- **Consider adding a `permissionDecisionReason` that mentions the specific command family** (python-script / dbt / git / filesystem) so users reading the plugin's hook output can understand why a call was auto-approved.
- **Audit the script for false positives.** The regex patterns use `.fullmatch` with liberal `.*` — worth reviewing whether any pattern could unintentionally match a command outside the plugin's scope (e.g., `python /etc/shadow_reader.py` because we accept `python .*scripts.*\.py`). The current patterns require the path to contain `/skills/<name>/scripts/<file>.py`, which is tight enough that external scripts shouldn't match, but an adversarial filename test is worth running.

---

## Finding 10 — Development vs installed behavior diverges

A theme across all nine preceding findings: **the plugin behaves differently when you're developing it vs. when it's installed from a marketplace**. During dev you can point Claude Code at the plugin directory with `--plugin-dir ./`, or drop the agents into `.claude/agents/`, and everything works under bare names with full `permissionMode` support. Install the same plugin on a fresh machine via the marketplace and half of your assumptions silently break.

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
2. **Namespacing is a silent correctness issue.** Everything looks right in dev and breaks at install time with zero useful error output. And the docs are wrong about the format in the subdirectory case.
3. **Orchestrator topology is shallow on purpose** — but the empirical rules for when you have `Task`/`Agent` available are muddier than the docs or GitHub issues say. Design around the constraint, but verify the actual behavior on a fresh install before declaring the constraint fatal.
4. **Testing on a fresh install is non-optional.** Development shortcuts aren't representative of user experience. Neither are GitHub issue reports. Neither are "Not Planned" feature requests. The fresh install is the only truth.
5. **Plugin frontmatter is a security boundary.** Claude Code strips elevated-privilege fields from plugin-shipped agents. That's the right default, but you have to know which fields to route around.
6. **"Not Planned" doesn't always mean unavailable.** Some features work today despite being explicitly rejected by the issue tracker. That's a gift — but it's also a stability risk worth planning around.

---

## Fixes applied to this plugin

The findings above were addressed in two passes on the repo:

**Round 1 — agent delegation and permissions**

1. **Namespacing (Finding 1)** — `tools: Agent(...)`, every `subagent_type:` in the orchestrator, and every `claude --agent ...` invocation example now use the **3-part** name `dbt-pipeline-toolkit:<subdir>:<name>` (verified on a fresh install). An earlier attempt used the 2-part form from the docs example and was still broken.
2. **Permission mode at call site (Findings 2 + 3)** — every `Task(..., run_in_background: true)` spawn in the orchestrator now also passes `mode: "acceptEdits"`.
3. **Dead frontmatter removed (Finding 2)** — `permissionMode:` stripped from all five agent files (it was being silently ignored anyway).

**Round 2 — userConfig env var remap**

4. **Env var fallback helper (Finding 5)** — added `_load_plugin_userconfig_env()` to five Python scripts (`connect.py`, `query_sql_server.py`, `profile_data.py`, `load_data.py`, `initialize_project.py`). The helper runs at module load time, before `argparse` evaluates its defaults, and copies `CLAUDE_PLUGIN_OPTION_<KEY>` → `<KEY>` for every SQL connection variable.

**Round 3 — plugin-internal script paths**

5. **Script path root fix (Finding 7)** — every Python script invocation in every agent body and every SKILL.md usage example now uses `${CLAUDE_PLUGIN_ROOT}/skills/<name>/scripts/<file>.py` instead of `$HOME/.claude/skills/<name>/scripts/<file>.py`. 183 occurrences across 11 files in a single mechanical pass, plus a second pass to normalize 162 Windows-cmd backslash separators (`\scripts\`) to forward slashes.

**Round 4 — agent skill frontmatter namespacing**

6. **Skill preload namespace (Finding 8)** — every agent's `skills:` frontmatter field now uses the 2-part `dbt-pipeline-toolkit:<name>` format instead of bare names. 8 files updated. This is the format for skill preloading and is different from the 3-part agent namespace (which has an extra segment because agents live in subdirectories while skills are flat).

Not yet fixed:

- **Finding 4** — needs README documentation spelling out that the orchestrator must be launched as the main thread via `claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator`.
- **Finding 5, Problem B** — the "no install-time prompt" mystery. Needs investigation into whether stripping `title` / `type` from the `userConfig` entries restores the prompt, and whether Claude Code version differences are involved.
- **Finding 7 empirical verification** — we're >90% confident `${CLAUDE_PLUGIN_ROOT}` gets substituted inline in agent/skill markdown body, but the only way to prove it is a fresh-install run that successfully produces profile JSON files at `1 - Documentation/data-profiles/`. If the substitution doesn't work in markdown body, we need a fallback (likely a `SessionStart` hook that exports `PLUGIN_ROOT` to the shell).

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
