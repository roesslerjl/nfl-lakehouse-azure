import pandas as pd
from sklearn.model_selection import train_test_split
from config import (
    SEED,
    MART_PLAYS_TABLE,
    COVERAGE_TYPES_EXCLUDE,
    WP_NUMERIC_FEATURES, WP_TARGET,
    QB_EPA_NUMERIC_FEATURES, QB_EPA_CATEGORICAL_FEATURES, QB_EPA_TARGET,
    CLUSTERING_NUMERIC_FEATURES, CLUSTERING_CATEGORICAL_FEATURES,
)

# =============================================================================
# Data loading
# =============================================================================
def load_mart_plays(spark):
    """Load mart_plays from Unity Catalog and return as pandas DataFrame."""
    return spark.table(MART_PLAYS_TABLE).toPandas()

# =============================================================================
# Win Probability
# =============================================================================
def get_wp_features(df, test_size=0.2):
    """
    Filter to run/pass plays with valid WP, return train/test split.
    WP is always in [0,1] — nulls indicate non-scrimmage plays, drop them.
    """
    cols = WP_NUMERIC_FEATURES + [WP_TARGET]
    data = df[df["play_type"].isin(["pass", "run"])][cols].dropna()
    X = data[WP_NUMERIC_FEATURES]
    y = data[WP_TARGET].astype(int)
    return train_test_split(X, y, test_size=test_size, random_state=SEED)

# =============================================================================
# QB EPA
# =============================================================================
def get_qb_epa_features(df, test_size=0.2):
    """
    Filter to pass plays with valid QB EPA and coverage type.
    Excludes BLOWN coverages — scheme breakdowns, not play design signal.
    """
    all_cols = QB_EPA_NUMERIC_FEATURES + QB_EPA_CATEGORICAL_FEATURES + [QB_EPA_TARGET]
    data = (df[(df["play_type"] == "pass") &
               (~df["defense_coverage_type"].isin(COVERAGE_TYPES_EXCLUDE)) &
               (df["passer_name"].notna())]
            [all_cols].dropna(subset=[QB_EPA_TARGET]))
    X = data[QB_EPA_NUMERIC_FEATURES + QB_EPA_CATEGORICAL_FEATURES]
    y = data[QB_EPA_TARGET]
    return train_test_split(X, y, test_size=test_size, random_state=SEED)

# =============================================================================
# Play Clustering
# =============================================================================
def get_clustering_features(df):
    """
    Filter to run/pass plays with valid formation and personnel.
    No target — unsupervised. Returns full feature matrix, no split.
    """
    all_cols = CLUSTERING_NUMERIC_FEATURES + CLUSTERING_CATEGORICAL_FEATURES
    data = (df[df["play_type"].isin(["pass", "run"])]
            [all_cols].dropna(subset=["offense_formation"]))
    return data[CLUSTERING_NUMERIC_FEATURES], data[CLUSTERING_CATEGORICAL_FEATURES]
