# Plugin Learnings — DBT Pipeline Toolkit

Working notes and discoveries from building the `dbt-pipeline-toolkit` Claude Code plugin. Intended as source material for a conference presentation on **agentic tooling in data engineering**.

The plugin packages 9 specialized agents, 8 skills, 3 hooks, and an MCP server into a single installable unit distributed through an external marketplace repo (`AI-plugins`). The goal was end-to-end automation: drop CSVs in a folder, get a tested dbt star schema on SQL Server.

Everything in this doc is the result of things that **actually broke** when the plugin was installed on a second machine — not theory.

---

## Why this matters for data engineering

A data engineering pipeline is a *multi-agent problem by nature*. You have distinct roles — requirements, source profiling, staging, dimensions, facts, tests, validation — each with its own expertise and its own tools. Claude Code subagents map cleanly onto these roles, and orchestration lets a "conductor" agent drive the entire workflow with minimal human touch points (2 total in this plugin: a discovery Q&A and a plan approval gate).

The promise: a user drops CSV files in a folder, answers 5 questions, approves a plan, and walks away with a fully tested, validated dbt pipeline. The reality: getting there surfaced several gotchas that aren't obvious from the plugin documentation alone.

---

## Finding 1 — Plugin agents get namespaced at install time

### What I learned

When a Claude Code plugin is installed, every agent it ships is registered under a namespace derived from the plugin's `name` field in `plugin.json`. The format is:

```
<plugin-name>:<agent-name>
```

So `business-analyst` inside `dbt-pipeline-toolkit` becomes `dbt-pipeline-toolkit:business-analyst` once installed. This is confirmed in the official Claude Code plugins reference:

> "This name is used for namespacing components. For example, in the UI, the agent `agent-creator` for the plugin with name `plugin-dev` will appear as `plugin-dev:agent-creator`."

The marketplace name is **not** part of the namespace — only the plugin name.

### How it broke

The orchestrator agent had two places that referenced sibling agents by their bare names:

1. The `tools:` allowlist:
   ```yaml
   tools: Agent(business-analyst, data-explorer, dbt-staging-builder, ...)
   ```
2. Every `Task(...)` call in its workflow body:
   ```
   Task(subagent_type: "business-analyst", ...)
   ```

When running locally during development (via `.claude/agents/...` or `--plugin-dir`), agents live under their bare names and everything worked. When installed through the marketplace, the bare names no longer matched any registered agent — so the `Agent(...)` allowlist became effectively empty and every delegation call failed to resolve. The orchestrator ran, spawned nothing, and reported no errors.

### Takeaway for the talk

> **If your plugin has an orchestrator agent that spawns siblings, every reference needs to use the namespaced name.** This applies to both the `tools: Agent(...)` allowlist and every inline `subagent_type:` in prompts and code blocks inside the agent's system prompt.

This is a subtle but critical distinction between "works in dev" and "works when installed." It's worth a dedicated slide.

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

## Finding 5 — Development vs installed behavior diverges

A theme across all four findings: **the plugin behaves differently when you're developing it vs. when it's installed from a marketplace**. During dev you can point Claude Code at the plugin directory with `--plugin-dir ./`, or drop the agents into `.claude/agents/`, and everything works under bare names with full `permissionMode` support. Install the same plugin on a fresh machine via the marketplace and half of your assumptions silently break.

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

All three findings were addressed in a single pass on the orchestrator and the four builder agents:

1. **Namespacing** — `tools: Agent(...)` and every `subagent_type:` in the orchestrator now use `dbt-pipeline-toolkit:<name>`.
2. **Permission mode at call site** — every `Task(..., run_in_background: true)` spawn in the orchestrator now also passes `mode: "acceptEdits"`.
3. **Dead frontmatter removed** — `permissionMode:` stripped from all five agent files (it was being silently ignored anyway).

Details of the fixes — including line-level changes — are tracked in `CLAUDE.md` under the "Lessons Learned" section.

---

## Open questions for future iteration

- Can the orchestrator detect at runtime whether it's running as a subagent (and fail fast with a useful error) instead of silently doing nothing?
- Should the plugin ship a `settings.json` with a `subagentStatusLine` that makes background agent progress visible to the user? That would at least help diagnose stalled workers.
- Is there a way to validate plugin frontmatter offline — catching a stray `permissionMode` before it ships?
- How should the README document the invocation command so users can't miss it? A big fence at the top? A `/plugin install` post-install hook that prints usage?

Worth a live demo slide in the talk: show the "broken" behavior (orchestrator stalls), then the fix, then the working run, side-by-side.
