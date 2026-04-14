# Research — Plugin Subagent Delegation in Claude Code

**Date:** 2026-04-14
**Context:** While trying to get `dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator` to delegate to its 8 specialist subagents on a fresh plugin install, delegation kept failing silently across three naming attempts (bare, 2-part, 3-part). This research was gathered to find out whether plugin-to-plugin subagent delegation is a supported feature, a known bug, or architecturally blocked.
**Method:** General-purpose research agent, spawned from the main session, with a brief directing it to search GitHub issues, community forums, and look for working public plugin examples. No code changes made during research.

---

## ⚠️ Important caveat — subsequent real-world observation contradicts this research

**After this research report was gathered, the user tested the orchestrator on a fresh install by invoking it as `claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator "Build a pipeline"` and delegation to sibling plugin agents DID work.**

This directly contradicts the interpretation the research agent gave of Issues #23506 and #19077, which claimed that a custom agent loaded via `--agent` does not receive the `Task`/`Agent` tool at all. The GitHub issue reports may be:

- Out of date (behavior has changed in a Claude Code release since the issue was filed)
- Specific to a narrower configuration than the issue title suggests (e.g. only certain forms of `--agent` invocation, or only agents defined in `.claude/agents/` rather than plugin-shipped)
- Accurate for some code paths but not others (e.g. behavior differs between plain `--agent` invocation and plugin-installed `--agent <plugin:subdir:name>` invocation)

Either way, **the research below should be read as contextual background, not as a statement of current fact.** The empirical test on a fresh install is the authoritative source. The research is still valuable because:

1. It identified the feature request issue #19276 (closed "Not Planned"), which is a meaningful signal about official support level even if delegation empirically works today
2. It catalogued the community workarounds in case the behavior regresses
3. It proves that you cannot trust even recent GitHub issues as ground truth for Claude Code plugin behavior — another "verify on a fresh install" lesson

---

## Research agent's original findings (as received)

### TL;DR as the agent reported it

> "Your delegation isn't working because **custom agents launched via `claude --agent <name>` do not receive the `Task`/`Agent` tool at all**, regardless of what you put in the `tools:` frontmatter field. This is tracked in multiple open GitHub issues on `anthropics/claude-code`. The namespace format is a red herring — you could get it perfectly right and it would still fail."

This interpretation turned out to be empirically wrong for our plugin on our fresh install — but the underlying issues the agent cited are real, so we need to understand them.

### Primary sources cited

1. **[Issue #23506](https://github.com/anthropics/claude-code/issues/23506)** — "[BUG] Custom agents (--agent) cannot spawn subagents into teams - Task tool unavailable" (CLOSED as duplicate of #13533, unresolved)

   Agent's quote:
   > "When running Claude Code with a custom agent (`claude --agent daily`), the Teammate tool is available and can create teams via `spawnTeam`, but the **Task tool (subagent spawner) is not present in the session**."
   >
   > "The same workflow works correctly from a plain `claude` session (no `--agent` flag)."

   **Our observation contradicts this.** Our plugin orchestrator invoked via `claude --agent <3-part-name>` DID have the subagent spawner available. Possibly the bug reporter was using `--agent` with a non-plugin agent definition, or the behavior has changed.

2. **[Issue #19077](https://github.com/anthropics/claude-code/issues/19077)** (OPEN) — "[BUG] Sub-agents can't create sub-sub-agents, even with Task tool access"

   Agent's quote from the issue body:
   > **"Subagents cannot spawn other subagents."** — quoted directly from the [official subagents docs](https://code.claude.com/docs/en/sub-agents). "This is an intentional architectural decision, not a bug."
   >
   > **What Works:** Default main Claude instance (no "agent" in settings.json) → Has Task(). Default main instance wearing a SKILL → Has Task().
   >
   > **What Doesn't Work:** Custom agent as main (via settings.json) → **No Task() tool**. Worker subagents → No Task() tool.

   **Our observation again contradicts the "custom agent as main → no Task()" claim** for the plugin case. The "subagents cannot spawn other subagents" architectural rule remains true — our orchestrator can only delegate *because* it's running as the main thread, not as a leaf subagent.

3. **[Issue #19276](https://github.com/anthropics/claude-code/issues/19276)** (CLOSED, Not Planned, 2026-02-27) — "Feature Request: Custom Subagent Support in Task Tool"

   Agent's quote:
   > "The `Task()` tool in Claude Code only recognizes **3 hardcoded built-in subagents**: `general-purpose`, `plan`, `explore`. Custom agents from `~/.claude/agents/*.md`, `~/.claude/subagents.json`, and `~/.claude/plugins/*/agents/*.md` are **NOT discovered**."

   **This is the strongest signal in the research against what we observed.** If plugin agents weren't discoverable by Task, our orchestrator could not have spawned any. Two possibilities:

   - This feature request's claim was only partially correct — perhaps plugin-shipped agents ARE discoverable even though `~/.claude/agents/*.md` ones aren't
   - The behavior was updated after the issue was closed, even though the issue remained in "Not Planned" state
   - The interactive-chat `@agent-<plugin>:<agent>` path uses a different resolver than the programmatic `Task` path, and plugin agents are discoverable via one but not the other

   Worth re-reading the actual issue text rather than relying on the agent's summary, since the agent's interpretation has already been shown to be partially wrong.

4. **[Issue #13605](https://github.com/anthropics/claude-code/issues/13605)** (CLOSED completed) — Plugin subagents don't get MCP tools they declare

   Agent's quote:
   > "Custom subagents defined in Claude Code plugins cannot access MCP tools, regardless of how the `tools` field is configured in the agent definition. Built-in agents like `general-purpose` DO receive MCP tools, but custom plugin-defined agents do not."

   This is a separate axis from the delegation question but confirms plugin-shipped agents have a different runtime profile from built-in ones. We should verify whether our specialist agents can actually reach the `sql-server-mcp` tools at runtime, or if they're restricted to only the `tools:` field's native entries.

5. **[Issue #13627](https://github.com/anthropics/claude-code/issues/13627)** (CLOSED not-planned) — Custom agent body content not injected via Task tool

   Agent's quote:
   > "When a custom agent is defined in `.claude/agents/*.md` with markdown body content containing instructions, and that agent is spawned as a subagent via the Task tool, the body content is completely ignored."

   Another claim worth verifying empirically. If true, it would mean our specialist agents' system prompts aren't actually being applied when the orchestrator spawns them — they'd behave like `general-purpose` agents with only a short instruction from the orchestrator's `prompt:` parameter. Our initial happy-path run on the fresh install apparently worked, but we haven't verified whether the body content (50-200 lines per specialist) is actually in effect.

### Working architectures in other multi-agent plugins (as the agent reported)

The research agent searched specifically for public plugins doing multi-agent orchestration via `Task` and reported finding **none**. Every real-world multi-agent plugin uses one of three workarounds:

- **[wshobson/agents](https://github.com/wshobson/agents)** — 77 single-purpose plugins, no cross-plugin orchestration; users invoke agents directly via `@mention`
- **[barkain/claude-code-workflow-orchestration](https://github.com/barkain/claude-code-workflow-orchestration)** — uses plan mode + slash commands, not `Task` chaining
- **[baryhuang/claude-code-by-agents](https://github.com/baryhuang/claude-code-by-agents)** — external desktop app coordinates agents via `@mentions` over its own API, bypassing the `Task` tool entirely

Given that our plugin appears to work where the research says none should, `dbt-pipeline-toolkit` may be one of the first (or first documented) plugins to successfully use intra-plugin `Task`-based delegation from a main-thread orchestrator. That's either a happy discovery or a signal that something subtle is different about our configuration — worth investigating which.

### Recommended next steps (as the agent reported)

The research agent recommended three fallback architectures assuming delegation was blocked. Since delegation empirically works, **paths 1-3 below are no longer immediate fallbacks** but are preserved as contingency plans in case behavior regresses:

1. **Convert the orchestrator to a Skill.** `skills/dbt-pipeline-orchestrator/SKILL.md`. Skills run on the default main thread, which per #19077 has `Task` available. Keep the 8 specialists as plugin agents. Invoke via `/dbt-pipeline-toolkit:dbt-pipeline-orchestrator "Build a pipeline"`.

2. **Use `general-purpose` with injected role prompts.** From a skill-orchestrator, call `Task(subagent_type: "general-purpose", prompt: "<role prompt copied from the agent.md body>")`. Loses per-agent model choice, isolation, tool restrictions, and worktree support, but works without any feature-parity hopes.

3. **Drop the orchestrator entirely.** Turn each stage into its own slash command and let the user drive the workflow: `/dbt-start`, `/dbt-profile`, `/dbt-plan`, `/dbt-build`, etc. This matches what `barkain/claude-code-workflow-orchestration` does.

## What to take from this research

- **The feature request #19276 being "Not Planned" is still meaningful.** Even though delegation empirically works today, it's not officially supported, and could regress. Any production reliance on this delegation path should include a smoke test in CI and documented fallback to the skill-orchestrator pattern.
- **Issue #13627's claim about body content being ignored needs empirical testing.** If our specialist agent.md bodies are being silently dropped, the orchestrator isn't getting the behavior we designed — it's spawning `general-purpose`-like agents with only the orchestrator's short `prompt:` as context. A minimal test: spawn one specialist and ask it in its prompt "what are you specialized in?" — if it answers based on its own agent.md body, body content is being injected. If it answers generically, body content is being dropped.
- **The research illustrates a meta-lesson for the conference talk:** even well-cited, recent GitHub issues are not a reliable source of truth for Claude Code plugin behavior. Verify everything on a fresh install.

## Related follow-ups (not yet done)

- Re-read Issue #19276 directly (not via the research agent's summary) to understand exactly which agent sources it claimed weren't discoverable by `Task`, and whether that claim specifically excluded plugin-installed agents
- Empirically test whether our specialist agents receive their own body content when spawned from the orchestrator (per Issue #13627 concern)
- Check whether the MCP server tools (`sql-server-mcp:*`) are actually reachable from within a spawned specialist, or if they're restricted per Issue #13605
- Document the working invocation pattern in the plugin README so users don't go through the same discovery process we did
