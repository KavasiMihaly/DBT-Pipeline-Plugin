# {{PROJECT_DISPLAY_NAME}}

**Project Type**: Data Engineering with dbt + SQL Server + Power BI
**Created**: {{CREATED_DATE}}
**Description**: {{PROJECT_DESCRIPTION}}

---

## Overview

This project uses the **`dbt-pipeline-toolkit`** Claude Code plugin for automated dbt pipeline construction. The plugin ships 9 specialized agents (orchestrator + 8 specialists) and 8 skills that collectively handle source profiling, project scaffolding, staging model generation, dimension/fact modeling, test writing, and end-to-end validation. It was installed from the `OneDayBI-Marketplace` marketplace. If you need to re-install or update, run `/plugin update dbt-pipeline-toolkit@OneDayBI-Marketplace` in Claude Code.

Plugin-shipped skills are visible in the `/skills` menu under the `dbt-pipeline-toolkit:` namespace (e.g., `dbt-pipeline-toolkit:data-profiler`, `dbt-pipeline-toolkit:dbt-runner`). Plugin-shipped agents are visible in `/agents` under a 3-part namespace (e.g., `dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator`). Skills and agents marked "locked by plugin" are managed by the plugin lifecycle — they live in the plugin cache and cannot be edited in place.

Plugin-internal script paths use the `${CLAUDE_PLUGIN_ROOT}` environment variable, which Claude Code substitutes with the plugin's absolute cache path at load time. You'll see this in agent and skill content as `python "${CLAUDE_PLUGIN_ROOT}/skills/<skill-name>/scripts/<file>.py"`.

---

## Bash commands must be atomic — no compound shell expressions

**Every Bash command run in this project must be a single atomic operation.** This applies both to Claude's direct tool calls and to any Bash commands written into generated scripts, documentation, or agent prompts.

**Forbidden operators in Bash commands:**
- `&&` (AND), `||` (OR), `;` (sequence)
- `|` (pipe), `|&` (stderr pipe)
- Background `&`
- Subshells `(...)`, command substitution `$(...)` or backticks
- Heredocs
- Non-essential redirects like `2>/dev/null`, `>/dev/null` — Claude Code's Bash tool handles exit codes and stderr natively

**Only exception:** operators fully inside a quoted string argument where the shell does not interpret them — e.g., `python foo.py --sql "SELECT a || b FROM t"` where `||` is SQL syntax.

**How to rewrite compound commands:**
- "run A then B" → two separate Bash tool calls
- "run A, if fails run B" → issue A, read exit code, conditionally issue B
- "pipe A to B" → issue A, read the output, issue B with extracted arguments (or write a Python script that does both and call it atomically)
- "many related commands" → write them into a Python script and call the script as one atomic invocation

**Why:** The `dbt-pipeline-toolkit` plugin ships a PreToolUse hook that auto-approves plugin-internal Bash commands for background subagents, but the hook matches **per atomic command**. Compound shell expressions either fall through to interactive permission prompts (which background subagents cannot answer, causing silent stalls) or bypass the narrow allowlist (a security risk). Atomic commands are also individually auditable in the transcript and produce localized error messages when something fails.

This rule is enforced across every file in this project — agent prompts, skill examples, generated scripts, and CI/CD workflows. If you find a compound shell expression anywhere in this repo, refactor it to atomic form before committing.

---

## CRITICAL: Agent Orchestration Rules

**YOU MUST DELEGATE TO SPECIALIZED AGENTS. DO NOT BUILD MODELS YOURSELF.**

### Entry Point: Use `dbt-pipeline-orchestrator` for End-to-End Work

For building a complete pipeline from source files, the user should invoke the orchestrator as the main agent:

```bash
claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator "Build a pipeline"
```

The orchestrator runs the full workflow autonomously (business-analyst Q&A + design approval are the only user gates). It coordinates all specialists and maintains a single-source-of-truth `1 - Documentation/pipeline-design.md` document.

**When the user asks you (non-orchestrator Claude) to do dbt work in this project:**

1. **ALWAYS use the Agent tool** to invoke the appropriate specialized agent
2. **NEVER write dbt SQL files directly** — delegate to the agent
3. **NEVER create schema YAML files directly** — delegate to the agent
4. **Suggest `dbt-pipeline-orchestrator`** if the user is starting a fresh build

### Mandatory Delegation Table

| User Request | YOU MUST USE | DO NOT |
|-------------|--------------|--------|
| "Build a whole pipeline from scratch" | `dbt-pipeline-orchestrator` (run via `claude --agent ...`) | Coordinate the specialists yourself |
| "Create staging model for X" | `dbt-staging-builder` agent via Agent tool | Write the SQL yourself |
| "Create dimension for X" | `dbt-dimension-builder` agent via Agent tool | Write the SQL yourself |
| "Create fact table for X" | `dbt-fact-builder` agent via Agent tool | Write the SQL yourself |
| "Add tests to X" | `dbt-test-writer` agent via Agent tool | Write the YAML yourself |
| "Validate the pipeline" | `dbt-pipeline-validator` agent via Agent tool | Run dbt commands yourself |
| "Profile the source tables" | `data-explorer` agent via Agent tool | Run data-profiler directly |
| Vague requirements | `business-analyst` agent via Agent tool | Guess at requirements |

### How to Invoke Agents

Use the Agent tool with `subagent_type` matching the agent name:

```
Agent tool with:
  subagent_type: "dbt-staging-builder"
  prompt: "Create staging model for the orders table in source X"
```

### Your Role When Not Using Orchestrator

- **You coordinate** — decide which agent to use
- **Agents specialize** — they do the actual model building
- **You verify** — check agent results and report to user

**Agents have access to reference materials, SQL style guides, and testing patterns that ensure consistency. If you build models yourself, you bypass these standards.**

## Master Design Document: `1 - Documentation/pipeline-design.md`

This is the single source of truth for pipeline design decisions. Every specialist agent reads it before starting work. It contains 10 sections:

1. Requirements (business goals, KPIs, consumers)
2. Source Inventory
3. Source Relationship Map
4. Architecture Decisions
5. Staging Layer Plan
6. Dimension Plan
7. Fact Plan
8. Test Strategy
9. Validation Results
10. Design Decisions Log

**Do not modify this file manually while specialists are running.** The orchestrator owns its writes. If working without the orchestrator, specialists write their own sections (1, 8, 9) and return JSON envelopes for the orchestrator-owned sections (2-7).

## Schema YAML Convention (Parallel-Safe)

Each model has its own schema YAML file — this enables safe parallel execution under `isolation: worktree`:

- **Staging:** `models/staging/{source}/_stg_{source}__{entity}__schema.yml`
- **Dimensions:** `models/marts/_dim_{entity}__schema.yml`
- **Facts:** `models/marts/_fct_{subject}__schema.yml`

Do NOT combine multiple models into a shared `schema.yml` — that breaks parallel builds.

---

## Available Agents

### dbt-pipeline-orchestrator (Entry Point)
Coordinates the full E2E pipeline build from empty repo to validated pipeline. Run via:
```bash
claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator "Build a pipeline"
```
Requires ONE discovery Q&A + ONE design approval, then runs autonomously.

### business-analyst
Requirements gathering and technical discovery.
```
"I need better sales reporting" (vague requests)
```

### data-explorer
Profiles source tables/CSVs, maps relationships, summarizes schemas.
```
"Profile all tables in the raw schema"
```

### dbt-staging-builder
Creates staging models (stg_*) from raw source data.
```
"Create staging models for the orders table"
```

### dbt-dimension-builder
Creates dimension tables (dim_*) with attributes and hierarchies.
```
"Create a customer dimension with SCD Type 2"
```

### dbt-fact-builder
Creates fact tables (fct_*) with measures at specific grain.
```
"Create a daily sales fact table"
```

### dbt-test-writer
Adds comprehensive dbt tests (generic, custom, unit, contracts).
```
"Add tests to the staging models"
```

### dbt-pipeline-validator
End-to-end validation of completed pipelines.
```
"Validate the sales pipeline end-to-end"
```

## Available Skills

| Skill | Purpose | Example |
|-------|---------|---------|
| `sql-executor` | Load CSV files into SQL Server | `/sql-executor --file data.csv --table raw.data` |
| `sql-server-reader` | Query SQL Server (read-only) | `/sql-server-reader --query "SELECT * FROM table"` |
| `data-profiler` | Profile tables for data quality | `/data-profiler --table raw.customers` |
| `dbt-runner` | Run dbt commands | `/dbt-runner run --select stg_*` |
| `dbt-docs-generator` | Generate dbt documentation | `/dbt-docs-generator generate` |
| `dbt-test-coverage-analyzer` | Analyze test coverage | `/dbt-test-coverage-analyzer` |
| `tmdl-scaffold` | Create Power BI TMDL projects | `/tmdl-scaffold` |

## Critical: Data Loading Behavior

### Column Name Sanitization

When loading CSV files via `sql-executor`, column names are automatically sanitized:

| Original CSV Header | Database Column |
|--------------------|-----------------|
| `Field Name` | `field_name` |
| `Code/Format` | `code_format` |
| `Sales (USD)` | `sales_usd` |
| `Order-ID` | `order_id` |
| `Profit %` | `profit_pct` |
| `Item #` | `item_num` |

**Rules:**
- Spaces → underscores
- Slashes → underscores
- Parentheses/brackets → removed
- Special chars: `&`→`and`, `%`→`pct`, `#`→`num`
- All lowercase

### Default Schema

Data loaded via `sql-executor` goes to **`{{DEFAULT_SCHEMA}}` schema** by default (not `dbo`).

### Always Verify Before Creating Models

```sql
-- Check actual column names
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '{{DEFAULT_SCHEMA}}' AND TABLE_NAME = 'your_table'
ORDER BY ORDINAL_POSITION;
```

Or use: `mcp__sql-server-mcp__get_table_schema`

## Data Profiles Location

**IMPORTANT**: Data profiles are stored in `1 - Documentation/data-profiles/`

The `data-profiler` skill automatically saves profiling results here. Profiles contain:
- Primary key candidates
- Column statistics (nulls, cardinality, data types)
- Recommended dbt tests
- Data quality issues

**Always check for existing profiles before creating models:**
```bash
ls "1 - Documentation/data-profiles/"
```

## Project Structure

```
{{PROJECT_DISPLAY_NAME}}/
├── .claude/
│   └── settings.local.json  # Auto-allows skills and safe bash commands
├── 0 - Architecture Setup/  # Environment and tooling setup
├── 1 - Documentation/       # Project docs and architecture
│   └── data-profiles/       # Data profiling results (JSON)
├── 2 - Source Files/        # CSV source data files
├── 3 - Data Pipeline/       # dbt project
│   ├── models/
│   │   ├── staging/         # stg_* models
│   │   ├── intermediate/    # int_* models (optional)
│   │   └── marts/           # dim_* and fct_* models
│   ├── tests/               # Custom tests
│   └── dbt_project.yml
├── 4 - Semantic Layer/      # Power BI TMDL files
├── 5 - Report Building/     # .pbip report files
├── 6 - Agentic Resources/   # Agent/skill configs
│   └── reference/           # Shared standards and examples
├── 7 - Data Exports/        # Query results
├── .venv/                   # Python virtual environment
└── CLAUDE.md                # This file
```

## Typical Workflow

### Option A: End-to-End via Orchestrator (Recommended)

Drop source CSVs into the repo, then run:
```bash
claude --agent dbt-pipeline-toolkit:dbt-pipeline-orchestrator:dbt-pipeline-orchestrator "Build a pipeline"
```

The orchestrator runs the full 12-stage workflow:
1. Source discovery (scans repo for CSVs)
2. Discovery Q&A (5 questions via business-analyst)
3. Source profiling (data-explorer)
4. Data model draft (staging + dims + facts + tests)
5. **Plan approval gate** (user reviews pipeline-design.md summary)
6. Architecture scaffolding (skipped if already scaffolded — incremental mode)
7. Load source data (sql-executor skill)
8. Build staging models (sequential)
9. Build dimensions (parallel, worktree-isolated)
10. Build facts (parallel, after dims merged)
11. Write tests (dbt-test-writer, 80% coverage target)
12. Validate (dbt-pipeline-validator, full dbt build + tests)

User input total: initial prompt + 5 questions + 1 approval.

### Option B: Manual Per-Agent Workflow

When you want to build one piece at a time (add a new source to an existing pipeline, fix a single model, etc.):

1. **Load source data**: Use `sql-executor` skill to load CSV files
2. **Verify columns**: Check actual column names in database
3. **Profile data**: **DELEGATE to `data-explorer` agent** (or use `data-profiler` skill directly)
4. **Build staging**: **DELEGATE to `dbt-staging-builder` agent** (use Agent tool)
5. **Build dimensions**: **DELEGATE to `dbt-dimension-builder` agent** (use Agent tool)
6. **Build facts**: **DELEGATE to `dbt-fact-builder` agent** (use Agent tool)
7. **Add tests**: **DELEGATE to `dbt-test-writer` agent** (use Agent tool)
8. **Validate pipeline**: **DELEGATE to `dbt-pipeline-validator` agent** (use Agent tool)

**Steps 4-8 REQUIRE agent delegation. Do not write dbt models directly.**

In manual mode, **specialists still read `1 - Documentation/pipeline-design.md`** before starting — keep it updated so they have context.

## Database Connection

- **Server**: localhost
- **Database**: {{DATABASE_NAME}}
- **Default Schema**: {{DEFAULT_SCHEMA}}
- **Authentication**: SQL Server Auth or Windows Auth
- **Driver**: ODBC Driver 17 for SQL Server

## Dependencies

- SQL Server (local instance)
- Python 3.12+ with pandas, pyodbc, sqlalchemy
- dbt-core with dbt-sqlserver adapter
- ODBC Driver 17 for SQL Server

## Git Workflow

**IMPORTANT**: Claude Code will NOT create git commits automatically. The user will handle all git operations.

## Repository Maintenance

### Periodic Cleanup Tasks

**Claude Code Temporary Files**:
Claude Code creates temporary `tmpclaude-*-cwd` files in the root directory during operations.

```bash
rm -f tmpclaude-*-cwd
```

The `-f` flag suppresses "no such file" errors without needing a shell redirect. Atomic command, single operation — consistent with this project's Bash command rules.

---

*This file serves as the persistent project context and is always loaded into Claude Code conversations. Keep it updated as the project evolves.*
