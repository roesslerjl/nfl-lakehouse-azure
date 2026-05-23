import time
import numpy as np
from sklearn.feature_selection import SelectFromModel
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor
from shared.preprocessing import build_qb_epa_preprocessor
from ml_config import SEED

# =============================================================================
# QB EPA Model
# =============================================================================
class QBEpaModel:
    """
    I wrap a full sklearn Pipeline for situation-adjusted QB EPA regression.

    I support two model types:
      "ridge"   -- linear baseline with L2 regularization. No feature selection
                   step because Ridge handles correlated features natively via
                   its penalty. Coefficient magnitudes are directly interpretable.
      "xgboost" -- XGBoost regressor with a SelectFromModel feature selection
                   step between the preprocessor and the estimator (see ADR-027).
                   SelectFromModel fits a fast internal XGBRegressor to score
                   each post-preprocessing feature and drops those below mean
                   importance. This removes low-signal sparse NGS columns
                   (time_to_throw, intended_air_yards, defense_coverage_type)
                   when they do not contribute enough to justify the noise
                   introduced by median imputation.

    I encapsulate the full Pipeline so the MLflow artifact is self-contained.
    Loading the run artifact gives a complete deployable object that handles
    raw feature input with no preprocessing setup on the caller's side.
    """

    SUPPORTED_TYPES = ("ridge", "xgboost")

    def __init__(self, model_type="xgboost", **model_params):
        if model_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"model_type must be one of {self.SUPPORTED_TYPES}")
        self.model_type = model_type
        self.model_params = model_params
        self.pipeline = None
        self.fit_time = None
        self.n_samples = None
        self.n_features = None

    def _build_pipeline(self, X_train):
        """
        I build the sklearn Pipeline for the chosen model type.

        Ridge gets two steps: preprocessor then estimator.
        XGBoost gets three steps: preprocessor, SelectFromModel, then estimator.
        I pass X_train to the preprocessor builder so it can infer which columns
        are present at fit time.
        """
        preprocessor = build_qb_epa_preprocessor(X_train)
        if self.model_type == "ridge":
            return Pipeline(steps=[
                ("preprocessor", preprocessor),
                ("model", Ridge(**self.model_params)),
            ])
        # The selector uses a lightweight internal XGBRegressor to rank features.
        # The final model then trains only on the features that cleared the mean
        # importance threshold. I use a fixed n_estimators for the selector so
        # the hyperparameter grid controls only the final estimator's complexity.
        return Pipeline(steps=[
            ("preprocessor", preprocessor),
            ("selector", SelectFromModel(
                XGBRegressor(n_estimators=100, random_state=SEED),
                threshold="mean",
            )),
            ("model", XGBRegressor(eval_metric="rmse", random_state=SEED, **self.model_params)),
        ])

    def fit(self, X_train, y_train):
        self.pipeline = self._build_pipeline(X_train)
        start = time.perf_counter()
        self.pipeline.fit(X_train, y_train)
        self.fit_time = time.perf_counter() - start
        self.n_samples = X_train.shape[0]
        self.n_features = X_train.shape[1]
        return self

    def predict(self, X):
        return self.pipeline.predict(X)

    def get_params(self):
        return {"model_type": self.model_type, **self.model_params}

    def get_fit_summary(self):
        """
        I return a dict of training metadata suitable for mlflow.log_metrics.

        For XGBoost I also include n_features_selected so we can inspect how
        many features survived the SelectFromModel step across hyperparameter
        combos. A very low number suggests the sparse NGS columns are being
        aggressively filtered.
        """
        summary = {
            "fit_time_sec": round(self.fit_time, 3),
            "n_samples": self.n_samples,
            "n_features_in": self.n_features,
        }
        if self.model_type == "xgboost":
            selector = self.pipeline.named_steps["selector"]
            summary["n_features_selected"] = int(selector.get_support().sum())
        return summary

    def get_feature_importances(self):
        """
        I return a (feature_names, importances) tuple for artifact logging.

        For Ridge I use absolute coefficient values across all post-OHE features.
        Larger absolute coefficient means the feature moves predicted EPA more
        per unit change, holding other features constant.

        For XGBoost I use gain-based importances across only the selected features
        so the names and importances arrays correspond 1-to-1. I filter feature_names
        through the selector's boolean mask before returning.
        """
        preprocessor = self.pipeline.named_steps["preprocessor"]
        feature_names = preprocessor.get_feature_names_out()
        if self.model_type == "ridge":
            model = self.pipeline.named_steps["model"]
            return feature_names, np.abs(model.coef_)
        selector = self.pipeline.named_steps["selector"]
        model = self.pipeline.named_steps["model"]
        selected_names = feature_names[selector.get_support()]
        return selected_names, model.feature_importances_
