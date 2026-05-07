from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import pandas as pd


def _find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    lowered_map = {str(col).strip().lower(): col for col in df.columns}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in lowered_map:
            return lowered_map[key]
    return None


def _is_money_like_column(col_name: str) -> bool:
    lowered = str(col_name).strip().lower()
    return any(
        token in lowered
        for token in [
            "amount",
            "price",
            "cost",
            "salary",
            "revenue",
            "total",
            "montant",
            "prix",
        ]
    )


def fill_missing(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    col = params.get("column")
    if col not in df.columns:
        return df

    strategy = str(params.get("strategy", "mode")).lower()
    value = params.get("value")

    if strategy == "constant":
        df[col] = df[col].fillna(value)
    elif strategy == "median" and pd.api.types.is_numeric_dtype(df[col]):
        df[col] = df[col].fillna(df[col].median())
    elif strategy == "mean" and pd.api.types.is_numeric_dtype(df[col]):
        df[col] = df[col].fillna(df[col].mean())
    else:
        mode = df[col].mode(dropna=True)
        if not mode.empty:
            df[col] = df[col].fillna(mode.iloc[0])
    return df


def normalize_text(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    col = params.get("column")
    if col not in df.columns:
        return df

    case_type = str(params.get("case", "strip")).lower()
    series = df[col].astype("string").str.strip()

    if case_type == "lower":
        series = series.str.lower()
    elif case_type == "upper":
        series = series.str.upper()
    elif case_type == "title":
        series = series.str.title()

    df[col] = series
    return df


def validate_values(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    col = params.get("column")
    if col not in df.columns:
        return df

    min_val = params.get("min")
    max_val = params.get("max")
    allowed = params.get("allowed_values")

    if allowed is not None:
        mask = df[col].isin(allowed) | df[col].isna()
        df.loc[~mask, col] = pd.NA
        return df

    if min_val is not None or max_val is not None:
        values = pd.to_numeric(df[col], errors="coerce")
        mask = pd.Series([True] * len(df), index=df.index)
        if min_val is not None:
            mask &= values >= min_val
        if max_val is not None:
            mask &= values <= max_val
        df.loc[~mask, col] = pd.NA

    return df


def smart_type_conversion(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """Intelligently convert column types with aggressive detection.
    CRITICAL: Financial/numeric columns are NEVER converted to datetime.
    """
    col = params.get("column")
    if col not in df.columns:
        return df

    col_lower = col.lower()
    non_null = df[col].dropna()
    if len(non_null) == 0:
        return df

    numeric_ratio = float(pd.to_numeric(non_null, errors="coerce").notna().mean())
    date_ratio = float(
        pd.to_datetime(non_null, errors="coerce", format="mixed").notna().mean()
    )
    text_values = non_null.astype(str)
    alpha_ratio = float(
        (text_values.str.contains(r"[a-zA-Z]", regex=True, na=False)).mean()
    )

    # PRIORITY 1: Financial/Numeric columns MUST use pd.to_numeric() - NEVER datetime
    if any(
        kw in col_lower
        for kw in [
            "price",
            "amount",
            "cost",
            "salary",
            "qty",
            "quantity",
            "total",
            "revenue",
            "commission",
        ]
    ):
        if numeric_ratio >= 0.6:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    # PRIORITY 2: Date columns use pd.to_datetime() only
    if any(
        kw in col_lower
        for kw in [
            "date",
            "created",
            "updated",
            "birth",
            "naissance",
            "time",
            "timestamp",
        ]
    ):
        if date_ratio >= 0.5:
            df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")
        return df

    # PRIORITY 3: Generic numeric detection
    if numeric_ratio >= 0.8 and alpha_ratio < 0.2:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    # PRIORITY 4: Generic date detection ONLY if numeric_ratio is low
    if date_ratio >= 0.7 and numeric_ratio < 0.5:
        df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")
        return df

    return df


def aggressive_anomaly_detection(
    df: pd.DataFrame, params: Dict[str, Any]
) -> pd.DataFrame:
    """Aggressively flag anomalies using multiple heuristics."""
    col = params.get("column")
    if col not in df.columns:
        return df

    flag_col = params.get("flag_column") or f"{col}__anomaly"
    series = df[col]
    col_lower = col.lower()

    mask = pd.Series([False] * len(df), index=df.index)

    # Missing values are not automatically frauds. Only flag them when the caller
    # explicitly asks for it, or for identifier-like columns where absence is critical.
    if params.get("flag_missing", False) or any(
        kw in col_lower for kw in ["id", "identifier", "uuid", "code", "ref"]
    ):
        mask |= series.isna()

    if pd.api.types.is_numeric_dtype(series):
        numeric_series = pd.to_numeric(series, errors="coerce")
        if any(kw in col_lower for kw in ["price", "amount", "cost"]):
            mask |= numeric_series < 0
            mask |= numeric_series > numeric_series.quantile(0.99) * 10
        if any(kw in col_lower for kw in ["age", "qty", "quantity"]):
            mask |= numeric_series < 0
        if "percent" in col_lower or "ratio" in col_lower:
            mask |= (numeric_series < 0) | (numeric_series > 100)

        q1, q3 = numeric_series.quantile(0.25), numeric_series.quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            mask |= (numeric_series < (q1 - 3 * iqr)) | (
                numeric_series > (q3 + 3 * iqr)
            )

    if pd.api.types.is_datetime64_any_dtype(series):
        from datetime import datetime, timedelta

        today = pd.Timestamp.now()
        mask |= series > today
        mask |= series < pd.Timestamp("1900-01-01")

    if pd.api.types.is_object_dtype(series):
        text_series = series.astype(str)
        if "email" in col_lower:
            mask |= (
                ~text_series.str.contains(r"@.*\.", regex=True, na=False)
                & series.notna()
            )
        if "phone" in col_lower:
            digits_only = text_series.str.replace(r"\D", "", regex=True)
            mask |= (digits_only.str.len() < 7) & series.notna()
        if "url" in col_lower:
            mask |= (
                ~text_series.str.contains(r"https?://", regex=True, na=False)
                & series.notna()
            )

    df[flag_col] = mask.astype(bool)
    return df


def standardize_date(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    col = params.get("column")
    if col not in df.columns:
        return df
    # Avoid applying date standardization to money-like columns
    if _is_money_like_column(col):
        return df

    df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")
    return df


def remove_duplicate(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    subset = params.get("subset")
    if subset:
        valid_subset = [col for col in subset if col in df.columns]
        if valid_subset:
            return df.drop_duplicates(subset=valid_subset, keep="first")
    return df.drop_duplicates(keep="first")


def _build_anomaly_mask(
    df: pd.DataFrame, params: Dict[str, Any]
) -> Optional[pd.Series]:
    col = params.get("column")
    if col not in df.columns:
        return None

    series = df[col]
    problem = str(params.get("problem", "")).lower()
    numeric_series = pd.to_numeric(series, errors="coerce")

    if "negative" in problem:
        mask = numeric_series < 0
        if mask.notna().any():
            return mask.fillna(False)

    if any(token in problem for token in ["outlier", "extreme"]):
        q1 = numeric_series.quantile(0.25)
        q3 = numeric_series.quantile(0.75)
        if pd.notna(q1) and pd.notna(q3):
            iqr = q3 - q1
            if pd.notna(iqr) and iqr > 0:
                return (
                    (numeric_series < (q1 - 1.5 * iqr))
                    | (numeric_series > (q3 + 1.5 * iqr))
                ).fillna(False)

    if any(token in problem for token in ["missing", "null", "absent"]):
        return series.isna()

    if pd.api.types.is_numeric_dtype(series):
        return numeric_series.isna().fillna(True)

    return series.isna()


def mark_as_anomaly(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    col = params.get("column")
    if col not in df.columns:
        return df

    # Store anomalies in metadata by default so user-facing outputs stay clean.
    # A caller can still opt into a visible helper column with store="column".
    store = str(params.get("store", "metadata")).lower()
    flag_col = params.get("flag_column") or f"{col}__anomaly"
    mask = _build_anomaly_mask(df, params)
    if mask is None:
        return df

    if store == "metadata":
        anomalies = df.attrs.get("anomalies", {})
        anomalies[flag_col] = mask.astype(bool).to_list()
        df.attrs["anomalies"] = anomalies
        return df

    df[flag_col] = mask.astype(bool)
    return df


def reject_row(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    col = params.get("column")
    if col not in df.columns:
        return df

    flag_col = params.get("flag_column") or f"{col}__anomaly"
    mask = None
    if flag_col in df.columns:
        mask = df[flag_col].astype(bool)
    else:
        mask = _build_anomaly_mask(df, params)

    if mask is None:
        return df

    return df.loc[~mask].copy()


# New: derive useful columns (age, full_name, country) when possible
def derive_useful_columns(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    result = df

    # Derive age from date of birth with robust parsing (strings, Excel serials)
    dob_col = _find_column(
        result,
        [
            "date_of_birth",
            "birth_date",
            "date_naissance",
            "date de naissance",
            "date_naiss",
        ],
    )
    if dob_col and "age" not in result.columns:
        try:
            series = result[dob_col]
            # Already datetime: use directly to avoid accidental numeric conversion
            if pd.api.types.is_datetime64_any_dtype(series):
                dob_series = pd.to_datetime(series, errors="coerce")
                today = pd.Timestamp.now()
                age_series = (today - dob_series).dt.days // 365
                age_series = age_series.where((age_series >= 0) & (age_series <= 120))
                result["age"] = age_series.astype("Int64")
                return result

            # First try to coerce numeric-like strings to numeric (to detect Excel serials)
            numeric_vals = pd.to_numeric(series, errors="coerce")
            if numeric_vals.notna().any():
                max_val = numeric_vals.max()
            else:
                max_val = None

            # If many values look like Excel serials (numeric and large), treat those rows as Excel
            origin = pd.Timestamp("1899-12-30")
            numeric_frac = float(numeric_vals.notna().mean())
            if (
                max_val is not None
                and pd.notna(max_val)
                and max_val > 1000
                and numeric_frac >= 0.6
            ):
                dob_series = origin + pd.to_timedelta(numeric_vals, unit="D")
            else:
                # mixed content: convert numeric entries as Excel serials, parse others individually
                from dateutil.parser import parse as _parse

                parsed = []
                for i, v in enumerate(series):
                    # handle numeric-like entries
                    nv = numeric_vals.iat[i]
                    if pd.notna(nv) and nv > 1000:
                        parsed.append(origin + pd.to_timedelta(nv, unit="D"))
                        continue
                    s = str(v).strip()
                    if s == "" or s.lower() in ("nan", "none", "na", "<na>"):
                        parsed.append(pd.NaT)
                        continue
                    try:
                        dt = pd.to_datetime(s, errors="coerce")
                        if pd.notna(dt):
                            parsed.append(dt)
                            continue
                    except Exception:
                        pass
                    try:
                        dt = _parse(s, dayfirst=False)
                        parsed.append(pd.Timestamp(dt))
                        continue
                    except Exception:
                        try:
                            dt = _parse(s, dayfirst=True)
                            parsed.append(pd.Timestamp(dt))
                            continue
                        except Exception:
                            parsed.append(pd.NaT)

                dob_series = pd.to_datetime(pd.Series(parsed))

            today = pd.Timestamp.now()
            age_series = (today - dob_series).dt.days // 365
            # Clamp unrealistic ages and coerce to nullable Int
            age_series = age_series.where((age_series >= 0) & (age_series <= 120))
            result["age"] = age_series.astype("Int64")
        except Exception:
            pass

    # Derive full_name from first/last name
    first_col = _find_column(
        result, ["first_name", "prenom", "given_name", "prenom_nom", "prenom1"]
    ) or _find_column(result, ["prenom"])
    last_col = _find_column(
        result, ["last_name", "nom", "family_name", "surname"]
    ) or _find_column(result, ["nom"])
    if first_col and last_col and "full_name" not in result.columns:
        try:
            result["full_name"] = (
                result[first_col].astype("string").str.strip()
                + " "
                + result[last_col].astype("string").str.strip()
            ).str.strip()
        except Exception:
            pass

    # Copy nationality -> country when appropriate
    nat_col = _find_column(result, ["nationality", "pays", "country"])
    if nat_col and "country" not in result.columns:
        result["country"] = result[nat_col]

    return result


def drop_all_anomaly_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove all anomaly helper columns from final user-facing output."""
    drop_cols = [
        col
        for col in df.columns
        if str(col).startswith("__anomaly")
        or str(col).endswith("__anomaly")
        or str(col).startswith("anomaly_")
        or str(col).startswith("_anomaly_")
    ]
    if drop_cols:
        return df.drop(columns=drop_cols)
    return df


def _drop_useless_anomaly_columns(
    df: pd.DataFrame, min_true_ratio: float = 0.02
) -> pd.DataFrame:
    """Remove anomaly flag columns that contain almost no True values (i.e., not useful to keep as separate columns)."""
    cols_to_drop = []
    for col in df.columns:
        if (
            str(col).endswith("__anomaly")
            or str(col).startswith("anomaly_")
            or str(col).startswith("_anomaly_")
        ):
            try:
                series = df[col]
                # Normalize common textual boolean representations
                if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(
                    series
                ):
                    lowered = series.astype(str).str.strip().str.lower()
                    truthy = lowered.isin(["vrai", "true", "1", "yes", "y", "t"])
                    falsy = lowered.isin(
                        ["faux", "false", "0", "no", "n", "f"]
                    ) | lowered.isin(["nan", "none", "<na>"])
                    # where unknown, fall back to checking emptiness
                    bool_series = truthy.copy()
                    bool_series[~truthy & ~falsy] = series[~truthy & ~falsy].notna()
                else:
                    bool_series = series.astype(bool)

                true_ratio = float(bool_series.sum()) / max(1, len(bool_series))
                if true_ratio <= min_true_ratio:
                    cols_to_drop.append(col)
            except Exception:
                # if conversion fails, skip dropping
                continue

    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
    return df


action_map: Dict[str, Callable[[pd.DataFrame, Dict[str, Any]], pd.DataFrame]] = {
    "fill_missing": fill_missing,
    "remplir": fill_missing,
    "normalize_text": normalize_text,
    "normaliser": normalize_text,
    "convert_type": smart_type_conversion,
    "convertir": smart_type_conversion,
    "standardize_date": standardize_date,
    "standardiser_date": standardize_date,
    "remove_duplicate": remove_duplicate,
    "remove_duplicates": remove_duplicate,
    "mark_as_anomaly": mark_as_anomaly,
    "reject_row": reject_row,
    "valider": validate_values,
    "derive_useful_columns": derive_useful_columns,
    "derive_columns": derive_useful_columns,
}


def apply_action_map(df: pd.DataFrame, actions: List[Dict[str, Any]]) -> pd.DataFrame:
    for action_item in actions:
        action = str(action_item.get("action", "")).lower()
        params = action_item.get("params", action_item)
        handler = action_map.get(action)
        if handler:
            df = handler(df, params)
    return df


def apply_business_rules(df: pd.DataFrame, domain: str) -> pd.DataFrame:
    if df.empty:
        return df

    domain_key = str(domain or "generic").lower()
    result = df.copy()

    if domain_key == "sales":
        result = result.loc[
            :, ~result.columns.astype(str).str.contains(r"^Unnamed", case=False)
        ]

        sales_col = _find_column(
            result, ["Sales", "sales", "value", "amount", "revenue"]
        )
        segment_col = _find_column(
            result, ["Segment", "segment", "category", "customer_segment"]
        )

        if sales_col:
            result[sales_col] = (
                result[sales_col].astype("string").str.replace(",", ".", regex=False)
            )
            result[sales_col] = pd.to_numeric(result[sales_col], errors="coerce")

        corporate_total_col = (
            _find_column(result, ["Corporate Total", "corporate total"])
            or "Corporate Total"
        )
        if segment_col and sales_col:
            result[corporate_total_col] = result.groupby(segment_col)[
                sales_col
            ].transform("sum")


    elif domain_key == "logistics":
        # Normalize status values
        status_col = _find_column(
            result,
            ["status", "shipment_status", "delivery_status", "etat", "order_status"],
        )
        if status_col:
            result[status_col] = (
                result[status_col].astype("string").str.strip().str.title()
            )

        # Convert logistics dates
        for col in result.columns:
            col_key = str(col).strip().lower()
            if any(
                token in col_key
                for token in [
                    "date",
                    "pickup",
                    "delivery",
                    "ship",
                    "arrival",
                    "departure",
                    "created",
                    "updated",
                ]
            ):
                result[col] = pd.to_datetime(result[col], errors="coerce")

        # Convert quantity/weight/cost fields to numeric
        for col in result.columns:
            col_key = str(col).strip().lower()
            if any(
                token in col_key
                for token in [
                    "qty",
                    "quantity",
                    "weight",
                    "volume",
                    "price",
                    "cost",
                    "amount",
                    "distance",
                ]
            ):
                result[col] = (
                    result[col].astype("string").str.replace(",", ".", regex=False)
                )
                result[col] = pd.to_numeric(result[col], errors="coerce")

        # Derive lead time when both order and delivery dates exist
        order_col = _find_column(
            result, ["order_date", "created_date", "shipment_date", "pickup_date"]
        )
        delivery_col = _find_column(
            result, ["delivery_date", "arrival_date", "received_date"]
        )
        if order_col and delivery_col:
            lead_time_col = (
                _find_column(result, ["lead_time_days", "lead_time"])
                or "lead_time_days"
            )
            result[lead_time_col] = (result[delivery_col] - result[order_col]).dt.days
            result.loc[result[lead_time_col] < 0, lead_time_col] = pd.NA

    # After domain rules, derive useful columns and remove useless anomaly flags
    try:
        result = derive_useful_columns(result, {})
        result = _drop_useless_anomaly_columns(result)
    except Exception:
        pass

    return result
