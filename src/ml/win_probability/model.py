import time
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, log_loss
from xgboost import XGBClassifier
from shared.preprocessing import build_wp_preprocessor

# =============================================================================
# Win Probability Model
# =============================================================================
class WinProbabilityModel:
    """
    Wraps a full sklearn Pipeline (preprocessor + classifier) for win probability.
    Supports logreg and xgboost model types — same interface, swappable estimator.
    """
    SUPPORTED_TYPES = ("logreg", "xgboost")

    def __init__(self, model_type="logreg", **model_params):
        if model_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"model_type must be one of {self.SUPPORTED_TYPES}")
        self.model_type = model_type
        self.model_params = model_params
        self.pipeline = None
        self.fit_time = None
        self.n_samples = None
        self.n_features = None

    def _build_estimator(self):
        if self.model_type == "logreg":
            return LogisticRegression(max_iter=1000, **self.model_params)
        return XGBClassifier(eval_metric="logloss", random_state=42, **self.model_params)

    def fit(self, X_train, y_train):
        preprocessor = build_wp_preprocessor(X_train)
        self.pipeline = Pipeline(steps=[
            ("preprocessor", preprocessor),
            ("model", self._build_estimator()),
        ])
        start = time.perf_counter()
        self.pipeline.fit(X_train, y_train)
        self.fit_time = time.perf_counter() - start
        self.n_samples = X_train.shape[0]
        self.n_features = X_train.shape[1]
        return self

    def predict_proba(self, X):
        return self.pipeline.predict_proba(X)[:, 1]

    def get_params(self):
        return {"model_type": self.model_type, **self.model_params}

    def get_fit_summary(self):
        return {
            "fit_time_sec": round(self.fit_time, 3),
            "n_samples": self.n_samples,
            "n_features_in": self.n_features,
        }

    def get_diagnostics(self, X_test, y_test):
        proba = self.predict_proba(X_test)
        return {
            "auc": round(roc_auc_score(y_test, proba), 4),
            "log_loss": round(log_loss(y_test, proba), 4),
        }

    def get_feature_importances(self):
        """
        Returns (feature_names, importances) tuple.
        For logreg: absolute coefficient values. For xgboost: gain-based importances.
        """
        preprocessor = self.pipeline.named_steps["preprocessor"]
        model = self.pipeline.named_steps["model"]
        feature_names = preprocessor.get_feature_names_out()
        if self.model_type == "logreg":
            importances = np.abs(model.coef_[0])
        else:
            importances = model.feature_importances_
        return feature_names, importances
