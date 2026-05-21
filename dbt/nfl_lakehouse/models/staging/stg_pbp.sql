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

select
    season, week, game_id, play_id,
    offense_team, defense_team,
    passer_name, passer_id,
    rusher_name, rusher_id,
    receiver_name, receiver_id,
    play_type, down, yards_to_go, yards_from_end_zone, yards_gained,
    score_differential, game_seconds_remaining,
    quarter, two_minute, distance_bucket,
    red_zone, high_leverage, success,
    offense_formation, defense_coverage_type, coverage_available,
    personnel_rb, personnel_te, personnel_wr,
    play_concept, concept_label,
    pass_length, pass_location, run_location, run_gap,
    route, time_to_throw, intended_air_yards,
    expected_points_added, win_probability, win_probability_added,
    was_pressure, completion_pct_over_expected, qb_expected_points_added,
    fixed_drive, fixed_drive_result,
    offense_timeouts_remaining, defense_timeouts_remaining,
    posteam_won
from source