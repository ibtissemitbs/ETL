from __future__ import annotations

from typing import Any

import pandas as pd

from .domain_context import build_domain_context


def _infer_basic_type(
    column_name: str,
    dtype: str,
    numeric_ratio: float,
    date_ratio: float,
    unique_ratio: float,
) -> str:
    col_lower = column_name.lower()

    if any(token in col_lower for token in ["id", "identifier", "code", "uuid"]):
        if unique_ratio >= 0.7:
            return "identifiant"

    if any(
        token in col_lower
        for token in [
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
        return "datetime"

    if date_ratio >= 0.7:
        return "datetime"

    if pd.api.types.is_numeric_dtype(dtype) or numeric_ratio >= 0.7:
        if any(token in col_lower for token in ["phone", "postal", "zip"]):
            return "int"
        return "float" if "float" in dtype else "int"

    if any(
        token in col_lower
        for token in [
            "status",
            "type",
            "category",
            "genre",
            "sexe",
            "country",
            "region",
        ]
    ):
        return "category"

    if unique_ratio <= 0.25 and dtype == "object":
        return "category"

    return "string"


def _value_text_stats(values: list[str]) -> dict[str, Any]:
    if not values:
        return {
            "avg_length": 0.0,
            "max_length": 0,
            "digit_ratio": 0.0,
            "alpha_ratio": 0.0,
            "whitespace_ratio": 0.0,
            "special_ratio": 0.0,
            "numeric_parse_ratio": 0.0,
            "date_parse_ratio": 0.0,
            "has_mixed_case": False,
        }

    lengths = [len(value) for value in values]
    total_chars = sum(lengths) or 1
    digit_chars = sum(char.isdigit() for value in values for char in value)
    alpha_chars = sum(char.isalpha() for value in values for char in value)
    whitespace_chars = sum(char.isspace() for value in values for char in value)
    special_chars = total_chars - digit_chars - alpha_chars - whitespace_chars

    sample_series = pd.Series(values)
    numeric_parse_ratio = float(
        pd.to_numeric(sample_series, errors="coerce").notna().mean()
    )
    date_parse_ratio = float(
        pd.to_datetime(sample_series, errors="coerce", format="mixed").notna().mean()
    )

    has_mixed_case = any(
        any(c.islower() for c in value) and any(c.isupper() for c in value)
        for value in values
    )

    return {
        "avg_length": round(sum(lengths) / len(lengths), 2),
        "max_length": int(max(lengths)),
        "digit_ratio": round(digit_chars / total_chars, 4),
        "alpha_ratio": round(alpha_chars / total_chars, 4),
        "whitespace_ratio": round(whitespace_chars / total_chars, 4),
        "special_ratio": round(max(special_chars, 0) / total_chars, 4),
        "numeric_parse_ratio": round(numeric_parse_ratio, 4),
        "date_parse_ratio": round(date_parse_ratio, 4),
        "has_mixed_case": bool(has_mixed_case),
    }


class DataProfiler:
    """Data profiling class for analyzing datasets"""

    @staticmethod
    def profile(df: pd.DataFrame) -> dict:
        """Profile a DataFrame"""
        return build_dataset_profile(df)


def build_dataset_profile(df: pd.DataFrame) -> dict:
    profile = {
        "n_rows": len(df),
        "n_columns": len(df.columns),
        "dataset": {
            "rows": len(df),
            "columns": len(df.columns),
        },
        "schema": [],
        "columns": [],
    }

    # Large uploads do not need full per-cell profiling for every ratio.
    # Sampling keeps the ETL responsive while preserving enough signal for domain detection.
    use_sample = len(df) > 20000
    sample_size = 2000 if use_sample else None

    for col in df.columns:
        non_null = df[col].dropna()
        if use_sample and len(non_null) > 0:
            profiled_values = non_null.sample(
                n=min(sample_size or len(non_null), len(non_null)), random_state=42
            )
        else:
            profiled_values = non_null

        sample_values = profiled_values.astype(str).head(10).tolist()
        unique_count = int(df[col].nunique(dropna=True))
        unique_ratio = round(unique_count / max(len(df), 1), 4)
        numeric_ratio = (
            float(pd.to_numeric(profiled_values, errors="coerce").notna().mean())
            if len(profiled_values)
            else 0.0
        )
        date_ratio = (
            float(
                pd.to_datetime(
                    profiled_values, errors="coerce", format="mixed"
                ).notna().mean()
            )
            if len(profiled_values)
            else 0.0
        )
        text_stats = _value_text_stats(sample_values)
        inferred_type = _infer_basic_type(
            str(col), str(df[col].dtype), numeric_ratio, date_ratio, unique_ratio
        )

        column_profile = {
            "name": col,
            "dtype": str(df[col].dtype),
            "missing_count": int(df[col].isna().sum()),
            "missing_pct": round(float(df[col].isna().mean() * 100), 2),
            "unique_count": unique_count,
            "unique_pct": round(unique_ratio * 100, 2),
            "sample_values": sample_values,
            **text_stats,
            "numeric_parse_ratio": round(numeric_ratio, 4),
            "date_parse_ratio": round(date_ratio, 4),
            "inferred_type": inferred_type,
        }

        profile["schema"].append(
            {
                "name": col,
                "type": inferred_type,
                "nulls": int(df[col].isna().sum()),
            }
        )

        profile["columns"].append(column_profile)

    profile["domain_context"] = build_domain_context(profile, dataframe=df)

    return profile
