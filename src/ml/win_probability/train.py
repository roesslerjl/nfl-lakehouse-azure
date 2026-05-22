import itertools
import pandas as pd
import mlflow
import mlflow.sklearn
from shared.features import load_mart_plays, get_wp_features
from shared.mlflow_utils import get_or_create_experiment, log_feature_importance
from win_probability.model import WinProbabilityModel
from ml_config import LOGREG_PARAM_GRID, XGBOOST_WP_PARAM_GRID, SEED, WP_EXPERIMENT, WP_TARGET

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
    Uses mlflow.evaluate() for structured evaluation tables and automatic metrics.
    Returns list of (best_run_id, best_auc) per model type.
    """
    df = load_mart_plays(spark)
    X_train, X_test, y_train, y_test = get_wp_features(df)
    experiment_id = get_or_create_experiment(EXPERIMENT_NAME)

    # mlflow.evaluate() requires a single DataFrame with features + target column
    eval_data = X_test.copy()
    eval_data[WP_TARGET] = y_test.values

    results = []

    for model_cfg in MODEL_GRIDS:
        model_type = model_cfg["model_type"]
        combos = _expand_grid(model_cfg["param_grid"])

        best_auc = -1
        best_run_id = None
        best_model = None

        with mlflow.start_run(run_name=f"wp_{model_type}", experiment_id=experiment_id) as parent_run:
            for params in combos:
                clean_params = _strip_prefix(params)
                model = WinProbabilityModel(model_type=model_type, **clean_params)
                model.fit(X_train, y_train)
                fit_summary = model.get_fit_summary()

                with mlflow.start_run(run_name=f"wp_{model_type}__{clean_params}", experiment_id=experiment_id, nested=True) as child_run:
                    mlflow.log_params({**{"model_type": model_type}, **clean_params})
                    mlflow.log_metrics(fit_summary)
                    mlflow.sklearn.log_model(model.pipeline, "model")

                    eval_result = mlflow.evaluate(
                        model=f"runs:/{child_run.info.run_id}/model",
                        data=eval_data,
                        targets=WP_TARGET,
                        model_type="classifier",
                    )

                auc = eval_result.metrics.get("roc_auc", -1)
                print(f"  [{model_type}] {clean_params} → AUC: {auc:.4f}")

                if auc > best_auc:
                    best_auc = auc
                    best_run_id = child_run.info.run_id
                    best_model = model

            mlflow.log_metrics({"best_auc": best_auc})

        feature_names, importances = best_model.get_feature_importances()
        log_feature_importance(best_run_id, feature_names, importances)
        print(f"\n[wp_{model_type}] Best AUC: {best_auc:.4f} | run_id: {best_run_id}\n")
        results.append((best_run_id, best_auc))

    return results

# =============================================================================
# Databricks Workflow entry point
# =============================================================================
if __name__ == "__main__":
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    run_wp_experiment(spark)
