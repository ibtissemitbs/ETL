"""
Domain-specific cleaning rules for Logistics / Supply Chain data.
Designed for datasets with columns:
shipment_id, origin, destination, weight, shipping_cost, delivery_date, status
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class LogisticsDomainCleaner:
    """Specialized cleaner for logistics data."""

    VALID_ORIGINS = ["Tunisia", "USA", "China", "Germany", "Spain"]

    VALID_DESTINATIONS = [
        "France", "Italy", "UK", "Germany", "Spain", "China", "Tunisia", "USA"
    ]

    VALID_STATUS = ["Delivered", "Pending", "In Transit"]

    @staticmethod
    def clean_logistics_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        operations: Dict[str, object] = {}
        df = df.copy()

        # ensure anomaly helper columns exist so we can mark problematic rows instead of dropping them
        if "__anomaly" not in df.columns:
            df["__anomaly"] = False
        if "__anomaly_reasons" not in df.columns:
            df["__anomaly_reasons"] = ""

        # 1. Protect shipment_id and mark duplicates (non-destructive)
        if "shipment_id" in df.columns:
            before = len(df)
            dup_mask = df.duplicated(subset=["shipment_id"], keep="first")
            operations["duplicates_removed"] = int(dup_mask.sum())
            if dup_mask.any():
                df.loc[dup_mask, "__anomaly"] = True
                # append reason; keep existing reasons if any
                df.loc[dup_mask, "__anomaly_reasons"] = (
                    df.loc[dup_mask, "__anomaly_reasons"].astype(str).replace("nan", "") + ";duplicate_shipment_id"
                )

        # 2. Normalize text columns
        for col in ["origin", "destination", "status"]:
            if col in df.columns:
                df[col] = df[col].astype("string").str.strip()

        # 3. Validate origin
        if "origin" in df.columns:
            invalid_origin = ~df["origin"].isin(LogisticsDomainCleaner.VALID_ORIGINS)
            operations["invalid_origin"] = int(invalid_origin.sum())
            df.loc[invalid_origin, "origin"] = pd.NA

            mode_origin = df["origin"].mode(dropna=True)
            if not mode_origin.empty:
                df["origin"] = df["origin"].fillna(mode_origin.iloc[0])

        # 4. Validate destination
        if "destination" in df.columns:
            invalid_destination = ~df["destination"].isin(
                LogisticsDomainCleaner.VALID_DESTINATIONS
            )
            operations["invalid_destination"] = int(invalid_destination.sum())
            df.loc[invalid_destination, "destination"] = pd.NA

            mode_destination = df["destination"].mode(dropna=True)
            if not mode_destination.empty:
                df["destination"] = df["destination"].fillna(mode_destination.iloc[0])

        # 5. Clean weight: invalid / negative / empty -> NaN
        if "weight" in df.columns:
            df["weight"] = pd.to_numeric(df["weight"], errors="coerce")

            negative_weight = df["weight"] < 0
            operations["negative_weight_to_nan"] = int(negative_weight.sum())

            df.loc[negative_weight, "weight"] = pd.NA
            operations["weight_missing_or_invalid"] = int(df["weight"].isna().sum())

        # 6. Clean shipping_cost: invalid / negative / empty -> NaN
        if "shipping_cost" in df.columns:
            df["shipping_cost"] = pd.to_numeric(df["shipping_cost"], errors="coerce")

            negative_cost = df["shipping_cost"] < 0
            operations["negative_shipping_cost_to_nan"] = int(negative_cost.sum())

            df.loc[negative_cost, "shipping_cost"] = pd.NA
            operations["shipping_cost_missing_or_invalid"] = int(
                df["shipping_cost"].isna().sum()
            )

        # 7. Normalize delivery_date
        if "delivery_date" in df.columns:
            df["delivery_date"] = pd.to_datetime(
                df["delivery_date"],
                errors="coerce",
                format="mixed"
            )
            df["delivery_date"] = df["delivery_date"].dt.strftime("%Y-%m-%d")
            operations["invalid_delivery_date"] = int(df["delivery_date"].isna().sum())

        # 8. Validate status
        if "status" in df.columns:
            invalid_status = ~df["status"].isin(LogisticsDomainCleaner.VALID_STATUS)
            operations["invalid_status_defaulted"] = int(invalid_status.sum())

            df.loc[invalid_status, "status"] = "Pending"
            df["status"] = df["status"].fillna("Pending")

        logger.info("Logistics cleaning operations: %s", operations)

        df = df.drop(columns=["__anomaly", "__anomaly_reasons"], errors="ignore")

        return df, operations


def clean_logistics_business_rules(df: pd.DataFrame) -> pd.DataFrame:
    """
    Simple wrapper used by the ETL pipeline.
    Returns only the cleaned DataFrame.
    """
    cleaned_df, _ = LogisticsDomainCleaner.clean_logistics_data(df)
    return cleaned_df