---
name: dbt-runner
description: Execute dbt commands (run, test, compile, docs, build, snapshot, seed, source freshness, deps, debug, list, clean) for analytics engineering workflows. Use when running dbt models, testing data quality, generating documentation, managing dbt projects, running snapshots, or implementing Slim CI patterns. Supports advanced model selection, full refresh, state comparison, and parallel execution.
allowed-tools: Bash Read Glob
---

# dbt Runner

Execute dbt commands in the current dbt project to build, test, and document data transformations.

## Overview

This skill provides a wrapper for common dbt CLI operations, making it easy to run analytics engineering workflows from Claude Code. It handles command execution, output capture, and error reporting.

## Usage

The skill is invoked through the Python script located in `scripts/run_dbt.py`.

### Run all models

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run
```

### Run specific model with downstream dependencies

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --select my_model+
```

### Test all models

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" test
```

### Test specific model

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" test --select my_model
```

### Compile without executing

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" compile
```

### Generate documentation

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" docs generate
```

### Serve documentation locally

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" docs serve
```

### Full refresh incremental models

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --full-refresh
```

## Additional Commands

### Run snapshots (Type 2 SCD)

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" snapshot
```

### Load seed files

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" seed
```

### Check source freshness

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" source freshness
```

### Install packages from packages.yml

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" deps
```

### Debug connection and project setup

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" debug
```

### Build (run + test in one command)

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" build --select my_model+
```

### List resources

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" list --select tag:daily
```

### Clean artifacts

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" clean
```

## Slim CI Pattern

Run only modified models and their downstream dependencies for efficient CI/CD:

```bash
# Assumes state files exist in target/
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --select state:modified+
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" test --select state:modified+
```

**Setup**:
1. Save production state: `dbt run && dbt docs generate`
2. Store artifacts (manifest.json) in cloud storage (S3, GCS, Azure Blob)
3. In CI, download production state and compare against current branch
4. Only run models that have changed

**Benefits**:
- 10x faster CI builds
- Lower compute costs
- Faster feedback loops
- Reduced pipeline execution time

## Common Patterns

### Run staging models only

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --select stg_*
```

### Run models and test them

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --select my_model && python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" test --select my_model
```

### Compile and show compiled SQL

```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" compile --select my_model
# Check target/compiled/[project]/models/ for compiled SQL
```

## Model Selection Syntax

The `--select` flag supports dbt's powerful selection syntax:

### Basic Selection
- `model_name`: Specific model
- `model_name+`: Model and all downstream dependencies
- `+model_name`: Model and all upstream dependencies
- `+model_name+`: Model and all dependencies (parents + children)
- `stg_*`: Pattern matching for model names

### By Tag
```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --select tag:daily
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --select tag:pii
```

### By Path
```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --select path:models/staging/salesforce
```

### By Resource Type
```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" test --select test_type:generic
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" test --select test_type:singular
```

### Union and Intersection
```bash
# Union (OR) - run both models and their children
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --select fct_sales+,dim_customer+

# Intersection (AND) - models that match both criteria
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --select fct_sales+,tag:daily
```

### Exclude
```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --exclude tag:deprecated
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" test --exclude test_type:data
```

### N Levels of Dependencies
```bash
# 2 levels of parents
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --select 2+fct_sales

# 1 level of children
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --select fct_sales+1
```

## Useful Flags

### Variables (--vars)
Pass variables at runtime:
```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --vars '{"start_date": "2024-01-01", "end_date": "2024-12-31"}'
```

### Full Refresh (--full-refresh)
Force full table rebuild for incremental models:
```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --full-refresh --select fct_sales
```

### Fail Fast (--fail-fast)
Stop on first failure:
```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" test --fail-fast
```

### Threads (--threads)
Control parallelism:
```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --threads 8
```

### Target (--target)
Run against specific target environment:
```bash
python "$HOME/.claude/skills/dbt-runner\scripts\run_dbt.py" run --target prod
```

## Environment

The script assumes:
- dbt is installed and accessible via `dbt` command
- Current working directory contains a dbt project (dbt_project.yml)
- profiles.yml is configured (either in project or ~/.dbt/)

## Error Handling

The script captures dbt output and returns:
- Exit code 0 on success
- Exit code 1 on failure with error details

## Best Practices

1. **Always compile before running** to check for SQL errors
2. **Test after running** to validate data quality
3. **Use model selection** for faster iteration during development
4. **Generate docs regularly** to keep documentation current
5. **Check compiled SQL** in target/compiled/ when debugging

## Integration with dbt Developer Agent

This skill is designed to be used by the dbt-developer agent for executing dbt operations. The agent can:
- Run models as part of development workflow
- Execute tests to validate data quality
- Generate documentation for stakeholders
- Compile models for SQL review

## Related Resources

See `6 - Agentic Resources/Skills/DBT Developer/` for reference materials on:
- dbt best practices
- Model patterns
- Testing strategies
- SQL optimization for SQL Server
