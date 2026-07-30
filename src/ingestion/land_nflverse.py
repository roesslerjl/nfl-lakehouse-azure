"""
Bronze landing task: pull raw nflverse datasets and write untransformed
Parquet into a Unity Catalog managed volume.

This is the *landing* step only. No transformation, no filtering, no
deduplication — data lands exactly as received. Auto Loader consumes these
files incrementally to build the Bronze Delta tables.

Source library: nflreadpy (Polars-based). Replaces nfl_data_py, which was
deprecated and archived upstream in favour of nflreadpy, and which is
uninstallable on Python 3.12 because it pins pandas<2.0 — a version with no
cp312 wheel, whose source build fails under Cython 3. See ADR-021.

Deliberately avoids pandas entirely: Polars writes the raw Parquet, Spark
reads it downstream. No intermediate dataframe library in the ingestion path.

One module serves every nflverse dataset. Adding a dataset means adding one
line to LOADERS, not copying this file. Each dataset gets its own task in the
Lakeflow job, so failures are isolated and retryable per dataset.

Usage:
    python land_nflverse.py --catalog <cat> --dataset pbp     --seasons 2023 2024 2025
    python land_nflverse.py --catalog <cat> --dataset rosters --seasons 2023 2024 2025
"""

import argparse
import logging
import os
from datetime import datetime, timezone

import nflreadpy as nfl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dataset name -> nflreadpy loader. The key is also the directory name under
# the volume and the eventual Bronze table name, so it is the single source of
# truth for what this dataset is called across the pipeline.
LOADERS = {
    "pbp": nfl.load_pbp,
    "rosters": nfl.load_rosters,
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Land a raw nflverse dataset into a UC volume.")
    p.add_argument("--catalog", required=True)
    p.add_argument("--schema", default="bronze")
    p.add_argument("--volume", default="raw_landing")
    p.add_argument(
        "--dataset",
        required=True,
        choices=sorted(LOADERS),
        help="Which nflverse dataset to land. Must be a key in LOADERS.",
    )
    p.add_argument("--seasons", nargs="+", type=int, required=True)
    return p.parse_args()


def land(catalog: str, schema: str, volume: str, dataset: str, seasons: list[int]) -> None:
    """Write one Parquet file per season per run into the landing volume.

    Each run emits a uniquely named file rather than overwriting. Two reasons,
    and both matter:

    1. Bronze is an append-only record of what arrived and when. Dedup is a
       Silver concern, not a landing concern.
    2. Auto Loader tracks files it has already processed. Rewriting the same
       path makes that tracking ambiguous and invites silent reprocessing or
       silent skipping, depending on the file-detection mode.

    Seasons are fetched one at a time rather than in a single call. Slightly
    more requests, but it preserves the season= partition layout and gives a
    per-season row count in the logs, which is the reconciliation check
    against a known-good baseline.
    """
    loader = LOADERS[dataset]
    landing_root = f"/Volumes/{catalog}/{schema}/{volume}/{dataset}"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    total_rows = 0

    for season in seasons:
        logger.info("Pulling %s season %s from nflverse...", dataset, season)
        df = loader(seasons=[season])  # Polars DataFrame

        out_dir = f"{landing_root}/season={season}"
        os.makedirs(out_dir, exist_ok=True)
        out_path = f"{out_dir}/{dataset}_{season}_{run_id}.parquet"

        # Direct write to the Volumes FUSE mount. If this fails on a FUSE
        # limitation, write to /tmp first and shutil.copy across.
        df.write_parquet(out_path)

        total_rows += df.height
        logger.info(
            "dataset=%s season=%s rows=%s cols=%s -> %s",
            dataset, season, df.height, df.width, out_path,
        )

    logger.info(
        "Landing complete: dataset=%s, %s season(s), %s total rows, run_id=%s",
        dataset, len(seasons), total_rows, run_id,
    )


if __name__ == "__main__":
    args = parse_args()
    land(args.catalog, args.schema, args.volume, args.dataset, args.seasons)