SEED = 42

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
WP_TARGET = "win_probability"

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

XGBOOST_QB_PARAM_GRID = {
    "model__n_estimators": [100, 300],
    "model__max_depth": [4, 6],
    "model__learning_rate": [0.05, 0.1],
}

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
