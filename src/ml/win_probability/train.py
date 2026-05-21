from shared.features import load_mart_plays, get_wp_features
from shared.mlflow_utils import log_run, log_feature_importance
from win_probability.model import WinProbabilityModel
from config import LOGREG_PARAM_GRID, XGBOOST_WP_PARAM_GRID, SEED, WP_EXPERIMENT

# =============================================================================
# Experiment config
# =============================================================================
EXPERIMENT_NAME = WP_EXPERIMENT

RUNS = [
    {"model_type": "logreg", "C": 1.0},
    {"model_type": "xgboost", "n_estimators": 300, "max_depth": 6, "learning_rate": 0.05},
]

# =============================================================================
# Training
# =============================================================================
def run_wp_experiment(spark):
    """
    Train all WP model variants, log each as a separate MLflow run.
    Returns list of (run, diagnostics) tuples for inspection.
    """
    df = load_mart_plays(spark)
    X_train, X_test, y_train, y_test = get_wp_features(df)

    results = []
    for run_cfg in RUNS:
        model_type = run_cfg["model_type"]
        model_params = {k: v for k, v in run_cfg.items() if k != "model_type"}

        model = WinProbabilityModel(model_type=model_type, **model_params)
        model.fit(X_train, y_train)

        params = model.get_params()
        fit_summary = model.get_fit_summary()
        diagnostics = model.get_diagnostics(X_test, y_test)
        metrics = {**diagnostics, **fit_summary}

        run_name = f"wp_{model_type}"
        run = log_run(
            run_name=run_name,
            experiment_name=EXPERIMENT_NAME,
            params=params,
            metrics=metrics,
            pipeline=model.pipeline,
        )

        feature_names, importances = model.get_feature_importances()
        log_feature_importance(run.info.run_id, feature_names, importances)

        print(f"[{run_name}] AUC: {diagnostics['auc']} | log_loss: {diagnostics['log_loss']} | fit_time: {fit_summary['fit_time_sec']}s")
        results.append((run, diagnostics))

    return results

# =============================================================================
# Databricks Workflow entry point
# =============================================================================
if __name__ == "__main__":
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    run_wp_experiment(spark)
