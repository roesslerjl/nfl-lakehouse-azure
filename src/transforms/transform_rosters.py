# transform_rosters.py
# --------------------
# Silver transform for NFL roster data.
#
# Reads raw Bronze roster Parquet files, selects relevant columns,
# casts types, deduplicates, and writes cleaned Silver Parquet
# partitioned by season.
#
# Output feeds dim_players in the Gold dbt layer, which enables
# positional queries across all play-level marts (e.g. "all TEs
# on go routes"). See ADR-018, ADR-019.
#
# Usage:
#   python -m src.transforms.transform_rosters
#
# Output:
#   data/silver/rosters/season={year}/data.parquet

import pandas as pd
import logging
from pathlib import Path
from config.settings import BRONZE_PATH, SILVER_PATH, SEASONS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Columns selected from the raw roster; everything else is dropped
ROSTER_COLUMNS = [
    "player_id",            # unique player identifier — joins to passer_id,
                            # rusher_id, receiver_id in play-by-play Silver
    "player_name",          # full name for display
    "position",             # primary position: QB, RB, WR, TE, OL, etc.
    "depth_chart_position", # more specific role: slot WR, FB, LS, etc.
    "team",                 # team abbreviation for this season
    "season",               # season year — part of the composite key (ADR-019)
    "jersey_number",        # useful for display and identity resolution
]


def transform_rosters(seasons: list[int]):
    """
    Transform Bronze roster Parquet files into a cleaned Silver dataset.

    Reads raw per-season roster Parquet files from BRONZE_PATH, selects
    relevant columns, casts types, deduplicates, and writes one Parquet
    file per season to SILVER_PATH.

    Args:
        seasons: List of NFL season years to process. e.g. [2023, 2024, 2025]
    """
    for season in seasons:
        path = BRONZE_PATH / "rosters" / f"season={season}" / "data.parquet"
        df = pd.read_parquet(path)
        logger.info(f"Loaded season {season}: {len(df)} raw roster records")

        # Select relevant columns only
        df = df[ROSTER_COLUMNS]

        # Cast types for cleanliness
        df["season"] = df["season"].astype("int32")
        df["jersey_number"] = pd.to_numeric(
            df["jersey_number"], errors="coerce"    # coerce handles non-numeric values
        ).astype("Int64")                           # Int64 supports nulls; int32 does not

        # Deduplicate seasonal rosters can have multiple records per player
        # if they appeared on multiple teams mid-season. Keep the last record
        # per player_id which reflects their final team that season.
        before = len(df)
        df = df.sort_values("team").drop_duplicates(
            subset=["player_id", "season"],
            keep="last"                             # last team alphabetically
        )
        logger.info(f"Season {season}: {before} → {len(df)} records after dedup")

        # Rename for consistency with Silver naming conventions
        df = df.rename(columns={
            "player_name": "player_name", # already clean
            "depth_chart_position": "depth_position"  # shorter, cleaner
        })

        # Write Silver output
        output_path = SILVER_PATH / "rosters" / f"season={season}"
        output_path.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path / "data.parquet", index=False)
        logger.info(f"Season {season}: {len(df)} records → {output_path}")

    logger.info("Roster Silver transform complete.")


if __name__ == "__main__":
    transform_rosters(SEASONS)