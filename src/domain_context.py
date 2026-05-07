from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class DomainPack:
    domain: str
    label: str
    glossary: str
    rules: str
    examples: str


DOMAIN_PACKS: Dict[str, DomainPack] = {
    "logistics": DomainPack(
        domain="logistics",
        label="Logistics / Supply Chain",
        glossary="shipment, order, warehouse, delivery, route, carrier, tracking, dispatch",
        rules=(
            "Validate order and delivery dates, standardize warehouse and carrier names, "
            "treat codes and identifiers as stable keys, and preserve operational statuses."
        ),
        examples=(
            "order_id, shipment_date, delivery_date, warehouse_code, carrier_name, status, tracking_number"
        ),
    ),
    "sales": DomainPack(
        domain="sales",
        label="Sales / CRM",
        glossary="lead, opportunity, deal, revenue, customer, account, pipeline, conversion, region",
        rules=(
            "Normalize customer and account names, keep revenue fields numeric, standardize pipeline stages, "
            "and preserve deduplication keys like lead_id or deal_id."
        ),
        examples=(
            "lead_id, account_name, stage, revenue, close_date, region, customer_segment, owner"
        ),
    ),
}


def _safe_string(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip().lower()


def _score_domain(
    profile: Dict[str, Any], dataframe: Optional[pd.DataFrame] = None
) -> Tuple[str, int, Dict[str, int]]:
    """Return the best domain, its score, and all domain scores."""
    score = {name: 0 for name in DOMAIN_PACKS}

    tokens = []
    if "schema" in profile:
        for col in profile["schema"]:
            tokens.append(_safe_string(col.get("name", "")))
            tokens.append(_safe_string(col.get("type", "")))

    if "columns" in profile:
        for col in profile["columns"]:
            tokens.append(_safe_string(col.get("name", "")))
            for sample in col.get("sample_values", [])[:5]:
                tokens.append(_safe_string(sample))

    if dataframe is not None and not dataframe.empty:
        for column_name in dataframe.columns:
            tokens.append(_safe_string(column_name))
            sample_values = dataframe[column_name].dropna().astype(str).head(5).tolist()
            tokens.extend(_safe_string(value) for value in sample_values)

    joined = " ".join(tokens)

    keyword_map = {
        "logistics": [
            "shipment",
            "delivery",
            "warehouse",
            "tracking",
            "carrier",
            "dispatch",
            "order",
            "route",
        ],
        "sales": [
            "lead",
            "deal",
            "opportunity",
            "revenue",
            "crm",
            "pipeline",
            "customer",
            "account",
            "quota",
        ],
    }

    for domain, keywords in keyword_map.items():
        score[domain] += sum(1 for keyword in keywords if keyword in joined)

    if dataframe is not None and not dataframe.empty:
        column_names = " ".join(_safe_string(col) for col in dataframe.columns)
        if any(token in column_names for token in ["order_id", "shipment", "delivery"]):
            score["logistics"] += 2
        if any(
            token in column_names for token in ["revenue", "lead", "deal", "customer"]
        ):
            score["sales"] += 2
        # Only logistics/sales domain detection is supported.

        # Pivoted sales sheets often come with these structural markers.
        pivot_sales_markers = [
            "segment>>",
            "consumer total",
            "corporate total",
            "home office total",
            "unnamed:",
        ]
        if any(marker in column_names for marker in pivot_sales_markers):
            score["sales"] += 6

        # Strong evidence of CRM / sales segmentation.
        if any(
            marker in column_names
            for marker in ["consumer", "corporate", "home office"]
        ):
            score["sales"] += 3

    best_domain = max(score, key=score.get)
    if score[best_domain] == 0:
        return "generic", 0, score
    return best_domain, score[best_domain], score


def detect_domain(
    profile: Dict[str, Any], dataframe: Optional[pd.DataFrame] = None
) -> str:
    """Detect the most likely business domain from schema names and sample values."""
    best_domain, _, _ = _score_domain(profile, dataframe=dataframe)
    return best_domain


def get_domain_pack(domain: str) -> Optional[DomainPack]:
    return DOMAIN_PACKS.get(domain)


def build_domain_context(
    profile: Dict[str, Any],
    dataframe: Optional[pd.DataFrame] = None,
    domain_override: Optional[str] = None,
) -> Dict[str, Any]:
    domain, score, all_scores = _score_domain(profile, dataframe=dataframe)
    source = "auto"
    if domain_override:
        override = domain_override.strip().lower()
        if override in DOMAIN_PACKS:
            domain = override
            source = "manual"
            score = max(score, 1)
    pack = get_domain_pack(domain)

    if pack is None:
        return {
            "domain": "generic",
            "label": "Generic ETL",
            "glossary": "dataset, columns, values, cleaning, validation",
            "rules": "Use conservative transformations and preserve schema safety.",
            "examples": "id, date, status, value, name",
            "confidence": 0.0,
            "source": source,
            "scores": all_scores,
        }

    confidence = round(min(score / 8.0, 1.0), 2)
    return {
        "domain": pack.domain,
        "label": pack.label,
        "glossary": pack.glossary,
        "rules": pack.rules,
        "examples": pack.examples,
        "confidence": confidence,
        "source": source,
        "scores": all_scores,
    }


def format_domain_context(
    profile: Dict[str, Any],
    dataframe: Optional[pd.DataFrame] = None,
    domain_override: Optional[str] = None,
) -> str:
    context = build_domain_context(
        profile, dataframe=dataframe, domain_override=domain_override
    )
    return "\n".join(
        [
            "## DOMAIN CONTEXT",
            f"Detected domain: {context['label']}",
            f"Confidence: {context.get('confidence', 0.0)}",
            f"Source: {context.get('source', 'auto')}",
            f"Glossary: {context['glossary']}",
            f"Rules: {context['rules']}",
            f"Typical columns: {context['examples']}",
            "Use this context to adapt cleaning rules without overfitting or deleting business-critical fields.",
        ]
    )
