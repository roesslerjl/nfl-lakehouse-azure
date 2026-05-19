/*
  mart_plays.sql
  --------------
  Primary analytical mart the play-level query engine for the dashboard and ML pipelines.

  Source:  int_plays_enriched
  Grain:   one row per play (run/pass only, seasons 2023-2025)
  Depends: int_plays_enriched

  Materialized as table — query speed over build time (ADR-014).
  Surrogate key mart_key generated from game_id + play_id (ADR-015).

  This is the widest, most granular table in the Gold layer. All other
  marts aggregate from this one. Arbitrary slice-and-dice queries
  (e.g. "Jordan Love EPA on deep balls week 1-10 vs 10-18") are answered
  here without any joins.
*/

{{ config(materialized='table') }}   -- ADR-014: table over view for dashboard query speed

with enriched as (
    select * from {{ ref('int_plays_enriched') }}
)

select
    -- -------------------------------------------------------------------------
    -- Surrogate key (ADR-015)
    -- Hashes game_id + play_id into a single unique identifier per play.
    -- Use this as the primary key when joining marts or building ML features.
    -- -------------------------------------------------------------------------
    {{ dbt_utils.generate_surrogate_key(['game_id', 'play_id']) }} as mart_key,

    -- -------------------------------------------------------------------------
    -- Game identifiers
    -- -------------------------------------------------------------------------
    season,
    week,
    game_id,
    play_id,

    -- -------------------------------------------------------------------------
    -- Teams
    -- -------------------------------------------------------------------------
    offense_team,
    defense_team,

    -- -------------------------------------------------------------------------
    -- Primary player (see ADR-013 — derived in int_plays_enriched)
    -- -------------------------------------------------------------------------
    primary_player_name,
    primary_player_id,

    -- -------------------------------------------------------------------------
    -- All player identifiers retained for receiver and detailed queries
    -- -------------------------------------------------------------------------
    passer_name,
    passer_id,
    rusher_name,
    rusher_id,
    receiver_name,
    receiver_id,        -- joins to dim_players.player_id to look up receiver position
                        -- e.g. filter to all TEs on go routes (see dim_players)

    -- -------------------------------------------------------------------------
    -- Play type and situation
    -- -------------------------------------------------------------------------
    play_type,
    down,
    yards_to_go,
    yards_from_end_zone,
    distance_bucket,
    score_differential,
    game_seconds_remaining,
    quarter,
    two_minute,
    red_zone,
    high_leverage,

    -- -------------------------------------------------------------------------
    -- Formation and personnel
    -- -------------------------------------------------------------------------
    offense_formation,
    personnel_rb,
    personnel_te,
    personnel_wr,

    -- -------------------------------------------------------------------------
    -- Play concept taxonomy (Python config → Silver — see ADR-010)
    -- -------------------------------------------------------------------------
    play_concept,
    concept_label,
    pass_length,
    pass_location,
    run_location,
    run_gap,

    -- -------------------------------------------------------------------------
    -- NGS tracking columns (sparse — see ADR-005)
    -- -------------------------------------------------------------------------
    route,
    time_to_throw,
    intended_air_yards,
    defense_coverage_type,
    coverage_available,
    was_pressure,

    -- -------------------------------------------------------------------------
    -- Outcome metrics
    -- -------------------------------------------------------------------------
    expected_points_added,
    win_probability,
    win_probability_added,
    completion_pct_over_expected,
    qb_expected_points_added,
    success,
    yards_gained,

    -- -------------------------------------------------------------------------
    -- Game state
    -- -------------------------------------------------------------------------
    offense_timeouts_remaining,
    defense_timeouts_remaining

from enriched