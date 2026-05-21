/*
  int_plays_enriched.sql
  ----------------------
  Intermediate model — assembly layer between staging and marts.

  Source:  stg_pbp (staging model — never reference Silver directly)
  Grain:   one row per play (unchanged from staging)
  Depends: stg_pbp

  Derives two columns consumed by multiple downstream marts:
    - primary_player_name: the key player on the play (passer or rusher)
    - primary_player_id:   their ID, used for joining and grouping

  Keeping this logic here means mart_plays, mart_player_game, and
  mart_player_season all reference one definition — not three copies
  of the same CASE WHEN. See ADR-013.

  No aggregations. No business logic. No raw source references.
*/

with stg as (
    -- pull everything from staging — this is the only model that should
    -- reference stg_pbp directly. All marts reference int_plays_enriched.
    select * from {{ ref('stg_pbp') }}
)

select
    -- -------------------------------------------------------------------------
    -- Pass-through: all Silver columns carried forward unchanged
    -- -------------------------------------------------------------------------
    season,
    week,
    game_id,
    play_id,
    offense_team,
    defense_team,
    play_type,
    down,
    yards_to_go,
    yards_from_end_zone,
    yards_gained,
    score_differential,
    game_seconds_remaining,
    quarter,
    two_minute,
    distance_bucket,
    red_zone,
    high_leverage,
    success,
    offense_formation,
    defense_coverage_type,
    coverage_available,
    personnel_rb,
    personnel_te,
    personnel_wr,
    play_concept,
    concept_label,
    pass_length,
    pass_location,
    run_location,
    run_gap,
    passer_name,
    passer_id,
    rusher_name,
    rusher_id,
    receiver_name,
    receiver_id,        -- joins to dim_players.player_id to look up receiver position
    route,
    time_to_throw,
    intended_air_yards,
    expected_points_added,
    win_probability,
    win_probability_added,
    was_pressure,
    completion_pct_over_expected,
    qb_expected_points_added,
    fixed_drive,
    fixed_drive_result,
    offense_timeouts_remaining,
    defense_timeouts_remaining,
    posteam_won,                    -- binary game outcome — WP classifier target

    -- -------------------------------------------------------------------------
    -- Derived: primary player on the play
    -- For pass plays the QB is the key actor. For run plays it is the rusher.
    -- This unified field allows player-level marts to group without needing
    -- separate logic for each play type. See ADR-013.
    -- -------------------------------------------------------------------------
    case
        when play_type = 'pass' then passer_name
        when play_type = 'run'  then rusher_name
    end as primary_player_name,

    case
        when play_type = 'pass' then passer_id
        when play_type = 'run'  then rusher_id
    end as primary_player_id

from stg