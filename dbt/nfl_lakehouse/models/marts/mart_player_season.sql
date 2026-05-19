/*
  mart_player_season.sql
  ----------------------
  Player performance aggregated to season level.
  One row per player per role per season.

  Source:  mart_player_game
  Grain:   season + player_id + player_role
  Depends: mart_player_game

  Materialized as table (ADR-014).
  Surrogate key from season + player_id + player_role (ADR-015).

  Preserves the role-based grain from mart_player_game — a player who both
  passes and rushes gets one passer row and one rusher row at season level.

  All rates recomputed from summed raw counts — never averaged from game
  rates (ADR-016, ADR-017). QB metrics weighted by plays so high-volume
  games contribute proportionally to season averages.
*/

{{ config(materialized='table') }}   -- ADR-014

with game_stats as (
    select * from {{ ref('mart_player_game') }}
)

select
    -- Surrogate key (ADR-015)
    {{ dbt_utils.generate_surrogate_key(['season', 'player_id', 'player_role']) }} as mart_key,

    -- -------------------------------------------------------------------------
    -- Identifiers
    -- -------------------------------------------------------------------------
    season,
    player_id,
    player_name,
    player_role,
    offense_team,
    count(distinct game_id) as games_played,

    -- -------------------------------------------------------------------------
    -- Volume
    -- -------------------------------------------------------------------------
    sum(plays) as plays,
    sum(total_yards) as total_yards,

    -- -------------------------------------------------------------------------
    -- EPA — rates recomputed from counts, not averaged (ADR-016, ADR-017)
    -- -------------------------------------------------------------------------
    round(sum(total_epa), 3) as total_epa,
    round(sum(total_epa) / nullif(sum(plays), 0), 3) as epa_per_play,

    -- -------------------------------------------------------------------------
    -- Success rate — from raw count, not averaged rate (ADR-017)
    -- -------------------------------------------------------------------------
    round(sum(successful_plays) / nullif(sum(plays), 0), 3) as success_rate,

    -- -------------------------------------------------------------------------
    -- Situational performance
    -- -------------------------------------------------------------------------
    sum(red_zone_plays) as red_zone_plays,
    round(sum(red_zone_epa), 3) as red_zone_epa,
    sum(two_minute_plays) as two_minute_plays,
    round(sum(two_minute_epa), 3) as two_minute_epa,

    -- -------------------------------------------------------------------------
    -- Passer-specific metrics (null for rushers and receivers)
    -- Weighted by plays so high-volume games contribute proportionally
    -- -------------------------------------------------------------------------
    sum(pressure_plays) as pressure_plays,
    round(sum(pressure_epa), 3) as pressure_epa,
    round(sum(avg_cpoe * plays) / nullif(sum(plays), 0), 3) as avg_cpoe,

    -- -------------------------------------------------------------------------
    -- Intended air yards — populated for passers and receivers, null for rushers
    -- -------------------------------------------------------------------------
    round(sum(avg_intended_air_yards * plays) / nullif(sum(plays), 0), 3) as avg_intended_air_yards

from game_stats
group by
    season,
    player_id,
    player_name,
    player_role,
    offense_team