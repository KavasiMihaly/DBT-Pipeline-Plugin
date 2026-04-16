# dbt Testing Examples

Comprehensive examples for the 4-level testing framework: Generic Tests, Custom Tests, Unit Tests, and Data Contracts.

---

## Level 1: Generic Tests

Generic tests are built-in dbt tests applied via YAML configuration.

### Primary Key Tests

**File**: `models/marts/schema.yml`

```yaml
version: 2

models:
  - name: fct_sales
    description: Sales transactions at order line item grain
    columns:
      - name: sales_key
        description: Surrogate key for sales transactions
        data_tests:
          - unique
          - not_null
```

**What it tests**:
- `unique`: No duplicate values
- `not_null`: No NULL values
- Together: Valid primary key constraint

---

### Foreign Key Tests

```yaml
models:
  - name: fct_sales
    columns:
      - name: customer_key
        description: Foreign key to dim_customer
        data_tests:
          - not_null
          - relationships:
              to: ref('dim_customer')
              field: customer_key
              severity: error

      - name: product_key
        description: Foreign key to dim_product
        data_tests:
          - not_null
          - relationships:
              to: ref('dim_product')
              field: product_key
```

**What it tests**:
- Referential integrity (all FKs exist in dimension)
- No orphan records in fact table
- Data quality at relationship level

---

### Accepted Values Tests

```yaml
models:
  - name: stg_erp__orders
    columns:
      - name: order_status
        description: Current status of the order
        data_tests:
          - accepted_values:
              values: ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled', 'refunded']
              severity: error

      - name: payment_method
        data_tests:
          - accepted_values:
              values: ['credit_card', 'debit_card', 'paypal', 'wire_transfer', 'cash']
```

**What it tests**:
- Values are within expected domain
- No invalid/unexpected values
- Categorical data validation

---

### Not Null Tests for Critical Columns

```yaml
models:
  - name: fct_sales
    columns:
      - name: sales_amount
        description: Total sales amount (quantity * unit_price)
        data_tests:
          - not_null

      - name: order_date
        description: Date of the order
        data_tests:
          - not_null

      - name: quantity
        data_tests:
          - not_null
```

**What it tests**:
- Critical measures always have values
- Required business logic fields populated
- Data completeness

---

### Minimum Test Coverage by Model Type

```yaml
# Staging Models
models:
  - name: stg_source__entity
    columns:
      - name: primary_key
        data_tests:
          - unique
          - not_null

# Fact Tables
models:
  - name: fct_subject
    columns:
      - name: fact_key
        data_tests:
          - unique
          - not_null

      - name: foreign_key
        data_tests:
          - not_null
          - relationships:
              to: ref('dim_entity')
              field: entity_key

      - name: measure
        data_tests:
          - not_null

# Dimensions
models:
  - name: dim_entity
    columns:
      - name: entity_key
        data_tests:
          - unique
          - not_null

      - name: natural_key
        data_tests:
          - unique
          - not_null
```

**Coverage Target**: Minimum 80% of models must have tests

---

## Level 2: Custom Tests

Custom tests are organization-specific validation rules written in SQL.

### Singular Tests (One Model)

**File**: `tests/fct_sales_amount_positive.sql`

```sql
-- Test that sales_amount is always positive

select
    sales_key,
    sales_amount
from {{ ref('fct_sales') }}
where sales_amount < 0
```

**How it works**:
- Returns rows that FAIL the test
- Test passes if query returns 0 rows
- Test fails if query returns any rows

---

**File**: `tests/fct_orders_dates_logical.sql`

```sql
-- Test that ship_date is after order_date

select
    order_key,
    order_date,
    ship_date
from {{ ref('fct_orders') }}
where ship_date < order_date
    or ship_date is null
```

---

**File**: `tests/dim_customer_email_format.sql`

```sql
-- Test that email addresses are valid format

select
    customer_key,
    email
from {{ ref('dim_customer') }}
where email not like '%_@_%.__%'
    or email is null
```

---

### Custom Generic Tests (Reusable)

**File**: `macros/test_is_percentage.sql`

```sql
{% macro test_is_percentage(model, column_name) %}

select *
from {{ model }}
where {{ column_name }} < 0
   or {{ column_name }} > 1

{% endmacro %}
```

**Usage**:
```yaml
models:
  - name: fct_conversion_rates
    columns:
      - name: conversion_rate
        data_tests:
          - is_percentage

      - name: bounce_rate
        data_tests:
          - is_percentage
```

---

**File**: `macros/test_is_recent.sql`

```sql
{% macro test_is_recent(model, column_name, days_ago=30) %}

select *
from {{ model }}
where {{ column_name }} < dateadd(day, -{{ days_ago }}, getdate())
   or {{ column_name }} is null

{% endmacro %}
```

**Usage**:
```yaml
models:
  - name: stg_api__events
    columns:
      - name: event_timestamp
        data_tests:
          - is_recent:
              days_ago: 7
```

---

**File**: `macros/test_no_duplicates_where.sql`

```sql
{% macro test_no_duplicates_where(model, column_name, where_clause) %}

with duplicates as (
    select
        {{ column_name }},
        count(*) as record_count
    from {{ model }}
    where {{ where_clause }}
    group by {{ column_name }}
    having count(*) > 1
)

select *
from duplicates

{% endmacro %}
```

**Usage**:
```yaml
models:
  - name: fct_sales
    data_tests:
      - no_duplicates_where:
          column_name: order_id
          where_clause: "order_status = 'completed'"
```

---

### Custom Test with dbt_utils

**File**: Using dbt_utils package

```yaml
models:
  - name: fct_revenue
    columns:
      - name: revenue_date
        data_tests:
          - dbt_utils.expression_is_true:
              expression: ">= '2020-01-01'"

      - name: revenue_amount
        data_tests:
          - dbt_utils.expression_is_true:
              expression: "> 0"
```

---

## Level 3: Unit Tests

Unit tests test individual models in isolation with mocked input data.

### Basic Unit Test

**File**: `tests/unit/test_calculate_revenue.sql`

```sql
{{
    config(
        tags=['unit-test']
    )
}}

{% call dbt_unit_testing.test('fct_revenue', 'Calculate revenue correctly') %}
    {% call dbt_unit_testing.mock_ref('stg_orders') %}
        select
            1 as order_id,
            100 as customer_id,
            50.00 as unit_price,
            2 as quantity,
            cast('2024-01-15' as date) as order_date
    {% endcall %}

    {% call dbt_unit_testing.expect() %}
        select
            1 as order_id,
            100 as customer_id,
            100.00 as revenue,
            cast('2024-01-15' as date) as order_date
    {% endcall %}
{% endcall %}
```

**What it tests**:
- Transformation logic (quantity * unit_price = revenue)
- Input: Mocked stg_orders data
- Expected Output: Calculated revenue
- No database reads during test

---

### Unit Test with Multiple Inputs

**File**: `tests/unit/test_customer_segmentation.sql`

```sql
{{
    config(
        tags=['unit-test']
    )
}}

{% call dbt_unit_testing.test('fct_customer_segments', 'Segment customers by order count') %}
    {% call dbt_unit_testing.mock_ref('stg_customers') %}
        select 1 as customer_id, 'John Doe' as customer_name
        union all
        select 2 as customer_id, 'Jane Smith' as customer_name
    {% endcall %}

    {% call dbt_unit_testing.mock_ref('stg_orders') %}
        select 1 as order_id, 1 as customer_id, 100.00 as amount
        union all
        select 2 as order_id, 1 as customer_id, 150.00 as amount
        union all
        select 3 as order_id, 1 as customer_id, 200.00 as amount
        union all
        select 4 as order_id, 2 as customer_id, 50.00 as amount
    {% endcall %}

    {% call dbt_unit_testing.expect() %}
        select
            1 as customer_id,
            'John Doe' as customer_name,
            'High Value' as segment,
            3 as order_count,
            450.00 as total_amount
        union all
        select
            2 as customer_id,
            'Jane Smith' as customer_name,
            'Low Value' as segment,
            1 as order_count,
            50.00 as total_amount
    {% endcall %}
{% endcall %}
```

**What it tests**:
- Complex business logic (segmentation rules)
- Multiple upstream dependencies mocked
- Aggregation logic
- Edge cases with different scenarios

---

### Unit Test for Edge Cases

**File**: `tests/unit/test_division_by_zero.sql`

```sql
{{
    config(
        tags=['unit-test']
    )
}}

{% call dbt_unit_testing.test('fct_conversion_rates', 'Handle division by zero') %}
    {% call dbt_unit_testing.mock_ref('stg_events') %}
        select 'page_a' as page_name, 100 as impressions, 10 as clicks
        union all
        select 'page_b' as page_name, 0 as impressions, 0 as clicks
        union all
        select 'page_c' as page_name, 50 as impressions, 0 as clicks
    {% endcall %}

    {% call dbt_unit_testing.expect() %}
        select 'page_a' as page_name, 0.10 as conversion_rate
        union all
        select 'page_b' as page_name, 0.00 as conversion_rate
        union all
        select 'page_c' as page_name, 0.00 as conversion_rate
    {% endcall %}
{% endcall %}
```

**What it tests**:
- Edge case: Division by zero
- Null handling
- Default values for edge conditions

---

### Unit Test for Date Logic

**File**: `tests/unit/test_fiscal_period.sql`

```sql
{{
    config(
        tags=['unit-test']
    )
}}

{% call dbt_unit_testing.test('dim_date', 'Calculate fiscal year correctly') %}
    {% call dbt_unit_testing.mock_ref('date_spine') %}
        select cast('2024-06-30' as date) as date_day
        union all
        select cast('2024-07-01' as date) as date_day
        union all
        select cast('2024-12-31' as date) as date_day
    {% endcall %}

    {% call dbt_unit_testing.expect() %}
        select cast('2024-06-30' as date) as date_day, 2024 as fiscal_year
        union all
        select cast('2024-07-01' as date) as date_day, 2025 as fiscal_year
        union all
        select cast('2024-12-31' as date) as date_day, 2025 as fiscal_year
    {% endcall %}
{% endcall %}
```

**What it tests**:
- Fiscal calendar logic
- Date calculations
- Boundary conditions (fiscal year rollover)

---

## Level 4: Data Contracts

Data contracts enforce explicit schemas at build time, preventing breaking changes.

### Basic Data Contract

**File**: `models/marts/schema.yml`

```yaml
version: 2

models:
  - name: fct_sales
    config:
      contract:
        enforced: true
    columns:
      - name: sales_key
        data_type: bigint
        constraints:
          - type: not_null
          - type: primary_key

      - name: customer_key
        data_type: bigint
        constraints:
          - type: not_null
          - type: foreign_key
            to: ref('dim_customer')
            to_column: customer_key

      - name: sales_amount
        data_type: decimal(18,2)
        constraints:
          - type: not_null
          - type: check
            expression: "sales_amount >= 0"

      - name: order_date
        data_type: date
        constraints:
          - type: not_null
```

**What it enforces**:
- Exact data types (no implicit conversions)
- NOT NULL constraints
- PRIMARY KEY constraints
- FOREIGN KEY constraints
- CHECK constraints (business rules)

---

### Data Contract with Multiple Constraints

```yaml
models:
  - name: dim_customer
    config:
      contract:
        enforced: true
    columns:
      - name: customer_key
        data_type: bigint
        constraints:
          - type: not_null
          - type: primary_key

      - name: customer_id
        data_type: varchar(50)
        constraints:
          - type: not_null
          - type: unique

      - name: email
        data_type: varchar(255)
        constraints:
          - type: not_null
          - type: check
            expression: "email LIKE '%@%.%'"

      - name: customer_status
        data_type: varchar(20)
        constraints:
          - type: not_null
          - type: check
            expression: "customer_status IN ('active', 'inactive', 'suspended')"

      - name: credit_limit
        data_type: decimal(18,2)
        constraints:
          - type: check
            expression: "credit_limit >= 0"
```

**Benefits**:
- Catch breaking changes at build time
- Explicit contracts between teams
- Prevent downstream data quality issues
- Version control for schema changes

---

### Data Contract with Versioning

```yaml
models:
  - name: fct_sales
    description: "Sales transactions (v2 - added tax_amount column)"
    config:
      contract:
        enforced: true
    columns:
      - name: sales_key
        data_type: bigint
        constraints:
          - type: not_null
          - type: primary_key

      - name: sales_amount
        data_type: decimal(18,2)
        constraints:
          - type: not_null

      # New column in v2
      - name: tax_amount
        data_type: decimal(18,2)
        constraints:
          - type: not_null
          - type: check
            expression: "tax_amount >= 0"
```

**When contract changes**:
- Build fails if schema doesn't match contract
- Forces explicit schema migration
- Prevents accidental breaking changes
- Documents schema evolution

---

## Testing Best Practices

### 1. Test Coverage Strategy

```yaml
# Staging Models
models:
  - name: stg_source__entity
    data_tests: [unique: primary_key, not_null: primary_key]

# Fact Tables
models:
  - name: fct_subject
    data_tests:
      - unique: fact_key
      - not_null: fact_key
      - relationships: all foreign keys
      - not_null: critical measures
      - custom: business rules

# Dimensions
models:
  - name: dim_entity
    data_tests:
      - unique: entity_key, natural_key
      - not_null: entity_key, natural_key
      - accepted_values: categorical columns
```

**Coverage Target**: 80% of models must have tests

---

### 2. Test Severity Levels

```yaml
models:
  - name: fct_sales
    columns:
      - name: sales_key
        data_tests:
          - unique:
              severity: error  # Fail build

      - name: customer_key
        data_tests:
          - relationships:
              to: ref('dim_customer')
              field: customer_key
              severity: error

      - name: discount_amount
        data_tests:
          - dbt_utils.expression_is_true:
              expression: ">= 0"
              severity: warn  # Don't fail build, just warn
```

---

### 3. Test Tags for Organization

```yaml
models:
  - name: fct_sales
    data_tests:
      - relationships:
          to: ref('dim_customer')
          field: customer_key
          tags: ['referential_integrity']

      - dbt_utils.expression_is_true:
          expression: "sales_amount > 0"
          tags: ['business_rules', 'critical']
```

**Run specific test types**:
```bash
dbt test --select tag:referential_integrity
dbt test --select tag:critical
```

---

### 4. Test Documentation

```yaml
models:
  - name: fct_sales
    columns:
      - name: sales_amount
        description: Total sales amount (quantity * unit_price)
        data_tests:
          - not_null:
              meta:
                test_description: "Ensures all sales transactions have an amount"
                failure_action: "Investigate source data quality"
```

---

## Running Tests

### Run all tests
```bash
dbt test
```

### Run tests for specific model
```bash
dbt test --select fct_sales
```

### Run tests for model and downstream
```bash
dbt test --select fct_sales+
```

### Run specific test type
```bash
dbt test --select test_type:generic
dbt test --select test_type:singular
dbt test --select tag:unit-test
```

### Run tests with fail-fast
```bash
dbt test --fail-fast
```

---

## When to Use Each Level

### Level 1: Generic Tests
- ✅ Every model (baseline)
- ✅ Primary/foreign keys
- ✅ Critical columns
- ✅ 80% of all models

### Level 2: Custom Tests
- ✅ Business rules
- ✅ Complex validation
- ✅ Organization-specific logic
- ✅ Reusable patterns

### Level 3: Unit Tests
- ✅ Complex transformations
- ✅ Edge cases
- ✅ Development/debugging
- ✅ Regression prevention

### Level 4: Data Contracts
- ✅ Critical production tables
- ✅ Multi-team dependencies
- ✅ Governed datasets
- ✅ Schema stability required

---

## Common Patterns

### Pattern: Freshness Tests

```yaml
sources:
  - name: erp
    tables:
      - name: orders
        freshness:
          warn_after: {count: 1, period: day}
          error_after: {count: 2, period: day}
```

### Pattern: Row Count Tests

```yaml
models:
  - name: fct_sales
    data_tests:
      - dbt_utils.recency:
          datepart: day
          field: order_date
          interval: 1
```

### Pattern: Comparison Tests

```yaml
models:
  - name: fct_revenue
    data_tests:
      - dbt_utils.equality:
          compare_model: ref('fct_revenue_v1')
```

---

**Remember**: Tests are not optional. Every model must have appropriate tests based on its role and criticality.
