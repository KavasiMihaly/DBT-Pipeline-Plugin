---
name: pbip-from-dbt
description: Generate an openable Power BI Project (PBIP) from a completed dbt pipeline. Reads pipeline-design.md Section 11 (Created Objects Registry) to discover dim_*/fct_* tables in SQL Server, reads project-config.yml for connection details, and produces a PBIP folder with one M-partition table per dim/fact, parameterised SqlEndpoint and Database expressions, and a blank report shell. No measures, relationships, or visuals — user builds those in Power BI Desktop after opening.
allowed-tools: Bash Read Write Edit Glob
---

# pbip-from-dbt

Generate a valid, openable Power BI Project (PBIP) folder from a completed `dbt-pipeline-orchestrator` build. The output is a **sources-only** PBIP — every `dim_*` / `fct_*` table produced by dbt gets wired up as an M-partition pointing at SQL Server, but no model logic is added. The user opens the `.pbip` in Power BI Desktop, clicks Refresh, and starts building from there.

## When to use

- A dbt pipeline has completed and tables exist in SQL Server
- You want a head-start PBIP with all sources pre-wired
- You want parameterised connections (SqlEndpoint + Database) so the same model can target dev/prod
- You do **not** yet need measures, relationships, or visuals (those are manual in Desktop)

Use `tmdl-scaffold` instead if you want a bare empty semantic model with no dbt context.

## Prerequisites

- `pipeline-design.md` exists and has Section 11 (Created Objects Registry) populated. Created by `dbt-pipeline-orchestrator`.
- `project-config.yml` exists with `database.server` and `database.name` (created by `dbt-architecture-setup`), or you pass `--server` / `--database` explicitly.
- Python 3.10+. `pyyaml` is optional — without it, the script falls back to a minimal regex parser for `project-config.yml`.
- Power BI Desktop (January 2025 or later) to open the generated PBIP.

**No SQL Server connection is made at scaffold time.** Column metadata is discovered by Power BI Desktop on first refresh.

## Usage

All invocations use `${CLAUDE_PLUGIN_ROOT}` so the skill works on any machine after a fresh plugin install — never hardcode a local `$HOME`-style path.

### Basic

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/pbip-from-dbt/scripts/build_pbip.py" --output "4 - Semantic Layer" --name "Sales Analytics"
```

Defaults:
- `--design-file "1 - Documentation/pipeline-design.md"`
- `--config-file "project-config.yml"`
- `--schema "dbo_analytics"`
- `--culture "en-GB"`
- `--include "dim_*,fct_*"`
- `--exclude "stg_*,raw_*"`

Output: `4 - Semantic Layer/Sales Analytics/` with `.pbip`, `.Report/`, `.SemanticModel/`.

### Override connection

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/pbip-from-dbt/scripts/build_pbip.py" --output "4 - Semantic Layer" --name "Sales Analytics" --server "myserver.database.windows.net" --database "SalesDW" --schema "dbo_analytics"
```

### Overwrite existing output

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/pbip-from-dbt/scripts/build_pbip.py" --output "4 - Semantic Layer" --name "Sales Analytics" --force
```

### Filter tables

Only facts:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/pbip-from-dbt/scripts/build_pbip.py" --output "4 - Semantic Layer" --name "Sales" --include "fct_*"
```

Everything in registry except a specific table:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/pbip-from-dbt/scripts/build_pbip.py" --output "4 - Semantic Layer" --name "Sales" --exclude "fct_logs,stg_*"
```

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--output` | Yes | — | Parent directory. Project folder is created inside. |
| `--name` | Yes | — | Project display name and folder name. |
| `--design-file` | No | `1 - Documentation/pipeline-design.md` | Path to pipeline-design.md. |
| `--config-file` | No | `project-config.yml` | Path to project-config.yml. |
| `--project-root` | No | `.` | Root for resolving design/config files. |
| `--server` | No | from config | SQL Server endpoint literal. |
| `--database` | No | from config | Database name literal. |
| `--schema` | No | `dbo_analytics` | Schema containing dim_*/fct_* tables. |
| `--culture` | No | `en-GB` | Model culture. |
| `--include` | No | `dim_*,fct_*` | Comma-separated include globs. |
| `--exclude` | No | `stg_*,raw_*` | Comma-separated exclude globs. |
| `--force` | No | False | Overwrite existing output folder. |
| `--verbose` | No | False | Show progress. |

## Output structure

```
<output>/<name>/
├── <name>.pbip
├── .gitignore
├── <name>.Report/
│   ├── .platform
│   ├── definition.pbir                        # byPath → ../<name>.SemanticModel
│   ├── definition/
│   │   ├── report.json
│   │   ├── version.json
│   │   └── pages/
│   │       ├── pages.json
│   │       └── 895a4d3c5c2b505a42a5/page.json
│   └── StaticResources/SharedResources/BaseThemes/CY26SU02.json
└── <name>.SemanticModel/
    ├── .platform
    ├── .pbi/editorSettings.json
    ├── definition.pbism
    └── definition/
        ├── database.tmdl                       # compatibilityLevel: 1600
        ├── model.tmdl                          # ref table entries for every dim/fct
        ├── expressions.tmdl                    # SqlEndpoint + Database parameters
        ├── cultures/<culture>.tmdl
        └── tables/
            ├── dim_customer.tmdl               # partition only, no columns
            ├── dim_product.tmdl
            └── fct_sales.tmdl
```

**Each table TMDL** contains only a parameterised M partition — no columns. Power BI Desktop auto-detects columns on the first refresh.

### Example generated `expressions.tmdl`

```tmdl
expression SqlEndpoint = "myserver.database.windows.net" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
	lineageTag: <guid>
	queryGroup: Parameters

	annotation PBI_NavigationStepName = Navigation

	annotation PBI_ResultType = Text

expression Database = "SalesDW" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
	lineageTag: <guid>
	queryGroup: Parameters

	annotation PBI_NavigationStepName = Navigation

	annotation PBI_ResultType = Text
```

### Example generated `tables/dim_customer.tmdl`

```tmdl
table dim_customer
	lineageTag: <guid>

	partition dim_customer = m
		mode: import
		queryGroup: Tables
		source = ```
				let
				  Source = Sql.Database(
				    #"SqlEndpoint",
				    #"Database"
				  ),
				  Data = Source
				    {
				      [
				        Schema = "dbo_analytics",
				        Item   = "dim_customer"
				      ]
				    }
				    [Data]
				in
				  Data
				```

	annotation PBI_NavigationStepName = Navigation

	annotation PBI_ResultType = Table
```

## Post-generation steps

1. **Open the `.pbip`** in Power BI Desktop (Jan 2025 or later).
2. **Click Refresh** in the ribbon. Power BI queries SQL Server using the parameters, discovers column metadata, and populates the field list.
3. **Set up relationships** in Model View (the skill does not create any).
4. **Add measures** in a `_Measures` table of your choice.
5. **Commit to git** — the project-level `.gitignore` excludes `localSettings.json` and `cache.abf`.

## How it works

### Inputs

| Source | What is read |
|--------|--------------|
| `pipeline-design.md` Section 11 | `dim_*` / `fct_*` table names under the Dimensions and Facts subheadings |
| `project-config.yml` `database.*` | `server`, `name`, `schema` (all override-able via CLI) |

### Template provenance

Static PBIP files (theme, report shell, page, database/model structure) were captured from a blank PBIP that Power BI Desktop saved in **April 2026** (compatibility level 1600, theme CY26SU02). See `_Research/pbip-from-dbt-research.md` for exact schema versions. If Power BI Desktop changes its output format, re-capture the blank PBIP and update files under `templates/`.

### What gets generated per run (not templated)

- `model.tmdl` — includes `ref table` for every dim/fct and two `queryGroup` declarations (Parameters, Tables)
- `expressions.tmdl` — `SqlEndpoint` and `Database` parameter expressions with literal values
- `tables/<name>.tmdl` — one per dim/fact with an M partition and `lineageTag`
- `.platform` (×2) — new `logicalId` GUIDs per build

### What is deliberately **not** generated

- Measures, calculated columns, hierarchies
- Relationships (FK tests from dbt are not consumed here)
- Columns inside tables (Desktop discovers these on refresh)
- A second `byConnection` variant of `.pbir` (this skill always uses `byPath`)

## Security and safety

- **Machine-specific files are never copied.** `localSettings.json` contains a `securityBindingsSignature` encrypted with one machine's user keys; `cache.abf` is binary local cache. Both are gitignored and regenerated by Desktop on first open.
- **New `logicalId` GUIDs per build.** Avoids Fabric item collisions if the same project is scaffolded twice.
- **No SQL connection at scaffold time.** The script does not authenticate to the database.
- **File encoding** is UTF-8 without BOM. `.json` files use CRLF to match Desktop's output; TMDL works with either.
- **Output path is resolved to an absolute path** and the script refuses to overwrite an existing project unless `--force` is passed.

## Troubleshooting

### "Section 11 (Created Objects Registry) not found in design file"

Ensure `pipeline-design.md` has the orchestrator's standard section layout. Run `dbt-pipeline-orchestrator` to populate it, or pass `--design-file` to a file that does.

### "No tables matched after filtering"

Check `--include` / `--exclude` patterns. The registry parser takes the first column of markdown tables under `### Dimensions` and `### Facts`. Hidden rows or non-standard headings won't be picked up.

### "SQL server not specified"

Either add `database.server` to `project-config.yml` or pass `--server` on the command line.

### PBIP opens but tables appear empty

Expected. Click Refresh in the ribbon. Power BI queries SQL Server via the parameters and discovers columns.

### PBIP fails to open in Power BI Desktop

Most common causes:
- Wrong `.pbir` `byPath` — the `.SemanticModel` folder must sit next to the `.Report` folder. Verify folder names match `<name>.Report` and `<name>.SemanticModel`.
- `.platform` `logicalId` is not a valid GUID — re-run the script (it generates fresh GUIDs).
- Schema version drift — Power BI Desktop may have bumped a schema since the templates were captured. Re-capture a blank PBIP into `templates/` and re-run.

## Workflow integration

This skill is the **optional final step** of `dbt-pipeline-orchestrator`. It runs inside Stage 12 (Handoff Summary), conditionally on the Stage 11 validator returning status `Validated`. If validation failed or coverage is below target, the orchestrator skips this skill and prints a warning instead.

The typical automated sequence:

1. Stage 0-9 — orchestrator builds + tests the dbt pipeline
2. Stage 11 — `dbt-pipeline-validator` writes Section 10 of `pipeline-design.md`
3. **Stage 12 — this skill runs IF `Overall status: Validated`:**

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/pbip-from-dbt/scripts/build_pbip.py" --output "4 - Semantic Layer" --name "{project_name}"
   ```

4. User opens the generated `.pbip` in Power BI Desktop and clicks Refresh.

**Manual invocation** is also supported when you want to rebuild the PBIP without re-running the full pipeline — same command, same defaults.

## Related

- **`tmdl-scaffold`** — minimal empty semantic model (no dbt context, no report shell)
- **`sql-server-reader`** — read-only introspection of SQL Server (can be used to verify dim/fct tables exist before running this skill)
- **`dbt-pipeline-orchestrator`** — produces the `pipeline-design.md` that this skill consumes (same plugin, invokes this skill in Stage 12)

## Reference

- Microsoft Learn — [PBIP overview](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview)
- Microsoft Learn — [TMDL overview](https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-overview)
- Research doc — `_Research/pbip-from-dbt-research.md`
- Plan doc — `_Plan/pbip-from-dbt-skill.md`
