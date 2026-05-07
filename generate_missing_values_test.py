"""
Generate test data with MANY missing values in genre and date_naissance columns.
This specifically tests the improvement in missing value detection.
"""

import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

NUM_ROWS = 10000
OUTPUT_FILE = "data/test_missing_values.csv"

np.random.seed(42)
random.seed(42)

print(
    f"Generating {NUM_ROWS} rows with HEAVY missing values in genre & date_naissance..."
)

data = {
    "id": list(range(1, NUM_ROWS + 1)),
    "nom": [],
    "prenom": [],
    "email": [],
    "genre": [],  # Will have 80%+ missing
    "date_naissance": [],  # Will have 70%+ missing
    "adresse": [],
    "ville": [],
    "code_postal": [],
    "telephone": [],
}

names_f = ["Alice", "Marie", "Sophie", "Claire", "Julie"]
names_m = ["Paul", "Jean", "Michel", "Pierre", "Luc"]
prenoms = ["Smith", "Johnson", "Williams", "Brown", "Jones"]
villes = ["Paris", "Lyon", "Marseille", "Toulouse", "Nice"]

for i in range(NUM_ROWS):
    # Normal columns
    gender = random.choice(["F", "M"])
    data["nom"].append(random.choice(prenoms))
    data["prenom"].append(random.choice(names_f if gender == "F" else names_m))
    data["email"].append(f"user{i}@example.com")
    data["adresse"].append(f"{random.randint(1, 999)} rue de la Paix")
    data["ville"].append(random.choice(villes))
    data["code_postal"].append(f"{random.randint(75000, 75999)}")
    data["telephone"].append(
        f"0{random.randint(1, 9)}{random.randint(10000000, 99999999)}"
    )

    # GENRE - 75% missing with various forms
    if random.random() < 0.75:
        missing_form = random.choice(
            [
                "",
                "N/A",
                "null",
                "NA",
                "na",
                "N/A",
                "none",
                "---",
                "?",
                "unknown",
                "GENRE",
                "Missing",
                "Invalid",
                "n/a",
                "ND",
                "TBD",
                "-",
            ]
        )
        data["genre"].append(missing_form)
    else:
        data["genre"].append(gender)

    # DATE_NAISSANCE - 70% missing with various forms
    if random.random() < 0.70:
        missing_form = random.choice(
            [
                "",
                "N/A",
                "null",
                "NA",
                "na",
                "none",
                "---",
                "?",
                "unknown",
                "Date inconnue",
                "DATE",
                "TBD",
                "-",
                "2000-00-00",
                "invalid",
            ]
        )
        data["date_naissance"].append(missing_form)
    else:
        days_ago = random.randint(365 * 18, 365 * 80)
        birth_date = datetime.now() - timedelta(days=days_ago)
        data["date_naissance"].append(birth_date.strftime("%Y-%m-%d"))

# Create DataFrame
df = pd.DataFrame(data)

# Save
df.to_csv(OUTPUT_FILE, index=False)

print(f"\n✓ Generated {len(df)} rows")
print(f"✓ Genre: ~75% missing with various nullish tokens")
print(f"✓ Date_naissance: ~70% missing with various nullish tokens")
print(f"✓ Saved to: {OUTPUT_FILE}")
print(f"\nUpload to ETL at: http://127.0.0.1:8000/etl")
