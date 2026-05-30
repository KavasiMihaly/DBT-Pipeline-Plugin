# Workshop Discovery Baseline — 2026-05-29

Static source audit of the plugin in its current state (version 1.0.1), run from the dev machine.
Maps directly to Slice 1 of `_Plan/workshop-readiness-2026-05-24.md`. Live runtime verification
(Stage 2 hook firing, SQL connectivity, full Pre-Stage→Stage 7 dry run) is deferred to the
**test/demo machine** — not testable from here.

Method: bug-class greps across `agents/`, `skills/`, `hooks/` + `--help` smoke tests of the
core Python scripts. Each row ties back to a workshop issue.

## Pre-Slice-1 cross-plugin fixes — status

| Item | Issue | Check | Result | Effort left |
|---|---|---|---|---|
| **P-1** | I-064 | `bgIsolation` in `skills/sql-connection/scripts/configure.py` | ❌ **NOT DONE** — zero occurrences; configure.py does not write `worktree.bgIsolation: "none"` | ~10 min |
| **P-2** | I-065 | builder `agent.md` bodies reference `${CLAUDE_PLUGIN_ROOT}/reference/` | ❌ **NOT DONE** — 28 occurrences across all 4 builders; `initialize_project.py` does not copy `reference/*` into the project | ~1 h |
| **P-3** | I-063 | `AskUserQuestion` removed from BA frontmatter; Mode:analyze/write three-step pattern present | ❌ **NOT DONE** — BA still lists `AskUserQuestion` in `tools:` (line 11) and the whole agent.md assumes the BA calls it directly ("Runs in foreground only — AskUserQuestion requires an interactive…"). No analyze/write split. **CRITICAL — breaks money shot #1.** | ~3 h |
| **P-4** | I-072 | "save/write documentation to…" instructions in builder bodies | ❌ **NOT DONE** — all 3 builders still say "Save any project-level documentation to `1 - Documentation/` folder" (dimension:453, fact:365, staging:627) | ~30 min |

**All four Pre-Slice-1 fixes are still outstanding (~5 h).**

## Slice 2 critical bugs — status

| Issue | Check | Result |
|---|---|---|
| I-047 (bare `python scripts/` paths) | bare `scripts/*.py` refs in `agents/` + `skills/` | ✅ **APPEARS FIXED** — every reference now uses `${CLAUDE_PLUGIN_ROOT}/skills/.../scripts/`. Only remaining `python scripts/` hits are in `_Plan`/`_Research` docs describing the issue itself. TODO: confirm the `generate_docs.py` print-statement refs (I-047 cited lines 116,142) and close the issue. |
| I-046 (headerless CSV corruption) | `_find_sibling_profile`, `--no-header`, `--columns`, `--force-raw-load` in `load_data.py` | ✅ **APPEARS FIXED** — all three layers present and exposed in argparse. Pending live verification on a headerless source. |
| I-058 (unaliased-literal CREATE VIEW break) | aliasing guidance in `reference/sql-style-guide.md` + builder cross-refs | ⚠️ Guidance EXISTS and is cross-referenced from all 4 builders, BUT it's gated behind P-2 — until reference files are copied project-local, background builders can't read it (I-065). Effectively inert until P-2 lands. |
| I-002 (hook approves background Bash) | — | ⏳ NOT statically testable — requires live transcript on the demo machine. |

## Script smoke tests (`--help`)

| Script | Result |
|---|---|
| `dbt-runner/run_dbt.py` | Runs; imports OK. `--help` does not short-circuit the "no dbt project" check (minor UX nit). |
| `data-profiler/profile_data.py` | ✅ Clean help. |
| `sql-executor/load_data.py` | ✅ Clean help; I-046 flags present. |
| `sql-server-reader/query_sql_server.py` | ✅ Clean help. |
| `sql-connection/configure.py` | ✅ Clean help; presets azure/local/local-sql present. |

## New finding

| ID | Finding | Impact |
|---|---|---|
| **N-1** | Env-var mismatch: `profile_data.py` and `query_sql_server.py` read `--database` from **`DBT_DATABASE`**, while `load_data.py`, the MCP server, and userConfig all use **`SQL_DATABASE`**. | If the demo relies on userConfig (`CLAUDE_PLUGIN_OPTION_SQL_DATABASE` → `SQL_DATABASE`), the profiler and reader may not pick up the database name, forcing an explicit `--database` flag at Stage 2. Verify on the demo machine; file an `I-###` row if confirmed. |

## Docs-coherence fixes (claimed resolved 2026-05-29) — verified

| Issue | Result |
|---|---|
| I-075 (`tmdl-scaffold`) | ✅ Clean — only appears in issue-tracker descriptions. |
| I-076 (`Agents/reference/`) | ✅ Clean — only appears in issue-tracker descriptions. |

## Bottom line

- **Work remaining before the demo is essentially the entire Pre-Slice-1 block (~5 h).** None of the 4 cross-plugin fixes have been applied.
- Two Slice-2 bugs (I-046, I-047) already appear fixed in code — they just need their Issues.md status moved to `resolved` and live verification.
- The single biggest risk remains **I-063/P-3** (critical, ~3 h, breaks the BA discovery demo).
- Everything runtime (I-002 hook, SQL connectivity, full dry run, N-1 env var) must be verified on the **test/demo machine**, not here.
