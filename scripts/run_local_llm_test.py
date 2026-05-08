import json
import os
from pathlib import Path

import pandas as pd

from src.llm_helper import get_transformation_rules
from src.profiler import build_dataset_profile


SAMPLE_PATH = Path(__file__).resolve().parent.parent / "examples" / "sample_sales.csv"


def main() -> None:
    os.environ.setdefault("LLM_PROVIDER", "local")
    os.environ.setdefault("LLM_LOCAL_MODEL", "llama2")

    df = pd.read_csv(SAMPLE_PATH)
    profile = build_dataset_profile(df)
    rules = get_transformation_rules(
        profile,
        model=os.environ["LLM_LOCAL_MODEL"],
        use_cache=False,
        dataframe=df,
    )
    print(json.dumps(rules, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
