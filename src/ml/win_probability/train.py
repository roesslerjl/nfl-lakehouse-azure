import itertools
import mlflow
from shared.features import load_mart_plays, get_wp_features
from shared.mlflow_utils import get_or_create_experiment, log_feature_importance
from win_probability.model import WinProbabilityModel
from ml_config import LOGREG_PARAM_GRID, XGBOOST_WP_PARAM_GRID, SEED, WP_EXPERIMENT

# =============================================================================
# Experiment config
# =============================================================================
EXPERIMENT_NAME = WP_EXPERIMENT

MODEL_GRIDS = [
    {"model_type": "logreg",  "param_grid": LOGREG_PARAM_GRID},
    {"model_type": "xgboost", "param_grid": XGBOOST_WP_PARAM_GRID},
]

# =============================================================================
# Grid search helpers
# =============================================================================
def _expand_grid(param_grid):
    """Expand a param grid dict into a list of individual param dicts."""
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]

def _strip_prefix(params, prefix="model__"):
    """Strip sklearn pipeline prefix from param names for logging."""
    return {k.replace(prefix, ""): v for k, v in params.items()}

# =============================================================================
# Training
# =============================================================================
def run_wp_experiment(spark):
    """
    Grid search over all WP model variants.
    Each model type gets a parent MLflow run; each hyperparameter combo gets a child run.
    Returns list of (best_run, best_metrics) per model type.
    """
    df = load_mart_plays(spark)
    X_train, X_test, y_train, y_test = get_wp_features(df)
    experiment_id = get_or_create_experiment(EXPERIMENT_NAME)
    results = []

    for model_cfg in MODEL_GRIDS:
        model_type = model_cfg["model_type"]
        combos = _expand_grid(model_cfg["param_grid"])

        best_auc = -1
        best_run_id = None
        best_metrics = None

        with mlflow.start_run(run_name=f"wp_{model_type}", experiment_id=experiment_id) as parent_run:
            for params in combos:
                clean_params = _strip_prefix(params)
                model = WinProbabilityModel(model_type=model_type, **clean_params)
                model.fit(X_train, y_train)
                diagnostics = model.get_diagnostics(X_test, y_test)
                fit_summary = model.get_fit_summary()
                metrics = {**diagnostics, **fit_summary}

                with mlflow.start_run(run_name=f"wp_{model_type}__{clean_params}", experiment_id=experiment_id, nested=True) as child_run:
                    mlflow.log_params({**{"model_type": model_type}, **clean_params})
                    mlflow.log_metrics(metrics)
                    mlflow.sklearn.log_model(model.pipeline, "model")

                    if diagnostics["auc"] > best_auc:
                        best_auc = diagnostics["auc"]
                        best_run_id = child_run.info.run_id
                        best_metrics = metrics
                        best_model = model

                print(f"  [{model_type}] {clean_params} → AUC: {diagnostics['auc']} | log_loss: {diagnostics['log_loss']}")

            mlflow.log_params({"model_type": model_type, "best_auc": best_auc})
            mlflow.log_metrics({"best_auc": best_auc})

        feature_names, importances = best_model.get_feature_importances()
        log_feature_importance(best_run_id, feature_names, importances)
        print(f"\n[wp_{model_type}] Best AUC: {best_auc} | run_id: {best_run_id}\n")
        results.append((best_run_id, best_metrics))

    return results

# =============================================================================
# Databricks Workflow entry point
# =============================================================================
if __name__ == "__main__":
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    run_wp_experiment(spark)
