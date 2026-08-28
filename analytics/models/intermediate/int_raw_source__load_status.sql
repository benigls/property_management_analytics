{{ config(materialized='view') }}

with stg_operation__property as (
    select * from {{ ref('stg_operation__property') }}
),
stg_operation__unit as (
    select * from {{ ref('stg_operation__unit') }}
),
stg_operation__tenant as (
    select * from {{ ref('stg_operation__tenant') }}
),
stg_operation__lease as (
    select * from {{ ref('stg_operation__lease') }}
),
stg_operation__charge as (
    select * from {{ ref('stg_operation__charge') }}
),
stg_operation__payment as (
    select * from {{ ref('stg_operation__payment') }}
),
stg_operation__payment_allocation as (
    select * from {{ ref('stg_operation__payment_allocation') }}
),
stg_operation__gl_entry as (
    select * from {{ ref('stg_operation__gl_entry') }}
),
stg_operation__budget as (
    select * from {{ ref('stg_operation__budget') }}
),
stg_operation__vendor as (
    select * from {{ ref('stg_operation__vendor') }}
),
stg_operation__work_order as (
    select * from {{ ref('stg_operation__work_order') }}
),
stg_operation__work_order_status as (
    select * from {{ ref('stg_operation__work_order_status') }}
),
stg_operation__hud_fmr as (
    select * from {{ ref('stg_operation__hud_fmr') }}
),

source_load_status as (
    select
        'properties' as affected_table,
        count(*) as raw_record_count,
        max(source_loaded_at) as raw_loaded_at
    from stg_operation__property

    union all

    select 'units', count(*), max(source_loaded_at)
    from stg_operation__unit

    union all

    select 'tenants', count(*), max(source_loaded_at)
    from stg_operation__tenant

    union all

    select 'leases', count(*), max(source_loaded_at)
    from stg_operation__lease

    union all

    select 'charges', count(*), max(source_loaded_at)
    from stg_operation__charge

    union all

    select 'payments', count(*), max(source_loaded_at)
    from stg_operation__payment

    union all

    select 'payment_allocations', count(*), max(source_loaded_at)
    from stg_operation__payment_allocation

    union all

    select 'gl_entries', count(*), max(source_loaded_at)
    from stg_operation__gl_entry

    union all

    select 'budgets', count(*), max(source_loaded_at)
    from stg_operation__budget

    union all

    select 'vendors', count(*), max(source_loaded_at)
    from stg_operation__vendor

    union all

    select 'work_orders', count(*), max(source_loaded_at)
    from stg_operation__work_order

    union all

    select 'work_order_status_history', count(*), max(source_loaded_at)
    from stg_operation__work_order_status

    union all

    select 'hud_fmr', count(*), max(source_loaded_at)
    from stg_operation__hud_fmr
)

, final as (
    select
        affected_table,
        raw_record_count,
        raw_loaded_at
    from source_load_status
)
select * from final
