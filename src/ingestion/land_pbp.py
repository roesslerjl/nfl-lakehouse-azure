"""
Bronze landing task: pull raw NFL play-by-play from nfl-data-py and write
untransformed Parquet into a Unity Catalog managed volume.

This is the *landing* step only. No transformation, no filtering, no
deduplication. Data lands exactly as received. Auto Loader consumes these
files incrementally to build the Bronze Delta table.

Designed to run as a Lakeflow Jobs Python task on serverless compute.
Declare `nfl-data-py` in the task environment, no %pip install inline.

Usage:
    python -m src.ingestion.land_pbp \
        --catalog nfllakehousedsa_databricks \
        --schema bronze \
        --volume raw_landing \
        --seasons 2023 2024 2025
"""

import argparse
import logging
import os
from datetime import datetime, timezone

import nfl_data_py as nfl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Land raw NFL play-by-play into a UC volume.")
    p.add_argument("--catalog", required=True)
    p.add_argument("--schema", default="bronze")
    p.add_argument("--volume", default="raw_landing")
    p.add_argument("--dataset", default="pbp", help="Subdirectory under the volume root.")
    p.add_argument("--seasons", nargs="+", type=int, required=True)
    return p.parse_args()


def land_pbp(catalog: str, schema: str, volume: str, dataset: str, seasons: list[int]) -> None:
    """Write one Parquet file per season per run into the landing volume.

    Each run emits a uniquely named file rather than overwriting in place.
    Two reasons, and both matter:

    1. Bronze is an append-only record of what arrived and when. Dedup is a
       Silver concern, not a landing concern.
    2. Auto Loader tracks files it has already processed. Rewriting the same
       path makes that tracking ambiguous and invites silent reprocessing or
       silent skipping, depending on the file-detection mode.
    """
    landing_root = f"/Volumes/{catalog}/{schema}/{volume}/{dataset}"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for season in seasons:
        logger.info("Pulling season %s from nfl-data-py...", season)
        df = nfl.import_pbp_data([season])

        out_dir = f"{landing_root}/season={season}"
        os.makedirs(out_dir, exist_ok=True)
        out_path = f"{out_dir}/{dataset}_{season}_{run_id}.parquet"

        df.to_parquet(out_path, index=False)
        logger.info(
            "season=%s rows=%s cols=%s -> %s",
            season, len(df), len(df.columns), out_path,
        )

    logger.info("Landing complete: %s season(s), run_id=%s", len(seasons), run_id)


if __name__ == "__main__":
    args = parse_args()
    land_pbp(args.catalog, args.schema, args.volume, args.dataset, args.seasons)