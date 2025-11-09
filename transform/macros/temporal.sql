{%- macro add_temporal_columns() -%}
    current_timestamp as ingested_at,
    current_timestamp as valid_from,
    cast(null as timestamp) as valid_to
{%- endmacro -%}

{%- macro add_ingestion_timestamp() -%}
    current_timestamp as ingested_at
{%- endmacro -%}
