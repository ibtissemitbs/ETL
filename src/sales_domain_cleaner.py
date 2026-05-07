"""
Domain-specific cleaning rules for Sales data.
Designed for datasets with columns:
order_id, customer_name, product, price, quantity, order_date, country
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class SalesDomainCleaner:
    """Specialized cleaner for sales transactional data."""

    VALID_PRODUCTS = ["Laptop", "Phone", "Tablet", "Mouse", "Keyboard"]

    VALID_COUNTRIES = ["USA", "France", "Tunisia", "Spain", "China"]

    @staticmethod
    def clean_sales_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        operations: Dict[str, object] = {}
        df = df.copy()

        # 1. Protect order_id and remove duplicates
        if "order_id" in df.columns:
            before = len(df)
            df = df.drop_duplicates(subset=["order_id"], keep="first")
            operations["duplicates_removed"] = before - len(df)

        # 2. Normalize text columns
        for col in ["customer_name", "product", "country"]:
            if col in df.columns:
                df[col] = df[col].astype("string").str.strip()

        # 3. Clean customer_name
        if "customer_name" in df.columns:
            invalid_names = (
                df["customer_name"].isna()
                | df["customer_name"].str.lower().isin(
                    ["", "abc", "invalid", "none", "nan", "null", "n/a"]
                )
            )

            operations["customer_name_filled_unknown"] = int(invalid_names.sum())
            df.loc[invalid_names, "customer_name"] = "Unknown"

        # 4. Validate product
        if "product" in df.columns:
            invalid_product = ~df["product"].isin(SalesDomainCleaner.VALID_PRODUCTS)
            operations["invalid_product"] = int(invalid_product.sum())

            df.loc[invalid_product, "product"] = pd.NA

            mode_product = df["product"].mode(dropna=True)
            if not mode_product.empty:
                df["product"] = df["product"].fillna(mode_product.iloc[0])

        # 5. Clean price: invalid / negative / empty -> NaN
        if "price" in df.columns:
            df["price"] = pd.to_numeric(df["price"], errors="coerce")

            negative_price = df["price"] < 0
            operations["negative_price_to_nan"] = int(negative_price.sum())

            df.loc[negative_price, "price"] = pd.NA
            operations["price_missing_or_invalid"] = int(df["price"].isna().sum())

        # 6. Clean quantity: invalid / <= 0 / empty -> NaN
        if "quantity" in df.columns:
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

            invalid_quantity = df["quantity"] <= 0
            operations["invalid_quantity_to_nan"] = int(invalid_quantity.sum())

            df.loc[invalid_quantity, "quantity"] = pd.NA
            operations["quantity_missing_or_invalid"] = int(df["quantity"].isna().sum())

        # 7. Normalize order_date
        if "order_date" in df.columns:
            df["order_date"] = pd.to_datetime(
                df["order_date"],
                errors="coerce",
                format="mixed"
            )
            df["order_date"] = df["order_date"].dt.strftime("%Y-%m-%d")
            operations["invalid_order_date"] = int(df["order_date"].isna().sum())

        # 8. Validate country
        if "country" in df.columns:
            invalid_country = ~df["country"].isin(SalesDomainCleaner.VALID_COUNTRIES)
            operations["invalid_country"] = int(invalid_country.sum())

            df.loc[invalid_country, "country"] = pd.NA

            mode_country = df["country"].mode(dropna=True)
            if not mode_country.empty:
                df["country"] = df["country"].fillna(mode_country.iloc[0])

        logger.info("Sales cleaning operations: %s", operations)

        return df, operations


def clean_sales_business_rules(df: pd.DataFrame) -> pd.DataFrame:
    """
    Simple wrapper used by the ETL pipeline.
    Returns only the cleaned DataFrame.
    """
    cleaned_df, _ = SalesDomainCleaner.clean_sales_data(df)
    return cleaned_df