import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from ml_config import (RARE_CATEGORY_MIN_FREQ,
                    WP_NUMERIC_FEATURES, 
                    QB_EPA_NUMERIC_FEATURES, 
                    QB_EPA_CATEGORICAL_FEATURES, 
                    CLUSTERING_NUMERIC_FEATURES, 
                    CLUSTERING_CATEGORICAL_FEATURES)

# =============================================================================
# Custom transformers
# =============================================================================
class RareCategoryGrouper(BaseEstimator, TransformerMixin):
    """
    Collapse infrequent categories into 'Other' before one-hot encoding.
    """
    def __init__(self, min_freq=RARE_CATEGORY_MIN_FREQ, other_label="Other"):
        self.min_freq = min_freq
        self.other_label = other_label
        self.keep_ = None
        self.col_ = None

    def fit(self, X, y=None):
        if hasattr(X, "iloc"):
            if X.shape[1] != 1:
                raise ValueError("RareCategoryGrouper expects a single column.")
            self.col_ = X.columns[0]
            s = X.iloc[:, 0].astype(str)
        else:
            s = pd.Series(X).astype(str)
        freq = s.value_counts(normalize=True, dropna=False)
        self.keep_ = set(freq[freq >= self.min_freq].index)
        return self
    
    def transform(self, X):
        if hasattr(X, "iloc"):
            s = X.iloc[:, 0].astype(str)
            return s.where(s.isin(self.keep_), other=self.other_label).to_frame(name=self.col_)
        s = pd.Series(X).astype(str)
        return s.where(s.isin(self.keep_), other=self.other_label).to_frame()
    
    def get_feature_names_out(self, input_features=None):
        if input_features is not None:
            return np.array(input_features)
        if self.col_ is not None:
            return np.array([self.col_])
        return np.array([self.other_label])

# =============================================================================
# Preprocessor builders
# =============================================================================
def _cat_pipe():
    """
    Shared categorical pipeline: rare grouping → OHE.
    """
    return Pipeline(steps=[
        ("rare", RareCategoryGrouper()),
        ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

def _numeric_pipe():
    """
    Shared numeric pipeline: median impute → standard scale.
    """
    return Pipeline(steps=[
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])

def build_wp_preprocessor(X):
    """
    Win Probability — all numeric, no categoricals.
    """
    return ColumnTransformer(
        transformers=[("num", _numeric_pipe(), WP_NUMERIC_FEATURES)],
        remainder="drop"
    )

def build_qb_epa_preprocessor(X):
    """
    QB EPA — numeric + categorical. Per-column rare grouping before OHE.
    """
    cat_transformers = [
        (f"cat_{col}", Pipeline(steps=[("rare", RareCategoryGrouper()), ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), [col])
        for col in QB_EPA_CATEGORICAL_FEATURES
    ]
    return ColumnTransformer(
        transformers=[("num", _numeric_pipe(), QB_EPA_NUMERIC_FEATURES)] + cat_transformers,
        remainder="drop"
    )

def build_clustering_preprocessor(X_num, X_cat):
    """
    Play Clustering — built from separate numeric and categorical DataFrames.
    Caller passes X_num and X_cat from get_clustering_features().
    """
    cat_transformers = [
        (f"cat_{col}", Pipeline(steps=[("rare", RareCategoryGrouper()), ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), [col])
        for col in X_cat.columns
    ]
    X_combined = pd.concat([X_num, X_cat], axis=1)
    preprocessor = ColumnTransformer(
        transformers=[("num", _numeric_pipe(), list(X_num.columns))] + cat_transformers,
        remainder="drop"
    )
    return preprocessor, X_combined
