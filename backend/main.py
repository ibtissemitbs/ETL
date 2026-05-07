import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_structure_detector import DataStructureDetector, DataTransformer
from src.domain_context import build_domain_context
from src.hybrid_ml import get_hybrid_ml_service
from src.llm_helper import get_transformation_rules
from src.logistics_domain_cleaner import LogisticsDomainCleaner
from src.profiler import build_dataset_profile
from src.rules_engine import derive_useful_columns, drop_all_anomaly_columns
from src.sales_domain_cleaner import SalesDomainCleaner
from src.transform import apply_llm_rules

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Keep cleaning conservative to preserve user dataset structure.
MAX_COL_MISSING_RATIO_TO_DROP = 0.98
MAX_ROW_MISSING_RATIO_TO_DROP = 0.95

PROTECTED_COLUMNS = {
    "country",
    "pays",
    "nationality",
    "nation",
    "shipment_id",
    "order_id",
    "id",
}

app = FastAPI(
    title="ETL Platform",
    description="Plateforme de nettoyage et transformation de données",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Global state
current_df = None
current_filename = None
current_report = None
current_run_id = None
current_input_df = None

# ============================================================================
# UTILITIES
# ============================================================================


def convert_types_to_native(obj):
    """
    Convert NumPy types to native Python types for JSON serialization
    """
    if isinstance(obj, dict):
        return {k: convert_types_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_types_to_native(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif pd.isna(obj):
        return None
    else:
        return obj


def looks_like_identifier_column(col_name: str) -> bool:
    lowered = col_name.lower()
    return any(
        token in lowered
        for token in [
            "id",
            "code",
            "ref",
            "reference",
            "identifier",
            "order",
            "passeport",
        ]
    )


def looks_like_money_column(col_name: str) -> bool:
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


def is_protected_column(col_name: str) -> bool:
    lowered = str(col_name).strip().lower()
    return lowered in PROTECTED_COLUMNS


def format_user_facing_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize business date columns for display and export."""
    formatted = df.copy()
    for col in formatted.columns:
        col_lower = str(col).strip().lower()
        if "date" in col_lower or col_lower.endswith("_at"):
            parsed = pd.to_datetime(formatted[col], errors="coerce", format="mixed")
            formatted[col] = parsed.dt.strftime("%Y-%m-%d")
    return formatted


def prepare_user_facing_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Remove technical helper columns and format dates before returning data."""
    return format_user_facing_dates(drop_all_anomaly_columns(derive_useful_columns(df, {})))


def restore_essential_columns(
    cleaned_df: pd.DataFrame, source_df: pd.DataFrame | None
) -> pd.DataFrame:
    """Restore essential identifier and money columns from the source frame."""
    if source_df is None or cleaned_df is None or cleaned_df.empty:
        return cleaned_df

    restored = cleaned_df.copy()
    for col in source_df.columns:
        if col not in restored.columns and (
            looks_like_identifier_column(col)
            or looks_like_money_column(col)
            or is_protected_column(col)
        ):
            restored[col] = source_df[col]

    ordered_cols = [col for col in source_df.columns if col in restored.columns]
    ordered_cols.extend(col for col in restored.columns if col not in source_df.columns)
    return restored[ordered_cols]


def harmonize_customer_names_by_id(cleaned_df: pd.DataFrame, source_df: pd.DataFrame) -> pd.DataFrame:
    """For each identifier value (order_id, id, client_id, etc.),
    pick the most frequent non-empty customer_name from the original source
    and apply it to the cleaned frame so the same id has a consistent name.
    This only runs when both frames contain a customer_name-like column and
    an identifier-like column.
    """
    if source_df is None or cleaned_df is None:
        return cleaned_df

    # Find identifier column in source
    id_col = None
    for cand in ["order_id", "client_id", "customer_id", "id"]:
        if cand in source_df.columns:
            id_col = cand
            break

    if id_col is None:
        # try heuristic
        for col in source_df.columns:
            if looks_like_identifier_column(col):
                id_col = col
                break

    if id_col is None or "customer_name" not in source_df.columns:
        return cleaned_df

    # Build mapping id -> mode(customer_name) from source (ignore blanks)
    src = source_df[[id_col, "customer_name"]].copy()
    src["customer_name"] = src["customer_name"].astype("string").str.strip()
    src = src[src["customer_name"].notna() & (src["customer_name"] != "")]
    if src.empty:
        return cleaned_df

    name_mode = (
        src.groupby(id_col)["customer_name"]
        .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else None)
        .dropna()
    )

    if name_mode.empty:
        return cleaned_df

    # Apply mapping to cleaned_df where id matches
    if id_col in cleaned_df.columns:
        for idx, name in name_mode.items():
            mask = cleaned_df[id_col] == idx
            if mask.any():
                cleaned_df.loc[mask, "customer_name"] = name

    return cleaned_df


def validate_dates(col_name, string_values):
    """
    Detect date-specific problems in STRING values BEFORE conversion:
    - Impossible dates (month=00, day=00, etc.)
    - Future dates (>2026)
    - Dates too old (born before 1900)
    - Invalid format/text
    """
    issues = {"impossible": 0, "future": 0, "too_old": 0, "invalid_text": 0}

    for val in string_values:
        if pd.isna(val):
            continue

        val_str = str(val).strip().lower()

        # Text-based checks (before any parsing)
        if any(
            txt in val_str
            for txt in ["invalid", "error", "date inconnue", "tbd", "todo", "?"]
        ):
            issues["invalid_text"] += 1

        # Check for impossible dates in YYYY-MM-DD format like "2000-00-00"
        if "-" in val_str:
            parts = val_str.split("-")
            if len(parts) >= 3:
                try:
                    month = int(parts[1])
                    day = int(parts[2].split()[0])  # Handle times too
                    if month == 0 or day == 0:
                        issues["impossible"] += 1
                        continue
                    if month > 12:
                        issues["impossible"] += 1
                        continue
                    if day > 31:
                        issues["impossible"] += 1
                        continue
                except:
                    pass

        # Year-based checks
        if any(
            y in val_str
            for y in ["202" + str(i) for i in range(7, 10)] + ["2027", "2028"]
        ):
            issues["future"] += 1
        elif any(y in val_str for y in ["1899", "1898", "1897", "1896", "1895"]):
            issues["too_old"] += 1

    return issues


def normalize_missing_values(df):
    """
    Normalize ALL missing-value tokens (including null, N/A, "genre", "sexe", variations).
    Aggressively detects and standardizes missing values to pd.NA.
    Also detects DATE QUALITY ISSUES specifically.
    """
    normalized = df.copy()
    issue_counts = {
        "blank_strings": 0,
        "invalid_numeric": 0,
        "invalid_dates": 0,
        "suspicious_type_columns": 0,
        "impossible_dates": 0,
        "future_dates": 0,
        "very_old_dates": 0,
    }

    # EXTENDED list of missing value tokens (many more variations)
    missing_tokens = {
        "",
        "na",
        "n/a",
        "null",
        "none",
        "nan",
        "-",
        "--",
        "?",
        "unknown",
        "undefined",
        "n.a.",
        "n.a",
        "not available",
        "n/d",
        "n/d.",
        "nd",
        "void",
        "empty",
        "missing",
        "blank",
        "no value",
        "nodata",
        "no_data",
        "invalide",
        "invalid",
        "erreur",
        "error",
        "tbd",
        "todo",
        "xxx",
        "0000",
        "00000",
        "00000-00",
        "none.",
        "null.",
        "na.",
        "genre",
        "sexe",
    }

    for col in normalized.columns:
        col_lower = col.lower()
        original_null_count = int(normalized[col].isna().sum())

        # Check if column is object/string type OR numeric that might have nullish text
        if normalized[col].dtype == "object" or normalized[col].dtype == "string":
            original_values = normalized[col].copy()
            stripped = original_values.astype(str).str.strip().str.lower()

            # Detect missing: actual NaN, empty strings, or tokens in missing_tokens set
            blank_mask = (
                original_values.isna() | stripped.eq("") | stripped.isin(missing_tokens)
            )

            # Also catch strings that are purely non-alphanumeric (like "---", "___", "***")
            non_alnum_mask = stripped.str.replace(r"[^a-z0-9]", "", regex=True).eq("")
            blank_mask = blank_mask | (
                non_alnum_mask
                & ~original_values.astype(str).str.contains(
                    r"[a-zA-Z0-9]", regex=True, na=False
                )
            )

            new_nulls = int(blank_mask.sum()) - original_null_count
            issue_counts["blank_strings"] += new_nulls
            normalized.loc[blank_mask, col] = pd.NA

            logger.info(
                f"Column '{col}': detected {int(blank_mask.sum())} total missing values (+{new_nulls} new)"
            )

            non_null_values = normalized[col].dropna()
            if len(non_null_values) == 0:
                continue

            # Type detection hints
            numeric_hints = [
                "id",
                "age",
                "amount",
                "salary",
                "price",
                "count",
                "qty",
                "quantity",
                "score",
                "rate",
                "percent",
                "total",
                "number",
                "montant",
                "prix",
            ]
            date_hints = [
                "date",
                "time",
                "jour",
                "month",
                "year",
                "created",
                "updated",
                "birth",
                "naissance",
                "datedenaissance",
                "date_naissance",
            ]
            categorical_hints = [
                "genre",
                "sexe",
                "status",
                "category",
                "region",
                "country",
                "pays",
            ]

            should_check_numeric = any(
                hint in col_lower for hint in numeric_hints
            ) and not looks_like_identifier_column(col)
            should_check_date = any(
                hint in col_lower for hint in date_hints
            ) and not looks_like_money_column(col)
            should_check_categorical = any(
                hint in col_lower for hint in categorical_hints
            )

            # Skip conversion attempts for identifier columns entirely - they must stay as-is
            if looks_like_identifier_column(col):
                logger.info(
                    f"Column '{col}': Skipping all type conversions (identifier column)"
                )
                continue

            numeric_attempt = pd.to_numeric(non_null_values, errors="coerce")
            numeric_ratio = (
                float(numeric_attempt.notna().mean()) if len(numeric_attempt) > 0 else 0
            )
            date_attempt = pd.to_datetime(non_null_values, errors="coerce")
            date_ratio = (
                float(date_attempt.notna().mean()) if len(date_attempt) > 0 else 0
            )

            # Apply appropriate conversions based on column semantics
            if numeric_ratio >= 0.75 or (
                should_check_numeric and not should_check_categorical
            ):
                converted = pd.to_numeric(normalized[col], errors="coerce")
                invalid_mask = normalized[col].notna() & converted.isna()
                issue_counts["invalid_numeric"] += int(invalid_mask.sum())
                normalized[col] = converted
                if should_check_numeric and int(invalid_mask.sum()) > 0:
                    issue_counts["suspicious_type_columns"] += 1
                    logger.warning(
                        f"Column '{col}': {int(invalid_mask.sum())} invalid numeric values"
                    )
            elif (
                date_ratio >= 0.5 or should_check_date
            ) and not looks_like_money_column(
                col
            ):  # Lower threshold for dates
                # CRITICAL FIX: Prevent numeric columns from being converted to datetime
                # pd.to_datetime() treats numeric values as Unix timestamps, corrupting sales data
                # (e.g., 91.056 becomes 1970-01-01 00:00:00.000000091)
                # ALSO: Never convert identifier columns to datetime (shipment_id, order_id, etc.)
                if numeric_ratio >= 0.5 and not should_check_date:
                    logger.info(
                        f"Column '{col}': Skipping datetime conversion (numeric column with {numeric_ratio:.2f} ratio)"
                    )
                    continue
                if looks_like_identifier_column(col):
                    logger.info(
                        f"Column '{col}': Skipping datetime conversion (identifier column)"
                    )
                    continue

                # FIRST: detect specific date problems BEFORE conversion (on original string values)
                if should_check_date:  # For columns like date_naissance
                    # Get original string values for validation
                    orig_vals = normalized[col][normalized[col].notna()].copy()
                    date_issues = validate_dates(col, orig_vals)
                    issue_counts["impossible_dates"] += date_issues["impossible"]
                    issue_counts["future_dates"] += date_issues["future"]
                    issue_counts["very_old_dates"] += date_issues["too_old"]

                    if date_issues["impossible"] > 0:
                        logger.warning(
                            f"Column '{col}': {date_issues['impossible']} impossible dates detected (e.g., 2000-00-00, invalid months)"
                        )
                    if date_issues["future"] > 0:
                        logger.warning(
                            f"Column '{col}': {date_issues['future']} future dates detected"
                        )
                    if date_issues["too_old"] > 0:
                        logger.warning(
                            f"Column '{col}': {date_issues['too_old']} suspiciously old dates detected (<1895)"
                        )
                    if date_issues["invalid_text"] > 0:
                        logger.warning(
                            f"Column '{col}': {date_issues['invalid_text']} non-date text values detected"
                        )

                # THEN: convert and detect format errors
                converted = pd.to_datetime(normalized[col], errors="coerce")
                invalid_mask = normalized[col].notna() & converted.isna()
                issue_counts["invalid_dates"] += int(invalid_mask.sum())
                normalized[col] = converted
                if should_check_date and int(invalid_mask.sum()) > 0:
                    issue_counts["suspicious_type_columns"] += 1
                    logger.warning(
                        f"Column '{col}': {int(invalid_mask.sum())} unparseable date values (invalid format)"
                    )

    return normalized, issue_counts


def compute_quality_score(
    rows, cols, null_cells, empty_rows, empty_cols, duplicates, type_issues=0
):
    """Compute a transparent 0-100 data quality score."""
    total_cells = max(rows * cols, 1)
    row_count = max(rows, 1)
    col_count = max(cols, 1)

    null_penalty = min(45.0, (null_cells / total_cells) * 100.0 * 1.5)
    empty_row_penalty = min(20.0, (empty_rows / row_count) * 100.0 * 0.6)
    empty_col_penalty = min(20.0, (empty_cols / col_count) * 100.0 * 1.0)
    duplicate_penalty = min(10.0, (duplicates / row_count) * 100.0 * 0.4)
    type_penalty = min(25.0, (type_issues / total_cells) * 100.0 * 1.5)

    score = 100.0 - (
        null_penalty
        + empty_row_penalty
        + empty_col_penalty
        + duplicate_penalty
        + type_penalty
    )
    return round(max(0.0, min(100.0, score)), 1)


def enforce_sales_business_rules(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Apply hard sales-domain constraints before statistical cleanup.

    This keeps platform corrections deterministic for fields that have known
    business bounds, instead of letting generic outlier logic rewrite them.
    """
    df = df.copy()
    modifications: list[str] = []

    age_columns = [
        col
        for col in df.columns
        if col.lower() == "age"
        or col.lower().endswith("_age")
        or col.lower().startswith("age_")
    ]
    for col in age_columns:
        values = pd.to_numeric(df[col], errors="coerce")
        valid_mask = values.notna()
        if not valid_mask.any():
            continue

        below_mask = valid_mask & (values < 10)
        above_mask = valid_mask & (values > 100)
        if below_mask.any() or above_mask.any():
            df[col] = values.clip(lower=10, upper=100)
            modifications.append(
                f"✓ '{col}': {int(below_mask.sum())} valeurs < 10 relevées à 10 et {int(above_mask.sum())} valeurs > 100 ramenées à 100"
            )
        else:
            df[col] = values

    quantity_columns = [
        col
        for col in df.columns
        if col.lower() == "quantity"
        or col.lower().endswith("_quantity")
        or "qty" in col.lower()
    ]
    for col in quantity_columns:
        values = pd.to_numeric(df[col], errors="coerce")
        valid_mask = values.notna()
        if not valid_mask.any():
            continue

        negative_mask = valid_mask & (values < 0)
        if negative_mask.any():
            df[col] = values.clip(lower=0)
            modifications.append(
                f"✓ '{col}': {int(negative_mask.sum())} quantités négatives corrigées à 0"
            )
        else:
            df[col] = values

    unit_price_columns = [
        col
        for col in df.columns
        if col.lower() in {"unit_price", "price", "unitprice"}
        or col.lower().endswith("_price")
    ]
    for col in unit_price_columns:
        values = pd.to_numeric(df[col], errors="coerce")
        valid_mask = values.notna()
        if not valid_mask.any():
            continue

        negative_mask = valid_mask & (values < 0)
        if negative_mask.any():
            df[col] = values.clip(lower=0)
            modifications.append(
                f"✓ '{col}': {int(negative_mask.sum())} prix négatifs corrigés à 0"
            )
        else:
            df[col] = values

    discount_columns = [
        col
        for col in df.columns
        if col.lower() in {"discount_percent", "discount", "discount_rate"}
        or "discount" in col.lower()
        or "percent" in col.lower()
        or "rate" in col.lower()
    ]
    for col in discount_columns:
        values = pd.to_numeric(df[col], errors="coerce")
        valid_mask = values.notna()
        if not valid_mask.any():
            continue

        below_mask = valid_mask & (values < 0)
        above_mask = valid_mask & (values > 100)
        if below_mask.any() or above_mask.any():
            df[col] = values.clip(lower=0, upper=100)
            modifications.append(
                f"✓ '{col}': {int(below_mask.sum())} valeurs < 0 relevées à 0 et {int(above_mask.sum())} valeurs > 100 ramenées à 100"
            )
        else:
            df[col] = values

    return df, modifications


def apply_domain_cleaner(
    domain: str, df: pd.DataFrame
) -> tuple[pd.DataFrame, dict, str | None]:
    domain = str(domain or "generic").lower()

    if domain == "sales":
        cleaned, ops = SalesDomainCleaner.clean_sales_data(df)
        return cleaned, ops, "sales"
    if domain == "logistics":
        cleaned, ops = LogisticsDomainCleaner.clean_logistics_data(df)
        return cleaned, ops, "logistics"

    return df, {}, None


def record_feedback(
    domain: str,
    profile: dict,
    llm_rules: dict,
    ml_prediction: Any,
    run_id: str | None = None,
) -> None:
    plan = llm_rules.get("plan") or []
    if not plan:
        return

    feedback_dir = Path("reports") / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    out_path = feedback_dir / f"feedback_{datetime.now().strftime('%Y%m%d')}.jsonl"

    columns_by_name = {
        col.get("name"): col
        for col in profile.get("columns", [])
        if isinstance(col, dict)
    }

    with open(out_path, "a", encoding="utf-8") as f:
        for item in plan:
            if not isinstance(item, dict):
                continue
            column = item.get("column")
            column_profile = columns_by_name.get(column, {}) if column else {}
            role = None
            action = None
            if ml_prediction and column in getattr(
                ml_prediction, "role_predictions", {}
            ):
                role = ml_prediction.role_predictions[column].get("label")
            if ml_prediction and column in getattr(
                ml_prediction, "action_predictions", {}
            ):
                action = ml_prediction.action_predictions[column].get("label")

            entry = {
                "run_id": run_id,
                "domain": domain,
                "column": column,
                "column_profile": {
                    "dtype": column_profile.get("dtype"),
                    "missing_pct": column_profile.get("missing_pct"),
                    "unique_pct": column_profile.get("unique_pct"),
                    "inferred_type": column_profile.get("inferred_type"),
                },
                "role": role,
                "action": action or item.get("action"),
                "problem": item.get("problem"),
                "confidence": item.get("confidence"),
                "success": True,
                "source": "llm_plan",
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ============================================================================
# FRONTEND ROUTE
# ============================================================================


def render_frontend_file(filename: str):
    """Render a static HTML file from the frontend directory."""
    try:
        html_path = FRONTEND_DIR / filename
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Frontend error for {filename}: {e}")
        return "<h1>Frontend not found</h1>"


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the HTML interface"""
    return render_frontend_file("index.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the dashboard interface"""
    return render_frontend_file("dashboard.html")


@app.get("/etl", response_class=HTMLResponse)
async def serve_etl():
    """Serve the isolated ETL workspace interface"""
    return render_frontend_file("etl.html")


# ============================================================================
# UPLOAD AND PROCESS ROUTE
# ============================================================================


@app.post("/upload-and-process")
async def upload_and_process(
    file: UploadFile = File(...), domain_override: str | None = None
):
    """
    Upload a file and perform automated data cleaning.
    Supports: CSV, Excel, JSON
    """
    global current_df, current_filename, current_report, current_run_id, current_input_df

    try:
        logger.info(f"📥 Uploading file: {file.filename}")

        # Reset previous state to prevent stale exports if this upload fails.
        current_df = None
        current_filename = None
        current_report = None
        current_run_id = None
        current_input_df = None

        # Validate file
        if not file.filename:
            raise ValueError("No filename provided")

        # Get file extension
        ext = Path(file.filename).suffix.lower()

        if ext not in [".csv", ".xlsx", ".xls", ".json"]:
            raise ValueError(f"Unsupported format: {ext}. Use CSV, Excel, or JSON")

        # Save file temporarily
        file_path = UPLOAD_DIR / file.filename
        file_content = await file.read()

        with open(file_path, "wb") as f:
            f.write(file_content)

        logger.info(f"✓ File saved to {file_path}")

        # Read file based on extension with fallbacks for problematic .xls files
        try:
            if ext == ".csv":
                df = pd.read_csv(file_path)
            elif ext in [".xlsx", ".xls"]:
                df = pd.read_excel(file_path)
            elif ext == ".json":
                df = pd.read_json(file_path)
            else:
                raise ValueError("Invalid file format")
        except Exception as read_error:
            logger.error(f"File read error: {read_error}")
            # Fallback: some legacy/broken .xls workbooks cannot be parsed by pandas
            # Try to load with xlrd directly and convert the first sheet to a DataFrame
            if ext == ".xls":
                try:
                    import xlrd

                    logger.info("Attempting xlrd fallback for .xls (ignore_workbook_corruption=True)")
                    book = xlrd.open_workbook(str(file_path), ignore_workbook_corruption=True)
                    sheet = book.sheet_by_index(0)
                    # read rows
                    data = [sheet.row_values(i) for i in range(sheet.nrows)]
                    if len(data) == 0:
                        df = pd.DataFrame()
                    else:
                        header = data[0]
                        rows = data[1:]
                        df = pd.DataFrame(rows, columns=header)
                    logger.info("✓ Read .xls via xlrd fallback")
                except Exception as xlrd_err:
                    logger.error(f"xlrd fallback failed: {xlrd_err}")
                    raise ValueError(f"Could not read file: {str(read_error)}")
            else:
                raise ValueError(f"Could not read file: {str(read_error)}")

        logger.info(f"✓ Data loaded: {len(df)} rows, {len(df.columns)} columns")

        # KEEP ORIGINAL VALUES for validation and profiling
        df_original = df.copy()
        # Preserve original numeric values mapped by identifier to avoid domain-cleaner overwrites
        orig_numeric_map = {}
        if "shipment_id" in df_original.columns:
            try:
                tmp = df_original[["shipment_id"]].copy()
                if "weight" in df_original.columns:
                    tmp["_orig_weight"] = df_original["weight"]
                if "shipping_cost" in df_original.columns:
                    tmp["_orig_shipping_cost"] = df_original["shipping_cost"]
                tmp = tmp.set_index("shipment_id")
                orig_numeric_map = tmp.to_dict(orient="index")
            except Exception:
                orig_numeric_map = {}

        # ===== DETECT DOMAIN BEFORE TRANSFORMATION (important for sales with pivots) =====
        # This helps identify the domain on the raw structure
        dataset_profile_raw = build_dataset_profile(df_original)
        domain_context_raw = build_domain_context(
            dataset_profile_raw, dataframe=df_original, domain_override=domain_override
        )
        domain_detected_early = domain_context_raw.get("domain", "generic")

        logger.info(
            f"🔍 Early domain detection: {domain_detected_early} (confidence: {domain_context_raw.get('confidence')})"
        )

        # ===== AUTO-DETECT AND TRANSFORM DATA STRUCTURE =====
        structure_type = DataStructureDetector.detect_structure(df_original)
        structure_desc = DataStructureDetector.describe_structure(df_original)
        logger.info(f"🔍 Structure detected: {structure_type}")
        logger.info(f"📊 Structure details: {structure_desc}")

        df_structured = df_original.copy()
        if structure_type == "pivoted":
            logger.info(f"🔄 Transforming pivoted structure to transactional...")
            df_transformed = DataTransformer.transform(df_original, structure_type)
            logger.info(
                f"✓ Transformation complete: {len(df_transformed)} rows, {len(df_transformed.columns)} columns"
            )
            df_structured = df_transformed

        # Build a compact profile for the hybrid ML layer on the structured data
        dataset_profile = build_dataset_profile(df_structured)
        domain_context = build_domain_context(
            dataset_profile, dataframe=df_structured, domain_override=domain_override
        )

        # Use early domain detection if it was better (e.g., for pivoted sales data)
        if (
            domain_detected_early != "generic"
            and domain_context.get("domain", "generic") == "generic"
        ):
            logger.info(f"Using early domain detection: {domain_detected_early}")
            domain_context = domain_context_raw

        domain_detected = domain_context.get("domain", "generic")

        hybrid_service = get_hybrid_ml_service(domain=domain_detected)
        ml_prediction = hybrid_service.predict(dataset_profile, df_structured)
        ml_context = hybrid_service.build_llm_context(dataset_profile, df_structured)

        # ===== APPLY DOMAIN-SPECIFIC CLEANING RULES =====
        domain_ops = {}
        domain_cleaner_used = None
        df_domain_clean, domain_ops, domain_cleaner_used = apply_domain_cleaner(
            domain_detected, df_structured
        )
        if domain_cleaner_used:
            logger.info(f"🏷️ Domain cleaner applied: {domain_cleaner_used}")
            logger.info(f"✓ Domain cleaning ops: {domain_ops}")
            df_structured = df_domain_clean
            dataset_profile = build_dataset_profile(df_structured)

        # LLM/domain rules are now part of the actual pipeline, not just metadata
        llm_rules = get_transformation_rules(dataset_profile, dataframe=df_structured)

        # Normalize missing tokens and coerce obvious numeric/date columns before applying rules
        df_prepared, type_issues = normalize_missing_values(df_structured)
        current_input_df = df_prepared.copy()
        df_clean, llm_applied_steps = apply_llm_rules(
            df_prepared.copy(), llm_rules, domain=domain_detected
        )

        # Save original stats
        original_size = len(df_prepared)
        original_cols = len(df_prepared.columns)
        original_nulls = int(df_prepared.isnull().sum().sum())
        original_duplicates = int(len(df_prepared) - len(df_prepared.drop_duplicates()))
        original_empty_cols = int(
            (df_prepared.isnull().sum() == len(df_prepared)).sum()
        )
        original_empty_rows = int(df_prepared.isnull().all(axis=1).sum())

        quality_before = compute_quality_score(
            original_size,
            original_cols,
            original_nulls,
            original_empty_rows,
            original_empty_cols,
            original_duplicates,
            type_issues.get("invalid_numeric", 0)
            + type_issues.get("invalid_dates", 0)
            + type_issues.get("suspicious_type_columns", 0),
        )

        # Pivoted business sheets are structurally dirty even if they do not contain nulls.
        # Penalize the raw score so the report reflects the real ETL effort required.
        if structure_type == "pivoted":
            quality_before = max(0.0, quality_before - 15.0)

        quality_issues_before = {
            "rows": int(original_size),
            "columns": int(original_cols),
            "null_cells": int(original_nulls),
            "null_rate": f"{(original_nulls / max(original_size * original_cols, 1) * 100):.1f}%",
            "empty_columns": int(original_empty_cols),
            "empty_rows": int(original_empty_rows),
            "duplicates": int(original_duplicates),
            "duplicate_rate": f"{(original_duplicates / max(original_size, 1) * 100):.1f}%",
            "invalid_numeric": int(type_issues.get("invalid_numeric", 0)),
            "invalid_dates": int(type_issues.get("invalid_dates", 0)),
            "suspicious_type_columns": int(
                type_issues.get("suspicious_type_columns", 0)
            ),
        }

        # ============================================================================
        # DATA CLEANING OPERATIONS (AGGRESSIVE)
        # ============================================================================

        modifications = [f"🤖 {step}" for step in llm_applied_steps]
        if domain_cleaner_used:
            modifications.insert(
                0, f"🏷️ Domain cleaner '{domain_cleaner_used}' applied: {domain_ops}"
            )

        # **EARLY DETECTION**: Report date validation problems BEFORE aggressive cleanup
        logger.info(
            f"Checking {len(df_clean.columns)} columns for date validation issues..."
        )
        logger.info(f"Column list: {list(df_clean.columns)}")

        for col in df_clean.columns:
            col_lower = col.lower()
            logger.info(f"  Checking column: '{col}' (lower: '{col_lower}')")

            if "naissance" in col_lower and "date" in col_lower:
                logger.info(f"    ✓ Found date_naissance column: '{col}'")
                try:
                    if col not in df_original.columns:
                        logger.warning(f"    Column '{col}' not in df_original")
                        continue

                    orig_values = (
                        df_original[col][df_original[col].notna()].astype(str).values
                    )
                    logger.info(f"    Validating {len(orig_values)} non-null values...")
                    date_issues = validate_dates(col, orig_values)
                    logger.info(f"    Issues found: {date_issues}")

                    if date_issues["impossible"] > 0:
                        msg = f"⚠️  '{col}': {date_issues['impossible']} dates impossibles détectées (ex: mois=00, jour=00)"
                        logger.info(f"    Adding: {msg}")
                        modifications.append(msg)
                    if date_issues["future"] > 0:
                        msg = f"⚠️  '{col}': {date_issues['future']} dates futures détectées (>2026)"
                        logger.info(f"    Adding: {msg}")
                        modifications.append(msg)
                    if date_issues["too_old"] > 0:
                        msg = f"⚠️  '{col}': {date_issues['too_old']} dates très anciennes détectées (<1895)"
                        logger.info(f"    Adding: {msg}")
                        modifications.append(msg)
                    if date_issues["invalid_text"] > 0:
                        msg = f"⚠️  '{col}': {date_issues['invalid_text']} valeurs texte invalides (TBD, invalid, etc.)"
                        logger.info(f"    Adding: {msg}")
                        modifications.append(msg)
                except Exception as e:
                    logger.exception(f"    Error validating '{col}': {e}")

        # 1. Mark (don't delete) completely empty rows as anomalies
        initial_rows = len(df_clean)
        mask_all_na = df_clean.isna().all(axis=1)
        dropped = int(mask_all_na.sum())
        df_removed = df_clean[mask_all_na].copy()
        if dropped > 0:
            # add anomaly flag column and mark the rows that would have been dropped
            if "__anomaly" not in df_clean.columns:
                df_clean["__anomaly"] = False
            df_clean.loc[mask_all_na, "__anomaly"] = True
            modifications.append(f"⚠️ {dropped} lignes complètement vides marquées comme anomalies (conservées dans l'APRES)")

        # 2. Drop columns with very high missing values (conservative mode)
        initial_cols = len(df_clean.columns)
        cols_to_drop = []
        for col in df_clean.columns:
            null_rate = df_clean[col].isnull().sum() / max(len(df_clean), 1)
            if null_rate > MAX_COL_MISSING_RATIO_TO_DROP and not is_protected_column(col):
                cols_to_drop.append(col)

        if cols_to_drop:
            df_clean = df_clean.drop(columns=cols_to_drop)
            modifications.append(
                f"❌ {len(cols_to_drop)} colonnes avec >{int(MAX_COL_MISSING_RATIO_TO_DROP*100)}% valeurs manquantes supprimées: {', '.join(cols_to_drop[:3])}"
            )

        # 3. Drop completely empty columns (except protected columns)
        empty_non_protected_cols = [
            col
            for col in df_clean.columns
            if df_clean[col].isna().all() and not is_protected_column(col)
        ]
        if empty_non_protected_cols:
            df_clean = df_clean.drop(columns=empty_non_protected_cols)

        if len(df_clean.columns) < initial_cols:
            dropped_cols = initial_cols - len(df_clean.columns)
            modifications.append(
                f"❌ {dropped_cols} colonnes complètement vides supprimées"
            )

        # 4. Remove duplicate rows
        # NOTE: de-duplication is deferred to after we restore essential identifier
        # and money columns from the original frame to avoid collapsing distinct
        # records that were made identical by intermediate normalization.
        modifications.append(
            "ℹ️ Déduplication différée: will remove exact duplicates after restoring identifiers"
        )

        # 5. Remove rows with extreme missing values only (conservative mode)
        initial_rows = len(df_clean)
        row_missing_ratio = df_clean.isnull().sum(axis=1) / max(
            len(df_clean.columns), 1
        )
        df_clean = df_clean[row_missing_ratio < MAX_ROW_MISSING_RATIO_TO_DROP]
        if len(df_clean) < initial_rows:
            dropped = initial_rows - len(df_clean)
            modifications.append(
                f"❌ {dropped} lignes avec >{int(MAX_ROW_MISSING_RATIO_TO_DROP*100)}% valeurs manquantes supprimées"
            )

        # 5.5 Specialized numeric cleanup for shipping_cost and weight
        logger.info("Step 5.5: Normalizing 'shipping_cost' and 'weight' columns in place")
        for sensitive in ("weight", "shipping_cost"):
            if sensitive in df_clean.columns:
                try:
                    def _normalize_value(value):
                        # Empty or whitespace-only strings -> NaN
                        if pd.isna(value):
                            return pd.NA
                        if isinstance(value, str) and not value.strip():
                            return pd.NA
                        # Convert to numeric; non-numeric values -> NaN
                        numeric_value = pd.to_numeric(value, errors="coerce")
                        if pd.notna(numeric_value):
                            return abs(numeric_value)
                        # Non-numeric, non-empty values -> NaN
                        return pd.NA

                    df_clean[sensitive] = df_clean[sensitive].map(_normalize_value)
                except Exception as e:
                    logger.exception(f"Error normalizing sensitive column '{sensitive}': {e}")

        # 6. SMART filling strategy by column type
        for col in df_clean.columns:
            col_lower = col.lower()
            nulls_in_col = int(df_clean[col].isnull().sum())

            if nulls_in_col == 0:
                continue

            # CATEGORICAL columns (genre, sexe, status, etc.)
            # BUT NEVER FILL ID columns (shipment_id, order_id, id, etc.)
            is_id_column = any(hint in col_lower for hint in ["_id", "shipment_id", "order_id", "client_id"])
            
            if (not is_id_column) and (
                any(
                    hint in col_lower
                    for hint in [
                        "genre",
                        "sexe",
                        "status",
                        "category",
                        "type",
                        "country",
                        "pays",
                        "nationality",
                    ]
                ) or is_protected_column(col)
            ):
                # Use mode (most frequent value)
                mode_val = df_clean[col].mode()
                if len(mode_val) > 0:
                    fill_value = mode_val[0]
                else:
                    fill_value = "Autre"
                df_clean[col] = df_clean[col].fillna(fill_value)
                modifications.append(
                    f"✓ '{col}' (catégorie): {nulls_in_col} valeurs manquantes remplies (mode={fill_value})"
                )

            # DATE columns (date_naissance, datedenaissance, ordre_date, etc.)
            elif any(hint in col_lower for hint in ["date", "naissance"]):
                try:
                    # Convert to datetime if not already
                    if df_clean[col].dtype != "datetime64[ns]":
                        df_clean[col] = pd.to_datetime(df_clean[col], errors="coerce")

                    # Use median date for filling
                    median_date = df_clean[col].median()
                    if pd.notna(median_date):
                        df_clean[col] = df_clean[col].fillna(median_date)
                        modifications.append(
                            f"✓ '{col}' (date): {nulls_in_col} valeurs manquantes remplies (médiane={median_date.date()})"
                        )
                    else:
                        # Fallback: use today's date
                        df_clean[col] = df_clean[col].fillna(pd.Timestamp.now())
                        modifications.append(
                            f"✓ '{col}' (date): {nulls_in_col} valeurs manquantes remplies (aujourd'hui)"
                        )
                except Exception as e:
                    logger.error(f"Error processing date column '{col}': {e}")
                    df_clean[col] = df_clean[col].fillna("2000-01-01")
                    modifications.append(
                        f"✓ '{col}' (date): {nulls_in_col} valeurs manquantes remplies (défaut)"
                    )

            # NUMERIC columns
            elif pd.api.types.is_numeric_dtype(df_clean[col]):
                # For sensitive numeric columns like shipping_cost and weight,
                # we prefer to keep NaN for missing/non-numeric values rather than
                # filling with median or zero. Only apply median fill to other numeric cols.
                if any(x in col_lower for x in ["shipping_cost", "shipping", "weight", "poids"]):
                    # Do not fill missing values for these columns; leave as NaN
                    modifications.append(
                        f"i '{col}' (numeric): {nulls_in_col} valeurs manquantes laissées en NaN (colonnes sensibles)"
                    )
                else:
                    median_val = df_clean[col].median()
                    if pd.notna(median_val):
                        df_clean[col] = df_clean[col].fillna(median_val)
                        modifications.append(
                            f"✓ '{col}' (numeric): {nulls_in_col} valeurs manquantes remplies (médiane={median_val:.2f})"
                        )
                    else:
                        df_clean[col] = df_clean[col].fillna(0)
                        modifications.append(
                            f"✓ '{col}' (numeric): {nulls_in_col} valeurs manquantes remplies (zéro)"
                        )

            # TEXT columns
            # BUT NEVER FILL ID columns (shipment_id, order_id, id, etc.) - they must keep their original values
            is_id_column = any(hint in col_lower for hint in ["_id", "shipment_id", "order_id", "client_id"])
            
            if not is_id_column:
                # Try to find common patterns first
                non_null_vals = df_clean[col].dropna().astype(str)
                if len(non_null_vals) > 0:
                    # Use mode if available
                    mode_val = df_clean[col].mode()
                    if len(mode_val) > 0:
                        fill_value = mode_val[0]
                    else:
                        fill_value = "Non spécifié"
                else:
                    fill_value = "Non spécifié"

                df_clean[col] = df_clean[col].fillna(fill_value)
                modifications.append(
                    f"✓ '{col}' (texte): {nulls_in_col} valeurs manquantes remplies"
                )
            else:
                # Skip filling for ID columns - leave NaN as is
                modifications.append(
                    f"i '{col}' (ID column): {nulls_in_col} valeurs manquantes conservées (colonne d'identifiant)"
                )

            if pd.api.types.is_object_dtype(
                df_clean[col]
            ) or pd.api.types.is_string_dtype(df_clean[col]):
                df_clean[col] = df_clean[col].astype(str).str.strip()

        # 7. Fill missing datetime values with median date when possible
        for col in df_clean.columns:
            if pd.api.types.is_datetime64_any_dtype(df_clean[col]):
                nulls_in_col = int(df_clean[col].isnull().sum())
                if nulls_in_col > 0:
                    valid_dates = df_clean[col].dropna()
                    if not valid_dates.empty:
                        median_date = valid_dates.sort_values().iloc[
                            len(valid_dates) // 2
                        ]
                        df_clean[col] = df_clean[col].fillna(median_date)
                        modifications.append(
                            f"✓ '{col}': {nulls_in_col} valeurs de date remplies"
                        )

        # 8. TEXT NORMALIZATION (strip spaces, fix case, remove special chars)
        logger.info("Step 8: TEXT NORMALIZATION")
        for col in df_clean.columns:
            if df_clean[col].dtype == "object" or pd.api.types.is_string_dtype(
                df_clean[col]
            ):
                original = df_clean[col].copy()
                # Strip leading/trailing spaces
                df_clean[col] = df_clean[col].astype(str).str.strip()
                # Standardize common values
                if any(
                    x in col.lower()
                    for x in ["status", "category", "type", "genre", "sexe"]
                ):
                    # Title case for categorical columns
                    df_clean[col] = df_clean[col].str.title()

                changes = (original != df_clean[col]).sum()
                if changes > 0:
                    modifications.append(
                        f"✓ '{col}': {changes} valeurs normalisées (espaces, casse)"
                    )
                    logger.info(f"  Normalized {changes} values in '{col}'")

        # 9. PHONE STANDARDIZATION (convert to consistent format: 0X format for FR)
        logger.info("Step 9: PHONE STANDARDIZATION")
        phone_cols = [
            col
            for col in df_clean.columns
            if "phone" in col.lower() or "telephone" in col.lower()
        ]
        for col in phone_cols:
            if col in df_clean.columns:
                original_count = len(df_clean[col])
                standardized = []
                changes = 0

                for val in df_clean[col]:
                    if pd.isna(val) or str(val).strip() == "":
                        standardized.append(val)
                    else:
                        val_str = (
                            str(val)
                            .strip()
                            .replace(" ", "")
                            .replace("(", "")
                            .replace(")", "")
                            .replace("-", "")
                        )
                        # Convert to 0X format (French standard)
                        if val_str.startswith("33") and len(val_str) == 11:
                            standardized.append("0" + val_str[2:])
                            changes += 1
                        elif val_str.startswith("1") and len(val_str) == 10:
                            # US format: keep as is (or could convert)
                            standardized.append(val_str)
                        else:
                            standardized.append(val_str if len(val_str) > 0 else val)

                if changes > 0:
                    df_clean[col] = standardized
                    modifications.append(
                        f"✓ '{col}': {changes} numéros standardisés au format français"
                    )
                    logger.info(f"  Standardized {changes} phone numbers in '{col}'")

        # 10. LOGICAL CONSISTENCY CHECKS (date inversions, quantity/price conflicts)
        logger.info("Step 10: LOGICAL CONSISTENCY CHECKS")
        logical_issues = 0
        # Check for date inversions (delivery before order) with vectorized comparisons.
        order_date_cols = [
            c
            for c in df_clean.columns
            if "order_date" in c.lower() or "created" in c.lower()
        ]
        delivery_date_cols = [
            c
            for c in df_clean.columns
            if "delivery" in c.lower() or "shipped" in c.lower()
        ]

        if order_date_cols and delivery_date_cols:
            for ocol in order_date_cols:
                if ocol not in df_clean.columns:
                    continue
                odate = pd.to_datetime(df_clean[ocol], errors="coerce")
                for dcol in delivery_date_cols:
                    if dcol not in df_clean.columns:
                        continue
                    ddate = pd.to_datetime(df_clean[dcol], errors="coerce")
                    inversion_mask = odate.notna() & ddate.notna() & (ddate < odate)
                    swapped_count = int(inversion_mask.sum())
                    if swapped_count > 0:
                        df_clean.loc[inversion_mask, [ocol, dcol]] = df_clean.loc[
                            inversion_mask, [dcol, ocol]
                        ].to_numpy()
                        logical_issues += swapped_count
                        logger.info(
                            f"  Swapped {swapped_count} inverted dates between '{ocol}' and '{dcol}'"
                        )

        if logical_issues > 0:
            modifications.append(
                f"✓ {logical_issues} incohérences logiques corrigées (dates inversées)"
            )

        # 11. HARD BUSINESS RULES FOR SALES DATA
        logger.info("Step 11: SALES BUSINESS RULES")
        df_clean, business_rule_changes = enforce_sales_business_rules(df_clean)
        modifications.extend(business_rule_changes)

        # 12. OUTLIER DETECTION (statistical, for numeric columns)
        logger.info("Step 12: OUTLIER DETECTION")
        outlier_count = 0
        # EXCLUDE derived columns and business-rule columns from statistical outlier correction.
        # These values are intentionally bounded above by explicit domain rules.
        derived_cols = {
            "age",
            "customer_age",
            "full_name",
            "country",
            "quantity",
            "unit_price",
            "discount_percent",
        }
        for col in df_clean.columns:
            # Skip derived columns - they should not have outlier detection applied
            col_lower = str(col).lower()
            if (
                col in derived_cols
                or col_lower == "age"
                or col_lower.endswith("_age")
                or col_lower.startswith("age_")
                or col_lower == "quantity"
                or col_lower.endswith("_quantity")
                or "qty" in col_lower
                or col_lower == "unit_price"
                or col_lower.endswith("_price")
                or "discount" in col_lower
            ):
                logger.debug(f"  Skipping outlier detection for derived column '{col}'")
                continue

            if pd.api.types.is_numeric_dtype(df_clean[col]):
                try:
                    valid_vals = df_clean[col].dropna()
                    if len(valid_vals) < 4:
                        continue

                    Q1 = valid_vals.quantile(0.25)
                    Q3 = valid_vals.quantile(0.75)
                    IQR = Q3 - Q1

                    if IQR == 0:
                        logger.debug(
                            f"  IQR is 0 for '{col}', skipping outlier detection"
                        )
                        continue

                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR

                    outlier_mask = (df_clean[col] < lower_bound) | (
                        df_clean[col] > upper_bound
                    )
                    outlier_vals = int(outlier_mask.sum())

                    if outlier_vals > 0:
                        # For sensitive columns (weight, shipping_cost), do NOT replace outliers
                        col_lower = str(col).lower()
                        is_sensitive = any(x in col_lower for x in ["weight", "shipping_cost", "shipping", "poids"])
                        
                        if is_sensitive:
                            # Keep outliers as-is for sensitive columns; just log them
                            msg = f"ℹ️  '{col}': {outlier_vals} valeurs aberrantes détectées mais conservées (colonnes sensibles)"
                            modifications.append(msg)
                            logger.info(f"  {msg}")
                        else:
                            # Replace outliers with median for other numeric columns
                            median_val = valid_vals.median()
                            df_clean.loc[outlier_mask, col] = median_val
                            outlier_count += outlier_vals
                            msg = f"⚠️  '{col}': {outlier_vals} valeurs aberrantes détectées et corrigées (Q1={Q1:.2f}, Q3={Q3:.2f}, IQR={IQR:.2f})"
                            modifications.append(msg)
                            logger.info(f"  {msg}")
                except Exception as e:
                    logger.warning(f"  Error in outlier detection for '{col}': {e}")

            # FINAL GUARANTEE: keep one internal flagged frame for metrics,
            # but expose only the sanitized user-facing frame to the UI/export.
            df_with_flags = df_clean.copy()
            df_clean_display = prepare_user_facing_dataframe(df_with_flags)
            df_clean = df_clean_display.copy()

        # Calculate final stats based on flagged version (matches what users will see)
        final_size = len(df_with_flags)
        final_cols = len(df_with_flags.columns) - 1 if "__anomaly" in df_with_flags.columns else len(df_with_flags.columns)  # Don't count __anomaly in cols
        final_nulls = int(df_clean_display.isnull().sum().sum())
        final_duplicates = int(len(df_clean_display) - len(df_clean_display.drop_duplicates()))
        final_empty_cols = int((df_clean_display.isnull().sum() == len(df_clean_display)).sum())
        final_empty_rows = int(df_clean_display.isnull().all(axis=1).sum())

        # Calculate quality scores before/after cleaning
        quality_after = compute_quality_score(
            final_size,
            final_cols,
            final_nulls,
            final_empty_rows,
            final_empty_cols,
            final_duplicates,
            0,
        )

        quality_improvement = max(0.0, quality_after - quality_before)

        rows_removed = original_size - final_size
        cols_removed = original_cols - final_cols
        nulls_removed = original_nulls - final_nulls
        duplicates_removed = original_duplicates - final_duplicates

        # DEBUG: Log df_with_flags columns and shipment_id values
        if 'df_with_flags' in locals():
            logger.info(f"DEBUG: df_with_flags columns: {df_with_flags.columns.tolist()}")
            if 'shipment_id' in df_with_flags.columns:
                logger.info(f"DEBUG: df_with_flags['shipment_id'].head(5) = {df_with_flags['shipment_id'].head(5).tolist()}")
            else:
                logger.info(f"DEBUG: shipment_id NOT in df_with_flags columns!")

        # CRITICAL FIX: Restore identifier columns from original input if they were corrupted to datetime
        # shipment_id and similar columns can be mistakenly converted to datetime64[ns] by type detection
        # When this happens, string values become NaT (datetime null), losing the original data
        for id_col in ['shipment_id', 'order_id', 'id', 'client_id', 'customer_id']:
            if id_col in df_with_flags.columns and id_col in current_input_df.columns:
                if pd.api.types.is_datetime64_any_dtype(df_with_flags[id_col]):
                    logger.info(f"RESTORING {id_col}: Was converted to datetime64, restoring from original input")
                    df_with_flags[id_col] = current_input_df[id_col]

        # Store for export
        # Ensure money-like columns remain numeric: prefer values from pre-normalized dataframe
        for col in df_with_flags.columns:
            if looks_like_money_column(col):
                try:
                    if col in df_prepared.columns:
                        df_with_flags[col] = df_prepared[col]
                        logger.info(
                            f"Preserved money-like column '{col}' from pre-normalized data (dtype={df_with_flags[col].dtype})"
                        )
                    else:
                        df_with_flags[col] = pd.to_numeric(df_with_flags[col], errors="coerce")
                        logger.info(
                            f"Coerced money-like column '{col}' to numeric for export (dtype={df_with_flags[col].dtype})"
                        )
                except Exception as e:
                    logger.warning(
                        f"Could not preserve/coerce money-like column '{col}': {e}"
                    )

        # Restore essential identifier / financial columns if a downstream step
        # accidentally removed them from the cleaned frame.
        for col in df_prepared.columns:
            if col not in df_with_flags.columns and (
                looks_like_identifier_column(col) or looks_like_money_column(col)
            ):
                df_with_flags[col] = df_prepared[col]
                modifications.append(
                    f"✓ '{col}' restaurée depuis les données pré-nettoyées"
                )

        # Keep the original column order for shared columns, then append derived ones.
        ordered_cols = [col for col in df_prepared.columns if col in df_with_flags.columns]
        ordered_cols.extend(col for col in df_with_flags.columns if col not in df_prepared.columns)
        df_with_flags = df_with_flags[ordered_cols]

        # Log final dtypes for troubleshooting
        for col in df_with_flags.columns:
            if looks_like_money_column(col) or "total" in col.lower():
                logger.info(f"Final dtype for '{col}': {df_with_flags[col].dtype}")

        df_with_flags = restore_essential_columns(df_with_flags, current_input_df)
        current_df = prepare_user_facing_dataframe(df_with_flags)
        current_filename = file.filename
        current_run_id = str(uuid.uuid4())

        # Harmonize customer names by identifier using original input
        try:
            current_df = harmonize_customer_names_by_id(current_df, current_input_df)
            modifications.append("✓ customer_name harmonized by identifier where possible")
        except Exception as e:
            logger.warning(f"Failed to harmonize customer_name by id: {e}")

        # Mark exact duplicates instead of dropping them for metrics only.
        post_dup_before = len(df_with_flags)
        dup_mask = df_with_flags.duplicated(keep="first")
        if dup_mask.any():
            if "__anomaly" not in df_with_flags.columns:
                df_with_flags["__anomaly"] = False
            df_with_flags.loc[dup_mask, "__anomaly"] = True
            dropped = int(dup_mask.sum())
            modifications.append(f"⚠️ {dropped} lignes dupliquées marquées comme anomalies (lignes exactement identiques)")
        else:
            modifications.append("✓ Aucun doublon exact détecté après restauration des identifiants")

        current_df = prepare_user_facing_dataframe(df_with_flags)

        record_feedback(
            domain_detected,
            dataset_profile,
            llm_rules,
            ml_prediction,
            run_id=current_run_id,
        )

        logger.info(f"✓ Cleaning complete!")
        logger.info(
            f"  Original: {original_size} rows, {original_cols} cols, {original_nulls} nulls, {original_duplicates} dups"
        )
        logger.info(
            f"  Final: {final_size} rows, {final_cols} cols, {final_nulls} nulls"
        )
        logger.info(
            f"  Quality before: {quality_before:.1f}% | after: {quality_after:.1f}% | improvement: {quality_improvement:.1f}%"
        )

        # Build the full report for dashboards and internal inspection.
        response = {
            "status": "success",
            "run_id": current_run_id,
            "filename": file.filename,
            "message": "✅ Nettoyage automatique complété!",
            "quality_before": f"{quality_before:.1f}%",
            "quality_after": f"{quality_after:.1f}%",
            "quality_report": {
                "score_before": f"{quality_before:.1f}%",
                "score_after": f"{quality_after:.1f}%",
                "score_improvement": f"{quality_improvement:.1f}%",
                "before": quality_issues_before,
                "after": {
                    "null_cells": int(final_nulls),
                    "null_rate": f"{(final_nulls / (len(df_clean) * len(df_clean.columns)) * 100) if len(df_clean) > 0 else 0:.1f}%",
                    "empty_columns": int(final_empty_cols),
                    "empty_rows": int(final_empty_rows),
                    "duplicates": int(final_duplicates),
                    "duplicate_rate": f"{(final_duplicates / len(df_clean) * 100) if len(df_clean) > 0 else 0:.1f}%",
                },
                "improvements": {
                    "rows_removed": rows_removed,
                    "columns_removed": cols_removed,
                    "nulls_removed": nulls_removed,
                    "duplicates_removed": duplicates_removed,
                },
            },
            "modifications": modifications,
            "preview": {
                "before_sample": df.head(50).to_dict(orient="records"),
                "after_sample": (current_df.head(50).to_dict(orient="records") if current_df is not None else df_clean.head(50).to_dict(orient="records")),
                "removed_sample": (df_removed.head(50).to_dict(orient="records") if 'df_removed' in locals() else []),
                "anomaly_count": (int(df_with_flags['__anomaly'].sum()) if 'df_with_flags' in locals() and '__anomaly' in df_with_flags.columns else 0),
                "structure_comparison": {
                    "before": {
                        "rows": original_size,
                        "columns": original_cols,
                        "schema": {
                            col: str(dtype) for col, dtype in zip(df.columns, df.dtypes)
                        },
                    },
                    "after": {
                        "rows": final_size,
                        "columns": final_cols,
                        "schema": {
                            col: str(dtype)
                            for col, dtype in zip(df_clean.columns, df_clean.dtypes)
                        },
                    },
                    "after_with_flags": {
                        "rows": (len(df_with_flags) if 'df_with_flags' in locals() else final_size),
                        "columns": (len(current_df.columns) if 'current_df' in locals() else final_cols),
                    },
                },
            },
            "data_stats": {
                "original_size": original_size,
                "cleaned_size": final_size,
                "rows_cleaned": rows_removed,
                "rows_marked_anomalies": (int(df_with_flags['__anomaly'].sum()) if 'df_with_flags' in locals() and '__anomaly' in df_with_flags.columns else 0),
                "data_quality_before": f"{quality_before:.1f}%",
                "data_quality_after": f"{quality_after:.1f}%",
                "data_quality_improved_by": f"{quality_improvement:.1f}%",
            },
            "ml_insights": {
                "summary": ml_prediction.summary,
                "roles": ml_prediction.role_predictions,
                "actions": ml_prediction.action_predictions,
                "anomalies": ml_prediction.anomaly_scores,
                "llm_context": ml_context,
                "trained": bool(
                    getattr(hybrid_service, "meta", {}).get("trained_columns")
                ),
            },
            "domain_context": domain_context,
            "dataset_profile": {
                "domain_context": domain_context,
            },
        }

        # Store the full report in memory for dashboard access.
        current_report = response

        # Return a compact payload to keep the browser UI responsive.
        public_response = {
            "status": response["status"],
            "run_id": response["run_id"],
            "filename": response["filename"],
            "message": response["message"],
            "quality_before": response["quality_before"],
            "quality_after": response["quality_after"],
            "quality_report": response["quality_report"],
            "modifications": response["modifications"],
            "data_stats": response["data_stats"],
            "domain_context": response["domain_context"],
        }

        # Convert NumPy types to native Python types for JSON serialization
        return convert_types_to_native(public_response)

    except ValueError as ve:
        current_df = None
        current_filename = None
        current_report = None
        current_run_id = None
        current_input_df = None
        logger.error(f"Validation error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        current_df = None
        current_filename = None
        current_report = None
        current_run_id = None
        current_input_df = None
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.get("/last-report")
async def get_last_report():
    """Return the last execution report (if any)"""
    global current_report
    if current_report is None:
        raise HTTPException(status_code=404, detail="No report available")

    return convert_types_to_native(current_report)


@app.post("/retrain-ml")
async def retrain_ml(tune: bool = False, domain: str | None = None):
    """Trigger retraining of the hybrid ML models. If `tune` is true, run hyperparameter tuning."""
    try:
        hybrid_service = get_hybrid_ml_service(domain=domain)
        # Discover training files from workspace
        trainer = hybrid_service
        if tune:
            # Run tuning (may be slow)
            meta = trainer.tune_and_train_from_files()
            return {"status": "ok", "tuned": True, "meta": meta}
        else:
            meta = trainer.train_from_files()
            return {"status": "ok", "tuned": False, "meta": meta}
    except Exception as e:
        logger.exception("Retrain error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# EXPORT ROUTES
# ============================================================================


@app.post("/export-csv")
async def export_csv(run_id: str | None = None):
    """Export cleaned data as CSV"""
    global current_df, current_filename, current_run_id, current_input_df

    if current_df is None:
        raise HTTPException(status_code=400, detail="No data to export")

    if run_id and current_run_id and run_id != current_run_id:
        raise HTTPException(
            status_code=409,
            detail="Export session mismatch. Please re-run upload before exporting.",
        )

    try:
        export_df = restore_essential_columns(current_df, current_input_df)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = UPLOAD_DIR / f"cleaned_{timestamp}.csv"

        export_df.to_csv(output_path, index=False, encoding="utf-8")

        return FileResponse(
            path=output_path, filename=output_path.name, media_type="text/csv"
        )
    except Exception as e:
        logger.error(f"CSV export error: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur export: {str(e)}")


@app.post("/export-excel")
async def export_excel(run_id: str | None = None):
    """Export cleaned data as Excel"""
    global current_df, current_filename, current_run_id, current_input_df

    if current_df is None:
        raise HTTPException(status_code=400, detail="No data to export")

    if run_id and current_run_id and run_id != current_run_id:
        raise HTTPException(
            status_code=409,
            detail="Export session mismatch. Please re-run upload before exporting.",
        )

    try:
        export_df = restore_essential_columns(current_df, current_input_df)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = UPLOAD_DIR / f"cleaned_{timestamp}.xlsx"

        export_df.to_excel(output_path, index=False, na_rep="NaN")

        return FileResponse(
            path=output_path,
            filename=output_path.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        logger.error(f"Excel export error: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur export: {str(e)}")


# ============================================================================
# STARTUP
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
