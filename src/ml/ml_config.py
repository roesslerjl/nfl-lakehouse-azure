SEED = 42
DATABRICKS_USER = "jlroessler98@gmail.com"

# =============================================================================
# Unity Catalog
# =============================================================================
CATALOG = "nfllakehouse_databricks"
GOLD_SCHEMA = "gold"
MART_PLAYS_TABLE = f"{CATALOG}.{GOLD_SCHEMA}.mart_plays"

# =============================================================================
# Preprocessing
# =============================================================================
RARE_CATEGORY_MIN_FREQ = 0.02
COVERAGE_TYPES_EXCLUDE = ["BLOWN"]

# =============================================================================
# Win Probability
# =============================================================================
WP_NUMERIC_FEATURES = [
    "down", "yards_to_go", "yards_from_end_zone",
    "score_differential", "game_seconds_remaining",
    "offense_timeouts_remaining", "defense_timeouts_remaining",
]
WP_TARGET = "posteam_won"

LOGREG_PARAM_GRID = {"model__C": [0.01, 0.1, 1.0, 10.0]}
XGBOOST_WP_PARAM_GRID = {
    "model__n_estimators": [100, 300],
    "model__max_depth": [4, 6],
    "model__learning_rate": [0.05, 0.1],
}

# =============================================================================
# QB EPA
# =============================================================================
QB_EPA_NUMERIC_FEATURES = [
    "yards_to_go", "yards_from_end_zone", "score_differential",
    "game_seconds_remaining", "time_to_throw", "intended_air_yards",
    "personnel_rb", "personnel_te", "personnel_wr",
]
QB_EPA_CATEGORICAL_FEATURES = [
    "down", "distance_bucket", "offense_formation",
    "defense_coverage_type", "pass_length",
]
QB_EPA_TARGET = "qb_expected_points_added"

RIDGE_QB_PARAM_GRID = {"model__alpha": [0.1, 1.0, 10.0, 100.0]}

XGBOOST_QB_PARAM_GRID = {
    "model__n_estimators": [100, 300],
    "model__max_depth": [4, 6],
    "model__learning_rate": [0.05, 0.1],
    # I include subsample because QB EPA targets are noisy. Row subsampling
    # per tree reduces overfitting to individual outlier plays.
    "model__subsample": [0.7, 0.9],
}

# Unity Catalog path for the registered QB EPA model (see ADR-028).
QB_EPA_MODEL_REGISTRY_NAME = f"{CATALOG}.{GOLD_SCHEMA}.qb_epa"

# =============================================================================
# Play Clustering
# =============================================================================
CLUSTERING_NUMERIC_FEATURES = [
    "yards_to_go", "yards_from_end_zone", "score_differential",
    "game_seconds_remaining", "personnel_rb", "personnel_te", "personnel_wr",
]
CLUSTERING_CATEGORICAL_FEATURES = [
    "offense_formation", "pass_length", "pass_location",
    "run_location", "down", "distance_bucket", "route",
]
KMEANS_K_GRID = list(range(4, 17))

# =============================================================================
# MLflow Experiment Names
# =============================================================================
WP_EXPERIMENT = f"/Users/{DATABRICKS_USER}/win_probability"
QB_EPA_EXPERIMENT = f"/Users/{DATABRICKS_USER}/qb_epa"
CLUSTERING_EXPERIMENT = f"/Users/{DATABRICKS_USER}/play_clustering"
