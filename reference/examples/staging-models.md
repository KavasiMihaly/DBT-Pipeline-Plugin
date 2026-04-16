# Staging Model Examples

Staging models (stg_*) transform raw source data with basic cleaning, renaming, and type casting.

---

## Basic Staging Model

**File**: `models/staging/erp/stg_erp__customers.sql`

```sql
with

source as (
    select * from {{ source('erp', 'customers') }}
),

renamed as (
    select
        -- Primary Key
        customer_id,

        -- Attributes
        first_name,
        last_name,
        email,
        phone,

        -- Metadata
        created_at,
        updated_at

    from source
)

select * from renamed
```

**Purpose**:
- Select all columns explicitly (no SELECT *)
- Rename columns for consistency
- Organize columns by category (keys, attributes, metadata)
- Minimal transformation - just cleaning and renaming

---

## Staging Model with Source YAML

**File**: `models/staging/erp/schema.yml`

```yaml
version: 2

sources:
  - name: erp
    description: Enterprise Resource Planning system
    database: raw_database
    schema: erp_schema
    tables:
      - name: customers
        description: Customer master data from ERP
        columns:
          - name: customer_id
            description: Primary key
            tests:
              - unique
              - not_null

          - name: email
            description: Customer email address
            tests:
              - not_null

models:
  - name: stg_erp__customers
    description: Staging layer for ERP customer data
    columns:
      - name: customer_id
        description: Primary key
        tests:
          - unique
          - not_null

      - name: email
        tests:
          - not_null
```

**Key Elements**:
- Source definition pointing to raw tables
- Tests on source columns (data quality at origin)
- Model documentation with grain
- Tests on staging model columns

---

## Staging Model with Type Casting

**File**: `models/staging/sales/stg_sales__orders.sql`

```sql
with

source as (
    select * from {{ source('sales', 'orders') }}
),

cleaned as (
    select
        -- Primary Key
        cast(order_id as bigint) as order_id,

        -- Foreign Keys
        cast(customer_id as bigint) as customer_id,

        -- Attributes
        cast(order_number as varchar(50)) as order_number,
        cast(order_status as varchar(20)) as order_status,
        cast(order_amount as decimal(18,2)) as order_amount,

        -- Dates
        cast(order_date as date) as order_date,
        cast(created_at as datetime2) as created_at,
        cast(updated_at as datetime2) as updated_at

    from source
    where order_id is not null  -- Filter out null keys
)

select * from cleaned
```

**Features**:
- Explicit type casting for data quality
- Consistent data types across models
- Basic filtering (null key removal)
- Clear column organization

---

## Staging Model with Null Handling

**File**: `models/staging/marketing/stg_marketing__campaigns.sql`

```sql
with

source as (
    select * from {{ source('marketing', 'campaigns') }}
),

cleaned as (
    select
        -- Primary Key
        campaign_id,

        -- Attributes with null handling
        coalesce(campaign_name, 'Unknown Campaign') as campaign_name,
        coalesce(campaign_type, 'Other') as campaign_type,
        coalesce(budget_amount, 0.00) as budget_amount,
        coalesce(is_active, 0) as is_active,

        -- Dates
        start_date,
        end_date,
        created_at,
        updated_at

    from source
),

final as (
    select
        campaign_id,
        campaign_name,
        campaign_type,
        budget_amount,
        case
            when is_active = 1 then true
            else false
        end as is_active,
        start_date,
        end_date,
        created_at,
        updated_at
    from cleaned
)

select * from final
```

**Null Handling Strategies**:
- `COALESCE()` for default values
- Convert bit fields to boolean
- Preserve original data types
- Document null handling rules in comments

---

## Staging Model with Multiple Sources

**File**: `models/staging/finance/stg_finance__transactions.sql`

```sql
with

bank_transactions as (
    select * from {{ source('finance', 'bank_transactions') }}
),

credit_card_transactions as (
    select * from {{ source('finance', 'credit_card_transactions') }}
),

-- Standardize bank transactions
bank_standardized as (
    select
        transaction_id,
        'bank' as transaction_source,
        account_number,
        transaction_date,
        transaction_amount,
        transaction_description,
        created_at
    from bank_transactions
),

-- Standardize credit card transactions
credit_standardized as (
    select
        transaction_id,
        'credit_card' as transaction_source,
        card_number as account_number,
        transaction_date,
        transaction_amount,
        merchant_name as transaction_description,
        created_at
    from credit_card_transactions
),

-- Union all sources
unioned as (
    select * from bank_standardized
    union all
    select * from credit_standardized
)

select * from unioned
```

**Multi-Source Pattern**:
- Separate CTE for each source
- Standardize column names across sources
- Add source identifier column
- Union all sources into single model

---

## Best Practices

### Column Organization
Always organize columns in this order:
1. **Primary Keys** - Unique identifiers
2. **Foreign Keys** - References to other tables
3. **Attributes** - Descriptive columns
4. **Dates/Timestamps** - Temporal data
5. **Metadata** - System columns (created_at, updated_at)

### Naming Conventions
- **Model**: `stg_<source>__<entity>` (e.g., `stg_erp__customers`)
- **Source**: Lowercase, underscore-separated
- **Columns**: Lowercase, underscore-separated

### Transformation Rules
- ✅ **Do**: Rename, type cast, coalesce nulls
- ✅ **Do**: Filter out invalid records (null keys)
- ✅ **Do**: Add source identifier for unions
- ❌ **Don't**: Join to other tables
- ❌ **Don't**: Aggregate data
- ❌ **Don't**: Add business logic

### Materialization
Staging models should be **views** (default):
```yaml
# dbt_project.yml
models:
  my_project:
    staging:
      +materialized: table  # REQUIRED on SQL Server — views break due to EXEC() quoting in dbt-sqlserver adapter
```

### Testing
Every staging model must have:
- Primary key tests (unique + not_null)
- Critical column tests (not_null)
- Source freshness checks (optional)

---

## Common Patterns

### Pattern 1: One Source, One Model
Most common pattern - one staging model per source table.

### Pattern 2: Multiple Sources, One Model
Union multiple sources with similar schemas into one staging model.

### Pattern 3: One Source, Multiple Models
Split large source tables into multiple staging models by entity type.

### Pattern 4: Source + Reference Data
Join source with reference/lookup tables for standardization.

---

## When to Use Staging Models

Use staging models for:
- ✅ Raw source data transformation
- ✅ Column renaming and type casting
- ✅ Basic data cleaning (nulls, invalids)
- ✅ Standardizing multiple sources
- ✅ First layer of data quality tests

Don't use staging models for:
- ❌ Complex business logic
- ❌ Aggregations or calculations
- ❌ Joining multiple business entities
- ❌ Creating derived metrics

For these, use **intermediate** or **mart** models instead.
