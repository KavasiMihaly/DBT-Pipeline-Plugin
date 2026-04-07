---
name: dbt-project-initializer
description: Initialize a new data engineering project with the complete folder structure, dbt configuration, Python virtual environment, and CLAUDE.md for agentic development. Use when starting a new analytics/BI project, creating a data pipeline repository, or scaffolding a dbt + Power BI project from scratch. Sets up everything needed for personal agents and skills to start implementing pipelines.
allowed-tools: Bash Read Write Edit Glob
---

# Project Initializer

Initialize a complete data engineering project with the standard folder structure, environment setup, and agentic development configuration.

## Overview

This skill creates a fully configured project structure for dbt + SQL Server + Power BI development workflows. It sets up:
- Numbered folder structure (0-7) for organized development
- Python virtual environment with all required packages
- dbt project configuration templates
- CLAUDE.md customized for the project
- Reference materials for agents

## Usage

### Interactive Mode (Recommended)

Run the initialization script interactively:

```bash
python "$HOME/.claude/skills/dbt-project-initializer\scripts\initialize_project.py" --target "C:\path\to\new\project"
```

The script will prompt for:
- **Project name**: Used for folder name and dbt project (e.g., "Sales Analytics")
- **Database name**: SQL Server database name (required — no default)
- **Database schema**: Default schema for raw data (default: "raw")
- **Description**: Brief project description for documentation

### Non-Interactive Mode

Provide all parameters via command line:

```bash
python "$HOME/.claude/skills/dbt-project-initializer\scripts\initialize_project.py" \
  --target "C:\path\to\new\project" \
  --name "sales_analytics" \
  --database "SalesDB" \
  --schema "raw" \
  --description "Sales performance analytics pipeline"
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--target` | Yes | - | Target directory for the new project |
| `--name` | No | Prompted | Project name (lowercase, underscores) |
| `--database` | Yes | — | SQL Server database name |
| `--schema` | No | "raw" | Schema for source data loaded via sql-executor |
| `--dbt-schema` | No | "dbo" | dbt default schema prefix (see Schema Convention below) |
| `--description` | No | Prompted | Project description |
| `--skip-venv` | No | False | Skip virtual environment creation |
| `--skip-deps` | No | False | Skip dependency installation |
| `--force`, `-f` | No | False | Force initialization even if target directory is not empty |

### Schema Convention

The project uses two schema parameters:

1. **`--schema`** (default: `raw`): Where sql-executor loads source CSV data
   - Source tables created in `raw` schema (e.g., `raw.carbon_intensity`)

2. **`--dbt-schema`** (default: `dbo`): dbt's default schema prefix
   - dbt concatenates this with model schemas to create final schema names:
   - Staging models → `dbo_staging`
   - Intermediate models → `dbo_intermediate`
   - Marts (facts/dims) → `dbo_analytics`

**Final Schema Structure:**
```
raw                    # Source data (sql-executor)
dbo_staging            # Staging views (stg_*)
dbo_intermediate       # Intermediate models (int_*)
dbo_analytics          # Marts - facts and dimensions (fct_*, dim_*)
```

## What Gets Created

```
ProjectName/
├── 0 - Architecture Setup/
│   ├── setup_environment.ps1    # Python environment setup
│   ├── project-config.yml       # Project configuration
│   └── README.md                # Setup documentation
├── 1 - Documentation/           # Project docs (empty)
├── 2 - Source Files/            # CSV source data (empty)
├── 3 - Data Pipeline/
│   ├── dbt_project.yml          # dbt project config
│   ├── packages.yml             # dbt packages (dbt_utils)
│   ├── profiles.yml.example     # Profile template
│   ├── models/
│   │   ├── staging/            # stg_* models
│   │   ├── intermediate/       # int_* models
│   │   └── marts/              # dim_* and fct_* models
│   ├── tests/                   # Custom tests
│   ├── macros/                  # Custom macros
│   ├── seeds/                   # Seed data
│   └── snapshots/               # SCD snapshots
├── 4 - Semantic Layer/          # Power BI TMDL (empty)
├── 5 - Report Building/         # Power BI reports (empty)
├── 6 - Agentic Resources/
│   └── reference/               # Copied from skill templates
│       ├── sql-style-guide.md
│       ├── testing-patterns.md
│       ├── tmdl-best-practices-guide.md
│       └── examples/
├── 7 - Data Exports/            # Query results (empty)
├── .venv/                       # Python virtual environment
├── .gitignore                   # Git ignore file
└── CLAUDE.md                    # Project-specific agent config
```

## Virtual Environment Setup

The skill automatically creates a Python 3.12 virtual environment and installs:

**dbt Dependencies**:
- dbt-core
- dbt-sqlserver
- dbt-fabric

**Data Processing**:
- pandas
- sqlalchemy
- pyodbc
- python-dotenv

## Post-Initialization Steps

After initialization, complete these steps:

1. **Configure dbt profile**:
   ```bash
   cd "3 - Data Pipeline"
   cp profiles.yml.example profiles.yml
   # Edit profiles.yml with your connection details
   dbt debug
   ```

2. **Install dbt packages**:
   ```bash
   dbt deps
   ```

3. **Load source data**:
   - Place CSV files in "2 - Source Files/"
   - Use `/sql-executor` skill to load into database

4. **Start development**:
   - Use dbt-staging-builder agent for first models
   - Use data-profiler skill to understand source data

## Integration with Agents

The generated CLAUDE.md configures the project for these agents:

| Agent | Purpose |
|-------|---------|
| dbt-staging-builder | Create stg_* models from sources |
| dbt-dimension-builder | Create dim_* tables |
| dbt-fact-builder | Create fct_* tables with incremental |
| dbt-test-writer | Add comprehensive dbt tests |
| dbt-pipeline-validator | End-to-end validation |
| business-analyst | Requirements gathering |

## Customization

### Modifying Templates

Template files are located in the skill's `templates/` directory:
- `CLAUDE.md.template` - Project CLAUDE.md template
- `dbt_project.yml.template` - dbt project template
- `setup_environment.ps1` - Environment setup script
- `gitignore.template` - .gitignore template

Edit these to customize default configurations.

### Adding Reference Materials

The skill copies reference materials from `Agents/reference/` in this repository. To add new reference materials:
1. Add files to `Agents/reference/`
2. They will be copied automatically during initialization

## Troubleshooting

### Python 3.12 Not Found

```powershell
# Install Python 3.12
winget install Python.Python.3.12

# Verify installation
py -3.12 --version
```

### Virtual Environment Issues

```powershell
# Force recreate
.\0 - Architecture Setup\setup_environment.ps1 -Force

# Skip venv, just update packages
.\0 - Architecture Setup\setup_environment.ps1 -SkipVenvCreation
```

### dbt Connection Issues

```powershell
cd "3 - Data Pipeline"
dbt debug

# Check ODBC driver
python -c "import pyodbc; print(pyodbc.drivers())"
```

## Related Skills

- **dbt-runner**: Execute dbt commands after project setup
- **sql-executor**: Load CSV data into SQL Server
- **data-profiler**: Profile source data before modeling
- **tmdl-scaffold**: Initialize Power BI semantic models
