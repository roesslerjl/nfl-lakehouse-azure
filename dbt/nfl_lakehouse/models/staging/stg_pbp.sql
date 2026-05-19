/*
  stg_pbp.sql
  -----------
  Staging model for play-by-play data.
  Thin translation layer between Silver (Delta) and the dbt Gold layer.

  Source: silver.pbp (Delta table in Unity Catalog)
  Grain: one row per play (run/pass only — filtered at Silver)

  No business logic here. All renaming was handled in the Silver transform.
  All downstream models reference this staging model, never Silver directly.
*/

with source as (
    select * from {{ source('silver', 'pbp') }}
)

select * from source