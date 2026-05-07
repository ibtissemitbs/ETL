"""
Generate comprehensive test dataset for platform testing
with ALL data quality issues
"""

import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

np.random.seed(42)
random.seed(42)


def generate_platform_test_data(n_rows=10000):
    """Generate large dataset with all error types for platform testing"""

    data = {
        "transaction_id": [],
        "customer_name": [],
        "email": [],
        "phone": [],
        "order_date": [],
        "delivery_date": [],
        "product": [],
        "quantity": [],
        "unit_price": [],
        "total_amount": [],
        "status": [],
        "country": [],
        "postal_code": [],
    }

    products = [
        "Laptop",
        "Phone",
        "Tablet",
        "Monitor",
        "Keyboard",
        "Mouse",
        "Headphones",
    ]
    statuses = ["pending", "shipped", "delivered", "returned"]
    countries = ["FR", "US", "UK", "DE", "ES"]

    for i in range(n_rows):
        # TRANSACTION ID (type errors)
        if random.random() < 0.04:
            data["transaction_id"].append(f"TRX-{i}")
        else:
            data["transaction_id"].append(str(100000 + i))

        # CUSTOMER NAME (normalization issues)
        if random.random() < 0.08:
            names = ["  John Smith  ", "JOHN SMITH", "john smith", " john  smith"]
            data["customer_name"].append(random.choice(names))
        elif random.random() < 0.03:
            data["customer_name"].append("")
        else:
            data["customer_name"].append("John Smith")

        # EMAIL (missing)
        if random.random() < 0.05:
            data["email"].append("")
        else:
            data["email"].append(f"customer{i}@example.com")

        # PHONE (standardization)
        if random.random() < 0.10:
            formats = [
                f"33{random.randint(100000000, 999999999)}",
                f"0{random.randint(100000000, 999999999)}",
                f"+33 {random.randint(100000000, 999999999)}",
            ]
            data["phone"].append(random.choice(formats))
        elif random.random() < 0.05:
            data["phone"].append("N/A")
        else:
            data["phone"].append(f"0{random.randint(100000000, 999999999)}")

        # ORDER DATE vs DELIVERY DATE (logical inconsistency)
        order_date = datetime(2024, random.randint(1, 12), random.randint(1, 28))
        data["order_date"].append(order_date.strftime("%Y-%m-%d"))

        if random.random() < 0.06:  # Delivery BEFORE order
            delivery_date = order_date - timedelta(days=random.randint(1, 10))
            data["delivery_date"].append(delivery_date.strftime("%Y-%m-%d"))
        elif random.random() < 0.04:
            data["delivery_date"].append("2025-13-45")  # Impossible date
        elif random.random() < 0.05:
            data["delivery_date"].append("")
        else:
            delivery_date = order_date + timedelta(days=random.randint(1, 30))
            data["delivery_date"].append(delivery_date.strftime("%Y-%m-%d"))

        # PRODUCT (standardization)
        if random.random() < 0.08:
            data["product"].append(random.choice(products).lower())
        elif random.random() < 0.05:
            data["product"].append(random.choice(products).upper())
        elif random.random() < 0.03:
            data["product"].append("")
        else:
            data["product"].append(random.choice(products))

        # QUANTITY (type errors, logical)
        if random.random() < 0.05:
            data["quantity"].append(f"{random.randint(1, 100)}x")
        elif random.random() < 0.04:
            data["quantity"].append(str(random.randint(-5, 0)))
        elif random.random() < 0.04:
            data["quantity"].append("")
        else:
            data["quantity"].append(str(random.randint(1, 50)))

        # UNIT PRICE (type errors, outliers)
        if random.random() < 0.05:  # Outliers
            data["unit_price"].append(str(random.randint(1000, 99000)))
        elif random.random() < 0.04:
            data["unit_price"].append(f"${random.randint(1, 500)}")
        elif random.random() < 0.03:
            data["unit_price"].append(str(random.randint(-100, -1)))
        elif random.random() < 0.04:
            data["unit_price"].append("")
        else:
            data["unit_price"].append(str(random.randint(10, 500)))

        # TOTAL AMOUNT (logical inconsistency - should = qty*price)
        if random.random() < 0.08:
            data["total_amount"].append(str(random.randint(100, 50000)))
        elif random.random() < 0.04:
            data["total_amount"].append("")
        else:
            try:
                qty = int(str(data["quantity"][-1]).replace("x", ""))
                price = int(str(data["unit_price"][-1]).replace("$", ""))
                data["total_amount"].append(str(qty * price))
            except:
                data["total_amount"].append("0")

        # STATUS (normalization)
        if random.random() < 0.10:
            status_variants = ["pending", "PENDING", " pending ", "Pending", "pending "]
            data["status"].append(random.choice(status_variants))
        elif random.random() < 0.04:
            data["status"].append("Unknown")
        else:
            data["status"].append(random.choice(statuses))

        # COUNTRY (standardization)
        if random.random() < 0.06:
            country_variants = [
                random.choice(countries).lower(),
                random.choice(countries) + " ",
                " " + random.choice(countries),
            ]
            data["country"].append(random.choice(country_variants))
        elif random.random() < 0.04:
            data["country"].append("")
        else:
            data["country"].append(random.choice(countries))

        # POSTAL CODE (format issues)
        if random.random() < 0.06:
            data["postal_code"].append(f"{random.randint(10000, 99999)}")
        elif random.random() < 0.04:
            data["postal_code"].append("")
        else:
            data["postal_code"].append(f"{random.randint(75000, 75999)}")

    df = pd.DataFrame(data)

    # Add exact duplicates
    if len(df) > 50:
        dup_rows = df.iloc[:30].copy()
        df = pd.concat([df, dup_rows], ignore_index=True)

    return df


print("=" * 100)
print("GENERATING COMPREHENSIVE PLATFORM TEST DATA")
print("=" * 100)

df = generate_platform_test_data(10000)
output_file = "data/platform_test_data.csv"
df.to_csv(output_file, index=False)

print(f"\n✅ Generated: {output_file}")
print(f"   Rows: {len(df)}")
print(f"   Columns: {len(df.columns)}")

print(f"\n📋 Data Quality Issues:")
print(f"   • Type errors: ~4-5% in numeric columns")
print(f"   • Standardization issues: ~10% (phone, status, country formats)")
print(f"   • Normalization issues: ~8% (spaces, case)")
print(f"   • Missing values: ~5% across columns")
print(f"   • Logical inconsistencies: ~6-8% (delivery before order)")
print(f"   • Outliers: ~5% in unit_price (>1000)")
print(f"   • Duplicates: 30 exact rows added")

print(f"\n✓ Ready for platform testing!\n")
