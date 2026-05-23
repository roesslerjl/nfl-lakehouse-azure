import itertools
import pandas as pd
import mlflow
import mlflow.sklearn
from mlflow import MlflowClient
from sklearn.inspection import permutation_importance
from shared.features import load_mart_plays, get_qb_epa_features
from shared.mlflow_utils import get_or_create_experiment, log_feature_importance
from qb_epa.model import QBEpaModel
from ml_config import (
    RIDGE_QB_PARAM_GRID, XGBOOST_QB_PARAM_GRID, SEED,
    QB_EPA_EXPERIMENT, QB_EPA_TARGET, QB_EPA_MODEL_REGISTRY_NAME,
)

# =============================================================================
# Experiment config
# =============================================================================
EXPERIMENT_NAME = QB_EPA_EXPERIMENT

# I run Ridge first as a linear baseline, then XGBoost. Comparing the two RMSE
# values tells us whether the added complexity of XGBoost is justified. If Ridge
# comes close, the linear situational adjustment is already a strong signal.
MODEL_GRIDS = [
    {"model_type": "ridge",   "param_grid": RIDGE_QB_PARAM_GRID},
    {"model_type": "xgboost", "param_grid": XGBOOST_QB_PARAM_GRID},
]

# =============================================================================
# Grid search helpers
# =============================================================================
def _expand_grid(param_grid):
    """I expand a param grid dict into a flat list of individual param dicts."""
    keys   = list(param_grid.keys())
    values = list(param_grid.values())
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]

def _strip_prefix(params, prefix="model__"):
    """I strip the sklearn pipeline step prefix from param names before logging."""
    return {k.replace(prefix, ""): v for k, v in params.items()}

# =============================================================================
# Post-run artifact helpers
# =============================================================================
def _log_qb_residuals(model, X_test, y_test, passer_name_test):
    """
    I compute per-QB mean residuals on the test set and log them as an MLflow
    table so I can inspect situation-adjusted performance in the MLflow UI.

    A positive mean_residual means the QB outperformed the model's situational
    expectation across those plays. This is the core analytical signal of the
    experiment: controlling for game situation, which QBs consistently add EPA
    above what the context predicts?

    I sort by mean_residual descending so the top rows immediately show
    the QBs performing above situational expectation.
    """
    predictions = model.predict(X_test)
    play_level = pd.DataFrame({
        "passer_name":   passer_name_test.values,
        "actual_epa":    y_test.values,
        "predicted_epa": predictions,
        "residual":      y_test.values - predictions,
    })
    qb_summary = (
        play_level
        .groupby("passer_name")
        .agg(
            plays              = ("residual",      "count"),
            mean_residual      = ("residual",      "mean"),
            actual_epa_mean    = ("actual_epa",    "mean"),
            predicted_epa_mean = ("predicted_epa", "mean"),
        )
        .reset_index()
        .sort_values("mean_residual", ascending=False)
    )
    mlflow.log_table(data=qb_summary, artifact_file="qb_residuals.json")

def _log_permutation_importance(model, X_test, y_test):
    """
    I compute permutation importance and log it as an MLflow table.

    Permutation importance works by shuffling one feature column at a time and
    measuring how much RMSE degrades. This is more honest than gain-based
    importance because it captures each feature's actual predictive contribution
    to unseen data rather than how often the tree happened to split on it during
    training. Features that look important by gain but are just correlated proxies
    for other features will show low permutation importance.

    I use neg_root_mean_squared_error as the scoring function so the scale
    matches the RMSE we track everywhere else. A larger importance_mean means
    shuffling that feature hurts RMSE more, making it more important.
    """
    perm_result = permutation_importance(
        model.pipeline, X_test, y_test,
        n_repeats=10,
        random_state=SEED,
        scoring="neg_root_mean_squared_error",
    )
    perm_df = (
        pd.DataFrame({
            "feature":         X_test.columns.tolist(),
            "importance_mean": perm_result.importances_mean,
            "importance_std":  perm_result.importances_std,
        })
        .sort_values("importance_mean", ascending=False)
        .reset_index(drop=True)
    )
    mlflow.log_table(data=perm_df, artifact_file="permutation_importance.json")

# =============================================================================
# Training
# =============================================================================
def run_qb_epa_experiment(spark):
    """
    I run the full QB EPA grid search across Ridge and XGBoost model types.

    Each model type gets a parent MLflow run. Each hyperparameter combo gets a
    child run with mlflow.evaluate() metrics (RMSE, MAE, R2), a per-prediction
    table for post-hoc slicing, and a feature importance CSV on the best child.

    After the XGBoost loop I reopen the best XGBoost child run to add permutation
    importance and per-QB residuals. I then register that model in the Unity
    Catalog Model Registry under nfllakehouse_databricks.gold.qb_epa and tag it
    with the @champion alias (see ADR-028).

    I return a list of (best_run_id, best_rmse) tuples, one per model type.
    """
    df = load_mart_plays(spark)
    X_train, X_test, y_train, y_test, passer_name_test = get_qb_epa_features(df)
    experiment_id = get_or_create_experiment(EXPERIMENT_NAME)

    # mlflow.evaluate() needs a single DataFrame with features and the target.
    eval_data = X_test.copy()
    eval_data[QB_EPA_TARGET] = y_test.values

    # I track the best XGBoost model across the outer loop so I can register it
    # in the Model Registry and log its additional artifacts after all runs finish.
    best_xgb_run_id = None
    best_xgb_model  = None

    results = []

    for model_cfg in MODEL_GRIDS:
        model_type = model_cfg["model_type"]
        combos     = _expand_grid(model_cfg["param_grid"])

        best_rmse   = float("inf")
        best_run_id = None
        best_model  = None

        with mlflow.start_run(run_name=f"qb_epa_{model_type}", experiment_id=experiment_id) as parent_run:
            for params in combos:
                clean_params = _strip_prefix(params)
                model = QBEpaModel(model_type=model_type, **clean_params)
                model.fit(X_train, y_train)
                fit_summary = model.get_fit_summary()

                with mlflow.start_run(
                    run_name=f"qb_epa_{model_type}__{clean_params}",
                    experiment_id=experiment_id,
                    nested=True,
                ) as child_run:
                    mlflow.log_params({**{"model_type": model_type}, **clean_params})
                    mlflow.log_metrics(fit_summary)
                    mlflow.sklearn.log_model(model.pipeline, "model")

                    # mlflow.evaluate() with model_type="regressor" automatically
                    # logs RMSE, MAE, and R2 as structured metrics in the MLflow UI.
                    eval_result = mlflow.evaluate(
                        model=f"runs:/{child_run.info.run_id}/model",
                        data=eval_data,
                        targets=QB_EPA_TARGET,
                        model_type="regressor",
                    )

                    # I log a per-prediction table so I can slice model errors by
                    # game situation (down, formation, coverage type) after the run.
                    pred_table = eval_data.copy()
                    pred_table["predicted_epa"] = model.predict(X_test)
                    pred_table["residual"]       = pred_table[QB_EPA_TARGET] - pred_table["predicted_epa"]
                    mlflow.log_table(data=pred_table, artifact_file="eval_predictions.json")

                rmse = eval_result.metrics.get("root_mean_squared_error", float("inf"))
                print(f"  [qb_epa_{model_type}] {clean_params} -> RMSE: {rmse:.4f}")

                if rmse < best_rmse:
                    best_rmse   = rmse
                    best_run_id = child_run.info.run_id
                    best_model  = model

            mlflow.log_metrics({"best_rmse": best_rmse})

        # I log gain-based feature importances on the best child run for this
        # model type. For Ridge this is absolute coefficients; for XGBoost this
        # is gain over the selected features only (see QBEpaModel.get_feature_importances).
        feature_names, importances = best_model.get_feature_importances()
        log_feature_importance(best_run_id, feature_names, importances)
        print(f"\n[qb_epa_{model_type}] Best RMSE: {best_rmse:.4f} | run_id: {best_run_id}\n")

        if model_type == "xgboost":
            best_xgb_run_id = best_run_id
            best_xgb_model  = best_model

        results.append((best_run_id, best_rmse))

    # I reopen the best XGBoost child run once to log the two artifacts that
    # require the full test set. I do this outside the parent run context so
    # MLflow does not treat them as nested artifacts of the parent.
    with mlflow.start_run(run_id=best_xgb_run_id):
        _log_permutation_importance(best_xgb_model, X_test, y_test)
        _log_qb_residuals(best_xgb_model, X_test, y_test, passer_name_test)

    # I register the best XGBoost model in the Unity Catalog Model Registry
    # and tag it @champion so downstream consumers can load it by alias without
    # hardcoding a run ID (see ADR-028).
    registered = mlflow.register_model(
        model_uri=f"runs:/{best_xgb_run_id}/model",
        name=QB_EPA_MODEL_REGISTRY_NAME,
    )
    client = MlflowClient()
    client.set_registered_model_alias(QB_EPA_MODEL_REGISTRY_NAME, "champion", registered.version)
    print(f"\n[qb_epa] Registered model version {registered.version} as @champion.\n")

    return results

# =============================================================================
# Databricks Workflow entry point
# =============================================================================
if __name__ == "__main__":
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    run_qb_epa_experiment(spark)
