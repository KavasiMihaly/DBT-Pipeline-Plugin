# Fact Table Examples

Fact tables (fct_*) store measures and foreign keys at a specific grain, typically with incremental materialization.

---

## Basic Fact Table

**File**: `models/marts/fct_sales.sql`

```sql
{{
    config(
        materialized='incremental',
        unique_key='sales_key',
        on_schema_change='fail',
        incremental_strategy='delete+insert'
    )
}}

with

orders as (
    select * from {{ ref('stg_erp__orders') }}
),

order_items as (
    select * from {{ ref('stg_erp__order_items') }}
),

sales_transactions as (
    select
        -- Keys
        {{ dbt_utils.generate_surrogate_key([
            'order_items.order_id',
            'order_items.line_number'
        ]) }} as sales_key,
        orders.customer_id as customer_key,
        orders.order_date_id as date_key,

        -- Measures
        order_items.quantity,
        order_items.unit_price,
        order_items.quantity * order_items.unit_price as sales_amount,
        order_items.discount_amount,

        -- Metadata
        orders.created_at

    from order_items
    inner join orders
        on order_items.order_id = orders.order_id

    {% if is_incremental() %}
        -- Only process new/updated records
        where orders.updated_at > (select max(created_at) from {{ this }})
    {% endif %}
)

select * from sales_transactions
```

**Key Features**:
- Surrogate key using `dbt_utils.generate_surrogate_key()`
- Foreign keys to dimensions
- Measures (facts) - numeric values
- Incremental strategy for performance
- Grain: One row per order line item

---

## Fact Table with delete+insert Strategy (SQL Server Default)

**File**: `models/marts/fct_revenue.sql`

```sql
{{
    config(
        materialized='incremental',
        unique_key='revenue_key',
        on_schema_change='fail',
        incremental_strategy='delete+insert'
    )
}}

with

sales as (
    select * from {{ ref('stg_sales__transactions') }}
),

revenue_facts as (
    select
        -- Surrogate Key
        {{ dbt_utils.generate_surrogate_key(['transaction_id']) }} as revenue_key,

        -- Foreign Keys
        customer_id as customer_key,
        product_id as product_key,
        cast(format(transaction_date, 'yyyyMMdd') as int) as date_key,

        -- Measures
        gross_amount,
        discount_amount,
        tax_amount,
        gross_amount - discount_amount + tax_amount as net_amount,

        -- Metadata
        transaction_date,
        updated_at

    from sales
    where transaction_date is not null

    {% if is_incremental() %}
        -- Incremental filter
        and updated_at > (select max(updated_at) from {{ this }})
    {% endif %}
)

select * from revenue_facts
```

**delete+insert Strategy**:
- **How it works**: Deletes rows matching `unique_key`, then inserts all new rows
- **Best for**: Small to medium incremental loads (< 1M rows per run)
- **SQL Server**: ⭐⭐⭐⭐⭐ Most reliable and performant
- **Performance**: Fast, predictable behavior

---

## Fact Table with append Strategy (Immutable Events)

**File**: `models/marts/fct_web_events.sql`

```sql
{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='append'
    )
}}

with

web_events as (
    select * from {{ ref('stg_web__events') }}
),

event_facts as (
    select
        -- Primary Key (natural key from source)
        event_id,

        -- Foreign Keys
        user_id as user_key,
        session_id as session_key,
        cast(format(event_timestamp, 'yyyyMMdd') as int) as date_key,

        -- Event Attributes
        event_type,
        event_category,
        page_url,
        referrer_url,

        -- Measures
        page_load_time_ms,
        time_on_page_seconds,

        -- Timestamps
        event_timestamp,
        created_at

    from web_events

    {% if is_incremental() %}
        -- Only new events (immutable - never updated)
        where event_timestamp > (select max(event_timestamp) from {{ this }})
    {% endif %}
)

select * from event_facts
```

**append Strategy**:
- **How it works**: Only inserts new rows, no updates or deletes
- **Best for**: Immutable event data (logs, transactions, clicks)
- **SQL Server**: ⭐⭐⭐⭐⭐ Fastest strategy
- **Performance**: Minimal overhead, no lookups

---

## Fact Table with merge Strategy (Use with Caution)

**File**: `models/marts/fct_inventory.sql`

```sql
{{
    config(
        materialized='incremental',
        unique_key='inventory_key',
        incremental_strategy='merge',
        merge_update_columns=['quantity_on_hand', 'quantity_reserved', 'updated_at']
    )
}}

with

inventory as (
    select * from {{ ref('stg_warehouse__inventory') }}
),

inventory_facts as (
    select
        -- Surrogate Key
        {{ dbt_utils.generate_surrogate_key([
            'product_id',
            'warehouse_id',
            'snapshot_date'
        ]) }} as inventory_key,

        -- Foreign Keys
        product_id as product_key,
        warehouse_id as warehouse_key,
        cast(format(snapshot_date, 'yyyyMMdd') as int) as date_key,

        -- Measures
        quantity_on_hand,
        quantity_reserved,
        quantity_on_hand - quantity_reserved as quantity_available,

        -- Metadata
        snapshot_date,
        updated_at

    from inventory

    {% if is_incremental() %}
        where updated_at > (select max(updated_at) from {{ this }})
    {% endif %}
)

select * from inventory_facts
```

**merge Strategy**:
- **How it works**: Uses SQL MERGE to update matching rows, insert new rows
- **Best for**: Snowflake, BigQuery (optimized for these platforms)
- **SQL Server Warning**: ⭐⭐ Can be slow for large tables
- **Recommendation**: Prefer `delete+insert` on SQL Server unless specific requirements

---

## Fact Table with Date Dimension Integration

**File**: `models/marts/fct_orders.sql`

```sql
{{
    config(
        materialized='incremental',
        unique_key='order_key',
        on_schema_change='fail',
        incremental_strategy='delete+insert'
    )
}}

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
        {{ dbt_utils.generate_surrogate_key(['orders.order_id']) }} as order_key,
        orders.customer_id as customer_key,

        -- Date foreign keys
        date_ordered.date_key as order_date_key,
        date_shipped.date_key as ship_date_key,
        date_delivered.date_key as delivery_date_key,

        -- Measures
        orders.order_amount,
        orders.tax_amount,
        orders.shipping_amount,
        orders.order_amount + orders.tax_amount + orders.shipping_amount as total_amount,

        -- Derived Measures
        datediff(day, orders.order_date, orders.ship_date) as days_to_ship,
        datediff(day, orders.ship_date, orders.delivery_date) as days_in_transit,

        -- Metadata
        orders.order_date,
        orders.updated_at

    from orders

    left join dim_date as date_ordered
        on orders.order_date = date_ordered.date_actual

    left join dim_date as date_shipped
        on orders.ship_date = date_shipped.date_actual

    left join dim_date as date_delivered
        on orders.delivery_date = date_delivered.date_actual

    {% if is_incremental() %}
        where orders.updated_at > (select max(updated_at) from {{ this }})
    {% endif %}
)

select * from order_facts
```

**Date Integration Pattern**:
- Multiple date foreign keys (order, ship, delivery)
- Join to dim_date to get date_key
- Derived date measures (days between dates)
- Clear naming: `order_date_key`, `ship_date_key`

---

## Fact Table with Multiple Measure Groups

**File**: `models/marts/fct_customer_metrics.sql`

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

orders as (
    select * from {{ ref('stg_erp__orders') }}
),

-- Order metrics
order_metrics as (
    select
        customer_id,
        count(distinct order_id) as order_count,
        sum(order_amount) as total_order_amount,
        avg(order_amount) as avg_order_amount,
        min(order_date) as first_order_date,
        max(order_date) as last_order_date,
        datediff(day, min(order_date), max(order_date)) as customer_lifespan_days
    from orders
    group by customer_id
),

-- Customer facts
customer_facts as (
    select
        -- Keys
        {{ dbt_utils.generate_surrogate_key(['customers.customer_id']) }} as customer_metric_key,
        customers.customer_id as customer_key,

        -- Order Measures
        coalesce(order_metrics.order_count, 0) as order_count,
        coalesce(order_metrics.total_order_amount, 0) as total_order_amount,
        coalesce(order_metrics.avg_order_amount, 0) as avg_order_amount,

        -- Lifetime Value
        coalesce(order_metrics.total_order_amount, 0) * 1.2 as estimated_ltv,

        -- Dates
        order_metrics.first_order_date,
        order_metrics.last_order_date,
        order_metrics.customer_lifespan_days,

        -- Metadata
        current_timestamp as calculated_at

    from customers
    left join order_metrics
        on customers.customer_id = order_metrics.customer_id
)

select * from customer_facts
```

**Aggregate Fact Pattern**:
- Pre-aggregated measures by grain (customer)
- Multiple measure groups (orders, lifetime value)
- Handles nulls with COALESCE
- Materialized as table (not incremental)

---

## Incremental Strategy Comparison

| Strategy | SQL Server | Use When | Updates | Deletes | Performance |
|----------|-----------|----------|---------|---------|-------------|
| **delete+insert** | ⭐⭐⭐⭐⭐ | Default choice | ✅ | ✅ | Fast & reliable |
| **merge** | ⭐⭐ | Complex logic | ✅ | ✅ | Slow on large tables |
| **append** | ⭐⭐⭐⭐⭐ | Immutable events | ❌ | ❌ | Fastest |
| **insert_overwrite** | ❌ | N/A (not supported) | ✅ | ✅ | Not available |

---

## Best Practices

### Grain Definition
Always define grain clearly in documentation:
```yaml
models:
  - name: fct_sales
    description: Sales transactions at order line item grain (one row per line item)
```

### Surrogate Keys
Use `dbt_utils.generate_surrogate_key()` for composite keys:
```sql
{{ dbt_utils.generate_surrogate_key(['order_id', 'line_number']) }} as sales_key
```

### Incremental Filters
Always filter in incremental mode:
```sql
{% if is_incremental() %}
    where updated_at > (select max(updated_at) from {{ this }})
{% endif %}
```

### Foreign Keys
Name foreign keys consistently:
```sql
customer_id as customer_key  -- References dim_customer
product_id as product_key    -- References dim_product
```

### Indexes
Add indexes for large fact tables (>10M rows):
```sql
{{
    config(
        post_hook=[
            "CREATE NONCLUSTERED INDEX ix_fct_sales_date ON {{ this }} (date_key)",
            "CREATE NONCLUSTERED INDEX ix_fct_sales_customer ON {{ this }} (customer_key)"
        ]
    )
}}
```

### Testing
Every fact table must have:
- Primary key tests (unique + not_null)
- Foreign key relationship tests
- Critical measure tests (not_null, > 0)
- Freshness checks for incremental models

---

## When to Use Each Materialization

### Incremental (Most Common)
- Large fact tables (>10M rows)
- Daily/hourly loads
- Measurable grain with unique_key

### Table
- Small fact tables (<1M rows)
- Aggregate facts
- Full refresh acceptable

### View
- Rarely used for facts
- Only for very small datasets or real-time queries

---

## Common Pitfalls

❌ **Don't**: Forget incremental filter
```sql
{% if is_incremental() %}
    where updated_at > (select max(updated_at) from {{ this }})
{% endif %}
```

❌ **Don't**: Use SELECT * in fact tables
```sql
-- Bad
select * from source

-- Good
select
    specific,
    columns,
    only
from source
```

❌ **Don't**: Mix measures and dimensions in one model
```sql
-- Bad - dimensions belong in dim_ models
select
    customer_id,
    customer_name,  -- ❌ Dimension attribute
    order_amount    -- ✅ Measure
```

❌ **Don't**: Skip on_schema_change config
```sql
config(
    on_schema_change='fail'  -- Catch breaking changes
)
```
