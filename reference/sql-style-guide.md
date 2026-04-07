# SQL Style Guide for dbt

Comprehensive SQL style guide for writing consistent, maintainable dbt models.

---

## Core Principles

1. **Readability First**: Code is read more often than written
2. **Consistency**: Follow the same patterns throughout the project
3. **Explicitness**: Be explicit about intentions, avoid implicit behavior
4. **Maintainability**: Make code easy to modify and extend

---

## Keyword Casing

### Use lowercase keywords

✅ **Good**:
```sql
select
    customer_id,
    customer_name
from {{ ref('stg_erp__customers') }}
where is_active = 1
```

❌ **Bad**:
```sql
SELECT
    customer_id,
    customer_name
FROM {{ ref('stg_erp__customers') }}
WHERE is_active = 1
```

**Rationale**: Lowercase is easier to read and type, reduces visual noise

---

## CTEs (Common Table Expressions)

### Always use CTEs instead of subqueries

✅ **Good**:
```sql
with

customers as (
    select * from {{ ref('stg_erp__customers') }}
),

orders as (
    select * from {{ ref('stg_erp__orders') }}
),

customer_metrics as (
    select
        customers.customer_id,
        customers.customer_name,
        count(orders.order_id) as order_count
    from customers
    left join orders
        on customers.customer_id = orders.customer_id
    group by
        customers.customer_id,
        customers.customer_name
)

select * from customer_metrics
```

❌ **Bad**:
```sql
select
    c.customer_id,
    c.customer_name,
    (select count(*)
     from {{ ref('stg_erp__orders') }} o
     where o.customer_id = c.customer_id) as order_count
from {{ ref('stg_erp__customers') }} c
```

**Rationale**: CTEs improve readability, enable easier testing, and make query logic clearer

---

## Standard CTE Pattern

### Use consistent CTE structure

```sql
with

-- Import CTEs (source data)
source_table_1 as (
    select * from {{ ref('upstream_model_1') }}
),

source_table_2 as (
    select * from {{ ref('upstream_model_2') }}
),

-- Transformation CTEs (business logic)
transformed as (
    select
        column_1,
        column_2,
        column_1 + column_2 as derived_column
    from source_table_1
),

-- Join CTEs (combine data)
joined as (
    select
        transformed.column_1,
        transformed.derived_column,
        source_table_2.column_3
    from transformed
    inner join source_table_2
        on transformed.column_1 = source_table_2.column_1
),

-- Final CTE (final shaping)
final as (
    select
        column_1,
        column_3,
        derived_column
    from joined
)

select * from final
```

**CTE Naming Conventions**:
- `source` or `<table_name>` - Import CTEs
- `renamed` - Column renaming
- `cleaned` - Data cleaning
- `transformed` - Business logic
- `joined` - Combining tables
- `aggregated` - Aggregations
- `filtered` - Filtering logic
- `final` - Final output shaping

---

## Column Selection

### Never use SELECT *

✅ **Good**:
```sql
with

source as (
    select
        customer_id,
        first_name,
        last_name,
        email,
        created_at,
        updated_at
    from {{ source('erp', 'customers') }}
)

select * from source
```

❌ **Bad**:
```sql
select *
from {{ source('erp', 'customers') }}
```

**Exception**: SELECT * is acceptable ONLY in import CTEs when immediately followed by explicit selection:

```sql
with

source as (
    select * from {{ source('erp', 'customers') }}  -- ✅ OK here
),

renamed as (
    select
        customer_id,
        first_name,
        last_name
    from source
)

select * from renamed  -- ✅ Final select * from CTE is OK
```

**Rationale**:
- Explicit columns make schema changes visible
- Prevents unexpected columns in downstream models
- Improves documentation and understanding
- Better performance (only selected columns processed)

---

## Column Qualification

### Always qualify columns with table/CTE names in joins

✅ **Good**:
```sql
with

customers as (
    select * from {{ ref('stg_erp__customers') }}
),

orders as (
    select * from {{ ref('stg_erp__orders') }}
),

joined as (
    select
        customers.customer_id,
        customers.customer_name,
        customers.email,
        orders.order_id,
        orders.order_date,
        orders.order_amount
    from customers
    inner join orders
        on customers.customer_id = orders.customer_id
)

select * from joined
```

❌ **Bad**:
```sql
select
    customer_id,    -- Which table?
    customer_name,
    order_id,
    order_date
from {{ ref('stg_erp__customers') }} customers
inner join {{ ref('stg_erp__orders') }} orders
    on customer_id = customer_id  -- Ambiguous!
```

**Rationale**: Prevents ambiguity, makes source of each column clear, easier debugging

---

## Column Organization

### Organize columns by logical groups

```sql
with

source as (
    select * from {{ ref('stg_erp__orders') }}
),

renamed as (
    select
        -- Primary Key
        order_id,

        -- Foreign Keys
        customer_id,
        product_id,
        warehouse_id,

        -- Attributes
        order_number,
        order_status,
        order_type,

        -- Measures
        quantity,
        unit_price,
        quantity * unit_price as line_amount,
        discount_amount,
        tax_amount,

        -- Dates
        order_date,
        ship_date,
        delivery_date,

        -- Metadata
        created_at,
        updated_at,
        created_by,
        updated_by

    from source
)

select * from renamed
```

**Standard Order**:
1. Primary Keys
2. Foreign Keys
3. Attributes (descriptive columns)
4. Measures (numeric facts)
5. Dates and Timestamps
6. Metadata (system columns)

---

## Indentation and Spacing

### Use consistent indentation (4 spaces)

✅ **Good**:
```sql
with

customers as (
    select
        customer_id,
        customer_name,
        email
    from {{ ref('stg_erp__customers') }}
    where is_active = 1
)

select * from customers
```

### One column per line in SELECT

✅ **Good**:
```sql
select
    customer_id,
    customer_name,
    email,
    phone
from customers
```

❌ **Bad**:
```sql
select customer_id, customer_name, email, phone
from customers
```

### Leading commas (optional but recommended)

✅ **Good** (leading commas):
```sql
select
    customer_id
    , customer_name
    , email
from customers
```

✅ **Good** (trailing commas):
```sql
select
    customer_id,
    customer_name,
    email
from customers
```

**Choose one style and be consistent throughout the project**

---

## Joins

### Multi-line join conditions

✅ **Good**:
```sql
with

customers as (
    select * from {{ ref('dim_customer') }}
),

orders as (
    select * from {{ ref('fct_sales') }}
),

joined as (
    select
        customers.customer_id,
        customers.customer_name,
        orders.sales_amount
    from customers
    inner join orders
        on customers.customer_key = orders.customer_key
        and customers.is_active = 1
        and orders.order_date >= '2024-01-01'
)

select * from joined
```

### Join order and formatting

```sql
from base_table
inner join table_2
    on base_table.key = table_2.key
left join table_3
    on base_table.key = table_3.key
left join table_4
    on table_3.foreign_key = table_4.key
where base_table.is_active = 1
```

**Best Practices**:
- Most restrictive joins first (INNER)
- Less restrictive joins later (LEFT)
- Indent join conditions
- One condition per line for complex joins

---

## WHERE Clauses

### One condition per line

✅ **Good**:
```sql
select
    customer_id,
    order_date,
    order_amount
from orders
where order_status = 'completed'
    and order_date >= '2024-01-01'
    and order_amount > 0
    and customer_id is not null
```

❌ **Bad**:
```sql
select customer_id, order_date, order_amount
from orders
where order_status = 'completed' and order_date >= '2024-01-01' and order_amount > 0
```

---

## GROUP BY and ORDER BY

### Use column names, not numbers

✅ **Good**:
```sql
select
    customer_id,
    count(*) as order_count,
    sum(order_amount) as total_amount
from orders
group by
    customer_id
order by
    total_amount desc,
    customer_id
```

❌ **Bad**:
```sql
select
    customer_id,
    count(*) as order_count,
    sum(order_amount) as total_amount
from orders
group by 1
order by 3 desc, 1
```

**Rationale**: Column names are more maintainable when columns change

---

## CASE Statements

### Formatted for readability

✅ **Good**:
```sql
select
    customer_id,
    case
        when order_count = 0 then 'New'
        when order_count between 1 and 5 then 'Regular'
        when order_count between 6 and 20 then 'Frequent'
        when order_count > 20 then 'VIP'
        else 'Unknown'
    end as customer_segment,

    case
        when total_amount < 100 then 'Low Value'
        when total_amount < 1000 then 'Medium Value'
        else 'High Value'
    end as value_segment

from customer_metrics
```

### Align WHEN/THEN/ELSE

```sql
case
    when condition_1 then 'result_1'
    when condition_2 then 'result_2'
    when condition_3 then 'result_3'
    else 'default'
end as column_name
```

---

## Naming Conventions

### Models

```
stg_<source>__<entity>     # Staging models
int_<subject>__<verb>      # Intermediate models
fct_<subject>              # Fact tables
dim_<entity>               # Dimensions
```

### Columns

```
<entity>_key               # Surrogate keys
<entity>_id                # Natural keys
<event>_date               # Dates (order_date)
<event>_at                 # Timestamps (created_at)
is_<condition>             # Booleans (is_active)
has_<attribute>            # Booleans (has_discount)
<measure>_amount           # Money (sales_amount)
<measure>_count            # Counts (order_count)
<measure>_rate             # Rates (conversion_rate)
```

### CTEs

```
source                     # Raw import
renamed                    # Column renaming
cleaned                    # Data cleaning
transformed                # Business logic
joined                     # Combined tables
aggregated                 # Aggregations
filtered                   # Filtering
final                      # Final output
```

---

## Comments

### Use comments for complex logic

✅ **Good**:
```sql
with

customers as (
    select * from {{ ref('stg_erp__customers') }}
),

-- Calculate customer lifetime value
-- LTV = (Average Order Value) × (Number of Orders) × (Average Customer Lifespan in Years)
-- Assumption: Average customer lifespan = 3 years
customer_ltv as (
    select
        customer_id,
        avg(order_amount) as avg_order_value,
        count(distinct order_id) as order_count,
        avg(order_amount) * count(distinct order_id) * 3 as lifetime_value
    from orders
    group by customer_id
)

select * from customer_ltv
```

### Avoid obvious comments

❌ **Bad**:
```sql
-- Select customer_id
select
    customer_id,  -- Customer ID
    customer_name  -- Customer name
from customers
```

**Comment when**:
- Complex business logic
- Non-obvious calculations
- Assumptions or constraints
- Why something is done (not what)

---

## Jinja and Macros

### Jinja formatting

✅ **Good**:
```sql
{{
    config(
        materialized='incremental',
        unique_key='sales_key',
        on_schema_change='fail'
    )
}}

with

sales as (
    select * from {{ ref('stg_sales') }}
    {% if is_incremental() %}
        where updated_at > (select max(updated_at) from {{ this }})
    {% endif %}
)

select * from sales
```

### Macro calls

```sql
-- Surrogate key generation
{{ dbt_utils.generate_surrogate_key(['order_id', 'line_number']) }} as sales_key

-- Date functions
{{ dbt.current_timestamp() }}
{{ dbt.dateadd('day', 1, 'order_date') }}
```

---

## SQL Server Specific

### Use cross-database macros

✅ **Good**:
```sql
{{ dbt.current_timestamp() }}
{{ dbt.dateadd('day', 1, 'order_date') }}
```

❌ **Bad** (T-SQL specific):
```sql
GETDATE()
DATEADD(day, 1, order_date)
```

### Avoid T-SQL specific syntax

Use standard SQL or dbt macros for portability

---

## Anti-Patterns to Avoid

❌ **Don't use SELECT ***
❌ **Don't use table aliases in WHERE without FROM**
❌ **Don't mix business logic with staging**
❌ **Don't hard-code dates (use variables)**
❌ **Don't use UNION without UNION ALL (unless deduplication needed)**
❌ **Don't use implicit joins (comma-separated tables)**
❌ **Don't nest more than 2-3 levels of CTEs**

---

## Example: Complete Well-Formatted Model

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

-- Import source data
orders as (
    select * from {{ ref('stg_erp__orders') }}
),

order_items as (
    select * from {{ ref('stg_erp__order_items') }}
),

customers as (
    select * from {{ ref('dim_customer') }}
),

-- Calculate line-level sales
sales_detail as (
    select
        -- Surrogate Key
        {{ dbt_utils.generate_surrogate_key([
            'order_items.order_id',
            'order_items.line_number'
        ]) }} as sales_key,

        -- Foreign Keys
        orders.customer_id as customer_key,
        cast(format(orders.order_date, 'yyyyMMdd') as int) as date_key,

        -- Measures
        order_items.quantity,
        order_items.unit_price,
        order_items.quantity * order_items.unit_price as line_amount,
        order_items.discount_amount,
        order_items.line_amount - order_items.discount_amount as net_amount,

        -- Metadata
        orders.order_date,
        orders.updated_at

    from order_items
    inner join orders
        on order_items.order_id = orders.order_id
    where orders.order_status = 'completed'
        and order_items.quantity > 0

    {% if is_incremental() %}
        and orders.updated_at > (select max(updated_at) from {{ this }})
    {% endif %}
),

-- Add customer attributes for enrichment
enriched_sales as (
    select
        sales_detail.sales_key,
        sales_detail.customer_key,
        sales_detail.date_key,
        sales_detail.quantity,
        sales_detail.unit_price,
        sales_detail.line_amount,
        sales_detail.discount_amount,
        sales_detail.net_amount,
        sales_detail.order_date,
        sales_detail.updated_at,

        -- Customer segment for analysis
        customers.customer_segment,
        customers.customer_region

    from sales_detail
    left join customers
        on sales_detail.customer_key = customers.customer_key
),

-- Final output
final as (
    select * from enriched_sales
)

select * from final
```

---

## Quick Reference Checklist

- [ ] Lowercase keywords
- [ ] CTEs instead of subqueries
- [ ] No SELECT * (except in import CTEs)
- [ ] Columns qualified in joins
- [ ] Columns organized logically (keys, attributes, measures, dates, metadata)
- [ ] One column per line
- [ ] One condition per line in WHERE
- [ ] Column names in GROUP BY/ORDER BY (not numbers)
- [ ] Comments for complex logic
- [ ] Consistent indentation (4 spaces)
- [ ] Final CTE named `final`
- [ ] Standard CTE pattern followed

---

**Remember**: Consistency is more important than any individual rule. Pick a style and apply it throughout your project.
