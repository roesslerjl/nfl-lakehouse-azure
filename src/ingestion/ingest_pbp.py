import nfl_data_py as nfl
import pandas as pd
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bronze layer — raw ingestion, no transformations
# Data lands exactly as received from nfl-data-py

BRONZE_PATH = Path("data/bronze/pbp")

def ingest_pbp(seasons: list[int]):
    """
    Pull play-by-play data for given seasons and write to local Parquet.
    Bronze layer: schema-on-read, no transformations, no filtering.
    """
    BRONZE_PATH.mkdir(parents=True, exist_ok=True)

    for season in seasons:
        logger.info(f"Ingesting season {season}...")
        
        df = nfl.import_pbp_data([season])
        
        output_path = BRONZE_PATH / f"season={season}"
        output_path.mkdir(exist_ok=True)
        
        df.to_parquet(output_path / "data.parquet", index=False)
        
        logger.info(f"Season {season}: {len(df)} rows, {len(df.columns)} cols → {output_path}")

if __name__ == "__main__":
    ingest_pbp([2023, 2024, 2025])