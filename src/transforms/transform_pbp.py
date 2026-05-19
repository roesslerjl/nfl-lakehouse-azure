import pandas as pd
import numpy as np
import re
import logging
from pathlib import Path
from config.settings import BRONZE_PATH, SILVER_PATH, SEASONS
from config.play_concept_map import PLAY_CONCEPT_MAP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def transform_pbp(seasons: list[int]):
    """
    Transform Bronze play-by-play Parquet into a cleaned Silver dataset.

    Reads raw per-season Parquet files from BRONZE_PATH, filters to run/pass
    plays, selects and renames columns, casts types, handles nulls, and
    writes a single partitioned Parquet to SILVER_PATH.

    Args:
        seasons: List of NFL season years to process. e.g. [2023, 2024, 2025]
    """
    # BRONZE_PATH / SILVER_PATH are dataset-agnostic base paths — append /pbp
    # for play-by-play. See config/settings.py and ADR-018.
    bronze_pbp = BRONZE_PATH / "pbp"
    silver_pbp = SILVER_PATH / "pbp"

    frames = []
    for season in seasons:
        path = bronze_pbp / f"season={season}" / "data.parquet"
        frames.append(pd.read_parquet(path))
        logger.info(f"Loaded season {season}: {len(frames[-1])} rows")

    # ignore_index=True resets the row index so there are no duplicate index values across seasons
    # Without it, each season's rows would retain their original 0-N indices and overlap
    # load full bronze first, then filter
    # slightly more memory than filtering per-season, but simpler and fast enough locally
    # In production on Databricks, Spark handles this via partition pruning automatically
    df = pd.concat(frames, ignore_index=True)
    logger.info(f"Combined: {len(df)} rows across {len(seasons)} seasons")

    # Filter to analytically useful plays
    df = df[df["play_type"].isin(["run", "pass"])].copy()
    logger.info(f"After play_type filter: {len(df)} rows")

    # Select relevant columns for silver medalliomn structure 
    SILVER_COLUMNS = [
        "season", "week", "game_id", "play_id",
        "posteam", "defteam",
        "passer_player_name", "passer_player_id",
        "rusher_player_name", "rusher_player_id",
        "receiver_player_name", "receiver_player_id",  # receiver_player_id required
                                                        # for dim_players join in Gold
        "play_type", "down", "ydstogo", "yardline_100",
        "score_differential", "game_seconds_remaining",
        "offense_formation", "defense_coverage_type",
        "offense_personnel",
        "pass_length", "pass_location", "run_location", "run_gap",
        "route", "time_to_throw", "ngs_air_yards",
        "epa", "wp", "wpa", "was_pressure", "cpoe", "qb_epa",
        "posteam_timeouts_remaining", "defteam_timeouts_remaining",
        "fixed_drive", "fixed_drive_result",
        # yards_gained — actual yards gained on the play (positive or negative)
        # Fundamental metric for drive yardage totals, player yards, and team
        # rushing/passing yards across all Gold marts
        "yards_gained",
    ]

    df = df[SILVER_COLUMNS]

    # Type cast dataframe for cleanliness
    df["down"] = df["down"].astype("Int64")
    df["epa"]  = df["epa"].astype("float64")
    df["wp"]   = df["wp"].astype("float64")
    df["wpa"]  = df["wpa"].astype("float64")
    df["was_pressure"] = (
        df["was_pressure"]
        .map({"True": 1, "False": 0})
        .fillna(0)
        .astype("int8")
    )

    # Derive required columns not in bronze layer
    # pd.cut() bins a continuous value into labeled categories
    # three intervals: (0,3] → short, (3,7] → medium, (7,inf] → long
    df["distance_bucket"] = pd.cut(
        df["ydstogo"],
        bins=[0, 3, 7, float("inf")],
        labels=["short", "medium", "long"],
    )

    df["success"] = (df["epa"] > 0).astype("int8")
    df["high_leverage"] = (df["wp"].between(0.2, 0.8)).astype("int8")
    df["coverage_available"] = df["defense_coverage_type"].notna().astype("int8")

    # Derive quarter (1-4) from game_seconds_remaining
    # NFL game = 3600 seconds total, each quarter = 900 seconds (15 min)
    # game_seconds_remaining counts DOWN from 3600 → 0 over the course of the game
    # OT plays fall outside the 0-3600 range and are assigned quarter = 5
    quarter_conditions = [
        df["game_seconds_remaining"] > 2700,                        # Q1: 2701-3600s remaining
        df["game_seconds_remaining"].between(1801, 2700),           # Q2: 1801-2700s remaining
        df["game_seconds_remaining"].between(901, 1800),            # Q3: 901-1800s remaining
        df["game_seconds_remaining"].between(0, 900),               # Q4: 0-900s remaining
    ]
    quarter_values = [1, 2, 3, 4]
    df["quarter"] = np.select(
        quarter_conditions,
        quarter_values,
        default=5   # 5 = overtime — outside the standard 3600s game clock
    )

    # Derive two_minute flag (Y/N)
    # Two-minute warning applies in Q2 and Q4 only (final 2 mins of each half)
    # Q4: game_seconds_remaining <= 120 (final 2 min of game)
    # Q2: game_seconds_remaining between 1800-1920 (final 2 min before halftime)
    q4_two_minute = df["game_seconds_remaining"] <= 120
    q2_two_minute = df["game_seconds_remaining"].between(1800, 1920)
    df["two_minute"] = np.where(q4_two_minute | q2_two_minute, "Y", "N")

    # Derive red_zone flag (1/0)
    # NFL red zone = inside the opponent's 20-yard line
    # yards_from_end_zone <= 20 is the universally accepted threshold
    df["red_zone"] = (df["yardline_100"] <= 20).astype("int8")

    # Personnel parsing 
    # extracting RB/TE/WR counts from the offense_personnel string
    def parse_personnel(personnel_str):
        if pd.isna(personnel_str):
            return 0, 0, 0
        rb = int(m.group(1)) if (m := re.search(r"(\d+) RB", personnel_str)) else 0
        te = int(m.group(1)) if (m := re.search(r"(\d+) TE", personnel_str)) else 0
        wr = int(m.group(1)) if (m := re.search(r"(\d+) WR", personnel_str)) else 0
        return rb, te, wr

    df[["personnel_rb", "personnel_te", "personnel_wr"]] = df["offense_personnel"].apply(
        lambda x: pd.Series(parse_personnel(x))
    )

    # drop old personnel column as it is no longer needed
    df = df.drop(columns=["offense_personnel"])

    # Derive play_concept
    # produces values like Pass: Shotgun_ShortRight, UnderCenter_DeepLeft, Pistol_ShortMiddle
    # and Run: Shotgun_LeftEnd, UnderCenter_MiddleGuard
    def build_play_concept(row):
        formation = row["offense_formation"]
        if pd.isna(formation):
            return None

        formation_key = formation.replace(" ", "")  # "Under Center" → "UnderCenter"

        if row["play_type"] == "pass":
            length   = row["pass_length"]
            location = row["pass_location"]
            if pd.isna(length) or pd.isna(location):
                return None
            descriptor = f"{length.capitalize()}{location.capitalize()}"
        else:
            location = row["run_location"]
            gap      = row["run_gap"]
            if pd.isna(location) or pd.isna(gap):
                return None
            descriptor = f"{location.capitalize()}{gap.capitalize()}"

        return f"{formation_key}_{descriptor}"

    df["play_concept"]  = df.apply(build_play_concept, axis=1)
    df["concept_label"] = df["play_concept"].map(PLAY_CONCEPT_MAP)

    # Rename columns to human-readable names
    # Applied after all derived columns are calculated, so intermediate logic
    # still references original Bronze column names throughout this script.
    # The rename map is the single source of truth for Silver column naming.
    RENAME_MAP = {
        # Team identifiers
        "posteam":                    "offense_team",
        "defteam":                    "defense_team",
        "posteam_timeouts_remaining": "offense_timeouts_remaining",
        "defteam_timeouts_remaining": "defense_timeouts_remaining",
        # Player identifiers — drop redundant _player_ infix
        "passer_player_name":         "passer_name",
        "passer_player_id":           "passer_id",
        "rusher_player_name":         "rusher_name",
        "rusher_player_id":           "rusher_id",
        "receiver_player_name":       "receiver_name",
        "receiver_player_id":         "receiver_id",
        # Field position / distance
        "ydstogo":                    "yards_to_go",
        "yardline_100":               "yards_from_end_zone",
        # Spell out acronyms
        "epa":                        "expected_points_added",
        "wp":                         "win_probability",
        "wpa":                        "win_probability_added",
        "cpoe":                       "completion_pct_over_expected",
        "qb_epa":                     "qb_expected_points_added",
        # ngs_air_yards = NGS-tracked intended air yards (where the ball was thrown,not where it was caught). 
        # Rename to reflect meaning rather than data source.
        "ngs_air_yards":              "intended_air_yards",
    }
    df = df.rename(columns=RENAME_MAP)

    # write silver output
    silver_pbp.mkdir(parents=True, exist_ok=True)

    for season in df["season"].unique():
        season_df = df[df["season"] == season]
        output_path = silver_pbp / f"season={season}"
        output_path.mkdir(exist_ok=True)
        season_df.to_parquet(output_path / "data.parquet", index=False)
        logger.info(f"Season {season}: {len(season_df)} rows → {output_path}")

    logger.info("Silver transform complete.")


if __name__ == "__main__":
    transform_pbp(SEASONS)