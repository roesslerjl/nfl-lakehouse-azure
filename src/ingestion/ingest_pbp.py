import nfl_data_py as nfl
import pandas as pd
import logging
from config.settings import BRONZE_PATH, SEASONS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bronze layer — raw ingestion, no transformations
# Data lands exactly as received from nfl-data-py

def ingest_pbp(seasons: list[int]) -> None:
    """
    Pull play-by-play data for given seasons and write to local Parquet.
    Bronze layer: schema-on-read, no transformations, no filtering.
    Storage path driven by config/settings.py — swap STORAGE_ROOT env
    var to point at ADLS Gen2 in production.
    """
    # BRONZE_PATH is the dataset-agnostic base — append /pbp for play-by-play
    pbp_path = BRONZE_PATH / "pbp"
    pbp_path.mkdir(parents=True, exist_ok=True)

    for season in seasons:
        logger.info(f"Ingesting season {season}...")

        df = nfl.import_pbp_data([season])

        output_path = pbp_path / f"season={season}"
        output_path.mkdir(exist_ok=True)

        df.to_parquet(output_path / "data.parquet", index=False)

        logger.info(f"Season {season}: {len(df)} rows, {len(df.columns)} cols → {output_path}")

if __name__ == "__main__":
    ingest_pbp(SEASONS)