import pandas as pd
from sklearn.model_selection import train_test_split
from ml_config import (
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
    I filter to pass plays with a valid QB EPA target and a known passer.
    I exclude BLOWN coverages because they represent scheme breakdowns rather
    than play design signal and would add noise to the model.

    I return a 5-tuple: (X_train, X_test, y_train, y_test, passer_name_test).
    passer_name_test travels alongside the test split so train.py can compute
    per-QB residuals on the same rows the model was evaluated on.
    """
    all_cols = QB_EPA_NUMERIC_FEATURES + QB_EPA_CATEGORICAL_FEATURES + [QB_EPA_TARGET, "passer_name"]
    data = (df[(df["play_type"] == "pass") &
               (~df["defense_coverage_type"].isin(COVERAGE_TYPES_EXCLUDE)) &
               (df["passer_name"].notna())]
            [all_cols].dropna(subset=[QB_EPA_TARGET]))
    X = data[QB_EPA_NUMERIC_FEATURES + QB_EPA_CATEGORICAL_FEATURES]
    y = data[QB_EPA_TARGET]
    passer_name = data["passer_name"]
    X_train, X_test, y_train, y_test, pn_train, pn_test = train_test_split(
        X, y, passer_name, test_size=test_size, random_state=SEED
    )
    # I discard pn_train because residuals are only computed on the test set.
    return X_train, X_test, y_train, y_test, pn_test

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
