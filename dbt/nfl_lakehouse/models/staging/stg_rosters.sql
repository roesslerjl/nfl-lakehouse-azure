/*
  stg_rosters.sql
  ---------------
  Staging model for NFL roster data.
  Thin translation layer between Silver rosters (Delta) and the dbt Gold layer.

  Source:  silver.rosters (Delta table in Unity Catalog, defined in sources.yml)
  Grain:   one row per player per season (ADR-019)
  Depends: sources.yml

  No business logic here. All cleaning and deduplication was handled upstream
  in src/transforms/transform_rosters.py (Silver transform).
  dim_players references this model, never Silver directly.
*/

with source as (
    select * from {{ source('silver', 'rosters') }}
)

select * from source