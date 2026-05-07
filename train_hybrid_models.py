from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None

try:
    from lightgbm import LGBMClassifier
except Exception:
    LGBMClassifier = None

from src.hybrid_ml import (
    ACTION_MODEL_PATH,
    ANOMALY_MODEL_PATH,
    ROLE_MODEL_PATH,
    HybridMLService,
    _build_training_frame,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_preprocessor(numeric_features: List[str], categorical_features: List[str]):
    return ColumnTransformer(
        transformers=[
            ("num", SimpleImputer(strategy="median"), numeric_features),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "encoder",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                categorical_features,
            ),
        ]
    )


def evaluate_and_select(
    features_df: pd.DataFrame, y: pd.Series, preprocessor, candidates: dict
):
    results = {}
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    for name, clf in candidates.items():
        pipe = Pipeline(steps=[("preprocessor", preprocessor), ("model", clf)])
        try:
            scores = cross_val_score(pipe, features_df, y, cv=cv, scoring="f1_macro")
            results[name] = float(np.mean(scores))
            logger.info("%s CV f1_macro: %s", name, results[name])
        except Exception as exc:
            logger.warning("Failed CV for %s: %s", name, exc)
            results[name] = 0.0
    # pick best
    best_name = max(results, key=results.get)
    return best_name, results


def main() -> None:
    load_dotenv()

    root = Path(__file__).parent
    candidates = []
    for pattern in ["data/*.csv", "data/processed/*.csv", "*.csv"]:
        candidates.extend(root.glob(pattern))

    data_files = [
        str(path)
        for path in candidates
        if path.is_file() and "report" not in path.name.lower()
    ]
    logger.info("Training hybrid ML models on %s file(s)", len(data_files))

    frames = []
    for p in data_files:
        try:
            frames.append(pd.read_csv(p))
        except Exception:
            try:
                frames.append(pd.read_excel(p))
            except Exception as exc:
                logger.warning("Skipping file %s: %s", p, exc)

    features_df, role_series, action_series, anomaly_features = _build_training_frame(
        frames
    )
    if features_df.empty:
        logger.error("No features extracted; aborting training")
        return

    categorical_features = ["dtype", "name_token"]
    numeric_features = [
        "missing_pct",
        "unique_pct",
        "unique_ratio",
        "avg_length",
        "max_length",
        "digit_ratio",
        "alpha_ratio",
        "whitespace_ratio",
        "special_ratio",
        "numeric_parse_ratio",
        "date_parse_ratio",
        "sample_count",
    ]

    preprocessor = build_preprocessor(numeric_features, categorical_features)

    # Candidate models
    candidates_role = {
        "random_forest": RandomForestClassifier(
            n_estimators=250,
            random_state=42,
            class_weight="balanced_subsample",
            min_samples_leaf=2,
        )
    }
    candidates_action = {
        "random_forest": RandomForestClassifier(
            n_estimators=250,
            random_state=42,
            class_weight="balanced_subsample",
            min_samples_leaf=2,
        )
    }
    if XGBClassifier is not None:
        candidates_role["xgboost"] = XGBClassifier(
            use_label_encoder=False, eval_metric="logloss", random_state=42
        )
        candidates_action["xgboost"] = XGBClassifier(
            use_label_encoder=False, eval_metric="logloss", random_state=42
        )
    if LGBMClassifier is not None:
        candidates_role["lightgbm"] = LGBMClassifier(random_state=42)
        candidates_action["lightgbm"] = LGBMClassifier(random_state=42)

    logger.info(
        "Evaluating role prediction candidates: %s", list(candidates_role.keys())
    )
    best_role_name, role_scores = evaluate_and_select(
        features_df, role_series, preprocessor, candidates_role
    )
    logger.info("Best role model: %s", best_role_name)

    logger.info(
        "Evaluating action prediction candidates: %s", list(candidates_action.keys())
    )
    best_action_name, action_scores = evaluate_and_select(
        features_df, action_series, preprocessor, candidates_action
    )
    logger.info("Best action model: %s", best_action_name)

    # Train and persist best models
    best_role_clf = candidates_role[best_role_name]
    best_action_clf = candidates_action[best_action_name]

    role_pipeline = Pipeline(
        steps=[("preprocessor", preprocessor), ("model", best_role_clf)]
    )
    action_pipeline = Pipeline(
        steps=[("preprocessor", preprocessor), ("model", best_action_clf)]
    )

    role_pipeline.fit(features_df, role_series)
    action_pipeline.fit(features_df, action_series)

    # Anomaly model (use same logic as HybridMLService)
    normal_mask = [True]
    try:
        from src.hybrid_ml import _infer_role_from_features, _is_normal_column

        normal_mask = [
            _is_normal_column(row, _infer_role_from_features(row))
            for row in features_df.to_dict(orient="records")
        ]
        normal_rows = anomaly_features[
            pd.Series(normal_mask, index=anomaly_features.index)
        ]
        if normal_rows.empty:
            normal_rows = anomaly_features
    except Exception:
        normal_rows = anomaly_features

    anomaly_model = IsolationForest(
        n_estimators=200, contamination=0.15, random_state=42
    )
    anomaly_model.fit(normal_rows)

    joblib.dump(role_pipeline, ROLE_MODEL_PATH)
    joblib.dump(action_pipeline, ACTION_MODEL_PATH)
    joblib.dump(anomaly_model, ANOMALY_MODEL_PATH)

    meta = {
        "trained_columns": int(len(features_df)),
        "best_role_model": best_role_name,
        "best_action_model": best_action_name,
        "role_cv_scores": role_scores,
        "action_cv_scores": action_scores,
    }

    logger.info("Training complete. Meta: %s", meta)


if __name__ == "__main__":
    main()
