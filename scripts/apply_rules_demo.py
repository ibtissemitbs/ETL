from pathlib import Path

import pandas as pd

from src.llm_helper import get_transformation_rules
from src.profiler import build_dataset_profile
from src.transform import apply_llm_rules


SAMPLE_PATH = Path(__file__).resolve().parent.parent / "examples" / "sample_sales.csv"


def main() -> None:
    df = pd.read_csv(SAMPLE_PATH)
    profile = build_dataset_profile(df)
    rules = get_transformation_rules(profile, dataframe=df, use_cache=False)
    cleaned, steps = apply_llm_rules(df, rules, domain="sales")

    print("Original shape:", df.shape)
    print("Cleaned shape:", cleaned.shape)
    print("Applied steps:")
    for step in steps:
        print("-", step)


if __name__ == "__main__":
    main()
