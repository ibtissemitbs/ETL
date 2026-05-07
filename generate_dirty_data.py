"""
Generate large, dirty sales dataset with all possible data quality issues
for testing the ETL platform.
"""

import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Configuration
NUM_ROWS = 10000
OUTPUT_FILE = "data/dirty_sales_large.csv"

# Seeds for reproducibility
np.random.seed(42)
random.seed(42)

print(f"Generating {NUM_ROWS} rows of dirty sales data...")

# Base data generation
data = {
    "order_id": list(range(1, NUM_ROWS + 1)),
    "customer_name": [],
    "email": [],
    "product_category": [],
    "quantity": [],
    "unit_price": [],
    "total_amount": [],
    "order_date": [],
    "delivery_date": [],
    "payment_status": [],
    "region": [],
    "discount_percent": [],
    "customer_age": [],
}

# Names pool
names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry"]
last_names = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
]

# Categories
categories = ["Electronics", "Clothing", "Home", "Sports", "Books", "Furniture", "Toys"]

# Regions
regions = ["North", "South", "East", "West", "Central"]

# Payment statuses
payment_statuses = ["Paid", "Pending", "Failed", "Refunded", "Cancelled"]

# Generate rows with intentional errors
for i in range(NUM_ROWS):
    # Order ID - mostly good, some duplicates
    if i > 0 and random.random() < 0.05:  # 5% duplicates
        data["order_id"][i] = data["order_id"][i - 1]

    # Customer name - some empty, some with extra spaces, some with mixed case
    name_choice = random.random()
    if name_choice < 0.08:  # 8% missing
        data["customer_name"].append("")
    elif name_choice < 0.12:  # 4% nullish tokens
        data["customer_name"].append(random.choice(["N/A", "null", "na", "---", "?"]))
    elif name_choice < 0.15:  # 3% extra spaces/formatting issues
        name = f"{random.choice(names)}  {random.choice(last_names)}"  # double space
        data["customer_name"].append(name)
    else:
        data["customer_name"].append(
            f"{random.choice(names)} {random.choice(last_names)}"
        )

    # Email - some invalid, some missing, some duplicates
    email_choice = random.random()
    if email_choice < 0.1:  # 10% missing
        data["email"].append("")
    elif email_choice < 0.15:  # 5% invalid format
        data["email"].append(
            random.choice([f"user{i}", "email", "not.an.email", "@domain"])
        )
    elif email_choice < 0.2:  # 5% duplicates
        data["email"].append(f"user{random.randint(0, 100)}@example.com")
    else:
        data["email"].append(f"user{i}@example.com")

    # Product category - some invalid
    cat_choice = random.random()
    if cat_choice < 0.07:  # 7% missing/invalid
        data["product_category"].append(
            random.choice(["", "INVALID", "unknown", "null"])
        )
    else:
        data["product_category"].append(random.choice(categories))

    # Quantity - some negative, some text, some missing
    qty_choice = random.random()
    if qty_choice < 0.08:  # 8% problematic
        if random.random() < 0.5:
            data["quantity"].append(random.choice([-5, -1, 0]))  # negative/zero
        else:
            data["quantity"].append(
                random.choice(["abc", "text", "", "N/A"])
            )  # non-numeric
    else:
        data["quantity"].append(random.randint(1, 100))

    # Unit price - some negative, some impossibly large, some text
    price_choice = random.random()
    if price_choice < 0.08:  # 8% problematic
        if random.random() < 0.5:
            data["unit_price"].append(
                random.choice([-99.99, -10, 999999, 0])
            )  # out of range
        else:
            data["unit_price"].append(
                random.choice(["expensive", "", "N/A", "???"])
            )  # non-numeric
    else:
        data["unit_price"].append(round(random.uniform(5, 500), 2))

    # Total amount - often missing or wrong
    total_choice = random.random()
    if total_choice < 0.12:  # 12% missing/wrong
        data["total_amount"].append(random.choice(["", "N/A", "error", -50]))
    else:
        data["total_amount"].append(round(random.uniform(10, 5000), 2))

    # Order date - some future dates, some very old, some invalid format, some missing
    date_choice = random.random()
    if date_choice < 0.1:  # 10% problematic
        if random.random() < 0.4:
            data["order_date"].append("")  # missing
        elif random.random() < 0.3:
            data["order_date"].append(
                random.choice(["2099-01-01", "2050-12-31"])
            )  # future
        else:
            data["order_date"].append(
                random.choice(["invalid", "01/13/2024", "2024-13-01"])
            )  # invalid format
    else:
        days_ago = random.randint(0, 365)
        order_date = datetime.now() - timedelta(days=days_ago)
        data["order_date"].append(order_date.strftime("%Y-%m-%d"))

    # Delivery date - should be >= order date, but often violates this
    deliv_choice = random.random()
    if deliv_choice < 0.15:  # 15% problematic
        if random.random() < 0.3:
            data["delivery_date"].append("")  # missing
        elif random.random() < 0.4:
            data["delivery_date"].append("2099-01-01")  # future
        else:
            data["delivery_date"].append(
                random.choice(["N/A", "pending", "invalid"])
            )  # non-date
    else:
        # Some are before order_date (data quality issue)
        days_after = random.randint(-10, 30)
        delivery_date = (
            datetime.now()
            - timedelta(days=random.randint(0, 365))
            + timedelta(days=days_after)
        )
        data["delivery_date"].append(delivery_date.strftime("%Y-%m-%d"))

    # Payment status - some invalid values, some case mismatch
    status_choice = random.random()
    if status_choice < 0.08:  # 8% problematic
        data["payment_status"].append(
            random.choice(["", "UNKNOWN", "processing", "n/a"])
        )
    elif status_choice < 0.12:  # 4% case mismatch
        data["payment_status"].append(random.choice(["PAID", "pending", "FAILED"]))
    else:
        data["payment_status"].append(random.choice(payment_statuses))

    # Region - some invalid, some misspelled
    region_choice = random.random()
    if region_choice < 0.08:  # 8% problematic
        data["region"].append(
            random.choice(["", "Unknown", "north ", " South", "MIDDLE"])
        )
    else:
        data["region"].append(random.choice(regions))

    # Discount percent - some > 100, some negative, some text
    disc_choice = random.random()
    if disc_choice < 0.08:  # 8% problematic
        data["discount_percent"].append(random.choice([-10, 150, 999, ""]))
    else:
        data["discount_percent"].append(round(random.uniform(0, 50), 2))

    # Customer age - some too low/high, some text, some negative
    age_choice = random.random()
    if age_choice < 0.1:  # 10% problematic
        if random.random() < 0.5:
            data["customer_age"].append(
                random.choice([-5, -1, 0, 150, 200])
            )  # unrealistic
        else:
            data["customer_age"].append(
                random.choice(["N/A", "unknown", ""])
            )  # non-numeric
    else:
        data["customer_age"].append(random.randint(18, 85))

# Create DataFrame
df = pd.DataFrame(data)

# Add some completely duplicate rows (5% of data)
num_dup_rows = int(NUM_ROWS * 0.05)
if num_dup_rows > 0:
    dup_indices = np.random.choice(len(df), num_dup_rows, replace=True)
    dup_rows = df.iloc[dup_indices].copy()
    df = pd.concat([df, dup_rows], ignore_index=True)

# Shuffle rows to mix errors
df = df.sample(frac=1).reset_index(drop=True)

# Save to CSV
df.to_csv(OUTPUT_FILE, index=False)

print(f"✓ Generated {len(df)} rows (including {len(df) - NUM_ROWS} duplicates)")
print(f"✓ Data quality issues included:")
print(f"   - Missing/null values (various forms: '', 'N/A', 'null', 'na', 'nan', '?')")
print(f"   - Type mismatches (numeric columns with text, dates with invalid formats)")
print(f"   - Out-of-range values (negative prices, ages > 100, discounts > 100%)")
print(f"   - Future dates (order & delivery dates)")
print(f"   - Case inconsistencies (PAID vs Paid, north vs North)")
print(f"   - Whitespace issues (extra spaces in names and regions)")
print(f"   - Data logic violations (delivery before order, negative quantities)")
print(f"   - Complete row duplicates (~5%)")
print(f"\n✓ Saved to: {OUTPUT_FILE}")
print(f"\nTo test the platform, upload this file to the ETL interface:")
print(f"  1. Navigate to http://127.0.0.1:8000/etl")
print(f"  2. Upload {OUTPUT_FILE}")
print(f"  3. View cleaning results in the dashboard: http://127.0.0.1:8000/dashboard")
