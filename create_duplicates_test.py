#!/usr/bin/env python3
"""Create a test file with explicit duplicates for testing anomaly flagging"""
import pandas as pd

# Create simple data with duplicates
data = {
    'shipment_id': [
        'SH-100', 'SH-101', 'SH-102',  # normal
        'SH-100',  # duplicate of first
        'SH-103', 'SH-101',  # normal and duplicate of second
        'SH-104', 'SH-102',  # normal and duplicate of third
    ],
    'origin': ['China', 'USA', 'Germany', 'China', 'Spain', 'USA', 'Italy', 'Germany'],
    'destination': ['France', 'UK', 'Spain', 'France', 'Italy', 'UK', 'Germany', 'Spain'],
    'weight': [10, 20, 15, 10, 25, 20, 18, 15],
    'shipping_cost': [50.5, 100.0, 75.25, 50.5, 85.75, 100.0, 120.0, 75.25],
    'delivery_date': [
        '2024-01-01', '2024-01-02', '2024-01-03',
        '2024-01-01', '2024-01-05', '2024-01-02',
        '2024-01-06', '2024-01-03'
    ],
    'status': ['Delivered', 'In Transit', 'Pending', 'Delivered', 'In Transit', 'In Transit', 'Pending', 'Pending'],
}

df = pd.DataFrame(data)
df.to_csv('test_with_duplicates.csv', index=False)
print(f"Created test_with_duplicates.csv with {len(df)} rows (5 exact duplicates expected)")
print(f"Duplicates: {len(df) - len(df.drop_duplicates())}")
print(df)
