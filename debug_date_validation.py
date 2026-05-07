"""Direct test of validate_dates function"""

from pathlib import Path

import pandas as pd

# Read the test file
df = pd.read_csv("data/test_missing_values.csv")

print("Sample date_naissance values from CSV:")
print(df["date_naissance"].head(30).tolist())
print("\n" + "=" * 80)

# Manually call validate_dates logic
test_values = df["date_naissance"].dropna().astype(str).values[:50]
print(f"Testing first 50 non-null date_naissance values:")

issues = {"impossible": 0, "future": 0, "too_old": 0, "invalid_text": 0}

for i, val in enumerate(test_values):
    val_str = str(val).strip().lower()
    print(f"{i:2}. '{val}' ", end="")

    # Text-based checks
    if any(
        txt in val_str
        for txt in ["invalid", "error", "date inconnue", "tbd", "todo", "?"]
    ):
        print("→ INVALID_TEXT")
        issues["invalid_text"] += 1
    # Check for impossible dates in YYYY-MM-DD format like "2000-00-00"
    elif "-" in val_str:
        parts = val_str.split("-")
        if len(parts) >= 3:
            try:
                month = int(parts[1])
                day = int(parts[2].split()[0])
                if month == 0 or day == 0 or month > 12 or day > 31:
                    print(f"→ IMPOSSIBLE (month={month}, day={day})")
                    issues["impossible"] += 1
                else:
                    print("→ OK")
            except:
                print("→ PARSE_ERROR")
        else:
            print("→ NOT_YYYY-MM-DD")
    else:
        print("→ NO_DASH")

print("\n" + "=" * 80)
print(f"SUMMARY:")
print(f"  Impossible dates: {issues['impossible']}")
print(f"  Future dates: {issues['future']}")
print(f"  Too old dates: {issues['too_old']}")
print(f"  Invalid text: {issues['invalid_text']}")
print(f"  Total problems: {sum(issues.values())}")
