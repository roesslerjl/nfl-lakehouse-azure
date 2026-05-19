/*
  mart_player_game.sql
  --------------------
  Player performance aggregated to game level.
  One row per player per role per game.

  Source:  int_plays_enriched
  Grain:   game_id + player_id + player_role
  Depends: int_plays_enriched

  Materialized as table (ADR-014).
  Surrogate key from game_id + player_id + player_role (ADR-015).

  Built as a UNION of three role-based CTEs:
    - passer_stats:   one row per QB per game (pass plays only)
    - rusher_stats:   one row per ball carrier per game (run plays only)
    - receiver_stats: one row per targeted receiver per game (pass plays only)

  A player who both passes and rushes (e.g. Jalen Hurts) gets two rows —
  one for each role. This preserves analytical clarity: passing EPA and
  rushing EPA are fundamentally different metrics and should not be merged.

  Role-specific columns are null where they do not apply:
    - pressure_plays, pressure_epa, avg_cpoe → null for rushers and receivers
    - avg_intended_air_yards                 → null for rushers only

  Join to dim_players on player_id + season to filter by position
  (e.g. all TEs as receivers, all RBs as rushers).
*/

{{ config(materialized='table') }}   -- ADR-014

with plays as (
    select * from {{ ref('int_plays_enriched') }}
),

-- ─── PASSERS ──────────────────────────────────────────────────────────────────
-- One row per QB per game. Filtered to pass plays only.
-- pressure_plays, avg_cpoe, avg_intended_air_yards populated here only.
passer_stats as (
    select
        season,
        week,
        game_id,
        offense_team,
        passer_id as player_id,
        passer_name as player_name,
        'passer' as player_role,
        count(*) as plays,
        sum(yards_gained) as total_yards,
        round(sum(expected_points_added), 3) as total_epa,
        round(avg(expected_points_added), 3) as epa_per_play,
        sum(success) as successful_plays,
        round(avg(cast(success as double)), 3) as success_rate,
        sum(red_zone) as red_zone_plays,
        round(sum(case when red_zone = 1 then expected_points_added end), 3) as red_zone_epa,
        sum(case when two_minute = 'Y' then 1 else 0 end) as two_minute_plays,
        round(sum(case when two_minute = 'Y' then expected_points_added end), 3) as two_minute_epa,
        sum(was_pressure) as pressure_plays,
        round(sum(case when was_pressure = 1 then expected_points_added end), 3) as pressure_epa,
        round(avg(completion_pct_over_expected), 3) as avg_cpoe,
        round(avg(intended_air_yards), 3) as avg_intended_air_yards
    from plays
    where play_type = 'pass'
      and passer_id is not null
    group by season, week, game_id, offense_team, passer_id, passer_name
),

-- ─── RUSHERS ──────────────────────────────────────────────────────────────────
-- One row per ball carrier per game. Filtered to run plays only.
-- pressure_plays, pressure_epa, avg_cpoe are null — passer-only metrics.
rusher_stats as (
    select
        season,
        week,
        game_id,
        offense_team,
        rusher_id as player_id,
        rusher_name as player_name,
        'rusher' as player_role,
        count(*) as plays,
        sum(yards_gained) as total_yards,
        round(sum(expected_points_added), 3) as total_epa,
        round(avg(expected_points_added), 3) as epa_per_play,
        sum(success) as successful_plays,
        round(avg(cast(success as double)), 3) as success_rate,
        sum(red_zone) as red_zone_plays,
        round(sum(case when red_zone = 1 then expected_points_added end), 3) as red_zone_epa,
        sum(case when two_minute = 'Y' then 1 else 0 end) as two_minute_plays,
        round(sum(case when two_minute = 'Y' then expected_points_added end), 3) as two_minute_epa,
        null as pressure_plays,
        null as pressure_epa,
        null as avg_cpoe,
        null as avg_intended_air_yards
    from plays
    where play_type = 'run'
      and rusher_id is not null
    group by season, week, game_id, offense_team, rusher_id, rusher_name
),

-- ─── RECEIVERS ────────────────────────────────────────────────────────────────
-- One row per targeted receiver per game. Pass plays only.
-- `plays` = targets here. pressure_plays, pressure_epa, avg_cpoe are null.
-- avg_intended_air_yards is populated — depth of target is receiver-relevant.
receiver_stats as (
    select
        season,
        week,
        game_id,
        offense_team,
        receiver_id as player_id,
        receiver_name as player_name,
        'receiver' as player_role,
        count(*) as plays,   -- targets
        sum(yards_gained) as total_yards,
        round(sum(expected_points_added), 3) as total_epa,
        round(avg(expected_points_added), 3) as epa_per_play,
        sum(success) as successful_plays,
        round(avg(cast(success as double)), 3) as success_rate,
        sum(red_zone) as red_zone_plays,
        round(sum(case when red_zone = 1 then expected_points_added end), 3) as red_zone_epa,
        sum(case when two_minute = 'Y' then 1 else 0 end) as two_minute_plays,
        round(sum(case when two_minute = 'Y' then expected_points_added end), 3)  as two_minute_epa,
        null as pressure_plays,
        null as pressure_epa,
        null as avg_cpoe,
        round(avg(intended_air_yards), 3) as avg_intended_air_yards
    from plays
    where play_type = 'pass'
      and receiver_id is not null
    group by season, week, game_id, offense_team, receiver_id, receiver_name
)

-- ─── UNION + SURROGATE KEY ────────────────────────────────────────────────────
-- Combine all three role sets. Generate surrogate key once in the outer select
-- to avoid repeating the macro call three times.
select
    {{ dbt_utils.generate_surrogate_key(['game_id', 'player_id', 'player_role']) }} as mart_key,
    combined.*
from (
    select * from passer_stats
    union all
    select * from rusher_stats
    union all
    select * from receiver_stats
) combined