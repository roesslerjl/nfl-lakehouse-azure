import pandas as pd
import mlflow
import mlflow.sklearn

# =============================================================================
# Experiment setup
# =============================================================================
def get_or_create_experiment(name):
    """Return experiment ID, creating the experiment if it doesn't exist."""
    experiment = mlflow.get_experiment_by_name(name)
    if experiment is not None:
        return experiment.experiment_id
    return mlflow.create_experiment(name)

# =============================================================================
# Run logging
# =============================================================================
def log_run(run_name, experiment_name, params, metrics, pipeline, artifact_path="model"):
    """
    Log a complete training run to MLflow.
    Logs params, metrics, and the full sklearn Pipeline as a single artifact.
    Returns the MLflow run object.
    """
    experiment_id = get_or_create_experiment(experiment_name)
    with mlflow.start_run(run_name=run_name, experiment_id=experiment_id) as run:
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(pipeline, artifact_path)
    return run

def log_feature_importance(run_id, feature_names, importances, top_n=20):
    """
    Log feature importances as a CSV artifact on an existing run.
    Works for XGBoost (feature_importances_) and logistic regression (coef_).
    """
    df = (pd.DataFrame({"feature": feature_names, "importance": importances})
          .sort_values("importance", ascending=False)
          .head(top_n)
          .reset_index(drop=True))
    with mlflow.start_run(run_id=run_id):
        mlflow.log_text(df.to_csv(index=False), "feature_importance.csv")
    return df
