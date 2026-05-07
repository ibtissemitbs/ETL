from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

from .rules_engine import (
    apply_action_map,
    apply_business_rules,
    derive_useful_columns,
    drop_all_anomaly_columns,
)

try:
    from .logistics_domain_cleaner import clean_logistics_business_rules
except Exception:  # pragma: no cover - optional domain cleaner
    clean_logistics_business_rules = None

try:
    from .sales_domain_cleaner import clean_sales_business_rules
except Exception:  # pragma: no cover - optional domain cleaner
    clean_sales_business_rules = None


def _is_identifier_like_column(col_name: str) -> bool:
    lowered = col_name.lower()
    if lowered == "id" or lowered.endswith("_id") or lowered.startswith("id_"):
        return True
    return any(
        token in lowered
        for token in [
            "code",
            "ref",
            "reference",
            "identifier",
            "uuid",
            "passeport",
            "order_id",
            "orderid",
            "order id",
        ]
    )


def _is_money_like_column(col_name: str) -> bool:
    lowered = col_name.lower()
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




def _is_business_numeric_column(col_name: str) -> bool:
    """Columns where missing/invalid values must stay NaN, not 0 or median."""
    lowered = str(col_name).strip().lower()
    return lowered in {
        "price",
        "quantity",
        "weight",
        "shipping_cost",
    } or any(
        token in lowered
        for token in ["price", "cost", "amount", "weight", "quantity", "qty"]
    )


def _is_business_date_column(col_name: str) -> bool:
    lowered = str(col_name).strip().lower()
    return lowered in {"order_date", "delivery_date"} or "date" in lowered


def _apply_domain_specific_cleaner(df: pd.DataFrame, domain: str, applied_steps: List[str]) -> pd.DataFrame:
    """Final safety layer: applies explicit Sales/Logistics business rules after LLM actions."""
    domain_key = str(domain or "generic").strip().lower()

    if domain_key == "logistics" and clean_logistics_business_rules is not None:
        before_rows = len(df)
        df = clean_logistics_business_rules(df)
        applied_steps.append(
            f"Regles metier finales Logistics appliquees ({before_rows} -> {len(df)} lignes)"
        )

    elif domain_key == "sales" and clean_sales_business_rules is not None:
        before_rows = len(df)
        df = clean_sales_business_rules(df)
        applied_steps.append(
            f"Regles metier finales Sales appliquees ({before_rows} -> {len(df)} lignes)"
        )

    return df


def _format_user_facing_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Format business date columns for final user-facing output."""
    for col in ["order_date", "delivery_date"]:
        if col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
            df[col] = parsed.dt.strftime("%Y-%m-%d")
    return df

def _parse_ratio(series: pd.Series, target_type: str) -> float:
    non_null = series.dropna()
    if non_null.empty:
        return 0.0

    if target_type == "datetime":
        numeric_ratio = float(pd.to_numeric(non_null, errors="coerce").notna().mean())
        if numeric_ratio >= 0.5:
            return 0.0
        parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
        return float(parsed.notna().mean())

    if target_type in {"int", "float"}:
        parsed = pd.to_numeric(non_null, errors="coerce")
        return float(parsed.notna().mean())

    return 0.0


def apply_rename_columns(
    df: pd.DataFrame, rules: Dict[str, str], applied_steps: List[str]
) -> pd.DataFrame:
    valid_rules = {old: new for old, new in rules.items() if old in df.columns}
    if valid_rules:
        df = df.rename(columns=valid_rules)
        applied_steps.append(f"Colonnes renommees: {valid_rules}")
    return df


def apply_drop_columns(
    df: pd.DataFrame, columns: List[str], applied_steps: List[str]
) -> pd.DataFrame:
    protected_cols = {
        "order_id", "shipment_id", "customer_name", "product", "price",
        "quantity", "order_date", "country", "origin", "destination",
        "weight", "shipping_cost", "delivery_date", "status",
    }

    existing_cols = []
    ignored_cols = []
    for col in columns:
        if col not in df.columns:
            continue
        if str(col).strip().lower() in protected_cols:
            ignored_cols.append(col)
            continue
        existing_cols.append(col)

    if existing_cols:
        df = df.drop(columns=existing_cols)
        applied_steps.append(f"Colonnes supprimees: {existing_cols}")
    if ignored_cols:
        applied_steps.append(f"Suppression ignoree pour colonnes metier protegees: {ignored_cols}")
    return df


def apply_convert_types(
    df: pd.DataFrame, rules: Dict[str, str], applied_steps: List[str]
) -> pd.DataFrame:
    for col, target_type in rules.items():
        target_type = str(target_type).strip().lower()
        if col not in df.columns:
            continue

        try:
            if target_type == "datetime" and _is_business_numeric_column(col):
                applied_steps.append(
                    f"Conversion type ignoree sur '{col}' -> datetime (colonne numerique metier protegee)"
                )
                continue

            if _is_identifier_like_column(col) and target_type != "string":
                applied_steps.append(
                    f"Conversion type ignoree sur '{col}' -> {target_type} (colonne identifiant protegee)"
                )
                continue

            ratio = _parse_ratio(df[col], target_type)

            if target_type in {"int", "float"} and ratio < 0.6:
                applied_steps.append(
                    f"Conversion type ignoree sur '{col}' -> {target_type} (ratio numerique trop faible: {ratio:.2f})"
                )
                continue

            if target_type == "datetime":
                if _is_money_like_column(col):
                    applied_steps.append(
                        f"Conversion type ignoree sur '{col}' -> datetime (colonne monetaire protegee)"
                    )
                    continue
                if ratio < 0.6 or _is_identifier_like_column(col):
                    applied_steps.append(
                        f"Conversion type ignoree sur '{col}' -> datetime (ratio date trop faible: {ratio:.2f})"
                    )
                    continue

            if target_type == "int":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            elif target_type == "float":
                df[col] = pd.to_numeric(df[col], errors="coerce")
            elif target_type == "datetime":
                df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")
            elif target_type == "string":
                df[col] = df[col].astype("string")

            applied_steps.append(
                f"Conversion type appliquee sur '{col}' -> {target_type}"
            )
        except Exception as e:
            applied_steps.append(f"Echec conversion type sur '{col}': {str(e)}")

    return df


def apply_fill_nulls(
    df: pd.DataFrame, rules: Dict[str, Any], applied_steps: List[str]
) -> pd.DataFrame:
    """
    Fill missing values safely.

    IMPORTANT for Sales/Logistics:
    price, quantity, weight, and shipping_cost are business numerical values.
    Missing/invalid values must stay NaN instead of being replaced by 0 or median,
    because 0 would create false business information.
    """
    protected_numeric_nulls = {
        "price",
        "quantity",
        "weight",
        "shipping_cost",
    }
    protected_date_nulls = {
        "order_date",
        "delivery_date",
    }

    for col, fill_value in rules.items():
        if col not in df.columns:
            continue

        col_key = str(col).strip().lower()

        if col_key in protected_numeric_nulls or _is_business_numeric_column(col):
            applied_steps.append(
                f"Fill null ignore sur '{col}' : valeur numerique metier conservee en NaN"
            )
            continue

        if col_key in protected_date_nulls:
            applied_steps.append(
                f"Fill null ignore sur '{col}' : date metier manquante conservee en NaT"
            )
            continue

        before_nulls = int(df[col].isna().sum())
        try:
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_fill = pd.to_numeric(
                    pd.Series([fill_value]), errors="coerce"
                ).iloc[0]
                if pd.isna(numeric_fill):
                    # Safe fallback for generic numeric columns only.
                    if before_nulls < len(df[col]):
                        median_fill = df[col].dropna().median()
                        df[col] = df[col].fillna(median_fill)
                else:
                    df[col] = df[col].fillna(numeric_fill)

            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                date_fill = pd.to_datetime(fill_value, errors="coerce")
                if pd.isna(date_fill):
                    # For generic dates, keep NaT rather than inventing 2000-01-01.
                    applied_steps.append(
                        f"Fill null ignore sur '{col}' : date invalide proposee, NaT conserve"
                    )
                    continue
                df[col] = df[col].fillna(date_fill)

            else:
                df[col] = df[col].fillna(fill_value)

        except Exception as exc:
            # Last-resort fallback: do not use 0 for numeric columns.
            applied_steps.append(
                f"Fill null echoue sur '{col}', valeurs manquantes conservees: {str(exc)}"
            )
            continue

        after_nulls = int(df[col].isna().sum())
        filled_count = before_nulls - after_nulls
        applied_steps.append(
            f"Nulls remplis dans '{col}': {filled_count} valeurs avec '{fill_value}'"
        )

    return df

def apply_normalization_rules(
    df: pd.DataFrame, rules: Dict[str, Dict[str, str]], applied_steps: List[str]
) -> pd.DataFrame:
    for col, mapping in rules.items():
        if col not in df.columns:
            continue

        if isinstance(mapping, dict):
            df[col] = df[col].replace(mapping)
            applied_steps.append(f"Normalisation par mapping appliquee sur '{col}'")

    return df


def apply_text_case_rules(
    df: pd.DataFrame, rules: Dict[str, str], applied_steps: List[str]
) -> pd.DataFrame:
    for col, case_type in rules.items():
        if col not in df.columns:
            continue

        if col.lower() in {"customer_name", "price"}:
            applied_steps.append(
                f"Transformation casse ignoree sur '{col}' (valeur d'origine preservee)"
            )
            continue

        df[col] = df[col].astype("string")

        if case_type == "lower":
            df[col] = df[col].str.lower()
        elif case_type == "upper":
            df[col] = df[col].str.upper()
        elif case_type == "title":
            df[col] = df[col].str.title()

        applied_steps.append(
            f"Transformation casse appliquee sur '{col}' -> {case_type}"
        )

    return df


def apply_deduplication(
    df: pd.DataFrame, dedup_rules: Dict[str, Any], applied_steps: List[str]
) -> pd.DataFrame:
    if not dedup_rules.get("remove_duplicates", False):
        return df

    subset = dedup_rules.get("subset", None)

    if subset:
        valid_subset = [col for col in subset if col in df.columns]
        before = len(df)
        df = df.drop_duplicates(subset=valid_subset)
        after = len(df)
        applied_steps.append(
            f"Doublons supprimes avec subset={valid_subset}: {before - after}"
        )
    else:
        before = len(df)
        df = df.drop_duplicates()
        after = len(df)
        applied_steps.append(f"Doublons supprimes (global): {before - after}")

    return df


def apply_validation_rules(
    df: pd.DataFrame, rules: Dict[str, Any], applied_steps: List[str]
) -> pd.DataFrame:
    for col, rule in rules.items():
        if col not in df.columns or not isinstance(rule, dict):
            continue

        rule_type = rule.get("type")

        if rule_type == "range":
            min_val = rule.get("min")
            max_val = rule.get("max")
            mask = pd.Series([True] * len(df), index=df.index)

            values = pd.to_numeric(df[col], errors="coerce")
            if min_val is not None:
                mask &= values >= min_val
            if max_val is not None:
                mask &= values <= max_val

            invalid_count = int((~mask & df[col].notna()).sum())
            df.loc[~mask, col] = pd.NA
            applied_steps.append(
                f"Validation range sur '{col}': {invalid_count} valeurs invalides mises a NA"
            )

        elif rule_type == "past_date":
            today = pd.Timestamp(datetime.today().date())
            mask = df[col] <= today
            invalid_count = int((~mask & df[col].notna()).sum())
            df.loc[~mask, col] = pd.NaT
            applied_steps.append(
                f"Validation past_date sur '{col}': {invalid_count} dates futures corrigees"
            )

        elif rule_type == "allowed_values":
            allowed_values = rule.get("values", [])
            invalid_mask = ~df[col].isin(allowed_values) & df[col].notna()
            invalid_count = int(invalid_mask.sum())
            df.loc[invalid_mask, col] = pd.NA
            applied_steps.append(
                f"Validation allowed_values sur '{col}': {invalid_count} valeurs invalides mises a NA"
            )

    return df


def _build_action_plan_from_rules(llm_rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    plan_items = llm_rules.get("plan") or []
    actions: List[Dict[str, Any]] = []

    for item in plan_items:
        if not isinstance(item, dict):
            continue

        action = str(item.get("action", "")).lower().strip()
        column = item.get("column")
        if not action or not column:
            continue

        actions.append(
            {
                "action": action,
                "params": {
                    "column": column,
                    "problem": item.get("problem", ""),
                    "confidence": item.get("confidence", 0.5),
                },
            }
        )

    return actions


def apply_llm_rules(
    df: pd.DataFrame, llm_rules: Dict[str, Any], domain: str = "generic"
) -> tuple[pd.DataFrame, List[str]]:
    """
    Applique un plan de nettoyage validé au DataFrame.

    Order of execution:
    1. Generic/domain rules from rules_engine
    2. LLM plan through deterministic action_map
    3. FINAL Sales/Logistics business rules as a safety layer
    4. Final user-facing cleanup
    """
    applied_steps: List[str] = []

    # First pass: generic domain rules.
    df = apply_business_rules(df, domain)
    applied_steps.append(f"Regles metier generiques appliquees pour domaine '{domain}'")

    # LLM is allowed to propose only a plan. Execution remains deterministic.
    action_plan = _build_action_plan_from_rules(llm_rules)
    if action_plan:
        df = apply_action_map(df, action_plan)
        applied_steps.append(
            f"Plan applique: {len(action_plan)} actions executees par le moteur deterministe"
        )

    # Final pass: explicit Sales/Logistics rules to correct LLM mistakes.
    # This prevents: negative values -> 0/abs, numeric -> datetime, wrong category values, etc.
    df = _apply_domain_specific_cleaner(df, domain, applied_steps)

    # Final deterministic cleanup for user-facing output
    df = derive_useful_columns(df, {})
    df = drop_all_anomaly_columns(df)
    df = _format_user_facing_dates(df)
    applied_steps.append(
        "Nettoyage final: colonnes utiles derivees et colonnes anomaly supprimees"
    )

    if llm_rules.get("dataset_summary"):
        summary = llm_rules.get("dataset_summary", {})
        applied_steps.append(
            f"Plan LLM recu pour type={summary.get('dataset_type', 'unknown')} qualite={summary.get('general_quality', 'unknown')}"
        )

    return df, applied_steps
