# Plugin-wide Logical Consistency Review — 2026-04-21

Full audit of the `dbt-pipeline-toolkit` plugin across three layers (agents, skills, infrastructure). Three specialist Explore agents ran in parallel; this document merges their findings into a single prioritized list with Issues.md follow-up recommendations.

## Scope

- **Agents** (9): orchestrator, business-analyst, data-explorer, architecture-setup, staging-builder, dimension-builder, fact-builder, test-writer, pipeline-validator
- **Skills** (9 incl. sql-connection and pbip-from-dbt): SKILL.md vs scripts, cross-script interfaces, env-var precedence
- **Infrastructure**: `.claude-plugin/plugin.json`, `hooks/*.py`, `servers/src/*.ts`, `reference/`

## Executive summary

| Severity | Count | What |
|---|---|---|
| Critical (blocks pipeline) | **2** | Test-writer Section 8/9 contract break (A-001); `--warn-error` flag documented but not implemented (S-001) |
| High (wrong output but may complete) | **2** | `--target` missing from `export` subcommand (S-002); 2-part invocation in orchestrator `description:` (A-002 = I-010, already filed) |
| Medium (confusing, not breaking) | **5** | Pipeline-validator JSON envelope undocumented (A-005); Section 8 drafted pre-Section 6 (A-006); date_spine source not explained in ref (P-008); `tests:`/`data_tests:` mixed in ref (P-009); hook reason field missing in one branch (P-002) |
| Low (cleanup) | **4** | Section 1 phrasing ambiguous (A-003); staging materialization wording (P-010); dbt-runner wrapper docs (S-013); orchestrator dual-purpose `--target` (S-014 = I-017, already filed) |
| Passes (verified resolved issues hold) | **14** | Path-prefix fixes, env-var precedence, worktree collision, hook output format, merge_settings_local, column_name_mapping, profile sibling lookup, 3-part namespaces, 2-part skill namespaces, MCP auth modes, MCP env-var mapping, `__file__` usage appropriate, file encoding, dbt-runner CWD discovery |

---

## Critical findings (file Issues.md entries immediately)

### C-1 — Test-writer writes Section 8; orchestrator expects Section 9

**Proposed issue ID:** I-049
**Source findings:** A-001, A-004

**Evidence (verified by direct grep):**

| File | Line | Content |
|---|---|---|
| `agents/dbt-pipeline-orchestrator/agent.md` | 249 | `Also draft Section 8 (Semantic Layer Plan):` |
| `agents/dbt-pipeline-orchestrator/agent.md` | 265 | `Also draft Section 9 (test strategy): 80% coverage, standard PK/FK tests, custom tests derived from Section 1 business rules.` |
| `agents/dbt-pipeline-orchestrator/agent.md` | 572 | `Wait for completion. Verify test-writer wrote Section 9.` |
| `agents/dbt-test-writer/agent.md` | 29 | `When you finish, write your test strategy summary to Section 8 of ...` |

**Why it breaks:** Orchestrator reserves Section 8 for the Semantic Layer Plan (ER diagram, conformed keys, tmdl-scaffold handoff, Sections 8.1–8.5) and Section 9 for Test Strategy. The test-writer will **overwrite Section 8 with its test strategy**, destroying the semantic-layer content the orchestrator drafted at Stage 3 (line 249). Then Stage 10 (line 572) will search Section 9, find nothing, and assume zero tests were written — pipeline validation degrades.

**Fix:** Change `agents/dbt-test-writer/agent.md:29` from "Section 8" to "Section 9". Grep the full test-writer file for any other "Section 8" references and fix them. Add a regression test: pipeline-design.md template should document Section-to-agent ownership as a table at the top.

### C-2 — `dbt-docs-generator --warn-error` flag documented but not implemented

**Proposed issue ID:** I-050
**Source finding:** S-001

**Evidence:**

| File | Line | Content |
|---|---|---|
| `skills/dbt-docs-generator/SKILL.md` | 401 | `python "${CLAUDE_PLUGIN_ROOT}/skills/dbt-docs-generator/scripts/generate_docs.py" generate --warn-error` |
| `skills/dbt-docs-generator/scripts/generate_docs.py` | 337–360 | argparse defines `--project-dir`, `--target`, `--no-catalog`, `--port`, `--no-browser`, `--output-dir`. **No `--warn-error`.** |

**Why it breaks:** Any user copy-pasting the SKILL.md example hits `unrecognized arguments: --warn-error`. Same class of bug as I-018 ("LLM invented a plausible flag name") but this one shipped.

**Fix:** Either (a) add `--warn-error` to argparse and pass it through to dbt, or (b) delete the line from SKILL.md. (a) is preferable — dbt's own `--warn-error` is useful for CI gating.

---

## High findings

### H-1 — `generate_docs.py export` subcommand missing `--target` flag

**Proposed issue ID:** I-051
**Source finding:** S-002

Three of four subcommands (`generate`, `serve`, `all`) define `--target`; `export` (lines 358–362) does not. Asymmetric API — users will hit `unrecognized arguments: --target prod` only on the export path.

**Fix:** Add `export_parser.add_argument('--target', help='dbt target to use')`.

### H-2 — Orchestrator frontmatter `description:` still uses 2-part invocation form

Already tracked as **I-010** (open). A-002 re-confirms it's still present at `agents/dbt-pipeline-orchestrator/agent.md:11`. One-line fix; has been open since 2026-04-14.

---

## Medium findings

### M-1 — Pipeline-validator lacks JSON completion envelope spec (A-005)

All four builders (staging, dim, fact, test-writer) document a structured JSON envelope they return. Validator does not. Orchestrator Stage 11 (line 581) expects structured output to drive Stage 12 logic. Reading Section 10 prose works today, but the contract is implicit.

**Proposed issue ID:** I-052. Add a small JSON schema to validator's agent.md.

### M-2 — Orchestrator drafts Section 8 before Section 6 exists (A-006)

Stage 3 (line 249) tells the orchestrator to draft Section 8 (Semantic Layer Plan) with "dims from Section 6". But Section 6 is built by dim builders in Stage 8. Workflow is executable via "draft placeholder, replace later" but the instructions don't say so.

**Proposed issue ID:** I-053. Add "this is a placeholder — refine after Stage 8" note at line 249.

### M-3 — Reference example doesn't explain where `date_spine` macro comes from (P-008)

`reference/examples/dimension-models.md:243-247` uses bare `date_spine()` with a note explaining why it's not `dbt_utils.date_spine`. But it doesn't tell the reader that the macro is auto-installed by `initialize_project.py` into `3 - Data Pipeline/macros/date_spine.sql`. A user copying the example without running the initializer first will hit "macro not found".

**Proposed issue ID:** I-054. Two-sentence addition to the existing callout.

### M-4 — `reference/testing-patterns.md` mixes `tests:` and `data_tests:` (P-009)

Examples use both keys, with no indication that `data_tests:` is the dbt 1.8+ canonical form. I-042 fixed the analyzer to accept both, so nothing breaks — but users can't tell which is preferred.

**Proposed issue ID:** I-055. Add a preface paragraph: "Use `data_tests:` for dbt ≥ 1.8. `tests:` shown below is the legacy form and still accepted." Migrate newer examples to `data_tests:` only.

### M-5 — `validate-dbt-structure.py` emits `{"decision": "approve"}` without `reason` in one branch (P-002)

Line 27 omits the reason field; line 184 includes it. Not broken (reason is optional per Claude Code hook spec), but inconsistent.

**Proposed issue ID:** I-056 (or merge into an existing cleanup issue). One-line fix.

---

## Low findings (cleanup)

- **L-1 (A-003)** — `agents/dbt-pipeline-orchestrator/agent.md:74` phrasing about who writes Section 1 is ambiguous. Reword: "Section 1 is written exclusively by business-analyst; all other sections are written by orchestrator." No Issues.md entry needed — just fix inline if touched.
- **L-2 (P-010)** — `reference/examples/staging-models.md:283-290` says "staging should be views" then "REQUIRED on SQL Server: use table". Reword to be unambiguous. No Issues.md entry needed.
- **L-3 (S-013)** — dbt-runner SKILL.md shows `docs serve` / `docs generate` as if they were structured subcommands, but the script is a transparent wrapper passing args through to dbt. Minor clarity improvement.
- **L-4 (S-014)** — dbt-test-coverage-analyzer `--target` dual-purpose (reporting + enforcement) already tracked as **I-017**; SKILL.md documents the design intent. No new action needed.

---

## Resolved-issue verifications (positive findings)

The audit independently confirmed that the following resolved Issues.md entries are still correctly implemented in code:

| Verified | Finding ID | Issue |
|---|---|---|
| `${CLAUDE_PLUGIN_ROOT}` paths everywhere, no bare `scripts/` | A-007, S-010, S-011 | I-047, Finding 7 |
| 2-part skill namespace in agent frontmatter | A-008 | 2026-04-14 skills-namespacing finding |
| 3-part `subagent_type:` in orchestrator | A-009 | 2026-04-14 agent-namespacing finding |
| `approve-plugin-bash.py` uses `decision: approve` (not `hookSpecificOutput`) | P-003 | I-031 |
| `create-worktree.py` base-branch resolution cascade | P-004 | I-041 |
| `create-worktree.py` UUID fallback | P-005 | I-032 |
| MCP server 4 auth modes match plugin.json | P-006 | — |
| MCP server env-var mapping complete | P-007 | — |
| `merge_settings_local()` preserves `pluginConfigs` | S-003 | I-040 |
| Profile JSON includes `column_name_mapping` + `columns[].column_name` | S-004 | I-030 |
| Coverage analyzer reads both `tests:` and `data_tests:` | S-005 | I-042 |
| `pbip-from-dbt` reads 3 config shapes | S-006 | I-045 |
| SQL scripts env-var precedence (bare → CLAUDE_PLUGIN_OPTION_ → settings.local.json) | S-007, S-008 | I-029 |
| File encoding UTF-8 everywhere | S-009 | — |
| `load_data.py` sibling profile lookup | S-012 | I-046 |
| `run_dbt.py` venv auto-discovery + CWD-based project root | S-010 | I-023, I-028 |

---

## Recommended follow-up

1. **File I-049, I-050 immediately** (critical). I-049 is a one-line fix; I-050 is small (5–10 lines). Both have zero blast radius.
2. **File I-051–I-056** as a batch when convenient. None are blocking.
3. **Close I-010** on the same commit that fixes A-002 / I-010.
4. **Don't file anything for L-1 through L-4** — fix inline if touching those files, otherwise leave for natural cleanup.
5. **Add a CI/pre-commit grep regression check** (already suggested in I-018, I-021) covering three known bug classes:
   - `python scripts/` (bare paths, I-047 class)
   - `dbt_utils.date_spine` (I-048 class)
   - `Section N` mismatches between agent and orchestrator (A-001 class) — harder to grep mechanically; may need a small linter that diffs "who writes what Section" across all agents.
6. **Run a fresh-install smoke test** after I-049 and I-050 fixes to re-verify the critical paths.

---

## Audit caveats

- Memory records referenced by the audits (file:line citations) are point-in-time; the consolidator (me) independently verified the two critical findings (A-001 and S-001) against the current code before writing this document.
- The skills audit spot-checked encoding and env-var precedence rather than exhaustively reading every line of every script. If you want certainty on those, run a targeted grep pass.
- The infrastructure audit didn't compile-test the TypeScript MCP server; it verified source↔declaration alignment only.
