# ingest_rosters.py
# -----------------
# Bronze ingestion for NFL roster data.
#
# Pulls player roster data for each season via nfl-data-py and writes
# raw Parquet files to the Bronze layer, partitioned by season.
#
# Roster data provides player attributes (position, team, jersey number)
# that are not available in play-by-play data. Required to build dim_players
# in Gold, which enables positional queries across all marts.
#
# Usage:
#   python -m src.ingestion.ingest_rosters
#
# Output:
#   data/bronze/rosters/season={year}/data.parquet

import nfl_data_py as nfl
import logging
from pathlib import Path
from config.settings import BRONZE_PATH, SEASONS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ingest_rosters(seasons: list[int]):
    """
    Pull NFL roster data from nfl-data-py and write to Bronze layer.

    Fetches one roster per season and writes each as a raw Parquet file.
    No transformations are applied. Bronze retains the source data as-is.

    Args:
        seasons: List of NFL season years to ingest. e.g. [2023, 2024, 2025]
    """
    for season in seasons:
        logger.info(f"Fetching roster for season {season}...")

        # import_seasonal_rosters returns one row per player per season
        # include_practice_squad=False keeps only active roster players
        df = nfl.import_seasonal_rosters(years=[season])

        logger.info(f"Season {season}: {len(df)} roster records, "
                    f"{df['position'].nunique()} positions")

        # Write raw to Bronze: no filtering, no column selection
        # Bronze always retains the full source schema (schema-on-read)
        output_path = BRONZE_PATH / "rosters" / f"season={season}"
        output_path.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path / "data.parquet", index=False)

        logger.info(f"Season {season} written → {output_path}")

    logger.info("Roster ingestion complete.")


if __name__ == "__main__":
    ingest_rosters(SEASONS)