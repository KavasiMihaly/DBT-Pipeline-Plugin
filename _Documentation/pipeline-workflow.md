# dbt Pipeline Plugin — End-to-End Workflow

**Last updated:** 2026-04-21
**Applies to:** `dbt-pipeline-toolkit` plugin, orchestrator v2 (post I-057)

This document describes the complete pipeline that runs when a user invokes the orchestrator from a repo containing source CSV files. It is the authoritative process map — the orchestrator's `agent.md` is the implementation; this is the narrative.

## Audience

- **Plugin users** — understand what will happen before approving, and what to look for if something fails.
- **Plugin contributors** — understand how the pieces fit so a change to one stage doesn't silently break the contract the next stage depends on.
- **Future orchestrator agent** — this document is the map; `pipeline-design.md` is the evolving artifact.

## Invocation

```
claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator "Build a pipeline"
```

The orchestrator runs in the user's current working directory. That directory becomes the target repo. All paths throughout the workflow are relative to cwd unless stated absolute.

## User interaction budget

Exactly **two** interactive touch points. Everything else runs autonomously.

1. **Discovery Q&A** — 5 questions via `business-analyst` subagent (Stage 2)
2. **Design approval** — native plan mode with semantic model summary (Stage 4)

A third, conditional touch point: **deviation escalation** at Stages 8 and 9 if a builder can't satisfy its prompt. The user is asked *accept deviation* (update the plan to match reality) vs. *abort* (fix sources and re-run). This only fires on contract breaks — a clean build never hits it.

## The master document

All design decisions, plans, build outputs, and validation results live in a single evolving file: **`1 - Documentation/pipeline-design.md`**. Every stage reads it; most stages write to a specific section.

### Section ownership

| Section | Owner | When written |
|---|---|---|
| 1. Requirements | `business-analyst` direct | Stage 2 |
| 2. Source Inventory | orchestrator from data-explorer JSON | Stage 1/2 |
| 3. Source Relationship Map | orchestrator from data-explorer JSON | Stage 1/2 |
| 4. Architecture Decisions | orchestrator from architecture-setup JSON | Stage 5 |
| 5. Staging Layer Plan | orchestrator drafts, appends rows from staging-builder JSONs | Stage 3 + Stage 7 |
| 6. Dimension Plan | orchestrator drafts, merges dim-builder JSONs | Stage 3 + Stage 8 |
| 7. Fact Plan | orchestrator drafts, merges fact-builder JSONs | Stage 3 + Stage 9 |
| **8. Semantic Layer Plan** | **orchestrator drafts as user-facing contract** | **Stage 3** |
| 9. Test Strategy | `dbt-test-writer` direct | Stage 3 draft → Stage 10 fill |
| 10. Validation Results | `dbt-pipeline-validator` direct | Stage 11 |
| 11. Created Objects Registry | orchestrator updates after every create | Stages 6–9 |
| 12. Design Decisions Log | orchestrator appends throughout | All stages |

### Section 8 is special

Section 8 is **not a derived summary** of Sections 5-7. It is the user-facing semantic contract — the answer to "what questions will users analyze?" Sections 5-7 are its implementation (which sources to stage, which dims to build, which facts to grain how). Stage 4's approval summary leads with Section 8 so the user is evaluating semantic utility, not just table shapes.

## The 13 stages

### Pre-Stage — Connection Check

Run `configure.py --test-only` to verify the SQL Server connection. If it fails, ask the user for Azure SQL vs. local-SQL preset, run `configure.py --preset <choice>`, re-test. Do not proceed until the test passes.

**Why:** downstream scripts (load_data, profile_data, query_sql_server) fall back to `localhost` silently if env vars aren't set. Failing fast here saves debugging a late-stage Stage 6 load failure.

### Stage 0 — Source Discovery

Two atomic Bash calls:
- `find . -name "*.csv" -type f` → pick the folder with the most CSVs as `source_files_origin`. Zero CSVs fails hard.
- `ls dbt_project.yml` → exit 0 means **incremental mode** (existing project), non-zero means **fresh build**. Incremental skips Stage 5 scaffolding.

### Stage 1 — Source Profiling (parallel)

Fan out one `data-explorer` subagent per CSV (or one sequential agent if ≤3 files). Each invokes:

```
python "${CLAUDE_PLUGIN_ROOT}/skills/data-profiler/scripts/profile_data.py" --file <csv> --format json
```

The profiler writes `1 - Documentation/data-profiles/profile_<name>.json` for each source with column stats, PK candidates, data-type inference, date-format detection, and **header-presence detection**. Headerless CSVs get a `header.status: "missing"` flag with a `missing_header_row` quality issue attached — so downstream stages know these columns are synthetic placeholders.

Orchestrator collects the JSON envelopes and writes Sections 2-3 of the master doc.

### Stage 2 — Discovery Q&A (user touch point 1)

Spawn `business-analyst` subagent.

**If any profile has `header.status != "present"`**, BA must FIRST resolve the headers (WebSearch published data dictionary, confirm column names with user via `AskUserQuestion`, rewrite the profile JSON with verified names, flip `header.verified = true`) BEFORE asking the 5 discovery questions. Building on unverified synthetic column names is a hard-refused path.

Once headers are verified (or were never missing), BA asks 5 discovery questions — business goals, consumers, KPIs, time grain, known business rules. BA writes Section 1 directly.

### Stage 3 — Draft Proposed Data Model

**Think Section 8 first.** What will users analyze? What measures, dimensions, hierarchies, schema topology (single star vs. galaxy) does the semantic model need? These answer Section 1 directly.

Then derive:
- **Section 5 (Staging)** — one stg_ model per source table
- **Section 6 (Dimensions)** — each dim that Section 8 requires (customer, product, date, etc.), with natural key, SCD type, attribute list
- **Section 7 (Facts)** — each fact that Section 8 requires, with grain, FKs, measures, incremental strategy
- **Section 8.1–8.5** — fill in shared dims, schema topology decision, conformed-keys table, **full Mermaid ER diagram with actual entity names** (no placeholder `dim_customer` / `dim_product` leftover from template), semantic notes for `tmdl-scaffold` handoff
- **Section 9 (Tests)** — 80% coverage target, list of custom tests derived from Section 1 business rules

All rows in Sections 5-7 get `status: proposed` until builders complete them.

### Stage 4 — Plan Approval Gate (user touch point 2)

Native plan mode. The user sees a summary that **leads with the Semantic Model**:

```markdown
## Semantic Model (what users will analyze)
- Schema topology: {star | galaxy}
- Shared dimensions: ...
- Conformed keys: ...
- Role-playing: ...
- Key measures: ...
- ER diagram: {Mermaid from Section 8.4}

## Proposed Data Model (implementation of the semantic model above)
  Sources, Staging, Dimensions, Facts, Tests, Execution
```

The framing is deliberate: the user approves **the answers users will get**, and the physical model is a consequence. Revisions go back to Stage 3; approval sets `pipeline-design.md` Status to `Approved` and proceeds to Stage 5.

### Stage 5 — Project Scaffolding (fresh build only; skipped on incremental)

Foreground `dbt-architecture-setup` subagent. Runs `initialize_project.py` to create:

- Folder structure: `1 - Documentation/`, `2 - Source Files/`, `3 - Data Pipeline/`, `4 - Semantic Layer/`, `5 - Report Building/`, `6 - Data Exports/`
- dbt project: `dbt_project.yml`, `packages.yml` (`dbt_utils`), `profiles.yml`, `macros/date_spine.sql` (T-SQL-compatible, replaces `dbt_utils.date_spine` — see I-048)
- Python venv + `dbt-core` + `dbt-sqlserver`
- Git repo (needed for worktree isolation at Stages 8-9)
- `.gitignore` written FIRST (before `git add -A`) to prevent venv/packages leaks
- `.claude/settings.local.json` MERGED (not overwritten — see I-040) so the `pluginConfigs` written by `configure.py` survives

Post-scaffold, re-run `configure.py --test-only`. If it fails now but passed at Pre-Stage, the settings merge regressed — restore config before Stage 6.

### Stage 6 — Load Source Data

Orchestrator copies CSVs from `source_files_origin` to `2 - Source Files/` (uses `cp`, not `mv` — originals remain), then invokes:

```
python "${CLAUDE_PLUGIN_ROOT}/skills/sql-executor/scripts/load_data.py" --pattern "*.csv" --schema raw
```

The loader detects headerless CSVs via sibling profile JSON (I-046) and refuses to load unverified headers unless `--force-raw-load` is explicitly passed. Row counts go to Section 11.

### Stage 7 — Build Staging (sequential)

**Sequential, not parallel.** The first staging model is the canary: if source-specific quirks exist (date format misdetection, reserved-word collisions, EXEC() wrapper issues, column sanitization edge cases), they surface on model 1 — cheap to fix. Parallelizing early meant 19 models fail at once, which cost hours in the STATS19 retrospective.

For each source, spawn `dbt-staging-builder` in background. Prompt specifies which master-doc sections to read (Sections 1, 2-3, and the row in Section 5 for THIS model). Builder:
- Writes `stg_<source>__<entity>.sql` and its per-model schema YAML (`_stg_<source>__<entity>__schema.yml` — one YAML per model to enable worktree safety later)
- Bracket-quotes all column references (SQL Server reserved words)
- Defaults to `materialized: table` (EXEC() wrapper breaks views — I-027)
- Validates via `dbt parse` and `dbt run --select stg_<model>`
- Returns JSON envelope

Orchestrator appends row to Section 5 and Section 11 after each completion.

### Stage 8 — Build Dimensions (parallel fan-out, strict conformance gate)

All dim-builders spawn at once. Each runs in its own worktree (`isolation: worktree`) to avoid file-write collisions. Per-dim schema YAMLs (`_dim_<entity>__schema.yml`) guarantee no two builders touch the same file.

Each dim-builder reads Sections 1-6 AND Section 8, then runs **Step 0** before writing SQL:

1. Compare prompt parameters against the Section 6 row for this dim — NK, SCD type, attribute list, hierarchy.
2. Check each specified attribute exists in the source staging model (via profile JSON or staging column list).
3. On any mismatch: complete the build with what CAN be satisfied, then set `conforms_to_plan: false` and fill `deviations[]` with structured entries (`type`, `expected`, `actual`, `impact`).

Builder returns JSON envelope with `status`, `conforms_to_plan`, `deviations[]`, `build_status`, `errors[]`, `warnings[]`.

**Strict conformance gate:** orchestrator waits for all dim-builders, then scans every envelope for:
- `status != "success"`
- `conforms_to_plan == false`
- non-empty `deviations[]` or `errors[]`

Any hit → **HALT**. Log full context to Section 12. Invoke `AskUserQuestion`:
- **Accept deviation** → user confirms degraded build is acceptable; orchestrator updates Sections 6 and 8 to match reality; log acceptance in Section 12; proceed.
- **Abort** → pipeline stops; user revises sources or Section 8 target; restart.

Clean runs merge JSON envelopes into Section 6, update Section 11 (Dimensions), merge worktrees back to main (so Stage 9 can resolve `ref(dim_*)`).

**Why the gate:** the orchestrator is the single source of plan consistency. If a dim-builder silently drops a required attribute, the user's Power BI semantic layer lies. The gate catches this at the builder seam, with full context, before the user opens the PBIP.

### Stage 9 — Build Facts (parallel fan-out, strict conformance gate)

Same structure as Stage 8. Fact-builders read Sections 1-7 AND Section 8 (especially 8.3 conformed keys and 8.5 measures). Step 0 checks:

1. Prompt vs. Section 7 row (grain, FKs, measures, incremental strategy)
2. Each FK dim exists in Section 11 and uses the conformed-key formula from Section 8.3 (so joins will actually match)
3. Each measure corresponds to a numeric column in staging (check profile `data_type`)
4. Grain is enforceable (`order_id` is actually PK-unique in staging for "one row per order")

Deviation types include `missing_measure`, `missing_fk`, `grain_violation`, `measure_type_mismatch`, `conformed_key_mismatch`, `prompt_vs_section7_mismatch`.

Strict gate same as Stage 8. Merge envelopes into Section 7, update Section 11, merge worktrees.

### Stage 10 — Write Tests

Spawn `dbt-test-writer` in background. Reads Sections 1, 5-8 (requirements + all built models + semantic contract). Iterates until `analyze_coverage.py` reports ≥80% coverage. Runs `dbt test` to execute. Writes Section 9 (Test Strategy) directly — this is test-writer's only write target, explicitly not Section 8 (per I-049).

Coverage analyzer reads both `tests:` (dbt <1.8) and `data_tests:` (dbt ≥1.8) YAML keys (I-042) so no tests are silently missed.

### Stage 11 — Validate Pipeline

Spawn `dbt-pipeline-validator` in background. Runs:

```
python ... run_dbt.py build --full-refresh
python ... analyze_coverage.py --format json --target 80
```

Writes Section 10 with `Overall status`:
- `Validated` — all models built, all tests pass, coverage ≥80%
- `Build complete, coverage below target` — models built, tests pass, coverage <80%
- `Build Failed` — build or test failure
- `No Pipeline Found` — can't locate dbt project

### Stage 12 — Handoff Summary

Orchestrator sets the top-level `Status:` field in pipeline-design.md from Section 10's `Overall status` value:

| Section 10 says | Top-level Status |
|---|---|
| `Validated` | `Validated` |
| `Build complete, coverage below target` | `Building` |
| `Build Failed` | `Building` |

**If and only if** Section 10 reports `Validated`, run `pbip-from-dbt` to produce a `.pbip` skeleton in `4 - Semantic Layer/`. The skeleton has no measures, relationships, or visuals — user opens in Power BI Desktop and clicks Refresh to discover column metadata. This is a scaffolding courtesy, not a full semantic model migration.

Present final user-facing summary with:
- Pipeline status
- Model counts by layer
- Test coverage number
- PBIP path (if scaffolded)
- Any accepted deviations from Stage 8/9 gates (so user remembers they diverged from the original plan)

## Strict-conformance policy (the safety net)

The orchestrator is the single source of plan consistency: it drafts Sections 5-8 as a coherent set at Stage 3, then encodes each row of Sections 5-7 into the prompt for the relevant builder.

Builders are **strict enforcers at their own seam**. They don't re-derive the plan; they verify the orchestrator's prompt matches their own Section row and the available source data. If not, they emit structured deviations and the orchestrator halts.

This contract means:
- **A clean run never touches the user.** Prompts match Section rows, sources have what builders need, build succeeds silently, user sees the final handoff summary and an openable PBIP.
- **A degraded run always touches the user.** Any deviation triggers `AskUserQuestion` with full context. The user either accepts (updating the plan to match reality) or aborts.
- **There is no third state.** The pipeline cannot complete with a silent mismatch between the approved semantic model (Stage 4) and the delivered warehouse contents (Stage 11).

## Parallelism policy

| Stage | Strategy | Why |
|---|---|---|
| 1 profiling | parallel, one agent per CSV | independent reads, I/O-bound |
| 7 staging | **sequential** | compile-one-then-scale: catch source-specific quirks cheaply on model 1 |
| 8 dimensions | parallel with worktree isolation | independent writes to unique `_dim_<entity>__schema.yml` files |
| 9 facts | parallel with worktree isolation | same pattern, and they only run after dims are merged to main |
| 10 tests | single background agent | test-writer iterates across all models serially by design |
| 11 validate | single background agent | `dbt build --full-refresh` is one operation |

Worktrees require a git repo — initialized at Stage 5. If git is absent at Stage 8, parallel builders will fail.

## Atomic-Bash policy

Every Bash command issued anywhere in the plugin (orchestrator, spawned subagents, hook logic, SKILL.md examples) must be a single atomic operation. No `&&`, `||`, `;`, `|`, subshells, command substitution, backticks, or heredocs at the shell level.

**Why:** the plugin's `PreToolUse` hook (`approve-plugin-bash.py`) matches commands against a narrow allowlist per-subcommand. Compound expressions fall through to the default permission flow, which in background-subagent context means the tool call stalls silently (no interactive channel to answer the prompt). This is documented in depth in CLAUDE.md; it's the reason the orchestrator issues separate `git init`, `git add -A`, `git commit` calls rather than chaining them.

## Failure modes and escalations

| Failure | Stage | Handling |
|---|---|---|
| Connection test fails | Pre-Stage | Ask user for preset, re-configure, re-test |
| Zero CSVs found | 0 | Hard fail with message |
| Profile detects unverified headers | 1→2 | BA WebSearches + AskUserQuestion before discovery |
| User revises plan | 4 | Back to Stage 3 with user feedback |
| Staging model compile/run fails | 7 | First model failure = halt (canary); subsequent failures escalate per their JSON envelope |
| Dim builder deviation | 8 | Strict gate halts, AskUserQuestion (accept/abort) |
| Fact builder deviation | 9 | Strict gate halts, AskUserQuestion (accept/abort) |
| Test coverage <80% | 10 | Test-writer iterates until reached OR reports `below target` in Section 9 |
| dbt build failure | 11 | Validator writes `Build Failed` to Section 10; orchestrator reflects in top-level Status |

## File reference

| What | Where |
|---|---|
| This document | `_Documentation/pipeline-workflow.md` |
| Master design (per project) | `1 - Documentation/pipeline-design.md` |
| Orchestrator agent | `agents/dbt-pipeline-orchestrator/agent.md` |
| Builder agents | `agents/dbt-<staging\|dimension\|fact>-builder/agent.md` |
| Issues tracker | `_Plan/Issues.md` |
| Lessons learned | `CLAUDE.md` (plugin root) |
| Full-plugin review (snapshot) | `_Research/plugin-review-2026-04-21.md` |

## Related issues

- **I-049** — Test-writer Section 8→9 (critical, resolved 2026-04-21)
- **I-048** — `dbt_utils.date_spine` replaced with plugin T-SQL macro (high, resolved 2026-04-21)
- **I-046** — `load_data.py` headerless CSV handling (high, resolved 2026-04-20)
- **I-039** — Headerless CSV detection across profiler/BA/staging (critical, resolved 2026-04-19)
- **I-040** — `settings.local.json` merge (critical, resolved 2026-04-19)
- **I-057** — Semantic-contract guardrails documented in this file (high, resolved 2026-04-21)

See `_Plan/Issues.md` for the full tracker with all resolved and open items.
