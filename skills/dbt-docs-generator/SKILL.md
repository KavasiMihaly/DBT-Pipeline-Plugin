---
name: dbt-docs-generator
description: Generate and serve dbt documentation including model lineage, column descriptions, and test results. Use when creating dbt documentation, viewing model relationships, exploring data lineage, or sharing documentation with stakeholders. Supports generating static sites, serving locally, and exporting documentation artifacts.
allowed-tools: Bash Read Glob
---

# dbt Docs Generator

Generate comprehensive dbt documentation with model lineage, descriptions, and test results.

## Overview

This skill helps you:
- Generate dbt documentation (manifest.json, catalog.json, index.html)
- Serve documentation locally for interactive browsing
- Export static documentation sites for sharing
- View model lineage and dependencies
- Browse column-level documentation and tests
- Access compiled SQL for all models

## Usage

### Generate Documentation

```bash
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" generate
```

Runs `dbt docs generate` to create:
- `manifest.json` - Model metadata and lineage
- `catalog.json` - Column information from database
- `index.html` - Documentation site

**Output location**: `target/` directory

### Serve Documentation Locally

```bash
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" serve
```

Starts a local web server to browse documentation interactively.

**Features**:
- Interactive lineage graph (DAG)
- Click through model dependencies
- View compiled SQL
- Search models and columns
- Browse test results

**Access**: Opens browser to `http://localhost:8080`

**Stop server**: Press Ctrl+C

### Generate and Serve (One Command)

```bash
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" all
```

Runs both `generate` and `serve` in sequence.

### Export Static Site

```bash
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" export --output-dir ./docs-export
```

Exports a static HTML site that can be:
- Uploaded to web hosting (S3, Azure Blob, Netlify)
- Shared as a zip file
- Committed to repository (with caution)
- Served by any static web server

**Output**: Complete static site in specified directory

### Custom Port

```bash
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" serve --port 8081
```

Start docs server on a different port (useful if 8080 is in use).

### Generate Only Manifest (Fast)

```bash
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" generate --no-catalog
```

Generates only manifest.json, skips catalog.json (database query).

**Use when**:
- You only need lineage information
- Database connection is unavailable
- Faster generation needed

## What Gets Generated

### manifest.json
- Model definitions and configurations
- Model dependencies (lineage)
- Test definitions
- Macro definitions
- Source configurations
- Compiled SQL for all models

### catalog.json
- Column names and data types from database
- Column statistics (if available)
- Table row counts
- Database schema information

**Requires**: Active database connection

### index.html
- Documentation website
- Interactive lineage graph
- Search functionality
- Model browsing interface

## Documentation Content

### Model Documentation

For each model, documentation shows:
- **Description**: From schema.yml
- **Columns**: Names, types, descriptions
- **Tests**: All tests defined on model/columns
- **Dependencies**: Upstream models (sources, staging, etc.)
- **Dependents**: Downstream models that use this model
- **Compiled SQL**: The actual SQL that runs
- **Code**: The dbt model SQL template

### Lineage Graph (DAG)

Interactive graph showing:
- Visual representation of model dependencies
- Color-coded by layer (staging, marts)
- Click to navigate between models
- Zoom and pan capabilities
- Highlight paths between models

### Column Documentation

For each column:
- **Name**: Column name in database
- **Type**: Data type
- **Description**: From schema.yml
- **Tests**: Tests defined on this column

## Best Practices

### 1. Document Before Generating
Ensure models have descriptions in schema.yml:

```yaml
models:
  - name: fct_sales
    description: Daily sales transactions with customer and product information
    columns:
      - name: sales_key
        description: Surrogate primary key for sales transactions
        tests:
          - unique
          - not_null
```

### 2. Generate After Changes
Regenerate docs after:
- Adding new models
- Modifying model dependencies
- Adding/updating descriptions
- Adding/removing tests
- Schema changes

### 3. Review Before Sharing
Before sharing with stakeholders:
- Verify all models have descriptions
- Check that column descriptions are clear
- Ensure lineage graph is correct
- Remove any sensitive information

### 4. Version Control
**DO commit**:
- schema.yml files with descriptions
- README.md files

**DON'T commit** (add to .gitignore):
- target/ directory (too large, generated)
- manifest.json, catalog.json (generated)
- index.html (generated)

Exception: You may commit these for static site hosting.

### 5. CI/CD Integration
Generate docs in CI/CD pipeline:

```yaml
# GitHub Actions example
- name: Generate dbt Docs
  run: |
    dbt docs generate

- name: Deploy to GitHub Pages
  uses: peaceiris/actions-gh-pages@v3
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    publish_dir: ./target
```

## Output Interpretation

### Successful Generation

```
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" generate

Running: dbt docs generate
15:23:45  Running with dbt=1.7.4
15:23:46  Found 45 models, 120 tests, 3 sources
15:23:47
15:23:47  Concurrency: 4 threads
15:23:47
15:23:48  Building catalog
15:23:52  Catalog written to target/catalog.json
15:23:52  Done.

SUCCESS: Documentation generated
Files created:
  - target/manifest.json (523 KB)
  - target/catalog.json (145 KB)
  - target/index.html (89 KB)

View docs: python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" serve
```

### Catalog Generation Issues

If catalog generation fails:

```
WARNING: Could not generate catalog.json
Reason: Database connection failed

Documentation generated with manifest only.
Catalog.json will be missing column information.

To fix:
1. Check database connection in profiles.yml
2. Ensure models have been run (tables exist in database)
3. Run 'dbt run' to create tables, then regenerate docs
```

## Use Cases

### Use Case 1: Developer Documentation Review
```bash
# After creating new models
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" all

# Browse locally
# Verify lineage is correct
# Check model descriptions are clear
```

### Use Case 2: Stakeholder Presentation
```bash
# Generate clean docs
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" generate

# Export static site
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" export --output-dir ./stakeholder-docs

# Share folder with stakeholders
# Or upload to web hosting
```

### Use Case 3: PR Documentation Check
```bash
# In PR workflow
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" generate

# Check if manifest.json generated successfully
# Validates that all refs are correct
# Ensures no circular dependencies
```

### Use Case 4: Onboarding New Team Members
```bash
# Start docs server
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" serve

# New team member can:
# - Browse all models and their purpose
# - Understand data lineage
# - See what tests exist
# - View example SQL queries
```

## Integration with Agents

**dbt-orchestrator**: Generate docs after model creation workflow
**dbt-staging-builder**: Verify source documentation exists
**dbt-test-writer**: Document tests that were added
**All model builders**: Validate model descriptions are complete

## Troubleshooting

### Issue: Port Already in Use
```
Error: Port 8080 is already in use
```

**Solution**:
```bash
# Use different port
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" serve --port 8081
```

### Issue: Database Connection Failed
```
Error: Could not connect to database
```

**Solution**:
- Check profiles.yml configuration
- Verify database credentials
- Ensure database is accessible
- Use `--no-catalog` flag to skip catalog generation

### Issue: No Models Found
```
Error: No models found in project
```

**Solution**:
- Verify you're in the correct directory
- Check dbt_project.yml exists
- Ensure models/ directory has .sql files

### Issue: Circular Dependency
```
Error: Circular dependency detected
```

**Solution**:
- Review manifest.json for circular refs
- Check model dependencies
- Fix circular reference in models
- Regenerate docs

## Output Locations

**Default locations**:
```
target/
├── manifest.json       # Model metadata and lineage
├── catalog.json        # Column info from database
├── index.html          # Documentation website
├── graph.gpickle       # Dependency graph (binary)
└── run/                # Compiled SQL
```

**Exported site** (if using export):
```
docs-export/
├── manifest.json
├── catalog.json
├── index.html
└── [other static assets]
```

## Performance Notes

**Generation time**:
- Small projects (<50 models): 5-10 seconds
- Medium projects (50-200 models): 10-30 seconds
- Large projects (>200 models): 30-60 seconds

**Catalog generation** is the slowest part:
- Queries each model in database for schema
- Use `--no-catalog` to skip for faster generation

## Advanced Options

### Specify dbt Project Directory
```bash
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" generate --project-dir /path/to/project
```

### Specify Target Profile
```bash
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" generate --target prod
```

Uses `prod` target from profiles.yml instead of default.

### Generate with Warnings
```bash
python "$HOME/.claude/skills/dbt-docs-generator\scripts\generate_docs.py" generate --warn-error
```

Treats warnings as errors (stricter validation).

## Related Skills

- **dbt-runner**: Run models before generating docs
- **dbt-test-coverage-analyzer**: Check documentation coverage
- **dbt-orchestrator**: Coordinate docs generation in workflow

## When to Use

**Use this skill when**:
- ✅ Creating documentation for new models
- ✅ Updating documentation after changes
- ✅ Sharing project overview with stakeholders
- ✅ Onboarding new team members
- ✅ Validating model dependencies
- ✅ Reviewing data lineage
- ✅ Preparing for code review
- ✅ Creating static documentation site

**Typical workflow**:
1. Create/modify dbt models
2. Add descriptions to schema.yml
3. Run `generate_docs.py generate`
4. Run `generate_docs.py serve` to review
5. Share or export as needed

## Requirements

**Python Dependencies**:
- None (uses dbt CLI commands directly)

**dbt Requirements**:
- Valid dbt project (dbt_project.yml)
- dbt CLI installed and in PATH
- Database connection configured (for catalog)

**System Requirements**:
- Python 3.8+
- dbt Core 1.0+ or dbt Cloud CLI

---

**Best Practice**: Generate docs regularly and review lineage
**Target Audience**: Developers, analysts, stakeholders
**Update Frequency**: After every significant model change
