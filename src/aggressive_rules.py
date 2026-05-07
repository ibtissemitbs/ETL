"""Aggressive Business Rules for Data Cleaning Engine."""

from typing import Any, Dict, List

import pandas as pd


class AggressiveRulesEngine:
    """Applies aggressive, business-aware data quality rules."""

    FINANCIAL_KEYWORDS = ["price", "amount", "cost", "total", "salary"]
    DATE_KEYWORDS = ["date", "created", "updated", "birth", "time"]
    ID_KEYWORDS = ["id", "identifier", "uuid", "code", "ref"]
    QTY_KEYWORDS = ["qty", "quantity", "count", "volume"]

    @staticmethod
    def detect_type_mismatches(
        df: pd.DataFrame, profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Aggressively detect type mismatches in critical columns."""
        issues = []

        for col in profile.get("columns", []):
            col_name = col.get("name", "")
            if col_name not in df.columns:
                continue

            col_lower = col_name.lower()
            series = df[col_name]
            non_null = series.dropna()

            if len(non_null) == 0:
                continue

            numeric_ratio = float(
                pd.to_numeric(non_null, errors="coerce").notna().mean()
            )
            date_ratio = float(
                pd.to_datetime(non_null, errors="coerce", format="mixed").notna().mean()
            )

            # Financial columns MUST be numeric
            if any(kw in col_lower for kw in AggressiveRulesEngine.FINANCIAL_KEYWORDS):
                if numeric_ratio < 0.7:
                    issues.append(
                        {
                            "column": col_name,
                            "problem": f"Financial column stored as non-numeric ({numeric_ratio*100:.0f}% numeric)",
                            "action": "convert_type",
                            "severity": "critical",
                            "confidence": 0.92,
                        }
                    )

            # Date columns SHOULD be date-like
            if any(kw in col_lower for kw in AggressiveRulesEngine.DATE_KEYWORDS):
                if date_ratio < 0.6:
                    issues.append(
                        {
                            "column": col_name,
                            "problem": f"Date column format inconsistent ({date_ratio*100:.0f}% parseable)",
                            "action": "standardize_date",
                            "severity": "high",
                            "confidence": 0.88,
                        }
                    )

        return issues

    @staticmethod
    def detect_business_violations(
        df: pd.DataFrame, profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect violations of domain-specific business rules."""
        issues = []

        for col in profile.get("columns", []):
            col_name = col.get("name", "")
            if col_name not in df.columns:
                continue

            col_lower = col_name.lower()

            # Financial rules - no negatives
            if any(kw in col_lower for kw in AggressiveRulesEngine.FINANCIAL_KEYWORDS):
                series = pd.to_numeric(df[col_name], errors="coerce")
                neg_count = (series < 0).sum()
                if neg_count > 0:
                    pct = neg_count / len(series) * 100
                    issues.append(
                        {
                            "column": col_name,
                            "problem": f"Financial column has {pct:.1f}% negative values (invalid)",
                            "action": "mark_as_anomaly",
                            "severity": "high",
                            "confidence": 0.90,
                        }
                    )

            # Quantity/count rules - no negatives
            if any(kw in col_lower for kw in AggressiveRulesEngine.QTY_KEYWORDS):
                series = pd.to_numeric(df[col_name], errors="coerce")
                neg_count = (series < 0).sum()
                if neg_count > 0:
                    issues.append(
                        {
                            "column": col_name,
                            "problem": f"Quantity column has {(neg_count/len(series)*100):.1f}% negative values",
                            "action": "mark_as_anomaly",
                            "severity": "high",
                            "confidence": 0.92,
                        }
                    )

        return issues

    @staticmethod
    def detect_identifier_issues(
        df: pd.DataFrame, profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect duplicate and missing identifier issues."""
        issues = []

        for col in profile.get("columns", []):
            col_name = col.get("name", "")
            if col_name not in df.columns:
                continue

            col_lower = col_name.lower()

            if any(kw in col_lower for kw in AggressiveRulesEngine.ID_KEYWORDS):
                series = df[col_name]
                dup_count = series.duplicated().sum()
                null_count = series.isna().sum()

                if dup_count > 0:
                    issues.append(
                        {
                            "column": col_name,
                            "problem": f"Identifier column has {(dup_count/len(series)*100):.1f}% duplicates",
                            "action": "remove_duplicate",
                            "severity": "critical",
                            "confidence": 0.90,
                        }
                    )

                if null_count > 0:
                    issues.append(
                        {
                            "column": col_name,
                            "problem": f"Identifier column missing {null_count} values",
                            "action": "mark_as_anomaly",
                            "severity": "critical",
                            "confidence": 0.95,
                        }
                    )

        return issues

    @staticmethod
    def detect_date_anomalies(
        df: pd.DataFrame, profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect impossible/invalid dates."""
        issues = []

        for col in profile.get("columns", []):
            col_name = col.get("name", "")
            if col_name not in df.columns:
                continue

            col_lower = col_name.lower()

            if any(kw in col_lower for kw in AggressiveRulesEngine.DATE_KEYWORDS):
                try:
                    series = pd.to_datetime(df[col_name], errors="coerce")
                    non_null = series.dropna()
                    if len(non_null) == 0:
                        continue

                    today = pd.Timestamp.now()
                    future_dates = (non_null > today).sum()
                    old_dates = (non_null < pd.Timestamp("1900-01-01")).sum()

                    if future_dates > 0:
                        issues.append(
                            {
                                "column": col_name,
                                "problem": f"Date column has {future_dates} future dates (invalid)",
                                "action": "mark_as_anomaly",
                                "severity": "high",
                                "confidence": 0.95,
                            }
                        )

                    if old_dates > 0:
                        issues.append(
                            {
                                "column": col_name,
                                "problem": f"Date column has {old_dates} dates before 1900 (invalid)",
                                "action": "mark_as_anomaly",
                                "severity": "high",
                                "confidence": 0.90,
                            }
                        )
                except Exception:
                    pass

        return issues

    @staticmethod
    def generate_comprehensive_plan(
        df: pd.DataFrame, profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comprehensive aggressive cleaning plan."""
        all_issues = []

        # Run all detection engines
        all_issues.extend(AggressiveRulesEngine.detect_type_mismatches(df, profile))
        all_issues.extend(AggressiveRulesEngine.detect_business_violations(df, profile))
        all_issues.extend(AggressiveRulesEngine.detect_identifier_issues(df, profile))
        all_issues.extend(AggressiveRulesEngine.detect_date_anomalies(df, profile))

        # Convert issues to plan items
        plan = []
        seen = set()

        for issue in all_issues:
            key = (issue["column"], issue["action"])
            if key not in seen:
                seen.add(key)
                plan.append(
                    {
                        "column": issue["column"],
                        "problem": issue["problem"],
                        "action": issue["action"],
                        "confidence": issue["confidence"],
                        "priority": issue["severity"],
                    }
                )

        # Sort by severity then confidence
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        plan.sort(
            key=lambda x: (
                severity_order.get(x.get("priority", "low"), 3),
                -x.get("confidence", 0),
            )
        )

        return {
            "dataset_summary": {
                "dataset_type": "generic",
                "general_quality": (
                    "low" if len(plan) > 8 else "medium" if len(plan) > 2 else "high"
                ),
                "critical_issues": [
                    p["problem"] for p in plan if p.get("priority") == "critical"
                ][:5],
            },
            "plan": plan,
        }
