# Issue Tracker — dbt-pipeline-toolkit

Single source of truth for every known bug, empirical verification need, design gap, architectural risk, and enhancement in this plugin. This is NOT a backlog of planned features — see `_Plan/Backlog.md` for forward-looking work items. This file is for **problems we already know about**.

**Maintenance rules:** every new issue discovered during development or testing MUST be added here with a unique ID. Never silently fix an issue without an entry — create the entry, then mark it resolved in the same commit. See `CLAUDE.md` section "Issue Tracker Maintenance" for the full policy.

---

## Schema

| Column | Values |
|---|---|
| **ID** | Sequential `I-###` — never reuse IDs even after closing |
| **Title** | Short noun phrase describing the problem |
| **Category** | `empirical` (unverified claim needing fresh-install test), `bug` (known broken), `docs` (missing/incorrect documentation), `enhancement` (improvement to working feature), `risk` (known architectural concern) |
| **Severity** | `critical` (blocks shipping), `high` (significant impact), `medium` (workaround exists), `low` (nice to have) |
| **Status** | `open`, `in-progress`, `blocked` (waiting on external), `resolved` (fixed, awaiting verification), `closed` (fixed and verified), `wontfix` |
| **Found** | Date the issue was identified (YYYY-MM-DD) |
| **Source** | Which finding, session, or commit surfaced it |
| **Blocker** | What's preventing resolution (if blocked) or next step (otherwise) |

---

## Open issues

### Empirical verification needs (high priority — blocks shipping claims)

| ID | Title | Category | Severity | Status | Found | Source | Blocker |
|---|---|---|---|---|---|---|---|
| I-001 | PreToolUse hook actually fires for background subagent Bash calls | empirical | critical | open | 2026-04-14 | Finding 9 | Fresh-install test — run orchestrator, verify `python profile_data.py` succeeds in Stage 2 |
| I-002 | PreToolUse hook `permissionDecision: "allow"` actually skips the prompt in background context | empirical | critical | open | 2026-04-14 | Finding 9 | Same test as I-001 — if the hook fires but doesn't short-circuit the permission layer, the fix is incomplete |
| I-003 | Profile JSON files materialize in `1 - Documentation/data-profiles/` after Stage 2 | empirical | critical | open | 2026-04-14 | Findings 7 + 9 | Happy-path signal that `${CLAUDE_PLUGIN_ROOT}` substitution, the hook allowlist, and the env var remap all work together |
| I-004 | `${CLAUDE_PLUGIN_ROOT}` is actually substituted inline in agent/skill markdown body at load time | empirical | high | open | 2026-04-14 | Finding 7 | The plugins-reference says yes, `plugin.json` usage confirms it for `mcpServers`, but body substitution is unverified for agent markdown specifically |
| I-005 | Plugin subagents receive their own agent.md body content at spawn time (Issue #13627) | empirical | high | open | 2026-04-14 | Finding 6 research | Test: spawn a specialist, ask it in its prompt "what role are you specialized in?" — if generic answer, body content is being dropped |
| I-006 | Plugin subagents can access declared MCP tools (Issue #13605) | empirical | high | open | 2026-04-14 | Finding 6 research | Test: have a specialist try to call `sql-server-mcp:*` tools and see if they resolve |
| I-007 | Plugin subagents auto-load project `CLAUDE.md` at spawn time | empirical | medium | open | 2026-04-14 | Finding 9 Round 3 | Test: deploy a `CLAUDE.md` with a distinctive rule at Stage 5, spawn a specialist in Stage 7, verify the specialist sees the rule |
| I-008 | `userConfig` install-time prompts actually fire when the plugin is installed | empirical | high | open | 2026-04-14 | Finding 5 Problem B | User observation: installed the plugin on a fresh machine and NO prompt appeared for `sql_server`, `sql_database`, etc. Unknown whether this is Claude Code version difference, undocumented `title`/`type` field fields in `userConfig` confusing the parser, or something else |
| I-009 | `skills:` agent frontmatter preload actually injects skill content into the subagent context | empirical | medium | open | 2026-04-14 | Finding 8 | After namespace fix, we don't know whether preloading was contributing anything behaviorally — test by removing a specialist's `skills:` field and comparing quality of generated models |

### Real bugs (open)

| ID | Title | Category | Severity | Status | Found | Source | Notes |
|---|---|---|---|---|---|---|---|
| I-010 | Orchestrator frontmatter `description:` field still uses 2-part invocation command | bug | low | open | 2026-04-14 | Self-audit | `agents/dbt-pipeline-orchestrator/agent.md:11` says "Run via `claude --agent dbt-pipeline-orchestrator`" — should be the 3-part form `dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator`. Was not updated when we fixed the namespace references elsewhere. |
| I-011 | `skills/sql-connection/` has no `SKILL.md` — not a valid skill | bug | medium | open | 2026-04-14 | Finding 5 audit | The directory has only `scripts/connect.py`. Claude Code won't register it as a skill, so it doesn't appear in `/skills` and isn't namespaced. Currently used as a shared Python library by other skill scripts via `sys.path` hacks. Options: (a) add a minimal `SKILL.md` so it shows up as `dbt-pipeline-toolkit:sql-connection`, (b) move `connect.py` to a shared `lib/` directory and update imports in the other scripts. |

### Documentation gaps

| ID | Title | Category | Severity | Status | Found | Source | Notes |
|---|---|---|---|---|---|---|---|
| I-012 | Plugin README missing main-thread invocation instructions | docs | high | open | 2026-04-14 | Finding 4 | The plugin README must prominently explain that the orchestrator only works when launched via `claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator "Build a pipeline"` — not via @mention, auto-delegation, or `/agents` picker. Users invoking it any other way will hit the "subagents cannot spawn subagents" wall. |
| I-013 | Plugin README missing fresh-install configuration instructions | docs | medium | open | 2026-04-14 | Finding 5 Problem B | Until I-008 is resolved, the README needs a section telling users to manually add `sql_server`, `sql_database`, `sql_auth_type`, etc. to their `settings.json` under `pluginConfigs.dbt-pipeline-toolkit.options` if the install-time prompts don't fire. |
| I-014 | SKILL.md files use `${CLAUDE_PLUGIN_ROOT}/skills/<name>/` instead of `${CLAUDE_SKILL_DIR}/` | docs | low | open | 2026-04-14 | Finding 8 open follow-up | Inside a SKILL.md, the more idiomatic form is `${CLAUDE_SKILL_DIR}/scripts/<file>.py` which doesn't hardcode the skill's own name. Not a correctness issue — the current `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/<file>.py` form works fine. Purely a cleanliness improvement. |

### Architectural risks

| ID | Title | Category | Severity | Status | Found | Source | Notes |
|---|---|---|---|---|---|---|---|
| I-015 | Plugin delegation via `Task` is officially "Not Planned" but empirically works | risk | high | open | 2026-04-14 | Finding 6 | The core subagent delegation path this plugin depends on was explicitly closed as "Not Planned" in GitHub Issue #19276. Empirical testing shows it works today, but Anthropic could break it in any release without warning. Mitigation: keep `_Research/plugin-subagent-delegation.md` updated with any new signals, add a CI smoke test that runs the orchestrator end-to-end before every release. Fallback architecture documented: skill-orchestrator pattern that converts the orchestrator to a Skill instead of an Agent. |
| I-016 | `permissionMode` stripping and other plugin-agent restrictions could apply to more fields | risk | medium | open | 2026-04-14 | Finding 2 | The docs list `hooks`, `mcpServers`, `permissionMode` as stripped from plugin agent frontmatter, but other fields might also be silently ignored. Worth periodically auditing plugin agent behavior against standalone agent behavior to catch new restrictions. |

### Enhancements (low priority — nice to have)

| ID | Title | Category | Severity | Status | Found | Source | Notes |
|---|---|---|---|---|---|---|---|
| I-017 | Add `--strict` flag to `analyze_coverage.py` to separate report from enforcement | enhancement | low | open | 2026-04-15 | Round 2.5 phantom-flag incident | Current design overloads `--target` as both reporting target and enforcement threshold (script exits 1 unconditionally when below target). A cleaner design: `--target <pct>` sets the reporting target, `--strict` enables the exit-1 enforcement. Defaults: `--target 80`, strict off. Eliminates the `--target 0` workaround I had to document for reporting-only calls. |
| I-018 | Add a CI/pre-commit check that verifies flag names referenced in SKILL.md match script argparse | enhancement | medium | open | 2026-04-15 | Round 2.5 phantom-flag incident | Grep every SKILL.md for `python .*\.py\s+--<flag>` patterns, extract flag names, then grep the corresponding script's argparse for those flags. Fail if any flag in the docs doesn't exist in the script. Catches the class of "LLM invented a plausible flag name" bugs I hit during the atomic-commands refactor. |
| I-019 | Audit hook allowlist regex patterns for adversarial filename false-positives | enhancement | medium | open | 2026-04-14 | Finding 9 open follow-up | The patterns use `.fullmatch` with liberal `.*` — worth confirming no pattern could unintentionally match a command outside the plugin's scope (e.g. `python /etc/scripts/shadow_reader.py` — current patterns require `/skills/<name>/scripts/<file>.py` but edge cases should be tested with a parametrized test file) |
| I-020 | Expand hook `permissionDecisionReason` to include the specific matched category | enhancement | low | open | 2026-04-14 | Finding 9 open follow-up | Currently the reason is generic ("all subcommands match the allowlist"). Adding the specific category (python-script / git / filesystem / pip) would make the plugin's auto-approvals more auditable in transcripts. |
| I-021 | Audit for other dev-path patterns beyond `$HOME/.claude/skills/` | enhancement | low | open | 2026-04-14 | Finding 7 open follow-up | The grep pass that found 183 `$HOME/.claude/skills/` occurrences should be repeated for adjacent patterns like `$HOME/.claude/plugins/`, `$HOME/.claude/hooks/`, `%USERPROFILE%\.claude\...` to catch any other dev-workflow leakage. |
| I-022 | Document `connect.py` library structure since it's not a real skill | enhancement | low | open | 2026-04-14 | Related to I-011 | Even if we don't add a `SKILL.md` to `sql-connection/`, the fact that it's a shared library imported by other skill scripts should be documented in the plugin CLAUDE.md so future contributors don't mistake it for a dormant skill. |

---

## Recently resolved (kept for historical context)

Resolved issues are kept in this file for ~30 days before being archived. Items with `closed` status (fixed AND verified on a fresh install) can be moved to `_Plan/Issues-Archive.md` after verification.

*(No resolved issues yet — this file was just created.)*

---

## Issue lifecycle

1. **Discovery** — a new problem is identified during development, testing, or research. Create a new `I-###` row immediately. Never leave undocumented problems in the codebase.
2. **Triage** — assign category and severity. If severity is `critical`, flag it in the next status message to the user so it's not missed.
3. **Work** — when someone starts on it, update status to `in-progress`. If the work requires a research doc, put it in `_Research/` and link from the `Source` column. If the work requires a plan, put it in `_Plan/<name>.md` and link from `Source`.
4. **Resolution** — when the code fix is committed, update status to `resolved`. Keep the issue open until it's verified.
5. **Verification** — after the fix is tested (usually on a fresh install), update status to `closed` and add a note about what was tested.
6. **Archive** — closed issues older than 30 days can be moved to `Issues-Archive.md` to keep this file tight.

## When an issue is NOT appropriate

Some things should NOT go in this tracker:

- **New features planned from scratch** — those go in `Backlog.md`. The issue tracker is for problems with existing behavior.
- **Conversation-level context** — "the user asked about X" is not an issue. Issues should be actionable technical work.
- **Questions for the user** — ask in conversation, don't file as issues.
- **Completed work with no outstanding concerns** — once a fix is verified, it doesn't need an ongoing tracker entry. Archive it.
