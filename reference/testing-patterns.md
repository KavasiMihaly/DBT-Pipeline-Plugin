# dbt Testing Patterns

Comprehensive guide to implementing the 4-level testing framework for data quality assurance.

---

## Testing Philosophy

**Goal**: Catch data quality issues as early as possible in the development lifecycle.

**Test Coverage Target**: Minimum 80% of models must have tests

**Testing Levels**:
1. **Level 1: Generic Tests** - Foundation (every model)
2. **Level 2: Custom Tests** - Organization-specific validation
3. **Level 3: Unit Tests** - Isolated transformation testing
4. **Level 4: Data Contracts** - Schema enforcement

---

## Level 1: Generic Tests (Foundation)

Generic tests are the baseline for all models. Every model must have appropriate generic tests.

### Primary Key Testing Strategy

**Every model needs a valid primary key**:

```yaml
models:
  - name: model_name
    columns:
      - name: primary_key_column
        tests:
          - unique
          - not_null
```

**Composite Primary Keys**:

```yaml
models:
  - name: fct_sales
    tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns:
            - order_id
            - line_number
```

### Foreign Key Testing Strategy

**Every foreign key needs referential integrity**:

```yaml
models:
  - name: fct_sales
    columns:
      - name: customer_key
        tests:
          - not_null
          - relationships:
              to: ref('dim_customer')
              field: customer_key
              severity: error
```

### Minimum Test Coverage by Model Type

#### Staging Models
```yaml
models:
  - name: stg_source__entity
    columns:
      - name: entity_id
        tests:
          - unique
          - not_null
```

**Required**:
- Primary key: unique + not_null

**Optional**:
- Critical columns: not_null
- Source freshness checks

#### Intermediate Models
```yaml
models:
  - name: int_subject__transformation
    columns:
      - name: composite_key
        tests:
          - unique
          - not_null
```

**Required**:
- Primary key: unique + not_null
- Foreign keys: relationships

#### Fact Tables
```yaml
models:
  - name: fct_subject
    columns:
      - name: fact_key
        tests:
          - unique
          - not_null

      - name: foreign_key
        tests:
          - not_null
          - relationships:
              to: ref('dim_entity')
              field: entity_key

      - name: measure_column
        tests:
          - not_null
```

**Required**:
- Primary key: unique + not_null
- All foreign keys: not_null + relationships
- Critical measures: not_null
- Business rule validation

#### Dimension Tables
```yaml
models:
  - name: dim_entity
    columns:
      - name: entity_key
        tests:
          - unique
          - not_null

      - name: natural_key
        tests:
          - unique
          - not_null
```

**Required**:
- Surrogate key: unique + not_null
- Natural key: unique + not_null
- Categorical columns: accepted_values

---

## Level 2: Custom Tests

Custom tests validate organization-specific business rules.

### Singular Test Patterns

**Pattern 1: Range Validation**

```sql
-- tests/fct_sales_amount_in_range.sql
-- Sales amounts should be between $0 and $1,000,000

select
    sales_key,
    sales_amount
from {{ ref('fct_sales') }}
where sales_amount < 0
   or sales_amount > 1000000
```

**Pattern 2: Date Logic Validation**

```sql
-- tests/fct_orders_dates_logical.sql
-- Ship date must be after order date

select
    order_key,
    order_date,
    ship_date
from {{ ref('fct_orders') }}
where ship_date < order_date
   or ship_date is null
```

**Pattern 3: Referential Orphans**

```sql
-- tests/fct_sales_no_orphan_customers.sql
-- All customers in sales must exist in customer dimension

select distinct
    fct_sales.customer_key
from {{ ref('fct_sales') }} as fct_sales
left join {{ ref('dim_customer') }} as dim_customer
    on fct_sales.customer_key = dim_customer.customer_key
where dim_customer.customer_key is null
```

**Pattern 4: Business Rule Validation**

```sql
-- tests/fct_revenue_matches_detail.sql
-- Revenue summary must match detail sum

with

summary as (
    select
        sum(revenue_amount) as total_revenue
    from {{ ref('fct_revenue_summary') }}
),

detail as (
    select
        sum(line_amount) as total_revenue
    from {{ ref('fct_revenue_detail') }}
)

select
    abs(summary.total_revenue - detail.total_revenue) as revenue_difference
from summary
cross join detail
where abs(summary.total_revenue - detail.total_revenue) > 0.01
```

### Custom Generic Test Patterns

**Pattern 1: Percentage Validation**

```sql
-- macros/test_is_percentage.sql
{% macro test_is_percentage(model, column_name) %}

select *
from {{ model }}
where {{ column_name }} < 0
   or {{ column_name }} > 1
   or {{ column_name }} is null

{% endmacro %}
```

**Pattern 2: Recency Validation**

```sql
-- macros/test_is_recent.sql
{% macro test_is_recent(model, column_name, days_ago=7) %}

select *
from {{ model }}
where {{ column_name }} < dateadd(day, -{{ days_ago }}, getdate())
   or {{ column_name }} is null

{% endmacro %}
```

**Pattern 3: Email Format Validation**

```sql
-- macros/test_valid_email.sql
{% macro test_valid_email(model, column_name) %}

select *
from {{ model }}
where {{ column_name }} not like '%_@_%.__%'
   or {{ column_name }} is null
   or len({{ column_name }}) < 5

{% endmacro %}
```

**Pattern 4: No Duplicates with Conditions**

```sql
-- macros/test_no_duplicates_where.sql
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

select * from duplicates

{% endmacro %}
```

---

## Level 3: Unit Tests

Unit tests validate transformation logic in isolation with mocked data.

### Unit Test Patterns

**Pattern 1: Simple Calculation**

```sql
-- tests/unit/test_revenue_calculation.sql
{{
    config(tags=['unit-test'])
}}

{% call dbt_unit_testing.test('fct_revenue', 'Calculate revenue = quantity * price') %}
    {% call dbt_unit_testing.mock_ref('stg_sales') %}
        select 1 as sale_id, 10 as quantity, 25.50 as unit_price
        union all
        select 2 as sale_id, 5 as quantity, 100.00 as unit_price
    {% endcall %}

    {% call dbt_unit_testing.expect() %}
        select 1 as sale_id, 255.00 as revenue
        union all
        select 2 as sale_id, 500.00 as revenue
    {% endcall %}
{% endcall %}
```

**Pattern 2: Aggregation Logic**

```sql
-- tests/unit/test_customer_aggregation.sql
{{
    config(tags=['unit-test'])
}}

{% call dbt_unit_testing.test('fct_customer_metrics', 'Aggregate customer orders') %}
    {% call dbt_unit_testing.mock_ref('stg_orders') %}
        select 100 as customer_id, 50.00 as amount, cast('2024-01-15' as date) as order_date
        union all
        select 100 as customer_id, 75.00 as amount, cast('2024-02-20' as date) as order_date
        union all
        select 200 as customer_id, 30.00 as amount, cast('2024-01-10' as date) as order_date
    {% endcall %}

    {% call dbt_unit_testing.expect() %}
        select 100 as customer_id, 2 as order_count, 125.00 as total_amount
        union all
        select 200 as customer_id, 1 as order_count, 30.00 as total_amount
    {% endcall %}
{% endcall %}
```

**Pattern 3: Edge Cases (NULL Handling)**

```sql
-- tests/unit/test_null_handling.sql
{{
    config(tags=['unit-test'])
}}

{% call dbt_unit_testing.test('fct_sales', 'Handle NULL discounts') %}
    {% call dbt_unit_testing.mock_ref('stg_sales') %}
        select 1 as sale_id, 100.00 as amount, 10.00 as discount
        union all
        select 2 as sale_id, 100.00 as amount, null as discount
    {% endcall %}

    {% call dbt_unit_testing.expect() %}
        select 1 as sale_id, 90.00 as net_amount
        union all
        select 2 as sale_id, 100.00 as net_amount
    {% endcall %}
{% endcall %}
```

**Pattern 4: Date Calculations**

```sql
-- tests/unit/test_fiscal_period.sql
{{
    config(tags=['unit-test'])
}}

{% call dbt_unit_testing.test('dim_date', 'Calculate fiscal year (starts July 1)') %}
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

### When to Write Unit Tests

✅ **Write unit tests for**:
- Complex business logic
- Calculation validation
- Edge case handling
- Macro functionality
- Regression prevention

❌ **Don't write unit tests for**:
- Simple SELECT statements
- Direct staging transformations
- Models already covered by integration tests

---

## Level 4: Data Contracts

Data contracts enforce schemas at build time, preventing breaking changes.

### Data Contract Patterns

**Pattern 1: Critical Fact Table**

```yaml
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
```

**Pattern 2: Dimension with Constraints**

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

      - name: customer_status
        data_type: varchar(20)
        constraints:
          - type: not_null
          - type: check
            expression: "customer_status IN ('active', 'inactive', 'suspended')"

      - name: email
        data_type: varchar(255)
        constraints:
          - type: check
            expression: "email LIKE '%@%.%'"
```

**Pattern 3: Versioned Contracts**

```yaml
models:
  - name: fct_orders_v2
    description: "Orders fact table v2 - added tax_amount column (breaking change)"
    config:
      contract:
        enforced: true
    columns:
      - name: order_key
        data_type: bigint
        constraints:
          - type: not_null
          - type: primary_key

      - name: order_amount
        data_type: decimal(18,2)
        constraints:
          - type: not_null

      # New in v2
      - name: tax_amount
        data_type: decimal(18,2)
        constraints:
          - type: not_null
          - type: check
            expression: "tax_amount >= 0"
```

### When to Use Data Contracts

✅ **Enforce contracts on**:
- Critical production tables
- Tables consumed by multiple teams
- Governed/audited datasets
- Tables with stability requirements
- External API-like tables

❌ **Don't enforce contracts on**:
- Development/staging models
- Experimental models
- Frequently changing models
- Internal intermediate models

---

## Testing Strategy by Model Layer

### Staging Layer
```yaml
models:
  - name: stg_source__entity
    columns:
      - name: entity_id
        tests:
          - unique
          - not_null

    # Source freshness
sources:
  - name: source_name
    tables:
      - name: table_name
        freshness:
          warn_after: {count: 1, period: day}
          error_after: {count: 2, period: day}
```

**Focus**: Data quality at source, freshness monitoring

### Intermediate Layer
```yaml
models:
  - name: int_subject__verb
    columns:
      - name: composite_key
        tests:
          - unique
          - not_null

      - name: foreign_key
        tests:
          - relationships:
              to: ref('upstream_model')
              field: key_column
```

**Focus**: Transformation correctness, key integrity

### Mart Layer (Facts)
```yaml
models:
  - name: fct_subject
    config:
      contract:
        enforced: true
    columns:
      - name: fact_key
        tests:
          - unique
          - not_null

      - name: foreign_key
        tests:
          - not_null
          - relationships:
              to: ref('dim_entity')
              field: entity_key

      - name: measure
        tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: ">= 0"

    tests:
      - dbt_utils.recency:
          datepart: day
          field: transaction_date
          interval: 1
```

**Focus**: Complete coverage, data contracts, freshness, business rules

### Mart Layer (Dimensions)
```yaml
models:
  - name: dim_entity
    config:
      contract:
        enforced: true
    columns:
      - name: entity_key
        tests:
          - unique
          - not_null

      - name: natural_key
        tests:
          - unique
          - not_null

      - name: categorical_field
        tests:
          - accepted_values:
              values: ['value1', 'value2', 'value3']
```

**Focus**: Key integrity, categorical validation, contracts

---

## CI/CD Testing Patterns

### Pull Request Testing
```bash
# Run only modified models and downstream
dbt test --select state:modified+
```

### Pre-Deployment Testing
```bash
# Run all tests with fail-fast
dbt test --fail-fast

# Run only critical tests
dbt test --select tag:critical
```

### Production Monitoring
```bash
# Run freshness checks
dbt source freshness

# Run relationship tests
dbt test --select test_type:relationships

# Run business rule tests
dbt test --select tag:business_rules
```

---

## Test Severity and Error Handling

### Severity Levels

```yaml
models:
  - name: fct_sales
    columns:
      - name: sales_key
        tests:
          - unique:
              severity: error  # Fail build
          - not_null:
              severity: error

      - name: discount_amount
        tests:
          - dbt_utils.expression_is_true:
              expression: ">= 0"
              severity: warn  # Don't fail, just warn
```

**Use `error` for**:
- Primary/foreign key violations
- Critical business rules
- Data contracts
- Referential integrity

**Use `warn` for**:
- Non-critical validations
- Soft business rules
- Data quality monitoring
- Optional constraints

---

## Test Documentation Pattern

```yaml
models:
  - name: fct_sales
    description: Sales transactions at line item grain
    meta:
      test_strategy: "Full coverage with contracts"
      test_owner: "Analytics Team"

    columns:
      - name: sales_amount
        description: Total sales amount (quantity * unit_price)
        tests:
          - not_null:
              meta:
                test_description: "Sales must have an amount"
                failure_action: "Investigate source data quality"
                jira_ticket: "DATA-123"
```

---

## Test Performance Optimization

### Pattern 1: Test Sampling
```yaml
models:
  - name: fct_large_table
    columns:
      - name: expensive_column
        tests:
          - unique:
              where: "order_date >= dateadd(day, -30, getdate())"
```

### Pattern 2: Test Limiting
```yaml
models:
  - name: fct_sales
    tests:
      - dbt_utils.recency:
          datepart: day
          field: order_date
          interval: 1
          config:
            limit: 100  # Only check 100 rows
```

---

## Testing Checklist

### For Every Model
- [ ] Primary key tests (unique + not_null)
- [ ] Foreign key tests (relationships)
- [ ] Critical column tests (not_null)
- [ ] Tests documented in schema.yml

### For Fact Tables
- [ ] All foreign keys have relationship tests
- [ ] Critical measures have not_null tests
- [ ] Business rules validated
- [ ] Freshness checks configured
- [ ] Data contract enforced (for critical tables)

### For Dimensions
- [ ] Surrogate key tests (unique + not_null)
- [ ] Natural key tests (unique + not_null)
- [ ] Categorical values validated
- [ ] Data contract enforced (for shared dimensions)

### For Custom Logic
- [ ] Unit tests written for complex transformations
- [ ] Edge cases covered
- [ ] Regression tests for bugs

---

## Testing Anti-Patterns

❌ **Don't**:
- Skip tests on critical models
- Only test some layers
- Ignore test failures
- Write tests without documentation
- Use severity: warn for critical tests
- Test implementation details
- Duplicate tests across levels

✅ **Do**:
- Test every model appropriately
- Use severity correctly
- Document test purpose
- Monitor test failures
- Fix or remove failing tests
- Balance coverage and performance
- Layer tests appropriately

---

**Remember**: Testing is not optional. Every model must have appropriate tests based on its criticality and layer.
