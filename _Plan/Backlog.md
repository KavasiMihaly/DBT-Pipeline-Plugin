# Backlog — dbt-pipeline-toolkit

Forward-looking work items and epics for this plugin. Follows the column schema required by the global user CLAUDE.md convention.

**Relationship to the issue tracker:** `Issues.md` captures **problems with existing behavior** (bugs, empirical verification needs, risks). This file captures **planned new work** (features, integrations, structural improvements). Some entries reference specific issues where the planned work is the fix.

| Backlog Item | Epic | Plan File | Research File | State |
|---|---|---|---|---|
| **Workshop demo readiness — 1-week sprint to demo-ready (Pre-Stage → Stage 7 live, Stage 12 fallback snapshot)** | **Workshop demo readiness** | `_Plan/workshop-readiness-2026-05-24.md` | — | **In Progress** |
| **Pre-Slice-1 P-1 — Apply `worktree.bgIsolation: "none"` setting via `configure.py` (closes I-064)** | Workshop demo readiness | `_Plan/workshop-readiness-2026-05-24.md:Pre-Slice-1 P-1` | `Plugins/Dataflow to Notebook Plugin/_Documentation/plugin_learnings.md` (N8) + `anthropics/claude-code` CHANGELOG.md v2.1.143 | In Progress |
| **Pre-Slice-1 P-2 — Scaffold-time copy of `reference/*` into project (closes I-065)** | Workshop demo readiness | `_Plan/workshop-readiness-2026-05-24.md:Pre-Slice-1 P-2` | `Plugins/Dataflow to Notebook Plugin/_Documentation/plugin_learnings.md` (N14) | In Progress |
| **Pre-Slice-1 P-3 — Restructure Stage 2 to three-sub-step parent-owned pattern (closes reopened I-063)** | Workshop demo readiness | `_Plan/workshop-readiness-2026-05-24.md:Pre-Slice-1 P-3` | `Plugins/Dataflow to Notebook Plugin/_Documentation/plugin_learnings.md` (N15) | In Progress |
| **Pre-Slice-1 P-4 — Tighten builder agent bodies + Stage 7 orchestrator prompts to prevent stray files (closes I-072)** | Workshop demo readiness | `_Plan/workshop-readiness-2026-05-24.md:Pre-Slice-1 P-4` | `Plugins/Dataflow to Notebook Plugin/_Documentation/plugin_learnings.md` (N16) | In Progress |
| Slice 1 — Discovery dry run + diagnostic baseline (Day 1) | Workshop demo readiness | `_Plan/workshop-readiness-2026-05-24.md:Slice 1` | — | Backlog |
| Slice 2 — Critical-bug fixes from discovery + I-047 audit + I-058 hardening (Days 2-3) | Workshop demo readiness | `_Plan/workshop-readiness-2026-05-24.md:Slice 2` | — | Backlog |
| Slice 3 — Stage 8-12 single-pass dry run + fallback snapshot capture (Day 4) | Workshop demo readiness | `_Plan/workshop-readiness-2026-05-24.md:Slice 3` | — | Backlog |
| Slice 4 — Confirmation dry runs + dress rehearsal + runbook (Days 5-6) | Workshop demo readiness | `_Plan/workshop-readiness-2026-05-24.md:Slice 4` | — | Backlog |
| Slice 5 — Workshop day execution (Day 7) | Workshop demo readiness | `_Plan/workshop-readiness-2026-05-24.md:Slice 5` | — | Backlog |
| Fresh-install empirical verification of every claim in Finding 9 | Production readiness | (tbd) | `_Research/plugin-subagent-delegation.md` | Backlog |
| Build end-to-end smoke test that runs orchestrator on a 3-table sample dataset | Production readiness | (tbd) | — | Backlog |
| Write comprehensive plugin README covering install, configuration, invocation, troubleshooting | Documentation | (tbd) | — | Backlog |
| Investigate and fix `userConfig` install-time prompt behavior (see I-008) | Production readiness | (tbd) | — | Backlog |
| Build fallback skill-orchestrator architecture (in case `Task`-based delegation regresses) | Architectural resilience | (tbd) | `_Research/plugin-subagent-delegation.md` | Backlog |
| Refactor `skills/sql-connection/` into a proper library or promote to a real skill (see I-011) | Code hygiene | (tbd) | — | Backlog |
| Add CI check that verifies SKILL.md flag references match script argparse (see I-018) | Developer tooling | (tbd) | — | Backlog |
| Add `--strict` flag to `analyze_coverage.py` to separate reporting from enforcement (see I-017) | Code hygiene | (tbd) | — | Backlog |
| Build conference talk materials from `_Documentation/plugin_learnings.md` | Talk preparation | (tbd) | — | Backlog |
| Audit `hooks/remove-worktree.py` for untracked-file destruction; add commit-and-merge-back step OR drop worktree isolation for builders (see I-064) | Architectural resilience | (tbd) | Sibling `Dataflow to Notebook Plugin/_Documentation/plugin_learnings.md` (N8) | Backlog |
| Build pre-ship audit suite — pytest gates: `gate_atomic_bash`, `gate_paths`, `gate_namespace`, `gate_skills_frontmatter`, `gate_plugin_manifest`, `gate_skill_md_flag_match` (supersedes I-018) | Cross-plugin learnings adoption | `_Plan/backlog-refresh-cross-plugin-learnings.md` | Sibling Dataflow plugin's gate suite | Backlog |
| Bundle a tiny 3-table sample dataset + `--dry-run` / `--sample` orchestrator flag so first-run smoke test needs no live DB | Cross-plugin learnings adoption | (tbd) | Sibling Dataflow plugin (N6) | Backlog |
| Add HIGH RISK / HUMAN REVIEW comment-block convention to builder agents (staging / dim / fact / test-writer) for ambiguous patterns instead of silent best-effort outputs | Cross-plugin learnings adoption | (tbd) | Sibling Fabric Migration `_Documentation/plugin_learnings.md` (HIGH RISK cells) | Backlog |
| Add `_Documentation/sql-pattern-backlog.md` — running catalog of T-SQL patterns that need future plugin support; builder agents auto-append unknown forms | Cross-plugin learnings adoption | (tbd) | Sibling Fabric Migration M-pattern backlog | Backlog |
| Add `dbt parse` / DAG-resolution gate before Stage 7 parallel staging fan-out so parallelization only runs on a clean dependency inventory | Cross-plugin learnings adoption | (tbd) | Sibling Fabric Migration `migration-design.md` Section 2 | Backlog |
| Trust-but-verify post-spawn artifact check: after each background `Task` returns, orchestrator atomically `ls` claimed output paths and HALTs on miss (extend I-057 from dim/fact to staging + test-writer) | Architectural resilience | (tbd) | Sibling Dataflow plugin N8 / N9 | Backlog |
| Dynamic question selection in business-analyst — skip irrelevant questions based on profile inventory (no CSVs → skip CSV question, etc.) | UX | (tbd) | Sibling Dataflow plugin (N4) | Backlog |
| Setup-CorpCertBundle helper script + README section for users behind corporate TLS interception — Norton, Zscaler, etc. (see I-067) | Production readiness | (tbd) | Agent memory (Norton TLS environment note) | Backlog |
| Document the "bug-class audit" policy formally in CLAUDE.md and reference it from Issues.md anti-patterns block (see I-066) | Documentation | (tbd) | Agent memory `feedback_audit_bug_class.md` | Backlog |
| Versioning + rollback story: tag releases on git, document how a user pins to an older version when the marketplace pulls latest | Production readiness | (tbd) | AI-plugins marketplace exploration | Backlog |
| Periodic audit of plugin-shipped agent restrictions (what fields beyond `hooks` / `mcpServers` / `permissionMode` get silently stripped from agent frontmatter) — extends I-016 | Architectural resilience | (tbd) | — | Backlog |
| Copy `reference/*` style guides into the project at scaffold time so background subagents can read them via project-local paths (see I-065) | Cross-plugin learnings adoption | (tbd) | Sibling Dataflow plugin (N14) | Backlog |
| Adopt `claude plugin tag` (v2.1.121) for releases — supersedes the "versioning + rollback story" row, drop custom tagging design | Upstream tooling adoption | (tbd) | Claude Code changelog v2.1.121 | Backlog |
| Document `claude plugin details <name>` (v2.1.139) in README so users can audit component inventory + per-session token cost before enabling | Upstream tooling adoption | (tbd) | Claude Code changelog v2.1.139 | Backlog |
| Refactor `hooks/approve-plugin-bash.py` registration in `plugin.json` to use `args: string[]` exec form (v2.1.139) — removes shell layer, fewer quoting bugs | Upstream tooling adoption | (tbd) | Claude Code changelog v2.1.139 | Backlog |
| Investigate `type: 'mcp_tool'` hooks (v2.1.118) — could let hooks invoke `sql-server-mcp:*` tools directly without spawning Python scripts | Upstream tooling adoption | (tbd) | Claude Code changelog v2.1.118 | Backlog |
| Investigate `PreCompact` hook (v2.1.130) — could block compaction during multi-stage orchestrator runs to preserve context | Upstream tooling adoption | (tbd) | Claude Code changelog v2.1.130 | Backlog |
| Investigate plugin dependency manifest (v2.1.143) — relevant if DBT plugin should declare a dependency on a sibling for shared reference materials | Upstream tooling adoption | (tbd) | Claude Code changelog v2.1.143 | Backlog |
| Re-test `hooks:`/`mcpServers:` in orchestrator frontmatter (see I-068) — if green, simplify main-thread agent config. **(PARTIALLY SUPERSEDED — see I-068: the `permissionMode` claim was invalid; the original "v2.1.116/120/121/130 lifted all three" basis was incorrect. `permissionMode` removal stands and call-site `mode: "acceptEdits"` is still required. Re-test scope reduced to `hooks:`/`mcpServers:` on the orchestrator's OWN frontmatter only.)** | Upstream tooling adoption | (tbd) | Claude Code changelog v2.1.116/117 (corrected) | Backlog |
| Re-test `worktree.bgIsolation: 'none'` (see I-069) — if green, close I-064 without writing a merge-back hook | Upstream tooling adoption | (tbd) | Claude Code changelog v2.1.143 | Backlog |
| ~~Re-test `AskUserQuestion` in background subagents (see I-070)~~ **(SUPERSEDED — see I-070: claim invalid. v2.1.146 does not exist in the changelog; the "Auto mode no longer suppresses AskUserQuestion" entry was a fabrication/misread. `AskUserQuestion` remains hard-restricted from any subagent spawned via the Agent tool. I-063's three-sub-step parent-owned pattern is the actual fix, not this re-test.)** | Upstream tooling adoption | (tbd) | — (changelog basis invalid) | Won't do |
| ~~Re-test `userConfig` optional-field handling (see I-071)~~ **(SUPERSEDED — see I-071: claim invalid. v2.1.119 was "/config settings persist," unrelated to userConfig. No changelog entry between v2.1.110 and v2.1.150 addresses userConfig install-time prompts. I-008 remains fully open at original severity; continue sidestepping via `configure.py`.)** | Upstream tooling adoption | (tbd) | — (changelog basis invalid) | Won't do |

## Epics

**Workshop demo readiness** *(new — active 2026-05-24)* — 1-week sprint to make Pre-Stage → Stage 7 demonstrably reliable on the demo laptop with full Road Safety Data, including two pre-baked fallback snapshots (`design-complete` at Stage 4, `end-result` at Stage 12). Driven by `_Plan/workshop-readiness-2026-05-24.md`. This epic supersedes routine Production readiness work for the duration of the sprint; routine work resumes post-workshop.

**Production readiness** — everything required to claim the plugin works reliably on a fresh install. Covers empirical verification, end-to-end smoke tests, README documentation, `userConfig` fixes, TLS troubleshooting, versioning story.

**Documentation** — user-facing docs: README, troubleshooting guide, architecture diagrams, "how it works" explainers, and the bug-class audit policy. Distinct from internal `_Documentation/plugin_learnings.md` which is developer/talk material.

**Architectural resilience** — work that hedges against future Claude Code changes that could break the current design. Primary focus: the "Not Planned" delegation path (Finding 6), fallback skill-orchestrator pattern, worktree-hook safety, trust-but-verify post-spawn checks, plugin-shipped restrictions audit cadence.

**Code hygiene** — quality improvements that don't change behavior but make the codebase easier to maintain. Includes `sql-connection` refactor, `${CLAUDE_SKILL_DIR}` usage in SKILL.md, coverage script flag redesign.

**Cross-plugin learnings adoption** — pattern-porting work where another plugin in this marketplace has battle-tested a solution we should mirror. Source plugins cited in each row's Research File column. Primary contributors so far: Dataflow to Notebook Plugin (`plugin_learnings.md` N1–N15) and Fabric Migration Test (`migration-design.md`, HIGH RISK / HUMAN REVIEW cells).

**Upstream tooling adoption** — re-tests and refactors driven by Claude Code release notes. Every time the changelog ships a feature that affects a design decision baked into this plugin (e.g. main-thread agent frontmatter now honored, `worktree.bgIsolation: 'none'`, `claude plugin tag`), file a row here with the version reference. Pair with an empirical `I-###` row in `Issues.md` for the re-test itself.

**Developer tooling** — pre-commit hooks, CI checks, validation scripts. Catches regressions automatically instead of relying on human review.

**UX** — improvements that reduce friction for the end-user during orchestration. Currently: tightening business-analyst question selection so the user touches the system fewer times.

**Talk preparation** — turning the plugin_learnings.md content into a conference presentation. Distinct from the plugin development work itself.

## Review cadence

- **Before every plugin release:** walk through Issues.md (specifically `empirical` + `critical` rows) and confirm each one has been tested on a fresh install
- **After every significant development session:** add any new discoveries to Issues.md or Backlog.md, whichever fits
- **Weekly (or whenever the tracker gets stale):** review `open` items, archive closed items older than 30 days, re-triage severity of items that have been open too long
- **After every cross-plugin learning exchange:** scan sibling plugin learnings folders for new patterns worth porting; add rows under the "Cross-plugin learnings adoption" epic
