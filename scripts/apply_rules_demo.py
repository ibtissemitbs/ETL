import json
import os
import sys

import pandas as pd

sys.path.append(".")

os.environ["LLM_PROVIDER"] = "local"

from src.llm_helper import get_transformation_rules
from src.profiler import build_dataset_profile
from src.transform import apply_llm_rules

csv_path = "backend/uploads/logistics_dirty_test.csv"
if not os.path.exists(csv_path):
    raise FileNotFoundError(csv_path)

# Read original
df_orig = pd.read_csv(csv_path)
print("Original dataset shape:", df_orig.shape)
print("\nOriginal first 5 rows:")
print(df_orig.head(5))
print("\nOriginal dtypes:")
print(df_orig.dtypes)
print("\nOriginal null counts:")
print(df_orig.isnull().sum())

# Get profile and rules
profile = build_dataset_profile(df_orig)
rules = get_transformation_rules(
    profile, model="mistral:latest", use_cache=False, dataframe=df_orig
)

print("\n" + "=" * 80)
print("RULES GENERATED:")
print("=" * 80)
print(json.dumps(rules, indent=2, ensure_ascii=False))

# Apply rules
print("\n" + "=" * 80)
print("APPLYING RULES...")
print("=" * 80)
df_clean, applied_steps = apply_llm_rules(df_orig, rules)

print("\nTransformation steps applied:")
for step in applied_steps:
    print(f"  • {step}")

print("\nCleaned dataset shape:", df_clean.shape)
print("\nCleaned first 5 rows:")
print(df_clean.head(5))
print("\nCleaned dtypes:")
print(df_clean.dtypes)
print("\nCleaned null counts:")
print(df_clean.isnull().sum())

# Save cleaned version
output_path = "backend/uploads/logistics_cleaned_result.csv"
df_clean.to_csv(output_path, index=False)
print(f"\n✅ Cleaned dataset saved to: {output_path}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Rows: {len(df_orig)} → {len(df_clean)}")
print(f"Columns: {len(df_orig.columns)} → {len(df_clean.columns)}")
print(f"Total nulls: {df_orig.isnull().sum().sum()} → {df_clean.isnull().sum().sum()}")
