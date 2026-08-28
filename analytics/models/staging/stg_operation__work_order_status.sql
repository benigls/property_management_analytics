with source as (
    select * from {{ source('raw', 'work_order_status_history') }}
),

renamed as (
    select
        cast(status_event_id as varchar) as status_event_id,
        cast(work_order_id as varchar) as work_order_id,
        lower(trim(cast(status as varchar))) as work_order_status,
        cast(event_at as timestamp) as event_at,
        cast(event_sequence as integer) as event_sequence,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
