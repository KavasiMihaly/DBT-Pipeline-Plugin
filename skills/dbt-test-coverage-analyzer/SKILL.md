---
name: dbt-test-coverage-analyzer
description: Analyze dbt test coverage across all models and identify gaps. Calculate coverage percentages, find untested models, identify missing primary key and foreign key tests. Use when validating test coverage, ensuring data quality standards, or preparing for production deployment. Reports coverage by layer (staging, marts) and model type.
allowed-tools: Read Glob Grep
---

# Test Coverage Analyzer

Analyze test coverage across all dbt models to ensure data quality standards are met.

## Overview

This skill scans your dbt project to:
- Calculate test coverage percentage (target: 80%)
- Identify untested models
- Find models missing primary key tests (unique + not_null)
- Find models missing foreign key tests (relationships)
- Report coverage by layer (staging, intermediate, marts)
- Generate actionable recommendations

## Usage

### Basic Coverage Report

```bash
python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py"
```

Outputs:
- Overall test coverage percentage
- Coverage by layer (staging, marts)
- List of untested models
- Models missing critical tests

### Detailed Report with Recommendations

```bash
python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py" --detailed
```

Includes:
- All basic report information
- Specific missing tests per model
- Test recommendations
- Priority ranking (critical, high, medium)

### JSON Output for Automation

```bash
python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py" --format json
```

Returns structured JSON for CI/CD integration or further processing.

### Filter by Layer

```bash
# Analyze only staging models
python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py" --layer staging

# Analyze only marts (facts + dimensions)
python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py" --layer marts
```

## Coverage Targets

**Overall Target**: 80% of models have tests

**By Layer**:
- **Staging (stg_*)**: 100% - Every staging model must have PK tests
- **Facts (fct_*)**: 100% - PK + FK + critical measure tests required
- **Dimensions (dim_*)**: 100% - PK + natural key tests required
- **Intermediate (int_*)**: 70% - At least PK tests

**Critical Tests** (Must have):
- Primary keys: `unique` + `not_null`
- Foreign keys: `not_null` + `relationships`

## Report Interpretation

### Sample Output

```
=== dbt Test Coverage Report ===

Overall Coverage: 75.0% (45/60 models)
Target: 80% ⚠️  BELOW TARGET

Coverage by Layer:
  ├─ staging/    : 100.0% (15/15) ✓
  ├─ marts/      : 66.7%  (30/45) ⚠️
  │  ├─ facts    : 80.0%  (12/15)
  │  └─ dims     : 60.0%  (18/30)
  └─ intermediate: 0.0%   (0/0)   N/A

UNTESTED MODELS (15):
  Critical (5):
    ⚠️  fct_sales - Missing: PK tests, FK tests
    ⚠️  dim_customer - Missing: PK tests
    ⚠️  dim_product - Missing: PK tests
    ⚠️  fct_orders - Missing: PK tests, FK tests
    ⚠️  dim_date - Missing: PK tests

  High Priority (10):
    ⚠️  fct_revenue - Missing: FK tests to dim_customer
    ⚠️  dim_location - Missing: natural key tests
    ... (8 more)

RECOMMENDATIONS:
1. Add primary key tests (unique + not_null) to 5 models
2. Add foreign key tests (relationships) to 8 models
3. Add critical measure tests (not_null) to 3 fact tables
4. Current coverage: 75% → Target: 80% (Need 3 more models tested)
```

### Coverage Calculation

```
Coverage % = (Models with Tests / Total Models) × 100

Model "has tests" if:
- Has at least 1 generic test (unique, not_null, relationships, accepted_values)
- OR has at least 1 custom test (singular or generic)
```

## What This Skill Checks

### 1. Primary Key Tests
Every model should have a primary key with:
- `unique` test
- `not_null` test

### 2. Foreign Key Tests
For fact tables and models with foreign keys:
- `not_null` test on FK column
- `relationships` test linking to dimension

### 3. Critical Column Tests
For important columns:
- `not_null` on required measures
- `accepted_values` on categorical columns
- Custom tests for business rules

### 4. Model Documentation
Checks if models have:
- Description in schema.yml
- Column descriptions for keys

## Integration with CI/CD

### Pre-commit Hook
```bash
# .git/hooks/pre-commit
python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py" --format json > coverage.json
COVERAGE=$(jq -r '.overall_percentage' coverage.json)

if (( $(echo "$COVERAGE < 80" | bc -l) )); then
    echo "❌ Test coverage is $COVERAGE%, below 80% target"
    exit 1
fi
```

### GitHub Actions
```yaml
- name: Check dbt Test Coverage
  run: |
    python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py" --detailed
    python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py" --format json > coverage.json

- name: Fail if below target
  run: |
    COVERAGE=$(jq -r '.overall_percentage' coverage.json)
    if (( $(echo "$COVERAGE < 80" | bc -l) )); then
      echo "::error::Test coverage $COVERAGE% is below 80% target"
      exit 1
    fi
```

## Output Formats

### Human-Readable (Default)
- Formatted text with colors and symbols
- Easy to read in terminal
- Includes recommendations

### JSON
```json
{
  "overall_percentage": 75.0,
  "target_percentage": 80.0,
  "total_models": 60,
  "tested_models": 45,
  "untested_models": 15,
  "by_layer": {
    "staging": {"percentage": 100.0, "tested": 15, "total": 15},
    "marts": {"percentage": 66.7, "tested": 30, "total": 45}
  },
  "critical_gaps": [
    {
      "model": "fct_sales",
      "missing": ["pk_unique", "pk_not_null", "fk_customer", "fk_product"],
      "priority": "critical"
    }
  ],
  "recommendations": [
    "Add primary key tests to 5 models",
    "Add foreign key tests to 8 models"
  ]
}
```

### Markdown Report
```bash
python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py" --format markdown > coverage-report.md
```

Generates a markdown file suitable for:
- Pull request comments
- Documentation
- Project wikis

## When to Use

**Use this skill when**:
- ✅ Validating test coverage before PR merge
- ✅ Ensuring new models have proper tests
- ✅ Preparing for production deployment
- ✅ Auditing data quality standards
- ✅ Identifying testing gaps in existing project
- ✅ Implementing CI/CD quality gates

**Typical workflow**:
1. Developer creates new dbt models
2. Run `dbt-test-coverage-analyzer` to check coverage
3. Add missing tests based on recommendations
4. Re-run to verify 80% target met
5. Proceed with PR/deployment

## Limitations

**This skill does NOT**:
- ❌ Run the actual dbt tests (use `dbt test` for that)
- ❌ Validate test logic or correctness
- ❌ Check test execution results (pass/fail)
- ❌ Measure code quality beyond test presence

**This skill DOES**:
- ✅ Count which models have tests
- ✅ Identify missing test types
- ✅ Calculate coverage percentages
- ✅ Provide test recommendations

## Requirements

**Python Dependencies**:
- `pyyaml` - Parse schema.yml files
- `pathlib` - File system navigation
- Standard library only (no external tools required)

**dbt Project Requirements**:
- Valid dbt project structure
- Models in `models/` directory
- Schema files (schema.yml) in model directories

## Related Skills

- **dbt-runner**: Run dbt tests after adding them
- **dbt-test-writer agent**: Create comprehensive tests
- **dbt-orchestrator agent**: Coordinate model and test creation

## Examples

### Example 1: Check Coverage Before PR
```bash
# In PR workflow
python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py" --detailed

# Output shows gaps
# Add missing tests
# Re-check
python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py"

# Coverage now 85% ✓
# Proceed with PR
```

### Example 2: Focus on Marts Layer
```bash
# Check only marts coverage
python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py" --layer marts

# Shows facts at 80%, dims at 60%
# Focus on dimension tests
# Re-check marts
python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py" --layer marts

# All marts now at 90%+ ✓
```

### Example 3: CI/CD Integration
```bash
# Run in CI pipeline
python "$HOME/.claude/skills/dbt-test-coverage-analyzer\scripts\analyze_coverage.py" --format json > coverage.json

# Parse result
jq -r '.recommendations[]' coverage.json

# Fail build if below threshold
```

## Best Practices

1. **Run regularly**: Check coverage after adding new models
2. **Track over time**: Monitor coverage trends in project
3. **Use in CI/CD**: Automate coverage checks in pipelines
4. **Focus on critical models first**: Ensure facts and dimensions are fully tested
5. **Document exceptions**: If a model doesn't need tests, document why
6. **Combine with test execution**: Coverage + test results = complete quality picture

---

**Target**: 80% overall coverage
**Priority**: Critical for production deployments
**Frequency**: Run before every PR merge
