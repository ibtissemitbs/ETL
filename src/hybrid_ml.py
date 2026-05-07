from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

try:
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import IsolationForest, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import GridSearchCV, StratifiedKFold
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - optional fallback
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent.parent / "models"


def _normalize_domain(domain: Optional[str]) -> str:
    if not domain:
        return "generic"
    return str(domain).strip().lower()


def _build_model_paths(domain: Optional[str]) -> Dict[str, Path]:
    norm_domain = _normalize_domain(domain)
    if norm_domain == "generic":
        return {
            "role": MODEL_DIR / "column_role_model.joblib",
            "action": MODEL_DIR / "action_model.joblib",
            "anomaly": MODEL_DIR / "anomaly_model.joblib",
            "meta": MODEL_DIR / "hybrid_ml_meta.json",
        }

    return {
        "role": MODEL_DIR / f"{norm_domain}_column_role_model.joblib",
        "action": MODEL_DIR / f"{norm_domain}_action_model.joblib",
        "anomaly": MODEL_DIR / f"{norm_domain}_anomaly_model.joblib",
        "meta": MODEL_DIR / f"{norm_domain}_hybrid_ml_meta.json",
    }


ROLE_LABELS = ["identifiant", "date", "numerique", "texte", "categorie"]
ACTION_LABELS = [
    "fill_missing",
    "convert_type",
    "standardize_date",
    "remove_duplicate",
    "mark_as_anomaly",
    "reject_row",
    "ignore",
]


def _safe_float(value: Any) -> float:
    try:
        numeric = float(value)
        if np.isnan(numeric) or np.isinf(numeric):
            return 0.0
        return numeric
    except Exception:
        return 0.0


def _name_token(column_name: str) -> str:
    name = column_name.lower()
    if any(
        keyword in name
        for keyword in [
            "date",
            "time",
            "naissance",
            "birth",
            "order",
            "delivery",
            "created",
            "updated",
        ]
    ):
        return "date"
    if any(keyword in name for keyword in ["id", "uuid", "identifier", "code", "ref"]):
        return "identifiant"
    if any(
        keyword in name
        for keyword in [
            "price",
            "amount",
            "qty",
            "quantity",
            "total",
            "salary",
            "count",
            "rate",
            "score",
            "phone",
            "postal",
            "zip",
        ]
    ):
        return "numerique"
    if any(
        keyword in name
        for keyword in [
            "status",
            "type",
            "category",
            "genre",
            "sexe",
            "country",
            "region",
            "city",
        ]
    ):
        return "categorie"
    if any(
        keyword in name
        for keyword in [
            "name",
            "title",
            "description",
            "comment",
            "address",
            "email",
            "product",
        ]
    ):
        return "texte"
    return "other"


def _infer_role_from_features(features: Dict[str, Any]) -> str:
    name = str(features.get("column_name", "")).lower()
    name_token = str(features.get("name_token", "other"))
    unique_ratio = _safe_float(features.get("unique_ratio"))
    numeric_ratio = _safe_float(features.get("numeric_parse_ratio"))
    date_ratio = _safe_float(features.get("date_parse_ratio"))
    dtype = str(features.get("dtype", ""))

    if name_token == "identifiant" or ("id" in name and unique_ratio >= 0.65):
        return "identifiant"
    if name_token == "date" or date_ratio >= 0.7:
        return "date"
    if (
        name_token == "numerique"
        or pd.api.types.is_numeric_dtype(dtype)
        or numeric_ratio >= 0.75
    ):
        return "numerique"
    if name_token == "categorie" or unique_ratio <= 0.3:
        return "categorie"
    return "texte"


def _infer_action_from_features(features: Dict[str, Any], role_label: str) -> str:
    missing_pct = _safe_float(features.get("missing_pct"))
    numeric_ratio = _safe_float(features.get("numeric_parse_ratio"))
    date_ratio = _safe_float(features.get("date_parse_ratio"))
    unique_ratio = _safe_float(features.get("unique_ratio"))
    whitespace_ratio = _safe_float(features.get("whitespace_ratio"))
    special_ratio = _safe_float(features.get("special_ratio"))
    mixed_case = bool(features.get("has_mixed_case"))
    name_token = str(features.get("name_token", "other"))
    column_name = str(features.get("column_name", "")).lower()

    if missing_pct >= 50:
        return "reject_row"
    if role_label == "date" and (date_ratio < 0.8 or name_token == "date"):
        return "standardize_date"
    if role_label == "numerique" and numeric_ratio < 0.8:
        return "convert_type"
    if role_label == "identifiant" and unique_ratio < 0.9:
        return "remove_duplicate"
    if role_label == "numerique" and (special_ratio > 0.25 or mixed_case):
        return "mark_as_anomaly"
    if missing_pct >= 5:
        return "fill_missing"
    if role_label == "categorie" and (whitespace_ratio > 0.02 or mixed_case):
        return "fill_missing"
    return "ignore"


def _is_normal_column(features: Dict[str, Any], role_label: str) -> bool:
    missing_pct = _safe_float(features.get("missing_pct"))
    numeric_ratio = _safe_float(features.get("numeric_parse_ratio"))
    date_ratio = _safe_float(features.get("date_parse_ratio"))
    unique_ratio = _safe_float(features.get("unique_ratio"))

    if missing_pct > 15:
        return False
    if role_label == "date" and date_ratio < 0.7:
        return False
    if role_label == "numerique" and numeric_ratio < 0.7:
        return False
    if role_label == "identifiant" and unique_ratio < 0.6:
        return False
    return True


def _extract_features_from_series(df: pd.DataFrame, column_name: str) -> Dict[str, Any]:
    series = df[column_name]
    non_null = series.dropna()
    sample_values = non_null.astype(str).head(50).tolist()

    lengths = [len(value) for value in sample_values] or [0]
    total_chars = sum(lengths) or 1
    digit_chars = sum(char.isdigit() for value in sample_values for char in value)
    alpha_chars = sum(char.isalpha() for value in sample_values for char in value)
    whitespace_chars = sum(char.isspace() for value in sample_values for char in value)
    special_chars = max(total_chars - digit_chars - alpha_chars - whitespace_chars, 0)

    numeric_ratio = (
        float(pd.to_numeric(non_null, errors="coerce").notna().mean())
        if len(non_null)
        else 0.0
    )
    date_ratio = (
        float(pd.to_datetime(non_null, errors="coerce", format="mixed").notna().mean())
        if len(non_null)
        else 0.0
    )
    unique_ratio = float(series.nunique(dropna=True) / max(len(df), 1))

    return {
        "column_name": column_name,
        "dtype": str(series.dtype),
        "name_token": _name_token(column_name),
        "missing_count": int(series.isna().sum()),
        "missing_pct": round(float(series.isna().mean() * 100), 4),
        "unique_count": int(series.nunique(dropna=True)),
        "unique_pct": round(unique_ratio * 100, 4),
        "unique_ratio": round(unique_ratio, 4),
        "avg_length": round(float(np.mean(lengths)), 4),
        "max_length": int(max(lengths)),
        "digit_ratio": round(digit_chars / total_chars, 4),
        "alpha_ratio": round(alpha_chars / total_chars, 4),
        "whitespace_ratio": round(whitespace_chars / total_chars, 4),
        "special_ratio": round(special_chars / total_chars, 4),
        "numeric_parse_ratio": round(numeric_ratio, 4),
        "date_parse_ratio": round(date_ratio, 4),
        "has_mixed_case": bool(
            any(
                any(c.islower() for c in value) and any(c.isupper() for c in value)
                for value in sample_values
            )
        ),
        "sample_count": len(sample_values),
    }


def _profile_to_rows(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for column in profile.get("columns", []):
        row = dict(column)
        row["name_token"] = _name_token(str(column.get("name", "")))
        row["column_name"] = str(column.get("name", ""))
        row["dtype"] = str(column.get("dtype", "string"))
        row.setdefault("unique_count", 0)
        row.setdefault("unique_pct", 0.0)
        row.setdefault("unique_ratio", 0.0)
        row.setdefault("missing_pct", 0.0)
        row.setdefault("numeric_parse_ratio", 0.0)
        row.setdefault("date_parse_ratio", 0.0)
        row.setdefault("whitespace_ratio", 0.0)
        row.setdefault("special_ratio", 0.0)
        row.setdefault("avg_length", 0.0)
        row.setdefault("max_length", 0)
        row.setdefault("has_mixed_case", False)
        row.setdefault("sample_count", 0)
        rows.append(row)
    return rows


def _select_numeric_columns() -> List[str]:
    return [
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


def _build_training_frame(
    dataframes: Iterable[pd.DataFrame],
) -> Tuple[pd.DataFrame, pd.Series, pd.Series, pd.DataFrame]:
    feature_rows: List[Dict[str, Any]] = []
    role_labels: List[str] = []
    action_labels: List[str] = []

    for df in dataframes:
        if df is None or df.empty:
            continue
        for column_name in df.columns:
            features = _extract_features_from_series(df, column_name)
            role_label = _infer_role_from_features(features)
            action_label = _infer_action_from_features(features, role_label)

            feature_rows.append(features)
            role_labels.append(role_label)
            action_labels.append(action_label)

    if not feature_rows:
        empty = pd.DataFrame()
        return empty, pd.Series(dtype=str), pd.Series(dtype=str), empty

    features_df = pd.DataFrame(feature_rows)
    role_series = pd.Series(role_labels, name="role")
    action_series = pd.Series(action_labels, name="action")
    anomaly_features = features_df[_select_numeric_columns()].copy()
    return features_df, role_series, action_series, anomaly_features


@dataclass
class HybridPrediction:
    role_predictions: Dict[str, Dict[str, Any]]
    action_predictions: Dict[str, Dict[str, Any]]
    anomaly_scores: Dict[str, Dict[str, Any]]
    summary: Dict[str, Any]


class HybridMLService:
    def __init__(self, domain: Optional[str] = None) -> None:
        self.domain = _normalize_domain(domain)
        self.model_dir = MODEL_DIR
        self.model_dir.mkdir(parents=True, exist_ok=True)
        paths = _build_model_paths(self.domain)
        self.role_model_path = paths["role"]
        self.action_model_path = paths["action"]
        self.anomaly_model_path = paths["anomaly"]
        self.meta_path = paths["meta"]
        self.role_model = None
        self.action_model = None
        self.anomaly_model = None
        self.meta: Dict[str, Any] = {}
        self.load()

    def load(self) -> bool:
        if not SKLEARN_AVAILABLE:
            logger.warning(
                "scikit-learn not available; hybrid ML service will use heuristics only"
            )
            return False

        loaded = False
        if self.role_model_path.exists():
            try:
                self.role_model = joblib.load(self.role_model_path)
                loaded = True
            except Exception as exc:
                logger.warning(
                    "Unable to load role model %s: %s", self.role_model_path, exc
                )
                self.role_model = None
        if self.action_model_path.exists():
            try:
                self.action_model = joblib.load(self.action_model_path)
                loaded = True
            except Exception as exc:
                logger.warning(
                    "Unable to load action model %s: %s", self.action_model_path, exc
                )
                self.action_model = None
        if self.anomaly_model_path.exists():
            try:
                self.anomaly_model = joblib.load(self.anomaly_model_path)
                loaded = True
            except Exception as exc:
                logger.warning(
                    "Unable to load anomaly model %s: %s", self.anomaly_model_path, exc
                )
                self.anomaly_model = None
        if self.meta_path.exists():
            with open(self.meta_path, "r", encoding="utf-8") as f:
                self.meta = json.load(f)
        return loaded

    def train(self, dataframes: Iterable[pd.DataFrame]) -> Dict[str, Any]:
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn is required to train the hybrid ML models")

        features_df, role_labels, action_labels, anomaly_features = (
            _build_training_frame(dataframes)
        )
        if features_df.empty:
            raise ValueError("No training data available for hybrid ML models")

        categorical_features = ["dtype", "name_token"]
        numeric_features = _select_numeric_columns()

        preprocessor = ColumnTransformer(
            transformers=[
                ("num", SimpleImputer(strategy="median"), numeric_features),
                (
                    "cat",
                    Pipeline(
                        steps=[
                            ("imputer", SimpleImputer(strategy="most_frequent")),
                            (
                                "encoder",
                                OneHotEncoder(
                                    handle_unknown="ignore", sparse_output=False
                                ),
                            ),
                        ]
                    ),
                    categorical_features,
                ),
            ]
        )

        role_pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=250,
                        random_state=42,
                        class_weight="balanced_subsample",
                        min_samples_leaf=2,
                    ),
                ),
            ]
        )
        role_pipeline.fit(features_df, role_labels)

        action_pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=250,
                        random_state=42,
                        class_weight="balanced_subsample",
                        min_samples_leaf=2,
                    ),
                ),
            ]
        )
        action_pipeline.fit(features_df, action_labels)

        normal_mask = [
            _is_normal_column(row, _infer_role_from_features(row))
            for row in features_df.to_dict(orient="records")
        ]
        normal_rows = anomaly_features[
            pd.Series(normal_mask, index=anomaly_features.index)
        ]
        if normal_rows.empty:
            normal_rows = anomaly_features

        anomaly_model = IsolationForest(
            n_estimators=200,
            contamination=0.15,
            random_state=42,
        )
        anomaly_model.fit(normal_rows)

        self.role_model = role_pipeline
        self.action_model = action_pipeline
        self.anomaly_model = anomaly_model
        self.meta = {
            "trained_columns": int(len(features_df)),
            "trained_roles": sorted(set(role_labels)),
            "trained_actions": sorted(set(action_labels)),
            "feature_columns": numeric_features + categorical_features,
        }

        joblib.dump(self.role_model, self.role_model_path)
        joblib.dump(self.action_model, self.action_model_path)
        joblib.dump(self.anomaly_model, self.anomaly_model_path)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.meta, f, indent=2, ensure_ascii=False)

        return self.meta

    def train_from_files(
        self, file_paths: Optional[Iterable[str]] = None
    ) -> Dict[str, Any]:
        frames: List[pd.DataFrame] = []
        paths = list(file_paths or self._discover_training_files())
        for file_path in paths:
            try:
                path = Path(file_path)
                if path.suffix.lower() == ".csv":
                    frames.append(pd.read_csv(path))
                elif path.suffix.lower() in {".xlsx", ".xls"}:
                    frames.append(pd.read_excel(path))
            except Exception as exc:
                logger.warning("Skipping training file %s: %s", file_path, exc)

        return self.train(frames)

    def tune_and_train(
        self, dataframes: Iterable[pd.DataFrame], n_jobs: int = -1
    ) -> Dict[str, Any]:
        """Perform hyperparameter tuning (GridSearchCV) across RF/XGB/LGB candidates and train final models."""
        if not SKLEARN_AVAILABLE:
            raise RuntimeError(
                "scikit-learn is required to tune/train the hybrid ML models"
            )

        features_df, role_labels, action_labels, anomaly_features = (
            _build_training_frame(dataframes)
        )
        if features_df.empty:
            raise ValueError("No training data available for tuning")

        categorical_features = ["dtype", "name_token"]
        numeric_features = _select_numeric_columns()

        preprocessor = ColumnTransformer(
            transformers=[
                ("num", SimpleImputer(strategy="median"), numeric_features),
                (
                    "cat",
                    Pipeline(
                        steps=[
                            ("imputer", SimpleImputer(strategy="most_frequent")),
                            (
                                "encoder",
                                OneHotEncoder(
                                    handle_unknown="ignore", sparse_output=False
                                ),
                            ),
                        ]
                    ),
                    categorical_features,
                ),
            ]
        )

        cv = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)

        # Candidate estimators and parameter grids
        candidates = {}
        rf = RandomForestClassifier(random_state=42, class_weight="balanced_subsample")
        candidates["random_forest"] = (
            rf,
            {
                "model__n_estimators": [100, 250],
                "model__min_samples_leaf": [1, 2],
            },
        )

        try:
            from xgboost import XGBClassifier

            xgb = XGBClassifier(
                use_label_encoder=False, eval_metric="logloss", random_state=42
            )
            candidates["xgboost"] = (
                xgb,
                {"model__n_estimators": [100, 250], "model__max_depth": [3, 6]},
            )
        except Exception:
            logger.info("XGBoost not available for tuning")

        try:
            from lightgbm import LGBMClassifier

            lgb = LGBMClassifier(random_state=42)
            candidates["lightgbm"] = (
                lgb,
                {"model__n_estimators": [100, 250], "model__num_leaves": [31, 63]},
            )
        except Exception:
            logger.info("LightGBM not available for tuning")

        def run_grid(X: pd.DataFrame, y: pd.Series):
            best_models = {}
            scores = {}
            for name, (estimator, grid) in candidates.items():
                pipe = Pipeline(
                    steps=[("preprocessor", preprocessor), ("model", estimator)]
                )
                try:
                    search = GridSearchCV(
                        pipe, param_grid=grid, scoring="f1_macro", cv=cv, n_jobs=n_jobs
                    )
                    search.fit(X, y)
                    best_models[name] = search.best_estimator_
                    scores[name] = float(search.best_score_)
                    logger.info("Tuned %s best_score=%s", name, scores[name])
                except Exception as exc:
                    logger.warning("GridSearch failed for %s: %s", name, exc)
                    scores[name] = 0.0
            if not scores:
                raise RuntimeError("No candidate models available for tuning")
            best_name = max(scores, key=scores.get)
            return best_name, best_models, scores

        # Tune for role and action separately
        logger.info("Starting hyperparameter tuning for role prediction")
        best_role_name, best_role_models, role_scores = run_grid(
            features_df, role_labels
        )

        logger.info("Starting hyperparameter tuning for action prediction")
        best_action_name, best_action_models, action_scores = run_grid(
            features_df, action_labels
        )

        # Final selected estimators
        final_role_pipeline = best_role_models[best_role_name]
        final_action_pipeline = best_action_models[best_action_name]

        # Fit anomaly model similarly to train()
        normal_mask = [
            _is_normal_column(row, _infer_role_from_features(row))
            for row in features_df.to_dict(orient="records")
        ]
        normal_rows = anomaly_features[
            pd.Series(normal_mask, index=anomaly_features.index)
        ]
        if normal_rows.empty:
            normal_rows = anomaly_features

        anomaly_model = IsolationForest(
            n_estimators=200, contamination=0.15, random_state=42
        )
        anomaly_model.fit(normal_rows)

        # Persist
        self.role_model = final_role_pipeline
        self.action_model = final_action_pipeline
        self.anomaly_model = anomaly_model
        self.meta = {
            "trained_columns": int(len(features_df)),
            "best_role_model": best_role_name,
            "best_action_model": best_action_name,
            "role_cv_scores": role_scores,
            "action_cv_scores": action_scores,
        }

        joblib.dump(self.role_model, self.role_model_path)
        joblib.dump(self.action_model, self.action_model_path)
        joblib.dump(self.anomaly_model, self.anomaly_model_path)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.meta, f, indent=2, ensure_ascii=False)

        return self.meta

    def tune_and_train_from_files(
        self, file_paths: Optional[Iterable[str]] = None, n_jobs: int = -1
    ) -> Dict[str, Any]:
        frames: List[pd.DataFrame] = []
        paths = list(file_paths or self._discover_training_files())
        for file_path in paths:
            try:
                path = Path(file_path)
                if path.suffix.lower() == ".csv":
                    frames.append(pd.read_csv(path))
                elif path.suffix.lower() in {".xlsx", ".xls"}:
                    frames.append(pd.read_excel(path))
            except Exception as exc:
                logger.warning("Skipping training file %s: %s", file_path, exc)

        return self.tune_and_train(frames, n_jobs=n_jobs)

    def _discover_training_files(self) -> List[str]:
        candidates: List[Path] = []
        root = Path(__file__).parent.parent
        for pattern in ["data/*.csv", "data/processed/*.csv", "*.csv"]:
            candidates.extend(root.glob(pattern))

        unique: List[str] = []
        seen = set()
        for path in candidates:
            if (
                path.is_file()
                and path.name not in seen
                and "report" not in path.name.lower()
            ):
                seen.add(path.name)
                unique.append(str(path))
        return unique

    def _prepare_inference_frame(
        self, profile: Dict[str, Any], dataframe: Optional[pd.DataFrame]
    ) -> pd.DataFrame:
        if dataframe is not None and not dataframe.empty:
            rows = [
                _extract_features_from_series(dataframe, column_name)
                for column_name in dataframe.columns
            ]
            return pd.DataFrame(rows)
        return pd.DataFrame(_profile_to_rows(profile))

    def predict(
        self, profile: Dict[str, Any], dataframe: Optional[pd.DataFrame] = None
    ) -> HybridPrediction:
        features_df = self._prepare_inference_frame(profile, dataframe)
        if features_df.empty:
            return HybridPrediction({}, {}, {}, {"message": "No features available"})

        role_predictions: Dict[str, Dict[str, Any]] = {}
        action_predictions: Dict[str, Dict[str, Any]] = {}
        anomaly_scores: Dict[str, Dict[str, Any]] = {}

        for _, row in features_df.iterrows():
            column_name = str(row.get("column_name", row.get("name", "unknown")))
            row_dict = row.to_dict()
            role_fallback = _infer_role_from_features(row_dict)
            action_fallback = _infer_action_from_features(row_dict, role_fallback)

            if self.role_model is not None:
                row_frame = pd.DataFrame([row_dict])
                role_label = str(self.role_model.predict(row_frame)[0])
                role_prob = float(np.max(self.role_model.predict_proba(row_frame)))
            else:
                role_label = role_fallback
                role_prob = 0.55

            if self.action_model is not None:
                row_frame = pd.DataFrame([row_dict])
                action_label = str(self.action_model.predict(row_frame)[0])
                action_prob = float(np.max(self.action_model.predict_proba(row_frame)))
            else:
                action_label = action_fallback
                action_prob = 0.55

            anomaly_input = pd.DataFrame(
                [{key: row_dict.get(key, 0.0) for key in _select_numeric_columns()}]
            )
            if self.anomaly_model is not None:
                score = float(self.anomaly_model.decision_function(anomaly_input)[0])
                anomaly_flag = bool(self.anomaly_model.predict(anomaly_input)[0] == -1)
            else:
                score = 0.0
                anomaly_flag = not _is_normal_column(row_dict, role_label)

            role_predictions[column_name] = {
                "label": role_label,
                "confidence": round(role_prob, 4),
                "fallback": role_fallback,
            }
            action_predictions[column_name] = {
                "label": action_label,
                "confidence": round(action_prob, 4),
                "fallback": action_fallback,
            }
            anomaly_scores[column_name] = {
                "score": round(score, 4),
                "flagged": anomaly_flag,
            }

        top_actions: Dict[str, int] = {}
        suspicious_columns: List[str] = []
        for column_name, action in action_predictions.items():
            top_actions[action["label"]] = top_actions.get(action["label"], 0) + 1
            if anomaly_scores.get(column_name, {}).get("flagged"):
                suspicious_columns.append(column_name)

        summary = {
            "columns_analyzed": len(features_df),
            "suspicious_columns": suspicious_columns[:10],
            "action_counts": top_actions,
            "role_counts": {
                label: sum(
                    1 for item in role_predictions.values() if item["label"] == label
                )
                for label in ROLE_LABELS
            },
            "model_mode": "trained" if self.role_model is not None else "heuristic",
        }

        return HybridPrediction(
            role_predictions, action_predictions, anomaly_scores, summary
        )

    def build_llm_context(
        self, profile: Dict[str, Any], dataframe: Optional[pd.DataFrame] = None
    ) -> str:
        prediction = self.predict(profile, dataframe)
        summary = prediction.summary

        roles_text = ", ".join(
            f"{role}: {count}"
            for role, count in summary.get("role_counts", {}).items()
            if count
        )
        actions_text = ", ".join(
            f"{action}: {count}"
            for action, count in summary.get("action_counts", {}).items()
            if count
        )
        suspicious = ", ".join(summary.get("suspicious_columns", [])) or "none"

        details = [
            "## ML INSIGHTS",
            f"Model mode: {summary.get('model_mode', 'heuristic')}",
            f"Columns analyzed: {summary.get('columns_analyzed', 0)}",
            f"Predicted roles: {roles_text or 'none'}",
            f"Recommended plan actions: {actions_text or 'none'}",
            f"Suspicious columns: {suspicious}",
            "Use these ML signals to draft a plan only. Do not mutate data directly in the LLM output.",
        ]
        return "\n".join(details)


_SERVICES: Dict[str, HybridMLService] = {}


def get_hybrid_ml_service(domain: Optional[str] = None) -> HybridMLService:
    key = _normalize_domain(domain)
    if key not in _SERVICES:
        _SERVICES[key] = HybridMLService(domain=key)
    return _SERVICES[key]


def train_hybrid_models_from_workspace(
    file_paths: Optional[Iterable[str]] = None,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    service = get_hybrid_ml_service(domain=domain)
    return service.train_from_files(file_paths)
