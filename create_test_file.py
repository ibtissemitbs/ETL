import pandas as pd
from datetime import datetime, timedelta
import random

# Create valid logistics data with some issues to clean
random.seed(42)
base_date = datetime(2024, 1, 1)

data = {
    'shipment_id': [f'SH-{1000+i}' for i in range(20)],
    'origin': ['China', 'USA', 'Germany', 'Spain', 'Italy'] * 4,
    'destination': ['France', 'UK', 'Germany', 'Italy', 'Spain'] * 4,
    'weight': [random.uniform(5, 100) for _ in range(20)],
    'shipping_cost': [random.uniform(10, 500) for _ in range(20)],
    'delivery_date': [base_date + timedelta(days=random.randint(1, 60)) for _ in range(20)],
    'status': ['In Transit', 'Delivered', 'Pending', 'In Transit', 'Delivered'] * 4,
}

# Introduce some realistic data quality issues
df = pd.DataFrame(data)

# Add some missing values and inconsistencies
df.loc[2, 'weight'] = None
df.loc[5, 'shipping_cost'] = 'Invalid'
df.loc[8, 'delivery_date'] = 'not a date'
df.loc[11, 'status'] = 'DELIVERED'  # wrong case
df.loc[15, 'weight'] = '  45.6  '  # extra spaces

# Save as Excel
df.to_excel('test_logistics_clean.xlsx', index=False)
print(f"Created test_logistics_clean.xlsx with {len(df)} rows")
print(f"Shape: {df.shape}")
print(df.head())
