"""
Generate comprehensive test data with ALL types of data quality issues:
1. Type errors (text in numeric columns)
2. Standardization issues (inconsistent phone, date formats)
3. Normalization issues (extra spaces, case inconsistency)
4. Duplicates
5. Logical inconsistencies (date inversions, quantity/price conflicts)
6. Missing values
7. Outliers
"""

import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Set seed for reproducibility
np.random.seed(42)
random.seed(42)


def generate_comprehensive_dirty_data(n_rows=5000):
    """Generate data with ALL types of errors"""

    data = {
        "order_id": [],
        "customer_name": [],
        "phone": [],
        "order_date": [],
        "delivery_date": [],
        "quantity": [],
        "unit_price": [],
        "total_amount": [],
        "product_category": [],
        "shipping_status": [],
    }

    for i in range(n_rows):
        # 1. ORDER ID (numeric, but introduce text sometimes)
        if random.random() < 0.05:  # 5% type errors
            data["order_id"].append(f"ORD-{i}")  # TEXT instead of number
        else:
            data["order_id"].append(str(1000 + i))

        # 2. CUSTOMER NAME (normalization issues)
        names = ["  John  ", "JOHN", "john", "John", "jOhN "]
        if random.random() < 0.08:
            data["customer_name"].append(
                random.choice(names)
            )  # Extra spaces, case issues
        elif random.random() < 0.05:
            data["customer_name"].append("")  # Missing
        else:
            data["customer_name"].append("John Doe" if i % 2 == 0 else "Jane Smith")

        # 3. PHONE (standardization issues - multiple formats)
        if random.random() < 0.1:  # 10% standardization issues
            formats = [
                f"33{random.randint(100000000, 999999999)}",  # +33 format
                f"0{random.randint(100000000, 999999999)}",  # 0X format
                f"{random.randint(1000000000, 9999999999)}",  # No format
                f"({random.randint(100, 999)}) {random.randint(100, 999)}-{random.randint(1000, 9999)}",  # US format
            ]
            data["phone"].append(random.choice(formats))
        elif random.random() < 0.05:
            data["phone"].append("N/A")  # Missing value variant
        else:
            data["phone"].append(f"0{random.randint(100000000, 999999999)}")

        # 4. ORDER DATE vs DELIVERY DATE (logical inconsistency)
        order_date = datetime(2024, random.randint(1, 12), random.randint(1, 28))
        data["order_date"].append(order_date.strftime("%Y-%m-%d"))

        if random.random() < 0.08:  # 8% logical errors - delivery before order!
            delivery_date = order_date - timedelta(days=random.randint(1, 10))
            data["delivery_date"].append(delivery_date.strftime("%Y-%m-%d"))
        elif random.random() < 0.03:
            data["delivery_date"].append("2025-13-45")  # Impossible date
        elif random.random() < 0.05:
            data["delivery_date"].append("")  # Missing
        else:
            delivery_date = order_date + timedelta(days=random.randint(1, 30))
            data["delivery_date"].append(delivery_date.strftime("%Y-%m-%d"))

        # 5. QUANTITY (numeric - introduce type errors and logical issues)
        if random.random() < 0.07:  # 7% type errors in numeric
            data["quantity"].append(f"{random.randint(1, 100)}pcs")  # Text attached
        elif random.random() < 0.05:  # 5% negative or zero (logical error)
            data["quantity"].append(str(random.randint(-10, 0)))
        elif random.random() < 0.05:
            data["quantity"].append("N/A")  # Missing
        else:
            data["quantity"].append(str(random.randint(1, 100)))

        # 6. UNIT PRICE (numeric with outliers and type errors)
        if random.random() < 0.05:  # 5% outliers
            data["unit_price"].append(
                str(random.randint(1000, 50000))
            )  # Extremely high
        elif random.random() < 0.06:  # 6% type errors
            data["unit_price"].append(f"${random.randint(1, 500)}")  # Currency symbol
        elif random.random() < 0.04:  # 4% negative (logical)
            data["unit_price"].append(str(-random.randint(1, 500)))
        elif random.random() < 0.05:
            data["unit_price"].append("")  # Missing
        else:
            data["unit_price"].append(str(random.randint(10, 500)))

        # 7. TOTAL AMOUNT (should equal quantity * unit_price - introduce inconsistencies)
        if random.random() < 0.10:  # 10% logical inconsistencies
            data["total_amount"].append(
                str(random.randint(100, 50000))
            )  # Random, not qty*price
        elif random.random() < 0.05:
            data["total_amount"].append("")  # Missing
        else:
            try:
                qty = int(str(data["quantity"][-1]).replace("pcs", ""))
                price = int(str(data["unit_price"][-1]).replace("$", ""))
                data["total_amount"].append(str(qty * price))
            except:
                data["total_amount"].append("0")

        # 8. PRODUCT CATEGORY (standardization + duplication)
        if random.random() < 0.12:  # 12% standardization issues
            categories = [
                "Electronics",
                " Electronics ",  # Extra spaces
                "ELECTRONICS",  # All caps
                "electronics",  # All lowercase
                "Electro­nics",  # With special char
            ]
            data["product_category"].append(random.choice(categories))
        elif random.random() < 0.05:
            data["product_category"].append("")  # Missing
        else:
            data["product_category"].append(
                random.choice(["Electronics", "Clothing", "Food", "Books"])
            )

        # 9. SHIPPING STATUS (normalization)
        if random.random() < 0.10:  # 10% normalization issues
            statuses = [
                "pending",
                " PENDING",
                "Pending ",
                "PENDING",
                "pending ",
            ]
            data["shipping_status"].append(random.choice(statuses))
        elif random.random() < 0.05:
            data["shipping_status"].append("Unknown Status")  # Invalid
        else:
            data["shipping_status"].append(
                random.choice(["pending", "shipped", "delivered"])
            )

    df = pd.DataFrame(data)

    # Add DUPLICATES (exact and partial)
    if len(df) > 10:
        dup_rows = df.iloc[:10].copy()
        df = pd.concat([df, dup_rows], ignore_index=True)

    return df


# Generate and save
df = generate_comprehensive_dirty_data(5000)
output_file = "data/comprehensive_dirty_data.csv"
df.to_csv(output_file, index=False)

print("=" * 80)
print("COMPREHENSIVE TEST DATA GENERATED")
print("=" * 80)
print(f"✓ File: {output_file}")
print(f"✓ Rows: {len(df)}")
print(f"\nData Quality Issues Included:")
print(f"  1. Type Errors: ~5-7% in order_id, quantity, unit_price")
print(f"  2. Standardization Issues: ~10-12% phone, category, status")
print(f"  3. Normalization Issues: ~8-10% names (spaces, case)")
print(f"  4. Missing Values: ~5% in various columns")
print(
    f"  5. Logical Inconsistencies: ~8-10% (delivery before order, qty/price conflicts)"
)
print(f"  6. Outliers: ~5% in unit_price (extremely high)")
print(f"  7. Duplicates: 10 exact duplicate rows added")
print(f"\nSample rows:")
print(df.head(15))
print(f"\nUnique values per column:")
for col in df.columns:
    print(f"  {col}: {df[col].nunique()} unique values")
