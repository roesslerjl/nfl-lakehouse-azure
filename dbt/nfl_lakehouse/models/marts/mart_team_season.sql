/*
  mart_team_season.sql
  --------------------
  Team performance aggregated to season level. One row per team per season.

  Source:  mart_team_game
  Grain:   one row per team per season (season + team)
  Depends: mart_team_game

  Materialized as table (ADR-014).
  Surrogate key from season + team (ADR-015).

  References mart_team_game rather than int_plays_enriched directly (ADR-016).
  All rates recomputed from summed raw counts — never averaged from game-level
  rates (ADR-017). This ensures a team that played 70 plays in Week 1 and
  40 plays in Week 17 is weighted correctly in season averages.
*/

{{ config(materialized='table') }}   -- ADR-014

with game_stats as (
    select * from {{ ref('mart_team_game') }}
)

select
    -- Surrogate key (ADR-015)
    {{ dbt_utils.generate_surrogate_key(['season', 'team']) }} as mart_key,

    -- -------------------------------------------------------------------------
    -- Identifiers
    -- -------------------------------------------------------------------------
    season,
    team,
    count(distinct game_id) as games_played,

    -- -------------------------------------------------------------------------
    -- Offense — volume
    -- -------------------------------------------------------------------------
    sum(total_plays) as total_plays,
    sum(pass_plays) as pass_plays,
    sum(rush_plays) as rush_plays,
    round(sum(pass_plays) * 1.0 / nullif(sum(total_plays), 0), 3) as pass_rate,
    sum(total_yards) as total_yards,
    sum(passing_yards) as passing_yards,
    sum(rushing_yards) as rushing_yards,

    -- -------------------------------------------------------------------------
    -- Offense — efficiency (rates from counts — ADR-016, ADR-017)
    -- -------------------------------------------------------------------------
    round(sum(total_epa), 3) as total_epa,
    round(sum(total_epa) / nullif(sum(total_plays), 0), 3) as epa_per_play,
    round(sum(successful_plays) * 1.0 / nullif(sum(total_plays), 0), 3) as success_rate,

    -- -------------------------------------------------------------------------
    -- Offense — situational
    -- -------------------------------------------------------------------------
    sum(red_zone_plays) as red_zone_plays,
    round(sum(red_zone_epa), 3) as red_zone_epa,
    sum(two_minute_plays) as two_minute_plays,
    round(sum(two_minute_epa), 3) as two_minute_epa,

    -- -------------------------------------------------------------------------
    -- Defense — volume
    -- -------------------------------------------------------------------------
    sum(plays_allowed) as plays_allowed,
    sum(yards_allowed) as yards_allowed,
    sum(passing_yards_allowed) as passing_yards_allowed,
    sum(rushing_yards_allowed) as rushing_yards_allowed,

    -- -------------------------------------------------------------------------
    -- Defense — efficiency (rates from counts — ADR-016, ADR-017)
    -- -------------------------------------------------------------------------
    round(sum(total_epa_allowed), 3) as total_epa_allowed,
    round(sum(total_epa_allowed) / nullif(sum(plays_allowed), 0), 3) as epa_per_play_allowed,
    round(sum(successful_plays_allowed) * 1.0 / nullif(sum(plays_allowed), 0), 3) as success_rate_allowed,

    -- -------------------------------------------------------------------------
    -- Defense — pressure (weighted average by pass plays allowed)
    -- -------------------------------------------------------------------------
    round(
        sum(pressure_rate * pass_plays_allowed) /
        nullif(sum(pass_plays_allowed), 0), 3
    ) as pressure_rate,

    -- -------------------------------------------------------------------------
    -- Defense — situational
    -- -------------------------------------------------------------------------
    sum(red_zone_plays_allowed) as red_zone_plays_allowed,
    round(sum(red_zone_epa_allowed), 3) as red_zone_epa_allowed

from game_stats
group by season, team