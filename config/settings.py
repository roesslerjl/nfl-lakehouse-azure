import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Seasons ──────────────────────────────────────────────
SEASONS = [2023, 2024, 2025]

# ── Storage ───────────────────────────────────────────────
# Local development: writes to data/ folder
# Azure production: set STORAGE_ROOT env var to ADLS path
# e.g. abfss://bronze@youraccount.dfs.core.windows.net/
STORAGE_ROOT = os.getenv("STORAGE_ROOT", "data")

BRONZE_PATH = Path(STORAGE_ROOT) / "bronze" / "pbp"
SILVER_PATH = Path(STORAGE_ROOT) / "silver" / "pbp"
GOLD_PATH   = Path(STORAGE_ROOT) / "gold"

# ── Azure (production only) ───────────────────────────────
STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT", "")
STORAGE_CONTAINER    = os.getenv("AZURE_CONTAINER", "nfl-lakehouse")

# ── Databricks (production only) ──────────────────────────
DATABRICKS_HOST  = os.getenv("DATABRICKS_HOST", "")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")