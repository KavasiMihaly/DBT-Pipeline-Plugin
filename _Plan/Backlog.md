# Backlog — dbt-pipeline-toolkit

Forward-looking work items and epics for this plugin. Follows the column schema required by the global user CLAUDE.md convention.

**Relationship to the issue tracker:** `Issues.md` captures **problems with existing behavior** (bugs, empirical verification needs, risks). This file captures **planned new work** (features, integrations, structural improvements). Some entries reference specific issues where the planned work is the fix.

| Backlog Item | Epic | Plan File | Research File | State |
|---|---|---|---|---|
| Fresh-install empirical verification of every claim in Finding 9 | Production readiness | (tbd) | `_Research/plugin-subagent-delegation.md` | Backlog |
| Build end-to-end smoke test that runs orchestrator on a 3-table sample dataset | Production readiness | (tbd) | — | Backlog |
| Write comprehensive plugin README covering install, configuration, invocation, troubleshooting | Documentation | (tbd) | — | Backlog |
| Investigate and fix `userConfig` install-time prompt behavior (see I-008) | Production readiness | (tbd) | — | Backlog |
| Build fallback skill-orchestrator architecture (in case `Task`-based delegation regresses) | Architectural resilience | (tbd) | `_Research/plugin-subagent-delegation.md` | Backlog |
| Refactor `skills/sql-connection/` into a proper library or promote to a real skill (see I-011) | Code hygiene | (tbd) | — | Backlog |
| Add CI check that verifies SKILL.md flag references match script argparse (see I-018) | Developer tooling | (tbd) | — | Backlog |
| Add `--strict` flag to `analyze_coverage.py` to separate reporting from enforcement (see I-017) | Code hygiene | (tbd) | — | Backlog |
| Build conference talk materials from `_Documentation/plugin_learnings.md` | Talk preparation | (tbd) | — | Backlog |

## Epics

**Production readiness** — everything required to claim the plugin works reliably on a fresh install. Covers empirical verification, end-to-end smoke tests, README documentation, and `userConfig` fixes.

**Documentation** — user-facing docs: README, troubleshooting guide, architecture diagrams, "how it works" explainers. Distinct from internal `_Documentation/plugin_learnings.md` which is developer/talk material.

**Architectural resilience** — work that hedges against future Claude Code changes that could break the current design. Primary focus: the "Not Planned" delegation path (Finding 6) and the fallback skill-orchestrator pattern.

**Code hygiene** — quality improvements that don't change behavior but make the codebase easier to maintain. Includes `sql-connection` refactor, `${CLAUDE_SKILL_DIR}` usage in SKILL.md, coverage script flag redesign.

**Developer tooling** — pre-commit hooks, CI checks, validation scripts. Catches regressions automatically instead of relying on human review.

**Talk preparation** — turning the plugin_learnings.md content into a conference presentation. Distinct from the plugin development work itself.

## Review cadence

- **Before every plugin release:** walk through Issues.md (specifically `empirical` + `critical` rows) and confirm each one has been tested on a fresh install
- **After every significant development session:** add any new discoveries to Issues.md or Backlog.md, whichever fits
- **Weekly (or whenever the tracker gets stale):** review `open` items, archive closed items older than 30 days, re-triage severity of items that have been open too long
