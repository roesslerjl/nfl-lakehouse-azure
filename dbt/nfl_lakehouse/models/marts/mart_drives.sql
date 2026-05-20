/*
  mart_drives.sql
  ---------------
  Drive-level aggregation mart. One row per drive per game.

  Source:  int_plays_enriched
  Grain:   one row per drive — identified by game_id + offense_team + fixed_drive
  Depends: int_plays_enriched

  Materialized as table (ADR-014).
  Surrogate key from game_id + offense_team + fixed_drive (ADR-015).
  Note: fixed_drive is only unique within a single game, not globally —
  hence the three-field surrogate key.

  Answers questions about drive efficiency, scoring rates, field position,
  and play calling tendencies at the drive level.
*/

{{ config(materialized='table') }}   -- ADR-014: table over view for dashboard query speed

with plays as (
    select * from {{ ref('int_plays_enriched') }}
),

-- Isolate the first play of each drive to capture starting field position.
-- row_number() ordered by play_id ascending gives play sequence within a drive.
-- Can't use MIN(yards_from_end_zone) because drives don't always start furthest from the end zone — field position changes play to play.
drive_first_play as (
    select
        game_id,
        offense_team,
        fixed_drive,
        yards_from_end_zone as starting_field_position
    from (
        select
            game_id,
            offense_team,
            fixed_drive,
            yards_from_end_zone,
            row_number() over (
                partition by game_id, offense_team, fixed_drive
                order by play_id asc          -- earliest play = start of drive
            ) as play_order
        from plays
    ) ranked
    where play_order = 1                      -- keep first play of drive only
),

-- Aggregate all plays within each drive into a single summary row
drive_stats as (
    select
        season,
        week,
        game_id,
        offense_team,
        defense_team,
        fixed_drive,
        fixed_drive_result,

        -- Play count and type breakdown
        count(*) as play_count,
        sum(case when play_type = 'pass' then 1 else 0 end) as pass_plays,
        sum(case when play_type = 'run'  then 1 else 0 end) as run_plays,
        round(
            sum(case when play_type = 'pass' then 1.0 else 0 end) / count(*),
            3
        ) as pass_rate,

        -- Yardage
        sum(yards_gained) as total_yards,

        -- EPA metrics
        round(sum(expected_points_added), 3) as total_epa,
        round(avg(expected_points_added), 3) as epa_per_play,

        -- Success rate — cast to double before avg to avoid integer division
        round(avg(cast(success as double)), 3) as success_rate,

        -- Scoring flags
        -- fixed_drive_result values from nfl-data-py: 'Touchdown', 'Field goal',
        -- 'Punt', 'Turnover', 'Turnover on downs', 'End of half', 'Opp touchdown'
        max(case when fixed_drive_result = 'Touchdown' then 1 else 0 end) as scored_touchdown,
        max(case when lower(fixed_drive_result) in ('touchdown', 'field goal') then 1 else 0 end) as scored_points

    from plays
    group by
        season, week, game_id, offense_team, defense_team,
        fixed_drive, fixed_drive_result
)

select
    -- Surrogate key (ADR-015) — three fields because fixed_drive is only
    -- unique within a game, not globally
    {{ dbt_utils.generate_surrogate_key(['ds.game_id', 'ds.offense_team', 'ds.fixed_drive']) }} as mart_key,

    -- Identifiers
    ds.season,
    ds.week,
    ds.game_id,
    ds.offense_team,
    ds.defense_team,
    ds.fixed_drive,
    ds.fixed_drive_result,

    -- Field position
    dfp.starting_field_position,

    -- Drive metrics
    ds.play_count,
    ds.pass_plays,
    ds.run_plays,
    ds.pass_rate,
    ds.total_yards,
    ds.total_epa,
    ds.epa_per_play,
    ds.success_rate,

    -- Scoring
    ds.scored_touchdown,
    ds.scored_points

from drive_stats ds
left join drive_first_play dfp
    on  ds.game_id       = dfp.game_id
    and ds.offense_team  = dfp.offense_team
    and ds.fixed_drive   = dfp.fixed_drive