/*
  dim_players.sql
  ---------------
  Player dimension table. One row per player per season.

  Source:  stg_rosters
  Grain:   one row per player per season (ADR-019)
  Depends: stg_rosters

  Materialized as table (ADR-014).
  Surrogate key from player_id + season (ADR-015, ADR-019).

  This dimension table enables positional filtering across all play-level
  marts. Without it, queries like "all TEs on go routes" or "all slot WRs
  in the red zone" are impossible — play-by-play data carries player IDs
  but not positions.

  Join pattern in downstream queries:
    join dim_players dp
      on  plays.receiver_id = dp.player_id
      and plays.season      = dp.season
*/

{{ config(materialized='table') }}   -- ADR-014

with rosters as (
    select * from {{ ref('stg_rosters') }}
)

select
    -- Surrogate key (ADR-015)
    -- Composite of player_id + season because a player can appear on different
    -- teams in different seasons — player_id alone is not unique (ADR-019)
    {{ dbt_utils.generate_surrogate_key(['player_id', 'season']) }} as dim_key,

    -- -------------------------------------------------------------------------
    -- Player identity
    -- -------------------------------------------------------------------------
    player_id,              -- joins to passer_id, rusher_id, receiver_id in plays
    player_name,
    season,

    -- -------------------------------------------------------------------------
    -- Position — the primary reason this dimension exists
    -- position:       broad role (QB, RB, WR, TE, OL, etc.)
    -- depth_position: specific role (slot WR, FB, LS, etc.) — sparse but useful
    -- -------------------------------------------------------------------------
    position,
    depth_position,

    -- -------------------------------------------------------------------------
    -- Team and display attributes
    -- -------------------------------------------------------------------------
    team,
    jersey_number

from rosters