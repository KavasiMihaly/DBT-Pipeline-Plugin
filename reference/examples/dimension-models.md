# Dimension Table Examples

Dimension tables (dim_*) store descriptive attributes and hierarchies, typically materialized as tables.

---

## Basic Dimension Table (SCD Type 1)

**File**: `models/marts/dim_customer.sql`

```sql
{{
    config(
        materialized='table'
    )
}}

with

customers as (
    select * from {{ ref('stg_erp__customers') }}
),

customer_attributes as (
    select
        -- Surrogate Key
        {{ dbt_utils.generate_surrogate_key(['customer_id']) }} as customer_key,

        -- Natural Key
        customer_id,

        -- Attributes
        first_name,
        last_name,
        first_name || ' ' || last_name as full_name,
        email,
        phone,

        -- Metadata
        created_at,
        updated_at

    from customers
)

select * from customer_attributes
```

**SCD Type 1 Features**:
- Overwrites on each run (no history)
- Single current row per entity
- Surrogate key for relationships
- Natural key preserved

---

## Dimension with Hierarchy

**File**: `models/marts/dim_product.sql`

```sql
{{
    config(
        materialized='table'
    )
}}

with

products as (
    select * from {{ ref('stg_erp__products') }}
),

categories as (
    select * from {{ ref('stg_erp__categories') }}
),

subcategories as (
    select * from {{ ref('stg_erp__subcategories') }}
),

product_dimension as (
    select
        -- Surrogate Key
        {{ dbt_utils.generate_surrogate_key(['products.product_id']) }} as product_key,

        -- Natural Key
        products.product_id,

        -- Product Attributes
        products.product_name,
        products.product_code,
        products.product_description,
        products.list_price,
        products.cost_price,
        products.list_price - products.cost_price as profit_margin,

        -- Hierarchy Level 1: Category
        categories.category_id,
        categories.category_name,

        -- Hierarchy Level 2: Subcategory
        subcategories.subcategory_id,
        subcategories.subcategory_name,

        -- Hierarchy Path (for drill-down)
        categories.category_name || ' > ' || subcategories.subcategory_name || ' > ' || products.product_name as product_hierarchy_path,

        -- Metadata
        products.created_at,
        products.updated_at

    from products

    left join subcategories
        on products.subcategory_id = subcategories.subcategory_id

    left join categories
        on subcategories.category_id = categories.category_id
)

select * from product_dimension
```

**Hierarchy Features**:
- Multiple hierarchy levels (Category → Subcategory → Product)
- IDs and names for each level
- Hierarchy path for drill-down queries
- Left joins to preserve orphan records

---

## Dimension with SCD Type 2 (Using Snapshots)

**File**: `snapshots/snap_dim_customer_history.sql`

```sql
{% snapshot snap_dim_customer_history %}

{{
    config(
        target_schema='snapshots',
        unique_key='customer_id',
        strategy='timestamp',
        updated_at='updated_at',
        invalidate_hard_deletes=True
    )
}}

with

customers as (
    select * from {{ ref('stg_erp__customers') }}
)

select
    customer_id,
    first_name,
    last_name,
    email,
    phone,
    city,
    state,
    country,
    customer_status,
    created_at,
    updated_at
from customers

{% endsnapshot %}
```

**Corresponding Dimension**:

**File**: `models/marts/dim_customer_history.sql`

```sql
{{
    config(
        materialized='table'
    )
}}

with

customer_snapshots as (
    select * from {{ ref('snap_dim_customer_history') }}
),

customer_history as (
    select
        -- Surrogate Key (unique for each version)
        {{ dbt_utils.generate_surrogate_key([
            'customer_id',
            'dbt_valid_from'
        ]) }} as customer_history_key,

        -- Natural Key
        customer_id,

        -- Attributes
        first_name,
        last_name,
        first_name || ' ' || last_name as full_name,
        email,
        phone,
        city,
        state,
        country,
        customer_status,

        -- SCD Type 2 Columns
        dbt_valid_from as valid_from,
        dbt_valid_to as valid_to,
        case
            when dbt_valid_to is null then 1
            else 0
        end as is_current,

        -- Metadata
        created_at,
        updated_at

    from customer_snapshots
)

select * from customer_history
```

**SCD Type 2 Features**:
- Tracks complete history of changes
- `valid_from` and `valid_to` date range
- `is_current` flag for latest version
- Unique surrogate key per version
- Uses dbt snapshots for automation

---

## Date Dimension

**File**: `models/marts/dim_date.sql`

```sql
{{
    config(
        materialized='table'
    )
}}

with

date_spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2020-01-01' as date)",
        end_date="cast('2030-12-31' as date)"
    ) }}
),

date_dimension as (
    select
        -- Surrogate Key (YYYYMMDD format)
        cast(format(date_day, 'yyyyMMdd') as int) as date_key,

        -- Date Column
        date_day as date_actual,

        -- Day Attributes
        day(date_day) as day_of_month,
        datename(weekday, date_day) as day_name,
        datepart(weekday, date_day) as day_of_week,
        case
            when datepart(weekday, date_day) in (1, 7) then 1
            else 0
        end as is_weekend,

        -- Week Attributes
        datepart(week, date_day) as week_of_year,
        datepart(iso_week, date_day) as iso_week_of_year,

        -- Month Attributes
        month(date_day) as month_of_year,
        datename(month, date_day) as month_name,
        left(datename(month, date_day), 3) as month_name_short,
        format(date_day, 'yyyy-MM') as year_month,

        -- Quarter Attributes
        datepart(quarter, date_day) as quarter_of_year,
        'Q' + cast(datepart(quarter, date_day) as varchar) as quarter_name,
        format(date_day, 'yyyy') + '-Q' + cast(datepart(quarter, date_day) as varchar) as year_quarter,

        -- Year Attributes
        year(date_day) as year,

        -- Fiscal Attributes (assuming fiscal year starts July 1)
        case
            when month(date_day) >= 7 then year(date_day) + 1
            else year(date_day)
        end as fiscal_year,

        case
            when month(date_day) >= 7 then month(date_day) - 6
            else month(date_day) + 6
        end as fiscal_month,

        case
            when month(date_day) >= 7 then datepart(quarter, date_day) - 2
            when month(date_day) >= 4 then datepart(quarter, date_day) + 2
            else datepart(quarter, date_day) + 2
        end as fiscal_quarter

    from date_spine
)

select * from date_dimension
```

**Date Dimension Features**:
- Integer surrogate key (YYYYMMDD)
- Day, week, month, quarter, year attributes
- Fiscal calendar support
- Weekend flag
- Standardized naming (month_name, day_name)

---

## Role-Playing Dimension

**File**: `models/marts/dim_date.sql` (same as above)

**Usage in Fact Table**:

```sql
-- In fct_orders.sql

with

orders as (
    select * from {{ ref('stg_erp__orders') }}
),

dim_date as (
    select * from {{ ref('dim_date') }}
),

order_facts as (
    select
        -- Keys
        order_key,
        customer_key,

        -- Role-playing date keys
        date_ordered.date_key as order_date_key,
        date_shipped.date_key as ship_date_key,
        date_delivered.date_key as delivery_date_key,

        -- Measures
        order_amount

    from orders

    -- Order date role
    left join dim_date as date_ordered
        on orders.order_date = date_ordered.date_actual

    -- Ship date role
    left join dim_date as date_shipped
        on orders.ship_date = date_shipped.date_actual

    -- Delivery date role
    left join dim_date as date_delivered
        on orders.delivery_date = date_delivered.date_actual
)

select * from order_facts
```

**Role-Playing Pattern**:
- Single dim_date table
- Multiple foreign keys in fact table
- Aliased joins for each role
- Clear naming: `order_date_key`, `ship_date_key`

---

## Junk Dimension (Low-Cardinality Flags)

**File**: `models/marts/dim_order_flags.sql`

```sql
{{
    config(
        materialized='table'
    )
}}

with

-- All possible combinations of flags
flag_combinations as (
    select
        row_number() over (order by (select null)) as order_flag_key,
        is_expedited,
        is_gift_wrapped,
        is_international,
        requires_signature
    from (
        values
            (0, 0, 0, 0),
            (1, 0, 0, 0),
            (0, 1, 0, 0),
            (0, 0, 1, 0),
            (0, 0, 0, 1),
            (1, 1, 0, 0),
            (1, 0, 1, 0),
            (1, 0, 0, 1),
            (0, 1, 1, 0),
            (0, 1, 0, 1),
            (0, 0, 1, 1),
            (1, 1, 1, 0),
            (1, 1, 0, 1),
            (1, 0, 1, 1),
            (0, 1, 1, 1),
            (1, 1, 1, 1)
    ) as flags(is_expedited, is_gift_wrapped, is_international, requires_signature)
),

flag_dimension as (
    select
        order_flag_key,
        cast(is_expedited as bit) as is_expedited,
        cast(is_gift_wrapped as bit) as is_gift_wrapped,
        cast(is_international as bit) as is_international,
        cast(requires_signature as bit) as requires_signature,

        -- Derived attributes
        case
            when is_expedited = 1 then 'Expedited'
            else 'Standard'
        end as shipping_type,

        case
            when is_international = 1 then 'International'
            else 'Domestic'
        end as shipping_scope

    from flag_combinations
)

select * from flag_dimension
```

**Junk Dimension Features**:
- Consolidates low-cardinality flags
- Pre-generates all combinations
- Reduces fact table width
- Simplifies queries

---

## Degenerate Dimension (Transaction IDs)

```sql
-- In fact table directly (no separate dimension)

{{
    config(
        materialized='incremental',
        unique_key='transaction_key'
    )
}}

with

transactions as (
    select * from {{ ref('stg_pos__transactions') }}
),

transaction_facts as (
    select
        -- Surrogate Key
        {{ dbt_utils.generate_surrogate_key(['transaction_id']) }} as transaction_key,

        -- Degenerate Dimension (transaction number stored in fact)
        transaction_id,
        transaction_number,
        receipt_number,

        -- Foreign Keys
        customer_key,
        store_key,
        date_key,

        -- Measures
        transaction_amount,
        tax_amount

    from transactions
)

select * from transaction_facts
```

**Degenerate Dimension Pattern**:
- Transaction IDs stored directly in fact table
- No separate dimension table needed
- Common for unique identifiers

---

## Best Practices

### Surrogate Keys
Always use surrogate keys for relationships:
```sql
{{ dbt_utils.generate_surrogate_key(['natural_key']) }} as surrogate_key
```

### Natural Keys
Always preserve natural keys:
```sql
-- Surrogate Key
customer_key,

-- Natural Key (from source system)
customer_id
```

### Naming Conventions
```
dim_<entity>         -- Basic dimension (dim_customer)
dim_<entity>_history -- SCD Type 2 (dim_customer_history)
dim_date             -- Date dimension
dim_<flags>          -- Junk dimension (dim_order_flags)
```

### Materialization
Dimensions should be **tables**:
```yaml
# dbt_project.yml
models:
  my_project:
    marts:
      +materialized: table
```

### Testing
Every dimension must have:
- Surrogate key tests (unique + not_null)
- Natural key tests (unique + not_null)
- Critical attribute tests (not_null)

---

## When to Use Each Type

### SCD Type 1 (Overwrite)
- ✅ Corrections to errors
- ✅ Non-critical attributes
- ✅ When history not needed
- ❌ Don't use for auditable fields

### SCD Type 2 (History)
- ✅ Critical business attributes
- ✅ Regulatory/audit requirements
- ✅ Trend analysis over time
- ❌ Don't use for high-churn attributes

### Date Dimension
- ✅ Always create for time-series analysis
- ✅ Pre-calculate fiscal periods
- ✅ Support role-playing dates

### Junk Dimension
- ✅ Multiple low-cardinality flags
- ✅ Transaction characteristics
- ✅ Reduce fact table width

### Degenerate Dimension
- ✅ Transaction numbers/IDs
- ✅ High-cardinality identifiers
- ✅ Query filter fields only

---

## Common Pitfalls

❌ **Don't**: Store measures in dimensions
```sql
-- Bad - measures belong in facts
select
    customer_id,
    customer_name,
    total_orders  -- ❌ This is a measure
```

❌ **Don't**: Skip surrogate keys
```sql
-- Bad - use surrogate key
customer_id as customer_key

-- Good
{{ dbt_utils.generate_surrogate_key(['customer_id']) }} as customer_key
```

❌ **Don't**: Use SELECT * in dimensions
```sql
-- Bad
select * from source

-- Good
select
    specific,
    columns
from source
```

❌ **Don't**: Forget hierarchy paths
```sql
-- Good - include full path for drill-down
category || ' > ' || subcategory || ' > ' || product as hierarchy_path
```
