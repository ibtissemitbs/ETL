"""
Generate EXTREMELY dirty sales dataset with maximum chaos and all possible errors.
This version has real data corruption, encoding issues, type chaos, and illogical data.
"""

import random
import string
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

NUM_ROWS = 15000
OUTPUT_FILE = "data/extremely_dirty_sales.csv"

np.random.seed(42)
random.seed(42)

print(f"Generating {NUM_ROWS} rows of EXTREMELY dirty sales data...")

data = {
    "order_id": [],
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
categories = ["Electronics", "Clothing", "Home", "Sports", "Books", "Furniture", "Toys"]
regions = ["North", "South", "East", "West", "Central"]
payment_statuses = ["Paid", "Pending", "Failed", "Refunded", "Cancelled"]

# Generate rows with EXTREME chaos
for i in range(NUM_ROWS):
    # Order ID - chaos: duplicates, mixed format, text, negative, huge numbers
    id_choice = random.random()
    if id_choice < 0.05:  # 5% duplicates from previous
        data["order_id"].append(data["order_id"][-1] if data["order_id"] else i)
    elif id_choice < 0.08:  # 3% completely crazy IDs
        data["order_id"].append(
            random.choice(["ABC123XYZ", "!!!!", "😀", "-999999", "99999999999"])
        )
    elif id_choice < 0.12:  # 4% negative/zero
        data["order_id"].append(random.choice([-5, -1, 0, 0, 0]))
    elif id_choice < 0.15:  # 3% malformed
        data["order_id"].append(f"ORD-{i}-{random.choice(['ERR', 'NULL', 'BAD'])}")
    else:
        data["order_id"].append(i)

    # Customer name - EXTREME chaos
    name_choice = random.random()
    if name_choice < 0.05:  # 5% empty
        data["customer_name"].append("")
    elif name_choice < 0.08:  # 3% unicode/special chars
        data["customer_name"].append(
            random.choice(["😀😀😀", "©®™", "████", "\n\n\n", "\t\t\t"])
        )
    elif name_choice < 0.12:  # 4% extremely wrong
        data["customer_name"].append(
            random.choice(
                [
                    "0000000",
                    "-----",
                    "null null null",
                    "".join(
                        random.choices(string.ascii_letters, k=50)
                    ),  # random 50 char string
                    "123456789",
                ]
            )
        )
    elif name_choice < 0.15:  # 3% mixed case chaos
        name = f"{random.choice(names)} {random.choice(last_names)}"
        data["customer_name"].append(
            "".join(random.choice([c.upper(), c.lower()]) for c in name)
        )
    elif name_choice < 0.20:  # 5% nullish tokens
        data["customer_name"].append(
            random.choice(
                ["N/A", "null", "na", "---", "?", "unknown", "UNKNOWN", "None"]
            )
        )
    elif name_choice < 0.25:  # 5% extreme whitespace
        name = f"{random.choice(names)} {random.choice(last_names)}"
        data["customer_name"].append(
            "   " + name + "   " + "".join([" " for _ in range(random.randint(5, 20))])
        )
    else:
        data["customer_name"].append(
            f"{random.choice(names)} {random.choice(last_names)}"
        )

    # Email - EXTREME corruption
    email_choice = random.random()
    if email_choice < 0.05:  # 5% empty
        data["email"].append("")
    elif email_choice < 0.08:  # 3% unicode garbage
        data["email"].append("".join(random.choices("©®™ñáéíóú", k=20)))
    elif email_choice < 0.12:  # 4% completely wrong
        data["email"].append(
            random.choice(["123456", "aaaaaa", "!!!!!!!", "@@@@@", "null@null"])
        )
    elif email_choice < 0.16:  # 4% multiple @ signs
        data["email"].append(f"user{i}@domain@domain@{random.randint(1, 1000)}.com")
    elif email_choice < 0.20:  # 4% SQL injection attempt style
        data["email"].append(f"'; DROP TABLE--@example.com")
    elif email_choice < 0.24:  # 4% weird but valid format
        data["email"].append(
            f"{random.choice(['...', '___', '---'])}{i}{random.choice(['...', '___', '---'])}@test.test.test.test"
        )
    elif email_choice < 0.28:  # 4% mixed case/symbols
        data["email"].append(f"UsEr_{i}@ExAmPlE.CoM")
    else:
        data["email"].append(f"user{i}@example.com")

    # Product category - wrong/chaotic
    cat_choice = random.random()
    if cat_choice < 0.05:  # 5% empty
        data["product_category"].append("")
    elif cat_choice < 0.08:  # 3% unicode/special
        data["product_category"].append(
            random.choice(["🎁🎀🎊", "████████", "////////"])
        )
    elif cat_choice < 0.12:  # 4% completely wrong
        data["product_category"].append(
            random.choice(
                ["INVALID_CAT_12345", "unknown", "other", "misc", "TODO", "FIX_ME"]
            )
        )
    elif cat_choice < 0.16:  # 4% numbers instead
        data["product_category"].append(str(random.randint(1, 100)))
    elif cat_choice < 0.20:  # 4% mixed case
        cat = random.choice(categories)
        data["product_category"].append(
            "".join(random.choice([c.upper(), c.lower()]) for c in cat)
        )
    elif cat_choice < 0.24:  # 4% multiple categories
        data["product_category"].append(
            f"{random.choice(categories)}/{random.choice(categories)}/{random.choice(categories)}"
        )
    else:
        data["product_category"].append(random.choice(categories))

    # Quantity - EXTREME chaos
    qty_choice = random.random()
    if qty_choice < 0.05:  # 5% empty
        data["quantity"].append("")
    elif qty_choice < 0.08:  # 3% huge negative
        data["quantity"].append(random.choice([-999999, -50000, -10]))
    elif qty_choice < 0.12:  # 4% impossibly large
        data["quantity"].append(random.choice([999999999, 99999999, 9999999]))
    elif qty_choice < 0.16:  # 4% text garbage
        data["quantity"].append(
            random.choice(["ABCDEF", "qwerty", "......", "null", "LOTS"])
        )
    elif qty_choice < 0.20:  # 4% float when int expected
        data["quantity"].append(round(random.uniform(0.1, 100.9), 3))
    elif qty_choice < 0.24:  # 4% mixed text/numbers
        data["quantity"].append(
            f"{random.randint(1, 100)}x{random.choice(string.ascii_letters)}"
        )
    else:
        data["quantity"].append(random.randint(1, 100))

    # Unit price - CHAOS
    price_choice = random.random()
    if price_choice < 0.05:  # 5% empty
        data["unit_price"].append("")
    elif price_choice < 0.08:  # 3% huge negative
        data["unit_price"].append(random.choice([-999999, -50000, -100.99]))
    elif price_choice < 0.12:  # 4% impossibly huge
        data["unit_price"].append(random.choice([99999999.99, 999999999.99, 1e10]))
    elif price_choice < 0.16:  # 4% text
        data["unit_price"].append(
            random.choice(["expensive", "FREE", "$$$", "MILLIONS"])
        )
    elif price_choice < 0.20:  # 4% with currency symbol
        data["unit_price"].append(f"${random.randint(1, 500)}.{random.randint(0, 99)}")
    elif price_choice < 0.24:  # 4% scientific notation mixed
        data["unit_price"].append(f"{random.uniform(1, 1000):.2e}")
    else:
        data["unit_price"].append(round(random.uniform(5, 500), 2))

    # Total amount - wrong calc
    total_choice = random.random()
    if total_choice < 0.08:  # 8% empty
        data["total_amount"].append("")
    elif total_choice < 0.12:  # 4% negative
        data["total_amount"].append(random.choice([-9999, -100, -0.01]))
    elif total_choice < 0.16:  # 4% wrong/inconsistent with qty*price
        data["total_amount"].append(random.choice([0, 0.01, 1]))
    elif total_choice < 0.20:  # 4% huge
        data["total_amount"].append(random.choice([999999999, 1e10, 1e15]))
    else:
        data["total_amount"].append(round(random.uniform(10, 5000), 2))

    # Order date - TEMPORAL CHAOS
    date_choice = random.random()
    if date_choice < 0.08:  # 8% empty
        data["order_date"].append("")
    elif date_choice < 0.12:  # 4% far future
        data["order_date"].append(
            random.choice(["2099-01-01", "9999-12-31", "2050-06-15"])
        )
    elif date_choice < 0.16:  # 4% ancient past
        data["order_date"].append(
            random.choice(["1900-01-01", "1850-06-15", "0001-01-01"])
        )
    elif date_choice < 0.20:  # 4% malformed dates
        data["order_date"].append(
            random.choice(
                ["2024-13-45", "2024/13/32", "32-12-2024", "99/99/9999", "2024-02-30"]
            )
        )
    elif date_choice < 0.24:  # 4% text garbage
        data["order_date"].append(
            random.choice(["yesterday", "ASAP", "TBD", "null", "unknown"])
        )
    elif date_choice < 0.28:  # 4% wrong separators
        days_ago = random.randint(0, 365)
        order_date = datetime.now() - timedelta(days=days_ago)
        sep = random.choice(["/", " ", "-", "_", "|"])
        data["order_date"].append(order_date.strftime(f"%Y{sep}%m{sep}%d"))
    else:
        days_ago = random.randint(0, 365)
        order_date = datetime.now() - timedelta(days=days_ago)
        data["order_date"].append(order_date.strftime("%Y-%m-%d"))

    # Delivery date - even more chaos
    deliv_choice = random.random()
    if deliv_choice < 0.08:  # 8% empty
        data["delivery_date"].append("")
    elif deliv_choice < 0.12:  # 4% far future
        data["delivery_date"].append(random.choice(["2099-12-31", "9999-01-01"]))
    elif deliv_choice < 0.16:  # 4% before order (impossible)
        data["delivery_date"].append(datetime.now().strftime("%Y-%m-%d"))
    elif deliv_choice < 0.20:  # 4% invalid format
        data["delivery_date"].append(
            random.choice(["13-13-2024", "TBA", "pending", "null"])
        )
    elif deliv_choice < 0.24:  # 4% timestamp chaos
        data["delivery_date"].append(
            f"{datetime.now().isoformat()}Z{random.randint(0, 1000)}"
        )
    else:
        days_after = random.randint(-30, 30)
        delivery_date = (
            datetime.now()
            - timedelta(days=random.randint(0, 365))
            + timedelta(days=days_after)
        )
        data["delivery_date"].append(delivery_date.strftime("%Y-%m-%d"))

    # Payment status - WRONG
    status_choice = random.random()
    if status_choice < 0.05:  # 5% empty
        data["payment_status"].append("")
    elif status_choice < 0.08:  # 3% completely wrong
        data["payment_status"].append(
            random.choice(["SUCCESS", "NOPE", "YESPLEASE", "ERROR_CODE_500"])
        )
    elif status_choice < 0.12:  # 4% mixed case chaos
        data["payment_status"].append(random.choice(["pAiD", "PeNdInG", "fAiLeD"]))
    elif status_choice < 0.16:  # 4% with extra spaces/symbols
        data["payment_status"].append(
            random.choice(["  Paid  ", " Pending ", "***Failed***"])
        )
    elif status_choice < 0.20:  # 4% numbers
        data["payment_status"].append(random.choice(["1", "0", "2", "999"]))
    else:
        data["payment_status"].append(random.choice(payment_statuses))

    # Region - confused
    region_choice = random.random()
    if region_choice < 0.05:  # 5% empty
        data["region"].append("")
    elif region_choice < 0.08:  # 3% complete garbage
        data["region"].append(random.choice(["XYZ", "123", "NOWHERE", "████"]))
    elif region_choice < 0.12:  # 4% unicode
        data["region"].append(random.choice(["🌍🌎🌏", "©®™", "─────"]))
    elif region_choice < 0.16:  # 4% mixed case
        region = random.choice(regions)
        data["region"].append(
            "".join(random.choice([c.upper(), c.lower()]) for c in region)
        )
    elif region_choice < 0.20:  # 4% extra spaces/symbols
        data["region"].append(
            random.choice(["  North  ", " South ", "***East***", "---West---"])
        )
    elif region_choice < 0.24:  # 4% coordinates
        data["region"].append(
            f"{random.uniform(-90, 90):.2f},{random.uniform(-180, 180):.2f}"
        )
    else:
        data["region"].append(random.choice(regions))

    # Discount percent - CHAOS
    disc_choice = random.random()
    if disc_choice < 0.05:  # 5% empty
        data["discount_percent"].append("")
    elif disc_choice < 0.08:  # 3% huge negative
        data["discount_percent"].append(random.choice([-999, -500, -100]))
    elif disc_choice < 0.12:  # 4% way over 100
        data["discount_percent"].append(random.choice([150, 500, 1000, 99999]))
    elif disc_choice < 0.16:  # 4% text
        data["discount_percent"].append(
            random.choice(["HUGE", "FREE", "DISCOUNT", "N/A"])
        )
    elif disc_choice < 0.20:  # 4% with % symbol
        data["discount_percent"].append(f"{random.randint(0, 150)}%")
    else:
        data["discount_percent"].append(round(random.uniform(0, 50), 2))

    # Customer age - NONSENSE
    age_choice = random.random()
    if age_choice < 0.05:  # 5% empty
        data["customer_age"].append("")
    elif age_choice < 0.08:  # 3% huge negative
        data["customer_age"].append(random.choice([-999, -200, -1]))
    elif age_choice < 0.12:  # 4% impossibly old
        data["customer_age"].append(random.choice([500, 999, 10000]))
    elif age_choice < 0.16:  # 4% zero/negative
        data["customer_age"].append(random.choice([0, -5, -50]))
    elif age_choice < 0.20:  # 4% text
        data["customer_age"].append(random.choice(["twenty", "UNKNOWN", "N/A", "---"]))
    elif age_choice < 0.24:  # 4% float
        data["customer_age"].append(round(random.uniform(18, 85), 3))
    else:
        data["customer_age"].append(random.randint(18, 85))

# Create DataFrame
df = pd.DataFrame(data)

# Add EXTREME duplicates (10% instead of 5%)
num_dup_rows = int(NUM_ROWS * 0.10)
if num_dup_rows > 0:
    dup_indices = np.random.choice(len(df), num_dup_rows, replace=True)
    dup_rows = df.iloc[dup_indices].copy()
    df = pd.concat([df, dup_rows], ignore_index=True)

# Shuffle
df = df.sample(frac=1).reset_index(drop=True)

# Save
df.to_csv(OUTPUT_FILE, index=False)

print(f"✓ Generated {len(df)} rows (including {len(df) - NUM_ROWS} duplicates)")
print(f"\n✓ EXTREME data quality issues included:")
print(f"   - Missing/null values (empty strings, null, N/A, unknown, etc.)")
print(f"   - Unicode/emoji/special characters (██, 😀, ©®™)")
print(f"   - Type CHAOS (strings in numeric columns, numbers in text)")
print(f"   - Impossibly large values (999999999, 1e10, 1e15)")
print(f"   - Huge negative values (-999999, -50000)")
print(f"   - Temporal chaos (year 9999, 1900, invalid dates)")
print(f"   - Contradictory logic (delivery before order, negative quantities/prices)")
print(f"   - Extreme case inconsistencies (pAiD, PeNdInG, fAiLeD)")
print(f"   - Whitespace chaos (random spaces before/after)")
print(f"   - SQL injection attempt strings")
print(f"   - Random 50-char garbage strings")
print(f"   - Multiple values concatenated (Electronics/Clothing/Books)")
print(f"   - Malformed dates (2024-13-45, 2024-02-30, 32-12-2024)")
print(f"   - Currency symbols and %  mixed in")
print(f"   - Complete row duplicates (~10%)")
print(f"\n✓ Saved to: {OUTPUT_FILE}")
print(f"\nUpload to ETL at: http://127.0.0.1:8000/etl")
