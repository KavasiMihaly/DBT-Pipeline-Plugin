{#
    T-SQL-compatible date_spine macro for dbt-sqlserver projects.

    -------------------------------------------------------------------------
    Why this macro exists
    -------------------------------------------------------------------------
    `dbt_utils.date_spine(...)` internally expands to a nested WITH clause:

        with rawdata as (
            with p0 as (select 0 union all select 1), ...
            select ... from p0 cross join p1 ...
        )
        select dateadd(...) from rawdata

    T-SQL rejects a `WITH` clause nested inside another `WITH` clause outright
    ("Incorrect syntax near the keyword 'with'"). This is a dialect limitation,
    not an EXEC() wrapper issue — `materialized='table'` does not help either.

    See `_Plan/Issues.md` I-048 for full context.

    -------------------------------------------------------------------------
    How this macro fixes it
    -------------------------------------------------------------------------
    This macro emits a SINGLE SELECT with zero leading WITH clauses, composed
    entirely from inline derived tables. It can be called inside an outer
    `with date_spine as ({{ date_spine(...) }})` wrapper without nesting.

    Ranges up to ~100,000 days (~273 years) via a 5-way cross join of VALUES
    tallies. Extend the cross join if you need more.

    -------------------------------------------------------------------------
    Signature
    -------------------------------------------------------------------------
    Matches `dbt_utils.date_spine(datepart, start_date, end_date)` so call
    sites only need to drop the `dbt_utils.` namespace.

    Currently supports `datepart='day'` only. For coarser grains, group the
    day-level output in the caller (trivial via date_trunc / datepart).

    -------------------------------------------------------------------------
    Example usage
    -------------------------------------------------------------------------
        with
        date_spine as (
            {{ date_spine(
                datepart='day',
                start_date="cast('2020-01-01' as date)",
                end_date="cast('2030-12-31' as date)"
            ) }}
        )
        select * from date_spine
#}
{% macro date_spine(datepart, start_date, end_date) %}
    {% if datepart != 'day' %}
        {{ exceptions.raise_compiler_error(
            "date_spine macro currently supports datepart='day' only. Got: '" ~ datepart ~ "'. "
            "For coarser grains, group day-level output in the caller "
            "(e.g., `select distinct datefromparts(year(date_day), month(date_day), 1) as month_day`)."
        ) }}
    {% endif %}

    select dateadd(day, t.n, {{ start_date }}) as date_{{ datepart }}
    from (
        select (a.n + b.n * 10 + c.n * 100 + d.n * 1000 + e.n * 10000) as n
        from       (values (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) as a(n)
        cross join (values (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) as b(n)
        cross join (values (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) as c(n)
        cross join (values (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) as d(n)
        cross join (values (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) as e(n)
    ) as t
    where dateadd(day, t.n, {{ start_date }}) < {{ end_date }}
{% endmacro %}
