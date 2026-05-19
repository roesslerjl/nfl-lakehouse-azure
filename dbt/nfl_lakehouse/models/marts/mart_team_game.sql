/*
  mart_team_game.sql
  ------------------
  Team performance aggregated to game level. One row per team per game
  containing both offensive and defensive stats in a single row.

  Source:  int_plays_enriched
  Grain:   one row per team per game (game_id + team)
  Depends: int_plays_enriched

  Materialized as table (ADR-014).
  Surrogate key from game_id + team (ADR-015).

  Built by joining two aggregations:
    - offense_stats: plays where this team is on offense
    - defense_stats: plays where this team is on defense

  Combining both sides into one row enables single-query questions like
  "how did the Eagles perform in Week 5 on both sides of the ball?"

  Defensive EPA interpretation: negative total_epa_allowed means the defense
  held the offense below expected points — a sign of a dominant defense.
  Pressure rate = pressures generated / opponent pass plays.
*/

{{ config(materialized='table') }}   -- ADR-014

with plays as (
    select * from {{ ref('int_plays_enriched') }}
),

-- ─── OFFENSE ──────────────────────────────────────────────────────────────────
-- Aggregate all plays from the perspective of the team on offense
offense_stats as (
    select
        game_id,
        season,
        week,
        offense_team as team,
        defense_team as opponent,
        count(*) as total_plays,
        sum(case when play_type = 'pass' then 1 else 0 end) as pass_plays,
        sum(case when play_type = 'run'  then 1 else 0 end) as rush_plays,
        round(
            sum(case when play_type = 'pass' then 1.0 else 0 end) / count(*), 3
        ) as pass_rate,
        sum(yards_gained)  as total_yards,
        sum(case when play_type = 'pass' then yards_gained else 0 end) as passing_yards,
        sum(case when play_type = 'run'  then yards_gained else 0 end) as rushing_yards,
        round(sum(expected_points_added), 3) as total_epa,
        round(avg(expected_points_added), 3) as epa_per_play,
        sum(success) as successful_plays,  -- raw count for season rollup (ADR-017)
        round(avg(cast(success as double)), 3) as success_rate,
        sum(red_zone) as red_zone_plays,
        round(sum(case when red_zone = 1 then expected_points_added end), 3) as red_zone_epa,
        sum(case when two_minute = 'Y' then 1 else 0 end) as two_minute_plays,
        round(sum(case when two_minute = 'Y' then expected_points_added end), 3)  as two_minute_epa
    from plays
    group by game_id, season, week, offense_team, defense_team
),

-- ─── DEFENSE ──────────────────────────────────────────────────────────────────
-- Aggregate all plays from the perspective of the team on defense.
-- epa_allowed reflects the opponent's EPA — negative means a dominant defense.
defense_stats as (
    select
        game_id,
        defense_team as team,
        count(*) as plays_allowed,
        sum(yards_gained) as yards_allowed,
        sum(case when play_type = 'pass' then yards_gained else 0 end) as passing_yards_allowed,
        sum(case when play_type = 'run'  then yards_gained else 0 end) as rushing_yards_allowed,
        round(sum(expected_points_added), 3) as total_epa_allowed,
        round(avg(expected_points_added), 3) as epa_per_play_allowed,
        sum(success) as successful_plays_allowed,  -- raw count for season rollup (ADR-017)
        round(avg(cast(success as double)), 3) as success_rate_allowed,
        -- pressure_rate = pressures generated / opponent pass attempts
        -- measures how often the defense disrupts the QB
        round(
            sum(was_pressure) * 1.0 /
            nullif(sum(case when play_type = 'pass' then 1 else 0 end), 0), 3
        ) as pressure_rate,
        sum(red_zone) as red_zone_plays_allowed,
        round(sum(case when red_zone = 1 then expected_points_added end), 3) as red_zone_epa_allowed, 
        sum(case when play_type = 'pass' then 1 else 0 end) as pass_plays_allowed,
    from plays
    group by game_id, defense_team
),

-- ─── JOIN OFFENSE + DEFENSE ───────────────────────────────────────────────────
-- Combine both sides into one row per team per game.
-- Inner join — every team appears on both sides of every game.
combined as (
    select
        o.season,
        o.week,
        o.game_id,
        o.team,
        o.opponent,
        o.total_plays,
        o.pass_plays,
        o.rush_plays,
        o.pass_rate,
        o.total_yards,
        o.passing_yards,
        o.rushing_yards,
        o.total_epa,
        o.epa_per_play,
        o.successful_plays,
        o.success_rate,
        o.red_zone_plays,
        o.red_zone_epa,
        o.two_minute_plays,
        o.two_minute_epa,
        d.plays_allowed,
        d.yards_allowed,
        d.passing_yards_allowed,
        d.rushing_yards_allowed,
        d.total_epa_allowed,
        d.epa_per_play_allowed,
        d.successful_plays_allowed,
        d.success_rate_allowed,
        d.pressure_rate,
        d.red_zone_plays_allowed,
        d.red_zone_epa_allowed
    from offense_stats o
    inner join defense_stats d
        on  o.game_id = d.game_id
        and o.team = d.team
)

select
    {{ dbt_utils.generate_surrogate_key(['game_id', 'team']) }} as mart_key,
    *
from combined