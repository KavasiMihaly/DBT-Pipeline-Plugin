# dbt Pipeline Plugin — Process Map

How the `dbt-pipeline-toolkit` plugin turns a folder of raw CSV files into a tested, validated dbt star-schema pipeline on SQL Server, driven by one top-level orchestrator and eight specialist agents.

## High-Level Flow

```
User drops CSVs ──▶ Orchestrator ──▶ 13 stages (0-12) ──▶ Validated dbt pipeline
                        │
                        ├─ 2 user touch points (Q&A + plan approval)
                        └─ Single source of truth: pipeline-design.md
```

## Actors

| Actor | Role | Invocation mode |
|---|---|---|
| **User** | Provides CSVs, answers 5 discovery questions, approves plan | Interactive |
| **Orchestrator** (`dbt-pipeline-orchestrator`) | Main thread — coordinates all specialists, owns master doc | `claude --agent` |
| **business-analyst** | Reads profiles, asks 5 questions, writes Section 1 | Foreground subagent |
| **data-explorer** | Profiles CSVs in parallel, returns source inventory JSON | Background subagent (1 per CSV) |
| **dbt-architecture-setup** | Scaffolds folders, venv, dbt_project.yml, profiles.yml | Foreground subagent |
| **sql-executor** (skill) | Bulk-loads CSVs into `raw` schema | Bash-invoked |
| **dbt-staging-builder** | Builds `stg_*` models one-by-one | Background subagent (sequential) |
| **dbt-dimension-builder** | Builds `dim_*` models in parallel worktrees | Background subagent (parallel) |
| **dbt-fact-builder** | Builds `fct_*` models in parallel worktrees | Background subagent (parallel) |
| **dbt-test-writer** | Adds generic + custom tests, drives to 80% coverage | Background subagent |
| **dbt-pipeline-validator** | Runs `dbt build --full-refresh`, writes validation report | Background subagent |

## The 13 Stages

### Pre-Stage — Connection Check
- **Actor:** Orchestrator
- **Action:** `configure.py --test-only`; if no config, prompt user for Azure SQL or local SQL Server
- **Gate:** Must pass before Stage 0

### Stage 0 — Source Discovery
- **Actor:** Orchestrator
- **Input:** cwd with CSV files
- **Action:** `find . -name "*.csv"` → picks folder with most CSVs; `ls dbt_project.yml` → decides fresh vs incremental mode
- **Output:** `source_files_origin`, `mode = fresh | incremental`

### Stage 1 — Source Profiling (parallel)
- **Actor:** `data-explorer` (1 per CSV, fan-out)
- **Input:** Raw CSV files
- **Action:** `profile_data.py --file <csv> --format json` → writes `1 - Documentation/data-profiles/profile_<name>.json`
- **Output:** Column stats, PK candidates, data types, date formats, relationship hints
- **Merged into:** pipeline-design.md Sections 2 + 3

### Stage 2 — Discovery Q&A **(USER TOUCH POINT 1)**
- **Actor:** `business-analyst` (foreground)
- **Input:** All profile JSONs
- **Action:** Reads profiles, presents source-aware options, asks 5 standard questions in one `AskUserQuestion` call
- **Output:** Section 1 of pipeline-design.md (goals, consumers, metrics, time grain, target DB)

### Stage 3 — Draft Proposed Data Model
- **Actor:** Orchestrator
- **Input:** Section 1 + Sections 2-3
- **Action:** Maps sources → staging (`stg_*`), dimensions (`dim_*`, always add `dim_date`), facts (`fct_*`); detects galaxy schema; drafts Mermaid ER diagram
- **Output:** Sections 5, 6, 7, 8, 9 drafted as markdown tables

### Stage 4 — Plan Approval Gate **(USER TOUCH POINT 2)**
- **Actor:** Orchestrator → user via `ExitPlanMode`
- **Input:** Short summary of proposed model
- **Output:** Approve → proceed to Stage 5; Revise → edit Sections 5-7 and re-enter plan mode

### Stage 5 — Project Scaffolding *(skipped in incremental mode)*
- **Actor:** `dbt-architecture-setup` (foreground)
- **Action:** Creates numbered folders (0-7), venv, `dbt_project.yml`, `profiles.yml`, initial dbt packages
- **Gate:** `git init` + initial commit — required for worktree parallelism later

### Stage 6 — Load Source Data
- **Actor:** Orchestrator + `sql-executor` skill
- **Action:**
  1. `cp` CSVs to `2 - Source Files/` (keep originals in place)
  2. `load_data.py --pattern "*.csv" --schema raw`
  3. Verify row counts match Stage 1 profiles
- **Output:** `raw.<source_name>` tables in SQL Server + Section 11 registry rows

### Stage 7 — Build Staging Models (sequential)
- **Actor:** `dbt-staging-builder` (one at a time)
- **Why sequential:** Each stg_* model may surface source-specific issues (reserved words, date formats, EXEC quoting) — compile-one-then-scale
- **Action per model:** Write `stg_<source>__<entity>.sql` + schema.yml, run `dbt parse` + `dbt run --select stg_*`
- **Output:** One staging model + Section 5 row + Section 11 registry row

### Stage 8 — Build Dimensions (parallel fan-out)
- **Actor:** `dbt-dimension-builder` (parallel, one per dim)
- **Isolation:** Each builder runs in its own git worktree to avoid YAML collisions
- **Action:** Writes `dim_*.sql` + per-model schema YAML; runs `dbt run --select dim_*`
- **Output:** N dimension tables (SCD Type 1 default) + Section 6 + Section 11

### Stage 9 — Build Facts (parallel fan-out)
- **Actor:** `dbt-fact-builder` (parallel, one per fact)
- **Gate:** All worktrees from Stage 8 merged back to main first (so `ref(dim_*)` resolves)
- **Action:** Writes `fct_*.sql` with incremental strategy (default `delete+insert`), surrogate keys, FKs to dims
- **Output:** N fact tables + Section 7 + Section 11

### Stage 10 — Write Tests
- **Actor:** `dbt-test-writer`
- **Action:** Adds generic (PK/FK/not_null/accepted_values), custom, unit tests; iterates against `analyze_coverage.py --target 0` until ≥80%; runs `dbt test`
- **Output:** Test YAMLs + Section 9

### Stage 11 — Validate Pipeline
- **Actor:** `dbt-pipeline-validator`
- **Action:** `dbt build --full-refresh` end-to-end + final coverage report
- **Output:** Section 10 (validation results) + `validation-report-<date>.md`

### Stage 12 — Handoff Summary
- **Actor:** Orchestrator
- **Action:** Marks pipeline-design.md Status = Validated, appends Section 12 log, prints success summary
- **Next step suggestion:** Hand off to `tmdl-scaffold` for Power BI semantic layer

## Master Document: `pipeline-design.md`

A single file accumulates state across every stage. The orchestrator is the sole writer except for Sections 1, 9, 10 (written directly by BA, test-writer, validator — they have no parallel peers at their stage).

| Section | Owner | Written At |
|---|---|---|
| 1. Requirements | business-analyst | Stage 2 |
| 2. Source Inventory | Orchestrator | Stage 1 |
| 3. Source Relationship Map | Orchestrator | Stage 1 |
| 4. Architecture Decisions | Orchestrator | Stage 5 |
| 5. Staging Layer Plan | Orchestrator | Stages 3 + 7 |
| 6. Dimension Plan | Orchestrator | Stages 3 + 8 |
| 7. Fact Plan | Orchestrator | Stages 3 + 9 |
| 8. Semantic Layer Plan | Orchestrator | Stage 3 |
| 9. Test Strategy | test-writer | Stage 10 |
| 10. Validation Results | pipeline-validator | Stage 11 |
| 11. Created Objects Registry | Orchestrator | Stages 6, 7, 8, 9 |
| 12. Design Decisions Log | Orchestrator | All stages |

## Parallelism & Isolation Rules

- **Sequential:** Stages 0-6, 7 (staging one at a time), 10, 11, 12
- **Parallel fan-out:** Stage 1 (1 agent per CSV), Stage 8 (1 per dim), Stage 9 (1 per fact)
- **Isolation mechanism:** Git worktrees for builder agents — each specialist writes to its own worktree, orchestrator merges back before the next stage
- **Permission model:** Background subagents get `mode: "acceptEdits"` + plugin-level `PreToolUse` hook auto-approves plugin-internal Bash calls

## Guardrails & Gates

| Guardrail | Enforced Where |
|---|---|
| Connection must work | Pre-stage blocks Stage 0 |
| At least one CSV found | Stage 0 fails fast |
| Git repo initialized | Stage 5 — hard gate before Stage 8 |
| Row counts match profiles | Stage 6 — stop if mismatch |
| Dim worktrees merged before facts | Stage 9 start |
| 80% test coverage | Stage 10 loop target |
| All `dbt build` pass | Stage 11 acceptance |
| Atomic Bash commands only | Plugin-wide lint + hook allowlist |

## User Interaction Budget

Exactly **two** user touch points in the happy path:
1. **Stage 2** — 5 discovery questions via `AskUserQuestion`
2. **Stage 4** — plan approval via `ExitPlanMode`

Failure escalation is the only other time the orchestrator talks to the user.
