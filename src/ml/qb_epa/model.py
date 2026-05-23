import time
import numpy as np
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
      "ridge"   -- linear baseline with L2 regularization. Ridge handles
                   correlated situational features natively via its penalty
                   and produces directly interpretable coefficients.
      "xgboost" -- XGBoost regressor. Both pipelines are two steps:
                   preprocessor then estimator. I do not use SelectFromModel
                   here because XGBoost handles low-signal and sparse features
                   natively through its tree splitting and regularization
                   parameters (max_depth, subsample). A hard pre-selection step
                   was found to collapse the feature set to a single column,
                   destroying R2 by discarding nearly all signal before the
                   model even trained (see ADR-027 update).

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

        Both Ridge and XGBoost get the same two-step structure: preprocessor
        then estimator. I pass X_train to the preprocessor builder so it can
        infer which columns are present at fit time.
        """
        preprocessor = build_qb_epa_preprocessor(X_train)
        if self.model_type == "ridge":
            return Pipeline(steps=[
                ("preprocessor", preprocessor),
                ("model", Ridge(**self.model_params)),
            ])
        return Pipeline(steps=[
            ("preprocessor", preprocessor),
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
        """I return a dict of training metadata suitable for mlflow.log_metrics."""
        return {
            "fit_time_sec":  round(self.fit_time, 3),
            "n_samples":     self.n_samples,
            "n_features_in": self.n_features,
        }

    def get_feature_importances(self):
        """
        I return a (feature_names, importances) tuple for artifact logging.

        For Ridge I use absolute coefficient values across all post-OHE features.
        Larger absolute coefficient means the feature moves predicted EPA more
        per unit change, holding all other features constant.

        For XGBoost I use gain-based importances across all post-OHE features.
        Features that XGBoost never splits on will have zero importance and
        naturally sort to the bottom of the artifact.
        """
        preprocessor = self.pipeline.named_steps["preprocessor"]
        feature_names = preprocessor.get_feature_names_out()
        model = self.pipeline.named_steps["model"]
        if self.model_type == "ridge":
            return feature_names, np.abs(model.coef_)
        return feature_names, model.feature_importances_
