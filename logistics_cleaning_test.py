#!/usr/bin/env python3
"""
ETL CLEANING DEMO - LOGISTICS DATA TEST
Tests ETL cleaning workflow with real-world logistics dirty data
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from extract import load_file
    from llm_helper import get_transformation_rules
    from load import save_data
    from profiler import DataProfiler
    from transform import apply_llm_rules

    IMPORTS_OK = True
except ImportError as e:
    print(f"[WARNING] Import issue: {e}")
    IMPORTS_OK = False


def print_header(text):
    """Print formatted section header"""
    print(f"\n{'='*70}")
    print(f"{text:^70}")
    print(f"{'='*70}\n")


def print_section(text):
    """Print subsection"""
    print(f"\n{text}")
    print("-" * 70)


def load_logistics_data(filepath):
    """Load logistics dirty data from CSV"""
    print_section("LOADING LOGISTICS DATA")

    try:
        df = pd.read_csv(filepath)
        print(f"[LOADED] {filepath}")
        print(f"  - Rows: {len(df)}")
        print(f"  - Columns: {len(df.columns)}: {', '.join(df.columns)}")
        print(f"  - Size: {df.memory_usage(deep=True).sum() / 1024:.2f} KB")
        return df
    except Exception as e:
        print(f"[ERROR] Could not load data: {e}")
        return None


def analyze_logistics_quality(df):
    """Analyze data quality issues specific to logistics"""
    print_section("DATA QUALITY ANALYSIS - LOGISTICS DOMAIN")

    issues = {
        "null_by_column": {},
        "duplicates": 0,
        "invalid_dates": 0,
        "invalid_prices": 0,
        "invalid_quantities": 0,
        "invalid_statuses": 0,
        "data_issues": [],
    }

    print("\n[NULL VALUES BY COLUMN]:")
    for col in df.columns:
        nulls = df[col].isnull().sum()
        if nulls > 0:
            pct = (nulls / len(df)) * 100
            issues["null_by_column"][col] = nulls
            print(f"  - {col:20s}: {nulls:3d} nulls ({pct:5.1f}%)")

    # Check duplicates by order_id
    print("\n[DUPLICATES]:")
    dups = df.duplicated(subset=["order_id"], keep=False).sum()
    issues["duplicates"] = dups
    if dups > 0:
        print(f"  - Duplicate order IDs: {dups}")
        duplicate_ids = df[df.duplicated(subset=["order_id"], keep=False)][
            "order_id"
        ].unique()
        for oid in duplicate_ids:
            count = len(df[df["order_id"] == oid])
            print(f"    * Order {oid}: {count} times")

    # Check invalid dates
    print("\n[INVALID DATES]:")
    invalid_dates = 0
    for idx, val in df["delivery_date"].items():
        try:
            if pd.notna(val):
                pd.to_datetime(val)
        except:
            invalid_dates += 1
            print(f"  - Row {idx}: '{val}' (invalid)")
    issues["invalid_dates"] = invalid_dates

    # Check invalid prices
    print("\n[INVALID PRICES]:")
    invalid_prices = 0
    for idx, val in df["price"].items():
        try:
            if pd.notna(val):
                float(val)
                if float(val) < 0:
                    invalid_prices += 1
                    print(f"  - Row {idx}: {val} (negative)")
        except:
            invalid_prices += 1
            print(f"  - Row {idx}: '{val}' (non-numeric)")
    issues["invalid_prices"] = invalid_prices

    # Check invalid quantities
    print("\n[INVALID QUANTITIES]:")
    invalid_quantities = 0
    for idx, val in df["quantity"].items():
        try:
            if pd.notna(val):
                qty = int(float(val))
                if qty <= 0:
                    invalid_quantities += 1
                    print(f"  - Row {idx}: {val} (zero or negative)")
                elif qty > 500:
                    invalid_quantities += 1
                    print(f"  - Row {idx}: {val} (unrealistic)")
        except:
            invalid_quantities += 1
    issues["invalid_quantities"] = invalid_quantities

    # Check invalid statuses
    print("\n[INVALID STATUSES]:")
    valid_statuses = {"delivered", "returned", "pending", "cancelled"}
    invalid_statuses = 0
    for idx, val in df["status"].items():
        if pd.notna(val):
            if val.lower() not in valid_statuses and val.strip() != "":
                invalid_statuses += 1
                print(f"  - Row {idx}: '{val}' (unknown)")
        else:
            invalid_statuses += 1
    issues["invalid_statuses"] = invalid_statuses

    return issues


def demonstrate_llm_solutions():
    """Show LLM-recommended solutions for logistics data"""
    print_section("LLM-RECOMMENDED SOLUTIONS FOR LOGISTICS DATA")

    solutions = {
        "null_handling": [
            "customer_name: Use 'Unknown Customer' placeholder",
            "quantity: Remove rows (critical for order)",
            "price: Remove rows (critical for order)",
            "warehouse: Use most common warehouse (Tunis)",
            "city: Infer from warehouse location or use customer history",
            "delivery_date: Use order date + 5 days average",
            "status: Use 'pending' as default",
        ],
        "date_validation": [
            "Parse dates to YYYY-MM-DD format",
            "Validate month <= 12",
            "Validate day <= 31 (or month-specific)",
            "Replace invalid with null, then impute",
        ],
        "price_validation": [
            "Convert strings to float",
            "Ensure positive values",
            "Flag values outside reasonable range (1-5000 TND)",
        ],
        "quantity_validation": [
            "Convert to integer",
            "Ensure positive values (> 0)",
            "Flag unrealistic values (> 500 units per order)",
        ],
        "deduplication": [
            "Remove exact duplicates keeping first occurrence",
            "Strategy: Keep earliest order for duplicate IDs",
        ],
        "status_standardization": [
            "Standardize to: delivered, returned, pending, cancelled",
            "Convert to lowercase",
            "Empty values -> 'pending'",
        ],
    }

    for category, items in solutions.items():
        print(f"\n[{category.upper()}]:")
        for item in items:
            print(f"  - {item}")

    return solutions


def clean_logistics_data(df):
    """Apply cleaning transformations to logistics data"""
    print_section("APPLYING CLEANING TRANSFORMATIONS")

    df_clean = df.copy()
    transformations = []

    # 1. Remove rows with NULL quantity or price (critical fields)
    print("\n1. Removing rows with NULL quantity or price (critical fields)...")
    initial_rows = len(df_clean)
    df_clean = df_clean.dropna(subset=["quantity", "price"])
    rows_removed_critical = initial_rows - len(df_clean)
    if rows_removed_critical > 0:
        transformations.append(
            f"Removed {rows_removed_critical} rows with NULL quantity/price"
        )
        print(f"   [REMOVED] {rows_removed_critical} rows")

    # 2. Remove duplicate order IDs (keep first)
    print("\n2. Removing duplicate order IDs...")
    initial_rows = len(df_clean)
    df_clean = df_clean.drop_duplicates(subset=["order_id"], keep="first")
    dups_removed = initial_rows - len(df_clean)
    if dups_removed > 0:
        transformations.append(f"Removed {dups_removed} duplicate orders")
        print(f"   [REMOVED] {dups_removed} duplicates")

    # 3. Clean customer names
    print("\n3. Standardizing customer names...")
    df_clean["customer_name"] = df_clean["customer_name"].fillna("Unknown Customer")
    df_clean["customer_name"] = df_clean["customer_name"].str.strip().str.title()
    transformations.append("Standardized customer names: title case, trimmed")
    print(f"   [STANDARDIZED] Names")

    # 4. Fix warehouse NULL values
    print("\n4. Filling warehouse NULL values...")
    warehouse_mode = (
        df_clean[df_clean["warehouse"].notna()]["warehouse"].mode()[0]
        if len(df_clean[df_clean["warehouse"].notna()]) > 0
        else "Tunis"
    )
    df_clean["warehouse"] = df_clean["warehouse"].fillna(warehouse_mode)
    transformations.append(f"Filled warehouse NULLs with mode: {warehouse_mode}")
    print(f"   [FILLED] Using {warehouse_mode}")

    # 5. Fix city NULL values
    print("\n5. Fixing city NULL values...")
    # Try to match with warehouse or use default
    city_map = {"Tunis": "Tunis", "Sfax": "Sfax", "Sousse": "Sousse"}
    for idx in df_clean[df_clean["city"].isnull()].index:
        warehouse = df_clean.loc[idx, "warehouse"]
        df_clean.loc[idx, "city"] = city_map.get(warehouse, "Tunis")
    transformations.append("Filled city based on warehouse mapping")
    print(f"   [FILLED] City from warehouse")

    # 6. Fix delivery dates
    print("\n6. Validating and fixing delivery dates...")
    invalid_date_count = 0
    for idx, val in df_clean["delivery_date"].items():
        try:
            pd.to_datetime(val)
        except:
            df_clean.loc[idx, "delivery_date"] = pd.NaT
            invalid_date_count += 1
    if invalid_date_count > 0:
        transformations.append(f"Fixed {invalid_date_count} invalid dates")
        print(f"   [FIXED] {invalid_date_count} invalid dates")

    # 7. Convert quantity to integer, validate
    print("\n7. Converting and validating quantities...")
    qty_fixed = 0
    for idx, val in df_clean["quantity"].items():
        try:
            qty = int(float(val))
            if qty <= 0 or qty > 500:
                df_clean.loc[idx, "quantity"] = np.nan
                qty_fixed += 1
            else:
                df_clean.loc[idx, "quantity"] = qty
        except:
            df_clean.loc[idx, "quantity"] = np.nan
            qty_fixed += 1
    df_clean = df_clean.dropna(subset=["quantity"])
    transformations.append(f"Validated quantities, removed {qty_fixed} invalid")
    print(f"   [VALIDATED] {qty_fixed} quantities fixed/removed")

    # 8. Convert price to float, validate
    print("\n8. Converting and validating prices...")
    price_fixed = 0
    for idx, val in df_clean["price"].items():
        try:
            price = float(val)
            if price < 0 or price > 5000:
                df_clean.loc[idx, "price"] = np.nan
                price_fixed += 1
            else:
                df_clean.loc[idx, "price"] = price
        except:
            df_clean.loc[idx, "price"] = np.nan
            price_fixed += 1
    df_clean = df_clean.dropna(subset=["price"])
    transformations.append(f"Validated prices, removed {price_fixed} invalid")
    print(f"   [VALIDATED] {price_fixed} prices fixed/removed")

    # 9. Standardize status
    print("\n9. Standardizing status values...")
    status_lower = df_clean["status"].fillna("").str.lower()
    valid_statuses = ["delivered", "returned", "pending", "cancelled"]
    for idx, val in status_lower.items():
        if val not in valid_statuses:
            df_clean.loc[idx, "status"] = "pending"
    transformations.append(
        "Standardized status to: delivered, returned, pending, cancelled"
    )
    print(f"   [STANDARDIZED] Status values")

    # 10. Ensure date format consistency
    print("\n10. Ensuring date format consistency...")
    df_clean["delivery_date"] = pd.to_datetime(
        df_clean["delivery_date"], errors="coerce"
    )
    transformations.append("Standardized delivery_date to datetime format")
    print(f"   [STANDARDIZED] Date format")

    print(f"\n[TOTAL TRANSFORMATIONS] {len(transformations)} applied")
    return df_clean, transformations


def compare_before_after(dirty_df, clean_df):
    """Compare data quality before and after cleaning"""
    print_section("BEFORE & AFTER COMPARISON")

    comparison = {
        "before": {
            "rows": len(dirty_df),
            "null_cells": dirty_df.isnull().sum().sum(),
            "null_pct": (
                dirty_df.isnull().sum().sum()
                / (len(dirty_df) * len(dirty_df.columns))
                * 100
            ),
            "duplicate_rows": len(dirty_df)
            - len(dirty_df.drop_duplicates(subset=["order_id"])),
        },
        "after": {
            "rows": len(clean_df),
            "null_cells": clean_df.isnull().sum().sum(),
            "null_pct": (
                (
                    clean_df.isnull().sum().sum()
                    / (len(clean_df) * len(clean_df.columns))
                    * 100
                )
                if len(clean_df) > 0
                else 0
            ),
            "duplicate_rows": len(clean_df)
            - len(clean_df.drop_duplicates(subset=["order_id"])),
        },
    }

    print("\n[DATA QUALITY METRICS]\n")
    print(f"{'Metric':<30} {'Before':<20} {'After':<20}")
    print("-" * 70)

    metrics = [
        ("Orders", "rows"),
        ("Null Cells", "null_cells"),
        ("Null %", "null_pct"),
        ("Duplicates", "duplicate_rows"),
    ]

    for label, key in metrics:
        before = comparison["before"][key]
        after = comparison["after"][key]

        if isinstance(before, float):
            print(f"{label:<30} {before:<20.2f} {after:<20.2f}")
        else:
            print(f"{label:<30} {before:<20} {after:<20}")

    return comparison


def save_results(clean_df, comparison, transformations, issues):
    """Save cleaned data and report"""
    print_section("SAVING RESULTS")

    # Save cleaned data
    output_file = Path("data/processed/logistics_cleaned.csv")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(output_file, index=False)
    print(f"[SAVED] Cleaned data: {output_file}")
    print(f"        {len(clean_df)} rows, {len(clean_df.columns)} columns")

    # Save JSON report
    report = {
        "timestamp": datetime.now().isoformat(),
        "source": "logistics_dirty_test.csv",
        "data_quality": {
            "before": {
                k: int(v) if isinstance(v, (np.integer, np.floating)) else v
                for k, v in comparison["before"].items()
            },
            "after": {
                k: int(v) if isinstance(v, (np.integer, np.floating)) else v
                for k, v in comparison["after"].items()
            },
            "improvement": {
                "rows_removed": int(
                    comparison["before"]["rows"] - comparison["after"]["rows"]
                ),
                "nulls_removed": int(
                    comparison["before"]["null_cells"]
                    - comparison["after"]["null_cells"]
                ),
                "null_pct_improvement": float(
                    comparison["before"]["null_pct"] - comparison["after"]["null_pct"]
                ),
            },
        },
        "issues_found": {
            "null_by_column": {k: int(v) for k, v in issues["null_by_column"].items()},
            "duplicate_count": int(issues["duplicates"]),
            "invalid_dates": int(issues["invalid_dates"]),
            "invalid_prices": int(issues["invalid_prices"]),
            "invalid_quantities": int(issues["invalid_quantities"]),
            "invalid_statuses": int(issues["invalid_statuses"]),
        },
        "transformations_applied": transformations,
        "transformation_count": len(transformations),
    }

    report_file = (
        Path("reports/execution")
        / f"logistics_cleaning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[SAVED] Full report: {report_file}")

    return report_file


def main():
    """Main ETL cleaning workflow"""
    print_header("LOGISTICS DATA - ETL CLEANING TEST")
    print("Real-world logistics dirty data from Tunisia")

    # Load data
    logistics_file = Path("data/logistics_dirty_test.csv")
    if not logistics_file.exists():
        print(f"[ERROR] File not found: {logistics_file}")
        return

    df_dirty = load_logistics_data(logistics_file)
    if df_dirty is None:
        return

    # Analyze quality
    issues = analyze_logistics_quality(df_dirty)

    # Show LLM solutions
    solutions = demonstrate_llm_solutions()

    # Clean data
    df_clean, transformations = clean_logistics_data(df_dirty)

    # Compare
    comparison = compare_before_after(df_dirty, df_clean)

    # Save results
    report_file = save_results(df_clean, comparison, transformations, issues)

    # Summary
    print_header("FINAL SUMMARY")
    print(f"\nData Quality Improvements:")
    print(
        f"  - Orders: {comparison['before']['rows']} -> {comparison['after']['rows']} (-{comparison['before']['rows'] - comparison['after']['rows']})"
    )
    print(
        f"  - Null cells: {comparison['before']['null_cells']} -> {comparison['after']['null_cells']} (-{comparison['before']['null_cells'] - comparison['after']['null_cells']})"
    )
    print(
        f"  - Null %: {comparison['before']['null_pct']:.1f}% -> {comparison['after']['null_pct']:.1f}%"
    )
    print(f"\nTransformations Applied: {len(transformations)}")
    print(f"\nResults saved to:")
    print(f"  - Cleaned data: data/processed/logistics_cleaned.csv")
    print(f"  - Full report: {report_file}")
    print(f"\n[SUCCESS] Logistics Data Cleaning Complete!\n")


if __name__ == "__main__":
    main()
