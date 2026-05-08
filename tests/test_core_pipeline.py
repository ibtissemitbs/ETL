import pandas as pd

from src.domain_context import build_domain_context
from src.llm_helper import get_transformation_rules
from src.profiler import build_dataset_profile
from src.sales_domain_cleaner import SalesDomainCleaner


def test_backend_app_imports():
    from backend.main import app

    assert app.title == "ETL Platform"


def test_sales_domain_cleaner_preserves_business_schema():
    df = pd.DataFrame(
        {
            "order_id": ["A1", "A1", "A2"],
            "customer_name": [" Alice ", "Alice", "invalid"],
            "product": ["Laptop", "Laptop", "Phone"],
            "price": ["10.5", "10.5", "-4"],
            "quantity": ["2", "2", "3"],
            "order_date": ["2026-01-02", "2026-01-02", "not-a-date"],
            "country": ["France", "France", "Tunisia"],
        }
    )

    cleaned, ops = SalesDomainCleaner.clean_sales_data(df)

    assert len(cleaned) == 2
    assert list(cleaned.columns) == list(df.columns)
    assert ops["duplicates_removed"] == 1
    assert cleaned.loc[cleaned["order_id"] == "A2", "price"].isna().all()


def test_large_dataset_uses_safe_fallback_rules(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "groq")

    df = pd.DataFrame(
        {
            "order_id": [f"O-{idx}" for idx in range(50000)],
            "customer_name": ["Alice"] * 50000,
            "price": [10.0] * 50000,
            "quantity": [1] * 50000,
            "order_date": ["2026-01-01"] * 50000,
            "country": ["France"] * 50000,
        }
    )
    profile = build_dataset_profile(df)
    rules = get_transformation_rules(profile, dataframe=df, use_cache=False)

    assert "plan" in rules
    assert isinstance(rules["plan"], list)


def test_domain_context_sales_override():
    df = pd.DataFrame({"order_id": ["A1"], "price": [10], "quantity": [2]})
    profile = build_dataset_profile(df)

    context = build_domain_context(profile, dataframe=df, domain_override="sales")

    assert context["domain"] == "sales"
