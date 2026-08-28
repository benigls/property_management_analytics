{% macro analytics_as_of_date() -%}
    cast('{{ var("as_of_date", "2026-06-30") }}' as date)
{%- endmacro %}


{% macro analytics_cutoff_timestamp() -%}
    cast('{{ var("as_of_date", "2026-06-30") }} 23:59:59' as timestamp)
{%- endmacro %}


{% macro analytics_history_start_date() -%}
    ({{ analytics_as_of_date() }} - interval '3 years' + interval '1 day')
{%- endmacro %}


{% macro analytics_forecast_end_date() -%}
    ({{ analytics_as_of_date() }} + interval '1 year')
{%- endmacro %}


{% macro analytics_as_of_month_start() -%}
    cast(date_trunc('month', {{ analytics_as_of_date() }}) as date)
{%- endmacro %}
